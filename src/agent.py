import argparse
from google import genai
from google.genai import types
from psycopg.types.json import Jsonb

from .config import GEMINI_API_KEY, CHAT_MODEL
from .db import connect
from .tools import get_quote, get_news, search_filings

SYSTEM = """You are an equity research assistant. Given a stock ticker, produce a concise
"Should I care about this stock today?" brief for a reader who already knows the company.

Process:
1. Call get_quote for the current price, day change, volume, and 52-week range.
2. If the day's move is notable (roughly >2-3%) or the context is unclear, call get_news to find why.
3. Call search_filings to pull the company's own SEC-filing context relating to whatever is moving
   the stock (e.g. if datacenter demand is the story, search for that). Use specific queries.
4. Cross-reference: does today's move CONFIRM or CONTRADICT what the filings said about the business?
   This cross-reference is the most important part — not just price and news restated side by side.

Write the brief with these sections:
- HEADLINE: one line, the single most important thing today.
- WHAT MOVED: price, day change, position in the 52-week range.
- WHY: the driver (from news), or "no clear catalyst" if quiet.
- DOES IT MATTER: connect the move to fundamentals from the filings. Does it hit something
  management flagged as important or risky? Confirm or contradict? Reference the filing section.
- WATCH: 1-2 things to watch next.

Rules:
- Ground every claim in tool results. Do NOT invent numbers, dates, or quotes.
- If the filings don't address the topic, say so rather than guessing.
- Be concise. This is research and analysis, NOT financial advice — note that briefly at the end.
"""

def generate_brief(ticker: str):
    if not GEMINI_API_KEY:
        raise SystemExit("GOOGLE_API_KEY not set in .env")

    client = genai.Client(api_key = GEMINI_API_KEY)

    resp = client.models.generate_content(
        model = CHAT_MODEL,
        contents=f"Produce a 'Should i Care today' brief for {ticker.upper()} ",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM,
            tools=[get_quote , get_news , search_filings],
            temperature=0.3,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                maximum_remote_calls=8
            ),
        ),
    )

    return resp

def _print_tool_calls(resp):
    print("\n--- agent actions (tools it chose to call) ---")
    called = False
    for content in (resp.automatic_function_calling_history or []):
        for part in (content.parts or []):
            fc = getattr(part, "function_call", None)
            if fc:
                called = True
                args = dict(fc.args) if fc.args else {}
                pretty = ", ".join(f"{k}={v!r}" for k, v in args.items())
                print(f"  → {fc.name}({pretty})")
    if not called:
        print("  (none)")


def _save_brief(ticker, text):
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO briefs (ticker, content) VALUES (%s, %s);",
            (ticker.upper(), Jsonb({"brief": text})),
        )
        conn.commit()

def _main():
    ap = argparse.ArgumentParser(description="Generate a stock brief")
    ap.add_argument("ticker")
    ap.add_argument("--no-save", action="store_true", help="don't store the brief in the DB")
    args = ap.parse_args()

    resp = generate_brief(args.ticker)
    _print_tool_calls(resp)

    print("\n" + "=" * 70)
    print(f"BRIEF — {args.ticker.upper()}")
    print("=" * 70)
    print(resp.text)

    if not args.no_save:
        _save_brief(args.ticker, resp.text)
        print("\n[saved to briefs table]")


if __name__ == "__main__":
    _main()