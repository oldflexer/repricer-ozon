#!/bin/bash
set -e

# --- Проверка версии Python ---
if ! python3 -c "import sys; assert sys.version_info >= (3, 10)" 2>/dev/null; then
    echo "❌ Ошибка: требуется Python 3.10 или выше."
    echo "Текущая версия: $(python3 --version 2>&1)"
    exit 1
fi
echo "✅ Версия Python подходит: $(python3 --version)"

cd "$(dirname "$0")"

# --- Безопасная загрузка .env ---
if [ -f .env ]; then
    set -a
    # shellcheck source=/dev/null
    . ./.env
    set +a
fi

# --- Значения по умолчанию ---
INSTANCE_NAME="${INSTANCE_NAME:-$(basename "$(pwd)")}"
PORT="${PORT:-8501}"
CRON_SCHEDULE="${CRON_SCHEDULE:-0 * * * *}"
PARSER_CRON_SCHEDULE="${PARSER_CRON_SCHEDULE:-30 2,10,18 * * *}"

SERVICE_NAME="repricer-${INSTANCE_NAME}.service"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}"
CURRENT_USER=$(whoami)
WORKING_DIR=$(pwd)

echo "=== Развёртывание экземпляра: $INSTANCE_NAME (порт $PORT) ==="

# --- Создание папки логов ---
mkdir -p "$WORKING_DIR/logs"
chmod 755 "$WORKING_DIR/logs"

# --- Обновление кода (опционально) ---
if git rev-parse --git-dir > /dev/null 2>&1; then
    echo "=== Обновление кода из git ==="
    git checkout server
    git reset --hard HEAD
    git pull origin server
else
    echo "⚠️ Не git-репозиторий, обновление кода пропущено"
fi

# --- Виртуальное окружение ---
if [ ! -d ".venv" ]; then
    echo "=== Создание виртуального окружения ==="
    python3 -m venv .venv
fi

# --- Установка зависимостей ---
echo "=== Установка зависимостей ==="
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# --- Применение миграций БД ---
echo "=== Применение миграций БД ==="
if [ -f "scripts/upgrade_db.py" ]; then
    .venv/bin/python scripts/upgrade_db.py
else
    echo "⚠️ Скрипт scripts/upgrade_db.py не найден, миграции пропущены"
fi

# --- Установка Google Chrome ---
if ! command -v google-chrome &> /dev/null; then
    echo "=== Установка Google Chrome из официального репозитория ==="
    wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
    sudo sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'
    sudo apt-get update
    sudo apt-get install -y google-chrome-stable
else
    echo "✅ Google Chrome уже установлен"
fi

# --- Cron для основного репрайсера ---
if [ -f "deploy/cron.template" ]; then
    echo "=== Установка cron задач для репрайсера (${INSTANCE_NAME}) ==="
    CRON_TMP="/tmp/repricer_cron_${INSTANCE_NAME}_$$"
    
    sed -e "s|{{WORKING_DIR}}|$WORKING_DIR|g" \
        -e "s|{{CRON_SCHEDULE}}|$CRON_SCHEDULE|g" \
        -e "s|{{INSTANCE_NAME}}|$INSTANCE_NAME|g" \
        "deploy/cron.template" > "$CRON_TMP"
    
    # Удаляем старые блоки для этого INSTANCE_NAME
    crontab -l 2>/dev/null | sed -e "/# BEGIN_REPRICER_${INSTANCE_NAME}/,/# END_REPRICER_${INSTANCE_NAME}/d" > "$CRON_TMP.old" || true
    cat "$CRON_TMP" >> "$CRON_TMP.old"
    echo "" >> "$CRON_TMP.old"
    crontab "$CRON_TMP.old"
    rm -f "$CRON_TMP" "$CRON_TMP.old"
    echo "✅ Cron задачи для репрайсера обновлены"
else
    echo "⚠️ Шаблон cron не найден, пропускаем"
