"""CLI for replay/aggregation actions."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone

import structlog

from replay.aggregate import build_zone_stats
from replay.replay import rewind_group

log = structlog.get_logger("replay.main")


def _aggregate_cmd(_: argparse.Namespace) -> None:
    out = build_zone_stats()
    log.info("aggregate.complete", path=str(out))


def _rewind_cmd(args: argparse.Namespace) -> None:
    if args.hours_ago is not None:
        not_before = datetime.now(timezone.utc) - timedelta(hours=args.hours_ago)
    else:
        not_before = datetime.fromisoformat(args.not_before)
    new_offsets = asyncio.run(
        rewind_group(topic=args.topic, group_id=args.group, not_before=not_before)
    )
    log.info("rewind.complete", new_offsets=new_offsets)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_agg = sub.add_parser("aggregate", help="build zone_stats.parquet")
    p_agg.set_defaults(func=_aggregate_cmd)

    p_rew = sub.add_parser("rewind", help="rewind a consumer group to a timestamp")
    p_rew.add_argument("--topic", required=True)
    p_rew.add_argument("--group", required=True)
    p_rew.add_argument("--hours-ago", type=float, default=None)
    p_rew.add_argument("--not-before", type=str, default=None, help="ISO 8601 UTC")
    p_rew.set_defaults(func=_rewind_cmd)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
