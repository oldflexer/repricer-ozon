import streamlit as st
from pathlib import Path
from config.settings import settings, TIMEZONE
from ui.cache import get_repo, get_api_client, get_excel_loader, get_mail_notifier
from core.use_cases import RepricingUseCase
import asyncio
from typing import Dict, Any


def run_repricing(dry_run: bool = False) -> Dict[str, Any]:
    async def _run():
        loader = get_excel_loader()
        api = get_api_client()
        notifier = get_mail_notifier()
        repo = get_repo()
        use_case = RepricingUseCase(repo, api, notifier, loader)
        try:
            stats = await use_case.execute(dry_run=dry_run)
        finally:
            await api.close()
        return stats
    return asyncio.run(_run())


def execute_repricing(dry_run: bool):
    with st.status("🔄 Выполняется репрайсинг...", expanded=True) as status:
        st.write("📂 Загрузка данных из Excel...")
        try:
            stats = run_repricing(dry_run=dry_run)
            st.cache_data.clear()
            st.cache_resource.clear()
            status.update(label="✅ Готово!", state="complete")
            if dry_run:
                msg = f"✅ Dry run завершён. Обработано товаров: {stats.get('products_loaded', 0)}, рассчитано цен: {stats.get('prices_updated', 0)}"
            else:
                updated = stats.get('prices_updated', 0)
                errors = stats.get('errors', [])
                msg = f"✅ Готово! Обновлено цен: {updated}"
                if errors:
                    msg += f"\n⚠️ Ошибки: {', '.join(errors)}"
            warnings = stats.get('warnings', [])
            if warnings:
                with st.expander("⚠️ Предупреждения при загрузке Excel"):
                    for w in warnings:
                        st.warning(w)
            return msg, 'success'
        except Exception as e:
            status.update(label="❌ Ошибка", state="error")
            return f"❌ Ошибка: {e}", 'error'
        finally:
            st.session_state.running = False


