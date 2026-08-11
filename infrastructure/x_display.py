"""
Утилита для определения доступного X-сервера (Linux/macOS).

Находит свободный DISPLAY для запуска браузера в headful-режиме.
На Windows всегда возвращает None.
"""

import os
import subprocess
import sys
from pathlib import Path

from infrastructure.logger import logger


def get_available_display() -> str | None:
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
        display: str = os.environ["DISPLAY"]
        if _is_display_available(display):
            return display

    # 2. Ищем сокеты X11
    sockets: list[str] = [str(p) for p in Path("/tmp/.X11-unix").glob("X*")]
    displays: list[str] = []
    for sock in sockets:
        num: str = sock.split("/")[-1][1:]  # номер после 'X'
        if num.isdigit():
            display_candidate: str = f":{num}.0"
            if _is_display_available(display_candidate):
                displays.append(display_candidate)

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
    socket_path = Path(f'/tmp/.X11-unix/X{display[1:].split(".", maxsplit=1)[0]}')
    if not socket_path.exists():
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
        xauth_file = Path(os.environ.get("XAUTHORITY", str(Path.home() / ".Xauthority")))
        if xauth_file.exists():
            try:
                result: subprocess.CompletedProcess[str] = subprocess.run(
                    ["xauth", "list", display],
                    capture_output=True,
                    text=True,
                    timeout=1,
                    check=False,
                )
                if result.returncode == 0 and result.stdout.strip():
                    return True
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
        return False

