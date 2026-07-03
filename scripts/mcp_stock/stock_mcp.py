"""Stock lookup MCP server for xiaozhi.me cloud MCP endpoint."""

from __future__ import annotations

import json
import logging
import sys
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger("StockMCP")

if sys.platform == "win32":
    sys.stderr.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")

from fastmcp import FastMCP

mcp = FastMCP("Stock Lookup")

YAHOO_CHART_URL = (
    "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    "?interval=1d&range=5d"
)


def _normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper()


def fetch_stock_quote(symbol: str) -> dict[str, Any]:
    """Fetch latest price and daily change for a US stock ticker (Yahoo Finance API)."""
    ticker_symbol = _normalize_symbol(symbol)
    if not ticker_symbol:
        return {"success": False, "error": "Symbol is required"}

    url = YAHOO_CHART_URL.format(symbol=ticker_symbol)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "DeskBuddyStockMCP/1.0"},
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return {
            "success": False,
            "symbol": ticker_symbol,
            "error": f"HTTP {exc.code} fetching '{ticker_symbol}'",
        }
    except urllib.error.URLError as exc:
        return {
            "success": False,
            "symbol": ticker_symbol,
            "error": f"Network error: {exc.reason}",
        }
    except json.JSONDecodeError:
        return {
            "success": False,
            "symbol": ticker_symbol,
            "error": "Invalid response from market data API",
        }

    chart = (payload.get("chart") or {}).get("result") or []
    if not chart:
        return {
            "success": False,
            "symbol": ticker_symbol,
            "error": f"No market data found for '{ticker_symbol}'. Use a US ticker like AAPL, MSFT, TSLA.",
        }

    result = chart[0]
    meta = result.get("meta") or {}
    closes = (result.get("indicators") or {}).get("quote", [{}])[0].get("close") or []
    highs = (result.get("indicators") or {}).get("quote", [{}])[0].get("high") or []
    lows = (result.get("indicators") or {}).get("quote", [{}])[0].get("low") or []
    volumes = (result.get("indicators") or {}).get("quote", [{}])[0].get("volume") or []

    valid_closes = [c for c in closes if c is not None]
    if not valid_closes:
        return {
            "success": False,
            "symbol": ticker_symbol,
            "error": f"No price data for '{ticker_symbol}'",
        }

    price = float(valid_closes[-1])
    prev_close = float(meta.get("previousClose") or (valid_closes[-2] if len(valid_closes) > 1 else price))
    change = price - prev_close
    change_pct = (change / prev_close * 100.0) if prev_close else 0.0

    day_high = float(highs[-1]) if highs and highs[-1] is not None else price
    day_low = float(lows[-1]) if lows and lows[-1] is not None else price
    volume = int(volumes[-1]) if volumes and volumes[-1] is not None else None
    currency = meta.get("currency") or "USD"
    market_cap = meta.get("marketCap")

    direction = "up" if change >= 0 else "down"
    summary = (
        f"{ticker_symbol} is {direction} {abs(change_pct):.2f}% today at "
        f"{price:.2f} {currency} (change {change:+.2f})."
    )

    return {
        "success": True,
        "symbol": ticker_symbol,
        "price": round(price, 2),
        "previous_close": round(prev_close, 2),
        "change": round(change, 2),
        "change_percent": round(change_pct, 2),
        "day_high": round(day_high, 2),
        "day_low": round(day_low, 2),
        "volume": volume,
        "currency": currency,
        "market_cap": market_cap,
        "summary": summary,
    }


def fetch_stock_quotes(symbols: list[str]) -> dict[str, Any]:
    """Fetch quotes for multiple tickers (max 10)."""
    cleaned = [_normalize_symbol(s) for s in symbols if s and s.strip()]
    if not cleaned:
        return {"success": False, "error": "At least one symbol is required"}

    if len(cleaned) > 10:
        return {"success": False, "error": "Maximum 10 symbols per request"}

    quotes = [fetch_stock_quote(symbol) for symbol in cleaned]
    ok = [q for q in quotes if q.get("success")]
    return {
        "success": len(ok) > 0,
        "count": len(quotes),
        "quotes": quotes,
        "summary": "; ".join(q.get("summary", q.get("error", "")) for q in quotes),
    }


@mcp.tool()
def get_stock_price(symbol: str) -> dict:
    """
    Get the current stock price and how it is doing today for a US stock ticker.

    Use this when the user asks about stock prices, share price, market performance,
    whether a stock is up or down, or how a company stock is doing.

    Args:
        symbol: US stock ticker symbol, for example AAPL, MSFT, TSLA, NVDA, GOOGL.
    """
    result = fetch_stock_quote(symbol)
    logger.info("get_stock_price(%s) -> %s", symbol, result.get("summary", result.get("error")))
    return result


@mcp.tool()
def get_stock_prices(symbols: str) -> dict:
    """
    Get current prices for multiple US stocks in one call.

    Use when the user asks to compare several stocks or list multiple tickers.

    Args:
        symbols: Comma-separated tickers, for example "AAPL,MSFT,GOOGL".
    """
    parts = [s.strip() for s in symbols.split(",") if s.strip()]
    result = fetch_stock_quotes(parts)
    logger.info("get_stock_prices(%s) -> %d quotes", symbols, result.get("count", 0))
    return result


if __name__ == "__main__":
    mcp.run(transport="stdio")
