import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from config.settings import TIMEZONE
from ui.cache import get_repo, get_cached_products


def render_charts_tab():
    st.header("Графики")
    repo = get_repo()
    products = get_cached_products()
    if not products:
        st.info("Нет товаров в базе")
        return

    sku_options = [f"{p.sku} – {p.product_name}" for p in products]
    sku_to_sku = {opt: p.sku for opt, p in zip(sku_options, products)}
    st.subheader("Динамика цены и маржинальности")
    selected = st.multiselect(
        "Выберите товары", sku_options,
        default=sku_options[:2] if len(sku_options) >= 2 else sku_options,
        key="multi_price", width="stretch"
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