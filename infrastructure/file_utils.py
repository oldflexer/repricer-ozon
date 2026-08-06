"""
Утилиты для работы с файлами.

Содержит функции для проверки доступности файла (блокировка) и
безопасного точечного обновления Excel-файлов с сохранением форматирования.
"""

import os
import shutil
import time
from pathlib import Path

from openpyxl import load_workbook

from infrastructure.logger import logger

LOCK_WAIT_TIMEOUT = 60
"""Таймаут ожидания освобождения Excel-файла (сек)."""


def wait_for_excel_available(file_path: Path, timeout: int = LOCK_WAIT_TIMEOUT) -> bool:
    """
    Проверяет доступность Excel-файла для записи (не заблокирован ли другим процессом).

    Создаёт временный файл .lock_test; если это удаётся – файл доступен.

    Args:
        file_path: Путь к Excel-файлу.
        timeout: Максимальное время ожидания (сек).

    Returns:
        True, если файл доступен, иначе False.
    """
    test_file = file_path.with_suffix(".lock_test")
    deadline = time.time() + timeout

    while time.time() < deadline:
        try:
            with open(test_file, "w") as f:
                f.write("lock_test")
            os.remove(test_file)
            return True
        except PermissionError:
            logger.warning(f"Файл {file_path} занят. Ожидание освобождения...")
            time.sleep(2)
        except Exception as e:
            logger.error(f"Непредвиденная ошибка доступа к файлу: {e}")
            return False

    logger.error(f"Файл {file_path} оставался занятым дольше {timeout} сек.")
    return False


def save_safely(updates: dict, file_path: Path, max_retries: int = 3) -> None:
    """
    Сохраняет точечные обновления ячеек в Excel-файл с повторными попытками.

    Args:
        updates: Словарь {(row, col): value} для обновления.
        file_path: Путь к Excel-файлу.
        max_retries: Количество попыток при ошибках.

    Raises:
        Exception: Если после всех попыток сохранение не удалось.
    """
    tmp_path = file_path.with_suffix(".tmp.xlsx")
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            shutil.copy2(file_path, tmp_path)
            wb = load_workbook(tmp_path)
            ws = wb.active
            if ws is None:
                raise ValueError("Нет активного листа в книге")

            for (row, col), value in updates.items():
                ws.cell(row=row, column=col, value=value)

            wb.save(tmp_path)
            wb.close()
            os.replace(tmp_path, file_path)
            logger.info(f"Файл {file_path} успешно сохранён (попытка {attempt})")
            return
        except Exception as e:
            last_error = e
            logger.warning(f"Ошибка сохранения (попытка {attempt}/{max_retries}): {e}")
            if tmp_path.exists():
                os.remove(tmp_path)
            if attempt < max_retries:
                time.sleep(1)

    logger.error(f"Не удалось сохранить файл {file_path} после {max_retries} попыток: {last_error}")
    raise last_error or RuntimeError("Ошибка сохранения файла")