"""
Боковая панель Streamlit-дашборда.

Содержит:
- переключение страниц,
- кнопки запуска репрайсинга и парсинга (обычный и dry-run),
- загрузку и скачивание Excel-файла,
- отображение статуса выполнения задач.
"""

import asyncio
import base64
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import streamlit as st
from filelock import FileLock, Timeout

from config.settings import settings
from core.use_cases import (
    ParseCompetitorPricesUseCase,
    RepricingUseCase,
    RepricingUseCaseDependencies,
)
from infrastructure.logger import setup_logging, setup_parser_logging
from infrastructure.x_display import get_available_display
from ui.cache import get_api_client, get_excel_loader, get_mail_notifier, get_repo

LOCK_FILE = Path(tempfile.gettempdir()) / "repricer_parser.lock"

# Test comment

def get_base64_encoded_image(image_path: Path) -> str:
    """
    Кодирует изображение в base64 для встраивания в HTML.

    Args:
        image_path: Путь к файлу изображения.

    Returns:
        base64-строка.
    """
    with image_path.open("rb") as f:
        return base64.b64encode(f.read()).decode()


def run_repricing(dry_run: bool = False) -> dict[str, Any]:
    """
    Запускает репрайсинг в синхронном контексте (из Streamlit).

    Args:
        dry_run: Если True, цены не отправляются в Ozon.

    Returns:
        Словарь со статистикой выполнения.
    """

    logger = setup_logging("repricer.log", mode="w")
    logger.info("=== Запуск репрайсинга из дашборда ===")

    async def _run() -> dict[str, Any]:
        loader = get_excel_loader()
        api = get_api_client()
        notifier = get_mail_notifier()
        repo = get_repo()
        deps = RepricingUseCaseDependencies(
            product_repo=repo,
            history_repo=repo,
            analytics_repo=repo,
            marginality_repo=repo,
            maintenance_repo=repo,
            api_client=api,
            mail_notifier=notifier,
            loader=loader,
            calculator=None,
        )
        use_case = RepricingUseCase(deps)
        try:
            stats = await use_case.execute(dry_run=dry_run)
        finally:
            await api.close()
        return stats

    return asyncio.run(_run())


def execute_repricing(dry_run: bool) -> tuple[str, str]:
    """
    Выполняет репрайсинг с отображением прогресса в Streamlit.

    Args:
        dry_run: Флаг тестового запуска.

    Returns:
        Кортеж (сообщение, тип результата: 'success' или 'error').
    """
    with st.status("Выполняется репрайсинг...", expanded=True) as status:
        st.write("Загрузка данных из Excel...")
        try:
            stats = run_repricing(dry_run=dry_run)
            st.cache_data.clear()
            st.cache_resource.clear()
            status.update(label="Готово!", state="complete")

            if dry_run:
                msg = (
                    f"Dry run завершён. Обработано товаров: {stats.get('products_loaded', 0)}, "
                    f"рассчитано цен: {stats.get('prices_updated', 0)}"
                )
            else:
                updated = stats.get("prices_updated", 0)
                errors = stats.get("errors", [])
                msg = f"Готово! Обновлено цен: {updated}"
                if errors:
                    msg += f"\nОшибки: {', '.join(errors)}"

            warnings = stats.get("warnings", [])
            if warnings:
                with st.expander("Предупреждения при загрузке Excel"):
                    for w in warnings:
                        st.warning(w, icon=":material/warning:")

            return msg, "success"
        except Exception as e:
            status.update(label="Ошибка", state="error")
            return f"Ошибка: {e}", "error"
        finally:
            st.session_state.running = False


async def run_parsing(dry_run: bool = False) -> dict[str, Any]:
    """
    Запускает парсинг конкурентов в асинхронном контексте (из Streamlit).

    Args:
        dry_run: Если True, данные не записываются в Excel.

    Returns:
        Словарь со статистикой {updated, errors, skipped}.
    """
    logger = setup_parser_logging("parser.log", mode="w")
    logger.info("=== Запуск парсинга из дашборда ===")

    # Настройка окружения только для Linux
    if not sys.platform.startswith("win"):
        display = get_available_display()
        if display:
            os.environ["DISPLAY"] = display
            logger.info(f"Установлен DISPLAY={display}")
            if "XAUTHORITY" not in os.environ:
                os.environ["XAUTHORITY"] = "/home/server/.Xauthority"
        else:
            logger.warning("X-сервер не найден. Возможно, парсинг не сможет открыть браузер.")
    # На Windows ничего не делаем – DISPLAY не требуется

    use_case = ParseCompetitorPricesUseCase()
    return await use_case.execute(dry_run=dry_run)


