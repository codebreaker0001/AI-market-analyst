
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS companies (
    ticker TEXT PRIMARY KEY,
    name TEXT,
    cik TEXT,
    industry TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS filings (
    id                BIGSERIAL PRIMARY KEY,
    ticker            TEXT REFERENCES companies(ticker) ON DELETE CASCADE,
    form              TEXT,                      
    filing_date       DATE,
    period_of_report  TEXT,
    accession_no      TEXT UNIQUE,              
    raw_text          TEXT,
    char_count        INT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chunks (
    id           BIGSERIAL PRIMARY KEY,
    filing_id    BIGINT REFERENCES filings(id) ON DELETE CASCADE,
    ticker       TEXT,
    section      TEXT,                           -- 'Risk Factors', 'MD&A', ...
    chunk_index  INT,
    content      TEXT,
    token_count  INT,
    embedding    VECTOR(1024),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS chunks_ticker_idx  ON chunks (ticker);
CREATE INDEX IF NOT EXISTS chunks_section_idx ON chunks (section);

CREATE TABLE IF NOT EXISTS market_snapshots (
    id              BIGSERIAL PRIMARY KEY,
    ticker          TEXT REFERENCES companies(ticker) ON DELETE CASCADE,
    price           NUMERIC,
    previous_close  NUMERIC,
    day_change_pct  NUMERIC,
    volume          BIGINT,
    week52_high     NUMERIC,
    week52_low      NUMERIC,
    captured_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS market_ticker_time_idx ON market_snapshots (ticker, captured_at DESC);

CREATE TABLE IF NOT EXISTS briefs (
    id          BIGSERIAL PRIMARY KEY,
    ticker      TEXT,
    content     JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);