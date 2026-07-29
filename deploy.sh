#!/bin/bash
set -e

cd "$(dirname "$0")"

# --- Чтение параметров из .env (если есть) ---
if [ -f .env ]; then
    source .env
fi

# --- Значения по умолчанию ---
INSTANCE_NAME="${INSTANCE_NAME:-$(basename "$(pwd)")}"
PORT="${PORT:-8501}"
CRON_SCHEDULE="${CRON_SCHEDULE:-0 * * * *}"          # каждый час
PARSER_CRON_SCHEDULE="${PARSER_CRON_SCHEDULE:-30 2,10,18 * * *}"  # 02:30, 10:30, 18:30

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

echo "=== Установка зависимостей ==="
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# --- Установка Chrome для парсера (если не установлен) ---
if ! command -v google-chrome &> /dev/null && ! command -v chromium-browser &> /dev/null; then
    echo "=== Установка Chrome для парсера ==="
    if [ -f /etc/debian_version ]; then
        # Debian/Ubuntu
        sudo apt-get update
        sudo apt-get install -y chromium-browser
    elif [ -f /etc/redhat-release ]; then
        # RHEL/CentOS/Fedora
        sudo yum install -y chromium
    else
        echo "⚠️ Не удалось определить дистрибутив для установки Chrome. Установите вручную."
    fi
else
    echo "✅ Chrome уже установлен"
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
sudo systemctl restart "$SERVICE_NAME"
echo "✅ Сервис $SERVICE_NAME перезапущен"

echo "=== Установка прав на выполнение ==="
chmod +x deploy.sh

echo "=== Готово! Экземпляр $INSTANCE_NAME развёрнут ==="