fi

# --- Cron для парсера конкурентов ---
if [ -f "deploy/parser.cron.template" ]; then
    echo "=== Установка cron задач для парсера конкурентов (${INSTANCE_NAME}) ==="
    PARSER_CRON_TMP="/tmp/parser_cron_${INSTANCE_NAME}_$$"
    
    sed -e "s|{{WORKING_DIR}}|$WORKING_DIR|g" \
        -e "s|{{PARSER_CRON_SCHEDULE}}|$PARSER_CRON_SCHEDULE|g" \
        -e "s|{{INSTANCE_NAME}}|$INSTANCE_NAME|g" \
        "deploy/parser.cron.template" > "$PARSER_CRON_TMP"
    
    # Удаляем старые блоки для парсера
    crontab -l 2>/dev/null | sed -e "/# BEGIN_PARSER_REPRICER_${INSTANCE_NAME}/,/# END_PARSER_REPRICER_${INSTANCE_NAME}/d" > "$PARSER_CRON_TMP.old" || true
    cat "$PARSER_CRON_TMP" >> "$PARSER_CRON_TMP.old"
    echo "" >> "$PARSER_CRON_TMP.old"
    crontab "$PARSER_CRON_TMP.old"
    rm -f "$PARSER_CRON_TMP" "$PARSER_CRON_TMP.old"
    echo "✅ Cron задачи для парсера обновлены"
else
    echo "⚠️ Шаблон парсера не найден, пропускаем"
fi

# --- Cron для отключения автодобавления в акции---
if [ -f "deploy/disable_auto_add.cron.template" ]; then
    echo "=== Установка cron задач для отключения автодобавления в акции (${INSTANCE_NAME}) ==="
    CRON_TMP="/tmp/disable_auto_add_cron_${INSTANCE_NAME}_$$"
    
    sed -e "s|{{WORKING_DIR}}|$WORKING_DIR|g" \
        -e "s|{{INSTANCE_NAME}}|$INSTANCE_NAME|g" \
        "deploy/disable_auto_add.cron.template" > "$CRON_TMP"
    
    crontab -l 2>/dev/null | sed -e "/# BEGIN_DISABLE_AUTO_ADD_${INSTANCE_NAME}/,/# END_DISABLE_AUTO_ADD_${INSTANCE_NAME}/d" > "$CRON_TMP.old" || true
    cat "$CRON_TMP" >> "$CRON_TMP.old"
    echo "" >> "$CRON_TMP.old"
    crontab "$CRON_TMP.old"
    rm -f "$CRON_TMP" "$CRON_TMP.old"
    echo "✅ Cron задачи для отключения автодобавления в акции обновлены"
else
    echo "⚠️ Шаблон disable_auto_add.cron.template не найден, пропускаем"
fi

# --- systemd сервис ---
echo "=== Установка systemd сервиса ${SERVICE_NAME} ==="
sed -e "s|{{USER}}|$CURRENT_USER|g" \
    -e "s|{{WORKING_DIR}}|$WORKING_DIR|g" \
    -e "s|{{PORT}}|$PORT|g" \
    -e "s|{{INSTANCE_NAME}}|$INSTANCE_NAME|g" \
    "deploy/repricer-web.service.template" | sudo tee "$SERVICE_FILE" > /dev/null

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"

if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
    sudo systemctl restart "$SERVICE_NAME"
else
    sudo systemctl start "$SERVICE_NAME"
fi

echo "=== Проверка статуса сервиса ==="
if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "✅ Сервис $SERVICE_NAME успешно запущен"
else
    echo "❌ Сервис $SERVICE_NAME не запустился!"
    sudo systemctl status "$SERVICE_NAME" --no-pager
fi

echo "=== Установка прав на выполнение ==="
chmod +x deploy.sh

echo "=== Готово! Экземпляр $INSTANCE_NAME развёрнут ==="