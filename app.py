"""
Точка входа веб-интерфейса (Streamlit‑дашборд) репрайсера Ozon.

Обрабатывает:
- настройку страницы (заголовок, иконка, layout),
- подключение внешних стилей (Font Awesome, custom CSS),
- аутентификацию пользователя,
- инициализацию репозитория и состояний сессии,
- рендеринг выбранной страницы через боковое меню.
"""

import sys
from pathlib import Path

import streamlit as st

# Добавляем корень проекта в sys.path для импорта локальных модулей
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import settings
from infrastructure.db import SQLiteRepository
from ui.auth import check_auth
from ui.pages.analysis import render_analysis_page
from ui.pages.analytics import render_analytics
from ui.pages.requests import render_requests_page
from ui.pages.service import render_service
from ui.pages.statistics import render_statistics_page
from ui.pages.summary import render_summary
from ui.pages.tables import render_tables
from ui.sidebar import render_sidebar

# ------------------------------------------------------------------
# 1. Настройка страницы Streamlit
# ------------------------------------------------------------------
page_title = f"Менеджер {settings.INSTANCE_NAME}"
st.set_page_config(page_title=page_title, layout="wide", page_icon="static/favicon.ico")

# Подключение Font Awesome 6.7.2
st.markdown(
    '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.7.2/css/all.min.css">',
    unsafe_allow_html=True,
)

# Подключение пользовательских CSS-стилей
css_path = Path(__file__).parent / "static" / "styles.css"
with css_path.open(encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ------------------------------------------------------------------
# 2. Аутентификация
# ------------------------------------------------------------------
check_auth()

# ------------------------------------------------------------------
# 3. Инициализация состояния сессии
# ------------------------------------------------------------------

# Репозиторий БД
if "repo" not in st.session_state:
    st.session_state.repo = SQLiteRepository(settings.DATABASE_PATH_PATH)

# Состояния репрайсинга
if "running" not in st.session_state:
    st.session_state.running = False
if "result_message" not in st.session_state:
    st.session_state.result_message = None
if "result_type" not in st.session_state:
    st.session_state.result_type = None
if "dry_run_mode" not in st.session_state:
    st.session_state.dry_run_mode = False

# Состояния парсера конкурентов
if "parsing_running" not in st.session_state:
    st.session_state.parsing_running = False
if "parsing_dry_run" not in st.session_state:
    st.session_state.parsing_dry_run = False

# Текущая страница
if "current_page" not in st.session_state:
    st.session_state.current_page = "Сводка"

# ------------------------------------------------------------------
# 4. Боковая панель
# ------------------------------------------------------------------
with st.sidebar:
    render_sidebar()

# ------------------------------------------------------------------
# 5. Рендеринг выбранной страницы
# ------------------------------------------------------------------
page = st.session_state.current_page

if page == "Сводка":
    render_summary()
elif page == "Статистика":
    render_statistics_page()
elif page == "Аналитика":
    render_analytics()
elif page == "Анализ":
    render_analysis_page()
elif page == "Таблицы":
    render_tables()
elif page == "Запросы":
    render_requests_page()
elif page == "Сервис":
    render_service()
else:
    st.error("Страница не найдена")

