"""Research agent whose tools are served over MCP (manual tool loop).

We list the MCP tools, describe them to Gemini as plain function declarations,
and execute Gemini's chosen calls through the MCP session ourselves. This keeps
the (unpicklable) stdio session out of the Gemini config, avoiding the deep-copy
crash, while still routing every tool call through MCP.

Run:  python -m src.agent_mcp NVDA
"""
import sys
import json
import asyncio
import argparse

from google import genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from psycopg.types.json import Jsonb

from .config import GEMINI_API_KEY, CHAT_MODEL
from .db import connect

SYSTEM = """You are an equity research assistant. Given a stock ticker, produce a concise
"Should I care about this stock today?" brief for a reader who already knows the company.

Process:
1. Call get_quote for the current price, day change, volume, and 52-week range.
2. If the day's move is notable (>2-3%) or context is unclear, call get_news to find why.
3. Optionally call get_price_history for the recent trend.
4. Call search_filings to pull the company's SEC-filing context on whatever is moving the stock.
   Phrase queries as natural descriptive sentences, NOT boolean keywords.
5. Cross-reference: does today's move CONFIRM or CONTRADICT what the filings said? This is the
   most important part.

Sections: HEADLINE / WHAT MOVED / WHY / DOES IT MATTER (tie to filings, name the section) / WATCH.
Ground every claim in tool results; do not invent numbers. Research only — NOT financial advice.
"""

_ALLOWED = {"type", "properties", "required", "items", "enum", "description"}


def _clean_schema(s: dict) -> dict:
    """Reduce an MCP JSON Schema to the subset Gemini's Schema accepts."""
    out = {}
    for key, val in (s or {}).items():
        if key not in _ALLOWED:
            continue
        if key == "properties":
            out["properties"] = {
                p: {k: v for k, v in pdef.items() if k in ("type", "description", "enum", "items")}
                for p, pdef in val.items()
            }
        else:
            out[key] = val
    return out


def _mcp_result_to_dict(result) -> dict:
    """Turn an MCP call result into a JSON-safe dict for the function response."""
    sc = getattr(result, "structuredContent", None)
    if isinstance(sc, dict):
        return sc
    texts = [getattr(b, "text", "") for b in (result.content or []) if getattr(b, "text", "")]
    joined = "\n".join(texts)
    try:
        data = json.loads(joined)
        return data if isinstance(data, dict) else {"result": data}
    except Exception:
        return {"result": joined}


async def generate_brief(ticker: str, max_steps: int = 8):
    if not GEMINI_API_KEY:
        raise SystemExit("GEMINI_API_KEY not set in .env")
    client = genai.Client(api_key=GEMINI_API_KEY)

    params = StdioServerParameters(
        command=sys.executable, args=["-m", "src.mcp_server"], cwd="."
    )
    calls_made = []

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 1. Discover MCP tools -> Gemini function declarations
            mcp_tools = (await session.list_tools()).tools
            declarations = [
                types.FunctionDeclaration(
                    name=t.name,
                    description=(t.description or "")[:1024],
                    parameters=_clean_schema(t.inputSchema),
                )
                for t in mcp_tools
            ]
            gemini_tools = [types.Tool(function_declarations=declarations)]

            config = types.GenerateContentConfig(
                system_instruction=SYSTEM,
                tools=gemini_tools,
                temperature=0.3,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            )

            # 2. Manual reason-act loop
            contents = [types.Content(
                role="user",
                parts=[types.Part.from_text(text=f"Produce a 'should I care today?' brief for {ticker.upper()}.")],
            )]

            final_text = ""
            for _ in range(max_steps):
                resp = await client.aio.models.generate_content(
                    model=CHAT_MODEL, contents=contents, config=config
                )
                parts = resp.candidates[0].content.parts or []
                fcs = [p.function_call for p in parts if getattr(p, "function_call", None)]

                if not fcs:                      # model is done -> it produced the brief
                    final_text = resp.text
                    break

                contents.append(resp.candidates[0].content)   # record the model's tool-call turn

                response_parts = []
                for fc in fcs:
                    args = dict(fc.args) if fc.args else {}
                    calls_made.append((fc.name, args))
                    result = await session.call_tool(fc.name, args)   # execute via MCP
                    response_parts.append(
                        types.Part.from_function_response(
                            name=fc.name, response=_mcp_result_to_dict(result)
                        )
                    )
                contents.append(types.Content(role="user", parts=response_parts))

    return final_text, calls_made


def _save_brief(ticker, text):
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO briefs (ticker, content) VALUES (%s, %s);",
            (ticker.upper(), Jsonb({"brief": text})),
        )
        conn.commit()


def _main():
    ap = argparse.ArgumentParser(description="Generate a stock brief (tools via MCP)")
    ap.add_argument("ticker")
    ap.add_argument("--no-save", action="store_true")
    args = ap.parse_args()

    text, calls = asyncio.run(generate_brief(args.ticker))

    print("\n--- agent actions (tools called via MCP) ---")
    for name, a in calls:
        pretty = ", ".join(f"{k}={v!r}" for k, v in a.items())
        print(f"  → {name}({pretty})")
    if not calls:
        print("  (none)")

    print("\n" + "=" * 70)
    print(f"BRIEF — {args.ticker.upper()}  (tools served via MCP)")
    print("=" * 70)
    print(text or "(no text returned)")

    if not args.no_save and text:
        _save_brief(args.ticker, text)
        print("\n[saved to briefs table]")


if __name__ == "__main__":
    _main()