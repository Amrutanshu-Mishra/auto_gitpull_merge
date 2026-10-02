# Roadmap

Roughly in order. Each item respects the conventions in CLAUDE.md: plugins for sources,
numbered migrations for schema, single-model transforms, config not constants.

1. **Scheduling with Snowflake Tasks + Streams** — a Stream on `RAW.GITHUB_EVENTS_RAW` and a
   Task chain (`transform` → `enrich`) so enrichment runs inside Snowflake minutes after new
   rows land; ingest stays external (cron / GitHub Actions) until the extractor moves behind an
   external access integration.
2. **dbt migration** — lift `transforms/` into a dbt project 1:1 (`stg_` / `int_` / marts),
   `RAW` and `ISSUES_ENRICHED` as sources, tests on keys and freshness. The Python `transform`
   step becomes `dbt run`.
3. **More sources: PRs, commits, releases** — `github_pulls`, `github_commits`,
   `github_releases` extractors reusing `GITHUB_EVENTS_RAW`; staging views per entity; PR
   cycle time and release cadence in `REPO_HEALTH`.
4. **Cortex Search** — replace the hand-rolled `VECTOR_COSINE_SIMILARITY` query with a Cortex
   Search service over title + body + summary for hybrid (keyword + vector) retrieval and
   better *Ask* grounding.
5. **Stale-issue prediction (Snowpark ML)** — train on closed issues (category, sentiment,
   comments, author history, label set) to predict which open issues will go stale; surface a
   "likely to rot" list on Overview.
6. **GitHub App duplicate detector** — on `issues.opened`, embed the new issue, look up the top
   matches, and comment "possibly related: #123 (0.91)"; feedback reactions logged to META for
   threshold tuning.
7. **Slack alerts** — weekly `REPO_HEALTH` digest and instant alerts on sentiment drops or
   issue-rate spikes, via a Snowflake notification integration.
8. **Streamlit in Snowflake** — deploy `app/` as a SiS app; `queries.get_conn()` already
   detects the Snowpark session, so the change is packaging only (stage upload of `app/`,
   `repo_pulse/`, `config.yaml`).
