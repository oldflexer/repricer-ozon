"""
Страница «Статистика» дашборда.

Отображает:
    - основные статистики маржинальности (средняя, медиана, мин, макс),
    - распределение маржинальности,
    - распределение по типам стратегий,
    - эффективность стратегий (ROI).
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from ui.cache import get_cached_last_prices, get_cached_strategy_roi, get_repo


def render_statistics_page() -> None:
    """
    Рендерит страницу статистики.
    """
    st.markdown(
        '<h2><i class="fa-solid fa-chart-pie"></i> Статистика</h2>',
        unsafe_allow_html=True,
    )
    repo = get_repo()

    last_prices_df = get_cached_last_prices()
    if last_prices_df.empty:
        st.warning("Нет данных для статистики.")
        return

    margins = last_prices_df["last_margin"] * 100
    avg_margin = margins.mean()
    med_margin = margins.median()
    min_margin = margins.min()
    max_margin = margins.max()
    low_margin_count = (margins < 10).sum()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Средняя маржинальность", f"{avg_margin:.2f}%")
    col2.metric("Медианная маржа", f"{med_margin:.2f}%")
    col3.metric("Мин. маржа", f"{min_margin:.2f}%")
    col4.metric("Макс. маржа", f"{max_margin:.2f}%")
    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Товаров с маржей < 10%", f"{low_margin_count}")

    st.divider()

    st.subheader("Распределение маржинальности")
    if len(margins) > 0:
        bins = [-float("inf"), 0, 10, 20, 30, float("inf")]
        labels = ["<0%", "0-10%", "10-20%", "20-30%", ">30%"]
        margins_cat = pd.cut(margins, bins=bins, labels=labels, right=False)
        cat_counts = margins_cat.value_counts().reset_index()
        cat_counts.columns = ["Маржинальность", "Количество товаров"]
        fig_pie = px.pie(
            cat_counts,
            values="Количество товаров",
            names="Маржинальность",
            title="Распределение маржинальности (%)",
            hole=0.4,
        )
        st.plotly_chart(fig_pie, width="stretch")

    st.subheader("Распределение по типам стратегий")
    strategy_counts = repo.get_strategy_counts()
    if strategy_counts:
        strat_df = pd.DataFrame(
            [{"Тип": k, "Количество": v} for k, v in strategy_counts.items()]
        )
        fig_strat_pie = px.pie(
            strat_df,
            values="Количество",
            names="Тип",
            title="Распределение по типам стратегий",
            hole=0.4,
        )
        st.plotly_chart(fig_strat_pie, width="stretch")
    else:
        st.info("Нет данных о стратегиях")

    st.subheader("Эффективность стратегий (ROI)")
    strategy_roi = get_cached_strategy_roi()
    if not strategy_roi.empty:
        strategy_roi.rename(
            columns={
                "strategy_name": "Стратегия",
                "avg_abs_profit": "Средняя прибыль (₽)",
                "avg_marginality": "Средняя маржинальность (%)",
                "updates_count": "Кол-во обновлений",
            },
            inplace=True,
        )
        strategy_roi["Средняя маржинальность (%)"] *= 100
        strategy_roi["Средняя прибыль (₽)"] = strategy_roi["Средняя прибыль (₽)"].round(0)
        st.dataframe(strategy_roi, width="stretch", hide_index=True)
        fig_roi = px.bar(
            strategy_roi,
            x="Стратегия",
            y="Средняя прибыль (₽)",
            title="Средняя абсолютная прибыль по стратегиям",
        )
        st.plotly_chart(fig_roi, width="stretch")
    else:
        st.info("Недостаточно данных")