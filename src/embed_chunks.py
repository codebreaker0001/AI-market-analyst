"""Embed filing chunks with Google Gemini and store the vectors.

Run:  python -m src.embed_chunks
Resumable — only embeds chunks whose embedding is still NULL.
"""
import time
from google import genai
from google.genai import types
from google.genai.errors import ClientError, ServerError
from pgvector.psycopg import register_vector

from .config import GEMINI_API_KEY, EMBED_MODEL
from .db import connect

EMBED_DIM = 1024

BATCH_SIZE = 50     # chunks per Gemini request
MAX_RETRIES = 5


def _embed_batch(client, texts):
    """Embed a batch with retry + backoff. Returns a list of 1024-dim vectors."""
    delay = 2
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.models.embed_content(
                model=EMBED_MODEL,
                contents=texts,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT",     # these are stored documents
                    output_dimensionality=EMBED_DIM,    # 1024, matches the schema
                ),
            )
            return [e.values for e in resp.embeddings]
        except (ClientError, ServerError) as e:
            # 429 = rate limited; retry. Other client errors are real bugs -> raise.
            if isinstance(e, ClientError) and getattr(e, "code", None) != 429:
                raise
            if attempt == MAX_RETRIES:
                raise
            print(f"    rate limited — retrying in {delay}s")
            time.sleep(delay)
            delay *= 2
    return []


def embed_all():
    if not GEMINI_API_KEY:
        raise SystemExit("GOOGLE_API_KEY not set in .env")
    client = genai.Client(api_key=GEMINI_API_KEY)

    with connect() as conn:
        register_vector(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM chunks WHERE embedding IS NULL;")
            todo = cur.fetchone()[0]
            print(f"chunks to embed: {todo}")
            if not todo:
                print("nothing to do — all chunks already embedded")
                return

            done = 0
            while True:
                cur.execute(
                    "SELECT id, content FROM chunks "
                    "WHERE embedding IS NULL ORDER BY id LIMIT %s;",
                    (BATCH_SIZE,),
                )
                rows = cur.fetchall()
                if not rows:
                    break

                ids = [r[0] for r in rows]
                texts = [r[1] for r in rows]
                vectors = _embed_batch(client, texts)

                cur.executemany(
                    "UPDATE chunks SET embedding = %s WHERE id = %s;",
                    list(zip(vectors, ids)),
                )
                conn.commit()
                done += len(rows)
                print(f"  embedded {done}/{todo}")

                time.sleep(60)

    print("\n[embed] done")


if __name__ == "__main__":
    embed_all()