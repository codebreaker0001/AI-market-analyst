import re
from .db import connect

MAX_WORDS = 350
OVERLAP = 60
MIN_BLOCKS_WORD = 30

ITEM_NAMES = {
    "1": "Business", "1A": "Risk Factors", "1B": "Unresolved Staff Comments",
    "2": "Properties", "3": "Legal Proceedings", "5": "Market for Common Equity",
    "6": "Selected Financial Data", "7": "MD&A", "7A": "Market Risk",
    "8": "Financial Statements", "9A": "Controls and Procedures",
}

HEADER_RE = re.compile(r'(?im)^\s*item\s+(\d{1,2}[A-C]?)[.\-\u2014:)\s]')

def split_sections(text):
    matches = list(HEADER_RE.finditer(text))

    if not matches:
        return [("Full document", text)]

    blocks = []
    if matches[0].start() > 0:
        blocks.append(("Preamble" , text[:matches[0].start()]))

    for i,m in enumerate(matches):
        item = m.group(1).upper()
        section = ITEM_NAMES.get(item, f"Item {item}")
        start = m.start()
        end = matches[i+1].start() if i + 1< len(matches) else len(text)
        blocks.append((section , text[start:end]))

    return blocks


def chunk_text( text , max_words = MAX_WORDS , overlap = OVERLAP):

    words = text.split()

    if not words:
        return []
    chunks , step = [] , max_words - overlap

    for start in range (0 , len(words) , step):
        piece = words[start:start+max_words]
        if piece:
            chunks.append(" ".join(piece))
        if start + max_words >= len(words):
            break

    return chunks

def build_chunks(raw_text):

    out, idx = [],0

    for section , block in split_sections(raw_text):
        if len(block.split()) < MIN_BLOCKS_WORD:
            continue

        for piece in chunk_text(block):
            out.append({
                "section":section,
                "chunk_index":idx,
                "content":piece,
                "token_count": int(len(piece.split())/0.75)
            })
            idx +=1

    return out

def chunk_all():
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, ticker, form, raw_text FROM filings ORDER by ticker, filing_date;")
        filings = cur.fetchall()

        for filing_id, ticker,form, raw_text in filings:
            if not raw_text:
                continue

            cur.execute("DELETE FROM chunks WHERE filing_id = %s;", (filing_id,))

            chunks = build_chunks(raw_text)

            for c in chunks:
                cur.execute(
                    """
                    INSERT INTO chunks (filing_id, ticker, section, chunk_index, content, token_count)
                    VALUES (%s, %s, %s, %s, %s, %s);
                    """,
                    (filing_id, ticker, c["section"], c["chunk_index"], c["content"], c["token_count"]),
                )

            conn.commit()
            print(f"  {ticker:6s} {form:5s} filing {filing_id}: {len(chunks)} chunks")

    print("\n[chunk] done")


if __name__ == "__main__":
    chunk_all()