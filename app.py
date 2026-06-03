import asyncio
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import base64
from pathlib import Path
import sys
from typing import Dict, Any, List

from core.mappers import to_view_model

sys.path.insert(0, str(Path(__file__).parent))

from config.settings import settings, TIMEZONE
from infrastructure.db import SQLiteRepository
from infrastructure.excel_loader import ExcelLoader
from infrastructure.ozon_api import OzonApiClient
from infrastructure.mail_notifier import MailNotifier
from core.use_cases import RepricingUseCase
from core.entities import ProductInfo


def get_base64_encoded_image(image_path: Path) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


st.set_page_config(page_title="Репрайсер Ozon", layout="wide", page_icon="static/favicon.ico")

# Кастомизация кнопки загрузки файла (без скрытия крестика)
st.markdown("""
<style>
    div[data-testid="stFileUploader"] button {
        width: 100% !important;
        min-width: 100% !important;
        justify-content: center !important;
        position: relative;
        display: flex !important;
        align-items: center !important;
        padding: 0 !important;
    }
    div[data-testid="stFileUploader"] button > div {
        display: none !important;
    }
    div[data-testid="stFileUploader"] button::before {
        content: "📤 Загрузить файл Excel";
        display: block;
        font-size: 1rem;
        padding: 0.5rem 1rem;
        width: 100%;
        text-align: center;
        pointer-events: none;
    }
    div[data-testid="stFileUploader"]:has(div[data-testid="stFileChip"]) button {
        display: none !important;
    }
</style>
""", unsafe_allow_html=True)

icon_path = Path(__file__).parent / "static" / "favicon.ico"

