import base64
import os
import streamlit as st
from pathlib import Path
import asyncio
from typing import Dict, Any

from config.settings import settings
from ui.cache import get_repo, get_api_client, get_excel_loader, get_mail_notifier
from core.use_cases import RepricingUseCase
from parser import update_prices
from infrastructure.logger import setup_logging, setup_parser_logging
from filelock import FileLock, Timeout

LOCK_FILE = '/tmp/repricer_parser.lock'
LOCK_TIMEOUT = 1800


def get_base64_encoded_image(image_path: Path) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def run_repricing(dry_run: bool = False) -> Dict[str, Any]:
    logger = setup_logging('repricer.log', mode='w')
    logger.info("=== Запуск репрайсинга из дашборда ===")

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
            status.update(label="Готово!", state="complete")
            if dry_run:
                msg = f"Dry run завершён. Обработано товаров: {stats.get('products_loaded', 0)}, рассчитано цен: {stats.get('prices_updated', 0)}"
            else:
                updated = stats.get('prices_updated', 0)
                errors = stats.get('errors', [])
                msg = f"Готово! Обновлено цен: {updated}"
                if errors:
                    msg += f"\nОшибки: {', '.join(errors)}"
            warnings = stats.get('warnings', [])
            if warnings:
                with st.expander("Предупреждения при загрузке Excel"):
                    for w in warnings:
                        st.warning(w, icon=":material/warning:")
            return msg, 'success'
        except Exception as e:
            status.update(label="Ошибка", state="error")
            return f"Ошибка: {e}", 'error'
        finally:
            st.session_state.running = False


async def run_parsing(dry_run: bool = False) -> Dict[str, Any]:
    """
    Асинхронный запуск парсинга конкурентов.
    Запускает синхронную функцию update_prices в отдельном потоке.
    """
    logger = setup_parser_logging('parser.log', mode='w')
    logger.info("=== Запуск парсинга из дашборда ===")
    
    # Устанавливаем переменные окружения для процесса парсера
    os.environ['DISPLAY'] = ':10.0'
    os.environ['XAUTHORITY'] = '/home/server/.Xauthority'
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, update_prices, dry_run)


def execute_parsing(dry_run: bool):
    lock = FileLock(LOCK_FILE, timeout=LOCK_TIMEOUT)
    try:
        with lock.acquire(timeout=LOCK_TIMEOUT):
            with st.status("Выполняется парсинг конкурентов...", expanded=True) as status:
                st.write("Инициализация браузера и загрузка страниц Ozon...")
                try:
                    stats = asyncio.run(run_parsing(dry_run=dry_run))
                    if not dry_run:
                        st.cache_data.clear()
                        st.cache_resource.clear()
                    status.update(label="Парсинг завершён!", state="complete")
                    msg = f"Готово! Обновлено цен: {stats.get('updated', 0)}, ошибок: {stats.get('errors', 0)}, пропущено: {stats.get('skipped', 0)}"
                    return msg, 'success'
                except Exception as e:
                    status.update(label="Ошибка парсинга", state="error")
                    return f"Ошибка: {e}", 'error'
                finally:
                    st.session_state.parsing_running = False
    except Timeout:
        st.error(f"Парсер уже выполняется. Попробуйте позже.", icon=":material/cancel:")
        st.session_state.parsing_running = False
        return "Парсер занят", 'error'


def render_sidebar_section_excel(disabled: bool):
    if disabled:
        st.info("Загрузка Excel недоступна во время выполнения репрайсинга", icon=":material/info:")
        if settings.DATA_FILE_PATH.exists():
            with open(settings.DATA_FILE_PATH, "rb") as f:
                st.download_button(
                    "Скачать текущий Excel", f,
                    file_name=settings.DATA_FILE_PATH.name,
                    width="stretch", disabled=True
                )
    else:
        try:
            uploaded_file = st.file_uploader(
                "Выберите Excel файл", type=["xlsx"],
                label_visibility="collapsed", width="stretch", key="excel_uploader"
            )
            if uploaded_file is not None:
                with open(settings.DATA_FILE_PATH, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                st.success(f"Файл загружен: {settings.DATA_FILE_PATH.name}", icon=":material/check_circle:")
                st.cache_data.clear()
                st.cache_resource.clear()
        except Exception as e:
            st.error(f"Ошибка при загрузке файла: {e}", icon=":material/cancel:")
        if settings.DATA_FILE_PATH.exists():
            with open(settings.DATA_FILE_PATH, "rb") as f:
                st.download_button(
                    "Скачать текущий Excel", f,
                    file_name=settings.DATA_FILE_PATH.name,
                    width="stretch"
                )
        else:
            st.warning("Файл Excel пока не существует.", icon=":material/warning:")


def render_sidebar():
    icon_path = Path(__file__).parent.parent / "static" / "favicon.ico"
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

    if st.session_state.get('running'):
        msg, msg_type = execute_repricing(st.session_state.dry_run_mode)
        st.session_state.result_message = msg
        st.session_state.result_type = msg_type
        st.rerun()

    if st.session_state.get('parsing_running'):
        p_msg, p_msg_type = execute_parsing(st.session_state.parsing_dry_run)
        st.session_state.result_message = p_msg
        st.session_state.result_type = p_msg_type
        st.rerun()

    if st.session_state.get('result_message'):
        if st.session_state.get('result_type') == 'success':
            st.success(st.session_state.result_message, icon=":material/check_circle:")
        else:
            st.error(st.session_state.result_message, icon=":material/cancel:")
        st.session_state.result_message = None
        st.session_state.result_type = None

    is_busy = st.session_state.get('running') or st.session_state.get('parsing_running')

    st.markdown('<h3><i class="fa-solid fa-arrows-up-down"></i> Репрайсинг</h3>', unsafe_allow_html=True)
    if is_busy:
        st.warning("Выполняется задача. Пожалуйста, подождите...", icon=":material/warning:")

    if st.session_state.get('running'):
        st.button("Репрайсинг товаров", type="primary", width="stretch", disabled=True, icon=":material/rocket_launch:")
        st.button("Тест репрайсинга", width="stretch", disabled=True, icon=":material/bug_report:")
    else:
        if st.button("Репрайсинг товаров", type="primary", width="stretch", icon=":material/rocket_launch:"):
            st.session_state.running = True
            st.session_state.dry_run_mode = False
            st.rerun()
        if st.button("Тест репрайсинга", width="stretch", icon=":material/bug_report:"):
            st.session_state.running = True
            st.session_state.dry_run_mode = True
            st.rerun()

    st.markdown('<h3><i class="fa-solid fa-spider"></i> Парсинг конкурентов</h3>', unsafe_allow_html=True)
    if st.session_state.get('parsing_running'):
        st.button("Парсинг цен", type="primary", width="stretch", disabled=True, icon=":material/rocket_launch:")
        st.button("Тест парсинга", width="stretch", disabled=True, icon=":material/bug_report:")
    else:
        if st.button("Парсинг цен", type="primary", width="stretch", icon=":material/rocket_launch:"):
            st.session_state.parsing_running = True
            st.session_state.parsing_dry_run = False
            st.rerun()
        if st.button("Тест парсинга", width="stretch", icon=":material/bug_report:"):
            st.session_state.parsing_running = True
            st.session_state.parsing_dry_run = True
            st.rerun()

    st.markdown('<h3><i class="fa-solid fa-table-cells"></i> Работа с Excel</h3>', unsafe_allow_html=True)
    render_sidebar_section_excel(disabled=bool(is_busy))