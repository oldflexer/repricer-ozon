import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from config.settings import TIMEZONE
from ui.cache import get_repo, get_cached_products


def render_analytics():
    st.header("📈 Аналитика")

    tab1, tab2, tab3 = st.tabs(["📊 Динамика", "🔮 Прогнозирование", "📉 Отклонения индексов"])

    with tab1:
        render_dynamics()
    with tab2:
        render_forecasting()
    with tab3:
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
        st.warning("Недостаточно исторических данных для прогнозирования")
        return

    # Параметры прогноза
    col1, col2 = st.columns(2)
    with col1:
        window = st.slider("Окно сглаживания (дней)", min_value=3, max_value=30, value=7, step=1,
                           help="Скользящее среднее для сглаживания исторических данных",
                           key="forecast_window")
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
        st.warning("Недостаточно числовых данных для прогнозирования")
        return

    # Переводим маржинальность в проценты (0-100) для наглядности
    daily_df['avg_margin_pct'] = daily_df['avg_margin'] * 100

    # Сглаживаем ряды скользящим средним
    price_smoothed = daily_df['avg_price'].rolling(window=window, min_periods=1).mean()
    margin_smoothed = daily_df['avg_margin_pct'].rolling(window=window, min_periods=1).mean()

    daily_df['price_smoothed'] = price_smoothed
    daily_df['margin_smoothed'] = margin_smoothed

    # Линейная регрессия для прогноза (используем последние 2*window точек для тренда)
    train_len = min(len(daily_df), max(14, window * 2))
    x_train = np.arange(train_len)
    price_train = daily_df['price_smoothed'].iloc[-train_len:].astype(float).to_numpy()
    margin_train = daily_df['margin_smoothed'].iloc[-train_len:].astype(float).to_numpy()

    # Линейная регрессия для цены
    if len(x_train) > 1:
        price_coeffs = np.polyfit(x_train, price_train, 1)
        price_trend = price_coeffs[0]
        price_intercept = price_coeffs[1]
    else:
        price_trend = 0
        price_intercept = price_train[0] if len(price_train) > 0 else 0

    # Линейная регрессия для маржинальности
    if len(x_train) > 1:
        margin_coeffs = np.polyfit(x_train, margin_train, 1)
        margin_trend = margin_coeffs[0]
        margin_intercept = margin_coeffs[1]
    else:
        margin_trend = 0
        margin_intercept = margin_train[0] if len(margin_train) > 0 else 0

    # Прогноз
    last_x = train_len - 1
    forecast_x = np.arange(last_x + 1, last_x + forecast_days + 1)
    price_forecast = price_intercept + price_trend * forecast_x
    margin_forecast = margin_intercept + margin_trend * forecast_x

    price_forecast = np.maximum(price_forecast, 0)
    margin_forecast = np.clip(margin_forecast, 0, 100)

    last_date = daily_df['day'].max()
    forecast_dates = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=forecast_days)

    hist_price = daily_df[['day', 'price_smoothed']].rename(columns={'price_smoothed': 'avg_price'}).assign(type='История')
    hist_margin = daily_df[['day', 'margin_smoothed']].rename(columns={'margin_smoothed': 'avg_margin'}).assign(type='История')

    forecast_price_df = pd.DataFrame({'day': forecast_dates, 'avg_price': price_forecast, 'type': 'Прогноз'})
    forecast_margin_df = pd.DataFrame({'day': forecast_dates, 'avg_margin': margin_forecast, 'type': 'Прогноз'})

    combined_price = pd.concat([hist_price, forecast_price_df])
    combined_margin = pd.concat([hist_margin, forecast_margin_df])

    st.subheader(f"Прогноз средней цены (линейный тренд, окно={window})")
    fig_price = px.line(combined_price, x='day', y='avg_price', color='type',
                        title='Средняя цена', labels={'day': 'Дата', 'avg_price': 'Цена (₽)', 'type': ''})
    st.plotly_chart(fig_price, width="stretch")

    st.subheader(f"Прогноз средней маржинальности (линейный тренд, окно={window})")
    fig_margin = px.line(combined_margin, x='day', y='avg_margin', color='type',
                         title='Средняя маржинальность',
                         labels={'day': 'Дата', 'avg_margin': 'Маржинальность (%)', 'type': ''})
    st.plotly_chart(fig_margin, width="stretch")

    with st.expander("📊 Детали прогноза"):
        st.write(f"**Использовано дней истории:** {len(daily_df)}")
        st.write(f"**Окно сглаживания:** {window} дней")
        st.write(f"**Тренд цены:** {price_trend:.2f} ₽ в день")
        st.write(f"**Тренд маржинальности:** {margin_trend:.2f} процентных пункта в день")
        st.write(f"**Прогнозируемая средняя цена через {forecast_days} дней:** {price_forecast[-1]:.0f} ₽")
        st.write(f"**Прогнозируемая средняя маржинальность через {forecast_days} дней:** {margin_forecast[-1]:.1f}%")
        st.caption("Прогноз построен методом линейной регрессии по сглаженным данным. Реальная динамика может отличаться.")


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