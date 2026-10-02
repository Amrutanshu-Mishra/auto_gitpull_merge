-- Cortex-enriched issues. One row per issue; refreshed when the source updated_at moves.
CREATE TABLE IF NOT EXISTS ANALYTICS.ISSUES_ENRICHED (
    REPO          STRING             NOT NULL,
    ISSUE_NUMBER  NUMBER             NOT NULL,
    UPDATED_AT    TIMESTAMP_NTZ      NOT NULL,   -- source updated_at the enrichment was computed from
    SENTIMENT     FLOAT,                         -- -1 .. 1
    CATEGORY      STRING,                        -- one of config.categories
    SUMMARY       STRING,                        -- only when body > 300 chars
    EMBEDDING     VECTOR(FLOAT, 768),
    MODEL_VERSION STRING             NOT NULL,   -- functions/models used, for re-enrichment decisions
    ENRICHED_AT   TIMESTAMP_NTZ      NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT PK_ISSUES_ENRICHED PRIMARY KEY (REPO, ISSUE_NUMBER)
);
