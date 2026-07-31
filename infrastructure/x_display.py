"""
Утилита для определения доступного X-сервера (Linux/macOS).

Находит свободный DISPLAY для запуска браузера в headful-режиме.
На Windows всегда возвращает None.
"""

import glob
import logging
import os
import subprocess
import sys
from typing import Optional

logger = logging.getLogger(__name__)


def get_available_display() -> Optional[str]:
    """
    Определяет доступный X-сервер и возвращает строку DISPLAY (например, ':10.0').

    На Windows всегда возвращает None.

    Алгоритм:
        1. Если DISPLAY уже задан в окружении, проверяет его доступность.
        2. Ищет сокеты в /tmp/.X11-unix/ и проверяет каждый.
        3. Возвращает первый доступный дисплей или None.

    Returns:
        Строка DISPLAY или None.
    """
    if sys.platform.startswith("win"):
        logger.info("Windows: X-сервер не используется, возвращаем None")
        return None

    # 1. Проверяем текущий DISPLAY
    if "DISPLAY" in os.environ:
        display = os.environ["DISPLAY"]
        if _is_display_available(display):
            return display

    # 2. Ищем сокеты X11
    sockets = glob.glob("/tmp/.X11-unix/X*")
    displays = []
    for sock in sockets:
        num = sock.split("/")[-1][1:]  # номер после 'X'
        if num.isdigit():
            display = f":{num}.0"
            if _is_display_available(display):
                displays.append(display)

    if not displays:
        logger.warning("Не найден доступный X-сервер. Браузер не сможет открыться.")
        return None

    return displays[0]


def _is_display_available(display: str) -> bool:
    """
    Проверяет доступность X-сервера (только для Linux/macOS).

    Args:
        display: Строка DISPLAY (например, ':10.0').

    Returns:
        True, если X-сервер доступен.
    """
    if sys.platform.startswith("win"):
        return False

    # Проверка существования сокета
    socket_path = f'/tmp/.X11-unix/X{display[1:].split(".")[0]}'
    if not os.path.exists(socket_path):
        return False

    # Проверка через xdpyinfo (если установлен)
    try:
        subprocess.run(
            ["xdpyinfo", "-display", display],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=1,
            check=True,
        )
        return True
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
        # Если xdpyinfo нет, проверяем .Xauthority
        xauth_file = os.environ.get("XAUTHORITY", os.path.expanduser("~/.Xauthority"))
        if os.path.exists(xauth_file):
            try:
                result = subprocess.run(
                    ["xauth", "list", display],
                    capture_output=True,
                    text=True,
                    timeout=1,
                )
                if result.returncode == 0 and result.stdout.strip():
                    return True
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
        return False