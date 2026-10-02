from pathlib import Path

import pytest

from repo_pulse.migrate import MIGRATIONS_DIR, _verify, discover_migrations


def test_repo_migrations_are_well_formed():
    migs = discover_migrations(MIGRATIONS_DIR)
    assert [m.version for m in migs] == [1, 2, 3, 4]
    assert migs[0].path.name == "V001__foundation.sql"


def test_bad_filename_rejected(tmp_path: Path):
    (tmp_path / "V1_oops.sql").write_text("select 1;")
    with pytest.raises(SystemExit, match="Bad migration filename"):
        discover_migrations(tmp_path)


def test_duplicate_version_rejected(tmp_path: Path):
    (tmp_path / "V001__a.sql").write_text("select 1;")
    (tmp_path / "V001__b.sql").write_text("select 2;")
    with pytest.raises(SystemExit, match="Duplicate migration version"):
        discover_migrations(tmp_path)


def test_checksum_is_line_ending_agnostic(tmp_path: Path):
    (tmp_path / "V001__a.sql").write_bytes(b"select 1;\nselect 2;\n")
    lf = discover_migrations(tmp_path)[0].checksum
    (tmp_path / "V001__a.sql").write_bytes(b"select 1;\r\nselect 2;\r\n")
    assert discover_migrations(tmp_path)[0].checksum == lf


def test_modified_applied_migration_fails_loudly(tmp_path: Path):
    (tmp_path / "V001__a.sql").write_text("select 1;")
    mig = discover_migrations(tmp_path)[0]
    _verify([mig], {1: ("V001__a.sql", mig.checksum)})  # unchanged: ok
    with pytest.raises(SystemExit, match="checksum changed"):
        _verify([mig], {1: ("V001__a.sql", "deadbeef")})
