import streamlit as st
import base64
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from config.settings import settings
from ui.auth import check_auth
from ui.kpi import render_kpi
from ui.sidebar import render_sidebar
from ui.pages.summary import render_summary
from ui.pages.statistics import render_statistics_page
from ui.pages.analytics import render_analytics
from ui.pages.analysis import render_analysis_page
from ui.pages.tables import render_tables
from ui.pages.requests import render_requests_page
from ui.pages.service import render_service
from infrastructure.db import SQLiteRepository


def get_base64_encoded_image(image_path: Path) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


# Настройка страницы
page_title = f"Репрайсер {settings.INSTANCE_NAME}"
st.set_page_config(page_title=page_title, layout="wide", page_icon="static/favicon.ico")

# CSS
with open(Path(__file__).parent / "static" / "styles.css", encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Заголовок с иконкой
icon_path = Path(__file__).parent / "static" / "favicon.ico"
dashboard_title = f"Репрайсер {settings.INSTANCE_NAME}"
st.markdown(
    f"""
    <div style="display: flex; align-items: center; margin-bottom: 1rem;">
        <img src="data:image/png;base64,{get_base64_encoded_image(icon_path)}" width="40" style="margin-right: 12px;">
        <h1 style="display: inline; margin: 0;">{dashboard_title}</h1>
    </div>
    """,
    unsafe_allow_html=True,
)

# Аутентификация
check_auth()

# Инициализация репозитория в session_state
if 'repo' not in st.session_state:
    st.session_state.repo = SQLiteRepository(settings.DATABASE_PATH)

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

# Боковая панель
with st.sidebar:
    render_sidebar()

# KPI панель (видна всегда)
render_kpi()

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