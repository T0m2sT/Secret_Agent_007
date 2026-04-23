import logging
import requests
import yfinance as yf

logger = logging.getLogger(__name__)

_TRENDING_URL = "https://query1.finance.yahoo.com/v1/finance/trending/US"
_FINNHUB_URL = "https://finnhub.io/api/v1"


def fetch_trending_tickers(limit: int = 10) -> list[str]:
    """Fetch trending tickers from Yahoo Finance's US trending endpoint.

    Returns up to `limit` ticker symbols currently trending on Yahoo Finance.
    Never raises — returns an empty list on any failure.
    """
    try:
        resp = requests.get(
            _TRENDING_URL,
            params={"count": limit, "lang": "en-US"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        if resp.status_code != 200:
            logger.warning("fetch_trending_tickers: HTTP %d", resp.status_code)
            return []
        quotes = resp.json()["finance"]["result"][0]["quotes"]
        return [q["symbol"] for q in quotes[:limit] if "symbol" in q]
    except Exception as exc:
        logger.warning("fetch_trending_tickers failed: %r", exc)
        return []


def fetch_prices(tickers: list[str], api_key: str = None) -> dict[str, dict]:
    """Fetch real-time prices using Finnhub API (free tier supports real-time quotes).

    Returns a mapping of ticker -> {"price": float (USD), "pct_change": float}.
    Falls back to yfinance if Finnhub fails.
    Tickers with missing data are silently skipped.
    Never raises — returns an empty dict on complete failure.
    
    Args:
        tickers: List of ticker symbols
        api_key: Finnhub API key (optional, free tier allows limited requests without key)
    """
    prices = {}
    
    # Try Finnhub first for real-time quotes
    if api_key:
        for ticker in tickers:
            try:
                resp = requests.get(
                    f"{_FINNHUB_URL}/quote",
                    params={"symbol": ticker, "token": api_key},
                    timeout=10,
                )
                if resp.status_code != 200:
                    logger.warning("fetch_prices (Finnhub): HTTP %d for %s", resp.status_code, ticker)
                    continue
                
                data = resp.json()
                if "c" not in data or "o" not in data:
                    logger.warning("fetch_prices (Finnhub): missing price data for %s", ticker)
                    continue
                
                current_price = float(data["c"])  # current price
                open_price = float(data["o"])    # open price
                if open_price == 0:
                    # Fallback: use previous close if available
                    prev_close = float(data.get("pc", open_price))
                    if prev_close == 0:
                        continue
                    pct = ((current_price - prev_close) / prev_close) * 100
                else:
                    pct = ((current_price - open_price) / open_price) * 100
                
                prices[ticker] = {"price": round(current_price, 2), "pct_change": round(pct, 1)}
            except Exception as exc:
                logger.warning("fetch_prices (Finnhub) failed for %s: %r", ticker, exc)
                continue
        
        # If we got some prices from Finnhub, return them
        if prices:
            return prices
    
    # Fallback to yfinance with minute-level data for 24-hour availability
    logger.info("Falling back to yfinance for price data")
    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            # Fetch daily data first for reference (previous close)
            hist_daily = t.history(period="5d")
            if hist_daily.empty or len(hist_daily) < 2:
                logger.warning("fetch_prices: no history data for %s", ticker)
                continue
            
            prev_close = float(hist_daily["Close"].iloc[-2])
            
            # Try to get minute-level data from the last day (includes pre/post market)
            try:
                hist_minute = t.history(period="1d", interval="1m")
                if not hist_minute.empty and len(hist_minute) > 0:
                    last_price = float(hist_minute["Close"].iloc[-1])
                else:
                    # No minute data available, use daily close
                    last_price = float(hist_daily["Close"].iloc[-1])
            except Exception:
                # Fallback to daily close if minute data fails
                last_price = float(hist_daily["Close"].iloc[-1])
            
            if prev_close == 0:
                continue
            
            pct = ((last_price - prev_close) / prev_close) * 100
            prices[ticker] = {"price": round(last_price, 2), "pct_change": round(pct, 1)}
        except Exception as exc:
            logger.warning("fetch_prices failed for %s: %r", ticker, exc)
            continue
    
    return prices


def fetch_news(tickers: list[str], api_key: str) -> dict[str, list[str]]:
    """Fetch the latest headlines for each ticker from NewsAPI.

    Returns a mapping of ticker -> [headline, ...] (up to 3 per ticker).
    On any error (network, non-200 status, parse failure) the ticker
    maps to an empty list.  Never raises.

    Args:
        tickers: List of ticker symbols to search for.
        api_key: NewsAPI key supplied by the caller (must come from an
                 environment variable — never hardcode).
    """
    news: dict[str, list[str]] = {}
    for ticker in tickers:
        try:
            resp = requests.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": ticker,
                    "pageSize": 3,
                    "sortBy": "publishedAt",
                    "apiKey": api_key,
                },
                timeout=10,
            )
            if resp.status_code != 200:
                news[ticker] = []
                continue
            articles = resp.json().get("articles", [])
            news[ticker] = [a["title"] for a in articles[:3]]
        except Exception as exc:
            logger.warning("fetch_news failed for %s: %r", ticker, exc)
            news[ticker] = []
    return news
