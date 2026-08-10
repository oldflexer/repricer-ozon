"""
Unit tests for mail_notifier.py
"""

from unittest.mock import MagicMock, patch

import pytest

from infrastructure.mail_notifier import MailNotifier


class TestMailNotifier:
    """Tests for MailNotifier class."""

    @pytest.fixture
    def notifier(self):
        """Create MailNotifier with mocked settings."""
        with patch("infrastructure.mail_notifier.settings") as mock_settings:
            mock_settings.SMTP_HOST = "smtp.test.com"
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_USER = "user@test.com"
            mock_settings.SMTP_PASSWORD = "password"
            mock_settings.SENDER_EMAIL = "sender@test.com"
            mock_settings.RECIPIENT_EMAIL = "recipient@test.com"
            mock_settings.NOTIFICATION_MAX_DETAILS = 10
            notifier = MailNotifier()
            yield notifier

    def test_init(self, notifier):
        """Test initialization with settings."""
        assert notifier.host == "smtp.test.com"
        assert notifier.port == 587
        assert notifier.user == "user@test.com"
        assert notifier.password == "password"
        assert notifier.sender == "sender@test.com"
        assert notifier.recipient == "recipient@test.com"

    def test_check_config_missing(self):
        """Test _check_config with missing settings."""
        with patch("infrastructure.mail_notifier.settings") as mock_settings:
            mock_settings.SMTP_HOST = ""
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_USER = "user@test.com"
            mock_settings.SMTP_PASSWORD = "password"
            mock_settings.SENDER_EMAIL = "sender@test.com"
            mock_settings.RECIPIENT_EMAIL = "recipient@test.com"
            mock_settings.NOTIFICATION_MAX_DETAILS = 10
            notifier = MailNotifier()
            assert notifier._check_config() is False

    @patch("infrastructure.mail_notifier.smtplib.SMTP")
    def test_send_success(self, mock_smtp, notifier):
        """Test successful email send."""
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        result = notifier.send_message("Test Subject", "Test Body")

        assert result is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user@test.com", "password")
        mock_server.sendmail.assert_called_once()
        mock_server.quit.assert_called_once()

    @patch("infrastructure.mail_notifier.smtplib.SMTP")
    def test_send_failure(self, mock_smtp, notifier):
        """Test email send failure."""
        mock_smtp.side_effect = Exception("SMTP Error")

        result = notifier.send_message("Test Subject", "Test Body")

        assert result is False

    @patch("infrastructure.mail_notifier.smtplib.SMTP")
    def test_send_message_with_attachment(self, mock_smtp, notifier):
        """Test send_message_with_attachment."""
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        result = notifier.send_message_with_attachment(
            "Test Subject", "Test Body", "test.csv", "col1,col2\nval1,val2"
        )

        assert result is True
        mock_server.sendmail.assert_called_once()

    def test_generate_csv(self, notifier):
        """Test _generate_csv creates proper CSV."""
        updates = [
            {
                "sku": "SKU1",
                "product_name": "Product 1",
                "old_price": 100,
                "new_price": 110,
                "status": "updated",
                "reason": "",
            },
            {
                "sku": "SKU2",
                "product_name": "Product 2",
                "old_price": 200,
                "new_price": None,
                "status": "error",
                "reason": "API error",
            },
        ]

        csv_content = notifier._generate_csv(updates)

        # Check that all expected fields are present in the CSV (utf-8-sig adds BOM)
        assert "SKU" in csv_content
        assert "Название" in csv_content
        assert "Старая цена" in csv_content
        assert "Новая цена" in csv_content
        assert "Статус" in csv_content
        assert "Причина" in csv_content
        assert "SKU1" in csv_content
        assert "Product 1" in csv_content
        assert "100" in csv_content
        assert "110" in csv_content
        assert "updated" in csv_content
        assert "SKU2" in csv_content
        assert "error" in csv_content
        assert "API error" in csv_content

    @patch.object(MailNotifier, "send_message")
    @patch.object(MailNotifier, "send_message_with_attachment")
    def test_send_detailed_report_dry_run(self, mock_with_attachment, mock_send, notifier):
        """Test send_detailed_report in dry-run mode."""
        updates = [
            {
                "sku": "SKU1",
                "product_name": "Product 1",
                "old_price": 100,
                "new_price": 110,
                "status": "updated",
                "reason": "",
            },
        ]

        notifier.send_detailed_report(updates, [], dry_run=True)

        mock_send.assert_called_once()
        args = mock_send.call_args
        assert "[DRY-RUN]" in args[0][0]
        assert "ТЕСТОВЫЙ ЗАПУСК" in args[0][1]

    @patch.object(MailNotifier, "send_message")
    @patch.object(MailNotifier, "send_message_with_attachment")
    def test_send_detailed_report_with_csv_attachment(
        self, mock_with_attachment, mock_send, notifier
    ):
        """Test send_detailed_report uses CSV attachment when over limit."""
        with patch("infrastructure.mail_notifier.settings") as mock_settings:
            mock_settings.NOTIFICATION_MAX_DETAILS = 2
            updates = [
                {
                    "sku": f"SKU{i}",
                    "product_name": f"Product {i}",
                    "old_price": 100,
                    "new_price": 110,
                    "status": "updated",
                    "reason": "",
                }
                for i in range(5)
            ]

            notifier.send_detailed_report(updates, [], dry_run=False)

            mock_with_attachment.assert_called_once()
            mock_send.assert_not_called()

    @patch.object(MailNotifier, "send_message")
    @patch.object(MailNotifier, "send_message_with_attachment")
    def test_send_detailed_report_with_errors(self, mock_with_attachment, mock_send, notifier):
        """Test send_detailed_report includes errors."""
        updates = [
            {
                "sku": "SKU1",
                "product_name": "Product 1",
                "old_price": 100,
                "new_price": 110,
                "status": "updated",
                "reason": "",
            },
        ]
        errors = ["API timeout", "Database error"]

        notifier.send_detailed_report(updates, errors, dry_run=False)

        mock_send.assert_called_once()
        args = mock_send.call_args
        assert "Общие ошибки" in args[0][1]
        assert "API timeout" in args[0][1]
        assert "Database error" in args[0][1]

    @patch.object(MailNotifier, "send_message")
    def test_notify_cycle_complete(self, mock_send, notifier):
        """Test notify_cycle_complete (deprecated method)."""
        notifier.notify_cycle_complete(5, ["Error 1", "Error 2"])

        mock_send.assert_called_once()
        args = mock_send.call_args
        assert "5" in args[0][0]
        assert "Error 1" in args[0][1]

    @patch.object(MailNotifier, "send_message")
    def test_notify_critical_event(self, mock_send, notifier):
        """Test notify_critical_event (deprecated method)."""
        notifier.notify_critical_event("Critical: API down")

        mock_send.assert_called_once()
        args = mock_send.call_args
        assert "критическое событие" in args[0][0].lower()
        assert "API down" in args[0][1]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
