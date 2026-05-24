import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path
import sys
import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import DATA_FILE, DATABASE_PATH, TIMEZONE
from infrastructure.db import SQLiteRepository
from infrastructure.loader import DataLoader
from infrastructure.ozon_api import OzonApiClient
from infrastructure.mail_notifier import MailNotifier
from core.services import PriceCalculationService
from core.use_cases import RepricingUseCase
from core.entities import ProductInfo, StrategyInterval

# Настройка логирования
log_file = Path(__file__).parent / 'repricer.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, mode='w', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

st.set_page_config(page_title="Репрайсер Ozon", layout="wide", page_icon="📊")

st.markdown("""
<style>
    /* Растягиваем кнопку на всю ширину */
    div[data-testid="stFileUploader"] button {
        width: 100% !important;
        min-width: 100% !important;
        justify-content: center !important;
        position: relative;
        display: flex !important;
        align-items: center !important;
        padding: 0 !important;   /* убираем внутренние отступы */
    }
    /* Скрываем весь внутренний контейнер (иконка + текст Upload) */
    div[data-testid="stFileUploader"] button > div {
        display: none !important;
    }
    /* Добавляем наш текст через псевдоэлемент */
    div[data-testid="stFileUploader"] button::before {
        content: "📤 Загрузить файл Excel";
        display: block;
        font-size: 1rem;
        padding: 0.5rem 1rem;
        width: 100%;
        text-align: center;
        pointer-events: none;
    }
</style>
""", unsafe_allow_html=True)

st.title("🔄 Репрайсер Ozon")

# Инициализация репозитория для отображения данных
repo = SQLiteRepository(DATABASE_PATH)

def run_repricing(dry_run: bool = False) -> Dict[str, Any]:
    """Запуск полного цикла репрайсинга через Ozon API."""
    loader = DataLoader(DATA_FILE)
    api = OzonApiClient()
    notifier = MailNotifier()
    calc = PriceCalculationService()
    use_case = RepricingUseCase(repo, api, notifier, calc, loader)
    return use_case.execute(dry_run=dry_run)

# --------------------------------------------------------------
# Боковая панель
# --------------------------------------------------------------
with st.sidebar:
    st.header("Управление")
    
    if st.button("🚀 Полный цикл (отправка цен)", type="primary", use_container_width=True):
        with st.spinner("Выполняется загрузка, расчёт и отправка цен..."):
            try:
                stats = run_repricing(dry_run=False)
                updated = stats.get('prices_updated', 0)
                errors = stats.get('errors', [])
                st.success(f"✅ Готово! Обновлено цен: {updated}")
                if errors:
                    st.warning(f"⚠️ Ошибки: {', '.join(errors)}")
            except Exception as e:
                st.error(f"❌ Ошибка: {e}")
    
    if st.button("📝 Dry run (без отправки)", use_container_width=True):
        with st.spinner("Выполняется расчёт (цены не отправляются)..."):
            try:
                stats = run_repricing(dry_run=True)
                processed = stats.get('products_loaded', 0)
                calculated = stats.get('prices_updated', 0)
                st.success(f"✅ Обработано товаров: {processed}, рассчитано цен: {calculated}")
            except Exception as e:
                st.error(f"❌ Ошибка: {e}")
    
    st.divider()
    
    last_run_utc = repo.get_last_run_time()
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
        st.success(f"✅ Файл загружен: {DATA_FILE.name}")
    
    # Кнопка скачивания текущего Excel
    if DATA_FILE.exists():
        with open(DATA_FILE, "rb") as f:
            st.download_button(
                "📥 Скачать текущий Excel",
                f,
                file_name=DATA_FILE.name,
                use_container_width=True
            )
    else:
        st.warning("Файл Excel пока не существует.")
    
    st.divider()
    st.subheader("Обслуживание БД")
    if st.button("🧹 Удалить записи старше 1 недели", use_container_width=True):
        deleted = repo.delete_old_records(days=7)
        st.success(f"Удалено записей: {deleted}")
    
    st.divider()
    st.caption(f"Файл данных: {DATA_FILE}")
    st.caption(f"База данных: {DATABASE_PATH}")

# --------------------------------------------------------------
# Основные вкладки
# --------------------------------------------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📦 Товары", "📈 История", "📊 Графики", "📊 Статистика", "🔎 Анализ и комиссии"
])

