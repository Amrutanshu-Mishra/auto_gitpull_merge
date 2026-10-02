from datetime import datetime, timezone

import pytest
import requests

from repo_pulse.config import Config, CortexModels
from repo_pulse.sources.github_issues import GitHubIssuesExtractor


def make_config(limit: int = 100) -> Config:
    return Config(
        repos=["acme/widgets"],
        limits={"github_issues": limit},
        cortex=CortexModels("m", "m"),
        categories=["bug"],
    )


def issue(number: int, updated: str, pr: bool = False) -> dict:
    d = {"number": number, "title": f"issue {number}", "updated_at": updated, "labels": []}
    if pr:
        d["pull_request"] = {"url": "..."}
    return d


class FakeResponse:
    def __init__(self, status=200, json=None, headers=None, next_url=None):
        self.status_code = status
        self._json = json or []
        self.headers = headers or {}
        self.links = {"next": {"url": next_url}} if next_url else {}

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.headers = {}

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        return self.responses.pop(0)


def extractor(responses, limit=100, now=lambda: 1000.0):
    session = FakeSession(responses)
    slept = []
    ex = GitHubIssuesExtractor(make_config(limit), session=session, sleep=slept.append, now=now)
    return ex, session, slept


def test_paginates_skips_prs_and_passes_since():
    page1 = FakeResponse(
        json=[issue(1, "2024-01-01T00:00:00Z"), issue(2, "2024-01-02T00:00:00Z", pr=True)],
        next_url="https://api.github.com/repos/acme/widgets/issues?page=2",
    )
    page2 = FakeResponse(json=[issue(3, "2024-01-03T00:00:00Z")])
    ex, session, _ = extractor([page1, page2])

    since = datetime(2023, 12, 31, tzinfo=timezone.utc)
    records = list(ex.extract("acme/widgets", since))

    assert [r["entity_id"] for r in records] == ["1", "3"]
    assert records[0]["updated_at"] == datetime(2024, 1, 1, tzinfo=timezone.utc)
    assert records[1]["payload"] == issue(3, "2024-01-03T00:00:00Z")  # untouched
    url, params = session.calls[0]
    assert url.endswith("/repos/acme/widgets/issues")
    assert params["since"] == "2023-12-31T00:00:00Z"
    assert params["state"] == "all" and params["sort"] == "updated"
    assert session.calls[1] == (page1.links["next"]["url"], None)


def test_respects_limit():
    page1 = FakeResponse(
        json=[issue(i, "2024-01-01T00:00:00Z") for i in range(1, 4)], next_url="https://x/page2"
    )
    ex, session, _ = extractor([page1], limit=2)
    assert [r["entity_id"] for r in ex.extract("acme/widgets", None)] == ["1", "2"]
    assert len(session.calls) == 1


def test_rate_limit_sleeps_until_reset_then_retries():
    limited = FakeResponse(
        status=403, headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1042"}
    )
    ok = FakeResponse(json=[issue(1, "2024-01-01T00:00:00Z")])
    ex, session, slept = extractor([limited, ok], now=lambda: 1000.0)
    assert len(list(ex.extract("acme/widgets", None))) == 1
    assert slept == [42.0]
    assert len(session.calls) == 2


def test_retry_after_honoured_on_429():
    ex, _, slept = extractor(
        [FakeResponse(status=429, headers={"Retry-After": "7"}), FakeResponse(json=[])]
    )
    assert list(ex.extract("acme/widgets", None)) == []
    assert slept == [7.0]


def test_plain_403_raises():
    ex, _, slept = extractor([FakeResponse(status=403)])
    with pytest.raises(requests.HTTPError):
        list(ex.extract("acme/widgets", None))
    assert slept == []
