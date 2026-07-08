import base64
import streamlit as st
from pathlib import Path
from config.settings import settings
from ui.cache import get_repo, get_api_client, get_excel_loader, get_mail_notifier
from core.use_cases import RepricingUseCase
import asyncio
from typing import Dict, Any


def get_base64_encoded_image(image_path: Path) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


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
    with st.status("Выполняется репрайсинг...", expanded=True) as status:
        st.write("Загрузка данных из Excel...")
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


def render_sidebar_section_excel(disabled: bool):
    """Только секция работы с Excel (загрузка/скачивание)"""
    if disabled:
        st.info("Загрузка Excel недоступна во время выполнения репрайсинга")
        if settings.DATA_FILE.exists():
            with open(settings.DATA_FILE, "rb") as f:
                st.download_button(
                    "Скачать текущий Excel", f,
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
                    "Скачать текущий Excel", f,
                    file_name=settings.DATA_FILE.name,
                    width="stretch"
                )
        else:
            st.warning("Файл Excel пока не существует.")


def render_sidebar():
    icon_path = Path(__file__).parent.parent / "static" / "favicon.ico"
    # Логотип и название
    st.markdown(
        f"""
        <div style="display: flex; align-items: center; margin-bottom: 1rem;">
            <img src="data:image/png;base64,{get_base64_encoded_image(icon_path)}" width="40" style="margin-right: 12px;">
            <h1 style="display: inline; margin: 0; font-size: 1.5rem;">Репрайсер {settings.INSTANCE_NAME}</h1>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<h2><i class="fa-solid fa-file-lines"></i> Страница</h2>', unsafe_allow_html=True)
    page = st.radio(
        "Страница",
        options=["Сводка", "Статистика", "Аналитика", "Анализ", "Таблицы", "Запросы", "Сервис"],
        index=0,
        horizontal=True,
        label_visibility="collapsed"
    )
    st.session_state['current_page'] = page

    st.divider()
    st.markdown('<h2><i class="fa-solid fa-sliders"></i> Управление</h2>', unsafe_allow_html=True)

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
        st.warning("Репрайсинг выполняется. Пожалуйста, подождите...")
        st.button("Полный цикл", type="primary", width="stretch", disabled=True)
        st.button("Dry run", width="stretch", disabled=True)
    else:
        if st.button("Полный цикл", type="primary", width="stretch", icon=":material/rocket_launch:"):
            st.session_state.running = True
            st.session_state.dry_run_mode = False
            st.rerun()
        if st.button("Dry run", width="stretch", icon=":material/edit:"):
            st.session_state.running = True
            st.session_state.dry_run_mode = True
            st.rerun()

    st.divider()
    # Секция Excel (всегда видна, но кнопки могут быть disabled)
    st.markdown('<h3><i class="fa-solid fa-table-cells"></i> Работа с Excel</h3>', unsafe_allow_html=True)
    render_sidebar_section_excel(disabled=st.session_state.get('running', False))