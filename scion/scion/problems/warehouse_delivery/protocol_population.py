"""Warehouse protocol-to-manifest population reconciliation.

This is a problem-owned scientific-asset check, not a candidate gate.  The
split manifest's ordered case identifiers and their immutable byte identities
are the population authority.  The contract makes the protocol selector's
otherwise silent shortfall observable before a warehouse campaign is prepared.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import yaml
from pydantic import ValidationError

from scion.config.problem import ProtocolConfig, SplitManifest
from scion.core.models import ExperimentStage
from scion.protocol.experiment.selection import SplitManager, select_cases


SCHEMA_VERSION = "scion.warehouse_protocol_population_reconcile.v2"
_POPULATION_STAGES = ("screening", "validation", "frozen", "canary")


class WarehouseProtocolPopulationError(ValueError):
    """Raised when Warehouse formal assets cannot form one exact population."""


@dataclass(frozen=True)
class _RequestSpec:
    request_id: str
    stage: ExperimentStage
    hypothesis_action: str
    expand_round: int
    requested: int


@dataclass(frozen=True)
class _FileSnapshot:
    path: Path
    resolved_path: Path
    content: bytes
    sha256: str
    size_bytes: int

    def source_identity(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return _sha256_bytes(encoded)


def _absolute_lexical_path(path: Path, *, relative_to: Path | None = None) -> Path:
    expanded = path.expanduser()
    if not expanded.is_absolute():
        expanded = (relative_to or Path.cwd()) / expanded
    return Path(os.path.abspath(expanded))


def _assert_no_symlink_components(path: Path, *, label: str) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            metadata = os.lstat(current)
        except FileNotFoundError as exc:
            raise WarehouseProtocolPopulationError(
                f"{label} missing: {path}"
            ) from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise WarehouseProtocolPopulationError(
                f"{label} must be symlink-free: {current}"
            )


def _read_regular_snapshot(
    path: str | Path,
    *,
    label: str,
    relative_to: Path | None = None,
) -> _FileSnapshot:
    """Read one regular, symlink-free file once and bind metadata to its bytes."""

    lexical_path = _absolute_lexical_path(Path(path), relative_to=relative_to)
    _assert_no_symlink_components(lexical_path, label=label)
    resolved_before = lexical_path.resolve(strict=True)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(lexical_path, flags)
    except OSError as exc:
        raise WarehouseProtocolPopulationError(
            f"{label} cannot be opened: {lexical_path}: {exc.strerror}"
        ) from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise WarehouseProtocolPopulationError(
                f"{label} must be a regular file: {lexical_path}"
            )
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        content = b"".join(chunks)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)

    before_identity = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    after_identity = (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    _assert_no_symlink_components(lexical_path, label=label)
    path_after = os.stat(lexical_path, follow_symlinks=False)
    resolved_after = lexical_path.resolve(strict=True)
    if (
        before_identity != after_identity
        or len(content) != after.st_size
        or (path_after.st_dev, path_after.st_ino) != (after.st_dev, after.st_ino)
        or resolved_before != resolved_after
    ):
        raise WarehouseProtocolPopulationError(
            f"{label} changed while being read: {lexical_path}"
        )
    return _FileSnapshot(
        path=lexical_path,
        resolved_path=resolved_after,
        content=content,
        sha256=_sha256_bytes(content),
        size_bytes=len(content),
    )


def _yaml_mapping(snapshot: _FileSnapshot, *, label: str) -> dict[str, Any]:
    try:
        loaded = yaml.safe_load(snapshot.content.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise WarehouseProtocolPopulationError(
            f"{label} is not valid UTF-8 YAML: {snapshot.path}: {exc}"
        ) from exc
    if not isinstance(loaded, dict):
        raise WarehouseProtocolPopulationError(
            f"{label} must contain a YAML mapping: {snapshot.path}"
        )
    return loaded


def _load_protocol(snapshot: _FileSnapshot) -> ProtocolConfig:
    try:
        return ProtocolConfig.model_validate(
            _yaml_mapping(snapshot, label="protocol source")
        )
    except ValidationError as exc:
        raise WarehouseProtocolPopulationError(
            f"protocol source schema invalid: {snapshot.path}: {exc}"
        ) from exc


def _load_manifest(snapshot: _FileSnapshot) -> SplitManifest:
    try:
        manifest = SplitManifest.model_validate(
            _yaml_mapping(snapshot, label="manifest source")
        )
    except ValidationError as exc:
        raise WarehouseProtocolPopulationError(
            f"manifest source schema invalid: {snapshot.path}: {exc}"
        ) from exc
    roots: list[str] = []
    for root in manifest.safe_data_roots:
        roots.append(
            str(
                _absolute_lexical_path(
                    Path(root),
                    relative_to=snapshot.path.parent,
                )
            )
        )
    return manifest.model_copy(update={"safe_data_roots": roots})


def _manifest_cases(manifest: SplitManifest, stage: str) -> tuple[str, ...]:
    if stage not in _POPULATION_STAGES:
        raise ValueError(f"unsupported warehouse population stage: {stage}")
    return tuple(getattr(manifest, stage))


def _stable_case_id(stage: str, lexical_case_id: str) -> str:
    basename = Path(lexical_case_id.replace("\\", "/")).name
    if not basename:
        raise WarehouseProtocolPopulationError(
            f"{stage} manifest contains an empty case basename: {lexical_case_id!r}"
        )
    return f"warehouse_delivery/{stage}/{basename}"


def _case_identity(
    *,
    stage: str,
    manifest_index: int,
    lexical_case_id: str,
    manifest_dir: Path,
) -> dict[str, Any]:
    snapshot = _read_regular_snapshot(
        lexical_case_id,
        label=f"{stage} case[{manifest_index}]",
        relative_to=manifest_dir,
    )
    return {
        "stable_case_id": _stable_case_id(stage, lexical_case_id),
        "manifest_index": manifest_index,
        "lexical_path": lexical_case_id,
        "resolved_path": str(snapshot.resolved_path),
        "regular_file": True,
        "symlink_free": True,
        "size_bytes": snapshot.size_bytes,
        "content_sha256": snapshot.sha256,
    }


def _content_identity(case: dict[str, Any]) -> dict[str, str]:
    return {
        "stable_case_id": str(case["stable_case_id"]),
        "content_sha256": str(case["content_sha256"]),
    }


def _request_specs(protocol: ProtocolConfig) -> tuple[_RequestSpec, ...]:
    return (
        _RequestSpec(
            "screening.modify.initial",
            ExperimentStage.SCREENING,
            "modify",
            0,
            protocol.screening.n_cases_modify,
        ),
        _RequestSpec(
            "screening.create.initial",
            ExperimentStage.SCREENING,
            "create_new",
            0,
            protocol.screening.n_cases_create,
        ),
        _RequestSpec(
            "screening.modify.expanded",
            ExperimentStage.SCREENING,
            "modify",
            1,
            protocol.screening.expand_to_modify,
        ),
        _RequestSpec(
            "screening.create.expanded",
            ExperimentStage.SCREENING,
            "create_new",
            1,
            protocol.screening.expand_to_create,
        ),
        _RequestSpec(
            "validation.initial",
            ExperimentStage.VALIDATION,
            "modify",
            0,
            protocol.validation.n_cases,
        ),
        _RequestSpec(
            "validation.expanded",
            ExperimentStage.VALIDATION,
            "modify",
            1,
            protocol.validation.expand_to,
        ),
        _RequestSpec(
            "frozen.initial",
            ExperimentStage.FROZEN,
            "modify",
            0,
            protocol.frozen.n_cases,
        ),
    )


def reconcile_warehouse_protocol_population(
    protocol: ProtocolConfig,
    manifest: SplitManifest,
    *,
    protocol_snapshot: _FileSnapshot,
    manifest_snapshot: _FileSnapshot,
) -> dict[str, Any]:
    """Return the exact Warehouse W1 population contract for two snapshots."""

    split_manager = SplitManager(manifest)
    errors: list[str] = []
    population_rows: list[dict[str, Any]] = []
    populations: dict[str, tuple[str, ...]] = {}
    case_by_lexical: dict[tuple[str, str], dict[str, Any]] = {}

    for stage in _POPULATION_STAGES:
        exact_case_ids = _manifest_cases(manifest, stage)
        populations[stage] = exact_case_ids
        distinct_count = len(set(exact_case_ids))
        if distinct_count != len(exact_case_ids):
            errors.append(
                f"{stage} manifest contains duplicate case ids: "
                f"entries={len(exact_case_ids)} distinct={distinct_count}"
            )
        cases = [
            _case_identity(
                stage=stage,
                manifest_index=index,
                lexical_case_id=lexical_case_id,
                manifest_dir=manifest_snapshot.path.parent,
            )
            for index, lexical_case_id in enumerate(exact_case_ids)
        ]
        stable_ids = [str(case["stable_case_id"]) for case in cases]
        if len(set(stable_ids)) != len(stable_ids):
            errors.append(f"{stage} manifest contains duplicate stable case ids")
        for case in cases:
            case_by_lexical[(stage, str(case["lexical_path"]))] = case
        content_population = [_content_identity(case) for case in cases]
        population_rows.append(
            {
                "stage": stage,
                "available": distinct_count,
                "entries": len(exact_case_ids),
                "cases": cases,
                "manifest_order_sha256": _canonical_sha256(list(exact_case_ids)),
                "population_sha256": _canonical_sha256(content_population),
            }
        )

    expansion_pairs = (
        (
            "screening.modify",
            protocol.screening.n_cases_modify,
            protocol.screening.expand_to_modify,
        ),
        (
            "screening.create",
            protocol.screening.n_cases_create,
            protocol.screening.expand_to_create,
        ),
        (
            "validation",
            protocol.validation.n_cases,
            protocol.validation.expand_to,
        ),
    )
    for name, initial, expanded in expansion_pairs:
        if expanded < initial:
            errors.append(
                f"{name} expansion cannot shrink population: "
                f"initial={initial} expanded={expanded}"
            )
        elif expanded == initial:
            errors.append(
                f"{name} expansion must add cases: "
                f"initial={initial} expanded={expanded}"
            )

    for spec in _request_specs(protocol):
        stage = spec.stage.value
        available = len(set(populations[stage]))
        if spec.requested > available:
            errors.append(
                f"{spec.request_id} requests {spec.requested} cases but "
                f"manifest has {available} distinct {stage} cases"
            )

    # Preserve the problem-owned diagnostic instead of letting the generic
    # selector's fail-fast replace it with a less specific configuration error.
    if errors:
        raise WarehouseProtocolPopulationError("; ".join(errors))

    request_rows: list[dict[str, Any]] = []
    for spec in _request_specs(protocol):
        stage = spec.stage.value
        exact_population = populations[stage]
        available = len(set(exact_population))
        selected = tuple(
            select_cases(
                config=protocol,
                split_manager=split_manager,
                stage=spec.stage,
                hypothesis_action=spec.hypothesis_action,
                expand_round=spec.expand_round,
            )
        )
        resolved = len(selected)
        resolved_distinct = len(set(selected))
        if resolved != spec.requested or resolved_distinct != spec.requested:
            errors.append(
                f"{spec.request_id} resolved {resolved} entries/"
                f"{resolved_distinct} distinct cases for request {spec.requested}"
            )
        selected_identities = [
            case_by_lexical[(stage, lexical_case_id)] for lexical_case_id in selected
        ]
        request_rows.append(
            {
                "request_id": spec.request_id,
                "stage": stage,
                "hypothesis_action": spec.hypothesis_action,
                "expand_round": spec.expand_round,
                "requested": spec.requested,
                "available": available,
                "resolved": resolved,
                "resolved_distinct": resolved_distinct,
                "exact_selected_case_ids": list(selected),
                "selected_case_identities": selected_identities,
                "selection_location_sha256": _canonical_sha256(list(selected)),
                "selection_sha256": _canonical_sha256(
                    [_content_identity(case) for case in selected_identities]
                ),
            }
        )

    if errors:
        raise WarehouseProtocolPopulationError("; ".join(errors))

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "reconciled",
        "problem_family": "warehouse_delivery",
        "authority": "split_manifest_ordered_exact_case_content",
        "decision_features_excluded": True,
        "candidate_gate": False,
        "protocol_version": protocol.version,
        "manifest_version": manifest.version,
        "sources": {
            "protocol": protocol_snapshot.source_identity(),
            "manifest": manifest_snapshot.source_identity(),
        },
        "populations": population_rows,
        "requests": request_rows,
        "invariants": {
            "yaml_each_read_once": True,
            "case_each_read_once": True,
            "no_duplicate_manifest_case_ids": True,
            "no_duplicate_stable_case_ids": True,
            "all_cases_regular_and_symlink_free": True,
            "all_cases_content_bound": True,
            "no_silent_population_shortfall": True,
            "expansion_never_shrinks_population": True,
            "missing_cases_synthesized": False,
        },
    }
    payload["reconciliation_sha256"] = _canonical_sha256(payload)
    return payload


def reconcile_warehouse_protocol_population_from_paths(
    protocol_path: str | Path,
    manifest_path: str | Path,
) -> dict[str, Any]:
    """Read each source once, parse those bytes, and reconcile exact cases."""

    protocol_snapshot = _read_regular_snapshot(
        protocol_path,
        label="protocol source",
    )
    manifest_snapshot = _read_regular_snapshot(
        manifest_path,
        label="manifest source",
    )
    return reconcile_warehouse_protocol_population(
        _load_protocol(protocol_snapshot),
        _load_manifest(manifest_snapshot),
        protocol_snapshot=protocol_snapshot,
        manifest_snapshot=manifest_snapshot,
    )


def assert_warehouse_population_copy_matches(
    source: dict[str, Any],
    prepared_copy: dict[str, Any],
) -> None:
    """Reject a prepared copy that drifts from the source population bytes."""

    if source["protocol_version"] != prepared_copy["protocol_version"]:
        raise WarehouseProtocolPopulationError(
            "prepared-copy protocol version drift"
        )
    if source["manifest_version"] != prepared_copy["manifest_version"]:
        raise WarehouseProtocolPopulationError(
            "prepared-copy manifest version drift"
        )
    if (
        source["sources"]["protocol"]["sha256"]
        != prepared_copy["sources"]["protocol"]["sha256"]
    ):
        raise WarehouseProtocolPopulationError(
            "prepared-copy protocol content drift"
        )

    source_populations = {
        row["stage"]: row["population_sha256"] for row in source["populations"]
    }
    prepared_populations = {
        row["stage"]: row["population_sha256"]
        for row in prepared_copy["populations"]
    }
    if source_populations != prepared_populations:
        raise WarehouseProtocolPopulationError(
            "prepared-copy case population content drift"
        )

    source_requests = {
        row["request_id"]: (
            row["requested"],
            row["available"],
            row["resolved"],
            row["selection_sha256"],
        )
        for row in source["requests"]
    }
    prepared_requests = {
        row["request_id"]: (
            row["requested"],
            row["available"],
            row["resolved"],
            row["selection_sha256"],
        )
        for row in prepared_copy["requests"]
    }
    if source_requests != prepared_requests:
        raise WarehouseProtocolPopulationError(
            "prepared-copy selected case content drift"
        )


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path = _absolute_lexical_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    directory_descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_descriptor)
    finally:
        os.close(directory_descriptor)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe Warehouse W1 protocol/manifest population consistency."
    )
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expect-reconciliation-sha256")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        payload = reconcile_warehouse_protocol_population_from_paths(
            args.protocol,
            args.manifest,
        )
    except WarehouseProtocolPopulationError as exc:
        print(f"WAREHOUSE_W1_RECONCILE_FAILED={exc}", file=sys.stderr)
        return 64
    _write_json_atomic(args.output, payload)
    expected = str(args.expect_reconciliation_sha256 or "").strip()
    if expected and expected != payload["reconciliation_sha256"]:
        print(
            "WAREHOUSE_W1_RECONCILIATION_SHA256_MISMATCH="
            f"expected:{expected},actual:{payload['reconciliation_sha256']}",
            file=sys.stderr,
        )
        return 64
    print(f"WAREHOUSE_W1_RECONCILED={payload['reconciliation_sha256']}")
    print(f"ARTIFACT={_absolute_lexical_path(args.output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
