import streamlit as st
import base64
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from config.settings import settings
from ui.auth import check_auth
from ui.sidebar import render_sidebar
from ui.pages.summary import render_summary
from ui.pages.statistics import render_statistics_page
from ui.pages.analytics import render_analytics
from ui.pages.analysis import render_analysis_page
from ui.pages.tables import render_tables
from ui.pages.requests import render_requests_page
from ui.pages.service import render_service
from infrastructure.db import SQLiteRepository


# Настройка страницы
page_title = f"Репрайсер {settings.INSTANCE_NAME}"
st.set_page_config(page_title=page_title, layout="wide", page_icon="static/favicon.ico")

# Подключение Font Awesome 6.7.2
st.markdown(
    '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.7.2/css/all.min.css">',
    unsafe_allow_html=True,
)

# CSS
with open(Path(__file__).parent / "static" / "styles.css", encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Аутентификация
check_auth()

# Инициализация репозитория в session_state
if 'repo' not in st.session_state:
    st.session_state.repo = SQLiteRepository(settings.DATABASE_PATH_PATH)

# Состояния
if 'running' not in st.session_state:
    st.session_state.running = False
if 'result_message' not in st.session_state:
    st.session_state.result_message = None
if 'result_type' not in st.session_state:
    st.session_state.result_type = None
if 'dry_run_mode' not in st.session_state:
    st.session_state.dry_run_mode = False
if 'current_page' not in st.session_state:
    st.session_state.current_page = "Сводка"

# Состояния для парсера конкурентов
if 'parsing_running' not in st.session_state:
    st.session_state.parsing_running = False
if 'parsing_dry_run' not in st.session_state:
    st.session_state.parsing_dry_run = False

# Боковая панель
with st.sidebar:
    render_sidebar()

# Основная область – рендеринг выбранной страницы
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