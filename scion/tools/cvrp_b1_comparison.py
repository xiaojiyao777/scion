#!/usr/bin/env python3
"""Publish or replay the sealed CVRP B1 problem-owned comparison artifacts."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
from typing import Any

from scion.problems.cvrp.evidence.b1_comparison import (
    CANONICAL_INPUT_ROOT,
    RECEIPT_NAME,
    REPORT_NAME,
    CvrpB1ComparisonError,
    build_comparison_artifacts,
    integrity_reject_verdict,
    sha256_bytes,
    verify_existing_artifact_bytes,
)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_no_replace(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o644)
    except FileExistsError as exc:
        raise CvrpB1ComparisonError(
            f"refusing to replace existing comparison artifact: {path}"
        ) from exc
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    _fsync_directory(path.parent)


def _existing_regular(path: Path) -> bool:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return False
    if not stat.S_ISREG(mode):
        raise CvrpB1ComparisonError(
            f"comparison artifact entry is not a regular file: {path}"
        )
    return True


def _read_regular_no_follow(path: Path) -> bytes:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise CvrpB1ComparisonError(
            f"cannot open comparison artifact without following links: {path}"
        ) from exc
    with os.fdopen(descriptor, "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise CvrpB1ComparisonError(
                f"comparison artifact is not a regular file: {path}"
            )
        return handle.read()


def _publish(input_root: Path) -> dict[str, Any]:
    artifacts = build_comparison_artifacts(input_root)
    report_path = input_root / REPORT_NAME
    receipt_path = input_root / RECEIPT_NAME
    report_exists = _existing_regular(report_path)
    receipt_exists = _existing_regular(receipt_path)
    if receipt_exists and not report_exists:
        raise CvrpB1ComparisonError("receipt exists without its comparison report")
    if report_exists and receipt_exists:
        raise CvrpB1ComparisonError(
            "comparison artifacts already exist; use --check-existing"
        )
    if report_exists:
        actual_report = _read_regular_no_follow(report_path)
        if actual_report != artifacts.report_bytes:
            raise CvrpB1ComparisonError(
                "existing report is partial or differs from sealed replay"
            )
        _write_no_replace(receipt_path, artifacts.receipt_bytes)
        publication = "receipt_recovered_after_exact_report_replay"
    else:
        _write_no_replace(report_path, artifacts.report_bytes)
        # A failure here deliberately leaves the complete, byte-replayable report;
        # the contract permits a later exact replay to publish only the receipt.
        _write_no_replace(receipt_path, artifacts.receipt_bytes)
        publication = "report_then_receipt_published_no_replace"
    return {
        "passed": True,
        "publication": publication,
        "report_raw_sha256": sha256_bytes(artifacts.report_bytes),
        "receipt_raw_sha256": sha256_bytes(artifacts.receipt_bytes),
        "acceptance_verdict": artifacts.receipt["acceptance_verdict"],
        "f1_unlocked_by_closer_verdict": artifacts.receipt[
            "f1_unlocked_by_closer_verdict"
        ],
    }


def _check_existing(input_root: Path) -> dict[str, Any]:
    report_path = input_root / REPORT_NAME
    receipt_path = input_root / RECEIPT_NAME
    report_exists = _existing_regular(report_path)
    receipt_exists = _existing_regular(receipt_path)
    if receipt_exists and not report_exists:
        raise CvrpB1ComparisonError("receipt exists without its comparison report")
    if not report_exists or not receipt_exists:
        raise CvrpB1ComparisonError("both comparison artifacts are required for replay")
    return verify_existing_artifact_bytes(
        input_root,
        _read_regular_no_follow(report_path),
        _read_regular_no_follow(receipt_path),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Close or byte-replay the sealed CVRP B1 comparison"
    )
    parser.add_argument(
        "--input-root",
        type=Path,
        default=Path(CANONICAL_INPUT_ROOT),
        help="Sealed B1 root; its basename and artifact hashes are frozen.",
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--publish", action="store_true")
    action.add_argument("--check-existing", action="store_true")
    args = parser.parse_args(argv)
    try:
        root = args.input_root.expanduser().resolve(strict=True)
        canonical_root = Path(CANONICAL_INPUT_ROOT).resolve(strict=True)
        if root != canonical_root:
            raise CvrpB1ComparisonError(
                "formal CLI publication/replay requires the exact accepted B1 root"
            )
        result = _publish(root) if args.publish else _check_existing(root)
    except (CvrpB1ComparisonError, OSError) as exc:
        print(
            json.dumps(
                integrity_reject_verdict(exc), ensure_ascii=False, sort_keys=True
            )
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
