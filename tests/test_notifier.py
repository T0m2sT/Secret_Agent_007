import logging
import pytest
import requests
from unittest.mock import MagicMock
from agent.notifier import format_alert, format_portfolio, send_message

def test_format_alert_sell():
    action = {"ticker": "NVDA", "action": "SELL", "amount": "30%", "headline": "Export controls hit chip stocks", "reasoning": "Risk elevated short-term."}
    prices = {"NVDA": {"price": 118.40, "pct_change": -4.2}}
    msg = format_alert(action, prices)
    assert "SELL 30%" in msg
    assert "NVDA" in msg
    assert "118.40" in msg
    assert "-4.2%" in msg
    assert "Export controls" in msg
    assert "/reason" in msg

def test_format_alert_hold():
    action = {"ticker": "SPY", "action": "HOLD", "reasoning": "Stable trend."}
    prices = {"SPY": {"price": 520.00, "pct_change": 0.3}}
    msg = format_alert(action, prices)
    assert "HOLD" in msg
    assert "SPY" in msg
    assert "/reason" in msg

def test_format_alert_buy():
    action = {"ticker": "TSLA", "action": "BUY", "amount": "23.40", "headline": "Tesla new model launch", "reasoning": "Momentum building."}
    prices = {"TSLA": {"price": 234.00, "pct_change": 2.1}}
    msg = format_alert(action, prices)
    assert "BUY €23.40" in msg
    assert "TSLA" in msg

def test_format_portfolio():
    portfolio = {
        "cash": 23.40,
        "holdings": [{"ticker": "NVDA", "shares": 0.25, "avg_buy_price": 110.00, "last_price": 118.40}],
        "watchlist": ["AMD"],
        "last_run": "2026-04-20T12:00:00+00:00"
    }
    msg = format_portfolio(portfolio)
    assert "NVDA" in msg
    assert "23.40" in msg
    assert "P&L" in msg


def test_send_message_success(mocker):
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {"ok": True}
    mocker.patch("agent.notifier.requests.post", return_value=mock_resp)
    send_message("token", "chat", "hello")  # should not raise


def test_send_message_request_exception_is_logged(mocker, caplog):
    mocker.patch("agent.notifier.requests.post", side_effect=requests.RequestException("timeout"))
    with caplog.at_level(logging.ERROR, logger="agent.notifier"):
        send_message("token", "chat", "hello")
    assert "Failed to send" in caplog.text
