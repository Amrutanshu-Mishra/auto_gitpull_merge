"""GitHub issues via REST: GET /repos/{owner}/{repo}/issues."""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Callable, Iterator

import requests

from repo_pulse.config import Config
from repo_pulse.sources.base import Extractor, Record

API = "https://api.github.com"
PER_PAGE = 100
MAX_RATE_LIMIT_WAITS = 5


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class GitHubIssuesExtractor(Extractor):
    name = "github_issues"

    def __init__(
        self,
        config: Config,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], float] = time.time,
    ):
        super().__init__(config)
        self.sleep = sleep
        self.now = now
        self.session = session or requests.Session()
        self.session.headers.update(
            {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        )
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    def extract(self, repo: str, since: datetime | None) -> Iterator[Record]:
        params = {"state": "all", "sort": "updated", "direction": "asc", "per_page": PER_PAGE}
        if since is not None:
            params["since"] = since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        url: str | None = f"{API}/repos/{repo}/issues"
        yielded = 0
        while url:
            resp = self._get(url, params)
            params = None  # the Link header's next URL already carries the query string
            for issue in resp.json():
                if "pull_request" in issue:  # the issues endpoint also returns PRs
                    continue
                yield Record(
                    entity_id=str(issue["number"]),
                    updated_at=_parse_ts(issue["updated_at"]),
                    payload=issue,
                )
                yielded += 1
                if yielded >= self.limit:
                    return
            url = resp.links.get("next", {}).get("url")

    def _get(self, url: str, params: dict | None) -> requests.Response:
        for _ in range(MAX_RATE_LIMIT_WAITS):
            resp = self.session.get(url, params=params, timeout=30)
            if resp.status_code not in (403, 429):
                resp.raise_for_status()
                return resp
            wait = self._rate_limit_wait(resp)
            if wait is None:
                resp.raise_for_status()
            self.sleep(wait)
        raise RuntimeError(f"Gave up after {MAX_RATE_LIMIT_WAITS} rate-limit waits on {url}")

    def _rate_limit_wait(self, resp: requests.Response) -> float | None:
        """Seconds to sleep if this 403/429 is a rate limit, else None."""
        if "Retry-After" in resp.headers:
            return max(float(resp.headers["Retry-After"]), 1.0)
        if resp.headers.get("X-RateLimit-Remaining") == "0" and "X-RateLimit-Reset" in resp.headers:
            return max(float(resp.headers["X-RateLimit-Reset"]) - self.now(), 1.0)
        return None
