import streamlit as st
import pandas as pd
import asyncio
import sys
from pathlib import Path
import plotly.graph_objects as go
from typing import Dict, Any

# Корень проекта для импортов
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import DATA_FILE, DATABASE_PATH, TIMEZONE
from src.database import Database
from src.competitors_parser import CompetitorsParser
from src.products_parser import ProductsParser
from src.pricemaker import PriceMaker
from src.price_updater import PriceUpdater
from src.loader import DataLoader

st.set_page_config(page_title="Репрайсер Ozon", layout="wide", page_icon="📊")
st.title("🔄 Репрайсер Ozon")

# --- CSS для скрытия стандартных надписей file_uploader и изменения надписи ---
st.markdown("""
<style>
    .stFileUploader > small { display: none !important; }
    .stFileUploader button span { display: none !important; }
    .stFileUploader button::after {
        content: "📤 Загрузить новый файл" !important;
        display: inline-block !important;
    }
</style>
""", unsafe_allow_html=True)

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
loader = DataLoader(DATA_FILE)

# --- Универсальный запуск асинхронного кода с нужной политикой ---
def _run_async_with_proactor(async_func) -> Any:
    """Выполняет асинхронную функцию с принудительным ProactorEventLoop."""
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(async_func())
    finally:
        loop.close()

# --- Функции для кнопок ---
def run_full_cycle() -> Dict[str, Any]:
    products = loader.load()
    if not products:
        return {"products_loaded": 0, "prices_updated": 0, "errors": ["Нет товаров"]}
    for p in products:
        db.upsert_product(p)
        db.set_strategies(p['sku'], p['intervals'])

    async def fetch_real():
        prod_parser = ProductsParser()
        return await prod_parser.fetch_real_prices(products)
    real_prices = _run_async_with_proactor(fetch_real)

    async def parse_competitors():
        comp_parser = CompetitorsParser(db)
        return await comp_parser.run(products)
    comp_stats = _run_async_with_proactor(parse_competitors)

    pricemaker = PriceMaker(db)
    updates_for_ozon, margin_items = pricemaker.calculate(products, real_prices)

    updater = PriceUpdater(db, loader, dry_run=False)
    price_stats = updater.update(updates_for_ozon, margin_items)

    return {
        "products_loaded": len(products),
        "prices_updated": price_stats.get('prices_updated', 0),
        "errors": price_stats.get('errors', []),
        "competitor_prices_parsed": comp_stats.get('competitor_prices_parsed', 0)
    }

def run_competitors_parser() -> Dict[str, Any]:
    async def _run():
        products = loader.load()
        for p in products:
            db.upsert_product(p)
            db.set_strategies(p['sku'], p['intervals'])
        comp_parser = CompetitorsParser(db)
        return await comp_parser.run(products)
    return _run_async_with_proactor(_run)

def run_products_parser() -> Dict[str, Any]:
    async def _run():
        products = loader.load()
        prod_parser = ProductsParser()
        real_prices = await prod_parser.fetch_real_prices(products)
        return {"status": "ok", "real_prices": real_prices}
    return _run_async_with_proactor(_run)

def run_pricemaker() -> Dict[str, Any]:
    products = loader.load()
    for p in products:
        db.upsert_product(p)
        db.set_strategies(p['sku'], p['intervals'])
    real_prices = {p['sku']: p.get('current_price') for p in products}
    pricemaker = PriceMaker(db)
    updates_for_ozon, margin_items = pricemaker.calculate(products, real_prices)
    updater = PriceUpdater(db, loader, dry_run=False)
    return updater.update(updates_for_ozon, margin_items)

