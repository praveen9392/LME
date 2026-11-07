"""
Integration tests for Telegram alert formatting and dispatch.
"""
from unittest.mock import patch, MagicMock
from backend.integrations.telegram.client import TelegramClient


def test_telegram_client_send_success():
    client = TelegramClient(bot_token="123456:FAKE_TOKEN", chat_id="999888777")
    assert client.is_ready() is True

    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_post.return_value = mock_resp

        success = client.send("Hello world")
        assert success is True
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "123456:FAKE_TOKEN" in args[0]
        assert kwargs["json"]["chat_id"] == "999888777"
        assert kwargs["json"]["text"] == "Hello world"


def test_telegram_alert_helpers():
    client = TelegramClient(bot_token="123456:FAKE_TOKEN", chat_id="999888777")

    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_post.return_value = mock_resp

        assert client.alert_run_started("manual") is True
        assert client.alert_apply("Backend Engineer", "Stripe", 92, "JOB_123") is True
        assert client.alert_failed("Backend Engineer", "Stripe", "Network error") is True
        assert client.alert_run_summary(20, 5, 2, 3, 0) is True
        assert client.alert_profile_updated("Headline updated") is True
        assert client.alert_error("Critical error") is True
        assert client.alert_scheduler_started(["Task 1", "Task 2"]) is True
        assert client.alert_scheduler_stopped() is True
