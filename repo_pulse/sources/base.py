"""Common Extractor interface and plugin registry.

A source is a module in repo_pulse.sources that subclasses Extractor and sets
`name`. Subclassing registers it; the pipeline core never needs to change.
"""

from __future__ import annotations

import importlib
import pkgutil
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, ClassVar, Iterator, TypedDict

from repo_pulse.config import Config


class Record(TypedDict):
    entity_id: str          # source-native id: issue number, PR number, sha, ...
    updated_at: datetime    # timezone-aware; drives the ingest watermark
    payload: dict[str, Any]  # the full API object, untouched


REGISTRY: dict[str, type["Extractor"]] = {}


class Extractor(ABC):
    """`name` is the SOURCE column value and the config.limits key."""

    name: ClassVar[str] = ""

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.name:
            if cls.name in REGISTRY and REGISTRY[cls.name] is not cls:
                raise RuntimeError(f"Duplicate extractor name {cls.name!r}")
            REGISTRY[cls.name] = cls

    def __init__(self, config: Config):
        self.config = config
        self.limit = config.limit(self.name)

    @abstractmethod
    def extract(self, repo: str, since: datetime | None) -> Iterator[Record]:
        """Yield records for `repo` updated at or after `since` (None = everything)."""


def load_plugins() -> dict[str, type[Extractor]]:
    """Import every module in repo_pulse.sources so their subclasses register; return the registry."""
    import repo_pulse.sources as pkg

    for mod in pkgutil.iter_modules(pkg.__path__):
        importlib.import_module(f"{pkg.__name__}.{mod.name}")
    return REGISTRY


def get_extractor(name: str) -> type[Extractor]:
    registry = load_plugins()
    if name not in registry:
        raise SystemExit(f"Unknown source {name!r}. Available: {', '.join(sorted(registry))}")
    return registry[name]
