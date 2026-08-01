
import math
import yfinance as yf

from .config import TICKERS
from .db import connect


def _snapshot(ticker: str) -> dict | None:
    # One year of daily bars gives us price, prev close, volume, and 52-wk range
    hist = yf.Ticker(ticker).history(period="1y")
    if hist.empty or len(hist) < 2:
        print(f"  {ticker}: no history returned, skipping")
        return None

    closes = hist["Close"]
    price = float(closes.iloc[-1])   # most recent close
    prev = float(closes.iloc[-2])    # previous trading day's close

    vol = hist["Volume"].iloc[-1]
    volume = int(vol) if vol is not None and not math.isnan(vol) else None

    day_change_pct = round((price - prev) / prev * 100, 2) if prev else None

    return {
        "ticker": ticker,
        "price": round(price, 2),
        "previous_close": round(prev, 2),
        "day_change_pct": day_change_pct,
        "volume": volume,
        "week52_high": round(float(hist["High"].max()), 2),
        "week52_low": round(float(hist["Low"].min()), 2),
    }


def ingest():
    with connect() as conn, conn.cursor() as cur:
        for ticker in TICKERS:
            snap = _snapshot(ticker)
            if not snap:
                continue
            cur.execute(
                """
                INSERT INTO market_snapshots
                    (ticker, price, previous_close, day_change_pct,
                     volume, week52_high, week52_low)
                VALUES (%(ticker)s, %(price)s, %(previous_close)s,
                        %(day_change_pct)s, %(volume)s, %(week52_high)s, %(week52_low)s);
                """,
                snap,
            )
            conn.commit()
            chg = f"{snap['day_change_pct']:+.2f}%" if snap["day_change_pct"] is not None else "n/a"
            print(f"  {ticker:6s} {snap['price']:>10.2f}  ({chg})")

    print("\n[market] done")


if __name__ == "__main__":
    ingest()