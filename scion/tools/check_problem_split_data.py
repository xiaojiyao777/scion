#!/usr/bin/env python3
"""Verify that every case in a split resolves through one explicit data root."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCION_PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(SCION_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(SCION_PROJECT_DIR))

from scion.problems.cvrp.formal_data_identity import build_formal_data_identity


FAILURE_EXIT = 64


def _resolve_spec_path(scion_dir: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else scion_dir / path


def build_report(*, problem: str, split: str, data_root: Path) -> dict[str, object]:
    scion_dir = Path(__file__).resolve().parents[1]
    problem_path = _resolve_spec_path(scion_dir, problem)
    split_path = _resolve_spec_path(scion_dir, split)
    return build_formal_data_identity(
        problem_path=problem_path,
        split_path=split_path,
        data_root=data_root,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--problem", required=True)
    parser.add_argument("--split", required=True)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--expected-identity-sha256", default="")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    report = build_report(
        problem=args.problem,
        split=args.split,
        data_root=args.data_root,
    )
    expected = str(args.expected_identity_sha256 or "").strip()
    if expected:
        report["expected_identity_sha256"] = expected
        report["identity_matches_expected"] = (
            report.get("identity_sha256") == expected
        )
        report["ok"] = bool(report.get("ok")) and bool(
            report["identity_matches_expected"]
        )
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if report["ok"] else FAILURE_EXIT


if __name__ == "__main__":
    raise SystemExit(main())
