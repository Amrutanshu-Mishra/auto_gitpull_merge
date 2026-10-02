# repo-pulse setup

Everything needed to go from a fresh machine to a running app. Work top to bottom; each
section ends with what you should have in hand. Budget about 45 minutes, most of it waiting
for accounts.

## 1. Accounts

- [ ] **Snowflake trial** — <https://signup.snowflake.com>. Choose **Enterprise** edition and
      one of **AWS US West (Oregon)** or **AWS US East (N. Virginia)**; those regions have the
      full Cortex model catalogue, which avoids cross-region routing for `COMPLETE` and the
      embedding models. The trial gives roughly **$400 of credits for 30 days** — far more than
      this project uses. Note the account identifier from the activation email; you will need
      it in section 5.
- [ ] **GitHub token** — GitHub → *Settings → Developer settings → Personal access tokens →
      Fine-grained tokens → Generate new token*. Repository access: **Public repositories
      (read-only)**. No other permissions are needed. Copy it once; GitHub will not show it
      again. Unauthenticated calls are limited to **60 requests/hour**; a token raises that to
      **5,000/hour**, which matters as soon as you track a repo with more than a few pages of
      issues (100 issues per page).
- [ ] **Claude Code** — used to develop the project. Either a Claude Pro/Max plan or an
      Anthropic API key. Not needed to *run* the pipeline.

*You now have: a Snowflake account identifier + login, a GitHub token.*

## 2. Local software

- [ ] **Python 3.10 – 3.12**. Check with `python --version`. The Snowflake connector (and its
      `pyarrow` dependency) typically lags the newest Python release by a few months, so avoid
      a Python that came out in the last quarter. The project is developed on 3.12.
- [ ] **Git** and **Claude Code** (`npm install -g @anthropic-ai/claude-code`, or the desktop app).
- [ ] **OpenSSL** for section 4. It ships with macOS, Linux and Git for Windows (use *Git Bash*
      on Windows).
- [ ] **Virtual environment + dependencies**:

  ```bash
  git clone <your fork> repo-pulse && cd repo-pulse
  python -m venv .venv
  source .venv/bin/activate          # Windows: .venv\Scripts\activate
  pip install -r requirements.txt
  ```

