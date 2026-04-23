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
    st.subheader("Работа с Excel")
    uploaded_file = st.file_uploader("Загрузить новый файл", type=["xlsx"], label_visibility="visible")
    if uploaded_file is not None:
        with open(DATA_FILE, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success(f"Файл загружен: {DATA_FILE.name}")
        if st.button("Запустить с новым файлом"):
            run_repricer_thread()
            st.rerun()

    with open(DATA_FILE, "rb") as f:
        st.download_button("📥 Скачать текущий Excel", f, file_name=DATA_FILE.name)

    st.divider()
    st.caption(f"Файл данных: {DATA_FILE}")
    st.caption(f"База данных: {DATABASE_PATH}")

# --- Основные вкладки ---
tab1, tab2, tab3, tab4 = st.tabs(["📦 Товары", "🏷️ Конкуренты", "📈 История", "📊 Графики"])

with tab1:
    st.header("Товары")
    products = db.get_all_products()
    if not products:
        st.warning("Нет данных о товарах.")
    else:
        # Фильтры
        col1, col2, col3 = st.columns(3)
        with col1:
            sku_filter = st.text_input("🔍 SKU")
        with col2:
            name_filter = st.text_input("🔍 Название")
        with col3:
            strategy_filter = st.selectbox(
                "Тип стратегии",
                ["Все", "Ниже", "Выше", "Равная", "Смешанная"]
            )

        col4, col5, col6 = st.columns(3)
        with col4:
            ric_op = st.selectbox("РИЦ", ["Не важно", ">=", "<=", "="])
            ric_val = st.number_input("Значение РИЦ", value=0.0, step=100.0, format="%.2f", key="ric")
        with col5:
            margin_op = st.selectbox("Маржа", ["Не важно", ">=", "<=", "="])
            margin_val = st.number_input("Значение маржи", value=0.0, step=1.0, format="%.2f", key="margin")
        with col6:
            price_op = st.selectbox("Текущая цена", ["Не важно", ">=", "<=", "="])
            price_val = st.number_input("Значение цены", value=0.0, step=100.0, format="%.2f", key="price")

        rows = []
        for p in products:
            # Текстовые фильтры
            if sku_filter and sku_filter.lower() not in str(p['offer_id']).lower():
                continue
            if name_filter and name_filter.lower() not in (p['product_name'] or '').lower():
                continue

            hist = db.get_price_history(p['offer_id'])
            last_price = hist[-1]['target_price'] if hist else None
            last_margin = hist[-1]['margin'] if hist else None
            avg_week = db.get_average_margin(p['offer_id'], 7)
            avg_month = db.get_average_margin(p['offer_id'], 30)

            strategies = db.get_strategies(p['offer_id'])
            strat_types = set(s['strategy_type'] for s in strategies)
            if len(strat_types) > 1:
                strat_label = "Смешанная"
            elif 1 in strat_types:
                strat_label = "Ниже"
            elif 2 in strat_types:
                strat_label = "Выше"
            else:
                strat_label = "Равная"

            if strategy_filter != "Все" and strategy_filter != strat_label:
                continue

            # Фильтр по РИЦ
            if ric_op != "Не важно" and p['min_price'] is not None:
                if ric_op == ">=" and p['min_price'] < ric_val:
                    continue
                if ric_op == "<=" and p['min_price'] > ric_val:
                    continue
                if ric_op == "=" and abs(p['min_price'] - ric_val) > 1e-6:
                    continue

            # Фильтр по марже
            if margin_op != "Не важно" and last_margin is not None:
                if margin_op == ">=" and last_margin < margin_val:
                    continue
                if margin_op == "<=" and last_margin > margin_val:
                    continue
                if margin_op == "=" and abs(last_margin - margin_val) > 1e-6:
                    continue

            # Фильтр по текущей цене
            if price_op != "Не важно" and last_price is not None:
                if price_op == ">=" and last_price < price_val:
                    continue
                if price_op == "<=" and last_price > price_val:
                    continue
                if price_op == "=" and abs(last_price - price_val) > 1e-6:
                    continue

            strategy_text = "; ".join([
                f"{s['start_time']}-{s['end_time']}: {['','Ниже','Выше','Равная'][s['strategy_type']]}"
                + (f" {s['percent']}%" if s['strategy_type'] != 3 else "")
                for s in strategies
            ]) if strategies else "Равная"

            comps = db.get_competitors_for_product(p['offer_id'])
            comp_prices = []
            for c in comps:
                price_hist = db.get_competitor_price_history(c['id'])
                if price_hist:
                    comp_prices.append(f"{price_hist[-1]['price']:.0f}")
                else:
                    comp_prices.append("—")
            comp_prices_str = ", ".join(comp_prices) if comp_prices else "—"

            rows.append({
                "SKU": p['offer_id'],
                "Название": p['product_name'],
                "Себестоимость": p['cost_price'],
                "Мин. цена (РИЦ)": p['min_price'],
                "Прошлая цена": p['current_price'],
                "Текущая цена": f"{last_price:.2f}" if last_price else "—",
                "Маржа, %": f"{last_margin:.2f}" if last_margin else "—",
                "Ср. неделя, %": f"{avg_week:.2f}" if avg_week else "—",
                "Ср. месяц, %": f"{avg_month:.2f}" if avg_month else "—",
                "Стратегии": strategy_text,
                "Цены конкурентов": comp_prices_str
            })

        if rows:
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Нет товаров, соответствующих фильтрам.")

with tab2:
    st.header("Конкуренты")
    competitors = db.get_all_competitors_with_details()
    if not competitors:
        st.info("Нет данных о конкурентах")
    else:
        rows = []
        for c in competitors:
            price_hist = db.get_competitor_price_history(c['id'])
            last_price = price_hist[-1]['price'] if price_hist else None
            rows.append({
                "ID": c['id'],
                "Магазин": c['shop_name'] or "—",
                "Товар конкурента": c['product_name'] or "—",
                "Ссылка": c['url'],
                "Последняя цена": f"{last_price:.2f}" if last_price else "—",
                "Связанные SKU": c['offer_ids'] or "—"
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

with tab3:
    st.header("История изменений")
    with db._get_connection() as conn:
        hist_df = pd.read_sql_query('''
            SELECT offer_id as "SKU", 
                   timestamp as "Время", 
                   target_price as "Цена", 
                   margin as "Маржа, %"
            FROM price_history
            ORDER BY timestamp DESC
            LIMIT 100
        ''', conn)
    if not hist_df.empty:
        st.dataframe(hist_df, use_container_width=True, hide_index=True)
    else:
        st.info("История пуста")

with tab4:
    st.header("Графики")
    products = db.get_all_products()
    if products:
        sku_options = [f"{p['offer_id']} – {p['product_name']}" for p in products]
        sku_to_label = {opt: p['offer_id'] for opt, p in zip(sku_options, products)}

        # График 1: Динамика цены и маржи
        st.subheader("Динамика цены и маржинальности")
        selected = st.multiselect(
            "Выберите товары",
            sku_options,
            default=sku_options[:2] if len(sku_options)>=2 else sku_options,
            key="multi_price"
        )
        if selected:
            fig_price = go.Figure()
            fig_margin = go.Figure()
            for label in selected:
                sku = sku_to_label[label]
                hist = db.get_price_history(sku)
                if hist:
                    df = pd.DataFrame(hist)
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    fig_price.add_trace(go.Scatter(x=df['timestamp'], y=df['target_price'], mode='lines+markers', name=label))
                    fig_margin.add_trace(go.Scatter(x=df['timestamp'], y=df['margin'], mode='lines+markers', name=label))
            if fig_price.data:
                fig_price.update_layout(legend=dict(orientation="h", y=-0.2))
                fig_margin.update_layout(legend=dict(orientation="h", y=-0.2))
                col_left, col_right = st.columns(2)
                with col_left:
                    st.write("**Цена**")
                    st.plotly_chart(fig_price, use_container_width=True)
                with col_right:
                    st.write("**Маржа, %**")
                    st.plotly_chart(fig_margin, use_container_width=True)

        st.divider()
        st.subheader("Сравнение с конкурентами")
        selected_sku_comp = st.selectbox("Выберите товар", sku_options, key="comp_select")
        if selected_sku_comp:
            sku = sku_to_label[selected_sku_comp]
            # Получаем историю цены товара
            price_hist = db.get_price_history(sku)
            if price_hist:
                df_price = pd.DataFrame(price_hist)
                df_price['timestamp'] = pd.to_datetime(df_price['timestamp'])

                fig_comp = go.Figure()
                fig_comp.add_trace(go.Scatter(
                    x=df_price['timestamp'], y=df_price['target_price'],
                    mode='lines+markers', name='Наша цена'
                ))

                # Получаем конкурентов
                comps = db.get_competitors_for_product(sku)
                for c in comps:
                    comp_price_hist = db.get_competitor_price_history(c['id'])
                    if comp_price_hist:
                        df_comp = pd.DataFrame(comp_price_hist)
                        df_comp['timestamp'] = pd.to_datetime(df_comp['timestamp'])
                        shop = c['shop_name'] or f"Конкурент {c['competitor_index']}"
                        fig_comp.add_trace(go.Scatter(
                            x=df_comp['timestamp'], y=df_comp['price'],
                            mode='lines+markers', name=shop
                        ))

                fig_comp.update_layout(legend=dict(orientation="h", y=-0.2))
                st.plotly_chart(fig_comp, use_container_width=True)
            else:
                st.info("Нет данных о цене товара")