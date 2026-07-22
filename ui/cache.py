import streamlit as st
from infrastructure.db import SQLiteRepository
from infrastructure.excel_loader import ExcelLoader
from infrastructure.ozon_api import OzonApiClient
from infrastructure.mail_notifier import MailNotifier


def get_repo() -> SQLiteRepository:
    """Возвращает репозиторий из session_state."""
    return st.session_state.repo


@st.cache_resource(ttl=3600, show_spinner=False)
def get_cached_products():
    return get_repo().get_all_products()


@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_kpi():
    return get_repo().get_kpi_metrics()


@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_strategy_roi():
    return get_repo().get_strategy_roi()


@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_ozon_price_df():
    return get_repo().get_ozon_index_vs_price()


@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_last_prices():
    return get_repo().get_all_last_prices()


# ------ ЭТИ ФУНКЦИИ НЕ КЭШИРУЕМ ------
def get_excel_loader():
    from config.settings import settings
    return ExcelLoader(settings.DATA_FILE_PATH)


def get_api_client():
    return OzonApiClient()


def get_mail_notifier():
    return MailNotifier()