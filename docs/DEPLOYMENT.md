# DEPLOYMENT.md — Руководство по развёртыванию

## Требования
- Python 3.11+
- Linux (Ubuntu 20.04+/Debian 11+) или Windows Server
- Доступ к Ozon Seller API (Client ID, API Key)
- SMTP сервер для email-уведомлений
- Google Chrome / Chromium (для парсера конкурентов)

## Установка

### 1. Клонирование и окружение
```bash
git clone <repo>
cd repricer-ozon
python -m venv .venv
source .venv/bin/activate  # Linux
# .venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

### 2. Конфигурация
```
cp .env.example .env
# Отредактируйте .env:
# OZON_CLIENT_ID=xxx
# OZON_API_KEY=xxx
# SMTP_HOST=smtp.yandex.ru
# SMTP_PORT=465
# SMTP_USER=...
# SMTP_PASSWORD=...
# EMAIL_TO=...
# INSTANCE_NAME=main
# WEB_USER=admin
# WEB_PASSWORD=secure_password
# CHROME_PROFILE_PATH=/home/server/chrome_profile  # Linux
# CHROME_PROFILE_PATH=C:\Users\user\AppData\Local\Google\Chrome\User Data\Default  # Windows
```

### 3. Инициализация БД
```
python scripts/upgrade_db.py
```

### 4. Ручной логин в Ozon (для парсера)
```
python scripts/manual_login.py
# Откроется браузер с профилем Chrome, войдите в seller.ozon.ru за 5 минут
```

### 5. Проверка
```
python scripts/health_check.py
python scripts/repricer.py --dry-run
```

## Автоматический деплой (рекомендуется)

### Файлы в `deploy/`:
- `deploy.sh` — скрипт установки (создаёт venv, ставит зависимости, настраивает systemd/cron)
- `deploy/repricer-web.service.template` — systemd сервис для Streamlit дашборда
- `deploy/repricer.cron.template` — cron для репрайсинга
- `deploy/parser.cron.template` — cron для парсера конкурентов
- `deploy/disable_auto_add.cron.template` — cron для отключения автодобавления
- `deploy/update_price_timer.cron.template` — cron для таймера цен
- `deploy/cron.template` — базовый шаблон

### Быстрый деплой:
```bash
# На сервере
git clone <repo>
cd repricer-ozon
cp .env.example .env  # заполните переменные
chmod +x deploy.sh
sudo ./deploy.sh
```

Сервисы будут установлены и запущены автоматически.

## Systemd Service (Linux) — ручная настройка

### Создайте `/etc/systemd/system/repricer-ozon.service`:
```
[Unit]
Description=Ozon Repricer
After=network.target

[Service]
Type=oneshot
User=repricer
WorkingDirectory=/opt/repricer-ozon
EnvironmentFile=/opt/repricer-ozon/.env
ExecStart=/opt/repricer-ozon/.venv/bin/python scripts/repricer.py
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### Streamlit дашборд: `/etc/systemd/system/repricer-web.service`
```
[Unit]
Description=Ozon Repricer Web Dashboard
After=network.target

[Service]
Type=simple
User=repricer
WorkingDirectory=/opt/repricer-ozon
EnvironmentFile=/opt/repricer-ozon/.env
ExecStart=/opt/repricer-ozon/.venv/bin/python -m streamlit run app.py --server.port=8501 --server.address=0.0.0.0
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Таймеры:
```bash
# Репрайсинг каждые 30 минут
systemctl enable --now repricer-ozon.timer

# Дашборд
systemctl enable --now repricer-web.service
```

## Cron Jobs (альтернатива systemd)
```
# Репрайсинг каждые 30 минут
*/30 * * * * /opt/repricer-ozon/.venv/bin/python /opt/repricer-ozon/scripts/repricer.py

# Парсер конкурентов в 03:00
0 3 * * * /opt/repricer-ozon/.venv/bin/python /opt/repricer-ozon/scripts/competitors_parser.py

# Отключение автодобавления в 04:00
0 4 * * * /opt/repricer-ozon/.venv/bin/python /opt/repricer-ozon/scripts/actions_disable_auto_add.py

# Обновление таймера в 05:00
0 5 * * * /opt/repricer-ozon/.venv/bin/python /opt/repricer-ozon/scripts/actions_update_price_timer.py

# Health check каждый час
0 * * * * /opt/repricer-ozon/.venv/bin/python /opt/repricer-ozon/scripts/health_check.py
```

## Бэкапы БД
```
# Ежедневный бэкап (добавить в cron)
0 2 * * * cp /opt/repricer-ozon/data/repricer_main.db /opt/backups/repricer_$(date +\%F).db

# Хранение 30 дней
0 3 * * * find /opt/backups -name "repricer_*.db" -mtime +30 -delete
```

## Логи

- Ротация: TimedRotatingFileHandler, ежедневно, 7 бэкапов
- Пути: logs/repricer-{INSTANCE}.log, logs/parser-{INSTANCE}.log
- journald для systemd сервисов

## Мониторинг

- Health check: `python scripts/health_check.py` (exit code 0 = OK)
- Дашборд: `streamlit run app.py` (порт 8501)
- Метрики в дашборде: KPI, heatmap, последняя статистика, диагностика БД

## Безопасность

- .env с правами 600
- Отдельный пользователь для сервиса (не root)
- Firewall: только исходящие HTTPS (443) к api-seller.ozon.ru
- SMTP через TLS (порт 465/587)
- Chrome Profile — изолированный профиль для парсера
- File Locks — предотвращение параллельного запуска парсера
