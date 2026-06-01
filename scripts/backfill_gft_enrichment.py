#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.database import SessionLocal
from app.services.gft_backfill_service import DEFAULT_SLEEP_SECONDS, MODE_CHOICES, SOURCE_CHOICES, run_backfill


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill seguro y reanudable CIMA/BIFIMED/clinical para medicamentos publicados GFT.")
    parser.add_argument("--source", choices=sorted(SOURCE_CHOICES), default="all")
    parser.add_argument("--mode", choices=sorted(MODE_CHOICES), default="dry-run")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--cn")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--checkpoint-path", type=Path)
    parser.add_argument("--log-path", type=Path)
    parser.add_argument("--sleep", type=float, default=DEFAULT_SLEEP_SECONDS)
    parser.add_argument("--only-missing", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--stop-on-error", action="store_true")
    parser.add_argument("--audit-before", action="store_true")
    parser.add_argument("--audit-after", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    with SessionLocal() as db:
        result = run_backfill(
            db,
            source=args.source,
            mode=args.mode,
            limit=args.limit,
            offset=args.offset,
            cn=args.cn,
            resume=args.resume,
            checkpoint_path=args.checkpoint_path,
            log_path=args.log_path,
            sleep_seconds=args.sleep,
            only_missing=args.only_missing,
            force=args.force,
            stop_on_error=args.stop_on_error,
            audit_before=args.audit_before,
            audit_after=args.audit_after,
        )
    printable = {k: v for k, v in result.items() if k != "checkpoint"}
    printable["processed"] = result["checkpoint"].get("processed", 0)
    printable["succeeded"] = result["checkpoint"].get("succeeded", 0)
    printable["failed"] = result["checkpoint"].get("failed", 0)
    printable["skipped"] = result["checkpoint"].get("skipped", 0)
    print(json.dumps(printable, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
