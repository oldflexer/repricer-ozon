"""
Unit tests for file_utils.py
"""

from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from infrastructure.file_utils import LOCK_WAIT_TIMEOUT, save_safely, wait_for_excel_available


class TestFileUtils:
    """Tests for file_utils module."""

    def test_wait_for_excel_available_success(self):
        """Test wait_for_excel_available when file is immediately available."""
        file_path = Path("/tmp/test.xlsx")

        with patch("builtins.open", mock_open()) as m, patch("os.remove") as mock_remove:
            result = wait_for_excel_available(file_path, timeout=1)

            assert result is True
            m.assert_called_once_with(file_path.with_suffix(".lock_test"), "w")
            mock_remove.assert_called_once_with(file_path.with_suffix(".lock_test"))

    def test_wait_for_excel_available_permission_error_then_success(self):
        """Test wait_for_excel_available with temporary PermissionError."""
        file_path = Path("/tmp/test.xlsx")

        call_count = [0]

        def mock_open_func(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise PermissionError("File busy")
            return mock_open()(*args, **kwargs)

        with (
            patch("builtins.open", side_effect=mock_open_func),
            patch("os.remove"),
            patch("time.sleep") as mock_sleep,
        ):
            result = wait_for_excel_available(file_path, timeout=5)

            assert result is True
            mock_sleep.assert_called_with(2)

    def test_wait_for_excel_available_timeout(self):
        """Test wait_for_excel_available times out."""
        file_path = Path("/tmp/test.xlsx")

        # time.time() is called multiple times in the while loop
        # Also the logging module uses time.time() internally
        # Provide enough values to cover all calls
        time_values = [1000 + i for i in range(200)]  # 1000-1199

        with (
            patch("builtins.open", side_effect=PermissionError("File busy")),
            patch("time.sleep"),
            patch("time.time", side_effect=time_values),
        ):
            result = wait_for_excel_available(file_path, timeout=60)

            assert result is False

    def test_wait_for_excel_available_other_exception(self):
        """Test wait_for_excel_available with unexpected exception."""
        file_path = Path("/tmp/test.xlsx")

        with patch("builtins.open", side_effect=OSError("Disk full")):
            result = wait_for_excel_available(file_path, timeout=1)

            assert result is False

    def test_save_safely_success(self):
        """Test save_safely succeeds on first attempt."""
        file_path = Path("/tmp/test.xlsx")
        updates = {(1, 1): "value1", (2, 2): "value2"}

        with (
            patch("shutil.copy2"),
            patch("infrastructure.file_utils.load_workbook") as mock_load_wb,
            patch("os.replace") as mock_replace,
        ):
            mock_wb = MagicMock()
            mock_ws = MagicMock()
            mock_wb.active = mock_ws
            mock_load_wb.return_value = mock_wb

            save_safely(updates, file_path, max_retries=3)

            mock_load_wb.assert_called_once()
            mock_wb.save.assert_called_once()
            mock_wb.close.assert_called_once()
            mock_replace.assert_called_once()

    def test_save_safely_retries_then_succeeds(self):
        """Test save_safely retries on failure then succeeds."""
        file_path = Path("/tmp/test.xlsx")
        updates = {(1, 1): "value1"}

        call_count = [0]

        def mock_load_wb_func(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Temp error")
            mock_wb = MagicMock()
            mock_ws = MagicMock()
            mock_wb.active = mock_ws
            return mock_wb

        with (
            patch("shutil.copy2"),
            patch("infrastructure.file_utils.load_workbook", side_effect=mock_load_wb_func),
            patch("os.replace"),
            patch("os.path.exists", return_value=True),
            patch("os.remove"),
            patch("time.sleep") as mock_sleep,
        ):
            save_safely(updates, file_path, max_retries=3)

            assert call_count[0] == 2
            mock_sleep.assert_called_with(1)

    def test_save_safely_all_retries_fail(self):
        """Test save_safely raises after all retries fail."""
        file_path = Path("/tmp/test.xlsx")
        updates = {(1, 1): "value1"}

        with (
            patch("shutil.copy2"),
            patch(
                "infrastructure.file_utils.load_workbook", side_effect=Exception("Persistent error")
            ),
            patch("os.path.exists", return_value=True),
            patch("os.remove"),
            patch("time.sleep"),
            pytest.raises(Exception, match="Persistent error"),
        ):
            save_safely(updates, file_path, max_retries=3)

    def test_save_safely_no_active_sheet(self):
        """Test save_safely fails when no active sheet."""
        file_path = Path("/tmp/test.xlsx")
        updates = {(1, 1): "value1"}

        with (
            patch("shutil.copy2"),
            patch("infrastructure.file_utils.load_workbook") as mock_load_wb,
        ):
            mock_wb = MagicMock()
            mock_wb.active = None
            mock_load_wb.return_value = mock_wb

            with pytest.raises(ValueError, match="Нет активного листа"):
                save_safely(updates, file_path, max_retries=3)

    def test_lock_wait_timeout_constant(self):
        """Test LOCK_WAIT_TIMEOUT constant."""
        assert LOCK_WAIT_TIMEOUT == 60


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