# --- Боковая панель ---
with st.sidebar:
    st.header("Управление")
    
    if st.button("🚀 Полный цикл", type="primary", use_container_width=True):
        with st.spinner("Выполняется полный цикл..."):
            try:
                result = run_full_cycle()
                updated = result.get('prices_updated', 0)
                errors = result.get('errors', [])
                st.success(f"✅ Готово! Обновлено цен: {updated}")
                if errors:
                    st.warning(f"⚠️ Ошибки: {', '.join(errors)}")
            except Exception as e:
                st.error(f"❌ Ошибка: {e}")
    
    if st.button("🕷️ Спарсить конкурентов", use_container_width=True):
        with st.spinner("Парсинг конкурентов..."):
            try:
                result = run_competitors_parser()
                parsed = result.get('competitor_prices_parsed', 0)
                st.success(f"✅ Спарсено цен: {parsed}")
            except Exception as e:
                st.error(f"❌ Ошибка: {e}")
    
    if st.button("📦 Спарсить свои", use_container_width=True):
        with st.spinner("Парсинг своих товаров..."):
            try:
                run_products_parser()
                st.success("✅ Выполнено")
            except Exception as e:
                st.error(f"❌ Ошибка: {e}")
    
    if st.button("💰 Пересчитать и отправить цены", use_container_width=True):
        with st.spinner("Пересчёт цен..."):
            try:
                result = run_pricemaker()
                updated = result.get('prices_updated', 0)
                errors = result.get('errors', [])
                st.success(f"✅ Готово! Обновлено цен: {updated}")
                if errors:
                    st.warning(f"⚠️ Ошибки: {', '.join(errors)}")
            except Exception as e:
                st.error(f"❌ Ошибка: {e}")
    
    st.divider()
    last_run_utc = db.get_last_run_time()
    if last_run_utc:
        last_run_msk = last_run_utc.astimezone(TIMEZONE)
        st.metric("Последний запуск (МСК)", last_run_msk.strftime("%Y-%m-%d %H:%M"))
    else:
        st.metric("Последний запуск", "—")
    
    st.divider()
    st.subheader("Работа с Excel")
    uploaded_file = st.file_uploader("", type=["xlsx"], label_visibility="collapsed")
    if uploaded_file is not None:
        with open(DATA_FILE, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success(f"Файл загружен: {DATA_FILE.name}")
        if st.button("Запустить с новым файлом", use_container_width=True):
            with st.spinner("Полный цикл с новым файлом..."):
                try:
                    result = run_full_cycle()
                    updated = result.get('prices_updated', 0)
                    st.success(f"✅ Готово! Обновлено цен: {updated}")
                except Exception as e:
                    st.error(f"❌ Ошибка: {e}")
    with open(DATA_FILE, "rb") as f:
        st.download_button("📥 Скачать текущий Excel", f, file_name=DATA_FILE.name, use_container_width=True)
    
    st.divider()
    st.subheader("Обслуживание БД")
    if st.button("🧹 Удалить записи старше 1 недели", use_container_width=True):
        deleted = db.delete_old_records(days=7)
        st.success(f"Удалено записей: {deleted}")
    
    st.divider()
    st.caption(f"Файл данных: {DATA_FILE}")
    st.caption(f"База данных: {DATABASE_PATH}")

# --- Вкладки ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📦 Товары", "🏷️ Конкуренты", "📈 История", "📊 Графики", "📊 Статистика"
])

