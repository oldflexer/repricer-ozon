import os
import time
import logging
from pathlib import Path
import pandas as pd
from openpyxl import load_workbook

logger = logging.getLogger(__name__)

LOCK_WAIT_TIMEOUT = 60


def wait_for_excel_available(file_path: Path, timeout: int = LOCK_WAIT_TIMEOUT) -> bool:
    """Проверяет доступность Excel-файла для записи."""
    test_file = file_path.with_suffix('.lock_test')
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with open(test_file, 'w') as f:
                f.write('lock_test')
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


def save_safely(updates: dict, file_path: Path):
    """
    Точечное обновление ячеек через openpyxl (сохраняет стили).
    updates: {(row, col): value}
    """
    tmp_path = file_path.with_suffix('.tmp.xlsx')
    try:
        import shutil
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
        logger.info(f"Файл {file_path} успешно сохранён (форматирование сохранено).")
    except Exception as e:
        logger.error(f"Ошибка при сохранении файла {file_path}: {e}")
        if tmp_path.exists():
            os.remove(tmp_path)
        raise