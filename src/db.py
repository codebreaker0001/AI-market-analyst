from pathlib import Path
import psycopg
from .config import DATABASE_URL

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "sql" / "schema.sql"

def connect():
     """Open a new connection. Use with a `with` block so it closes cleanly."""
     return psycopg.connect(DATABASE_URL)


def init_db():
    """Run schema.sql — idempotent, safe to run repeatedly."""
    ddl = SCHEMA_PATH.read_text()

    with connect() as conn , conn.cursor() as curr:
        curr.execute(ddl)
        conn.commit()

    print("[db] Schema ready")



if __name__ =="__main__":

    init_db()