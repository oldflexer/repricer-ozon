import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from config.settings import TIMEZONE
from ui.cache import get_repo, get_cached_products


def render_requests_page():
    st.markdown('<h2><i class="fa-solid fa-clipboard-list"></i> Запросы / Управление товарами</h2>', unsafe_allow_html=True)
    repo = get_repo()
    products = get_cached_products()
    if not products:
        st.warning("Нет данных о товарах. Запустите репрайсер хотя бы один раз.")
        return

    # Список SKU для выбора
    sku_list = [p.sku for p in products]
    selected_sku = st.selectbox("Выберите товар (SKU)", sku_list, key="request_sku_select")

    if selected_sku:
        # Находим продукт
        product = next((p for p in products if p.sku == selected_sku), None)
        if product:
            st.subheader(f"Информация о товаре: {product.sku}")
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Название:** {product.product_name or '—'}")
                st.write(f"**Product ID:** {product.product_id or '—'}")
                st.write(f"**Offer ID:** {product.offer_id or '—'}")
            with col2:
                st.write(f"**Себестоимость:** {product.cost_price:.2f} ₽")
                st.write(f"**РИЦ (мин. цена):** {product.min_price:.2f} ₽")
                st.write(f"**Реальная цена покупателя:** {product.real_customer_price or '—'} ₽")

            # Получаем историю цен
            hist = repo.get_price_history(product.sku)
            if hist:
                df_hist = pd.DataFrame(hist)
                df_hist['timestamp'] = pd.to_datetime(df_hist['timestamp'])
                df_hist['timestamp'] = df_hist['timestamp'].dt.tz_localize('UTC').dt.tz_convert(TIMEZONE)
                df_hist['customer_price'] = df_hist['customer_price'].round(0)
                df_hist['marginality_pct'] = (df_hist['marginality'] * 100).round(2)

                st.subheader("История цен")
                st.dataframe(df_hist[['timestamp', 'customer_price', 'marginality_pct']].rename(
                    columns={'timestamp': 'Дата', 'customer_price': 'Цена (₽)', 'marginality_pct': 'Маржинальность (%)'}
                ), width="stretch", hide_index=True)

                # График истории
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df_hist['timestamp'], y=df_hist['customer_price'],
                    mode='lines+markers',
                    name='Цена',
                    hovertemplate='%{x}<br>Цена: %{y:.0f} ₽<extra></extra>'
                ))
                fig.update_layout(title='Динамика цены', xaxis_title='Дата', yaxis_title='Цена (₽)')
                st.plotly_chart(fig, width="stretch")
            else:
                st.info("Нет истории цен для этого товара")

            # Кнопка удаления
            st.divider()
            st.subheader("Удаление товара")
            st.warning("Удаление товара приведёт к удалению всех связанных записей (стратегии, история цен, история маржинальности). Действие необратимо.")
            if st.button(f"Удалить товар {product.sku}", type="secondary", key="delete_product_btn", icon=":material/delete:"):
                result = repo.delete_product(product.sku)
                if result['product'] > 0:
                    st.success(f"Товар {product.sku} удалён. Удалено записей: product={result['product']}, strategies={result['strategies']}, price_history={result['price_history']}, margin_history={result['margin_history']}")
                    # Очищаем кэш, чтобы обновить список товаров
                    st.cache_data.clear()
                    st.cache_resource.clear()
                    st.rerun()
                else:
                    st.error("Не удалось удалить товар")