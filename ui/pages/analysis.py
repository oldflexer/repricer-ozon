"""
Страница «Анализ» дашборда.

Содержит две вкладки:
    1. Комиссии и индексы – анализ комиссий FBS и сравнение с индексами Ozon.
    2. ABC-анализ – распределение товаров по вкладу в прибыль (диаграмма Парето).
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config.settings import ABC_A_THRESHOLD, ABC_B_THRESHOLD
from ui.cache import get_cached_ozon_price_df, get_repo


def render_analysis_page() -> None:
    """
    Отрисовывает страницу «Анализ» с переключением между вкладками.
    """
    st.markdown(
        '<h2><i class="fa-solid fa-magnifying-glass-chart"></i> Анализ комиссий FBS и индексов</h2>',
        unsafe_allow_html=True,
    )

    tabs = [
        ("Комиссии и индексы", ":material/money_bag:"),
        ("ABC-анализ", ":material/pie_chart:"),
    ]

    if "analysis_tab" not in st.session_state:
        st.session_state.analysis_tab = 0

    cols = st.columns(len(tabs))
    for i, (label, icon) in enumerate(tabs):
        with cols[i]:
            if st.button(
                label,
                icon=icon,
                key=f"analysis_tab_{i}",
                use_container_width=True,
                type="primary" if st.session_state.analysis_tab == i else "secondary",
            ):
                st.session_state.analysis_tab = i
                st.rerun()

    st.divider()

    if st.session_state.analysis_tab == 0:
        render_commissions_analysis()
    else:
        render_abc_analysis()


def render_commissions_analysis() -> None:
    """
    Отрисовывает вкладку анализа комиссий и индексов.
    """
    repo = get_repo()
    analysis_df = repo.get_commission_analysis()

    if analysis_df.empty:
        st.info("Нет данных для анализа. Запустите репрайсер.")
        return

    # Расчёт дополнительных полей
    analysis_df["fbs_first_mile_avg"] = (
        analysis_df["fbs_first_mile_min_amount"] + analysis_df["fbs_first_mile_max_amount"]
    ) / 2
    analysis_df["fbs_direct_flow_avg"] = (
        analysis_df["fbs_direct_flow_trans_min_amount"]
        + analysis_df["fbs_direct_flow_trans_max_amount"]
    ) / 2
    analysis_df["sales_commission"] = analysis_df["result_target_price"] * (
        analysis_df["sales_percent_fbs"] / 100
    )
    analysis_df["total_extra_costs"] = (
        analysis_df["sales_commission"]
        + analysis_df["fbs_first_mile_avg"]
        + analysis_df["fbs_direct_flow_avg"]
        + analysis_df["fbs_deliv_to_customer_amount"]
    )

    st.subheader("Сводка по комиссиям")
    cols = [
        "sales_percent_fbs",
        "fbs_first_mile_avg",
        "fbs_direct_flow_avg",
        "fbs_deliv_to_customer_amount",
        "total_extra_costs",
    ]
    st.dataframe(
        analysis_df[["sku", "product_name"] + cols].round(2),
        width="stretch",
    )

    st.subheader("Сравнение с индексами")
    with_index = analysis_df[analysis_df["ozon_index_data_price"] > 0]
    if not with_index.empty:
        st.write("Товары, имеющие индекс Ozon:")
        st.dataframe(
            with_index[["sku", "product_name", "ozon_index_data_price", "real_price"]].round(0),
            width="stretch",
        )
    else:
        st.info("Нет товаров с индексом Ozon.")

    st.subheader("Корреляция маржинальности и индекса Ozon")
    fig_corr = px.scatter(
        analysis_df,
        x="ozon_index_data_index",
        y="marginality",
        title="Зависимость маржинальности от индекса Ozon",
        labels={
            "ozon_index_data_index": "Индекс Ozon (коэффициент)",
            "marginality": "Маржинальность",
        },
    )
    st.plotly_chart(fig_corr, width="stretch")

    st.subheader("Зависимость цены от индекса Ozon")
    ozon_price_df = get_cached_ozon_price_df()
    if not ozon_price_df.empty:
        fig_scatter = px.scatter(
            ozon_price_df,
            x="ozon_index_data_price",
            y="real_price",
            color="marginality",
            hover_data=["sku", "product_name"],
            title="Цена покупателя vs Индекс Ozon (цвет – маржинальность)",
            labels={
                "ozon_index_data_price": "Индекс Ozon (₽)",
                "real_price": "Реальная цена покупателя (₽)",
                "marginality": "Маржинальность",
            },
            color_continuous_scale="RdYlGn",
            range_color=[-0.2, 0.4],
        )
        max_val = max(
            ozon_price_df["ozon_index_data_price"].max(),
            ozon_price_df["real_price"].max(),
        )
        fig_scatter.add_trace(
            go.Scatter(
                x=[0, max_val],
                y=[0, max_val],
                mode="lines",
                name="y=x",
                line={"dash": "dash", "color": "gray"},
                line={"dash": "dash", "color": "gray"},
            )
        )
        st.plotly_chart(fig_scatter, width="stretch")

        above = (ozon_price_df["real_price"] > ozon_price_df["ozon_index_data_price"]).sum()
        below = (ozon_price_df["real_price"] < ozon_price_df["ozon_index_data_price"]).sum()
        equal = (ozon_price_df["real_price"] == ozon_price_df["ozon_index_data_price"]).sum()
        st.markdown(
            f"**Товаров с ценой выше индекса:** {above} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"**Ниже индекса:** {below} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"**Равна индексу:** {equal}"
        )
    else:
        st.info("Нет товаров с индексом Ozon для анализа зависимости.")


def render_abc_analysis() -> None:
    """
    Отрисовывает вкладку ABC-анализа (диаграмма Парето).
    """
    st.subheader("ABC-анализ товаров")
    repo = get_repo()

    with repo._get_connection() as conn:
        df = pd.read_sql_query(
            """
            SELECT
                p.sku,
                p.product_name,
                p.net_price as cost_price,
                COALESCE(p.real_customer_price, ph.customer_price) as real_price,
                ph.marginality
            FROM (
                SELECT product_id,
                    CASE WHEN real_price IS NOT NULL THEN real_price
                         ELSE result_target_price * discount_coef END as customer_price,
                    marginality,
                    ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY timestamp DESC) as rn
                FROM product_price_history
            ) ph
            JOIN product p ON p.product_id = ph.product_id
            WHERE ph.rn = 1
            """,
            conn,
        )

    if df.empty:
        st.info("Нет данных для ABC-анализа")
        return

    # Расчёт прибыли на единицу товара
    df["profit"] = df["real_price"] - df["cost_price"]
    df["profit_positive"] = df["profit"].clip(lower=0)

    total_profit = df["profit_positive"].sum()
    if total_profit == 0:
        st.warning("Суммарная прибыль равна нулю, ABC-анализ невозможен")
        return

    # Сортируем по убыванию прибыли
    df_sorted = df.sort_values("profit_positive", ascending=False).reset_index(drop=True)
    df_sorted["cumulative_profit"] = df_sorted["profit_positive"].cumsum()
    df_sorted["cumulative_percent"] = df_sorted["cumulative_profit"] / total_profit * 100

    def assign_category(percent: float) -> str:
        """Определяет категорию A/B/C по накопленному проценту."""
        if percent <= ABC_A_THRESHOLD:
            return "A"
        if percent <= ABC_B_THRESHOLD:
            return "B"
        return "C"

    df_sorted["category"] = df_sorted["cumulative_percent"].apply(assign_category)

    # Группировка по категориям
    category_stats = (
        df_sorted.groupby("category")
        .agg(
            количество=("sku", "count"),
            суммарная_прибыль=("profit_positive", "sum"),
            доля_прибыли=("profit_positive", lambda x: x.sum() / total_profit * 100),
        )
        .round(2)
    )

    col1, col2 = st.columns(2)
    with col1:
        st.write("**Распределение по категориям**")
        st.dataframe(category_stats, width="stretch")
    with col2:
        fig_pie = px.pie(
            category_stats,
            values="количество",
            names=category_stats.index,
            title="Количество товаров по категориям",
            hole=0.3,
        )
        st.plotly_chart(fig_pie, width="stretch")

    # Диаграмма Парето
    st.subheader("Диаграмма Парето")
    top_n = 20
    top_df = df_sorted.head(top_n).copy()
    top_df["sku_str"] = top_df["sku"].astype(str)

    fig_pareto = go.Figure()
    fig_pareto.add_trace(
        go.Bar(
            x=top_df["sku_str"],
            y=top_df["profit_positive"],
            name="Прибыль на товар (₽)",
            marker_color="steelblue",
        )
    )
    fig_pareto.add_trace(
        go.Scatter(
            x=top_df["sku_str"],
            y=top_df["cumulative_percent"],
            name="Накопленный процент",
            yaxis="y2",
            mode="lines+markers",
            line={"color": "red", "width": 2},
            line={"color": "red", "width": 2},
        )
    )
    fig_pareto.update_layout(
        title=f"ABC-анализ по прибыли (топ-{top_n} товаров, от большей прибыли к меньшей)",
        xaxis_title="SKU",
        yaxis_title="Прибыль (₽)",
        yaxis2={
            "title": "Накопленный процент (%)",
            "overlaying": "y",
            "side": "right",
            "range": [0, 100],
            "title": "Накопленный процент (%)",
            "overlaying": "y",
            "side": "right",
            "range": [0, 100],
        },
        legend={"x": 0.01, "y": 0.99},
        legend={"x": 0.01, "y": 0.99},
        width=None,
    )
    fig_pareto.update_xaxes(type="category")
    st.plotly_chart(fig_pareto, width="stretch")

    st.subheader("Таблица ABC-категорий")
    st.dataframe(
        df_sorted[
            ["sku", "product_name", "profit_positive", "cumulative_percent", "category"]
        ].rename(
            columns={
                "profit_positive": "Прибыль (₽)",
                "cumulative_percent": "Накопленный %",
                "category": "Категория",
            }
        ),
        width="stretch",
        hide_index=True,
    )

    st.caption(
        "ABC-анализ проведён по вкладу в общую прибыль (реальная цена - себестоимость). "
        "Категории: A — 80% прибыли, B — следующие 15%, C — остальные 5%."
    )
