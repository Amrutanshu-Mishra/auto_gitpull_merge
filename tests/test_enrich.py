from repo_pulse.config import load_config
from repo_pulse.enrich import BATCH_MERGE_SQL, model_version, run_batch


class FakeCursor:
    def __init__(self, result):
        self.result = result
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchone(self):
        return self.result


class FakeConn:
    def __init__(self, result):
        self.cur = FakeCursor(result)

    def cursor(self):
        return self.cur


def test_model_version_records_embed_model():
    cfg = load_config()
    mv = model_version(cfg)
    assert f"embed=EMBED_TEXT_768:{cfg.cortex.embed_model}" in mv
    assert "classify=CLASSIFY_TEXT" in mv


def test_run_batch_sums_inserted_and_updated():
    conn = FakeConn((7, 3))
    assert run_batch(conn, {"batch_size": 10}) == 10
    sql, params = conn.cur.executed[0]
    assert sql is BATCH_MERGE_SQL
    assert params["batch_size"] == 10


def test_batch_sql_uses_config_driven_inputs_only():
    for placeholder in ("%(batch_size)s", "%(categories)s", "%(embed_model)s", "%(model_version)s"):
        assert placeholder in BATCH_MERGE_SQL
    assert "snowflake-arctic" not in BATCH_MERGE_SQL  # no hardcoded model names
