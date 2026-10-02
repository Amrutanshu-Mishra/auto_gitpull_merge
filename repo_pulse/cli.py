"""repo-pulse CLI: migrate | ingest [--source] | transform | enrich | all.

Exit codes: 0 success, 1 pipeline/config error, 2 bad arguments.
"""

from __future__ import annotations

import argparse
import logging
import sys

from repo_pulse.check import check
from repo_pulse.config import load_config
from repo_pulse.db import get_connection
from repo_pulse.enrich import enrich
from repo_pulse.migrate import migrate
from repo_pulse.pipeline import run_ingest
from repo_pulse.sources.base import load_plugins
from repo_pulse.transform import run_transforms

log = logging.getLogger("repo_pulse")

STEPS = {
    "all": ["migrate", "ingest", "transform", "enrich"],
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="repo-pulse")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="verify env, key file, Snowflake connection and Cortex access")
    sub.add_parser("migrate", help="apply pending migrations")
    p_ingest = sub.add_parser("ingest", help="extract sources into RAW")
    p_ingest.add_argument("--source", help="run a single source plugin")
    sub.add_parser("transform", help="run transforms/ (RAW -> STAGING -> ANALYTICS)")
    sub.add_parser("enrich", help="run Cortex enrichment")
    sub.add_parser("all", help="migrate -> ingest -> transform -> enrich; stops at the first failure")
    return parser


def run(args: argparse.Namespace) -> None:
    steps = STEPS.get(args.command, [args.command])
    config = load_config()
    if args.command == "check":
        if not check(config):
            raise SystemExit("some checks failed (see SETUP.md)")
        return
    conn = get_connection()
    try:
        for step in steps:
            log.info("==> %s", step)
            if step == "migrate":
                migrate(conn)
            elif step == "ingest":
                source = getattr(args, "source", None)
                for name in [source] if source else sorted(load_plugins()):
                    run_ingest(conn, config, name)
            elif step == "transform":
                run_transforms(conn)
            elif step == "enrich":
                enrich(conn, config)
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    try:
        run(args)
    except SystemExit as exc:  # our own loud failures carry a message
        if exc.code not in (None, 0):
            log.error("%s", exc.code)
            return 1
    except KeyboardInterrupt:
        log.error("interrupted")
        return 130
    except Exception:
        log.exception("%s failed", args.command)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