# --------------------------------------------------------------
# Вкладка "Товары"
# --------------------------------------------------------------
with tab1:
    st.header("Товары")
    products: List[ProductInfo] = repo.get_all_products()
    if not products:
        st.warning("Нет данных о товарах. Запустите хотя бы один цикл репрайсера.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            sku_filter = st.text_input("🔍 SKU")
        with col2:
            name_filter = st.text_input("🔍 Название")

        rows = []
        for p in products:
            if sku_filter and sku_filter.lower() not in str(p.sku).lower():
                continue
            if name_filter and name_filter.lower() not in (p.product_name or '').lower():
                continue

            hist = repo.get_price_history(p.sku)
            last_price = None
            last_margin = None
            if hist:
                last_entry = hist[-1]
                last_price = last_entry.get('customer_price')
                last_margin = last_entry.get('marginality')
            avg_week = repo.get_average_marginality(p.sku, 7)
            avg_month = repo.get_average_marginality(p.sku, 30)

            rows.append({
                "SKU": p.sku,
                "Название": p.product_name,
                "Себестоимость": p.cost_price,
                "Мин. цена (РИЦ)": p.min_price,
                "Текущая цена": f"{last_price:.0f}" if last_price else "—",
                "Маржинальность, %": f"{last_margin*100:.2f}" if last_margin else "—",
                "Ср. неделя, %": f"{avg_week*100:.2f}" if avg_week else "—",
                "Ср. месяц, %": f"{avg_month*100:.2f}" if avg_month else "—",
            })

        if rows:
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Нет товаров, соответствующих фильтрам.")

# --------------------------------------------------------------
# Вкладка "История"
# --------------------------------------------------------------
with tab2:
    st.header("История изменений")
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
        st.dataframe(hist_df, use_container_width=True, hide_index=True)
    else:
        st.info("История пуста. Запустите репрайсер для накопления данных.")

# --------------------------------------------------------------
# Вкладка "Графики"
# --------------------------------------------------------------
with tab3:
    st.header("Графики")
    products = repo.get_all_products()
    if not products:
        st.info("Нет товаров в базе")
    else:
        sku_options = [f"{p.sku} – {p.product_name}" for p in products]
        sku_to_sku = {opt: p.sku for opt, p in zip(sku_options, products)}

        st.subheader("Динамика цены и маржинальности")
        selected = st.multiselect(
            "Выберите товары",
            sku_options,
            default=sku_options[:2] if len(sku_options) >= 2 else sku_options,
            key="multi_price"
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
                col_left, col_right = st.columns(2)
                st.subheader("Динамика цены")
                st.plotly_chart(fig_price, use_container_width=True)

                st.subheader("Динамика маржинальности")
                st.plotly_chart(fig_margin, use_container_width=True)

# --------------------------------------------------------------
# Вкладка "Статистика" (расширенная)
# --------------------------------------------------------------
with tab4:
    st.header("Сводная статистика")
    products = repo.get_all_products()
    if not products:
        st.warning("Нет данных для статистики.")
    else:
        total_products = len(products)
        prices = []
        margins = []
        for p in products:
            hist = repo.get_price_history(p.sku)
            if hist:
                last_entry = hist[-1]
                customer_price = last_entry.get('customer_price')
                if customer_price is not None:
                    prices.append(customer_price)
                if 'marginality' in last_entry:
                    margins.append(last_entry['marginality'] * 100)
        avg_price = sum(prices) / len(prices) if prices else 0
        med_price = pd.Series(prices).median() if prices else 0
        avg_margin = sum(margins) / len(margins) if margins else 0
        med_margin = pd.Series(margins).median() if margins else 0
        min_margin = min(margins) if margins else 0
        max_margin = max(margins) if margins else 0
        low_margin_count = sum(1 for m in margins if m < 10) if margins else 0

        # Подсчёт стратегий
        strategy_counts = {"Ниже": 0, "Выше": 0, "Равная": 0, "Смешанная": 0}
        for p in products:
            strategies = repo.get_strategies(p.sku)
            strat_types = {s.strategy_type for s in strategies}
            if len(strat_types) > 1:
                strategy_counts["Смешанная"] += 1
            elif 1 in strat_types:
                strategy_counts["Ниже"] += 1
            elif 2 in strat_types:
                strategy_counts["Выше"] += 1
            else:
                strategy_counts["Равная"] += 1

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
        if margins:
            fig_hist = px.histogram(x=margins, nbins=20, title="Гистограмма маржинальности (%)",
                                    labels={'x': 'Маржинальность %', 'y': 'Количество товаров'})
            st.plotly_chart(fig_hist, use_container_width=True)

        st.subheader("Распределение по типам стратегий")
        strat_df = pd.DataFrame([{"Тип": k, "Количество": v} for k, v in strategy_counts.items()])
        st.bar_chart(strat_df.set_index("Тип"))

        st.caption("Статистика основана на последней записи в истории цен каждого товара.")

# --------------------------------------------------------------
# Новая вкладка "Анализ и комиссии"
# --------------------------------------------------------------
with tab5:
    st.header("Анализ комиссий FBS и индексов")
    # Получаем последние записи по каждому товару с комиссиями
    with repo._get_connection() as conn:
        analysis_df = pd.read_sql_query('''
            SELECT 
                p.sku,
                p.product_name,
                ph.result_target_price,
                ph.discount_coef,
                ph.sales_percent_fbs,
                ph.fbs_first_mile_min_amount,
                ph.fbs_first_mile_max_amount,
                ph.fbs_direct_flow_trans_min_amount,
                ph.fbs_direct_flow_trans_max_amount,
                ph.fbs_deliv_to_customer_amount,
                ph.external_index_data_price,
                ph.ozon_index_data_price,
                ph.self_marketplaces_index_data_price,
                (ph.result_target_price * ph.discount_coef) as real_price,
                ph.marginality
            FROM product_price_history ph
            JOIN product p ON p.product_id = ph.product_id
            WHERE ph.timestamp = (
                SELECT MAX(timestamp) FROM product_price_history WHERE product_id = ph.product_id
            )
            ORDER BY p.sku
        ''', conn)
    
    if analysis_df.empty:
        st.info("Нет данных для анализа. Запустите репрайсер.")
    else:
        # Расчёт средних комиссий
        analysis_df['fbs_first_mile_avg'] = (analysis_df['fbs_first_mile_min_amount'] + analysis_df['fbs_first_mile_max_amount']) / 2
        analysis_df['fbs_direct_flow_avg'] = (analysis_df['fbs_direct_flow_trans_min_amount'] + analysis_df['fbs_direct_flow_trans_max_amount']) / 2
        analysis_df['sales_commission'] = analysis_df['result_target_price'] * (analysis_df['sales_percent_fbs'] / 100)
        analysis_df['total_extra_costs'] = analysis_df['sales_commission'] + analysis_df['fbs_first_mile_avg'] + analysis_df['fbs_direct_flow_avg'] + analysis_df['fbs_deliv_to_customer_amount']
        
        st.subheader("Сводка по комиссиям")
        cols = ['sales_percent_fbs', 'fbs_first_mile_avg', 'fbs_direct_flow_avg', 'fbs_deliv_to_customer_amount', 'total_extra_costs']
        st.dataframe(analysis_df[['sku', 'product_name'] + cols].round(2), use_container_width=True)
        
        st.subheader("Сравнение с индексами")
        # Товары, у которых ozon_index_data_price не 0
        with_index = analysis_df[analysis_df['ozon_index_data_price'] > 0]
        if not with_index.empty:
            st.write("Товары, имеющие индекс Ozon:")
            st.dataframe(with_index[['sku', 'product_name', 'ozon_index_data_price', 'real_price']].round(0), use_container_width=True)
        else:
            st.info("Нет товаров с индексом Ozon.")
        
        st.subheader("Корреляция маржинальности и индексов")
        fig_corr = px.scatter(analysis_df, x='ozon_index_data_price', y='marginality', 
                              title="Зависимость маржинальности от индекса Ozon",
                              labels={'ozon_index_data_price': 'Индекс Ozon (цена)', 'marginality': 'Маржинальность'})
        st.plotly_chart(fig_corr, use_container_width=True)

# --------------------------------------------------------------
# Дополнительно: возможность просмотра логов (опционально)
# --------------------------------------------------------------
# Можно добавить ещё одну вкладку, но не перегружаем интерфейс