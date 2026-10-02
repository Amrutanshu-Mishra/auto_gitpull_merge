import pandas as pd

from app import queries


class ConnectorCursor:
    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params):
        self.calls.append((sql, params))

    def fetch_pandas_all(self):
        return pd.DataFrame({"REPO": ["a/b"]})


class ConnectorConn:
    def __init__(self):
        self.cur = ConnectorCursor()

    def cursor(self):
        return self.cur


class SnowparkResult:
    def __init__(self, params):
        self.params = params

    def to_pandas(self):
        return pd.DataFrame({"REPO": ["a/b"], "PARAMS": [str(self.params)]})


class SnowparkSession:
    def __init__(self):
        self.calls = []

    def sql(self, sql, params=None):
        self.calls.append((sql, params))
        return SnowparkResult(params)


def test_connector_path_rewrites_placeholders():
    conn = ConnectorConn()
    df = queries.run(conn, "SELECT ? AS a, ? AS b", (1, 2))
    sql, params = conn.cur.calls[0]
    assert sql == "SELECT %s AS a, %s AS b" and params == (1, 2)
    assert df["REPO"].tolist() == ["a/b"]


def test_snowpark_path_passes_qmark_params():
    sess = SnowparkSession()
    queries.run(sess, "SELECT ? AS a", (7,))
    assert sess.calls == [("SELECT ? AS a", [7])]


def test_no_literal_question_marks_in_query_strings():
    # `?` must only ever be a bind placeholder, since run() rewrites them for the connector
    import inspect, re

    src = inspect.getsource(queries)
    for sql in re.findall(r'"""(.*?)"""', src, re.S):
        assert "'?" not in sql and "?'" not in sql
