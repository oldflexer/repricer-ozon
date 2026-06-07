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
CRON_SCHEDULE="${CRON_SCHEDULE:-0 * * * *}"   # каждый час по умолчанию

echo "=== Развёртывание экземпляра: $INSTANCE_NAME (порт $PORT) ==="

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

# --- systemd сервис (уникальное имя) ---
SERVICE_NAME="repricer-${INSTANCE_NAME}.service"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}"
CURRENT_USER=$(whoami)
WORKING_DIR=$(pwd)

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

# --- Cron с блочными маркерами ---
if [ -f "deploy/cron.template" ]; then
    echo "=== Установка cron задач для ${INSTANCE_NAME} ==="
    CRON_TMP="/tmp/repricer_cron_${INSTANCE_NAME}_$$"
    
    # Генерируем новый блок из шаблона
    sed -e "s|{{WORKING_DIR}}|$WORKING_DIR|g" \
        -e "s|{{CRON_SCHEDULE}}|$CRON_SCHEDULE|g" \
        -e "s|{{INSTANCE_NAME}}|$INSTANCE_NAME|g" \
        "deploy/cron.template" > "$CRON_TMP"
    
    # Удаляем старый блок для этого INSTANCE_NAME (если есть)
    # Используем sed для удаления от BEGIN до END включительно
    crontab -l 2>/dev/null | sed -e "/# BEGIN_REPRICER_${INSTANCE_NAME}/,/# END_REPRICER_${INSTANCE_NAME}/d" > "$CRON_TMP.old" || true
    
    # Добавляем новый блок
    cat "$CRON_TMP" >> "$CRON_TMP.old"
    # Убедимся, что в конце есть перевод строки
    echo "" >> "$CRON_TMP.old"
    
    # Применяем обновлённый crontab
    crontab "$CRON_TMP.old"
    rm -f "$CRON_TMP" "$CRON_TMP.old"
    echo "✅ Cron задачи для ${INSTANCE_NAME} обновлены"
else
    echo "⚠️ Шаблон cron не найден, пропускаем"
fi

echo "=== Установка прав на выполнение ==="
chmod +x deploy.sh

echo "=== Готово! Экземпляр $INSTANCE_NAME развёрнут ==="