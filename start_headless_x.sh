#!/bin/bash
DISPLAY_NUM=99
SCREEN_SIZE="1920x1080x24"

# Убиваем старый Xorg, если висит
if pgrep -f "Xorg :${DISPLAY_NUM}" > /dev/null; then
    echo "Xorg :${DISPLAY_NUM} уже запущен, перезапускаем..."
    kill $(pgrep -f "Xorg :${DISPLAY_NUM}")
    sleep 2
else
    echo "Xorg :${DISPLAY_NUM} не найден, запускаем..."
fi

Xorg ":${DISPLAY_NUM}" -config /etc/X11/xorg.conf.d/10-headless.conf -noreset +extension GLX +extension RANDR &
export DISPLAY=":${DISPLAY_NUM}"
echo "export DISPLAY=:${DISPLAY_NUM}"

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