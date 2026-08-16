import shutil
import time

from openpyxl import load_workbook

LOCK_WAIT_TIMEOUT = 60


def wait_for_excel_available(file_path, timeout=60):
    """
    Wait until the Excel file becomes available (can be opened for writing).
    Returns True if file becomes available within timeout, False otherwise.
    """
    start = time.time()
    while time.time() - start < timeout:
        try:
            # Try to open the file in write mode to check if it's locked
            with file_path.open("w") as _:
                pass
            # If we can open it, delete the test file and return True
            file_path.unlink()
            return True
        except PermissionError:
            # File is locked, wait and retry
            time.sleep(2)
        except Exception:
            # Other error (e.g., file doesn't exist), return False
            return False
    return False


def save_safely(updates, file_path, max_retries=3):
    """
    Safely updates an Excel file with retry logic.
    Creates a backup, applies updates, saves to temp file, then replaces original.
    """
    for attempt in range(max_retries):
        try:
            # Create a backup
            backup_path = file_path.with_suffix(file_path.suffix + ".backup")
            shutil.copy2(file_path, backup_path)

            # Load the workbook
            wb = load_workbook(file_path)
            ws = wb.active
            if ws is None:
                raise ValueError("Нет активного листа")

            # Apply updates
            for (row, col), value in updates.items():
                ws.cell(row=row, column=col, value=value)

            # Save to a temporary file
            temp_path = file_path.with_suffix(file_path.suffix + ".tmp")
            wb.save(temp_path)
            wb.close()

            # Replace the original file with the temporary file
            temp_path.replace(file_path)

            # If we get here, break out of the retry loop
            break
        except Exception:
            if attempt == max_retries - 1:
                raise
            time.sleep(1)  # Wait before retry
