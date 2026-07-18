#!/usr/bin/env python3
"""Prepare, verify, run, or close the fixed CVRP F1 ancestry matrix."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PACKAGE_ROOT = _REPO_ROOT / "scion"
if str(_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_ROOT))

from scion.problems.cvrp.evidence.f1_ancestry import (  # noqa: E402
    CvrpF1Error,
    close_f1_root,
    prepare_f1_root,
    run_f1_root,
    verify_f1_root,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--output-root", required=True)
    prepare.add_argument("--python", required=True)
    mode = prepare.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--formal", action="store_true")

    for name in ("verify", "run", "close"):
        command = subparsers.add_parser(name)
        command.add_argument("--root", required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            plan = prepare_f1_root(
                repo_root=_REPO_ROOT,
                output_root=args.output_root,
                python=args.python,
                dry_run=bool(args.dry_run),
            )
            payload = {
                "status": "prepared",
                "dry_run": bool(args.dry_run),
                "root": str(plan.root),
                "manifest_sha256": plan.manifest_sha256,
                "jobs": len(plan.manifest["jobs"]),
            }
        elif args.command == "verify":
            plan = verify_f1_root(args.root)
            payload = {
                "status": "verified",
                "root": str(plan.root),
                "manifest_sha256": plan.manifest_sha256,
                "jobs": len(plan.manifest["jobs"]),
            }
        elif args.command == "run":
            run_f1_root(args.root)
            payload = {"status": "terminal", "root": str(Path(args.root).resolve())}
        else:
            payload = close_f1_root(args.root)
    except (CvrpF1Error, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
