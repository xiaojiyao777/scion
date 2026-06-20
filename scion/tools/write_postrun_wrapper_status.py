#!/usr/bin/env python3
"""Annotate launcher status with postrun acceptance outcome."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "outer-wrapper.v1"


def _read_status(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema": SCHEMA, "status": "finished"}
    if isinstance(raw, dict):
        return dict(raw)
    return {"schema": SCHEMA, "status": "finished"}


def build_status(
    base: Mapping[str, Any],
    *,
    wrapper_exit_code: int,
    campaign_exit_code: int,
    postrun_reports_exit_code: int,
    postrun_readiness_exit_code: int,
    postrun_report_dir: Path,
    postrun_readiness_path: Path,
) -> dict[str, Any]:
    postrun_failed = (
        postrun_reports_exit_code != 0 or postrun_readiness_exit_code != 0
    )
    payload = dict(base)
    payload.setdefault("schema", SCHEMA)
    payload.setdefault("status", "finished")
    payload["wrapper_exit_status"] = int(wrapper_exit_code)
    payload["campaign_wrapper_exit_status"] = int(campaign_exit_code)
    payload["postrun_acceptance_status"] = "failed" if postrun_failed else "ready"
    payload["postrun_acceptance_failed"] = postrun_failed
    payload["postrun_reports_exit_status"] = int(postrun_reports_exit_code)
    payload["postrun_readiness_exit_status"] = int(postrun_readiness_exit_code)
    payload["postrun_acceptance_report_dir"] = str(postrun_report_dir)
    payload["postrun_acceptance_readiness_file"] = postrun_readiness_path.name
    payload["postrun_acceptance_readiness_path"] = str(postrun_readiness_path)
    return payload


def write_status(
    output: Path,
    *,
    wrapper_exit_code: int,
    campaign_exit_code: int,
    postrun_reports_exit_code: int,
    postrun_readiness_exit_code: int,
    postrun_report_dir: Path,
    postrun_readiness_path: Path,
) -> dict[str, Any]:
    payload = build_status(
        _read_status(output),
        wrapper_exit_code=wrapper_exit_code,
        campaign_exit_code=campaign_exit_code,
        postrun_reports_exit_code=postrun_reports_exit_code,
        postrun_readiness_exit_code=postrun_readiness_exit_code,
        postrun_report_dir=postrun_report_dir,
        postrun_readiness_path=postrun_readiness_path,
    )
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--wrapper-exit-code", type=int, required=True)
    parser.add_argument("--campaign-exit-code", type=int, required=True)
    parser.add_argument("--postrun-reports-exit-code", type=int, required=True)
    parser.add_argument("--postrun-readiness-exit-code", type=int, required=True)
    parser.add_argument("--postrun-report-dir", type=Path, required=True)
    parser.add_argument("--postrun-readiness-path", type=Path, required=True)
    args = parser.parse_args(argv)

    write_status(
        args.output,
        wrapper_exit_code=args.wrapper_exit_code,
        campaign_exit_code=args.campaign_exit_code,
        postrun_reports_exit_code=args.postrun_reports_exit_code,
        postrun_readiness_exit_code=args.postrun_readiness_exit_code,
        postrun_report_dir=args.postrun_report_dir,
        postrun_readiness_path=args.postrun_readiness_path,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
