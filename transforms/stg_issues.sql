-- model: stg_issues
-- One row per issue (PRs excluded upstream). Typed columns pulled out of the untouched payload.
-- dbt: `select ... from {{ source('raw', 'github_events_raw') }}`; materialized as a view.
CREATE OR REPLACE VIEW STAGING.STG_ISSUES AS
SELECT
    repo,
    entity_id::NUMBER                                          AS issue_number,
    payload:title::STRING                                      AS title,
    LEFT(payload:body::STRING, 4000)                           AS body,
    payload:state::STRING                                      AS state,
    payload:user.login::STRING                                 AS author_login,
    TRANSFORM(payload:labels::ARRAY, l -> l:name::STRING)      AS labels,
    payload:comments::NUMBER                                   AS comments_count,
    payload:created_at::TIMESTAMP_NTZ                          AS created_at,
    payload:updated_at::TIMESTAMP_NTZ                          AS updated_at,
    payload:closed_at::TIMESTAMP_NTZ                           AS closed_at,
    payload:html_url::STRING                                   AS html_url,
    payload:state::STRING = 'open'                             AS is_open,
    DATEDIFF(
        'day',
        payload:created_at::TIMESTAMP_NTZ,
        COALESCE(payload:closed_at::TIMESTAMP_NTZ, CURRENT_TIMESTAMP()::TIMESTAMP_NTZ)
    )                                                          AS days_open
FROM RAW.GITHUB_EVENTS_RAW
WHERE source = 'github_issues'
