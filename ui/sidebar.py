"""
Боковая панель Streamlit-дашборда.

Содержит:
- переключение страниц,
- кнопки запуска репрайсинга и парсинга (обычный и dry-run),
- загрузку и скачивание Excel-файла,
- отображение статуса выполнения задач.
- Фоновые задачи для неблокирующего UI
"""

import asyncio
import base64
import os
import sys
import tempfile
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any, Callable, Optional

import streamlit as st
from filelock import FileLock, Timeout

from config.settings import settings
from core.use_cases import (
    ParseCompetitorPricesUseCase,
    RepricingUseCase,
    RepricingUseCaseDependencies,
)
from core.use_cases.parse_own_products import ParseOwnProductsUseCase
from core.use_cases.disable_auto_add import DisableAutoAddUseCase
from core.use_cases.update_price_timer import UpdatePriceTimerUseCase
from core.domain.pricing_rules import OzonPricingRules
from infrastructure.logger import setup_logging, setup_parser_logging
from ui.auth import get_session_info, logout, render_session_timer
from ui.cache import (
    get_api_client,
    get_excel_loader,
    get_mail_notifier,
    get_repo,
)

LOCK_FILE = Path(tempfile.gettempdir()) / 'repricer_parser.lock'

# Thread pool for background tasks
_background_threads: dict[str, threading.Thread] = {}
_task_results: dict[str, tuple[str, str]] = {}
_task_progress: dict[str, tuple[int, int, str]] = {}
_task_events: dict[str, threading.Event] = {}  # Signal task completion

# Real-time log storage (max 1000 entries)
_log_queue: deque[tuple[str, str, float]] = deque(maxlen=1000)  # (level, message, timestamp)
_log_subscribers: list[threading.Event] = []  # Events for real-time updates
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


