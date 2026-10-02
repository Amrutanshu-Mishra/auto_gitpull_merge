import repo_pulse.cli as cli


def test_all_expands_to_ordered_steps():
    assert cli.STEPS["all"] == ["migrate", "ingest", "transform", "enrich"]


def test_missing_credentials_exit_1(monkeypatch, caplog):
    for k in ("SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PRIVATE_KEY_FILE"):
        monkeypatch.delenv(k, raising=False)
    assert cli.main(["migrate"]) == 1
    assert "SNOWFLAKE_" in caplog.text


def test_bad_subcommand_exit_2():
    try:
        cli.main(["nope"])
    except SystemExit as e:
        assert e.code == 2
    else:
        raise AssertionError("argparse should exit 2")


def test_check_reports_missing_env(monkeypatch, capsys):
    from repo_pulse.check import REQUIRED_ENV, check
    from repo_pulse.config import load_config

    for k in REQUIRED_ENV:
        monkeypatch.delenv(k, raising=False)
    assert check(load_config()) is False
    out = capsys.readouterr().out
    assert out.startswith("[FAIL] env vars set") and "GITHUB_TOKEN" in out


def test_check_reports_missing_key_file(monkeypatch, capsys, tmp_path):
    from repo_pulse.check import REQUIRED_ENV, check
    from repo_pulse.config import load_config

    for k in REQUIRED_ENV:
        monkeypatch.setenv(k, "x")
    monkeypatch.setenv("SNOWFLAKE_PRIVATE_KEY_FILE", str(tmp_path / "nope.p8"))
    assert check(load_config()) is False
    out = capsys.readouterr().out
    assert "[PASS] env vars set" in out and "[FAIL] private key file exists" in out
