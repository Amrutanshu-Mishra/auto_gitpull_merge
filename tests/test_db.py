from pathlib import Path

from repo_pulse.db import split_statements


def test_semicolon_inside_comment_does_not_split():
    sql = "CREATE TABLE t (\n  a INT, -- note; still a comment\n  b INT\n);\nCREATE TABLE u (c INT);"
    stmts = split_statements(sql)
    assert len(stmts) == 2
    assert stmts[0].startswith("CREATE TABLE t") and "b INT" in stmts[0]


def test_all_migrations_split_cleanly():
    for path in sorted(Path("migrations").glob("V*.sql")):
        for stmt in split_statements(path.read_text(encoding="utf-8")):
            assert stmt.upper().startswith(("CREATE", "USE", "ALTER", "INSERT")), (path.name, stmt[:40])
