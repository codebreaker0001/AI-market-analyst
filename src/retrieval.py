import argparse
from google import genai
from google.genai import types
from pgvector import Vector
from pgvector.psycopg import register_vector

from .config import GEMINI_API_KEY, EMBED_MODEL 
from .db import connect

_client = None
EMBED_DIM = 1024


def _get_client():
    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            raise SystemExit("GEMINI PAI ERROR")
        _client = genai.Client(api_key = GEMINI_API_KEY)

    return _client

def embed_query(text):

    resp = _get_client().models.embed_content(
        model = EMBED_MODEL,
        contents = [text] ,
        config = types.EmbedContentConfig(
            task_type = "RETRIEVAL_QUERY",
            output_dimensionality=EMBED_DIM
        )
    )
    return resp.embeddings[0].values


def search(query, ticker=None , section = None, k = 5):

    qvec = Vector(embed_query(query))

    conditions = ["c.embedding IS NOT NULL"]
    params = {"qvec":qvec,"k":k}

    if ticker:
        conditions.append("c.ticker = %(ticker)s")
        params["ticker"] = ticker.upper()
    if section:
        conditions.append("c.section = %(section)s")
        params["section"] = section
    where = " AND ".join(conditions)

    sql = f"""
        SELECT c.ticker, c.section, c.content,
               f.form, f.filing_date,
               1 - (c.embedding <=> %(qvec)s) AS similarity
        FROM chunks c
        JOIN filings f ON f.id = c.filing_id
        WHERE {where}
        ORDER BY c.embedding <=> %(qvec)s
        LIMIT %(k)s;
    """
    with connect() as conn:
        register_vector(conn)
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    return [
        {"ticker": r[0], "section": r[1], "content": r[2],
         "form": r[3], "filing_date": r[4], "similarity": float(r[5])}
        for r in rows
    ]

def _main():
    ap = argparse.ArgumentParser(description="Search filing chunks")
    ap.add_argument("query")
    ap.add_argument("--ticker", default=None)
    ap.add_argument("--section", default=None)
    ap.add_argument("-k", type=int, default=5)
    args = ap.parse_args()

    results = search(args.query, ticker=args.ticker, section=args.section, k=args.k)
    if not results:
        print("no results")
        return
    for i, r in enumerate(results, 1):
        print(f"\n--- {i}. {r['ticker']} · {r['section']} · {r['form']} "
              f"{r['filing_date']} · sim={r['similarity']:.3f} ---")
        snippet = r["content"][:400].replace("\n", " ")
        print(snippet + ("..." if len(r["content"]) > 400 else ""))


if __name__ == "__main__":
    _main()