- [ ] *Optional:* the [Snowflake CLI](https://docs.snowflake.com/en/developer-guide/snowflake-cli/index)
      (`pip install snowflake-cli`) or SnowSQL, for running ad-hoc SQL from the terminal.
      Everything below can also be done in a Snowsight worksheet.

*You now have: an activated `.venv` with `snowflake-connector-python`, `streamlit`, etc.*

## 3. One-time Snowflake setup

Open Snowsight → *Projects → Worksheets → + SQL Worksheet*, switch the worksheet role to
**ACCOUNTADMIN** (top-right), and run the whole block:

```sql
-- Let Cortex route to another region if a model is not hosted in yours.
ALTER ACCOUNT SET CORTEX_ENABLED_CROSS_REGION = 'ANY_REGION';

-- A dedicated role that owns everything repo-pulse creates.
CREATE ROLE IF NOT EXISTS REPO_PULSE_ROLE;
GRANT CREATE WAREHOUSE, CREATE DATABASE ON ACCOUNT TO ROLE REPO_PULSE_ROLE;

-- Required to call SNOWFLAKE.CORTEX.* functions.
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE REPO_PULSE_ROLE;

-- A service user for the pipeline (TYPE = SERVICE: no password/MFA, key-pair only).
CREATE USER IF NOT EXISTS REPO_PULSE_USER
    DEFAULT_ROLE = REPO_PULSE_ROLE
    TYPE = SERVICE;
GRANT ROLE REPO_PULSE_ROLE TO USER REPO_PULSE_USER;

-- Lets SYSADMIN (and therefore ACCOUNTADMIN) see and manage what the role creates.
GRANT ROLE REPO_PULSE_ROLE TO ROLE SYSADMIN;
```

The warehouse and database are **not** created here — migration `V001__foundation.sql`
creates `REPO_PULSE_WH` and `REPO_PULSE` on the first `make migrate`, which is why the role
needs `CREATE WAREHOUSE` and `CREATE DATABASE`.

*You now have: `REPO_PULSE_ROLE`, `REPO_PULSE_USER`, Cortex enabled.*

## 4. Key-pair authentication

Snowflake is phasing out password-only logins (service users cannot use them at all), so the
pipeline authenticates with an RSA key pair. [`repo_pulse/db.py`](repo_pulse/db.py) passes
`private_key_file` to the connector; there is no password path.

- [ ] Generate an unencrypted PKCS#8 private key and its public key **in the project root**:

  ```bash
  openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out rsa_key.p8 -nocrypt
  openssl rsa -in rsa_key.p8 -pubout -out rsa_key.pub
  ```

- [ ] Register the public key on the user. Open `rsa_key.pub`, copy **only the body** — drop the
      `-----BEGIN PUBLIC KEY-----` / `-----END PUBLIC KEY-----` lines and join the remaining
      lines into one string — and run as ACCOUNTADMIN:

  ```sql
  ALTER USER REPO_PULSE_USER SET RSA_PUBLIC_KEY = 'MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...';
  ```

  One-liner to print the body:
  `grep -v '^-----' rsa_key.pub | tr -d '\n'`

- [ ] **Verify the key is ignored by git**: `rsa_key.p8`, `rsa_key.pub` and `*.p8` are listed in
      [`.gitignore`](.gitignore). Run `git status` — the key files must not appear. If you keep
      the key elsewhere, point `SNOWFLAKE_PRIVATE_KEY_FILE` at it (section 5).

*You now have: `rsa_key.p8` locally, its public half on `REPO_PULSE_USER`.*

## 5. Environment variables

Copy the template and fill it in. Secrets live **only** here — never in `config.yaml` or code.

```bash
cp .env.example .env
```

`.env` (identical to [`.env.example`](.env.example)):

```dotenv
# Snowflake account identifier, e.g. ABCDEFG-XY12345 (Snowsight: account menu -> Account -> copy identifier)
SNOWFLAKE_ACCOUNT=
SNOWFLAKE_USER=REPO_PULSE_USER
# Path to the PKCS#8 private key generated in SETUP.md section 4 (keep it out of git)
SNOWFLAKE_PRIVATE_KEY_FILE=rsa_key.p8
SNOWFLAKE_ROLE=REPO_PULSE_ROLE
# Created by migration V001; db.py connects without them and switches once they exist
SNOWFLAKE_WAREHOUSE=REPO_PULSE_WH
SNOWFLAKE_DATABASE=REPO_PULSE
# Fine-grained PAT with public repositories read-only access
GITHUB_TOKEN=
```

| Variable | Where it comes from |
|---|---|
| `SNOWFLAKE_ACCOUNT` | Snowsight, bottom-left account menu → hover the account → **Account → View account details**, or the *copy account identifier* icon. Use the `<orgname>-<account_name>` form (e.g. `ABCDEFG-XY12345`), **not** the full URL and not the legacy locator. |
| `SNOWFLAKE_USER` / `SNOWFLAKE_ROLE` | From section 3. |
| `SNOWFLAKE_PRIVATE_KEY_FILE` | Path to `rsa_key.p8` from section 4; relative paths resolve from where you run `make`. |
| `SNOWFLAKE_WAREHOUSE` / `SNOWFLAKE_DATABASE` | Names that `V001` will create. `db.py` opens the session **without** them, then runs `USE WAREHOUSE` / `USE DATABASE` only if they already exist, so the first `make migrate` on an empty account succeeds. |
| `GITHUB_TOKEN` | From section 1. |

*You now have: a filled `.env`.*

## 6. `config.yaml` — repos and Cortex models

[`config.yaml`](config.yaml) holds everything that is not a secret: the repos to track, per-source
row limits, the Cortex models and the issue categories. The model settings shipped are:

```yaml
cortex:
  embed_model: snowflake-arctic-embed-m-v1.5   # 768 dimensions
  complete_model: mistral-large2
```

> **Dimension warning.** `ANALYTICS.ISSUES_ENRICHED.EMBEDDING` is declared `VECTOR(FLOAT, 768)`
> and the pipeline calls `EMBED_TEXT_768`. `embed_model` must therefore be a **768-dimension**
> model (`snowflake-arctic-embed-m-v1.5`, `snowflake-arctic-embed-m`, `e5-base-v2`).
> A 1024-dimension model (`snowflake-arctic-embed-l-v2.0`, `nv-embed-qa-4`) would need
> `EMBED_TEXT_1024` **and** a new migration altering the column — do not just change the name.

For a first run, keep `repos` to one or two entries and set `limits.github_issues` to ~100.

*You now have: `config.yaml` with the right models and a small repo list.*

## 7. Sanity checks

First the automated one. It reads `.env`, checks the key file, opens a connection and runs the
three Cortex calls, printing one PASS/FAIL line each and exiting non-zero on any failure:

```bash
make check
```

Before `make migrate` the *warehouse + database* line will fail with "run `make migrate` first"
and the Cortex lines will fail because there is no warehouse to run them on — that is expected.
Run `make migrate`, then `make check` again; everything should pass.

The same checks by hand, in a Snowsight worksheet **as `REPO_PULSE_ROLE`** with warehouse
`REPO_PULSE_WH` selected (after `make migrate`):

```sql
SELECT SNOWFLAKE.CORTEX.SENTIMENT('this library is great');                        -- ≈ 0.7
SELECT SNOWFLAKE.CORTEX.COMPLETE('mistral-large2', 'say hi');                       -- some text
SELECT SNOWFLAKE.CORTEX.EMBED_TEXT_768('snowflake-arctic-embed-m-v1.5', 'test');    -- 768 floats
```

### Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Unknown function SNOWFLAKE.CORTEX.…` or `model … is not available in region` | Cross-region inference not enabled, or region without the model | Re-run `ALTER ACCOUNT SET CORTEX_ENABLED_CROSS_REGION = 'ANY_REGION'` as ACCOUNTADMIN (section 3); confirm the account is in AWS US West/East |
| `Insufficient privileges to operate on …` on a Cortex call | Role lacks the Cortex database role | `GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE REPO_PULSE_ROLE;` and reconnect |
| `JWT token is invalid` / `Incorrect username or password` / `250001` | Public key not registered, registered with header/footer lines, or wrong account identifier | Re-run the `ALTER USER … SET RSA_PUBLIC_KEY` with the body only; check `SNOWFLAKE_ACCOUNT` is `ORG-ACCOUNT`, not a URL; `DESC USER REPO_PULSE_USER` shows `RSA_PUBLIC_KEY_FP` when a key is set |
| `SNOWFLAKE_PRIVATE_KEY_FILE not found` | Path in `.env` is wrong relative to the working directory | Use an absolute path or run `make` from the project root |
| `Object does not exist` for `REPO_PULSE_WH` / `REPO_PULSE` | Migrations not applied yet | `make migrate` |
| `Insufficient privileges` on `CREATE WAREHOUSE` / `CREATE DATABASE` | Account-level grants missing | The two `GRANT … ON ACCOUNT` lines in section 3 |
| GitHub `403` during `make ingest` | `GITHUB_TOKEN` missing/invalid, or the 60/hour anonymous limit hit | Set the token in `.env`; if the response has `X-RateLimit-Remaining: 0` the extractor sleeps until reset automatically — a bare 403 means the token is bad |
| GitHub `404` for a repo | Typo in `config.yaml`, or a private repo with a public-only token | Use `owner/name`; grant the token access to that repo |
| `make check` passes but `make enrich` is slow | Every batch is a Cortex call per row | Lower `limits.github_issues` and `enrich.batch_size` while testing |

## 8. Cost control

- The warehouse is **XSMALL** with **`AUTO_SUSPEND = 60`** seconds and auto-resume — it costs
  nothing while idle and about 1 credit per running hour. A full `make all` on a few thousand
  issues is a few minutes of runtime.
- **Cortex is billed per million tokens** and is the only cost that scales with data. Enrichment
  makes 3–4 calls per issue, **once**; an issue is only re-enriched when GitHub reports it
  changed. Start with **1–2 repos and ~100 issues** (`limits.github_issues: 100`) until you
  are happy with the output, then raise the limit.
- The app makes one `EMBED_TEXT_768` call per *Similar Issues* search and one `COMPLETE` call per
  *Ask* question, cached for 10 minutes.
- Watch spend in Snowsight → **Admin → Cost Management** (Consumption tab, filter by
  `REPO_PULSE_WH`; Cortex usage appears under *AI Services*). Trial credits do not roll over,
  so there is no reason to hoard them, but a runaway loop would show up here first.

## 9. Run

```bash
make migrate      # creates warehouse, database, schemas, tables; records migrations in META
make ingest       # GitHub -> RAW.GITHUB_EVENTS_RAW, resuming from per-repo watermarks
make transform    # RAW -> STAGING.STG_ISSUES -> ANALYTICS.REPO_HEALTH (views)
make enrich       # Cortex sentiment / category / summary / embedding -> ANALYTICS.ISSUES_ENRICHED
# or all four, stopping at the first failure:
make all

streamlit run app/streamlit_app.py     # or: make app
```

Open <http://localhost:8501>. *Overview* shows repo health, *Similar Issues* does vector search,
*Ask* answers questions over recent issues. All four pipeline steps are safe to rerun.

Progress is logged to `META.PIPELINE_RUNS`; watermarks to `META.INGEST_WATERMARKS`:

```sql
SELECT * FROM REPO_PULSE.META.PIPELINE_RUNS ORDER BY STARTED_AT DESC LIMIT 20;
```
