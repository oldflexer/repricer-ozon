import streamlit as st
import pandas as pd
import asyncio
import threading
import logging
from pathlib import Path
import sys
import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import DATA_FILE, DATABASE_PATH, TIMEZONE
from src.database import Database
from src.loader import DataLoader
from src.main import Repricer

st.set_page_config(page_title="Репрайсер Ozon", layout="wide")
st.title("🔄 Репрайсер Ozon")

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

with st.sidebar:
    st.header("Управление")
    
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
    
    last_run_utc = db.get_last_run_time()
    if last_run_utc:
        last_run_msk = last_run_utc.astimezone(TIMEZONE)
        st.metric("Последний запуск (МСК)", last_run_msk.strftime("%Y-%m-%d %H:%M"))
    else:
        st.metric("Последний запуск", "—")
    
    st.divider()
    
    uploaded_file = st.file_uploader("📂 Загрузить новый Excel", type=["xlsx"])
    if uploaded_file is not None:
        with open(DATA_FILE, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success(f"Файл загружен: {DATA_FILE.name}")
        if st.button("Запустить с новым файлом"):
            result = run_repricer_thread()
            st.rerun()
    
    st.divider()
    
    with open(DATA_FILE, "rb") as f:
        st.download_button(
            label="📥 Скачать текущий Excel",
            data=f,
            file_name=DATA_FILE.name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    st.divider()
    st.caption(f"Файл данных: {DATA_FILE}")
    st.caption(f"База данных: {DATABASE_PATH}")

tab1, tab2, tab3, tab4 = st.tabs(["📦 Товары", "🏷️ Конкуренты", "📈 История", "📊 Графики"])

with tab1:
    st.header("Текущие товары")
    products = db.get_all_products()
    if not products:
        st.warning("Нет данных о товарах. Запустите репрайсер или загрузите файл.")
    else:
        # KPI
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Всего товаров", len(products))
        margins = []
        for p in products:
            with db._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT margin FROM price_history WHERE offer_id=? ORDER BY timestamp DESC LIMIT 1", (p['offer_id'],))
                row = cur.fetchone()
                if row and row[0] is not None:
                    margins.append(row[0])
        avg_margin = sum(margins)/len(margins) if margins else 0
        with col2:
            st.metric("Средняя маржа", f"{avg_margin:.2f}%")
        no_comp = sum(1 for p in products if not p.get('competitor_urls'))
        with col3:
            st.metric("Без конкурентов", no_comp)
        
        # Фильтры
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            strategies = sorted(list(set(p['strategy'] for p in products)))
            selected_strategies = st.multiselect("Стратегия", strategies, default=strategies)
        with col_f2:
            show_only_with_competitors = st.checkbox("Только товары с конкурентами")
        
        rows = []
        for p in products:
            if selected_strategies and p['strategy'] not in selected_strategies:
                continue
            if show_only_with_competitors and not p.get('competitor_urls'):
                continue
            
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
                "Прошлая цена": p['current_price'],
                "Текущая цена": f"{target_price:.2f}" if target_price else "—",
                "Маржа, %": f"{margin:.2f}" if margin else "—",
                "Ср. за неделю, %": f"{avg_week:.2f}" if avg_week else "—",
                "Ср. за месяц, %": f"{avg_month:.2f}" if avg_month else "—",
                "Мин. цена": p['min_price'],
                "Себестоимость": p['cost_price'],
                "Стратегия": p['strategy'],
                "Процент": p['strategy_percent'],
                "Конкуренты (цены)": competitor_prices,
            })
        
        if rows:
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Скачать таблицу (CSV)", csv, "repricer_export.csv", "text/csv")
        else:
            st.info("Нет товаров, соответствующих фильтрам.")

with tab2:
    st.header("Цены конкурентов")
    comp_data = []
    for p in products:
        urls = p.get('competitor_urls', [])
        if not urls:
            continue
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

with tab4:
    st.header("Динамика цены и маржинальности")
    products = db.get_all_products()
    if products:
        sku_list = [p['offer_id'] for p in products]
        selected_skus = st.multiselect("Выберите SKU", sku_list, default=sku_list[:2] if len(sku_list)>=2 else sku_list)
        if selected_skus:
            fig_price = go.Figure()
            fig_margin = go.Figure()
            for sku in selected_skus:
                with db._get_connection() as conn:
                    df = pd.read_sql_query('''
                        SELECT timestamp, target_price, margin
                        FROM price_history
                        WHERE offer_id = ?
                        ORDER BY timestamp ASC
                    ''', conn, params=(sku,))
                if not df.empty:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    fig_price.add_trace(go.Scatter(x=df['timestamp'], y=df['target_price'], mode='lines+markers', name=f'{sku} цена'))
                    fig_margin.add_trace(go.Scatter(x=df['timestamp'], y=df['margin'], mode='lines+markers', name=f'{sku} маржа'))
            st.subheader("Цена")
            st.plotly_chart(fig_price, use_container_width=True)
            st.subheader("Маржинальность, %")
            st.plotly_chart(fig_margin, use_container_width=True)