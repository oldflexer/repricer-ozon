import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from ui.cache import get_repo, get_cached_ozon_price_df


def render_analysis_tab():
    st.header("Анализ комиссий FBS и индексов")
    repo = get_repo()

    analysis_df = repo.get_commission_analysis()
    if analysis_df.empty:
        st.info("Нет данных для анализа. Запустите репрайсер.")
        return

    # Расчёт дополнительных полей
    analysis_df['fbs_first_mile_avg'] = (analysis_df['fbs_first_mile_min_amount'] + analysis_df['fbs_first_mile_max_amount']) / 2
    analysis_df['fbs_direct_flow_avg'] = (analysis_df['fbs_direct_flow_trans_min_amount'] + analysis_df['fbs_direct_flow_trans_max_amount']) / 2
    analysis_df['sales_commission'] = analysis_df['result_target_price'] * (analysis_df['sales_percent_fbs'] / 100)
    analysis_df['total_extra_costs'] = analysis_df['sales_commission'] + analysis_df['fbs_first_mile_avg'] + analysis_df['fbs_direct_flow_avg'] + analysis_df['fbs_deliv_to_customer_amount']

    st.subheader("Сводка по комиссиям")
    cols = ['sales_percent_fbs', 'fbs_first_mile_avg', 'fbs_direct_flow_avg', 'fbs_deliv_to_customer_amount', 'total_extra_costs']
    st.dataframe(analysis_df[['sku', 'product_name'] + cols].round(2), width="stretch")

    st.subheader("Сравнение с индексами")
    with_index = analysis_df[analysis_df['ozon_index_data_price'] > 0]
    if not with_index.empty:
        st.write("Товары, имеющие индекс Ozon:")
        st.dataframe(with_index[['sku', 'product_name', 'ozon_index_data_price', 'real_price']].round(0), width="stretch")
    else:
        st.info("Нет товаров с индексом Ozon.")

    st.subheader("Корреляция маржинальности и индекса Ozon")
    fig_corr = px.scatter(analysis_df, x='ozon_index_data_index', y='marginality',
                          title="Зависимость маржинальности от индекса Ozon",
                          labels={'ozon_index_data_index': 'Индекс Ozon (коэффициент)', 'marginality': 'Маржинальность'})
    st.plotly_chart(fig_corr, width="stretch")

    st.subheader("Зависимость цены от индекса Ozon")
    ozon_price_df = get_cached_ozon_price_df()
    if not ozon_price_df.empty:
        fig_scatter = px.scatter(
            ozon_price_df,
            x='ozon_index_data_price',
            y='real_price',
            color='marginality',
            hover_data=['sku', 'product_name'],
            title='Цена покупателя vs Индекс Ozon (цвет – маржинальность)',
            labels={
                'ozon_index_data_price': 'Индекс Ozon (₽)',
                'real_price': 'Реальная цена покупателя (₽)',
                'marginality': 'Маржинальность'
            },
            color_continuous_scale='RdYlGn',
            range_color=[-0.2, 0.4]
        )
        max_val = max(ozon_price_df['ozon_index_data_price'].max(), ozon_price_df['real_price'].max())
        fig_scatter.add_trace(go.Scatter(
            x=[0, max_val],
            y=[0, max_val],
            mode='lines',
            name='y=x',
            line=dict(dash='dash', color='gray')
        ))
        st.plotly_chart(fig_scatter, width="stretch")
        above = (ozon_price_df['real_price'] > ozon_price_df['ozon_index_data_price']).sum()
        below = (ozon_price_df['real_price'] < ozon_price_df['ozon_index_data_price']).sum()
        equal = (ozon_price_df['real_price'] == ozon_price_df['ozon_index_data_price']).sum()
        st.markdown(f"**Товаров с ценой выше индекса:** {above} &nbsp;&nbsp;|&nbsp;&nbsp; **Ниже индекса:** {below} &nbsp;&nbsp;|&nbsp;&nbsp; **Равна индексу:** {equal}")
    else:
        st.info("Нет товаров с индексом Ozon для анализа зависимости.")