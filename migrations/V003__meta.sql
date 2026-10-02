-- Incremental-load bookkeeping and a run log.
CREATE TABLE IF NOT EXISTS META.INGEST_WATERMARKS (
    SOURCE          STRING        NOT NULL,
    REPO            STRING        NOT NULL,
    LAST_UPDATED_AT TIMESTAMP_NTZ,           -- max source updated_at seen; next run fetches since here
    LAST_RUN_AT     TIMESTAMP_NTZ,
    ROWS_LOADED     INTEGER,
    CONSTRAINT PK_INGEST_WATERMARKS PRIMARY KEY (SOURCE, REPO)
);

CREATE TABLE IF NOT EXISTS META.PIPELINE_RUNS (
    RUN_ID      STRING        NOT NULL,     -- one id per CLI invocation
    STEP        STRING        NOT NULL,     -- migrate | ingest:<source> | transform:<model> | enrich
    STATUS      STRING        NOT NULL,     -- running | success | failed
    STARTED_AT  TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    FINISHED_AT TIMESTAMP_NTZ,
    ROWS        INTEGER,
    ERROR       STRING
);
