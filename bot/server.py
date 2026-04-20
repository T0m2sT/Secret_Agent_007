import os
import json
import logging
import anthropic
import requests
from flask import Flask, request

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ANTHROPIC_KEY = os.environ["ANTHROPIC_API_KEY"]
PORTFOLIO_URL = os.environ["PORTFOLIO_RAW_URL"]

def send(chat_id: str, text: str) -> None:
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
        resp.raise_for_status()
        if not resp.json().get("ok"):
            logger.error("Telegram error: %s", resp.json().get("description"))
    except requests.RequestException as exc:
        logger.error("Failed to send message: %r", exc)

def get_portfolio() -> dict:
    resp = requests.get(PORTFOLIO_URL, timeout=10)
    resp.raise_for_status()
    return resp.json()

@app.route(f"/webhook/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    data = request.json
    message = data.get("message", {})
    chat_id = str(message.get("chat", {}).get("id", ""))
    text = message.get("text", "").strip()

    if not chat_id or not text:
        return "ok", 200

    try:
        if text == "/reason":
            portfolio = get_portfolio()
            alert = portfolio.get("last_alert")
            if not alert:
                send(chat_id, "No recent alert to explain.")
            else:
                reasoning = alert.get("reasoning", "No reasoning available.")
                ticker = alert.get("ticker", "")
                action = alert.get("action", "")
                send(chat_id, f"🧠 *Analysis — {action} {ticker}*\n\n{reasoning}")

        elif text.startswith("/ask "):
            question = text[5:].strip()
            portfolio = get_portfolio()
            alert = portfolio.get("last_alert", {})
            context = f"Last alert: {json.dumps(alert, indent=2)}\nPortfolio cash: €{portfolio.get('cash', 0):.2f}"
            client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
            resp_ai = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=512,
                system="You are a concise trading analyst. Answer the user's question about their portfolio in 2-4 sentences.",
                messages=[{"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}],
            )
            send(chat_id, resp_ai.content[0].text)

        elif text == "/portfolio":
            portfolio = get_portfolio()
            lines = [f"📊 *Portfolio*\n💵 Cash: €{portfolio['cash']:.2f}\n\n*Holdings:*"]
            for h in portfolio.get("holdings", []):
                pnl = (h["last_price"] - h["avg_buy_price"]) * h["shares"]
                pnl_str = f"+€{pnl:.2f}" if pnl >= 0 else f"-€{abs(pnl):.2f}"
                lines.append(f"  {h['ticker']}: {h['shares']} shares | P&L: {pnl_str}")
            if portfolio.get("watchlist"):
                lines.append(f"\n👀 Watching: {', '.join(portfolio['watchlist'])}")
            send(chat_id, "\n".join(lines))

        elif text == "/status":
            portfolio = get_portfolio()
            last_run = portfolio.get("last_run", "Never")
            send(chat_id, f"🕐 Last run: {last_run}\n⏱ Next run: within 4 hours")

    except Exception as exc:
        logger.error("Webhook handler error: %r", exc)
        send(chat_id, "⚠️ An error occurred. Please try again later.")

    return "ok", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
