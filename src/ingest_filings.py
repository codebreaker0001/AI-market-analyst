from edgar import Company , set_identity

from .config import DATABASE_URL , N_10K ,N_10Q ,SEC_IDENTITY, TICKERS

from .db import connect


def _upsert_company(cur, ticker: str, company: Company):
    cur.execute(
        """
        INSERT INTO companies (ticker, name, cik, industry, updated_at)
        VALUES (%s, %s, %s, %s, now())
        ON CONFLICT (ticker) DO UPDATE
          SET name = EXCLUDED.name,
              cik = EXCLUDED.cik,
              industry = EXCLUDED.industry,
              updated_at = now();
        """,
        (ticker, company.name, str(company.cik), getattr(company, "industry", None)),
    )

def _save_filing(cur, ticker: str, filing) -> bool:
    """Insert one filing. Returns True if newly inserted, False if already present."""
    text = filing.text()
    cur.execute(
        """
        INSERT INTO filings (ticker, form, filing_date, period_of_report,
                             accession_no, raw_text, char_count)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (accession_no) DO NOTHING;
        """,
        (
            ticker,
            filing.form,
            filing.filing_date,
            str(getattr(filing, "period_of_report", "") or ""),
            filing.accession_no,
            text,
            len(text),
        ),
    )
    return cur.rowcount > 0

def ingest():
    if not SEC_IDENTITY:
        raise SystemExit(
            "SEC_IDENTITY is not set. Put 'Your Name your@email.com' in .env "
            "(SEC rejects requests without it)."
        )
    set_identity(SEC_IDENTITY)

    with connect() as conn,  conn.cursor() as cur:
        for tickers in TICKERS:
            print(f"\n=={tickers}==")
            company = Company(tickers)
            _upsert_company(cur, tickers, company)

            conn.commit()

            targets = [
                ("10-K", company.get_filings(form="10-K").latest(N_10K)),
                ("10-Q", company.get_filings(form="10-Q").latest(N_10Q)),
            ]
            for form, result in targets:
                filings = [result] if not hasattr(result, "__iter__") else list(result)
                for f in filings:
                    if f is None:
                        continue
                    added = _save_filing(cur, tickers, f)
                    conn.commit()
                    flag = "added" if added else "exists"
                    print(f"  {form}  {f.filing_date}  {f.accession_no}  [{flag}]")

    print("\n[filings] done")


if __name__ =="__main__":
    ingest()