def execute_parsing(dry_run: bool) -> tuple[str, str]:
    """
    Выполняет парсинг конкурентов с отображением прогресса в Streamlit.

    Args:
        dry_run: Флаг тестового запуска.

    Returns:
        Кортеж (сообщение, тип результата: 'success' или 'error').
    """
    lock = FileLock(LOCK_FILE, timeout=settings.PARSER_LOCK_TIMEOUT)
    try:
        with (
            lock.acquire(timeout=settings.PARSER_LOCK_TIMEOUT),
            st.status("Выполняется парсинг конкурентов...", expanded=True) as status,
        ):
            st.write("Инициализация браузера и загрузка страниц Ozon...")
            try:
                stats = asyncio.run(run_parsing(dry_run=dry_run))
                if not dry_run:
                    st.cache_data.clear()
                    st.cache_resource.clear()
                status.update(label="Парсинг завершён!", state="complete")
                msg = (
                    f"Готово! Обновлено цен: {stats.get('updated', 0)}, "
                    f"ошибок: {stats.get('errors', 0)}, "
                    f"пропущено: {stats.get('skipped', 0)}"
                )
                return msg, "success"
            except Exception as e:
                status.update(label="Ошибка парсинга", state="error")
                return f"Ошибка: {e}", "error"
            finally:
                st.session_state.parsing_running = False
        with (
            lock.acquire(timeout=settings.PARSER_LOCK_TIMEOUT),
            st.status("Выполняется парсинг конкурентов...", expanded=True) as status,
        ):
            st.write("Инициализация браузера и загрузка страниц Ozon...")
            try:
                stats = asyncio.run(run_parsing(dry_run=dry_run))
                if not dry_run:
                    st.cache_data.clear()
                    st.cache_resource.clear()
                status.update(label="Парсинг завершён!", state="complete")
                msg = (
                    f"Готово! Обновлено цен: {stats.get('updated', 0)}, "
                    f"ошибок: {stats.get('errors', 0)}, "
                    f"пропущено: {stats.get('skipped', 0)}"
                )
                return msg, "success"
            except Exception as e:
                status.update(label="Ошибка парсинга", state="error")
                return f"Ошибка: {e}", "error"
            finally:
                st.session_state.parsing_running = False
    except Timeout:
        st.error("Парсер уже выполняется. Попробуйте позже.", icon=":material/cancel:")
        st.session_state.parsing_running = False
        return "Парсер занят", "error"


def render_sidebar_section_excel(disabled: bool) -> None:
    """
    Отрисовывает секцию работы с Excel (загрузка/скачивание).
    
    Args:
        disabled: Если True, кнопки и загрузка блокируются.
    """
    
    if disabled:
        st.info(
            "Загрузка Excel недоступна во время выполнения репрайсинга",
            icon=":material/info:",
        )
        if settings.data_file_path.exists():
            with settings.data_file_path.open("rb") as f:
                st.download_button(
                    "Скачать текущий Excel",
                    f,
                    file_name=settings.data_file_path.name,
                    width="stretch",
                    disabled=True,
                )
    else:
        try:
            uploaded_file = st.file_uploader(
                "Выберите Excel файл",
                type=["xlsx"],
                label_visibility="collapsed",
                width="stretch",
                key="excel_uploader",
            )
            if uploaded_file is not None:
                with settings.data_file_path.open("wb") as f:
                    f.write(uploaded_file.getbuffer())
                st.success(
                    f"Файл загружен: {settings.data_file_path.name}",
                    icon=":material/check_circle:",
                )
                st.cache_data.clear()
                st.cache_resource.clear()
        except Exception as e:
            st.error(f"Ошибка при загрузке файла: {e}", icon=":material/cancel:")
    
    if settings.data_file_path.exists():
        with settings.data_file_path.open("rb") as f:
            st.download_button(
                "Скачать текущий Excel",
                f,
                file_name=settings.data_file_path.name,
                width="stretch",
            )
    else:
        st.warning("Файл Excel пока не существует.", icon=":material/warning:")

