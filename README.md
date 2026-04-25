# Репрайсер для Ozon

Автоматическое управление ценами на Ozon с мониторингом конкурентов, гибкими стратегиями и расчётом маржинальности.

## 🚀 Возможности

- Парсинг цен до 5 конкурентов на товар (selenium/nodriver).
- Стратегии: ниже/выше конкурента на X%, равная цена, временные интервалы.
- Расчёт маржинальности (текущая, средняя за неделю/месяц).
- Обновление цен через Ozon Seller API.
- Уведомления по email о завершении цикла.
- Веб-интерфейс (Streamlit) для мониторинга, графиков и ручного запуска.
- История в SQLite + запись в Excel.
- Синглтон браузер — один Chrome переиспользуется всеми парсерами, корректно закрывается при остановке.

## ⚙️ Структура проекта

```
repricer-ozon/
├── config/
│   └── settings.py     # Конфигурация (API-ключи, пути, задержки)
├── src/
│   ├── main.py         # Точка входа (CLI)
│   ├── loader.py       # Загрузка товаров из Excel
│   ├── database.py     # SQLite (товары, стратегии, история)
│   ├── parser.py       # Парсинг цен с Ozon (nodriver)
│   ├── calculator.py   # PriceCalculator + MarginCalculator
│   ├── pricemaker.py   # Расчёт целевых цен
│   ├── price_updater.py# Отправка в Ozon API + сохранение
│   ├── ozon_api.py     # Клиент Ozon Seller API
│   ├── mail_notifier.py# Email-уведомления
│   ├── notifier.py     # Уведомления в MAX
│   ├── products_parser.py   # Парсинг наших товаров
│   └── competitors_parser.py# Парсинг конкурентов
├── web/
│   └── app.py          # Streamlit-дашборд
├── tests/
│   ├── test_calculator.py
│   ├── test_database.py
│   ├── test_loader.py
│   ├── test_parser.py
│   └── test_integration.py
├── data/
│   └── products.xlsx   # Файл с товарами (заполняется вручную)
├── .env                # API-ключи и настройки
├── requirements.txt
├── PLAN.md
└── README.md
```

## ⚙️ Входные данные

Excel-файл `products.xlsx` с колонками:

| Колонка | Описание |
|---------|----------|
| SKU | Артикул товара |
| Название | Наименование |
| Себестоимость | Закупочная цена |
| Цена РИЦ | Минимальная допустимая цена (ограничение снизу) |
| Ваша цена | Текущая цена на Ozon |
| Конкурент 1..5 | Ссылки на товары конкурентов |
| Интервал 1..4 | Время в формате «ЧЧ:ММ-ЧЧ:ММ» |
| Стратегия 1..4 | 1 (ниже), 2 (выше), 3 (равная) |
| Процент 1..4 | X% для стратегий 1 и 2 |

Поддерживается до 4 временных интервалов на товар (расписание).

## 🔄 Принцип работы

1. Загрузка товаров из Excel → синхронизация с БД.
2. Запрос `product_id` и `previous_price` по SKU через Ozon API.
3. Парсинг наших товаров с витрины Ozon (реальная цена).
4. Парсинг цен конкурентов (nodriver, до 5 на товар).
5. Расчёт стратегической цены → деление на коэффициент `real_price / previous_price`.
6. Отправка целевых цен в Ozon API + сохранение в Excel (маржа, маржа за неделю/месяц).
7. Логирование в `repricer.log`, email-уведомление о завершении.

## 🖥️ Запуск

**Веб-интерфейс:**
```bash
streamlit run web/app.py
```

**CLI (полный цикл):**
```bash
python src/main.py
```

**CLI (dry-run, без отправки в Ozon):**
```bash
python src/main.py --dry-run
```

## 🔧 Настройка (.env)

```env
OZON_CLIENT_ID=ваш_client_id
OZON_API_KEY=ваш_api_key

SMTP_HOST=smtp.yandex.ru
SMTP_PORT=587
SMTP_USER=your@yandex.ru
SMTP_PASSWORD=ваш_пароль
SENDER_EMAIL=your@yandex.ru
RECIPIENT_EMAIL=admin@example.com

PARSER_DELAY=1.5
PARSER_TIMEOUT=10
MAX_RETRIES=3
HEADLESS=False

DATA_FILE=data/products.xlsx

WEB_USER=admin
WEB_PASS=admin
```

## 📊 Веб-интерфейс

- Авторизация (WEB_USER / WEB_PASS из .env).
- Таблица товаров с ценами, маржой и статусами.
- Графики изменения цены и маржинальности по товару.
- Кнопки: Полный цикл, Парсинг конкурентов, Парсинг товаров, Расчёт цен.
- Кнопка скачивания Excel-файла.

## 📝 Логирование

Все события пишутся в `repricer.log`. При повторном запуске (Streamlit rerun) дубли не создаются — проверка `if not logging.getLogger().handlers`.

## 🔧 Требования

- Python 3.10+
- Google Chrome (для парсинга)
- Ozon Seller API (Client ID, API Key)
- SMTP (опционально, для email-уведомлений)