from repo_pulse.config import load_config
from repo_pulse.sources.base import load_plugins


def test_config_loads():
    cfg = load_config()
    assert cfg.repos
    assert cfg.cortex.embed_model and cfg.cortex.complete_model
    assert cfg.categories


def test_github_issues_is_discovered():
    assert "github_issues" in load_plugins()
