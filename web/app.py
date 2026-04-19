import streamlit as st
import pandas as pd
import asyncio
import threading
import logging
from pathlib import Path
import sys
from datetime import datetime
import pytz

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import DATA_FILE, DATABASE_PATH, TIMEZONE
from src.database import Database
from src.loader import DataLoader
from src.main import Repricer

st.set_page_config(page_title="Репрайсер Ozon", layout="wide")
st.title("🔄 Репрайсер Ozon")

# --- Аутентификация ---
def check_password():
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    WEB_USER = os.getenv("WEB_USER", "admin")
    WEB_PASS = os.getenv("WEB_PASS", "admin")
    
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        with st.form("login"):
            username = st.text_input("Логин")
            password = st.text_input("Пароль", type="password")
            submit = st.form_submit_button("Войти")
            if submit:
                if username == WEB_USER and password == WEB_PASS:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Неверный логин или пароль")
        return False
    return True

if not check_password():
    st.stop()

db = Database(DATABASE_PATH)

# --- Функция запуска репрайсера ---
def run_repricer_async():
    async def _run():
        repricer = Repricer(dry_run=False)
        return await repricer.run()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_run())
    finally:
        loop.close()

def run_repricer_thread():
    return run_repricer_async()

# --- Боковая панель ---
with st.sidebar:
    st.header("Управление")
    
    # Кнопка запуска
    if st.button("🚀 Запустить репрайсинг сейчас", type="primary", use_container_width=True):
        with st.spinner("Выполняется парсинг и расчёт цен..."):
            result = run_repricer_thread()
            if result:
                st.success(f"✅ Готово! Обновлено цен: {result.get('prices_updated', 0)}")
                if result.get('errors'):
                    st.warning(f"⚠️ Ошибки: {', '.join(result['errors'])}")
            else:
                st.error("❌ Ошибка выполнения")
        st.rerun()
    
    # Последний запуск в МСК
    last_run_utc = db.get_last_run_time()
    if last_run_utc:
        last_run_msk = last_run_utc.astimezone(TIMEZONE)
        st.metric("Последний запуск (МСК)", last_run_msk.strftime("%Y-%m-%d %H:%M"))
    else:
        st.metric("Последний запуск", "—")
    
    st.divider()
    
    # Загрузка нового файла
    uploaded_file = st.file_uploader("📂 Загрузить новый Excel", type=["xlsx"])
    if uploaded_file is not None:
        # Сохраняем загруженный файл поверх DATA_FILE
        with open(DATA_FILE, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success(f"Файл загружен: {DATA_FILE.name}")
        # Предлагаем запустить репрайсер
        if st.button("Запустить с новым файлом"):
            result = run_repricer_thread()
            st.rerun()
    
    st.divider()
    st.caption(f"Файл данных: {DATA_FILE}")
    st.caption(f"База данных: {DATABASE_PATH}")

# --- Основная область с вкладками ---
tab1, tab2, tab3 = st.tabs(["📦 Товары", "🏷️ Конкуренты", "📈 История"])

with tab1:
    st.header("Текущие товары")
    products = db.get_all_products()
    if not products:
        st.warning("Нет данных о товарах. Запустите репрайсер или загрузите файл.")
    else:
        rows = []
        for p in products:
            with db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT target_price, margin, competitor_prices 
                    FROM price_history 
                    WHERE offer_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT 1
                ''', (p['offer_id'],))
                row = cursor.fetchone()
            
            target_price = row['target_price'] if row else None
            margin = row['margin'] if row else None
            competitor_prices = row['competitor_prices'] if row else "[]"
            
            avg_week = db.get_average_margin(p['offer_id'], 7)
            avg_month = db.get_average_margin(p['offer_id'], 30)
            
            rows.append({
                "SKU": p['offer_id'],
                "Название": p['product_name'],
                "Текущая цена (Ozon)": p['current_price'],
                "Целевая цена": f"{target_price:.2f}" if target_price else "—",
                "Маржа, %": f"{margin:.2f}" if margin else "—",
                "Ср. за неделю, %": f"{avg_week:.2f}" if avg_week else "—",
                "Ср. за месяц, %": f"{avg_month:.2f}" if avg_month else "—",
                "Мин. цена": p['min_price'],
                "Себестоимость": p['cost_price'],
                "Стратегия": p['strategy'],
                "Процент": p['strategy_percent'],
                "Конкуренты (цены)": competitor_prices,
            })
        
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Скачать таблицу (CSV)", csv, "repricer_export.csv", "text/csv")

with tab2:
    st.header("Цены конкурентов")
    # Собираем последние цены по каждому конкуренту для каждого товара
    comp_data = []
    for p in products:
        urls = p.get('competitor_urls', [])
        if not urls:
            continue
        # Получаем последнюю запись цен
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT competitor_prices FROM price_history 
                WHERE offer_id = ? 
                ORDER BY timestamp DESC LIMIT 1
            ''', (p['offer_id'],))
            row = cursor.fetchone()
        if row and row[0]:
            import json
            prices = json.loads(row[0])
            for i, url in enumerate(urls):
                price = prices[i] if i < len(prices) else None
                comp_data.append({
                    "SKU": p['offer_id'],
                    "Название": p['product_name'],
                    "Конкурент": f"Конкурент {i+1}",
                    "Ссылка": url,
                    "Цена": f"{price:.2f}" if price else "—"
                })
    if comp_data:
        comp_df = pd.DataFrame(comp_data)
        st.dataframe(comp_df, use_container_width=True, hide_index=True)
    else:
        st.info("Нет данных о конкурентах")

with tab3:
    st.header("История изменений цен")
    with db._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT offer_id, timestamp, target_price, margin 
            FROM price_history 
            ORDER BY timestamp DESC 
            LIMIT 50
        ''')
        history = cursor.fetchall()
    if history:
        hist_df = pd.DataFrame(history, columns=["SKU", "Время (UTC)", "Цена", "Маржа, %"])
        st.dataframe(hist_df, use_container_width=True, hide_index=True)
    else:
        st.info("История пуста")