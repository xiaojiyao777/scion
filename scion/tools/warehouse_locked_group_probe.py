#!/usr/bin/env python3
"""Generate or replay the fixed Warehouse W2 locked-group artifacts."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from scion.problems.warehouse_delivery.locked_group_probe import (
    RECEIPT_PATH,
    REPORT_PATH,
    build_probe_artifacts,
    verify_existing_artifact_bytes,
)
from scion.problems.warehouse_delivery.w2_preservation import (
    repository_root,
    sha256_bytes,
)


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _fixed_paths() -> tuple[Path, Path]:
    root = repository_root()
    return root / REPORT_PATH, root / RECEIPT_PATH


def _generate() -> dict[str, object]:
    report_bytes, receipt_bytes, report, receipt = build_probe_artifacts()
    report_path, receipt_path = _fixed_paths()
    _atomic_write(report_path, report_bytes)
    _atomic_write(receipt_path, receipt_bytes)
    return {
        "passed": True,
        "aggregate_sha256": report["aggregate_sha256"],
        "report_raw_sha256": receipt["report_raw_sha256"],
        "receipt_raw_sha256": sha256_bytes(receipt_bytes),
    }


def _check_existing() -> dict[str, object]:
    report_path, receipt_path = _fixed_paths()
    actual_report = report_path.read_bytes()
    actual_receipt = receipt_path.read_bytes()
    return verify_existing_artifact_bytes(actual_report, actual_receipt)


def main() -> int:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--generate", action="store_true")
    action.add_argument("--check-existing", action="store_true")
    args = parser.parse_args()
    result = _generate() if args.generate else _check_existing()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
