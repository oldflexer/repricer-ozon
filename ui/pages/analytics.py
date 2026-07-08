import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from config.settings import TIMEZONE
from ui.cache import get_repo, get_cached_products


def render_analytics():
    st.markdown('<h2><i class="fa-solid fa-chart-line"></i> Аналитика</h2>', unsafe_allow_html=True)

    # Вкладки с Material Icons (поддерживаются нативно)
    tabs = [
        ("Динамика", ":material/ssid_chart:"),
        ("Прогнозирование", ":material/mystery:"),
        ("Отклонения индексов", ":material/show_chart:")
    ]

    if "analytics_tab" not in st.session_state:
        st.session_state.analytics_tab = 0

    cols = st.columns(len(tabs))
    for i, (label, icon) in enumerate(tabs):
        with cols[i]:
            if st.button(
                label,
                icon=icon,
                key=f"analytics_tab_{i}",
                use_container_width=True,
                type="primary" if st.session_state.analytics_tab == i else "secondary"
            ):
                st.session_state.analytics_tab = i
                st.rerun()

    st.divider()

    if st.session_state.analytics_tab == 0:
        render_dynamics()
    elif st.session_state.analytics_tab == 1:
        render_forecasting()
    else:
        render_index_deviation()


def render_dynamics():
    """Вкладка динамики цен и маржинальности по выбранным товарам"""
    repo = get_repo()
    products = get_cached_products()
    if not products:
        st.info("Нет товаров в базе")
        return

    sku_options = [f"{p.sku} – {p.product_name}" for p in products]
    sku_to_sku = {opt: p.sku for opt, p in zip(sku_options, products)}
    selected = st.multiselect(
        "Выберите товары для отображения", sku_options,
        default=sku_options[:2] if len(sku_options) >= 2 else sku_options,
        key="analytics_multi"
    )
    if selected:
        fig_price = go.Figure()
        fig_margin = go.Figure()
        for label in selected:
            sku = sku_to_sku[label]
            hist = repo.get_price_history(sku)
            if hist:
                df = pd.DataFrame(hist)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df['timestamp'] = df['timestamp'].dt.tz_localize('UTC').dt.tz_convert(TIMEZONE)
                df['customer_price'] = df['customer_price'].round(0)
                fig_price.add_trace(go.Scatter(
                    x=df['timestamp'], y=df['customer_price'],
                    mode='lines+markers', name=label,
                    text=df['customer_price'].astype(int),
                    hovertemplate='%{x}<br>Цена: %{text} ₽<extra></extra>'
                ))
                fig_margin.add_trace(go.Scatter(
                    x=df['timestamp'], y=df['marginality'] * 100,
                    mode='lines+markers', name=label,
                    hovertemplate='%{x}<br>Маржа: %{y:.1f}%<extra></extra>'
                ))
        if fig_price.data:
            fig_price.update_layout(legend=dict(orientation="h", y=-0.2), yaxis_title="Цена (₽)")
            fig_margin.update_layout(legend=dict(orientation="h", y=-0.2), yaxis_title="Маржинальность (%)")
            st.subheader("Динамика цены")
            st.plotly_chart(fig_price, width="stretch")
            st.subheader("Динамика маржинальности")
            st.plotly_chart(fig_margin, width="stretch")
    else:
        st.info("Выберите товары для отображения графиков")


