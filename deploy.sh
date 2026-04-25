#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "=== Ветка server ==="
git checkout server

echo "=== Обновление кода ==="
git pull origin server

echo "=== Активация venv и установка зависимостей ==="
source venv/bin/activate
pip install -r requirements.txt

echo "=== Применение миграций (если будут) ==="
# python manage.py migrate  # зарезервировано для будущих миграций БД

echo "=== Перезапуск веб-интерфейса ==="
sudo systemctl restart repricer-web

echo "=== Готово! ==="