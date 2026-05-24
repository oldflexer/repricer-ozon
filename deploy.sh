#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "=== Ветка server ==="
git checkout server
git reset --hard HEAD
git pull origin server

# --- Автоматическое создание venv ---
if [ ! -d ".venv" ]; then
    echo "=== Виртуальное окружение не найдено, создаём... ==="
    python3 -m venv .venv
fi

echo "=== Активация venv и установка зависимостей ==="
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# --- Создание/обновление systemd сервиса из шаблона ---
SERVICE_TEMPLATE="deploy/repricer-web.service"
SERVICE_FILE="/etc/systemd/system/repricer-web.service"
CURRENT_USER=$(whoami)
WORKING_DIR=$(pwd)

if [ -f "$SERVICE_TEMPLATE" ]; then
    echo "=== Установка systemd сервиса из $SERVICE_TEMPLATE ==="
    sed -e "s|{{USER}}|$CURRENT_USER|g" \
        -e "s|{{WORKING_DIR}}|$WORKING_DIR|g" \
        "$SERVICE_TEMPLATE" | sudo tee "$SERVICE_FILE" > /dev/null
    sudo systemctl daemon-reload
    sudo systemctl enable repricer-web
    sudo systemctl restart repricer-web
    echo "✅ Сервис обновлён и перезапущен"
else
    echo "⚠️ Файл $SERVICE_TEMPLATE не найден, пропускаем установку сервиса"
fi

# --- Установка/обновление cron из шаблона ---
CRON_TEMPLATE="deploy/cron.example"
CRON_TMP="/tmp/repricer_cron_$$"

if [ -f "$CRON_TEMPLATE" ]; then
    echo "=== Установка cron задач из $CRON_TEMPLATE ==="
    # Заменяем плейсхолдер и добавляем новую строку в конце
    sed -e "s|{{WORKING_DIR}}|$WORKING_DIR|g" "$CRON_TEMPLATE" > "$CRON_TMP"
    echo "" >> "$CRON_TMP"   # добавляем пустую строку в конце
    # Удаляем старые строки, содержащие "# Repricer cron jobs"
    crontab -l 2>/dev/null | grep -v "# Repricer cron jobs" > "$CRON_TMP.old" || true
    cat "$CRON_TMP" >> "$CRON_TMP.old"
    crontab "$CRON_TMP.old"
    rm -f "$CRON_TMP" "$CRON_TMP.old"
    echo "✅ Cron задачи обновлены"
else
    echo "⚠️ Файл $CRON_TEMPLATE не найден, пропускаем установку cron"
fi

echo "=== Установка прав на выполнение ==="
chmod +x deploy.sh

echo "=== Готово! ==="