def _handle_repricing_buttons(is_busy: bool) -> None:
    """Обрабатывает кнопки репрайсинга."""
    st.markdown(
        '<h3><i class="fa-solid fa-arrows-up-down"></i> Репрайсинг</h3>', unsafe_allow_html=True
    )
    if is_busy:
        st.warning("Выполняется задача. Пожалуйста, подождите...", icon=":material/warning:")

    if st.session_state.get("running"):
        st.button(
            "Репрайсинг товаров",
            type="primary",
            width="stretch",
            disabled=True,
            icon=":material/rocket_launch:",
        )
        st.button(
            "Тест репрайсинга",
            width="stretch",
            disabled=True,
            icon=":material/bug_report:",
        )
    else:
        if st.button(
            "Репрайсинг товаров",
            type="primary",
            width="stretch",
            icon=":material/rocket_launch:",
        ):
            st.session_state.running = True
            st.session_state.dry_run_mode = False
            st.rerun()
        if st.button(
            "Тест репрайсинга",
            width="stretch",
            icon=":material/bug_report:",
        ):
            st.session_state.running = True
            st.session_state.dry_run_mode = True
            st.rerun()


def _handle_parsing_buttons(is_busy: bool) -> None:
    """Обрабатывает кнопки парсинга."""
    st.markdown(
        '<h3><i class="fa-solid fa-spider"></i> Парсинг конкурентов</h3>', unsafe_allow_html=True
    )
    if is_busy:
        st.warning("Выполняется задача. Пожалуйста, подождите...", icon=":material/warning:")

    if st.session_state.get("parsing_running"):
        st.button(
            "Парсинг цен",
            type="primary",
            width="stretch",
            disabled=True,
            icon=":material/rocket_launch:",
        )
        st.button(
            "Тест парсинга",
            width="stretch",
            disabled=True,
            icon=":material/bug_report:",
        )
    else:
        if st.button(
            "Парсинг цен",
            type="primary",
            width="stretch",
            icon=":material/rocket_launch:",
        ):
            st.session_state.parsing_running = True
            st.session_state.parsing_dry_run = False
            st.rerun()
        if st.button(
            "Тест парсинга",
            width="stretch",
            icon=":material/bug_report:",
        ):
            st.session_state.parsing_running = True
            st.session_state.parsing_dry_run = True
            st.rerun()


def _display_result_message() -> None:
    """Отображает сообщение о результате выполнения задачи."""
    if st.session_state.get("result_message"):
        if st.session_state.get("result_type") == "success":
            st.success(st.session_state.result_message, icon=":material/check_circle:")
        else:
            st.error(st.session_state.result_message, icon=":material/cancel:")
        st.session_state.result_message = None
        st.session_state.result_type = None


def render_sidebar() -> None:
    """Отрисовывает боковую панель дашборда."""
    icon_path = Path(__file__).parent.parent / "static" / "favicon.ico"

    # Заголовок с логотипом
    st.markdown(
        f"""
        <div style="display: flex; align-items: center; margin-bottom: 1rem;">
            <img src="data:image/png;base64,{get_base64_encoded_image(icon_path)}"
                 width="40" style="margin-right: 12px;">
            <h1 style="display: inline; margin: 0; font-size: 1.5rem;">
                Менеджер {settings.INSTANCE_NAME}
            </h1>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Выбор страницы
    st.markdown('<h2><i class="fa-solid fa-file-lines"></i> Страница</h2>', unsafe_allow_html=True)
    page = st.radio(
        "Страница",
        options=["Сводка", "Статистика", "Аналитика", "Анализ", "Таблицы", "Запросы", "Сервис"],
        index=0,
        horizontal=True,
        label_visibility="collapsed",
    )
    st.session_state["current_page"] = page

    st.divider()

    # Секция управления
    st.markdown('<h2><i class="fa-solid fa-sliders"></i> Управление</h2>', unsafe_allow_html=True)

    # Обработка результатов выполнения репрайсинга
    if st.session_state.get("running"):
        msg, msg_type = execute_repricing(st.session_state.dry_run_mode)
        st.session_state.result_message = msg
        st.session_state.result_type = msg_type
        st.rerun()

    # Обработка результатов выполнения парсинга
    if st.session_state.get("parsing_running"):
        p_msg, p_msg_type = execute_parsing(st.session_state.parsing_dry_run)
        st.session_state.result_message = p_msg
        st.session_state.result_type = p_msg_type
        st.rerun()

    # Отображение сообщения о результате
    _display_result_message()

    is_busy = bool(st.session_state.get("running") or st.session_state.get("parsing_running"))

    # Кнопки репрайсинга
    _handle_repricing_buttons(is_busy)

    # Кнопки парсинга
    _handle_parsing_buttons(is_busy)

    # Работа с Excel
    st.markdown(
        '<h3><i class="fa-solid fa-table-cells"></i> Работа с Excel</h3>', unsafe_allow_html=True
    )
    render_sidebar_section_excel(disabled=bool(is_busy))
