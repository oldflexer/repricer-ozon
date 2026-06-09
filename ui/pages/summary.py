import streamlit as st
import plotly.express as px
from ui.cache import get_repo


def render_summary():
    st.header("📊 Сводка")
    repo = get_repo()

    # Графики за последнюю неделю
    st.subheader("Динамика за последние 7 дней")
    daily_df = repo.get_daily_trends(days=7)
    if not daily_df.empty:
        daily_df['day'] = daily_df['day'].astype(str)
        daily_df['avg_margin'] = daily_df['avg_margin'] * 100

        col1, col2 = st.columns(2)
        with col1:
            fig_price = px.line(daily_df, x='day', y='avg_price',
                                title='Средняя цена (реальная)',
                                labels={'day': 'Дата', 'avg_price': 'Цена (₽)'})
            st.plotly_chart(fig_price, width="stretch")
        with col2:
            fig_margin = px.line(daily_df, x='day', y='avg_margin',
                                 title='Средняя маржинальность',
                                 labels={'day': 'Дата', 'avg_margin': 'Маржинальность (%)'})
            st.plotly_chart(fig_margin, width="stretch")
    else:
        st.info("Недостаточно данных для отображения динамики за неделю")

    # Дополнительная информация: топ-3 лучших и худших
    st.divider()
    col1, col2 = st.columns(2)
    top3, bottom3 = repo.get_top_bottom_marginality(limit=3)
    with col1:
        st.subheader("🏆 Топ-3 по маржинальности")
        if not top3.empty:
            st.dataframe(top3[['sku', 'product_name', 'marginality_pct']].rename(
                columns={'marginality_pct': 'Маржа, %'}
            ), hide_index=True, width="stretch")
        else:
            st.info("Нет данных")
    with col2:
        st.subheader("📉 Худшие 3 по маржинальности")
        if not bottom3.empty:
            st.dataframe(bottom3[['sku', 'product_name', 'marginality_pct']].rename(
                columns={'marginality_pct': 'Маржа, %'}
            ), hide_index=True, width="stretch")
        else:
            st.info("Нет данных")