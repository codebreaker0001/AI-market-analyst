"""Diagnose what yfinance is actually returning."""
import yfinance as yf

print("yfinance version:", yf.__version__)

t = yf.Ticker("AAPL")

print("\n--- fast_info ---")
try:
    fi = t.fast_info
    print("last_price:", fi.get("last_price"))
    print("keys:", list(fi.keys())[:10])
except Exception as e:
    print("fast_info ERROR:", type(e).__name__, e)

print("\n--- history(5d) ---")
try:
    h = t.history(period="5d")
    print("rows:", len(h))
    print(h[["Close"]].tail() if len(h) else "EMPTY dataframe")
except Exception as e:
    print("history ERROR:", type(e).__name__, e)