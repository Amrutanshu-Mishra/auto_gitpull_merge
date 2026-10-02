from pathlib import Path

from repo_pulse.transform import TRANSFORMS_DIR, discover_transforms, read_model


def test_repo_transforms_discovered_in_order():
    paths = discover_transforms(TRANSFORMS_DIR)
    assert [p.name for p in paths] == ["stg_issues.sql", "analytics_repo_health.sql"]
    assert "CREATE OR REPLACE VIEW STAGING.STG_ISSUES" in read_model(paths[0])


def test_trailing_semicolon_stripped(tmp_path: Path):
    f = tmp_path / "ok.sql"
    f.write_text("-- a; comment\nCREATE OR REPLACE VIEW a AS SELECT ';' AS x;\n")
    assert read_model(f).endswith("AS x")


def test_layer_then_filename_order(tmp_path: Path):
    for name in ("mart_b.sql", "analytics_a.sql", "stg_z.sql", "stg_a.sql", "int_c.sql"):
        (tmp_path / name).write_text("select 1")
    assert [p.name for p in discover_transforms(tmp_path)] == [
        "stg_a.sql", "stg_z.sql", "int_c.sql", "analytics_a.sql", "mart_b.sql"
    ]
