"""Central config: loads .env and exposes settings."""
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://analyst:analyst@localhost:5432/market")
SEC_IDENTITY = os.getenv("SEC_IDENTITY", "")
TICKERS = [t.strip().upper() for t in os.getenv("TICKERS", "NVDA,MSFT,GOOGL").split(",") if t.strip()]
# --- Embeddings (Day 2) ---
VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY", "")
EMBED_MODEL = "gemini-embedding-001"   # 1024-dim, matches the schema's VECTOR(1024)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY","")
CHAT_MODEL = "gemini-2.5-flash"
# How many of each form to pull on ingest
N_10K = 1   # latest annual report
N_10Q = 2   # latest two quarterlies