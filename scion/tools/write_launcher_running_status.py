#!/usr/bin/env python3
"""Write root launcher status after pre-campaign guards pass."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "outer-wrapper.v1"


def build_status(
    *,
    run_root: Path,
    campaign_dir: Path,
    git_commit: str,
    model: str,
    started_utc: str,
    pid: int,
    scion_base_url: str = "",
    completion_preflight: bool | None = None,
    postrun_reports: bool | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "running",
        "prepared_only": False,
        "run_root": str(run_root),
        "campaign_dir": str(campaign_dir),
        "git_commit": str(git_commit),
        "model": str(model),
        "started_utc": str(started_utc),
        "pid": int(pid),
    }
    if scion_base_url:
        payload["scion_base_url"] = str(scion_base_url)
    if completion_preflight is not None:
        payload["completion_preflight"] = bool(completion_preflight)
    if postrun_reports is not None:
        payload["postrun_reports"] = bool(postrun_reports)
    return payload


def write_status(
    *,
    output: Path,
    run_root: Path,
    campaign_dir: Path,
    git_commit: str,
    model: str,
    started_utc: str,
    pid: int,
    scion_base_url: str = "",
    completion_preflight: bool | None = None,
    postrun_reports: bool | None = None,
) -> dict[str, Any]:
    payload = build_status(
        run_root=run_root,
        campaign_dir=campaign_dir,
        git_commit=git_commit,
        model=model,
        started_utc=started_utc,
        pid=pid,
        scion_base_url=scion_base_url,
        completion_preflight=completion_preflight,
        postrun_reports=postrun_reports,
    )
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--git-commit", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--started-utc", required=True)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--scion-base-url", default="")
    parser.add_argument("--completion-preflight", type=_boolish, default=None)
    parser.add_argument("--postrun-reports", type=_boolish, default=None)
    args = parser.parse_args(argv)

    write_status(
        output=args.output,
        run_root=args.run_root,
        campaign_dir=args.campaign_dir,
        git_commit=args.git_commit,
        model=args.model,
        started_utc=args.started_utc,
        pid=args.pid,
        scion_base_url=args.scion_base_url,
        completion_preflight=args.completion_preflight,
        postrun_reports=args.postrun_reports,
    )
    return 0


def _boolish(value: str) -> bool:
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"expected boolean-like value, got {value!r}")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
