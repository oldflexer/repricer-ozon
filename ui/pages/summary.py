"""
Страница «Сводка» дашборда.

Отображает KPI-метрики:
    - средняя маржинальность (сегодня с дельтой),
    - обновления за неделю,
    - убыточные товары,
    - товары без индекса Ozon,
    - общее количество товаров,
    - графики динамики цены и маржи за 7 дней,
    - топ-3 и худшие 3 по маржинальности.
"""

import plotly.express as px
import streamlit as st

from ui.cache import get_cached_kpi, get_cached_products, get_repo


def render_summary() -> None:
    """
    Рендерит страницу сводки с KPI и графиками.
    """
    st.markdown(
        '<h2><i class="fa-solid fa-chart-simple"></i> Сводка</h2>',
        unsafe_allow_html=True,
    )
    repo = get_repo()

    # KPI
    kpi = get_cached_kpi()
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        delta_margin = kpi["avg_margin_today"] - kpi["avg_margin_yesterday"]
        st.metric(
            "Средняя маржинальность (сегодня)",
            f"{kpi['avg_margin_today']:.1f}%",
            delta=f"{delta_margin:+.1f}%" if delta_margin != 0 else None,
        )
    with col2:
        st.metric("Обновлений за неделю", kpi["updates_last_week"])
    with col3:
        st.metric("Убыточные товары", kpi["unprofitable_count"], delta=None)
    with col4:
        st.metric("Без индекса Ozon", kpi["no_index_count"])
    with col5:
        total_products = len(get_cached_products())
        st.metric("Всего товаров", total_products)

    st.divider()

    # Графики за 7 дней
    st.subheader("Динамика за последние 7 дней")
    daily_df = repo.get_daily_trends(days=7)
    if not daily_df.empty:
        daily_df["day"] = daily_df["day"].astype(str)
        daily_df["avg_margin"] = daily_df["avg_margin"] * 100

        col1, col2 = st.columns(2)
        with col1:
            fig_price = px.line(
                daily_df,
                x="day",
                y="avg_price",
                title="Средняя цена (реальная)",
                labels={"day": "Дата", "avg_price": "Цена (₽)"},
            )
            st.plotly_chart(fig_price, width="stretch")
        with col2:
            fig_margin = px.line(
                daily_df,
                x="day",
                y="avg_margin",
                title="Средняя маржинальность",
                labels={"day": "Дата", "avg_margin": "Маржинальность (%)"},
            )
            st.plotly_chart(fig_margin, width="stretch")
    else:
        st.info("Недостаточно данных для отображения динамики за неделю")

    # Топ-3 и худшие 3
    st.divider()
    col1, col2 = st.columns(2)
    top3, bottom3 = repo.get_top_bottom_marginality(limit=3)
    with col1:
        st.markdown(
            '<h4><i class="fa-solid fa-trophy"></i> Топ-3 по маржинальности</h4>',
            unsafe_allow_html=True,
        )
        if not top3.empty:
            st.dataframe(
                top3[["sku", "product_name", "marginality_pct"]].rename(
                    columns={"marginality_pct": "Маржа, %"}
                ),
                hide_index=True,
                width="stretch",
            )
        else:
            st.info("Нет данных")
    with col2:
        st.markdown(
            '<h4><i class="fa-solid fa-arrow-trend-down"></i> Худшие 3 по маржинальности</h4>',
            unsafe_allow_html=True,
        )
        if not bottom3.empty:
            st.dataframe(
                bottom3[["sku", "product_name", "marginality_pct"]].rename(
                    columns={"marginality_pct": "Маржа, %"}
                ),
                hide_index=True,
                width="stretch",
            )
        else:
            st.info("Нет данных")
