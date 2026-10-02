# repo-pulse

GitHub engineering-intelligence platform on Snowflake. Extract GitHub data → land it in Snowflake → transform → serve insights (incl. Cortex-powered) in a Streamlit app.

## Layout

```
repo_pulse/           package: config.py, db.py, cli.py, pipeline.py, migrate.py, enrich.py
repo_pulse/sources/   one plugin per source, each subclasses Extractor (base.py); auto-discovered
migrations/           numbered DDL: V001__name.sql, V002__...
transforms/           one SQL model per file; run stg_* -> int_* -> rest, then by name (future dbt models)
app/                  Streamlit app; app/queries.py is the only SQL entry point
config.yaml           repos, Cortex model names, limits, categories
```

## Data layers

`RAW` → `STAGING` → `ANALYTICS`

- **RAW**: untouched source JSON, exactly as received. Never transform, filter, or type-cast here.
- **STAGING**: typed, cleaned, deduplicated tables derived from RAW.
- **ANALYTICS**: enriched tables and business-facing views built on STAGING.

## Conventions

- **Sources are plugins.** Every source implements the common `Extractor` interface. Adding a new source must not require any change to the pipeline core — if it does, the core is wrong, fix the core.
- **Schema changes are migrations.** All DDL lives in `migrations/` as `V<NNN>__<name>.sql`, numbered sequentially, applied exactly once, and tracked in `META.SCHEMA_MIGRATIONS`. Never edit an applied migration; add a new one.
- **Transforms are idempotent.** Everything in `transforms/` must be safe to rerun (MERGE / CREATE OR REPLACE, not blind INSERT). One model per file, declarative SQL only — no procedural logic, no cursors, no stored-procedure control flow. These will be ported to dbt.
- **Config, not constants.** Repo lists, Cortex model names, and limits (batch sizes, lookback windows, row caps) live in `config.yaml`. Never hardcode them.
- **App reads through `app/queries.py` only.** Streamlit pages call functions in `queries.py`; no raw SQL strings in pages.
- **Secrets come from environment variables only.** Key-pair auth (`SNOWFLAKE_PRIVATE_KEY_FILE`); no credentials in code, config.yaml, or committed files. `rsa_key.p8` stays in `.gitignore`.

## Before finishing a change

- New source? Confirm it's a plugin and the core is untouched.
- New table/column? There's a migration for it.
- New transform? Reran it twice with identical results.
- New knob or model name? It's in `config.yaml`.
- New page query? It's a function in `app/queries.py`.
