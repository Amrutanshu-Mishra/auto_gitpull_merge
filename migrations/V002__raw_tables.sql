-- One generic landing table for every GitHub entity type (issues, PRs, commits, releases, ...).
-- New sources reuse it; they differ only by SOURCE.
CREATE TABLE IF NOT EXISTS RAW.GITHUB_EVENTS_RAW (
    SOURCE     STRING        NOT NULL,   -- extractor name, e.g. 'github_issues'
    REPO       STRING        NOT NULL,   -- 'owner/name'
    ENTITY_ID  STRING        NOT NULL,   -- source-native id (issue number, PR number, sha, ...)
    UPDATED_AT TIMESTAMP_NTZ NOT NULL,   -- source updated_at (UTC); MERGE only overwrites when newer
    PAYLOAD    VARIANT       NOT NULL,   -- untouched source JSON
    FETCHED_AT TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    -- Snowflake does not enforce UNIQUE. It documents the key the pipeline MERGEs on.
    CONSTRAINT UK_GITHUB_EVENTS_RAW UNIQUE (SOURCE, REPO, ENTITY_ID)
);
