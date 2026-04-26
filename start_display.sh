#!/bin/bash
# start_display.sh – управляет Xvfb и x11vnc

DISPLAY_NUM=99
RESOLUTION="1920x1080x24"

# ---------- Xvfb ----------
if pgrep -f "Xvfb :${DISPLAY_NUM}" >/dev/null; then
    echo "Xvfb :${DISPLAY_NUM} уже запущен, перезапускаем..."
    pkill -f "Xvfb :${DISPLAY_NUM}"
    sleep 1
else
    echo "Xvfb :${DISPLAY_NUM} не найден, запускаем..."
fi

Xvfb :${DISPLAY_NUM} -screen 0 ${RESOLUTION} &
sleep 1
echo "Xvfb :${DISPLAY_NUM} запущен"

# ---------- x11vnc ----------
if pgrep -f "x11vnc -display :${DISPLAY_NUM}" >/dev/null; then
    echo "x11vnc для :${DISPLAY_NUM} уже запущен, перезапускаем..."
    pkill -f "x11vnc -display :${DISPLAY_NUM}"
    sleep 1
else
    echo "x11vnc для :${DISPLAY_NUM} не найден, запускаем..."
fi

x11vnc -display :${DISPLAY_NUM} -bg -nopw -listen localhost -xkb
sleep 1
echo "x11vnc для :${DISPLAY_NUM} запущен"

# ---------- Экспорт DISPLAY ----------
export DISPLAY=:${DISPLAY_NUM}
echo "DISPLAY установлен в :${DISPLAY_NUM}"