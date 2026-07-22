#!/usr/bin/env python3
"""Prepare or independently verify a dormant Warehouse W3 dry root."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Warehouse W3 source/dry-root acceptance (formal run locked)."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare", help="build a dry manifest only")
    prepare.add_argument("--output-root", required=True, type=Path)
    prepare.add_argument("--source-commit")
    verify = subparsers.add_parser("verify-dry-root")
    verify.add_argument("--root", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    from scion.problems.warehouse_delivery.w3_fixed_arm import (
        prepare_dry_root,
        verify_dry_root,
    )

    if args.command == "prepare":
        result = prepare_dry_root(
            args.output_root, source_commit=args.source_commit
        )
    else:
        result = verify_dry_root(args.root)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
