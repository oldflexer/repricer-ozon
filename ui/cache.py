"""
Кэширование данных в Streamlit.

Использует декораторы @st.cache_data и @st.cache_resource для
оптимизации загрузки данных из БД и создания тяжёлых объектов.
"""

import streamlit as st

from config.settings import settings
from infrastructure.db import SQLiteRepository
from infrastructure.excel_loader import ExcelLoader
from infrastructure.mail_notifier import MailNotifier
from infrastructure.ozon_api import OzonApiClient


def get_repo() -> SQLiteRepository:
    """
    Возвращает репозиторий из session_state.

    Returns:
        SQLiteRepository: Экземпляр репозитория.
    """
    return st.session_state.repo


@st.cache_resource(ttl=3600, show_spinner=False)
def get_cached_products():
    """
    Возвращает закэшированный список всех товаров.

    Returns:
        List[ProductInfo]: Список товаров.
    """
    return get_repo().get_all_products()


@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_kpi():
    """
    Возвращает закэшированные KPI-метрики.

    Returns:
        Dict[str, Any]: Словарь с метриками.
    """
    return get_repo().get_kpi_metrics()


@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_strategy_roi():
    """
    Возвращает закэшированные данные ROI по стратегиям.

    Returns:
        pd.DataFrame: Данные ROI.
    """
    return get_repo().get_strategy_roi()


@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_ozon_price_df():
    """
    Возвращает закэшированные данные сравнения цены и индекса Ozon.

    Returns:
        pd.DataFrame: Данные сравнения.
    """
    return get_repo().get_ozon_index_vs_price()


@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_last_prices():
    """
    Возвращает закэшированные последние цены и маржинальность для всех товаров.

    Returns:
        pd.DataFrame: Данные последних цен.
    """
    return get_repo().get_all_last_prices()


# ------ ЭТИ ФУНКЦИИ НЕ КЭШИРУЕМ (создают новые объекты) ------
def get_excel_loader():
    """Создаёт новый экземпляр ExcelLoader."""
    return ExcelLoader(settings.DATA_FILE_PATH)


def get_api_client():
    """Создаёт новый экземпляр OzonApiClient."""
    return OzonApiClient()


def get_mail_notifier():
    """Создаёт новый экземпляр MailNotifier."""
    return MailNotifier()
