import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from config.settings import TIMEZONE
from ui.cache import get_repo, get_cached_last_prices, get_cached_strategy_roi, get_cached_products


def render_statistics_tab():
    st.header("Сводная статистика")
    repo = get_repo()

    # Основные метрики через оптимизированный метод
    last_prices_df = get_cached_last_prices()
    if last_prices_df.empty:
        st.warning("Нет данных для статистики.")
        return

    total_products = len(last_prices_df)
    avg_price = last_prices_df['last_price'].mean()
    med_price = last_prices_df['last_price'].median()
    margins = last_prices_df['last_margin'] * 100
    avg_margin = margins.mean()
    med_margin = margins.median()
    min_margin = margins.min()
    max_margin = margins.max()
    low_margin_count = (margins < 10).sum()

    # Подсчёт стратегий
    strategy_counts = repo.get_strategy_counts()

    # Метрики
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Всего товаров", total_products)
    col2.metric("Средняя цена", f"{avg_price:.0f} ₽")
    col3.metric("Медианная цена", f"{med_price:.0f} ₽")
    col4.metric("Средняя маржинальность", f"{avg_margin:.2f}%")
    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Медианная маржа", f"{med_margin:.2f}%")
    col6.metric("Мин. маржа", f"{min_margin:.2f}%")
    col7.metric("Макс. маржа", f"{max_margin:.2f}%")
    col8.metric("Товаров с маржей < 10%", f"{low_margin_count}")

    st.divider()
    st.subheader("Распределение маржинальности")
    if len(margins) > 0:
        bins = [-float('inf'), 0, 10, 20, 30, float('inf')]
        labels = ['<0%', '0-10%', '10-20%', '20-30%', '>30%']
        margins_cat = pd.cut(margins, bins=bins, labels=labels, right=False)
        cat_counts = margins_cat.value_counts().reset_index()
        cat_counts.columns = ['Маржинальность', 'Количество товаров']
        fig_pie = px.pie(cat_counts, values='Количество товаров', names='Маржинальность',
                         title='Распределение маржинальности (%)', hole=0.4)
        st.plotly_chart(fig_pie, width="stretch")

    st.subheader("Распределение по типам стратегий")
    strat_df = pd.DataFrame([{"Тип": k, "Количество": v} for k, v in strategy_counts.items()])
    fig_strat_pie = px.pie(strat_df, values='Количество', names='Тип',
                           title='Распределение по типам стратегий', hole=0.4)
    st.plotly_chart(fig_strat_pie, width="stretch")

    # --- Дополнительная аналитика ---
    st.divider()
    st.subheader("Эффективность стратегий")
    strategy_perf = repo.get_strategy_performance(days=30)
    if not strategy_perf.empty:
        st.dataframe(strategy_perf, width="stretch", hide_index=True)

    st.subheader("Динамика среднего отклонения от индекса Ozon")
    daily_deviation = repo.get_daily_deviation(days=30)
    if not daily_deviation.empty:
        daily_deviation['day'] = pd.to_datetime(daily_deviation['day'])
        fig_dev = px.line(daily_deviation, x='day', y='avg_ratio',
                          title='Среднее отношение нашей цены к индексу Ozon (за 30 дней)',
                          labels={'day': 'Дата', 'avg_ratio': 'Отношение (наша цена / индекс)'})
        st.plotly_chart(fig_dev, width="stretch")
    else:
        st.info("Нет данных с индексом Ozon для построения динамики.")

    st.subheader("Товары с неизменной ценой более 7 дней")
    stale_products = repo.get_stale_products(days=7)
    if not stale_products.empty:
        stale_products['last_update'] = pd.to_datetime(stale_products['last_update']).dt.tz_localize('UTC').dt.tz_convert(TIMEZONE)
        stale_products['days_stale'] = stale_products['days_stale'].round(1)
        stale_products.rename(columns={'sku': 'SKU', 'product_name': 'Название', 'last_update': 'Последнее обновление', 'days_stale': 'Дней без изменений'}, inplace=True)
        st.dataframe(stale_products, width="stretch", hide_index=True)
    else:
        st.success("Нет товаров с неизменной ценой более 7 дней.")

    st.subheader("Тепловая карта времени обновлений")
    heatmap_data = repo.get_update_heatmap(days=90)
    if not heatmap_data.empty:
        weekday_map = {0: 'Вс', 1: 'Пн', 2: 'Вт', 3: 'Ср', 4: 'Чт', 5: 'Пт', 6: 'Сб'}
        heatmap_data['weekday_label'] = heatmap_data['weekday'].astype(int).map(weekday_map)
        pivot = heatmap_data.pivot(index='hour', columns='weekday_label', values='updates').fillna(0)
        correct_order = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
        pivot = pivot.reindex(columns=correct_order, fill_value=0)
        fig_heatmap = px.imshow(pivot,
                                labels=dict(x="День недели", y="Час (МСК)", color="Количество обновлений"),
                                title="Тепловая карта обновлений цен (последние 90 дня)",
                                aspect="auto",
                                color_continuous_scale="Viridis")
        st.plotly_chart(fig_heatmap, width="stretch")
    else:
        st.info("Недостаточно данных для тепловой карты.")

    # Эффективность стратегий (ROI)
    st.divider()
    st.subheader("Эффективность стратегий (ROI)")
    strategy_roi = get_cached_strategy_roi()
    if not strategy_roi.empty:
        strategy_roi.rename(columns={
            'strategy_name': 'Стратегия',
            'avg_abs_profit': 'Средняя прибыль (₽)',
            'avg_marginality': 'Средняя маржинальность (%)',
            'updates_count': 'Кол-во обновлений'
        }, inplace=True)
        strategy_roi['Средняя маржинальность (%)'] = strategy_roi['Средняя маржинальность (%)'] * 100
        strategy_roi['Средняя прибыль (₽)'] = strategy_roi['Средняя прибыль (₽)'].round(0)
        st.dataframe(strategy_roi, width="stretch", hide_index=True)
        fig_roi = px.bar(strategy_roi, x='Стратегия', y='Средняя прибыль (₽)',
                         title='Средняя абсолютная прибыль по стратегиям (за 30 дней)')
        st.plotly_chart(fig_roi, width="stretch")
    else:
        st.info("Недостаточно данных для анализа эффективности стратегий.")

    # Динамика за последнюю неделю
    st.divider()
    st.subheader("Динамика за последнюю неделю")
    daily_df = repo.get_daily_trends(days=7)
    if not daily_df.empty:
        daily_df['day'] = pd.to_datetime(daily_df['day'])
        daily_df['avg_margin'] = daily_df['avg_margin'] * 100
        fig_price_trend = px.line(daily_df, x='day', y='avg_price', title='Средняя цена (реальная) за неделю')
        st.plotly_chart(fig_price_trend, width="stretch")
        fig_margin_trend = px.line(daily_df, x='day', y='avg_margin', title='Средняя маржинальность за неделю')
        st.plotly_chart(fig_margin_trend, width="stretch")

    # Лучшие и худшие по маржинальности
    st.subheader("Лучшие и худшие по маржинальности")
    top5, bottom5 = repo.get_top_bottom_marginality(limit=5)
    if not top5.empty:
        col_top, col_bottom = st.columns(2)
        with col_top:
            st.write("**Топ-5 по маржинальности**")
            st.dataframe(top5[['sku', 'product_name', 'marginality_pct']].rename(columns={'marginality_pct': 'Маржа, %'}), hide_index=True, width="stretch")
        with col_bottom:
            st.write("**Худшие 5 по маржинальности**")
            st.dataframe(bottom5[['sku', 'product_name', 'marginality_pct']].rename(columns={'marginality_pct': 'Маржа, %'}), hide_index=True, width="stretch")

    # Последние изменения
    st.subheader("Последние 10 изменений цен")
    recent_df = repo.get_recent_changes(limit=10)
    if not recent_df.empty:
        recent_df['timestamp'] = pd.to_datetime(recent_df['timestamp']).dt.tz_localize('UTC').dt.tz_convert(TIMEZONE)
        recent_df.rename(columns={'timestamp': 'Время (МСК)', 'price': 'Цена (₽)', 'margin_pct': 'Маржа, %'}, inplace=True)
        st.dataframe(recent_df, width="stretch", hide_index=True)

    # Экспорт
    st.divider()
    if st.button("📥 Экспорт истории цен в CSV", width="stretch"):
        export_df = repo.export_full_history()
        csv = export_df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button("Скачать CSV", csv, "price_history.csv", "text/csv", width="stretch")

    st.caption("Статистика основана на последней записи в истории цен каждого товара.")