def render_sidebar_section(disabled: bool):
    repo = get_repo()
    st.divider()
    st.subheader("🧮 Работа с Excel")
    if disabled:
        st.info("⛔ Загрузка Excel недоступна во время выполнения репрайсинга")
        if settings.DATA_FILE.exists():
            with open(settings.DATA_FILE, "rb") as f:
                st.download_button(
                    "📥 Скачать текущий Excel", f,
                    file_name=settings.DATA_FILE.name,
                    width="stretch", disabled=True
                )
    else:
        try:
            uploaded_file = st.file_uploader(
                "Выберите Excel файл", type=["xlsx"],
                label_visibility="collapsed", width="stretch", key="excel_uploader"
            )
            if uploaded_file is not None:
                with open(settings.DATA_FILE, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                st.success(f"✅ Файл загружен: {settings.DATA_FILE.name}")
                st.cache_data.clear()
                st.cache_resource.clear()
        except Exception as e:
            st.error(f"Ошибка при загрузке файла: {e}")
        if settings.DATA_FILE.exists():
            with open(settings.DATA_FILE, "rb") as f:
                st.download_button(
                    "📥 Скачать текущий Excel", f,
                    file_name=settings.DATA_FILE.name,
                    width="stretch"
                )
        else:
            st.warning("Файл Excel пока не существует.")

    st.divider()
    st.subheader("🗃️ Работа с БД")
    db_data = open(settings.DATABASE_PATH, "rb").read() if settings.DATABASE_PATH.exists() else b""
    st.download_button(
        "💾 Скачать БД", data=db_data,
        file_name=settings.DATABASE_PATH.name,
        mime="application/octet-stream",
        use_container_width=True,
        disabled=disabled
    )
    if disabled:
        st.button("🧹 Удалить записи старше 1 месяца", width="stretch", disabled=True)
    else:
        if st.button("🧹 Удалить записи старше 1 месяца", width="stretch"):
            try:
                deleted = repo.delete_old_records(days=30)
                st.success(f"Удалено записей: {deleted}")
                st.cache_data.clear()
            except Exception as e:
                st.error(f"Ошибка при удалении: {e}")

    last_cleanup = repo.get_last_cleanup_date()
    if last_cleanup:
        last_cleanup_msk = last_cleanup.astimezone(TIMEZONE)
        st.caption(f"🗑️ Последняя очистка БД: {last_cleanup_msk.strftime('%Y-%m-%d %H:%M')}")

    st.divider()
    st.caption(f"Файл данных: {settings.DATA_FILE.resolve()}")
    st.caption(f"База данных: {settings.DATABASE_PATH.resolve()}")


def display_last_run():
    repo = get_repo()
    last_run_utc = repo.get_last_run_time()
    st.header("🕒 Последний запуск (МСК)")
    if last_run_utc:
        last_run_msk = last_run_utc.astimezone(TIMEZONE)
        st.metric("🕒 Последний запуск (МСК)", last_run_msk.strftime("%Y-%m-%d %H:%M"), label_visibility="collapsed")
    else:
        st.metric("🕒 Последний запуск (МСК)", "—", label_visibility="collapsed")


def render_sidebar():
    st.header("📄 Страница")
    page = st.radio(
        "📄 Страница",
        options=["Сводка", "Статистика", "Аналитика", "Анализ", "Таблицы", "Запросы", "Сервис"],
        index=0,
        horizontal=True,
        label_visibility="collapsed"
    )
    st.session_state['current_page'] = page

    st.divider()
    st.header("🎛️ Управление")

    if st.session_state.get('result_message'):
        if st.session_state.get('result_type') == 'success':
            st.success(st.session_state.result_message)
        else:
            st.error(st.session_state.result_message)
        st.session_state.result_message = None
        st.session_state.result_type = None

    if st.session_state.get('running'):
        msg, msg_type = execute_repricing(st.session_state.dry_run_mode)
        st.session_state.result_message = msg
        st.session_state.result_type = msg_type
        st.rerun()

    if st.session_state.get('running'):
        st.warning("⏳ Репрайсинг выполняется. Пожалуйста, подождите...")
        st.button("🚀 Полный цикл", type="primary", width="stretch", disabled=True)
        st.button("📝 Dry run", width="stretch", disabled=True)
        st.divider()
        display_last_run()
        render_sidebar_section(disabled=True)
    else:
        if st.button("🚀 Полный цикл (отправка цен)", type="primary", width="stretch"):
            st.session_state.running = True
            st.session_state.dry_run_mode = False
            st.rerun()
        if st.button("📝 Dry run (без отправки)", width="stretch"):
            st.session_state.running = True
            st.session_state.dry_run_mode = True
            st.rerun()
        st.divider()
        display_last_run()
        render_sidebar_section(disabled=False)

    # Изменение пароля
    with st.expander("🔐 Изменить пароль"):
        new_password = st.text_input("Новый пароль", type="password", key="new_pass")
        confirm_password = st.text_input("Подтвердите пароль", type="password", key="confirm_pass")
        if st.button("Сохранить пароль", use_container_width=True):
            if new_password and new_password == confirm_password:
                env_path = Path(__file__).parent.parent / ".env"
                if env_path.exists():
                    with open(env_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    with open(env_path, "w", encoding="utf-8") as f:
                        for line in lines:
                            if line.startswith("WEB_PASS="):
                                f.write(f"WEB_PASS={new_password}\n")
                            else:
                                f.write(line)
                    settings.WEB_PASS = new_password
                    st.success("✅ Пароль изменён. При следующем входе используйте новый пароль.")
                else:
                    st.error("Файл .env не найден")
            else:
                st.error("Пароли не совпадают или пусты")

    st.divider()
    if st.button("🚪 Выйти", width="stretch"):
        st.session_state.authenticated = False
        st.session_state.running = False
        st.session_state.result_message = None
        st.session_state.result_type = None
        st.rerun()