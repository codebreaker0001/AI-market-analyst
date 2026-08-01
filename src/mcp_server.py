"""MCP server exposing the live market-data tools over the Model Context Protocol.

Run standalone:  python -m src.mcp_server   (starts a stdio server)
"""
import yfinance as yf
from fastmcp import FastMCP
import sys
import logging
from contextlib import redirect_stdout

from .ingest_market import _snapshot
from .retrieval import search

mcp = FastMCP("market-data")


@mcp.tool
def get_quote(ticker: str) -> dict:
    """Get the latest price snapshot for a stock ticker: current price,
    day change percent, volume, and 52-week high/low."""
    snap = _snapshot(ticker.upper())
    if not snap:
        return {"ticker": ticker.upper(), "error": "no market data"}
    return snap


@mcp.tool
def get_news(ticker: str, limit: int = 5) -> dict:
    """Get recent news headlines for a stock ticker."""
    try:
        raw = yf.Ticker(ticker.upper()).news or []
    except Exception:
        raw = []
    items = []
    for n in raw[:limit]:
        content = n.get("content", n)
        title = content.get("title") or n.get("title")
        pub = content.get("pubDate") or content.get("providerPublishTime")
        if title:
            items.append({"title": title, "published": str(pub) if pub else None})
    return {"ticker": ticker.upper(), "news": items}


@mcp.tool
def get_price_history(ticker: str, days: int = 30) -> dict:
    """Get recent daily closing prices for a ticker over the last N days."""
    try:
        hist = yf.Ticker(ticker.upper()).history(period=f"{max(days, 5)}d")
    except Exception:
        return {"ticker": ticker.upper(), "error": "no history"}
    closes = [
        {"date": str(d.date()), "close": round(float(c), 2)}
        for d, c in hist["Close"].items()
    ][-days:]
    return {"ticker": ticker.upper(), "closes": closes}

@mcp.tool
def search_filings(query: str, ticker: str = "", k: int = 5) -> dict:
    """Search the company's indexed SEC filings (10-K/10-Q) for relevant passages.
    Phrase the query as a natural descriptive sentence about the topic
    (e.g. 'AI data center infrastructure demand'), NOT as keywords joined by OR/AND —
    the search is semantic. Optionally filter by ticker."""
    try:
        with redirect_stdout(sys.stderr):
            results = search(query, ticker=ticker or None, k=k)
        for r in results:
            r["content"] = r["content"][:800]
            r["filing_date"] = str(r["filing_date"])
        return {"query": query, "ticker": ticker or None, "results": results}
    except Exception as e:
        return {"query": query, "results": [], "error": f"{type(e).__name__}: {e}"}

if __name__ == "__main__":
    mcp.run(transport="stdio")