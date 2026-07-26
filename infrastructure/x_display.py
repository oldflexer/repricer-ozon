import os
import sys
import glob
import subprocess
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def get_available_display() -> Optional[str]:
    """
    Определяет доступный X-сервер и возвращает строку DISPLAY (например, ':10.0').
    На Windows всегда возвращает None, так как X11 не используется.
    """
    if sys.platform.startswith('win'):
        logger.info("Windows: X-сервер не используется, возвращаем None")
        return None

    # 1. Если DISPLAY уже задан, проверяем, работает ли он
    if 'DISPLAY' in os.environ:
        display = os.environ['DISPLAY']
        if _is_display_available(display):
            return display

    # 2. Ищем все сокеты X11
    sockets = glob.glob('/tmp/.X11-unix/X*')
    displays = []
    for sock in sockets:
        num = sock.split('/')[-1][1:]  # извлекаем номер после 'X'
        if num.isdigit():
            display = f':{num}.0'
            if _is_display_available(display):
                displays.append(display)

    # 3. Если ничего не найдено, возвращаем None
    if not displays:
        logger.warning("Не найден доступный X-сервер. Браузер не сможет открыться.")
        return None

    # 4. Возвращаем первый найденный
    return displays[0]


def _is_display_available(display: str) -> bool:
    """Проверка доступности X-сервера (только для Linux/macOS)."""
    if sys.platform.startswith('win'):
        return False

    # Проверяем, что сокет существует
    socket_path = f'/tmp/.X11-unix/X{display[1:].split(".")[0]}'
    if not os.path.exists(socket_path):
        return False

    # Проверяем через xdpyinfo (если установлен)
    try:
        subprocess.run(
            ['xdpyinfo', '-display', display],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=1,
            check=True
        )
        return True
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
        # Если xdpyinfo нет, проверяем наличие записи в .Xauthority
        xauth_file = os.environ.get('XAUTHORITY', os.path.expanduser('~/.Xauthority'))
        if os.path.exists(xauth_file):
            try:
                result = subprocess.run(
                    ['xauth', 'list', display],
                    capture_output=True,
                    text=True,
                    timeout=1
                )
                if result.returncode == 0 and result.stdout.strip():
                    return True
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
        return False