import streamlit as st
from ui.cache import get_cached_kpi, get_cached_products


def render_kpi():
    """Отображение KPI-метрик."""
    kpi = get_cached_kpi()
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        delta_margin = kpi['avg_margin_today'] - kpi['avg_margin_yesterday']
        st.metric(
            "Средняя маржинальность (сегодня)",
            f"{kpi['avg_margin_today']:.1f}%",
            delta=f"{delta_margin:+.1f}%" if delta_margin != 0 else None
        )
    with col2:
        st.metric("Обновлений за неделю", kpi['updates_last_week'])
    with col3:
        st.metric("Убыточные товары", kpi['unprofitable_count'], delta=None)
    with col4:
        st.metric("Без индекса Ozon", kpi['no_index_count'])
    with col5:
        total_products = len(get_cached_products())
        st.metric("Всего товаров", total_products)
    st.divider()