#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "=== Ветка server ==="
git checkout server

echo "=== Сброс локальных изменений ==="
git reset --hard HEAD

echo "=== Обновление кода ==="
git pull origin server

echo "=== Активация venv и установка зависимостей ==="
source venv/bin/activate
pip install -r requirements.txt

echo "=== Перезапуск веб-интерфейса ==="
sudo systemctl restart repricer-web

echo "=== Установка флагов +x для скриптов ==="
chmod +x /home/user/repricer-ozon/deploy.sh
chmod +x /home/user/repricer-ozon/start_display.sh
chmod +x /home/user/repricer-ozon/set_env.sh

echo "=== Готово! ==="