st.markdown(
    f"""
    <div style="display: flex; align-items: center; margin-bottom: 1rem;">
        <img src="data:image/png;base64,{get_base64_encoded_image(icon_path)}" width="40" style="margin-right: 12px;">
        <h1 style="display: inline; margin: 0;">Репрайсер Ozon</h1>
    </div>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------------------
# Аутентификация
# --------------------------------------------------------------
def check_auth():
    """Проверяет и управляет аутентификацией пользователя."""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("🔐 Авторизация")
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            username = st.text_input("Логин")
            password = st.text_input("Пароль", type="password")
            if st.button("Войти", use_container_width=True):
                if username == settings.WEB_USER and password == settings.WEB_PASS:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Неверный логин или пароль")
        st.stop()  # Не показываем остальной интерфейс, пока не авторизованы

# Вызов проверки
check_auth()

# --------------------------------------------------------------
# Инициализация репозитория и состояния (только после успешного входа)
# --------------------------------------------------------------
repo = SQLiteRepository(settings.DATABASE_PATH)

if 'running' not in st.session_state:
    st.session_state.running = False
if 'result_message' not in st.session_state:
    st.session_state.result_message = None
if 'result_type' not in st.session_state:  # 'success', 'error'
    st.session_state.result_type = None
if 'dry_run_mode' not in st.session_state:
    st.session_state.dry_run_mode = False

def run_repricing(dry_run: bool = False) -> Dict[str, Any]:
    async def _run():
        loader = ExcelLoader(settings.DATA_FILE)
        api = OzonApiClient()
        notifier = MailNotifier()
        use_case = RepricingUseCase(repo, api, notifier, loader)
        try:
            stats = await use_case.execute(dry_run=dry_run)
        finally:
            await api.close()
        return stats
    return asyncio.run(_run())

def execute_repricing(dry_run: bool):
    """Запускает репрайсинг и возвращает результат или ошибку."""
    try:
        stats = run_repricing(dry_run=dry_run)
        if dry_run:
            msg = f"✅ Dry run завершён. Обработано товаров: {stats.get('products_loaded', 0)}, рассчитано цен: {stats.get('prices_updated', 0)}"
        else:
            updated = stats.get('prices_updated', 0)
            errors = stats.get('errors', [])
            msg = f"✅ Готово! Обновлено цен: {updated}"
            if errors:
                msg += f"\n⚠️ Ошибки: {', '.join(errors)}"
        return msg, 'success'
    except Exception as e:
        return f"❌ Ошибка: {e}", 'error'
    
# --------------------------------------------------------------
# KPI дашборд
# --------------------------------------------------------------
kpi = repo.get_kpi_metrics()
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    delta_margin = kpi['avg_margin_today'] - kpi['avg_margin_yesterday']
    st.metric(
        "Средняя маржинальность (сегодня)", 
        f"{kpi['avg_margin_today']:.1f}%",
        delta=f"{delta_margin:+.1f}%" if delta_margin != 0 else None
    )
with col2:
    st.metric("Обновлений за неделю", kpi['updates_last_week'])
with col3:
    st.metric("Убыточные товары", kpi['unprofitable_count'], delta=None)
with col4:
    st.metric("Без индекса Ozon", kpi['no_index_count'])
with col5:
    total_products = len(repo.get_all_products())
    st.metric("Всего товаров", total_products)
st.divider()

# --------------------------------------------------------------
# Боковая панель
# --------------------------------------------------------------
with st.sidebar:
    st.header("Управление")
    
    # --- Кнопка выхода ---
    if st.button("🚪 Выйти", width="stretch"):
        st.session_state.authenticated = False
        st.session_state.running = False
        st.session_state.result_message = None
        st.session_state.result_type = None
        st.rerun()
    
    # --- Показываем сообщение о результате предыдущего запуска ---
    if st.session_state.result_message:
        if st.session_state.result_type == 'success':
            st.success(st.session_state.result_message)
        else:
            st.error(st.session_state.result_message)
        st.session_state.result_message = None
        st.session_state.result_type = None

    if st.session_state.running:
        with st.spinner("Выполняется репрайсинг. Пожалуйста, подождите..."):
            msg, msg_type = execute_repricing(st.session_state.dry_run_mode)
            st.session_state.result_message = msg
            st.session_state.result_type = msg_type
            st.session_state.running = False
        st.rerun()
    
    # --- Блокировка всех элементов, если репрайсинг выполняется ---
    if st.session_state.running:
        st.warning("⏳ Репрайсинг выполняется. Пожалуйста, подождите...")
        st.button("🚀 Полный цикл (отправка цен)", type="primary", width="stretch", disabled=True)
        st.button("📝 Dry run (без отправки)", width="stretch", disabled=True)
        
        st.divider()
        
        last_run_utc = repo.get_last_run_time()
        if last_run_utc:
            last_run_msk = last_run_utc.astimezone(TIMEZONE)
            st.metric("Последний запуск (МСК)", last_run_msk.strftime("%Y-%m-%d %H:%M"))
        else:
            st.metric("Последний запуск", "—")
        
        st.divider()
        st.subheader("Работа с Excel")
        st.info("⛔ Загрузка Excel недоступна во время выполнения репрайсинга")
        if settings.DATA_FILE.exists():
            with open(settings.DATA_FILE, "rb") as f:
                st.download_button(
                    "📥 Скачать текущий Excel",
                    f,
                    file_name=settings.DATA_FILE.name,
                    width="stretch",
                    disabled=True
                )
        else:
            st.warning("Файл Excel пока не существует.")
        
        st.divider()
        st.subheader("Обслуживание БД")
        st.button("🧹 Удалить записи старше 1 месяца", width="stretch", disabled=True)
        
        st.divider()
        st.caption(f"Файл данных: {settings.DATA_FILE.resolve()}")
        st.caption(f"База данных: {settings.DATABASE_PATH.resolve()}")
    
    else:
        # --- Обычный режим (все элементы активны) ---
        if st.button("🚀 Полный цикл (отправка цен)", type="primary", width="stretch"):
            st.session_state.running = True
            st.session_state.dry_run_mode = False
            st.rerun()
        
        if st.button("📝 Dry run (без отправки)", width="stretch"):
            st.session_state.running = True
            st.session_state.dry_run_mode = True
            st.rerun()
        
        st.divider()
        
        last_run_utc = repo.get_last_run_time()
        if last_run_utc:
            last_run_msk = last_run_utc.astimezone(TIMEZONE)
            st.metric("Последний запуск (МСК)", last_run_msk.strftime("%Y-%m-%d %H:%M"))
        else:
            st.metric("Последний запуск", "—")
        
        st.divider()
        st.subheader("Работа с Excel")
        
        uploaded_file = st.file_uploader("", type=["xlsx"], label_visibility="collapsed", width="stretch")
        if uploaded_file is not None:
            with open(settings.DATA_FILE, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.success(f"✅ Файл загружен: {settings.DATA_FILE.name}")
        
        if settings.DATA_FILE.exists():
            with open(settings.DATA_FILE, "rb") as f:
                st.download_button(
                    "📥 Скачать текущий Excel",
                    f,
                    file_name=settings.DATA_FILE.name,
                    width="stretch"
                )
        else:
            st.warning("Файл Excel пока не существует.")
        
        st.divider()
        st.subheader("Обслуживание БД")
        if st.button("🧹 Удалить записи старше 1 месяца", width="stretch"):
            deleted = repo.delete_old_records(days=30)
            st.success(f"Удалено записей: {deleted}")
        
        st.divider()
        st.caption(f"Файл данных: {settings.DATA_FILE.resolve()}")
        st.caption(f"База данных: {settings.DATABASE_PATH.resolve()}")

        last_cleanup = repo.get_last_cleanup_date()
        if last_cleanup:
            last_cleanup_msk = last_cleanup.astimezone(TIMEZONE)
            st.caption(f"🗑️ Последняя очистка БД: {last_cleanup_msk.strftime('%Y-%m-%d %H:%M')}")

# --------------------------------------------------------------
# Основные вкладки (весь остальной код без изменений)
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

            # Берём цену покупателя: сначала из product.real_customer_price, иначе из истории
            if p.real_customer_price is not None:
                last_price = p.real_customer_price
            else:
                hist = repo.get_price_history(p.sku)
                last_price = hist[-1].get('customer_price') if hist else None

            last_margin = None
            hist = repo.get_price_history(p.sku)
            if hist:
                last_margin = hist[-1].get('marginality')
            avg_week = repo.get_average_marginality(p.sku, 7)
            avg_month = repo.get_average_marginality(p.sku, 30)

            view = to_view_model(p, last_price, last_margin, avg_week, avg_month)

            link = f'https://www.ozon.ru/product/{p.sku}/'

            rows.append({
                "SKU": view.sku,
                "Название": view.name,
                "Себестоимость": view.cost_price,
                "Мин. цена (РИЦ)": view.min_price,
                "Текущая цена": f"{view.current_price:.0f}" if view.current_price else "—",
                "Маржинальность, %": f"{view.marginality_percent:.2f}" if view.marginality_percent else "—",
                "Ср. неделя, %": f"{view.avg_week_margin:.2f}" if view.avg_week_margin else "—",
                "Ср. месяц, %": f"{view.avg_month_margin:.2f}" if view.avg_month_margin else "—",
                "Ссылка": link,
            })

        if rows:
            df = pd.DataFrame(rows)
            st.dataframe(
                df, 
                column_config={
                    "Ссылка": st.column_config.LinkColumn("Ссылка", display_text="🔗 Открыть"),
                },
                width="stretch", 
                hide_index=True)
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
        st.dataframe(hist_df, width="stretch", hide_index=True)
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
            key="multi_price",
            width="stretch"
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
            bins = [-float('inf'), 0, 10, 20, 30, float('inf')]
            labels = ['<0%', '0-10%', '10-20%', '20-30%', '>30%']
            margins_cat = pd.cut(margins, bins=bins, labels=labels, right=False)
            cat_counts = margins_cat.value_counts().reset_index()
            cat_counts.columns = ['Маржинальность', 'Количество товаров']
            fig_pie = px.pie(cat_counts, values='Количество товаров', names='Маржинальность',
                             title='Распределение маржинальности (%)', hole=0.4)
            st.plotly_chart(fig_pie, width="stretch")

        st.subheader("Распределение по типам стратегий")
        strat_df = pd.DataFrame([{"Тип": k, "Количество": v} for k, v in strategy_counts.items()])
        fig_strat_pie = px.pie(strat_df, values='Количество', names='Тип',
                               title='Распределение по типам стратегий', hole=0.4)
        st.plotly_chart(fig_strat_pie, width="stretch")

        # --- Дополнительная аналитика ---
        st.divider()
        st.subheader("Эффективность стратегий")
        with repo._get_connection() as conn:
            strategy_perf = pd.read_sql_query('''
                SELECT 
                    s.strategy_name,
                    AVG(ph.marginality) as avg_margin,
                    COUNT(*) as updates_count
                FROM product_price_history ph
                JOIN product_strategy ps ON ph.product_id = ps.product_id
                JOIN strategy s ON ps.strategy_id = s.id
                WHERE ph.timestamp >= datetime('now', '-30 days')
                GROUP BY s.id
            ''', conn)
        if not strategy_perf.empty:
            strategy_perf['avg_margin'] = strategy_perf['avg_margin'] * 100
            strategy_perf.rename(columns={'strategy_name': 'Стратегия', 'avg_margin': 'Средняя маржинальность (%)', 'updates_count': 'Количество обновлений (30 дней)'}, inplace=True)
            st.dataframe(strategy_perf, width="stretch", hide_index=True)

        st.subheader("Динамика среднего отклонения от индекса Ozon")
        with repo._get_connection() as conn:
            daily_deviation = pd.read_sql_query('''
                SELECT 
                    DATE(ph.timestamp) as day,
                    AVG( (ph.result_target_price * ph.discount_coef) / NULLIF(ph.ozon_index_data_price, 0) ) as avg_ratio
                FROM product_price_history ph
                WHERE ph.ozon_index_data_price > 0
                AND ph.timestamp >= datetime('now', '-30 days')
                GROUP BY day
                ORDER BY day
            ''', conn)
        if not daily_deviation.empty:
            daily_deviation['day'] = pd.to_datetime(daily_deviation['day'])
            fig_dev = px.line(daily_deviation, x='day', y='avg_ratio',
                              title='Среднее отношение нашей цены к индексу Ozon (за 30 дней)',
                              labels={'day': 'Дата', 'avg_ratio': 'Отношение (наша цена / индекс)'})
            st.plotly_chart(fig_dev, width="stretch")
        else:
            st.info("Нет данных с индексом Ozon для построения динамики.")

        st.subheader("Товары с неизменной ценой более 7 дней")
        with repo._get_connection() as conn:
            stale_products = pd.read_sql_query('''
                SELECT 
                    p.sku,
                    p.product_name,
                    MAX(ph.timestamp) as last_update,
                    JULIANDAY('now') - JULIANDAY(MAX(ph.timestamp)) as days_stale
                FROM product_price_history ph
                JOIN product p ON p.product_id = ph.product_id
                GROUP BY p.sku
                HAVING days_stale > 7
                ORDER BY days_stale DESC
            ''', conn)
        if not stale_products.empty:
            stale_products['last_update'] = pd.to_datetime(stale_products['last_update']).dt.tz_localize('UTC').dt.tz_convert(TIMEZONE)
            stale_products['days_stale'] = stale_products['days_stale'].round(1)
            stale_products.rename(columns={'sku': 'SKU', 'product_name': 'Название', 'last_update': 'Последнее обновление', 'days_stale': 'Дней без изменений'}, inplace=True)
            st.dataframe(stale_products, width="stretch", hide_index=True)
        else:
            st.success("Нет товаров с неизменной ценой более 7 дней.")

        st.subheader("Тепловая карта времени обновлений")
        with repo._get_connection() as conn:
            heatmap_data = pd.read_sql_query('''
                SELECT 
                    strftime('%w', timestamp) as weekday,
                    strftime('%H', timestamp) as hour,
                    COUNT(*) as updates
                FROM product_price_history
                WHERE timestamp >= datetime('now', '-90 days')
                GROUP BY weekday, hour
            ''', conn)

        if not heatmap_data.empty:
            # Маппинг дня недели: 0 = воскресенье, 1 = понедельник, ... 6 = суббота
            weekday_map = {0: 'Вс', 1: 'Пн', 2: 'Вт', 3: 'Ср', 4: 'Чт', 5: 'Пт', 6: 'Сб'}
            heatmap_data['weekday_label'] = heatmap_data['weekday'].astype(int).map(weekday_map)
            
            # Создаём сводную таблицу
            pivot = heatmap_data.pivot(index='hour', columns='weekday_label', values='updates').fillna(0)
            
            # Задаём правильный порядок дней недели
            correct_order = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
            # reindex по столбцам, заполняя отсутствующие дни нулями
            pivot = pivot.reindex(columns=correct_order, fill_value=0)
            
            fig_heatmap = px.imshow(pivot,
                                    labels=dict(x="День недели", y="Час (МСК)", color="Количество обновлений"),
                                    title="Тепловая карта обновлений цен (последние 90 дня)",
                                    aspect="auto",
                                    color_continuous_scale="Viridis")
            st.plotly_chart(fig_heatmap, width="stretch")
        else:
            st.info("Недостаточно данных для тепловой карты.")
        
        # --- Эффективность стратегий (ROI) ---
        st.divider()
        st.subheader("Эффективность стратегий (ROI)")
        strategy_roi = repo.get_strategy_roi()
        if not strategy_roi.empty:
            strategy_roi.rename(columns={
                'strategy_name': 'Стратегия',
                'avg_abs_profit': 'Средняя прибыль (₽)',
                'avg_marginality': 'Средняя маржинальность (%)',
                'updates_count': 'Кол-во обновлений'
            }, inplace=True)
            strategy_roi['Средняя маржинальность (%)'] = strategy_roi['Средняя маржинальность (%)'] * 100
            strategy_roi['Средняя прибыль (₽)'] = strategy_roi['Средняя прибыль (₽)'].round(0)
            st.dataframe(strategy_roi, width="stretch", hide_index=True)
            
            # Столбчатая диаграмма
            fig_roi = px.bar(strategy_roi, x='Стратегия', y='Средняя прибыль (₽)',
                            title='Средняя абсолютная прибыль по стратегиям (за 30 дней)')
            st.plotly_chart(fig_roi, width="stretch")
        else:
            st.info("Недостаточно данных для анализа эффективности стратегий.")

        # --- Динамика за последнюю неделю (уже есть) ---
        st.divider()
        st.subheader("Динамика за последнюю неделю")
        with repo._get_connection() as conn:
            daily_df = pd.read_sql_query('''
                SELECT 
                    DATE(ph.timestamp) as day,
                    AVG(ph.result_target_price * ph.discount_coef) as avg_price,
                    AVG(ph.marginality) as avg_margin
                FROM product_price_history ph
                WHERE ph.timestamp >= datetime('now', '-7 days')
                GROUP BY day
                ORDER BY day
            ''', conn)
        if not daily_df.empty:
            daily_df['day'] = pd.to_datetime(daily_df['day'])
            daily_df['avg_margin'] = daily_df['avg_margin'] * 100
            fig_price_trend = px.line(daily_df, x='day', y='avg_price', title='Средняя цена (реальная) за неделю')
            st.plotly_chart(fig_price_trend, width="stretch")
            fig_margin_trend = px.line(daily_df, x='day', y='avg_margin', title='Средняя маржинальность за неделю')
            st.plotly_chart(fig_margin_trend, width="stretch")

        # --- Лучшие и худшие по маржинальности (уже есть) ---
        st.subheader("Лучшие и худшие по маржинальности")
        with repo._get_connection() as conn:
            top_df = pd.read_sql_query('''
                SELECT 
                    p.sku,
                    p.product_name,
                    ph.marginality
                FROM product_price_history ph
                JOIN product p ON p.product_id = ph.product_id
                WHERE ph.timestamp = (SELECT MAX(timestamp) FROM product_price_history WHERE product_id = ph.product_id)
                ORDER BY ph.marginality DESC
            ''', conn)
        if not top_df.empty:
            top_df['marginality_pct'] = top_df['marginality'] * 100
            top5 = top_df.head(5)[['sku', 'product_name', 'marginality_pct']]
            bottom5 = top_df.tail(5)[['sku', 'product_name', 'marginality_pct']]
            col_top, col_bottom = st.columns(2)
            with col_top:
                st.write("**Топ-5 по маржинальности**")
                st.dataframe(top5, hide_index=True, width="stretch")
            with col_bottom:
                st.write("**Худшие 5 по маржинальности**")
                st.dataframe(bottom5, hide_index=True, width="stretch")

        # --- Последние изменения (уже есть) ---
        st.subheader("Последние 10 изменений цен")
        with repo._get_connection() as conn:
            recent_df = pd.read_sql_query('''
                SELECT 
                    p.sku,
                    p.product_name,
                    ph.timestamp,
                    ROUND(ph.result_target_price * ph.discount_coef, 0) as price,
                    ROUND(ph.marginality * 100, 2) as margin_pct
                FROM product_price_history ph
                JOIN product p ON p.product_id = ph.product_id
                ORDER BY ph.timestamp DESC
                LIMIT 10
            ''', conn)
        if not recent_df.empty:
            recent_df['timestamp'] = pd.to_datetime(recent_df['timestamp']).dt.tz_localize('UTC').dt.tz_convert(TIMEZONE)
            st.dataframe(recent_df, width="stretch", hide_index=True)

        # --- Экспорт (уже есть) ---
        st.divider()
        if st.button("📥 Экспорт истории цен в CSV", width="stretch"):
            with repo._get_connection() as conn:
                export_df = pd.read_sql_query('''
                    SELECT 
                        p.sku,
                        p.product_name,
                        ph.timestamp,
                        ROUND(ph.result_target_price * ph.discount_coef, 0) as price,
                        ROUND(ph.marginality * 100, 2) as margin_pct
                    FROM product_price_history ph
                    JOIN product p ON p.product_id = ph.product_id
                    ORDER BY ph.timestamp DESC
                ''', conn)
            csv = export_df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button("Скачать CSV", csv, "price_history.csv", "text/csv", width="stretch")

        st.caption("Статистика основана на последней записи в истории цен каждого товара.")

# --------------------------------------------------------------
# Вкладка "Анализ и комиссии"
# --------------------------------------------------------------
with tab5:
    st.header("Анализ комиссий FBS и индексов")
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
                ph.ozon_index_data_index,
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
        st.dataframe(analysis_df[['sku', 'product_name'] + cols].round(2), width="stretch")
        
        st.subheader("Сравнение с индексами")
        # Товары, у которых ozon_index_data_price не 0
        with_index = analysis_df[analysis_df['ozon_index_data_price'] > 0]
        if not with_index.empty:
            st.write("Товары, имеющие индекс Ozon:")
            st.dataframe(with_index[['sku', 'product_name', 'ozon_index_data_price', 'real_price']].round(0), width="stretch")
        else:
            st.info("Нет товаров с индексом Ozon.")
        
        st.subheader("Корреляция маржинальности и индекса Ozon")
        fig_corr = px.scatter(analysis_df, x='ozon_index_data_index', y='marginality', 
                              title="Зависимость маржинальности от индекса Ozon",
                              labels={'ozon_index_data_index': 'Индекс Ozon (коэффициент)', 'marginality': 'Маржинальность'})
        st.plotly_chart(fig_corr, width="stretch")

        st.subheader("Зависимость цены от индекса Ozon")
        ozon_price_df = repo.get_ozon_index_vs_price()
        if not ozon_price_df.empty:
            fig_scatter = px.scatter(
                ozon_price_df,
                x='ozon_index_data_price',
                y='real_price',
                color='marginality',
                hover_data=['sku', 'product_name'],
                title='Цена покупателя vs Индекс Ozon (цвет – маржинальность)',
                labels={
                    'ozon_index_data_price': 'Индекс Ozon (₽)',
                    'real_price': 'Реальная цена покупателя (₽)',
                    'marginality': 'Маржинальность'
                },
                color_continuous_scale='RdYlGn',
                range_color=[-0.2, 0.4]
            )
            # Добавляем линию y=x для справки
            max_val = max(ozon_price_df['ozon_index_data_price'].max(), ozon_price_df['real_price'].max())
            fig_scatter.add_trace(go.Scatter(
                x=[0, max_val],
                y=[0, max_val],
                mode='lines',
                name='y=x',
                line=dict(dash='dash', color='gray')
            ))
            st.plotly_chart(fig_scatter, width="stretch")
            
            # Статистика: сколько товаров с ценой выше/ниже индекса
            above = (ozon_price_df['real_price'] > ozon_price_df['ozon_index_data_price']).sum()
            below = (ozon_price_df['real_price'] < ozon_price_df['ozon_index_data_price']).sum()
            equal = (ozon_price_df['real_price'] == ozon_price_df['ozon_index_data_price']).sum()
            st.markdown(f"**Товаров с ценой выше индекса:** {above} &nbsp;&nbsp;|&nbsp;&nbsp; **Ниже индекса:** {below} &nbsp;&nbsp;|&nbsp;&nbsp; **Равна индексу:** {equal}")
        else:
            st.info("Нет товаров с индексом Ozon для анализа зависимости.")