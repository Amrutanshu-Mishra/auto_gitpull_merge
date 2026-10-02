-- model: analytics_repo_health
-- One row per repo. Category counts are an OBJECT keyed by category so the set of
-- categories stays in config.yaml, not in this model.
-- dbt: refs stg_issues; ISSUES_ENRICHED is a source (written by the enrich step).
CREATE OR REPLACE VIEW ANALYTICS.REPO_HEALTH AS
WITH issues AS (
    SELECT
        i.repo,
        i.issue_number,
        i.is_open,
        i.days_open,
        i.created_at,
        e.category,
        e.sentiment
    FROM STAGING.STG_ISSUES i
    LEFT JOIN ANALYTICS.ISSUES_ENRICHED e
           ON e.repo = i.repo AND e.issue_number = i.issue_number
),
by_category AS (
    SELECT repo, OBJECT_AGG(category, n) AS issues_by_category
    FROM (
        SELECT repo, COALESCE(category, 'unclassified') AS category, COUNT(*) AS n
        FROM issues
        GROUP BY 1, 2
    )
    GROUP BY 1
),
per_repo AS (
    SELECT
        repo,
        COUNT(*)                                                    AS total_issues,
        COUNT_IF(is_open)                                           AS open_issues,
        COUNT_IF(NOT is_open)                                       AS closed_issues,
        COUNT_IF(is_open) / NULLIF(COUNT_IF(NOT is_open), 0)        AS open_closed_ratio,
        AVG(sentiment)                                              AS avg_sentiment,
        MEDIAN(days_open)                                           AS median_days_open,
        COUNT(*) / GREATEST(DATEDIFF('week', MIN(created_at), CURRENT_TIMESTAMP()), 1)
                                                                    AS issues_per_week,
        COUNT_IF(created_at >= DATEADD('day', -7, CURRENT_TIMESTAMP()))
                                                                    AS issues_created_last_7d,
        MIN(created_at)                                             AS first_issue_at,
        MAX(created_at)                                             AS last_issue_at
    FROM issues
    GROUP BY 1
)
SELECT
    p.repo,
    p.total_issues,
    p.open_issues,
    p.closed_issues,
    p.open_closed_ratio,
    c.issues_by_category,
    p.avg_sentiment,
    p.median_days_open,
    p.issues_per_week,
    p.issues_created_last_7d,
    p.first_issue_at,
    p.last_issue_at
FROM per_repo p
LEFT JOIN by_category c ON c.repo = p.repo
