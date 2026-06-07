import streamlit as st
import pandas as pd
from config.settings import TIMEZONE
from ui.cache import get_repo


def render_history_tab():
    st.header("История изменений")
    repo = get_repo()
    # Используем новый метод репозитория, если он есть
    try:
        hist_df = repo.get_recent_history(limit=100)
    except AttributeError:
        # fallback для старых версий
        with repo._get_connection() as conn:
            hist_df = pd.read_sql_query('''
                SELECT 
                    p.sku as "SKU",
                    ph.timestamp,
                    ROUND(ph.result_target_price * ph.discount_coef, 0) as "Цена",
                    ph.marginality as "Маржинальность"
                FROM product_price_history ph
                JOIN product p ON p.product_id = ph.product_id
                ORDER BY ph.timestamp DESC
                LIMIT 100
            ''', conn)

    if not hist_df.empty:
        hist_df['timestamp'] = pd.to_datetime(hist_df['timestamp'])
        hist_df['timestamp'] = hist_df['timestamp'].dt.tz_localize('UTC').dt.tz_convert(TIMEZONE)
        hist_df['Маржинальность'] = (hist_df['Маржинальность'] * 100).round(2)
        hist_df.rename(columns={'timestamp': 'Время (МСК)'}, inplace=True)
        st.dataframe(hist_df, width="stretch", hide_index=True)
    else:
        st.info("История пуста. Запустите репрайсер для накопления данных.")