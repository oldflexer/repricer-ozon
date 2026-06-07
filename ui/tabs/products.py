import streamlit as st
import pandas as pd
from core.mappers import to_view_model
from ui.cache import get_repo, get_cached_products


def render_products_tab():
    st.header("Товары")
    repo = get_repo()
    products = get_cached_products()
    if not products:
        st.warning("Нет данных о товарах. Запустите хотя бы один цикл репрайсера.")
        return

    col1, col2 = st.columns(2)
    with col1:
        sku_filter = st.text_input("🔍 SKU")
    with col2:
        name_filter = st.text_input("🔍 Название")

    # Получаем все необходимые данные одним запросом (если метод реализован)
    # Для обратной совместимости используем старый способ, но с оптимизацией (кеш)
    # В идеале использовать repo.get_products_dashboard_data()
    rows = []
    for p in products:
        if sku_filter and sku_filter.lower() not in str(p.sku).lower():
            continue
        if name_filter and name_filter.lower() not in (p.product_name or '').lower():
            continue

        # Получаем последнюю цену
        if p.real_customer_price is not None:
            last_price = p.real_customer_price
        else:
            hist = repo.get_price_history(p.sku)
            last_price = hist[-1].get('customer_price') if hist else None

        # Последняя маржинальность
        hist = repo.get_price_history(p.sku)
        last_margin = hist[-1].get('marginality') if hist else None

        # Средние маржинальности за неделю/месяц
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
            column_config={"Ссылка": st.column_config.LinkColumn("Ссылка", display_text="🔗 Открыть")},
            width="stretch", hide_index=True
        )
    else:
        st.info("Нет товаров, соответствующих фильтрам.")