def render_forecasting():
    """Вкладка прогнозирования общих трендов (средняя цена и маржинальность)"""
    repo = get_repo()

    # Получаем исторические данные за последние 60 дней
    daily_df = repo.get_daily_trends(days=60)
    if daily_df.empty:
        st.warning("Недостаточно исторических данных для прогнозирования", icon=":material/warning:")
        return

    # Параметры прогноза
    col1, col2 = st.columns(2)
    with col1:
        degree = st.selectbox("Степень полинома", options=[2, 3, 4], index=0,
                              help="Степень полинома для аппроксимации тренда (2 – парабола, 3 – кубическая и т.д.)",
                              key="poly_degree")
    with col2:
        forecast_days = st.slider("Период прогноза (дней)", min_value=1, max_value=30, value=7, step=1,
                                  key="forecast_days")

    # Подготовка данных
    daily_df['day'] = pd.to_datetime(daily_df['day'])
    daily_df['avg_price'] = pd.to_numeric(daily_df['avg_price'], errors='coerce')
    daily_df['avg_margin'] = pd.to_numeric(daily_df['avg_margin'], errors='coerce')
    daily_df = daily_df.dropna(subset=['avg_price', 'avg_margin'])
    daily_df = daily_df.sort_values('day')

    if daily_df.empty:
        st.warning("Недостаточно числовых данных для прогнозирования", icon=":material/warning:")
        return

    # Переводим маржинальность в проценты (0-100)
    daily_df['avg_margin_pct'] = daily_df['avg_margin'] * 100

    # Используем последние train_len дней для построения тренда (все доступные)
    train_len = len(daily_df)
    x_train = np.arange(train_len)
    price_train = daily_df['avg_price'].astype(float).to_numpy()
    margin_train = daily_df['avg_margin_pct'].astype(float).to_numpy()

    # Проверяем, что данных достаточно для выбранной степени
    if train_len <= degree:
        st.warning(f"Недостаточно данных для полинома степени {degree}. Нужно больше {degree} точек.", icon=":material/warning:")
        return

    # Полиномиальная регрессия для цены
    price_coeffs = np.polyfit(x_train, price_train, degree)
    price_poly = np.poly1d(price_coeffs)

    # Полиномиальная регрессия для маржинальности
    margin_coeffs = np.polyfit(x_train, margin_train, degree)
    margin_poly = np.poly1d(margin_coeffs)

    # Прогноз на будущие дни (используем индексы от 0 до train_len+forecast_days-1)
    total_len = train_len + forecast_days
    x_full = np.arange(total_len)
    price_forecast_full = price_poly(x_full)
    margin_forecast_full = margin_poly(x_full)

    # Ограничиваем прогноз разумными пределами
    price_forecast_full = np.maximum(price_forecast_full, 0)
    margin_forecast_full = np.clip(margin_forecast_full, 0, 100)

    # Даты: исторические + прогнозные
    last_date = daily_df['day'].max()
    forecast_dates = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=forecast_days)
    all_dates = list(daily_df['day']) + list(forecast_dates)

    # Разделяем на историю и прогноз
    hist_price = price_forecast_full[:train_len]
    forecast_price = price_forecast_full[train_len:]
    hist_margin = margin_forecast_full[:train_len]
    forecast_margin = margin_forecast_full[train_len:]

    # Создаём DataFrame для графика
    df_plot = pd.DataFrame({
        'day': all_dates,
        'price_actual': list(daily_df['avg_price']) + [None] * forecast_days,
        'price_trend': list(hist_price) + list(forecast_price),
        'margin_actual': list(daily_df['avg_margin_pct']) + [None] * forecast_days,
        'margin_trend': list(hist_margin) + list(forecast_margin),
        'type': ['История'] * train_len + ['Прогноз'] * forecast_days
    })

    # График цены (фактические точки + кривая тренда)
    st.subheader(f"Прогноз средней цены (полином степени {degree})")
    fig_price = go.Figure()
    fig_price.add_trace(go.Scatter(
        x=df_plot['day'], y=df_plot['price_actual'],
        mode='markers',
        name='Факт',
        marker=dict(color='blue', size=6)
    ))
    fig_price.add_trace(go.Scatter(
        x=df_plot['day'], y=df_plot['price_trend'],
        mode='lines',
        name='Тренд + прогноз',
        line=dict(color='red', width=2, dash='solid')
    ))
    fig_price.update_layout(
        title='Средняя цена (факт и тренд)',
        xaxis_title='Дата',
        yaxis_title='Цена (₽)',
        legend=dict(orientation="h", y=-0.2)
    )
    st.plotly_chart(fig_price, width="stretch")

    # График маржинальности
    st.subheader(f"Прогноз средней маржинальности (полином степени {degree})")
    fig_margin = go.Figure()
    fig_margin.add_trace(go.Scatter(
        x=df_plot['day'], y=df_plot['margin_actual'],
        mode='markers',
        name='Факт',
        marker=dict(color='blue', size=6)
    ))
    fig_margin.add_trace(go.Scatter(
        x=df_plot['day'], y=df_plot['margin_trend'],
        mode='lines',
        name='Тренд + прогноз',
        line=dict(color='red', width=2, dash='solid')
    ))
    fig_margin.update_layout(
        title='Средняя маржинальность (факт и тренд)',
        xaxis_title='Дата',
        yaxis_title='Маржинальность (%)',
        legend=dict(orientation="h", y=-0.2)
    )
    st.plotly_chart(fig_margin, width="stretch")

    # Детали прогноза
    with st.expander("Детали прогноза"):
        st.write(f"**Использовано дней истории:** {train_len}")
        st.write(f"**Степень полинома:** {degree}")
        st.write(f"**Прогнозируемая средняя цена через {forecast_days} дней:** {forecast_price[-1]:.0f} ₽")
        st.write(f"**Прогнозируемая средняя маржинальность через {forecast_days} дней:** {forecast_margin[-1]:.1f}%")
        st.caption("Прогноз построен методом полиномиальной регрессии (кривая) по историческим данным. Реальная динамика может отличаться.")
        

def render_index_deviation():
    """Вкладка динамики среднего отклонения от индекса Ozon"""
    repo = get_repo()
    daily_deviation = repo.get_daily_deviation(days=30)
    if not daily_deviation.empty:
        daily_deviation['day'] = pd.to_datetime(daily_deviation['day'])
        fig_dev = px.line(daily_deviation, x='day', y='avg_ratio',
                          title='Среднее отношение цены к индексу Ozon (30 дней)',
                          labels={'day': 'Дата', 'avg_ratio': 'Отношение (наша цена / индекс)'})
        st.plotly_chart(fig_dev, width="stretch")
    else:
        st.info("Нет данных с индексом Ozon для отображения отклонений")