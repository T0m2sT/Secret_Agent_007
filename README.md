# Portfolio Agent

An AI-powered stock trading bot that monitors individual stocks up to 10 times per day, generates aggressive BUY/SELL/HOLD signals using Claude, and delivers them via Telegram. Runs entirely on GitHub Actions (agent) and Railway (Telegram bot server).

---

## How it works

### 1. Scheduled runs (GitHub Actions)

The agent runs automatically on this UTC schedule, clustered around US market hours:

| UTC | Lisbon (summer) | Purpose |
|-----|-----------------|---------|
| 08:00 | 09:00 | Your market open |
| 10:00 | 11:00 | Mid-morning |
| 13:00 | 14:00 | Pre-US open |
| 14:30 | 15:30 | US market open |
| 16:00 | 17:00 | US open momentum |
| 17:00 | 18:00 | US mid-session |
| 18:00 | 19:00 | US mid-session |
| 19:00 | 20:00 | Pre-US close |
| 20:30 | 21:30 | US market close |
| 22:00 | 23:00 | After-hours wrap |

You can also trigger a run manually via **Actions → Run workflow**.

---

### 2. Market calendar check

Before doing anything, the agent checks if the US market is open today via the Finnhub API. If it's a weekend or public holiday, the run exits silently — no prices fetched, no Claude call, no Telegram message.

---

### 3. Data fetching

The agent fetches three types of data for every ticker in your holdings, watchlist, and trending stocks:

- **Live prices** (Finnhub API, with yfinance fallback) — current price, today's % change, day high/low, 5-day high/low, week-over-week % change
- **News headlines** (NewsAPI) — up to 3 recent headlines per ticker
- **Trending tickers** (Yahoo Finance) — top 10 trending US stocks added as market buzz

---

### 4. Claude analysis

All data is sent to Claude (claude-sonnet-4-6) with a carefully engineered prompt. The prompt includes:

- **Current UTC time and market session** — Claude calibrates signal urgency based on whether it's pre-market, US open, mid-session, or after-hours
- **Per-ticker previous signals** — Claude checks what it recommended last run for each ticker to avoid flip-flopping
- **Portfolio allocation %** — each holding's share of total portfolio value, enabling rebalancing signals
- **5-day price context** — weekly range and trend, not just today's move
- **News quality filter** — Claude is instructed to discard vague, recycled, or tangentially related headlines

Claude's behaviour is configured to be aggressive and news-driven:
- News is the primary signal — a strong headline is enough to act
- SELL signals can be issued for **any stock**, including ones not in the portfolio (short positions)
- HOLD is only output when there is genuinely no edge
- Every non-HOLD action must name the specific news catalyst and explain why now

---

### 5. Signals and output

Claude returns a JSON object with:
- `actions` — one entry per holding and watchlist ticker: `BUY`, `SELL`, or `HOLD` with amount and reasoning
- `watchlist_additions` — tickers to start tracking
- `watchlist_removals` — tickers to stop tracking

**If there are non-HOLD signals:** each one is sent as an individual Telegram alert with the headline, price, and reasoning.

**If everything is HOLD:** a single summary message is sent listing all positions and their current prices.

---

### 6. Portfolio state update

After each run, `portfolio.json` is committed back to the repo with:
- Updated watchlist
- Last alert per ticker (for flip-flop prevention next run)
- Timestamp of last run

---

## Telegram bot commands

The bot server runs on Railway and listens for commands 24/7.

| Command | Description |
|---------|-------------|
| `/portfolio` | Current holdings, cash balance, and avg buy prices |
| `/log` | Closed trade history with P&L per trade and total |
| `/status` | Last agent run time and next scheduled run (Lisbon time) |
| `/reason` | Full reasoning behind the last BUY/SELL alert |
| `/ask [question]` | Ask Claude anything about your portfolio |
| `/buy TICKER SHARES PRICE_USD COST_EUR` | Record a buy (e.g. `/buy NVDA 2 880.00 40.00`) |
| `/sell TICKER SHARES\|%\|ALL PRICE_USD PROCEEDS_EUR` | Record a sell (e.g. `/sell NVDA ALL 900.00 82.00`) |
| `/reset` | Wipe portfolio back to €100 clean state |
| `/help` | Show all available commands |

---

## Project structure

```
agent/
  main.py          # Orchestrates the full run cycle
  analyst.py       # Claude prompt engineering and response parsing
  fetcher.py       # Price, news, and trending data fetching
  portfolio.py     # Portfolio state management (load, save, apply actions)
  notifier.py      # Telegram message formatting and sending

bot/
  server.py        # Flask webhook server for Telegram bot commands

tests/             # Full test suite (91% coverage)

.github/workflows/
  portfolio-agent.yml   # Scheduled GitHub Actions workflow

portfolio.json     # Live portfolio state (auto-committed after each run)
```

---

## Environment variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Claude API key |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token |
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID |
| `NEWS_API_KEY` | NewsAPI key |
| `FINNHUB_API_KEY` | Finnhub API key (real-time prices + market status) |
| `GITHUB_TOKEN` | GitHub token (bot server writes portfolio.json via API) |
| `GITHUB_REPO` | Repo in `owner/name` format |
| `PORTFOLIO_RAW_URL` | Raw URL to `portfolio.json` in the repo |

GitHub Actions secrets: `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `NEWS_API_KEY`, `FINNHUB_API_KEY`.

Railway env vars: all of the above plus `GITHUB_TOKEN`, `GITHUB_REPO`, `PORTFOLIO_RAW_URL`.
