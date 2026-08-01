import yfinance as yf
from .ingest_market import _snapshot
from .retrieval import search

def get_quote(ticker : str) ->dict:

    snap = _snapshot(ticker.upper())

    if not snap:
        return {"ticker" : ticker.upper(), "error": "no market data"}

    return snap

def get_news(ticker : str , limit : int = 5) -> dict:

    try:
        raw = yf.Ticker(ticker.upper()).news or []
    except Exception:
        raw = []

    items = []

    for n in raw[:limit]:
        content = n.get("content",n)
        title = content.get("title") or n.get("title")
        pub = content.get("pubDate") or content.get("providerPublishTime")

        if title:
            items.append({"title":title , "published":str(pub) if pub else None})

    return {"ticker":ticker.upper(), "items":items}

def search_filings(query:str ,  ticker:str = None, k: int = 5)->dict:
    results = search(query, ticker=ticker , k=k)

    for r in results:
        r["content"] = r["content"][:800]
        r["filing_date"] = str(r["filing_date"])

    return {"query":query , "ticker":ticker , "results":results}