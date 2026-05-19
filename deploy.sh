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
    python3 -m .venv .venv
fi

echo "=== Активация venv и установка зависимостей ==="
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "=== Перезапуск веб-интерфейса ==="
sudo systemctl restart repricer-web

echo "=== Установка прав на выполнение ==="
chmod +x deploy.sh

echo "=== Готово! ==="