def _run_async_in_thread(
    coro: Any, task_id: str, progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> None:
    """Запускает асинхронную корутину в отдельном потоке."""
    # Create event for this task
    event = threading.Event()
    _task_events[task_id] = event
    
    def run() -> None:
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Wrap progress callback to store progress
            def wrapped_progress(current: int, total: int, message: str) -> None:
                _task_progress[task_id] = (current, total, message)
                if progress_callback:
                    progress_callback(current, total, message)
            
            result = loop.run_until_complete(coro)
            _task_results[task_id] = (result, "success")
        except Exception as e:
            _task_results[task_id] = (f"Ошибка: {e}", "error")
        finally:
            if loop is not None:
                loop.close()
            # Clean up thread reference
            _background_threads.pop(task_id, None)
            # Signal completion
            event.set()
    
    thread = threading.Thread(target=run, daemon=True)
    _background_threads[task_id] = thread
    thread.start()


def _run_async_in_thread_sync(coro: Any) -> Any:
    """
    Запускает асинхронную корутину в отдельном потоке и возвращает результат.

    Args:
        coro: Асинхронная корутина для выполнения.

    Returns:
        Результат выполнения корутины.
    """
    result_container: list[Any] = []
    exception_container: list[BaseException] = []

    def run() -> None:
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result_container.append(loop.run_until_complete(coro))
        except Exception as e:
            exception_container.append(e)
        finally:
            if loop is not None:
                loop.close()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join()

    if exception_container:
        raise exception_container[0]
    return result_container[0] if result_container else None


def add_log(level: str, message: str) -> None:
    """Add a log entry to the queue and notify subscribers."""
    timestamp = time.time()
    _log_queue.append((level, message, timestamp))
    # Notify all subscribers
    for event in _log_subscribers:
        event.set()


def subscribe_to_logs() -> threading.Event:
    """Subscribe to real-time log updates."""
    event = threading.Event()
    _log_subscribers.append(event)
    return event


def unsubscribe_from_logs(event: threading.Event) -> None:
    """Unsubscribe from real-time log updates."""
    if event in _log_subscribers:
        _log_subscribers.remove(event)


def get_recent_logs(limit: int = 100) -> list[tuple[str, str, float]]:
    """Get recent log entries."""
    return list(_log_queue)[-limit:]


def clear_logs() -> None:
    """Clear the log queue."""
    _log_queue.clear()


def run_repricing(
    dry_run: bool = False, progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> dict[str, Any]:
    """
    Запускает репрайсинг в синхронном контексте (из Streamlit).

    Args:
        dry_run: Если True, цены не отправляются в Ozon.
        progress_callback: Опциональный колбэк для отображения прогресса (current, total, message).

    Returns:
        Словарь со статистикой выполнения.
    """

    logger = setup_logging("repricer.log", mode="w")
    logger.info("=== Запуск репрайсинга из дашборда ===")

    async def _run() -> dict[str, Any]:
        # Запуск репрайсинга
        loader = get_excel_loader()
        api = get_api_client()
        notifier = get_mail_notifier()
        repo = get_repo()
        pricing_rules = OzonPricingRules.from_settings(settings)
        
        # Get parse_own_products_use_case from container
        from core.container import container
        parse_own_products_use_case = container.parse_own_products_use_case()
        
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
            pricing_rules=pricing_rules,
            parse_own_products_use_case=parse_own_products_use_case,
            progress_callback=progress_callback,
        )
        use_case = RepricingUseCase(deps)
        try:
            stats = await use_case.execute(dry_run=dry_run)
            return stats
        finally:
            await api.close()

    # Run async function in a separate thread with its own event loop
    return _run_async_in_thread_sync(_run())  # type: ignore[no-any-return]
def execute_repricing(dry_run: bool) -> tuple[str, str]:
    """
    Выполняет репрайсинг с отображением прогресса в Streamlit (блокирующий вариант).

    Args:
        dry_run: Флаг тестового запуска.

    Returns:
        Кортеж (сообщение, тип результата: 'success' или 'error').
    """
    with st.status("Выполняется репрайсинг...", expanded=True) as status:
        try:
            def progress_cb(current: int, total: int, message: str) -> None:
                status.update(label=f"{message} ({current}/{total})")
                st.write(f"Шаг {current}/{total}: {message}")

            stats = run_repricing(dry_run=dry_run, progress_callback=progress_cb)
            updated = stats.get("updated", 0)
            errors = stats.get("errors", [])
            
            if not dry_run:
                st.cache_data.clear()
                st.cache_resource.clear()
            
            status.update(label="Репрайсинг завершён!", state="complete")
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


def start_repricing_background(dry_run: bool) -> str:
    """
    Запускает репрайсинг в фоновом потоке (неблокирующий).
    
    Args:
        dry_run: Флаг тестового запуска.
        
    Returns:
        ID задачи для отслеживания прогресса.
    """
    task_id = f"repricing_{int(time.time() * 1000)}"
    st.session_state.running = True
    st.session_state.current_task_id = task_id
    st.session_state.dry_run_mode = dry_run
    
    def progress_cb(current: int, total: int, message: str) -> None:
        _task_progress[task_id] = (current, total, message)
    
    async def _run() -> None:
        run_repricing(dry_run=dry_run, progress_callback=progress_cb)
    
    _run_async_in_thread(_run(), task_id, progress_cb)
    return task_id
def check_background_task(task_id: str) -> Optional[tuple[str, str]]:
    """
    Проверяет статус фоновой задачи.
    
    Returns:
        (message, type) если задача завершена, None если еще выполняется.
    """
    if task_id in _task_results:
        result = _task_results.pop(task_id)
        st.session_state.running = False
        st.session_state.parsing_running = False
        return result
    return None


def get_task_progress(task_id: str) -> Optional[tuple[int, int, str]]:
    """Возвращает прогресс задачи (current, total, message)."""
    return _task_progress.get(task_id)


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

    use_case = ParseCompetitorPricesUseCase()
    return await use_case.execute(dry_run=dry_run)


async def run_parsing_own_products(dry_run: bool = False) -> dict[str, Any]:
    """
    Запускает парсинг своих товаров в асинхронном контексте (из Streamlit).

    Args:
        dry_run: Если True, данные не записываются в БД.

    Returns:
        Словарь со статистикой {updated, errors, skipped}.
    """
    logger = setup_parser_logging("parser_own.log", mode="w")
    logger.info("=== Запуск парсинга своих товаров из дашборда ===")

    # Get dependencies from container
    from core.container import container
    use_case = container.parse_own_products_use_case()
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
                stats = _run_async_in_thread_sync(run_parsing(dry_run=dry_run))
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


def start_parsing_background(dry_run: bool) -> str:
    """
    Запускает парсинг в фоновом потоке (неблокирующий).
    
    Args:
        dry_run: Флаг тестового запуска.
        
    Returns:
        ID задачи для отслеживания прогресса.
    """
    task_id = f"parsing_{int(time.time() * 1000)}"
    st.session_state.parsing_running = True
    st.session_state.current_task_id = task_id
    st.session_state.parsing_dry_run = dry_run
    
    async def _run() -> tuple[str, str]:
        stats = await run_parsing(dry_run=dry_run)
        msg = (
            f"Готово! Обновлено цен: {stats.get('updated', 0)}, "
            f"ошибок: {stats.get('errors', 0)}, "
            f"пропущено: {stats.get('skipped', 0)}"
        )
        return msg, "success"
    
    _run_async_in_thread(_run(), task_id)
    return task_id


def start_parsing_own_products_background(dry_run: bool) -> str:
    """
    Запускает парсинг своих товаров в фоновом потоке (неблокирующий).

    Args:
        dry_run: Флаг тестового запуска.

    Returns:
        ID задачи для отслеживания прогресса.
    """
    task_id = f"parsing_own_{int(time.time() * 1000)}"
    st.session_state.parsing_running = True
    st.session_state.current_task_id = task_id
    st.session_state.parsing_dry_run = dry_run

    async def _run() -> tuple[str, str]:
        stats = await run_parsing_own_products(dry_run=dry_run)
        msg = (
            f"Готово! Обновлено товаров: {stats.get('updated', 0)}, "
            f"ошибок: {stats.get('errors', 0)}, "
            f"пропущено: {stats.get('skipped', 0)}"
        )
        return msg, "success"

    _run_async_in_thread(_run(), task_id)
    return task_id


def start_disable_auto_add_background(dry_run: bool) -> str:
    """
    Запускает отключение автодобавления в фоновом потоке (неблокирующий).

    Args:
        dry_run: Флаг тестового запуска.

    Returns:
        ID задачи для отслеживания прогресса.
    """
    task_id = f"disable_auto_add_{int(time.time() * 1000)}"
    st.session_state.current_task_id = task_id

    async def _run() -> tuple[str, str]:
        from core.container import container
        api_client = container.api_client()
        use_case = DisableAutoAddUseCase(api_client)
        stats = await use_case.execute(dry_run=dry_run)
        msg = (
            f"Готово! Удалено: {stats.get('deleted', 0)}, "
            f"ошибок: {stats.get('errors', 0)}"
        )
        return msg, "success"

    _run_async_in_thread(_run(), task_id)
    return task_id


def start_update_price_timer_background() -> str:
    """
    Запускает обновление таймера минимальной цены в фоновом потоке (неблокирующий).

    Returns:
        ID задачи для отслеживания прогресса.
    """
    task_id = f"update_price_timer_{int(time.time() * 1000)}"
    st.session_state.current_task_id = task_id

    async def _run() -> tuple[str, str]:
        from core.container import container
        from infrastructure.db import SQLiteRepository
        
        repo = SQLiteRepository(settings.database_path_path)
        products = repo.get_all_products()
        product_ids = [p.product_id for p in products if p.product_id]
        
        if not product_ids:
            return "Нет товаров в БД для обновления таймера", "error"
        
        api = container.api_client()
        use_case = UpdatePriceTimerUseCase(api)
        try:
            stats = await use_case.execute(product_ids)
            success_count = stats.get("success", 0)
            failed_count = stats.get("failed", 0)
            msg = f"Готово! Обновлено таймеров: {success_count}, ошибок: {failed_count}"
            return msg, "success"
        finally:
            await api.close()

    _run_async_in_thread(_run(), task_id)
    return task_id


def render_sidebar_section_excel(disabled: bool) -> None:
    """
    Отрисовывает секцию работы с Excel (загрузка/скачивание).

    Args:
        disabled: Если True, кнопки и загрузка блокируются.
    """

    if disabled:
        st.info(
            'Загрузка Excel недоступна во время выполнения репрайсинга',
            icon=":material/info:",
        )
        if settings.data_file_path.exists():
            with settings.data_file_path.open("rb") as f:
                st.download_button(
                    'Скачать текущий Excel',
                    f,
                    file_name=settings.data_file_path.name,
                    width="stretch",
                    disabled=True,
                )
    else:
        try:
            uploaded_file = st.file_uploader(
                'Выберите Excel файл',
                type=['xlsx'],
                label_visibility='collapsed',
                width="stretch",
                key='excel_uploader',
            )
            if uploaded_file is not None:
                with settings.data_file_path.open("wb") as f:
                    f.write(uploaded_file.getbuffer())
                st.success(
                    f'Файл загружен: {settings.data_file_path.name}',
                    icon=":material/check_circle:",
                )
                st.cache_data.clear()
                st.cache_resource.clear()
        except Exception as e:
            st.error(f"Ошибка при загрузке файла: {e}", icon=":material/cancel:")

    if settings.data_file_path.exists():
        with settings.data_file_path.open("rb") as f:
            st.download_button(
                'Скачать текущий Excel',
                f,
                file_name=settings.data_file_path.name,
                width="stretch",
                key="download_excel_sidebar",
            )
    else:
        st.warning("Файл Excel пока не существует.", icon=":material/warning:")
def _handle_repricing_buttons(is_busy: bool) -> None:
    """Обрабатывает кнопки репрайсинга."""
    if is_busy:
        st.warning("Выполняется задача. Пожалуйста, подождите...", icon=":material/warning:")

    if st.session_state.get("running"):
        st.button(
            'Репрайсинг товаров',
            type="primary",
            width="stretch",
            disabled=True,
            icon=":material/rocket_launch:",
        )
    else:
        if st.button(
            'Репрайсинг товаров',
            type="primary",
            width="stretch",
            icon=":material/rocket_launch:",
        ):
            start_repricing_background(dry_run=False)
            st.rerun()


def _handle_parsing_buttons(is_busy: bool) -> None:
    """Обрабатывает кнопки парсинга конкурентов."""
    if is_busy:
        st.warning("Выполняется задача. Пожалуйста, подождите...", icon=":material/warning:")

    if st.session_state.get("parsing_running"):
        st.button(
            'Парсинг цен конкурентов',
            type="primary",
            width="stretch",
            disabled=True,
            icon=":material/rocket_launch:",
        )
    else:
        if st.button(
            'Парсинг цен конкурентов',
            type="primary",
            width="stretch",
            icon=":material/rocket_launch:",
        ):
            start_parsing_background(dry_run=False)
            st.rerun()


def _handle_management_buttons(is_busy: bool) -> None:
    """Обрабатывает кнопки управления (дополнительные действия)."""
    if is_busy:
        st.warning("Выполняется задача. Пожалуйста, подождите...", icon=":material/warning:")

    # Отключение автодобавления в акции
    if st.button(
        'Автодобавление в акции',
        type="primary",
        width="stretch",
        icon=":material/block:",
        disabled=is_busy,
    ):
        start_disable_auto_add_background(dry_run=False)
        st.rerun()

    # Обновление таймера минимальной цены
    if st.button(
        'Таймер минимальной цены',
        type="primary",
        width="stretch",
        icon=":material/timer:",
        disabled=is_busy,
    ):
        start_update_price_timer_background()
        st.rerun()


def _display_result_message() -> None:
    """Отображает сообщение о результате выполнения задачи (toast notification)."""
    if st.session_state.get("result_message"):
        if st.session_state.get("result_type") == "success":
            st.toast(st.session_state.result_message, icon=":material/check_circle:")
        else:
            st.toast(st.session_state.result_message, icon=":material/cancel:")
        st.session_state.result_message = None
        st.session_state.result_type = None


def _display_background_progress() -> None:
    """Отображает прогресс фоновой задачи."""
    task_id = st.session_state.get("current_task_id")
    if not task_id:
        return
    
    # Check if task is complete
    result = check_background_task(task_id)
    if result:
        msg, msg_type = result
        st.session_state.result_message = msg
        st.session_state.result_type = msg_type
        st.rerun()
    
    # Show progress
    progress = get_task_progress(task_id)
    if progress:
        current, total, message = progress
        if total > 0:
            st.progress(current / total, text=f"{message} ({current}/{total})")
        else:
            st.info(message)
    
    # If task is still running, check event and rerun when done
    event = _task_events.get(task_id)
    if event and not event.is_set():
        # Task still running - use fragment to poll
        @st.fragment(run_every=2)
        def poll_task() -> None:
            if event.is_set():
                # Task completed, trigger rerun to show results
                st.rerun()
        poll_task()
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

    # Session info
    session_info = get_session_info()
    if session_info.get("authenticated"):
        with st.expander("👤 Сессия", expanded=False):
            st.markdown(f"**Пользователь:** {session_info.get('user', 'N/A')}")
            st.markdown(f"**Токен:** `{session_info.get('token', 'N/A')}`")
            render_session_timer()
            if st.button("🚪 Выйти", use_container_width=True):
                logout()

    st.divider()

    # Выбор страницы
    st.markdown('<h2><i class="fa-solid fa-file-lines"></i> Страница</h2>', unsafe_allow_html=True)
    page = st.radio(
        'Страница',
        options=['Сводка', 'Статистика', 'Аналитика', 'Анализ', 'Таблицы', 'Запросы', 'Сервис'],
        index=0,
        horizontal=True,
        label_visibility='collapsed',
    )
    st.session_state["current_page"] = page

    st.divider()

    # Секция управления
    st.markdown('<h2><i class="fa-solid fa-sliders"></i> Управление</h2>', unsafe_allow_html=True)

    # Проверка фоновых задач
    _display_background_progress()

    # Обработка результатов выполнения репрайсинга (для блокирующего режима)
    if st.session_state.get("running") and not st.session_state.get("current_task_id"):
        msg, msg_type = execute_repricing(st.session_state.dry_run_mode)
        st.session_state.result_message = msg
        st.session_state.result_type = msg_type
        st.rerun()

    # Обработка результатов выполнения парсинга (для блокирующего режима)
    if st.session_state.get("parsing_running") and not st.session_state.get("current_task_id"):
        p_msg, p_msg_type = execute_parsing(st.session_state.parsing_dry_run)
        st.session_state.result_message = p_msg
        st.session_state.result_type = p_msg_type
        st.rerun()

    # Отображение сообщения о результате
    _display_result_message()

    is_busy = bool(st.session_state.get("running") or st.session_state.get("parsing_running"))

    # Кнопки репрайсинга
    _handle_repricing_buttons(is_busy)

    # Кнопки парсинга конкурентов
    _handle_parsing_buttons(is_busy)

    # Кнопки управления
    _handle_management_buttons(is_busy)

    st.divider()

    # Работа с Excel
    st.markdown(
        '<h3><i class="fa-solid fa-table-cells"></i> Работа с Excel</h3>', unsafe_allow_html=True
    )
    render_sidebar_section_excel(disabled=bool(is_busy))
