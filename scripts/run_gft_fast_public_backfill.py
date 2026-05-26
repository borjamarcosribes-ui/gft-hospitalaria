#!/usr/bin/env python3
from __future__ import annotations

from scripts import run_gft_cache_backfill as cache_backfill


def main(argv=None):
    args = list(argv or [])
    if "--scope" not in args:
        args = ["--scope", "published", *args]
    return cache_backfill.main(args)


if __name__ == "__main__":
    raise SystemExit(main())