with tab1:
    st.header("Товары")
    products = db.get_all_products()
    if not products:
        st.warning("Нет данных о товарах.")
    else:
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
            margin_op = st.selectbox("Маржинальность", ["Не важно", ">=", "<=", "="])
            margin_val = st.number_input("Значение маржинальности", value=0.0, step=1.0, format="%.2f", key="margin")
        with col6:
            price_op = st.selectbox("Текущая цена", ["Не важно", ">=", "<=", "="])
            price_val = st.number_input("Значение цены", value=0.0, step=100.0, format="%.2f", key="price")

        rows = []
        for p in products:
            # Приводим фильтры к строковому SKU (в базе хранится как 'offer_id')
            sku_str = str(p['offer_id'])
            if sku_filter and sku_filter.lower() not in sku_str.lower():
                continue
            if name_filter and name_filter.lower() not in (p['product_name'] or '').lower():
                continue

            hist = db.get_price_history(sku_str)
            last_price = None
            last_margin = None
            if hist:
                last_entry = hist[-1]
                last_price = last_entry.get('target_price')
                last_margin = last_entry.get('margin')
            avg_week = db.get_average_margin(sku_str, 7)
            avg_month = db.get_average_margin(sku_str, 30)

            strategies = db.get_strategies(sku_str)
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

            if ric_op != "Не важно" and p['min_price'] is not None:
                if ric_op == ">=" and p['min_price'] < ric_val:
                    continue
                if ric_op == "<=" and p['min_price'] > ric_val:
                    continue
                if ric_op == "=" and abs(p['min_price'] - ric_val) > 1e-6:
                    continue

            if margin_op != "Не важно" and last_margin is not None:
                if margin_op == ">=" and last_margin < margin_val:
                    continue
                if margin_op == "<=" and last_margin > margin_val:
                    continue
                if margin_op == "=" and abs(last_margin - margin_val) > 1e-6:
                    continue

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

            comps = db.get_competitors_for_product(sku_str)
            comp_prices = []
            for c in comps:
                price_hist = db.get_competitor_price_history(c['id'])
                if price_hist:
                    comp_prices.append(f"{price_hist[-1]['price']:.0f}")
                else:
                    comp_prices.append("—")
            comp_prices_str = ", ".join(comp_prices) if comp_prices else "—"

            rows.append({
                "SKU": sku_str,
                "Название": p['product_name'],
                "Себестоимость": p['cost_price'],
                "Мин. цена (РИЦ)": p['min_price'],
                "Прошлая цена": p['current_price'],
                "Текущая цена": f"{last_price:.2f}" if last_price else "—",
                "Маржинальность, %": f"{last_margin:.2f}" if last_margin else "—",
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
                   timestamp, 
                   target_price as "Цена", 
                   margin as "Маржинальность, %"
            FROM price_history
            ORDER BY timestamp DESC
            LIMIT 100
        ''', conn)
    if not hist_df.empty:
        hist_df['timestamp'] = pd.to_datetime(hist_df['timestamp'])
        hist_df['timestamp'] = hist_df['timestamp'].dt.tz_localize('UTC').dt.tz_convert(TIMEZONE)
        hist_df.rename(columns={'timestamp': 'Время (МСК)'}, inplace=True)
        st.dataframe(hist_df, use_container_width=True, hide_index=True)
    else:
        st.info("История пуста")

with tab4:
    st.header("Графики")
    products = db.get_all_products()
    if products:
        sku_options = [f"{p['offer_id']} – {p['product_name']}" for p in products]
        sku_to_label = {opt: p['offer_id'] for opt, p in zip(sku_options, products)}

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
                    df['timestamp'] = df['timestamp'].dt.tz_localize('UTC').dt.tz_convert(TIMEZONE)
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
                    st.write("**Маржинальность, %**")
                    st.plotly_chart(fig_margin, use_container_width=True)

        st.divider()
        st.subheader("Сравнение с конкурентами")
        selected_sku_comp = st.selectbox("Выберите товар", sku_options, key="comp_select")
        if selected_sku_comp:
            sku = sku_to_label[selected_sku_comp]
            price_hist = db.get_price_history(sku)
            if price_hist:
                df_price = pd.DataFrame(price_hist)
                df_price['timestamp'] = pd.to_datetime(df_price['timestamp'])
                df_price['timestamp'] = df_price['timestamp'].dt.tz_localize('UTC').dt.tz_convert(TIMEZONE)

                fig_comp = go.Figure()
                fig_comp.add_trace(go.Scatter(
                    x=df_price['timestamp'], y=df_price['target_price'],
                    mode='lines+markers', name='Наша цена'
                ))

                comps = db.get_competitors_for_product(sku)
                for c in comps:
                    comp_price_hist = db.get_competitor_price_history(c['id'])
                    if comp_price_hist:
                        df_comp = pd.DataFrame(comp_price_hist)
                        df_comp['timestamp'] = pd.to_datetime(df_comp['timestamp'])
                        df_comp['timestamp'] = df_comp['timestamp'].dt.tz_localize('UTC').dt.tz_convert(TIMEZONE)
                        shop = c['shop_name'] or f"Конкурент {c['competitor_index']}"
                        fig_comp.add_trace(go.Scatter(
                            x=df_comp['timestamp'], y=df_comp['price'],
                            mode='lines+markers', name=shop
                        ))

                fig_comp.update_layout(legend=dict(orientation="h", y=-0.2))
                st.plotly_chart(fig_comp, use_container_width=True)
            else:
                st.info("Нет данных о цене товара")
    else:
        st.info("Нет товаров в базе")

with tab5:
    st.header("Сводная статистика")
    products = db.get_all_products()
    competitors = db.get_all_competitors_with_details()

    if not products:
        st.warning("Нет данных для статистики.")
    else:
        total_products = len(products)
        prices = []
        margins = []
        for p in products:
            hist = db.get_price_history(p['offer_id'])
            if hist:
                last_entry = hist[-1]
                if 'target_price' in last_entry and 'margin' in last_entry:
                    prices.append(last_entry['target_price'])
                    margins.append(last_entry['margin'])
        avg_price = sum(prices)/len(prices) if prices else 0
        avg_margin = sum(margins)/len(margins) if margins else 0

        strategy_counts = {"Ниже": 0, "Выше": 0, "Равная": 0, "Смешанная": 0}
        for p in products:
            strategies = db.get_strategies(p['offer_id'])
            strat_types = set(s['strategy_type'] for s in strategies)
            if len(strat_types) > 1:
                strategy_counts["Смешанная"] += 1
            elif 1 in strat_types:
                strategy_counts["Ниже"] += 1
            elif 2 in strat_types:
                strategy_counts["Выше"] += 1
            else:
                strategy_counts["Равная"] += 1

        total_competitors = len(competitors)
        total_links = 0
        for p in products:
            total_links += len(db.get_competitors_for_product(p['offer_id']))
        avg_competitors = total_links / total_products if total_products else 0

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Всего товаров", total_products)
        col2.metric("Средняя цена", f"{avg_price:.2f} ₽")
        col3.metric("Средняя маржинальность", f"{avg_margin:.2f}%")
        col4.metric("Всего конкурентов", total_competitors)

        st.divider()
        st.subheader("Распределение по типам стратегий")
        strat_df = pd.DataFrame([{"Тип": k, "Количество": v} for k, v in strategy_counts.items()])
        st.bar_chart(strat_df.set_index("Тип"))

        st.divider()
        col5, col6 = st.columns(2)
        with col5:
            st.metric("Среднее число конкурентов на товар", f"{avg_competitors:.1f}")
        with col6:
            products_with_comp = sum(1 for p in products if db.get_competitors_for_product(p['offer_id']))
            st.metric("Товаров с конкурентами", f"{products_with_comp} / {total_products}")

        st.caption("Статистика основана на последнем завершённом цикле репрайсера.")