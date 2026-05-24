# Репрайсер для Ozon (API‑версия)

Автоматическое управление ценами на Ozon через Ozon Seller API, с расчётом на основе индексов цен и заданных временны́х стратегий, контролем маржинальности по реальным комиссиям FBS.

## 🚀 Возможности

- Работа **только через Ozon Seller API**
- Автоматическое получение `product_id`, `offer_id`, названия товара через `/v3/product/info/list`.
- Получение цен, индексов и комиссий FBS через `/v5/product/info/prices`.
- Расчёт целевой цены с использованием динамического `discount_coef` на основе индексов (external, ozon, self_marketplaces) или коэффициента из `.env`.
- Гибкие временные стратегии: ниже/выше/равна индексу Ozon с настраиваемым процентом.
- Расчёт **маржинальности с учётом всех комиссий Ozon FBS**:
    sales_commission = result_target_price * (sales_percent_fbs/100)
    first_mile_avg = (min + max)/2
    direct_flow_avg = (min + max)/2
    total_cost = sales_commission + first_mile_avg + direct_flow_avg + fbs_deliv_to_customer + net_price
    marginality = (result_target_price - total_cost) / result_target_price
- Отправка цен в Ozon через `/v1/product/import/prices` (с поправкой `min_price = РИЦ / discount_coef`).
- Автоматическое обновление Excel-файла (реальная цена покупателя, маржа) и запись истории в SQLite.
- Email-уведомления о завершении цикла.
- Веб-интерфейс на **Streamlit** для просмотра товаров, графиков, статистики и ручного запуска.
- Поддержка `--dry-run` (расчёт без отправки).
- Готов к развёртыванию на сервере через systemd и cron.

## 🧱 Архитектура

Проект чётко разделён на слои:

    repricer-ozon/
    ├── config/
    │   └── settings.py          # переменные окружения, пути
    ├── core/
    │   ├── entities.py          # dataclasses (ProductInfo, PricingData, StrategyInterval...)
    │   ├── repository.py        # абстрактный репозиторий (IProductRepository)
    │   ├── services.py          # PriceCalculationService (полный алгоритм с индексами и FBS)
    │   └── use_cases.py         # RepricingUseCase (загрузка, расчёт, отправка, сохранение)
    ├── infrastructure/
    │   ├── db.py                # SQLiteRepository (таблицы, история, маржинальность)
    │   ├── loader.py            # загрузка из Excel (SKU, себестоимость, РИЦ, стратегии)
    │   ├── ozon_api.py          # клиент Ozon API (v3, v5, v1) с повторными попытками
    │   └── mail_notifier.py     # отправка email
    ├── app.py                   # Streamlit‑дашборд (только API)
    ├── main.py                  # CLI‑запуск (--dry-run)
    ├── deploy/                  # шаблоны для автоматического деплоя
    │   ├── repricer-web.service   # systemd unit для веб‑интерфейса
    │   └── cron.example            # настройки cron (запуск main.py каждый час)
    ├── data/                    # папка для products.xlsx и repricer.db
    ├── .env.example             # пример переменных окружения
    ├── requirements.txt
    └── README.md

## ⚙️ Входные данные (Excel)

Excel-файл `products.xlsx` должен содержать **только** следующие колонки (остальные игнорируются):

| Колонка            | Описание |
|--------------------|----------|
| `SKU`              | Артикул продавца (offer_id) – обязателен. |
| `Себестоимость`    | Закупочная цена (net_price). |
| `Цена РИЦ`         | Минимальная допустимая цена (ограничение снизу). |
| `Интервал 1`…`4`   | Временной интервал в формате `ЧЧ:ММ-ЧЧ:ММ`. |
| `Стратегия 1`…`4`  | Тип: 1 – ниже индекса, 2 – выше, 3 – равна. |
| `Процент 1`…`4`    | Процент отклонения (только для 1 и 2). |

Все остальные колонки (`Ваша цена`, `Название`, `Маржинальность` и т.д.) будут **записаны автоматически** после расчёта.

## 🔄 Принцип работы (алгоритм)

1. **Загрузка Excel** – читаются SKU, себестоимость, РИЦ и интервалы стратегий.
2. **Получение `product_id`, `offer_id`, названия** через `/v3/product/info/list`.
3. **Получение цен, индексов и комиссий FBS** через `/v5/product/info/prices`.
4. **Расчёт `discount_coef`**:
   - Если доступны индексы – `approx_real_price = средняя_цена * средний_индекс`.
   - `discount_coef = approx_real_price / marketing_seller_price`.
   - Если индексов нет – `discount_coef = COEFFICIENT_OZON` (по умолчанию 0.5).
5. **`target_min_price = РИЦ / discount_coef`**.
6. **Выбор активной стратегии** по текущему времени.
7. **`strategy_price`** – от `ozon_index_data_price` с учётом процента (если `ozon_index_data_price != 0`).
8. **`target_strategy_price = strategy_price / discount_coef`**.
9. **`result_target_price = max(target_strategy_price, target_min_price)`** – округляется до целого.
10. **Реальная цена для покупателя** = `result_target_price * discount_coef` (только для Excel и дашборда).
11. **Маржинальность** с учётом комиссий FBS (формула выше).
12. **Отправка в Ozon** (`/v1/product/import/prices`):
    - `price` = `result_target_price`
    - `min_price` = `РИЦ / discount_coef` (целое)
    - `net_price` = себестоимость
    - `old_price` = старая цена из API
13. **Сохранение**:
    - SQLite: история цен, маржинальности, комиссий.
    - Excel: реальная цена, маржа (текущая, за неделю, за месяц).
14. **Email-уведомление** о количестве обновлённых товаров или ошибках.

## 📊 Веб-интерфейс

- **Товары** – таблица с текущей ценой и маржинальностью, фильтры по SKU и названию.
- **История** – последние 100 изменений цен с реальной ценой покупателя.
- **Графики** – динамика цены и маржинальности по выбранным товарам.
- **Статистика** – средняя цена, средняя маржа, распределение стратегий.
- **Боковая панель** – запуск полного цикла, dry-run, загрузка/скачивание Excel, обслуживание БД.

---

*Дата последнего обновления: 2026‑05‑19*