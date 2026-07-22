"""Warehouse W3 frozen-input materialization and manifest construction.

This module is deliberately problem-owned.  It knows the exact Warehouse R3
ancestry, W1 case identity contract, solver source closure, arm semantics, and
directed merge opportunities.  It does not expose a generic experiment helper
and it never starts a formal solver job.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from random import Random
from typing import TYPE_CHECKING, Any, Iterator, Mapping, Sequence

import yaml

if TYPE_CHECKING:
    from scion.runtime.execution import GenericProcessSpec

SCHEMA = "scion.warehouse_w3_fixed_arm_manifest.v1"
DESIGN_COMMIT = "024ae1e3"
DESIGN_PATH = "scion/docs/planning/v0.4/v0.4-warehouse-w3-fixed-arm-matrix-20260718.md"
DESIGN_SHA256 = "5538a81b6d7980888cf594b07244a0b4863c57db85f3a04beb8f84555ad4bb35"
W1_PATH = "scion/contracts/warehouse_w1_population_receipt.v1.json"
W1_SHA256 = "5b7ddcf6c1cda6fa9fb742d1463c9fd4a3bbbcf3dbb361d8ef7172f0684f116c"
W2_MANIFEST_PATH = "scion/contracts/warehouse_w2_preservation_manifest.v1.json"
W2_MANIFEST_SHA256 = "0ee66091942583c2f499f83338a96abeff51e53b9583afe03fce3356a890dfc9"
W2_RECEIPT_PATH = "scion/contracts/warehouse_w2_locked_group_probe_receipt.v1.json"
W2_RECEIPT_SHA256 = "68eb68a12a38e465b790c1cf6a984207c68a47f7d4a3378f75b8b799db15eb0c"

R3_ROOT = Path(
    "/home/clawd/research/scion-experiments/"
    "v04-warehouse-direct-repaired-context-confirm-r3-2r-gpt56sol-"
    "20260714T135820Z-claw"
)
R3_EXPANDED_ROOT = Path(
    "/home/clawd/research/scion-experiments/"
    "v04-warehouse-r3-same-candidate-expand-1r-gpt56sol-"
    "20260714T142050Z-claw"
)
R3_VALIDATION_ROOT = Path(
    "/home/clawd/research/scion-experiments/"
    "v04-warehouse-r3-same-candidate-validation-1r-gpt56sol-"
    "20260714T145307Z-claw"
)
CHAMPION_RELATIVE = Path("campaign/champions/champion_v1")
R3_WORKSPACE_RELATIVE = Path("campaign/workspaces/52b0b193-7bc3-469c-97a2-216b494b4e4a")

HISTORICAL_METRICS = (
    (
        "r3_initial_screening",
        R3_ROOT,
        Path("campaign/metrics/0374674b-eeca-4eeb-b438-43e556bc38cb.json"),
        "116d6c30def6082e5ea7593465fd3eed7087d1dee88ae36a30599139b1f73b7c",
    ),
    (
        "r3_expanded_screening",
        R3_EXPANDED_ROOT,
        Path("campaign/metrics/c45b663c-17e9-410d-97c3-79c5faa8cbc9.json"),
        "b85fb3adbc35b19c9c16daff0ac0501470c2bda672aae93d749982f4a77dcc93",
    ),
    (
        "r3_validation",
        R3_VALIDATION_ROOT,
        Path("campaign/metrics/85be723f-7030-42eb-8fde-60ffb5298de5.json"),
        "76f967ba5e2de546893b247ad9de1102d74b5dde0a14988c7b9731b0f3be7dde",
    ),
)

PROBLEM_INPUTS = (
    "scion/problems/warehouse_delivery/problem-v1.yaml",
    "scion/problems/warehouse_delivery/protocol_prod.yaml",
    "scion/problems/warehouse_delivery/split_manifest_prod.yaml",
    "scion/problems/warehouse_delivery/seed_ledger.yaml",
)
PROTOCOL_ANALYSIS_SOURCES = (
    "scion/scion/protocol/experiment/feedback.py",
    "scion/scion/protocol/stats.py",
    "scion/scion/protocol/gates.py",
)
SOLVER_CLOSURE = (
    "config.py",
    "greedy_init.py",
    "models.py",
    "oracle.py",
    "pool.py",
    "solver.py",
    "vns.py",
    "registry.yaml",
    "operators/__init__.py",
    "operators/base.py",
    "operators/change_vehicle_type.py",
    "operators/destroy_rebuild.py",
    "operators/merge_vehicles.py",
    "operators/move_order.py",
    "operators/split_vehicle.py",
    "operators/swap_orders.py",
)
PROBLEM_LAYER_SOURCES = (
    "scion/scion/problems/warehouse_delivery/w3_fixed_arm.py",
    "scion/scion/problems/warehouse_delivery/w3_counter_fixtures.py",
    "scion/scion/problems/warehouse_delivery/w3_validation.py",
    "scion/scion/problems/warehouse_delivery/w3_analysis.py",
    "scion/tools/warehouse_w3_fixed_arm.py",
)
SOURCE_RECEIPT_SCHEMA = "scion.warehouse_w3_source_receipt.v1"
SOURCE_RECEIPT_NAME = "warehouse_w3_source_receipt.v1.json"

ARM_ORDER = ("champion", "destroy_only", "merge_only", "cumulative")
WILLIAMS = (
    ("champion", "destroy_only", "cumulative", "merge_only"),
    ("destroy_only", "merge_only", "champion", "cumulative"),
    ("merge_only", "cumulative", "destroy_only", "champion"),
    ("cumulative", "champion", "merge_only", "destroy_only"),
)
INITIAL_SCREENING_BASENAMES = (
    "instance_prod_scr_micro01.json",
    "instance_prod_scr_micro04.json",
    "instance_prod_scr_s03.json",
    "instance_prod_scr_ms02.json",
    "instance_prod_scr_m03.json",
    "instance_prod_scr_ml02.json",
)
EXPECTED_REGISTRY_SHA256 = (
    "1cf4797387d1bc1d75d2dffcb9a1d87f2fa0ce51bfdd2bf205cde3ea1a864525"
)
R3_REGISTRY_SHA256 = "4a3f8c737bb02cd3b87230ae4dad4a758287e0fef3ffb82e810a3f0592c212f1"

FORMAL_COUNTER_CONTRACT = {
    "schema": "scion.warehouse_w3_formal_directed_merge_counter.v1",
    "ordered_pairs": "all_nonempty_source_destination_pairs",
    "move": "complete_source_vehicle",
    "vehicle_type": "select_minimum_vehicle_type",
    "accept": "reconstructed_solution_current_oracle_feasible",
}
CHAMPION_COUNTER_CONTRACT = {
    "schema": "scion.warehouse_w3_champion_merge_eligible_counter.v1",
    "direction": "source_order_count_lte_destination_order_count",
    "predicate": "frozen_champion_capacity_and_hazard_minimum_type",
}
R3_COUNTER_CONTRACT = {
    "schema": "scion.warehouse_w3_r3_merge_eligible_counter.v1",
    "direction": "all_ordered_nonempty_pairs",
    "predicate": (
        "frozen_r3_source_unlocked_region_category_capacity_hazard_pickup_amount"
    ),
}


class WarehouseW3Error(RuntimeError):
    """Raised when W3 ancestry or a dry manifest is not closed."""


@dataclass(frozen=True)
class Snapshot:
    path: Path
    data: bytes
    sha256: str
    size_bytes: int


def repository_root() -> Path:
    return Path(__file__).resolve().parents[4]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def render_json(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(path.expanduser()))


def _assert_no_symlink_components(
    path: Path, *, allow_missing_leaf: bool = False
) -> None:
    absolute = _absolute(path)
    current = Path(absolute.anchor)
    parts = absolute.parts[1:]
    for index, part in enumerate(parts):
        current /= part
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            if allow_missing_leaf and index == len(parts) - 1:
                return
            raise WarehouseW3Error(f"path component is missing: {current}") from None
        if stat.S_ISLNK(metadata.st_mode):
            raise WarehouseW3Error(f"symlink is not accepted: {current}")


def read_regular(path: Path, *, expected_sha256: str | None = None) -> Snapshot:
    absolute = _absolute(path)
    _assert_no_symlink_components(absolute)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(absolute, flags)
    except OSError as exc:
        raise WarehouseW3Error(f"cannot open input {absolute}: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise WarehouseW3Error(f"input is not a regular file: {absolute}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    data = b"".join(chunks)
    path_after = os.stat(absolute, follow_symlinks=False)
    if (
        (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        or (after.st_dev, after.st_ino) != (path_after.st_dev, path_after.st_ino)
        or len(data) != after.st_size
    ):
        raise WarehouseW3Error(f"input changed while being read: {absolute}")
    digest = sha256_bytes(data)
    if expected_sha256 is not None and digest != expected_sha256:
        raise WarehouseW3Error(
            f"input hash mismatch: {absolute}: expected {expected_sha256}, got {digest}"
        )
    return Snapshot(absolute, data, digest, len(data))


def exclusive_write(path: Path, data: bytes, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(path, flags, mode)
    try:
        view = memoryview(data)
        while view:
            written = os.write(descriptor, view)
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def inventory_regular_tree(
    root: Path, relative: str | Path = "."
) -> dict[str, list[str]]:
    """Return exact regular-file/directory sets and reject every symlink/special file."""

    base = root if str(relative) == "." else root / relative
    _assert_no_symlink_components(base)
    files: list[str] = []
    directories: list[str] = []
    for current, dirnames, filenames in os.walk(base, topdown=True, followlinks=False):
        current_path = Path(current)
        relative_current = current_path.relative_to(root)
        if relative_current != Path("."):
            directories.append(str(relative_current))
        for dirname in list(dirnames):
            path = current_path / dirname
            metadata = os.lstat(path)
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
                raise WarehouseW3Error(
                    f"non-directory or symlink in sealed tree: {path}"
                )
        for filename in filenames:
            path = current_path / filename
            metadata = os.lstat(path)
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
                raise WarehouseW3Error(f"non-regular or symlink in sealed tree: {path}")
            files.append(str(path.relative_to(root)))
    return {
        "directories": sorted(directories, key=lambda value: value.encode("utf-8")),
        "files": sorted(files, key=lambda value: value.encode("utf-8")),
    }


def _copy_snapshot(snapshot: Snapshot, destination: Path) -> dict[str, Any]:
    exclusive_write(destination, snapshot.data)
    copied = read_regular(destination, expected_sha256=snapshot.sha256)
    return {
        "sealed_path": str(destination),
        "sha256": copied.sha256,
        "size_bytes": copied.size_bytes,
    }


class _UniqueLoader(yaml.SafeLoader):
    pass


def _unique_mapping(
    loader: _UniqueLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise WarehouseW3Error(
                f"duplicate YAML key {key!r} at line {key_node.start_mark.line + 1}"
            )
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _unique_mapping,
)


def load_unique_yaml(data: bytes, *, label: str) -> dict[str, Any]:
    try:
        loaded = yaml.load(data.decode("utf-8"), Loader=_UniqueLoader)
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise WarehouseW3Error(f"invalid YAML for {label}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise WarehouseW3Error(f"YAML root is not a mapping for {label}")
    return loaded


def registry_semantics(data: bytes, *, label: str) -> dict[str, Any]:
    loaded = load_unique_yaml(data, label=label)
    operators = loaded.get("operators")
    if not isinstance(operators, list) or not operators:
        raise WarehouseW3Error(f"registry has no operator list: {label}")
    normalized: list[dict[str, Any]] = []
    names: set[str] = set()
    for index, raw in enumerate(operators):
        if not isinstance(raw, dict):
            raise WarehouseW3Error(f"registry operator[{index}] is not a mapping")
        required = ("name", "file_path", "class_name", "weight")
        if any(key not in raw for key in required):
            raise WarehouseW3Error(f"registry operator[{index}] is incomplete")
        name = str(raw["name"])
        if name in names:
            raise WarehouseW3Error(f"registry contains duplicate operator {name}")
        names.add(name)
        weight = raw["weight"]
        if isinstance(weight, bool) or not isinstance(weight, (int, float)):
            raise WarehouseW3Error(f"registry operator {name} has nonnumeric weight")
        normalized.append(
            {
                "name": name,
                "file_path": str(raw["file_path"]),
                "class_name": str(raw["class_name"]),
                "weight": float(weight),
            }
        )
    payload = {
        "schema": "scion.warehouse_w3_registry_semantics.v1",
        "operators": normalized,
    }
    payload["semantic_sha256"] = canonical_sha256(payload)
    return payload


def _identity(path: Path, *, relative: str | None = None) -> dict[str, Any]:
    snapshot = read_regular(path)
    return {
        "path": relative if relative is not None else str(snapshot.path),
        "sha256": snapshot.sha256,
        "size_bytes": snapshot.size_bytes,
    }


def _tree_identity(root: Path, relative_files: Sequence[str]) -> dict[str, Any]:
    files = [
        _identity(root / relative, relative=relative) for relative in relative_files
    ]
    return {
        "files": files,
        "tree_sha256": canonical_sha256(
            {"domain": "scion.warehouse_w3_source_tree.v1", "items": files}
        ),
    }


def _stable_case_id(stage: str, lexical_path: str) -> str:
    return f"warehouse_delivery/{stage}/{Path(lexical_path).name}"


def _case_identity(stage: str, index: int, lexical_path: str) -> dict[str, Any]:
    snapshot = read_regular(Path(lexical_path))
    return {
        "stable_case_id": _stable_case_id(stage, lexical_path),
        "manifest_index": index,
        "lexical_path": lexical_path,
        "resolved_path": str(snapshot.path.resolve(strict=True)),
        "regular_file": True,
        "symlink_free": True,
        "size_bytes": snapshot.size_bytes,
        "content_sha256": snapshot.sha256,
    }


def _content_identity(case: Mapping[str, Any]) -> dict[str, str]:
    return {
        "stable_case_id": str(case["stable_case_id"]),
        "content_sha256": str(case["content_sha256"]),
    }


def _metric_source(
    label: str, root: Path, relative: Path, expected_sha256: str
) -> tuple[dict[str, Any], dict[str, Any], Snapshot]:
    snapshot = read_regular(root / relative, expected_sha256=expected_sha256)
    try:
        loaded = json.loads(snapshot.data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WarehouseW3Error(f"historical metric is invalid JSON: {label}") from exc
    if not isinstance(loaded, dict):
        raise WarehouseW3Error(f"historical metric is not a mapping: {label}")
    return (
        {
            "label": label,
            "protected_root": str(root),
            "relative_path": str(relative),
            "sha256": snapshot.sha256,
            "size_bytes": snapshot.size_bytes,
        },
        loaded,
        snapshot,
    )


def _selection_sha256(cases: Sequence[Mapping[str, Any]]) -> str:
    return canonical_sha256([_content_identity(case) for case in cases])


def _selection_location_sha256(paths: Sequence[str]) -> str:
    return canonical_sha256(list(paths))


def _case_contract(root: Path) -> tuple[dict[str, Any], dict[str, Snapshot]]:
    manifest_snapshot = read_regular(
        root / "scion/problems/warehouse_delivery/split_manifest_prod.yaml"
    )
    split = load_unique_yaml(manifest_snapshot.data, label="Warehouse split manifest")
    w1_snapshot = read_regular(root / W1_PATH, expected_sha256=W1_SHA256)
    w1 = json.loads(w1_snapshot.data)
    populations = {row["stage"]: row for row in w1["populations"]}

    cases_by_stage: dict[str, list[dict[str, Any]]] = {}
    snapshots: dict[str, Snapshot] = {}
    for stage in ("screening", "validation"):
        lexical = split.get(stage)
        if not isinstance(lexical, list) or len(lexical) != len(set(lexical)):
            raise WarehouseW3Error(f"{stage} W1 population is missing or duplicated")
        cases = [
            _case_identity(stage, index, str(path))
            for index, path in enumerate(lexical)
        ]
        if (
            canonical_sha256([_content_identity(case) for case in cases])
            != populations[stage]["population_sha256"]
        ):
            raise WarehouseW3Error(f"{stage} population differs from W1 receipt")
        if (
            canonical_sha256(list(map(str, lexical)))
            != populations[stage]["manifest_order_sha256"]
        ):
            raise WarehouseW3Error(f"{stage} manifest order differs from W1 receipt")
        cases_by_stage[stage] = cases
        for case in cases:
            snapshots[case["stable_case_id"]] = read_regular(Path(case["lexical_path"]))

    metric_entries: list[dict[str, Any]] = []
    metrics: dict[str, dict[str, Any]] = {}
    metric_snapshots: dict[str, Snapshot] = {}
    for label, metric_root, relative, expected in HISTORICAL_METRICS:
        entry, loaded, snapshot = _metric_source(label, metric_root, relative, expected)
        metric_entries.append(entry)
        metrics[label] = loaded
        metric_snapshots[label] = snapshot

    initial_paths = [str(path) for path in metrics["r3_initial_screening"]["case_ids"]]
    expanded_paths = [
        str(path) for path in metrics["r3_expanded_screening"]["case_ids"]
    ]
    validation_paths = [str(path) for path in metrics["r3_validation"]["case_ids"]]
    if tuple(Path(path).name for path in initial_paths) != INITIAL_SCREENING_BASENAMES:
        raise WarehouseW3Error("R3 initial screening case order drifted")
    if metrics["r3_initial_screening"].get("seed_set") != [42, 137]:
        raise WarehouseW3Error("R3 initial screening seeds drifted")
    if metrics["r3_expanded_screening"].get("seed_set") != [42, 137]:
        raise WarehouseW3Error("R3 expanded screening seeds drifted")
    if metrics["r3_validation"].get("seed_set") != [7, 19, 83]:
        raise WarehouseW3Error("R3 validation seeds drifted")

    by_path = {
        str(case["lexical_path"]): case
        for cases in cases_by_stage.values()
        for case in cases
    }
    try:
        initial = [by_path[path] for path in initial_paths]
        expanded = [by_path[path] for path in expanded_paths]
        validation = [by_path[path] for path in validation_paths]
    except KeyError as exc:
        raise WarehouseW3Error(
            f"historical case is outside W1 population: {exc}"
        ) from exc
    if len(initial) != 6 or len(expanded) != 14 or len(validation) != 5:
        raise WarehouseW3Error("historical W3 selected case counts are not 6/14/5")
    if not set(initial_paths).issubset(expanded_paths):
        raise WarehouseW3Error("R3 initial screening is not nested in expanded")
    if expanded != [
        case
        for case in cases_by_stage["screening"]
        if case["lexical_path"] in expanded_paths
    ]:
        raise WarehouseW3Error("R3 expanded screening is not in W1 manifest order")
    if validation != cases_by_stage["validation"]:
        raise WarehouseW3Error("R3 validation is not the W1 manifest order")

    expected_selections = {
        "r3_initial_screening": (
            "2ca79d833c7a54b6a18f826c9a9c7bdebe47b7ae9e3a406fc096811d66f37c07",
            "d37bb880ae4667109a31426549993de314e82c03a747ec2fae3bd960cf90512c",
            initial,
            initial_paths,
        ),
        "r3_expanded_screening": (
            "02f668e6cd96a4ae8dc2e801215651f5eec53b0297399088c0c9c0a7dbeb2e7f",
            "c103a56bbe995dac7e9fc2bb485f8915615a4e7c9d1b9a4c6c78d43c01104725",
            expanded,
            expanded_paths,
        ),
        "r3_validation": (
            "edf8ce68124b24b8d364be56853152bc6862fc03acff23c2d19dc7093b415b87",
            "b374e25970a059d01f7ee6aa6ba9430d020af001b5ae1b4353d8598421c34a1e",
            validation,
            validation_paths,
        ),
    }
    views: dict[str, Any] = {}
    for name, (
        selection_sha,
        location_sha,
        cases,
        paths,
    ) in expected_selections.items():
        actual_selection = _selection_sha256(cases)
        actual_location = _selection_location_sha256(paths)
        if actual_selection != selection_sha or actual_location != location_sha:
            raise WarehouseW3Error(f"W1/R3 selection identity mismatch: {name}")
        views[name] = {
            "selection_sha256": actual_selection,
            "selection_location_sha256": actual_location,
            "stable_case_ids": [case["stable_case_id"] for case in cases],
        }

    selected_screening_ids = {case["stable_case_id"] for case in expanded}
    not_selected = [
        case
        for case in cases_by_stage["screening"]
        if case["stable_case_id"] not in selected_screening_ids
    ]
    if len(not_selected) != 2:
        raise WarehouseW3Error("W3 must declare exactly two unselected screening cases")
    contract = {
        "w1_receipt_sha256": W1_SHA256,
        "historical_metrics": metric_entries,
        "views": views,
        "screening_selected": expanded,
        "validation_selected": validation,
        "w1_bound_not_selected": not_selected,
        "frozen_and_canary_opened": False,
    }
    snapshots.update(
        {f"metric/{key}": value for key, value in metric_snapshots.items()}
    )
    return contract, snapshots


def _arms(w2: Mapping[str, Any]) -> list[dict[str, Any]]:
    derivation = w2["r3"]["arm_derivation"]
    arms = derivation["arms"]
    if tuple(arm.get("name") for arm in arms) != ARM_ORDER:
        raise WarehouseW3Error("W2 arm order differs from W3")
    for arm in arms:
        actual = canonical_sha256(
            {"domain": "scion.warehouse_w3_arm.v1", "items": arm["components"]}
        )
        if actual != arm["arm_sha256"]:
            raise WarehouseW3Error(f"arm digest mismatch: {arm['name']}")
    return [dict(arm) for arm in arms]


def _component_source(arm: Mapping[str, Any], slot: str) -> Path:
    component = next(item for item in arm["components"] if item["slot"] == slot)
    champion = R3_ROOT / CHAMPION_RELATIVE / "operators" / f"{slot}.py"
    replacement = R3_ROOT / R3_WORKSPACE_RELATIVE / "operators" / f"{slot}.py"
    champion_sha = read_regular(champion).sha256
    replacement_sha = read_regular(replacement).sha256
    expected = str(component["sha256"])
    if expected == champion_sha:
        return champion
    if expected == replacement_sha:
        return replacement
    raise WarehouseW3Error(f"arm component has no frozen source: {arm['name']}:{slot}")


def _materialize_workspaces(
    staging: Path, arms: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    champion_root = R3_ROOT / CHAMPION_RELATIVE
    workspaces: list[dict[str, Any]] = []
    registry = read_regular(
        champion_root / "registry.yaml", expected_sha256=EXPECTED_REGISTRY_SHA256
    )
    champion_semantics = registry_semantics(registry.data, label="champion registry")
    r3_registry = read_regular(
        R3_ROOT / R3_WORKSPACE_RELATIVE / "registry.yaml",
        expected_sha256=R3_REGISTRY_SHA256,
    )
    if (
        registry_semantics(r3_registry.data, label="R3 registry")["operators"]
        != champion_semantics["operators"]
    ):
        raise WarehouseW3Error("champion and R3 registry semantics differ")

    for arm in arms:
        arm_name = str(arm["name"])
        destination = staging / "workspaces" / arm_name
        destination.mkdir(parents=True, mode=0o700)
        for relative in SOLVER_CLOSURE:
            source = champion_root / relative
            snapshot = read_regular(source)
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            exclusive_write(target, snapshot.data)
        for slot in ("destroy_rebuild", "merge_vehicles"):
            target = destination / "operators" / f"{slot}.py"
            target.unlink()
            component = read_regular(_component_source(arm, slot))
            exclusive_write(target, component.data)
        tree = _tree_identity(destination, SOLVER_CLOSURE)
        component_hashes = {
            slot: read_regular(destination / "operators" / f"{slot}.py").sha256
            for slot in ("destroy_rebuild", "merge_vehicles")
        }
        expected_components = {
            item["slot"]: item["sha256"] for item in arm["components"]
        }
        if component_hashes != expected_components:
            raise WarehouseW3Error(f"materialized component mismatch: {arm_name}")
        materialized_registry = read_regular(
            destination / "registry.yaml", expected_sha256=EXPECTED_REGISTRY_SHA256
        )
        semantics = registry_semantics(
            materialized_registry.data, label=f"{arm_name} registry"
        )
        if semantics != champion_semantics:
            raise WarehouseW3Error(f"registry semantic mismatch: {arm_name}")
        registry_files = {
            entry["file_path"]: read_regular(destination / entry["file_path"]).sha256
            for entry in semantics["operators"]
        }
        if (
            registry_files["operators/destroy_rebuild.py"]
            != component_hashes["destroy_rebuild"]
            or registry_files["operators/merge_vehicles.py"]
            != component_hashes["merge_vehicles"]
        ):
            raise WarehouseW3Error(f"registry does not bind arm components: {arm_name}")
        workspaces.append(
            {
                "arm": arm_name,
                "arm_sha256": arm["arm_sha256"],
                "relative_path": f"workspaces/{arm_name}",
                "tree": tree,
                "component_sha256": component_hashes,
                "registry_raw_sha256": materialized_registry.sha256,
                "registry_semantics": semantics,
                "registry_file_sha256": dict(sorted(registry_files.items())),
                "provenance": {
                    "kind": "generated",
                    "derivation": "w2_arm_components_over_frozen_r3_champion",
                    "arm_sha256": arm["arm_sha256"],
                },
            }
        )
    return workspaces


_WORKSPACE_MODULES = {
    "config",
    "greedy_init",
    "models",
    "oracle",
    "pool",
    "solver",
    "vns",
    "operators",
    "operators.base",
    "operators.change_vehicle_type",
    "operators.destroy_rebuild",
    "operators.merge_vehicles",
    "operators.move_order",
    "operators.split_vehicle",
    "operators.swap_orders",
}


@contextlib.contextmanager
def workspace_runtime(workspace: Path) -> Iterator[dict[str, Any]]:
    saved_path = list(sys.path)
    saved_dont_write_bytecode = sys.dont_write_bytecode
    saved_modules = {name: sys.modules.get(name) for name in _WORKSPACE_MODULES}
    for name in _WORKSPACE_MODULES:
        sys.modules.pop(name, None)
    sys.path.insert(0, str(workspace))
    sys.dont_write_bytecode = True
    try:
        solver = importlib.import_module("solver")
        yield {
            "solver": solver,
            "models": importlib.import_module("models"),
            "greedy": importlib.import_module("greedy_init"),
            "oracle": importlib.import_module("oracle"),
            "merge_operator": importlib.import_module(
                "operators.merge_vehicles"
            ).MergeVehicles,
        }
    finally:
        for name in _WORKSPACE_MODULES:
            sys.modules.pop(name, None)
        for name, module in saved_modules.items():
            if module is not None:
                sys.modules[name] = module
        sys.path[:] = saved_path
        sys.dont_write_bytecode = saved_dont_write_bytecode


def canonical_solution(solution: Any) -> dict[str, Any]:
    return {
        "assignment": dict(sorted(solution.assignment.items())),
        "vehicles": [
            {
                "vehicle_id": vehicle_id,
                "vehicle_type": solution.vehicles[vehicle_id].vehicle_type,
                "region": solution.vehicles[vehicle_id].region,
                "order_ids": sorted(solution.vehicles[vehicle_id].order_ids),
            }
            for vehicle_id in sorted(solution.vehicles)
            if solution.vehicles[vehicle_id].order_ids
        ],
    }


def _profile(
    runtime: Mapping[str, Any], instance: Any, solution: Any, vehicle_id: str
) -> dict[str, Any]:
    models = runtime["models"]
    order_ids = sorted(solution.vehicles[vehicle_id].order_ids)
    orders = [instance.orders[order_id] for order_id in order_ids]
    regions = {models.get_region(order.pickup_city) for order in orders}
    categories = {order.vehicle_category for order in orders}
    amounts: dict[str, float] = {}
    for order in orders:
        key = f"{order.destination_country},{order.ship_method}"
        amounts[key] = amounts.get(key, 0.0) + order.declaration_amount
    return {
        "order_ids": order_ids,
        "regions": regions,
        "categories": categories,
        "pallets": sum(models.calc_pallets(order.spu_list) for order in orders),
        "hazard": sum(order.hazard_quantity for order in orders if order.hazard_flag),
        "pickups": {order.pickup_name for order in orders},
        "amounts": amounts,
        "subcategories": {order.vehicle_subcategory for order in orders},
        "source_unlocked": all(order.locked_vehicle_id is None for order in orders),
    }


def _minimum_type(models: Any, pallets: int, hazard: int) -> str | None:
    vehicle_type = models.select_minimum_vehicle_type(pallets, hazard)
    if vehicle_type not in models.VEHICLE_TYPES:
        return None
    if models.VEHICLE_TYPES[vehicle_type].capacity < pallets:
        return None
    if hazard > 1800 and vehicle_type != "HQ40_DG":
        return None
    return vehicle_type


def _merged_solution(
    runtime: Mapping[str, Any],
    instance: Any,
    solution: Any,
    source: str,
    destination: str,
) -> Any | None:
    models = runtime["models"]
    candidate = solution.deep_copy()
    source_vehicle = candidate.vehicles[source]
    destination_vehicle = candidate.vehicles[destination]
    order_ids = list(destination_vehicle.order_ids) + list(source_vehicle.order_ids)
    pallets = sum(
        models.calc_pallets(instance.orders[item].spu_list) for item in order_ids
    )
    hazard = sum(
        instance.orders[item].hazard_quantity
        for item in order_ids
        if instance.orders[item].hazard_flag
    )
    vehicle_type = _minimum_type(models, pallets, hazard)
    if vehicle_type is None:
        return None
    destination_vehicle.order_ids = order_ids
    destination_vehicle.vehicle_type = vehicle_type
    for order_id in source_vehicle.order_ids:
        candidate.assignment[order_id] = destination
    del candidate.vehicles[source]
    candidate.remove_empty_vehicles()
    return candidate


def directed_merge_counts(
    runtime: Mapping[str, Any], instance: Any, solution: Any
) -> dict[str, Any]:
    vehicle_ids = sorted(
        vehicle_id
        for vehicle_id, vehicle in solution.vehicles.items()
        if vehicle.order_ids
    )
    profiles = {
        vehicle_id: _profile(runtime, instance, solution, vehicle_id)
        for vehicle_id in vehicle_ids
    }
    formal = 0
    champion = 0
    r3 = 0
    for source in vehicle_ids:
        source_profile = profiles[source]
        for destination in vehicle_ids:
            if source == destination:
                continue
            destination_profile = profiles[destination]
            pallets = source_profile["pallets"] + destination_profile["pallets"]
            hazard = source_profile["hazard"] + destination_profile["hazard"]
            vehicle_type = _minimum_type(runtime["models"], pallets, hazard)
            if vehicle_type is None:
                continue

            if len(source_profile["order_ids"]) <= len(
                destination_profile["order_ids"]
            ):
                champion += 1

            r3_eligible = (
                source_profile["source_unlocked"]
                and source_profile["regions"] == destination_profile["regions"]
                and len(source_profile["regions"]) == 1
                and source_profile["categories"] == destination_profile["categories"]
                and len(source_profile["categories"]) == 1
            )
            if r3_eligible:
                region = next(iter(source_profile["regions"]))
                if len(
                    source_profile["pickups"] | destination_profile["pickups"]
                ) > runtime["models"].get_max_pickups(region):
                    r3_eligible = False
            if r3_eligible:
                for key in sorted(
                    set(source_profile["amounts"]) | set(destination_profile["amounts"])
                ):
                    value = source_profile["amounts"].get(
                        key, 0.0
                    ) + destination_profile["amounts"].get(key, 0.0)
                    limit = instance.amount_limits.get(key)
                    if limit is not None and value > limit:
                        r3_eligible = False
                        break
            if r3_eligible:
                r3 += 1

            # Cheap necessary checks precede the authoritative reconstructed Oracle.
            if (
                source_profile["regions"] != destination_profile["regions"]
                or len(source_profile["regions"]) != 1
                or source_profile["categories"] != destination_profile["categories"]
                or len(source_profile["categories"]) != 1
            ):
                continue
            candidate = _merged_solution(
                runtime, instance, solution, source, destination
            )
            if candidate is None:
                continue
            result = runtime["oracle"].check_feasibility(candidate, instance, phase=1)
            if result.is_feasible:
                formal += 1
    return {
        "formal_compatible_directed_pairs": formal,
        "champion_merge_eligible_directed_pairs": champion,
        "r3_merge_eligible_directed_pairs": r3,
        "formal_counting_contract_sha256": canonical_sha256(FORMAL_COUNTER_CONTRACT),
        "champion_counting_contract_sha256": canonical_sha256(
            CHAMPION_COUNTER_CONTRACT
        ),
        "r3_counting_contract_sha256": canonical_sha256(R3_COUNTER_CONTRACT),
    }


def _greedy_fact(
    runtime: Mapping[str, Any], case: Mapping[str, Any], case_path: Path, seed: int
) -> dict[str, Any]:
    instance = runtime["solver"].load_instance(case_path, phase=1)
    initial = runtime["greedy"].greedy_init(instance, Random(seed))
    initial.objective = runtime["oracle"].recompute_objective(initial, instance)
    feasibility = runtime["oracle"].check_feasibility(initial, instance, phase=1)
    canonical = canonical_solution(initial)
    groups: dict[str, list[str]] = {}
    for order_id, order in instance.orders.items():
        if order.locked_vehicle_id is not None:
            groups.setdefault(order.locked_vehicle_id, []).append(order_id)
    group_vehicle_map = {
        group_id: initial.assignment[sorted(order_ids)[0]]
        for group_id, order_ids in sorted(groups.items())
    }
    return {
        "stable_case_id": case["stable_case_id"],
        "seed": seed,
        "initial_solution_sha256": canonical_sha256(
            {"domain": "scion.warehouse_w3_greedy_solution.v1", "solution": canonical}
        ),
        "initial_objective": {
            "subcategory_splits": initial.objective.subcategory_splits,
            "total_cost": initial.objective.total_cost,
        },
        "oracle_feasible": bool(feasibility.is_feasible),
        "oracle_issue_codes": [
            str(value).split(":", 1)[0] for value in feasibility.violations
        ],
        "vehicle_count": len(canonical["vehicles"]),
        "order_count": len(instance.orders),
        "locked_group_count": len(groups),
        "locked_order_count": sum(len(value) for value in groups.values()),
        "initial_group_vehicle_map": group_vehicle_map,
        "merge_pair_counts": directed_merge_counts(runtime, instance, initial),
    }


def _counter_fixture_proof(staging: Path) -> dict[str, Any]:
    from scion.problems.warehouse_delivery.w3_counter_fixtures import (
        FIXTURE_IDS,
        FIXTURE_SCHEMA,
        champion_executable_pairs,
        fixture,
        formal_oracle_pairs,
        r3_frozen_predicate_pairs,
    )

    partial: dict[str, dict[str, Any]] = {}
    with workspace_runtime(staging / "workspaces" / "champion") as champion_runtime:
        for fixture_id in FIXTURE_IDS:
            champion_instance, champion_solution = fixture(champion_runtime, fixture_id)
            counted = directed_merge_counts(
                champion_runtime, champion_instance, champion_solution
            )
            formal_pairs = formal_oracle_pairs(
                champion_runtime, champion_instance, champion_solution
            )
            champion_pairs = champion_executable_pairs(
                champion_runtime, champion_instance, champion_solution
            )
            partial[fixture_id] = {
                "counter_result": counted,
                "formal_oracle_pairs": formal_pairs,
                "champion_executable_pairs": champion_pairs,
            }
    with workspace_runtime(staging / "workspaces" / "cumulative") as r3_runtime:
        for fixture_id in FIXTURE_IDS:
            r3_instance, r3_solution = fixture(r3_runtime, fixture_id)
            partial[fixture_id]["r3_frozen_predicate_pairs"] = (
                r3_frozen_predicate_pairs(r3_runtime, r3_instance, r3_solution)
            )

    rows: list[dict[str, Any]] = []
    for fixture_id in FIXTURE_IDS:
        values = partial[fixture_id]
        counted = values["counter_result"]
        formal_pairs = values["formal_oracle_pairs"]
        champion_pairs = values["champion_executable_pairs"]
        r3_pairs = values["r3_frozen_predicate_pairs"]
        passed = (
            counted["formal_compatible_directed_pairs"] == len(formal_pairs)
            and counted["champion_merge_eligible_directed_pairs"] == len(champion_pairs)
            and counted["r3_merge_eligible_directed_pairs"] == len(r3_pairs)
        )
        rows.append(
            {
                "fixture_id": fixture_id,
                "formal_oracle_pairs": [list(pair) for pair in sorted(formal_pairs)],
                "champion_executable_pairs": [
                    list(pair) for pair in sorted(champion_pairs)
                ],
                "r3_frozen_predicate_pairs": [list(pair) for pair in sorted(r3_pairs)],
                "counter_result": counted,
                "passed": passed,
            }
        )
    if not all(row["passed"] for row in rows):
        raise WarehouseW3Error("directed counter fixture proof failed")
    proof = {
        "schema": "scion.warehouse_w3_directed_counter_proof.v1",
        "fixture_schema": FIXTURE_SCHEMA,
        "rows": rows,
        "passed": True,
    }
    proof["proof_sha256"] = canonical_sha256(proof)
    return proof


def _cells(case_contract: Mapping[str, Any]) -> list[dict[str, Any]]:
    cells: list[dict[str, Any]] = []
    specifications = (
        ("screening", case_contract["screening_selected"], (42, 137)),
        ("validation", case_contract["validation_selected"], (7, 19, 83)),
    )
    global_ordinal = 0
    for stage, cases, seeds in specifications:
        stage_ordinal = 0
        for case in cases:
            for seed in seeds:
                cells.append(
                    {
                        "cell_ordinal": global_ordinal,
                        "stage_cell_ordinal": stage_ordinal,
                        "stage": stage,
                        "stable_case_id": case["stable_case_id"],
                        "seed": seed,
                        "phase": 1,
                        "scientific_time_limit_seconds": 30,
                        "max_iterations": 200,
                    }
                )
                global_ordinal += 1
                stage_ordinal += 1
    if len(cells) != 43:
        raise WarehouseW3Error(f"expected 43 cells, got {len(cells)}")
    return cells


def build_schedule(
    cells: Sequence[Mapping[str, Any]], arms: Sequence[Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    arm_by_name = {str(arm["name"]): arm for arm in arms}
    jobs: list[dict[str, Any]] = []
    for cell in cells:
        sequence = WILLIAMS[int(cell["stage_cell_ordinal"]) % 4]
        for position, arm_name in enumerate(sequence):
            arm = arm_by_name[arm_name]
            jobs.append(
                {
                    "job_ordinal": len(jobs),
                    "cell_ordinal": cell["cell_ordinal"],
                    "stage_cell_ordinal": cell["stage_cell_ordinal"],
                    "stage": cell["stage"],
                    "stable_case_id": cell["stable_case_id"],
                    "seed": cell["seed"],
                    "arm": arm_name,
                    "arm_sha256": arm["arm_sha256"],
                    "arm_position": position,
                    "phase": 1,
                    "scientific_time_limit_seconds": 30,
                    "max_iterations": 200,
                }
            )
    if len(jobs) != 172:
        raise WarehouseW3Error(f"expected 172 jobs, got {len(jobs)}")

    balance: dict[str, Any] = {}
    for stage in ("screening", "validation"):
        stage_jobs = [job for job in jobs if job["stage"] == stage]
        positions = {
            arm: [
                sum(
                    job["arm"] == arm and job["arm_position"] == pos
                    for job in stage_jobs
                )
                for pos in range(4)
            ]
            for arm in ARM_ORDER
        }
        carryover = {
            f"{left}->{right}": 0
            for left in ARM_ORDER
            for right in ARM_ORDER
            if left != right
        }
        stage_cells = [cell for cell in cells if cell["stage"] == stage]
        for cell in stage_cells:
            sequence = WILLIAMS[int(cell["stage_cell_ordinal"]) % 4]
            for left, right in zip(sequence, sequence[1:]):
                carryover[f"{left}->{right}"] += 1
        balance[stage] = {"positions": positions, "first_order_carryover": carryover}
    if any(
        values != [7, 7, 7, 7] for values in balance["screening"]["positions"].values()
    ):
        raise WarehouseW3Error("screening Williams positions are not exactly balanced")
    if len(set(balance["screening"]["first_order_carryover"].values())) != 1:
        raise WarehouseW3Error("screening Williams carryover is not exactly balanced")
    return jobs, balance


def _native_libraries(executable: Path) -> list[dict[str, Any]]:
    try:
        completed = subprocess.run(
            ["ldd", str(executable)],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise WarehouseW3Error(
            f"cannot resolve Python native libraries: {exc}"
        ) from exc
    paths: set[Path] = set()
    for line in completed.stdout.splitlines():
        tokens = line.strip().split()
        candidate: str | None = None
        if "=>" in tokens:
            index = tokens.index("=>")
            if index + 1 < len(tokens) and tokens[index + 1].startswith("/"):
                candidate = tokens[index + 1]
        elif tokens and tokens[0].startswith("/"):
            candidate = tokens[0]
        if candidate is not None:
            paths.add(Path(candidate).resolve(strict=True))
    return [
        _identity(path)
        for path in sorted(paths, key=lambda value: str(value).encode("utf-8"))
    ]


def execution_environment() -> dict[str, str]:
    return {
        "HOME": os.environ.get("HOME", ""),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": os.environ.get("PATH", ""),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1",
    }


def _invocation_contract(environment: Mapping[str, str]) -> dict[str, Any]:
    return {
        "opaque_job_key": "warehouse-w3-{job_ordinal:03d}",
        "argv": [
            "{python}",
            "-B",
            "-s",
            "{workspace}/solver.py",
            "{sealed_case}",
            "--phase",
            "1",
            "--seed",
            "{seed}",
            "--time-limit",
            "30",
            "--max-iter",
            "200",
            "--registry",
            "{workspace}/registry.yaml",
        ],
        "cwd": "{workspace}",
        "environment": dict(environment),
        "case_from_sealed_root_only": True,
        "solver_payload_stream": "complete_stdout",
        "stderr_is_observation_only": True,
        "problem_layer_process_authority": False,
        "generic_runtime_required": "SpawnBackend",
    }


def _manifest_entry(
    values: Sequence[Mapping[str, Any]], key: str, expected: str
) -> Mapping[str, Any]:
    matches = [entry for entry in values if entry.get(key) == expected]
    if len(matches) != 1:
        raise WarehouseW3Error(f"manifest identity is not unique: {key}={expected}")
    return matches[0]


def process_spec_for_job(
    root: Path, manifest: Mapping[str, Any], job: Mapping[str, Any]
) -> "GenericProcessSpec":
    """Build one inert generic process fact; this function starts no process."""

    from scion.runtime.execution import GenericProcessSpec

    root = _absolute(root)
    workspace_entry = _manifest_entry(manifest["workspaces"], "arm", str(job["arm"]))
    case_entry = _manifest_entry(
        manifest["cases"], "stable_case_id", str(job["stable_case_id"])
    )
    workspace = root / str(workspace_entry["relative_path"])
    case_path = root / str(case_entry["sealed_relative_path"])
    contract = manifest["invocation_contract"]
    replacements = {
        "python": str(manifest["toolchain"]["python"]["executable"]),
        "workspace": str(workspace),
        "sealed_case": str(case_path),
        "seed": str(job["seed"]),
        "job_ordinal": int(job["job_ordinal"]),
    }
    argv = tuple(
        str(value).format(**replacements).encode("utf-8")
        for value in contract["argv"]
    )
    environment = tuple(
        sorted(
            f"{key}={value}".encode("utf-8")
            for key, value in contract["environment"].items()
        )
    )
    return GenericProcessSpec.create(
        opaque_job_key=str(contract["opaque_job_key"]).format(**replacements),
        executable=argv[0],
        argv=argv,
        environment=environment,
        cwd=str(workspace).encode("utf-8"),
    )


def _python_isolation_probe(
    executable: Path,
    workspace: Path,
    environment: Mapping[str, str],
    workspace_identity: Path,
) -> dict[str, Any]:
    script = r"""
import json, pathlib, site, sys, yaml
sys.path[0] = str(pathlib.Path.cwd().resolve())
site_dirs = [pathlib.Path(value) for value in site.getsitepackages()]
pth = []
for directory in site_dirs:
    if directory.is_dir():
        for path in sorted(directory.glob("*.pth")):
            pth.append(str(path.resolve()))
print(json.dumps({
    "sys_path": sys.path,
    "user_site": site.getusersitepackages(),
    "enable_user_site": site.ENABLE_USER_SITE,
    "user_site_on_sys_path": site.getusersitepackages() in sys.path,
    "site_packages": [str(path.resolve()) for path in site_dirs],
    "pth_paths": pth,
    "yaml_path": str(pathlib.Path(yaml.__file__).resolve()),
    "yaml_version": yaml.__version__,
}, sort_keys=True))
"""
    try:
        completed = subprocess.run(
            [str(executable), "-B", "-s", "-c", script],
            cwd=workspace,
            env=dict(environment),
            check=True,
            capture_output=True,
            text=True,
        )
        value = json.loads(completed.stdout)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        raise WarehouseW3Error(f"cannot probe isolated Python path: {exc}") from exc
    if (
        value["enable_user_site"] is not False
        or value["user_site_on_sys_path"] is not False
    ):
        raise WarehouseW3Error(
            "Python user site is active in the W3 execution environment"
        )
    pth_files = [_identity(Path(path)) for path in value.pop("pth_paths")]
    actual_workspace = str(workspace.resolve(strict=True))
    expected_workspace = str(workspace_identity)
    value["sys_path"] = [
        expected_workspace if item == actual_workspace else item
        for item in value["sys_path"]
    ]
    value["yaml_source"] = _identity(Path(value.pop("yaml_path")))
    value["pth_files"] = pth_files
    value["flags"] = ["-B", "-s"]
    value["environment"] = dict(environment)
    return value


def _toolchain(
    workspace: Path | None = None,
    environment: Mapping[str, str] | None = None,
    workspace_identity: Path | None = None,
) -> dict[str, Any]:
    executable = Path(sys.executable).resolve()
    workspace = workspace or repository_root()
    workspace_identity = workspace_identity or workspace
    environment = dict(environment or execution_environment())
    isolation = _python_isolation_probe(
        executable, workspace, environment, workspace_identity
    )
    return {
        "python": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
            "executable": str(executable),
            "executable_sha256": read_regular(executable).sha256,
        },
        "platform": platform.platform(),
        "dependencies": {
            "pyyaml_version": isolation["yaml_version"],
            "pyyaml_source": isolation["yaml_source"],
        },
        "native_libraries": _native_libraries(executable),
        "python_isolation": isolation,
    }


def _git(root: Path, *arguments: str, text: bool = False) -> bytes | str:
    try:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=root,
            check=True,
            capture_output=True,
            text=text,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        stderr = getattr(exc, "stderr", b"")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        raise WarehouseW3Error(
            f"cannot read exact Git source object ({' '.join(arguments)}): {stderr}"
        ) from exc
    return completed.stdout


def _resolve_source_commit(root: Path, requested: str | None) -> tuple[str, list[str]]:
    revision = requested or "HEAD"
    commit = str(_git(root, "rev-parse", "--verify", f"{revision}^{{commit}}", text=True)).strip()
    head = str(_git(root, "rev-parse", "--verify", "HEAD", text=True)).strip()
    if len(commit) != 40 or any(char not in "0123456789abcdef" for char in commit):
        raise WarehouseW3Error("source commit is not a full lowercase Git object id")
    if commit != head:
        raise WarehouseW3Error("source commit must equal the checked-out HEAD")
    status = str(
        _git(root, "status", "--porcelain=v1", "--untracked-files=all", text=True)
    )
    if status:
        raise WarehouseW3Error("source checkout must be clean before dry-root preparation")
    remote_lines = str(
        _git(root, "branch", "-r", "--contains", commit, text=True)
    ).splitlines()
    remote_refs = sorted(line.strip() for line in remote_lines if line.strip())
    if not remote_refs:
        raise WarehouseW3Error("source commit is not present on a remote-tracking ref")
    return commit, remote_refs


def _git_blob(root: Path, commit: str, relative: str) -> tuple[Snapshot, str]:
    path = Path(relative)
    if path.is_absolute() or not path.parts or any(
        part in {"", ".", ".."} for part in path.parts
    ):
        raise WarehouseW3Error(f"invalid Git source path: {relative}")
    object_name = f"{commit}:{relative}"
    blob_oid = str(_git(root, "rev-parse", "--verify", object_name, text=True)).strip()
    if len(blob_oid) != 40 or any(char not in "0123456789abcdef" for char in blob_oid):
        raise WarehouseW3Error(f"Git source is not a SHA-1 blob identity: {relative}")
    kind = str(_git(root, "cat-file", "-t", blob_oid, text=True)).strip()
    if kind != "blob":
        raise WarehouseW3Error(f"Git source is not a blob: {relative}")
    data = _git(root, "cat-file", "blob", blob_oid)
    if not isinstance(data, bytes):
        raise AssertionError("binary Git blob read unexpectedly returned text")
    return Snapshot(root / relative, data, sha256_bytes(data), len(data)), blob_oid


def _git_blob_entry(
    root: Path,
    staging: Path,
    commit: str,
    relative: str,
    *,
    sealed_prefix: str = "sealed/repository",
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    snapshot, blob_oid = _git_blob(root, commit, relative)
    if expected_sha256 is not None and snapshot.sha256 != expected_sha256:
        raise WarehouseW3Error(
            f"Git blob SHA-256 mismatch for {relative}: "
            f"expected {expected_sha256}, got {snapshot.sha256}"
        )
    sealed_path = f"{sealed_prefix}/{relative}"
    destination = staging / sealed_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    copied = _copy_snapshot(snapshot, destination)
    return {
        "source_path": relative,
        "sealed_path": sealed_path,
        "sha256": copied["sha256"],
        "size_bytes": copied["size_bytes"],
        "provenance": {
            "kind": "git_blob",
            "commit": commit,
            "path": relative,
            "blob_oid": blob_oid,
        },
    }


def _seal_repository_inputs(
    root: Path, staging: Path, source_commit: str
) -> list[dict[str, Any]]:
    relatives = (
        DESIGN_PATH,
        W1_PATH,
        W2_MANIFEST_PATH,
        W2_RECEIPT_PATH,
        *PROBLEM_INPUTS,
        *PROTOCOL_ANALYSIS_SOURCES,
        *PROBLEM_LAYER_SOURCES,
    )
    sealed: list[dict[str, Any]] = []
    for relative in relatives:
        expected = {
            DESIGN_PATH: DESIGN_SHA256,
            W1_PATH: W1_SHA256,
            W2_MANIFEST_PATH: W2_MANIFEST_SHA256,
            W2_RECEIPT_PATH: W2_RECEIPT_SHA256,
        }.get(relative)
        sealed.append(
            _git_blob_entry(
                root,
                staging,
                source_commit,
                relative,
                expected_sha256=expected,
            )
        )
    return sealed


def _seal_w2_preservation_inputs(
    root: Path, staging: Path, w2: Mapping[str, Any], source_commit: str
) -> list[dict[str, Any]]:
    """Seal every exact byte input behind the accepted W2 preservation pass."""

    sources: dict[tuple[str, str], tuple[Path, str | None]] = {}
    for entry in w2["protected_current_runtime"]:
        sources[("repository", entry["path"])] = (
            root / entry["path"],
            entry["sha256"],
        )
    owners = w2["allowed_semantic_text_owners"]
    owner_entries = (
        list(owners["python_docstring_only"])
        + list(owners["python_exact_code_plus_docstrings"])
        + list(owners["markdown"])
        + list(owners["yaml_guidance_only"])
        + [owners["adapter_exact_reverse_replacement"]]
    )
    for entry in owner_entries:
        path = str(entry["path"])
        # W2 admits reviewed post-W2 semantic text, so bind the source-commit blob.
        sources[("repository_owner", path)] = (root / path, None)
    r3 = w2["r3"]
    r3_root = Path(r3["root"])
    for entry in r3["evidence_files"]:
        sources[("r3", entry["path"])] = (r3_root / entry["path"], entry["sha256"])
    derivation = r3["arm_derivation"]
    for entry in (
        derivation["champion_operator_files"] + derivation["workspace_replacements"]
    ):
        sources[("r3_arm", entry["path"])] = (
            r3_root / entry["path"],
            entry["sha256"],
        )

    sealed: list[dict[str, Any]] = []
    for (scope, source_path), (absolute, expected) in sorted(sources.items()):
        sealed_prefix = f"sealed/w2_preservation_inputs/{scope}"
        if scope in {"repository", "repository_owner"}:
            entry = _git_blob_entry(
                root,
                staging,
                source_commit,
                source_path,
                sealed_prefix=sealed_prefix,
                expected_sha256=expected,
            )
            entry["scope"] = scope
            sealed.append(entry)
            continue
        snapshot = read_regular(absolute, expected_sha256=expected)
        sealed_path = f"{sealed_prefix}/{source_path}"
        destination = staging / sealed_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        copied = _copy_snapshot(snapshot, destination)
        sealed.append(
            {
                "scope": scope,
                "source_path": source_path,
                "sealed_path": sealed_path,
                "sha256": copied["sha256"],
                "size_bytes": copied["size_bytes"],
                "provenance": {
                    "kind": "external_evidence",
                    "protected_root": str(R3_ROOT),
                    "path": str(absolute),
                    "expected_sha256": expected,
                },
            }
        )
    return sealed


def _seal_cases_and_metrics(
    staging: Path, case_contract: Mapping[str, Any], snapshots: Mapping[str, Snapshot]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cases: list[dict[str, Any]] = []
    all_cases = (
        list(case_contract["screening_selected"])
        + list(case_contract["validation_selected"])
        + list(case_contract["w1_bound_not_selected"])
    )
    for case in all_cases:
        stage = str(case["stable_case_id"]).split("/")[1]
        basename = Path(str(case["lexical_path"])).name
        destination = staging / "cases" / stage / basename
        destination.parent.mkdir(parents=True, exist_ok=True)
        copied = _copy_snapshot(snapshots[str(case["stable_case_id"])], destination)
        copied.update(dict(case))
        copied["sealed_relative_path"] = str(destination.relative_to(staging))
        copied.pop("sealed_path", None)
        copied["provenance"] = {
            "kind": "external_evidence",
            "path": str(case["lexical_path"]),
            "expected_sha256": case["content_sha256"],
        }
        cases.append(copied)
    metrics: list[dict[str, Any]] = []
    for entry in case_contract["historical_metrics"]:
        label = str(entry["label"])
        destination = staging / "sealed" / "historical_metrics" / f"{label}.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        copied = _copy_snapshot(snapshots[f"metric/{label}"], destination)
        copied.update(dict(entry))
        copied["sealed_relative_path"] = str(destination.relative_to(staging))
        copied.pop("sealed_path", None)
        copied["provenance"] = {
            "kind": "external_evidence",
            "protected_root": entry["protected_root"],
            "path": str(Path(entry["protected_root"]) / entry["relative_path"]),
            "expected_sha256": entry["sha256"],
        }
        metrics.append(copied)
    return cases, metrics


def _protocol_gate_contract_from_snapshots(
    protocol_snapshot: Snapshot,
    problem_snapshot: Snapshot,
    gate_sources: Mapping[str, Snapshot],
) -> dict[str, Any]:
    protocol = load_unique_yaml(protocol_snapshot.data, label="Warehouse Protocol")
    problem = load_unique_yaml(problem_snapshot.data, label="Warehouse problem spec")
    measurement = problem["measurement"]
    effect_scale = measurement["effect_scale"]
    screening = protocol["gates"]["screening"]
    validation = protocol["gates"]["validation"]
    borderline = screening["expanded_borderline_advance"]

    def resolve_delta(raw: Any) -> float:
        if isinstance(raw, str):
            raw = effect_scale[raw]
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise WarehouseW3Error("Protocol practical delta is not numeric")
        return float(raw)

    contract: dict[str, Any] = {
        "schema": "scion.warehouse_w3_protocol_gate_derivation.v1",
        "source": {
            "protocol_sha256": protocol_snapshot.sha256,
            "problem_sha256": problem_snapshot.sha256,
        },
        "quality_only_runtime_observation_excluded": True,
        "failed_pairs": 0,
        "candidate_failed_pairs": 0,
        "runtime_ratio_median": None,
        "runtime_regression_rate": None,
        "pairing_validity": measurement["pairing_validity"],
        "runtime_model": measurement["runtime_model"],
        "screening": {
            "win_rate_min": float(screening["win_rate_min"]),
            "practical_delta_min": resolve_delta(screening["median_delta_min"]),
            "expanded_borderline_advance": dict(borderline),
        },
        "validation": {
            "win_rate_min": float(validation["win_rate_min"]),
            "practical_delta_min": resolve_delta(validation["median_delta_min"]),
            "bootstrap_ci_low_min": float(validation["bootstrap_ci_low_min"]),
            "bootstrap_n": int(validation.get("bootstrap_n", 10000)),
            "expanded_case_count": int(protocol["validation"]["expand_to"]),
        },
        "gate_source_sha256": gate_sources["gates"].sha256,
        "stats_source_sha256": gate_sources["stats"].sha256,
        "feedback_source_sha256": gate_sources["feedback"].sha256,
    }
    contract["contract_sha256"] = canonical_sha256(contract)
    return contract


def _protocol_gate_contract(root: Path) -> dict[str, Any]:
    return _protocol_gate_contract_from_snapshots(
        read_regular(root / "scion/problems/warehouse_delivery/protocol_prod.yaml"),
        read_regular(root / "scion/problems/warehouse_delivery/problem-v1.yaml"),
        {
            "gates": read_regular(root / "scion/scion/protocol/gates.py"),
            "stats": read_regular(root / "scion/scion/protocol/stats.py"),
            "feedback": read_regular(
                root / "scion/scion/protocol/experiment/feedback.py"
            ),
        },
    )


def _verify_w2_before_prepare(root: Path) -> dict[str, Any]:
    # Imported only during preparation.  Formal run/replay needs no repository.
    from scion.problems.warehouse_delivery.w2_preservation import verify_w2_preservation

    verification = verify_w2_preservation(root / W2_MANIFEST_PATH)
    if verification["manifest_sha256"] != W2_MANIFEST_SHA256:
        raise WarehouseW3Error("W2 preservation verification returned wrong manifest")
    return verification


def _source_receipt(
    source_commit: str,
    remote_refs: Sequence[str],
    repository_inputs: Sequence[Mapping[str, Any]],
    w2_inputs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    git_blob_inputs = [
        dict(entry)
        for entry in (*repository_inputs, *w2_inputs)
        if entry["provenance"]["kind"] == "git_blob"
    ]
    receipt: dict[str, Any] = {
        "schema": SOURCE_RECEIPT_SCHEMA,
        "source_commit": source_commit,
        "pushed_remote_refs": list(remote_refs),
        "git_blob_inputs": git_blob_inputs,
        "git_blob_aggregate_sha256": canonical_sha256(
            {
                "domain": "scion.warehouse_w3_git_blob_closure.v1",
                "items": git_blob_inputs,
            }
        ),
        "working_tree_bytes_used_for_sealed_repository_inputs": False,
        "formal_jobs_started": 0,
    }
    return receipt


def _load_source_receipt(root: Path) -> dict[str, Any]:
    snapshot = read_regular(root / SOURCE_RECEIPT_NAME)
    try:
        receipt = json.loads(snapshot.data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WarehouseW3Error("W3 source receipt is not valid JSON") from exc
    if (
        not isinstance(receipt, dict)
        or render_json(receipt) != snapshot.data
        or receipt.get("schema") != SOURCE_RECEIPT_SCHEMA
        or receipt.get("working_tree_bytes_used_for_sealed_repository_inputs")
        is not False
        or receipt.get("formal_jobs_started") != 0
    ):
        raise WarehouseW3Error("W3 source receipt contract mismatch")
    entries = receipt.get("git_blob_inputs")
    if not isinstance(entries, list) or not entries:
        raise WarehouseW3Error("W3 source receipt has no Git blob closure")
    commit = receipt.get("source_commit")
    if (
        not isinstance(commit, str)
        or len(commit) != 40
        or any(char not in "0123456789abcdef" for char in commit)
    ):
        raise WarehouseW3Error("W3 source receipt commit is not canonical")
    recorded_refs = receipt.get("pushed_remote_refs")
    if not isinstance(recorded_refs, list) or not recorded_refs or not all(
        isinstance(ref, str) and ref for ref in recorded_refs
    ):
        raise WarehouseW3Error("W3 source receipt has no pushed remote ref")
    current_refs = {
        line.strip()
        for line in str(
            _git(repository_root(), "branch", "-r", "--contains", commit, text=True)
        ).splitlines()
        if line.strip()
    }
    if not current_refs.intersection(recorded_refs):
        raise WarehouseW3Error("W3 source commit is no longer on its recorded remote ref")
    expected_aggregate = canonical_sha256(
        {
            "domain": "scion.warehouse_w3_git_blob_closure.v1",
            "items": entries,
        }
    )
    if receipt.get("git_blob_aggregate_sha256") != expected_aggregate:
        raise WarehouseW3Error("W3 source receipt aggregate mismatch")
    return receipt


def _verify_sealed_git_entry(
    root: Path, receipt: Mapping[str, Any], sealed_path: str
) -> dict[str, Any]:
    matches = [
        entry
        for entry in receipt["git_blob_inputs"]
        if entry.get("sealed_path") == sealed_path
    ]
    if len(matches) != 1:
        raise WarehouseW3Error(f"Git blob source identity is not unique: {sealed_path}")
    entry = dict(matches[0])
    provenance = entry.get("provenance")
    if not isinstance(provenance, dict) or provenance.get("kind") != "git_blob":
        raise WarehouseW3Error(f"Git blob provenance is malformed: {sealed_path}")
    if provenance.get("commit") != receipt["source_commit"]:
        raise WarehouseW3Error(f"Git blob commit differs from source receipt: {sealed_path}")
    sealed = read_regular(root / sealed_path, expected_sha256=entry["sha256"])
    if sealed.size_bytes != entry["size_bytes"]:
        raise WarehouseW3Error(f"sealed Git blob size mismatch: {sealed_path}")
    git_snapshot, blob_oid = _git_blob(
        repository_root(), provenance["commit"], provenance["path"]
    )
    if (
        blob_oid != provenance.get("blob_oid")
        or git_snapshot.data != sealed.data
        or provenance.get("path") != entry.get("source_path")
    ):
        raise WarehouseW3Error(f"sealed bytes differ from Git blob: {sealed_path}")
    return entry


def _sealed_repository_entries(root: Path) -> list[dict[str, Any]]:
    receipt = _load_source_receipt(root)
    relatives = (
        DESIGN_PATH,
        W1_PATH,
        W2_MANIFEST_PATH,
        W2_RECEIPT_PATH,
        *PROBLEM_INPUTS,
        *PROTOCOL_ANALYSIS_SOURCES,
        *PROBLEM_LAYER_SOURCES,
    )
    return [
        _verify_sealed_git_entry(
            root, receipt, f"sealed/repository/{relative}"
        )
        for relative in relatives
    ]


def _sealed_w2_entries(root: Path, w2: Mapping[str, Any]) -> list[dict[str, Any]]:
    receipt = _load_source_receipt(root)
    specs: dict[tuple[str, str], str | None] = {}
    for entry in w2["protected_current_runtime"]:
        specs[("repository", entry["path"])] = entry["sha256"]
    owners = w2["allowed_semantic_text_owners"]
    owner_entries = (
        list(owners["python_docstring_only"])
        + list(owners["python_exact_code_plus_docstrings"])
        + list(owners["markdown"])
        + list(owners["yaml_guidance_only"])
        + [owners["adapter_exact_reverse_replacement"]]
    )
    for entry in owner_entries:
        specs[("repository_owner", entry["path"])] = None
    r3 = w2["r3"]
    for entry in r3["evidence_files"]:
        specs[("r3", entry["path"])] = entry["sha256"]
    derivation = r3["arm_derivation"]
    for entry in (
        derivation["champion_operator_files"] + derivation["workspace_replacements"]
    ):
        specs[("r3_arm", entry["path"])] = entry["sha256"]

    entries: list[dict[str, Any]] = []
    for (scope, source_path), expected in sorted(specs.items()):
        sealed_path = f"sealed/w2_preservation_inputs/{scope}/{source_path}"
        if scope in {"repository", "repository_owner"}:
            entry = _verify_sealed_git_entry(root, receipt, sealed_path)
            if expected is not None and entry["sha256"] != expected:
                raise WarehouseW3Error(
                    f"sealed W2 Git input differs from W2: {source_path}"
                )
            entries.append(entry)
            continue
        snapshot = read_regular(
            root / sealed_path,
            expected_sha256=expected,
        )
        entries.append(
            {
                "scope": scope,
                "source_path": source_path,
                "sealed_path": sealed_path,
                "sha256": snapshot.sha256,
                "size_bytes": snapshot.size_bytes,
                "provenance": {
                    "kind": "external_evidence",
                    "protected_root": str(R3_ROOT),
                    "path": str(R3_ROOT / source_path),
                    "expected_sha256": expected,
                },
            }
        )
    return entries


def _sealed_case_contract(
    root: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    split_snapshot = read_regular(
        root
        / "sealed/repository/scion/problems/warehouse_delivery/split_manifest_prod.yaml"
    )
    w1_snapshot = read_regular(root / f"sealed/repository/{W1_PATH}")
    split = load_unique_yaml(split_snapshot.data, label="sealed Warehouse split")
    w1 = json.loads(w1_snapshot.data)
    populations = {row["stage"]: row for row in w1["populations"]}
    cases_by_stage: dict[str, list[dict[str, Any]]] = {}
    all_cases: list[dict[str, Any]] = []
    for stage in ("screening", "validation"):
        lexical_paths = [str(value) for value in split[stage]]
        cases: list[dict[str, Any]] = []
        for index, lexical_path in enumerate(lexical_paths):
            if (
                not Path(lexical_path).is_absolute()
                or os.path.abspath(lexical_path) != lexical_path
            ):
                raise WarehouseW3Error(
                    f"sealed W1 case path is not absolute canonical: {lexical_path}"
                )
            sealed_relative = f"cases/{stage}/{Path(lexical_path).name}"
            snapshot = read_regular(root / sealed_relative)
            case = {
                "stable_case_id": _stable_case_id(stage, lexical_path),
                "manifest_index": index,
                "lexical_path": lexical_path,
                "resolved_path": lexical_path,
                "regular_file": True,
                "symlink_free": True,
                "size_bytes": snapshot.size_bytes,
                "content_sha256": snapshot.sha256,
                "sha256": snapshot.sha256,
                "sealed_relative_path": sealed_relative,
                "provenance": {
                    "kind": "external_evidence",
                    "path": lexical_path,
                    "expected_sha256": snapshot.sha256,
                },
            }
            cases.append(case)
            all_cases.append(case)
        if (
            canonical_sha256([_content_identity(case) for case in cases])
            != populations[stage]["population_sha256"]
        ):
            raise WarehouseW3Error(f"sealed {stage} population differs from W1")
        if (
            canonical_sha256(lexical_paths)
            != populations[stage]["manifest_order_sha256"]
        ):
            raise WarehouseW3Error(f"sealed {stage} order differs from W1")
        cases_by_stage[stage] = cases

    metrics: dict[str, dict[str, Any]] = {}
    metric_entries: list[dict[str, Any]] = []
    for label, protected_root, relative, expected in HISTORICAL_METRICS:
        sealed_relative = f"sealed/historical_metrics/{label}.json"
        snapshot = read_regular(root / sealed_relative, expected_sha256=expected)
        metrics[label] = json.loads(snapshot.data)
        metric_entries.append(
            {
                "label": label,
                "protected_root": str(protected_root),
                "relative_path": str(relative),
                "sha256": snapshot.sha256,
                "size_bytes": snapshot.size_bytes,
                "sealed_relative_path": sealed_relative,
                "provenance": {
                    "kind": "external_evidence",
                    "protected_root": str(protected_root),
                    "path": str(protected_root / relative),
                    "expected_sha256": expected,
                },
            }
        )
    by_lexical = {
        case["lexical_path"]: case
        for cases in cases_by_stage.values()
        for case in cases
    }
    selections: dict[str, tuple[list[dict[str, Any]], list[str], str, str]] = {}
    expected = {
        "r3_initial_screening": (
            "2ca79d833c7a54b6a18f826c9a9c7bdebe47b7ae9e3a406fc096811d66f37c07",
            "d37bb880ae4667109a31426549993de314e82c03a747ec2fae3bd960cf90512c",
        ),
        "r3_expanded_screening": (
            "02f668e6cd96a4ae8dc2e801215651f5eec53b0297399088c0c9c0a7dbeb2e7f",
            "c103a56bbe995dac7e9fc2bb485f8915615a4e7c9d1b9a4c6c78d43c01104725",
        ),
        "r3_validation": (
            "edf8ce68124b24b8d364be56853152bc6862fc03acff23c2d19dc7093b415b87",
            "b374e25970a059d01f7ee6aa6ba9430d020af001b5ae1b4353d8598421c34a1e",
        ),
    }
    for name, metric_name in (
        ("r3_initial_screening", "r3_initial_screening"),
        ("r3_expanded_screening", "r3_expanded_screening"),
        ("r3_validation", "r3_validation"),
    ):
        paths = [str(value) for value in metrics[metric_name]["case_ids"]]
        try:
            selected = [by_lexical[path] for path in paths]
        except KeyError as exc:
            raise WarehouseW3Error(f"sealed historical case outside W1: {exc}") from exc
        selection_sha, location_sha = expected[name]
        if (
            _selection_sha256(selected) != selection_sha
            or _selection_location_sha256(paths) != location_sha
        ):
            raise WarehouseW3Error(f"sealed W1 selection mismatch: {name}")
        selections[name] = (selected, paths, selection_sha, location_sha)
    initial = selections["r3_initial_screening"][0]
    expanded = selections["r3_expanded_screening"][0]
    validation = selections["r3_validation"][0]
    if (
        tuple(Path(case["lexical_path"]).name for case in initial)
        != INITIAL_SCREENING_BASENAMES
    ):
        raise WarehouseW3Error("sealed initial-six view drifted")
    if len(expanded) != 14 or len(validation) != 5:
        raise WarehouseW3Error("sealed W3 selection is not 14/5")
    expanded_ids = {case["stable_case_id"] for case in expanded}
    not_selected = [
        case
        for case in cases_by_stage["screening"]
        if case["stable_case_id"] not in expanded_ids
    ]
    internal = {
        "historical_metrics": metric_entries,
        "views": {
            name: {
                "selection_sha256": values[2],
                "selection_location_sha256": values[3],
                "stable_case_ids": [case["stable_case_id"] for case in values[0]],
            }
            for name, values in selections.items()
        },
        "screening_selected": expanded,
        "validation_selected": validation,
        "w1_bound_not_selected": not_selected,
        "frozen_and_canary_opened": False,
    }
    manifest_case_order = list(expanded) + list(validation) + list(not_selected)
    if len(manifest_case_order) != len(all_cases):
        raise WarehouseW3Error("sealed manifest case closure is not exhaustive")
    return internal, manifest_case_order, metric_entries


def _sealed_workspace_entries(
    root: Path, arms: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    semantic_reference: dict[str, Any] | None = None
    for arm in arms:
        name = str(arm["name"])
        workspace = root / "workspaces" / name
        tree = _tree_identity(workspace, SOLVER_CLOSURE)
        components = {
            slot: read_regular(workspace / "operators" / f"{slot}.py").sha256
            for slot in ("destroy_rebuild", "merge_vehicles")
        }
        expected_components = {
            item["slot"]: item["sha256"] for item in arm["components"]
        }
        if components != expected_components:
            raise WarehouseW3Error(f"sealed workspace component mismatch: {name}")
        registry = read_regular(
            workspace / "registry.yaml", expected_sha256=EXPECTED_REGISTRY_SHA256
        )
        semantics = registry_semantics(registry.data, label=f"sealed {name} registry")
        if semantic_reference is None:
            semantic_reference = semantics
        elif semantics != semantic_reference:
            raise WarehouseW3Error(
                f"sealed workspace registry semantics mismatch: {name}"
            )
        registry_files = {
            entry["file_path"]: read_regular(workspace / entry["file_path"]).sha256
            for entry in semantics["operators"]
        }
        entries.append(
            {
                "arm": name,
                "arm_sha256": arm["arm_sha256"],
                "relative_path": f"workspaces/{name}",
                "tree": tree,
                "component_sha256": components,
                "registry_raw_sha256": registry.sha256,
                "registry_semantics": semantics,
                "registry_file_sha256": dict(sorted(registry_files.items())),
                "provenance": {
                    "kind": "generated",
                    "derivation": "w2_arm_components_over_frozen_r3_champion",
                    "arm_sha256": arm["arm_sha256"],
                },
            }
        )
    return entries


def _prepared_closure_inventory(root: Path) -> dict[str, list[str]]:
    inventory = inventory_regular_tree(root)
    dynamic_prefixes = ("artifacts/", "control/", "raw/")
    root_controls = {
        "PREPARED_NO_FORMAL_JOBS",
        "warehouse_w3_fixed_arm_manifest.v1.json",
        "warehouse_w3_fixed_arm_manifest.v1.sha256",
    }
    inventory["files"] = [
        path
        for path in inventory["files"]
        if path not in root_controls
        and not any(path.startswith(prefix) for prefix in dynamic_prefixes)
    ]
    return inventory


def derive_manifest_from_sealed_root(root: Path) -> dict[str, Any]:
    """Rebuild every manifest field from sealed bytes and the current closed host."""

    root = _absolute(root)
    source_receipt = _load_source_receipt(root)
    repository_entries = _sealed_repository_entries(root)
    source_by_path = {entry["source_path"]: entry for entry in repository_entries}
    w2_bytes = read_regular(root / f"sealed/repository/{W2_MANIFEST_PATH}").data
    w2 = json.loads(w2_bytes)
    arms = _arms(w2)
    case_contract, cases, historical_metrics = _sealed_case_contract(root)
    workspaces = _sealed_workspace_entries(root, arms)
    cells = _cells(case_contract)
    jobs, balance = build_schedule(cells, arms)
    preflight: list[dict[str, Any]] = []
    case_by_id = {case["stable_case_id"]: case for case in cases}
    champion_workspace = root / "workspaces" / "champion"
    with workspace_runtime(champion_workspace) as runtime:
        for cell in cells:
            case = case_by_id[cell["stable_case_id"]]
            fact = _greedy_fact(
                runtime,
                case,
                root / case["sealed_relative_path"],
                int(cell["seed"]),
            )
            if not fact["oracle_feasible"]:
                raise WarehouseW3Error("sealed greedy initial is infeasible")
            preflight.append(fact)
    environment = execution_environment()
    protocol_gate = _protocol_gate_contract_from_snapshots(
        read_regular(
            root
            / "sealed/repository/scion/problems/warehouse_delivery/protocol_prod.yaml"
        ),
        read_regular(
            root / "sealed/repository/scion/problems/warehouse_delivery/problem-v1.yaml"
        ),
        {
            "gates": read_regular(
                root / "sealed/repository/scion/scion/protocol/gates.py"
            ),
            "stats": read_regular(
                root / "sealed/repository/scion/scion/protocol/stats.py"
            ),
            "feedback": read_regular(
                root / "sealed/repository/scion/scion/protocol/experiment/feedback.py"
            ),
        },
    )
    return {
        "schema": SCHEMA,
        "authority": {
            "design_path": DESIGN_PATH,
            "design_sha256": DESIGN_SHA256,
            "design_git_commit": DESIGN_COMMIT,
            "w1_receipt_path": W1_PATH,
            "w1_receipt_sha256": W1_SHA256,
            "w2_manifest_path": W2_MANIFEST_PATH,
            "w2_manifest_sha256": W2_MANIFEST_SHA256,
            "w2_receipt_path": W2_RECEIPT_PATH,
            "w2_receipt_sha256": W2_RECEIPT_SHA256,
        },
        "source": source_receipt,
        "protected_roots": [
            str(R3_ROOT),
            str(R3_EXPANDED_ROOT),
            str(R3_VALIDATION_ROOT),
        ],
        "output_root": {
            "path": str(root),
            "absent_before_creation": True,
            "parent_device": os.stat(root.parent).st_dev,
        },
        "execution_policy": {
            "retry": False,
            "resume": False,
            "reuse": False,
            "automatic_rerun": False,
            "interim_adaptation": False,
            "maximum_live_solver_processes": 1,
            "outer_launcher_timeout": None,
            "solver_owned_scientific_time_limit_seconds": 30,
        },
        "toolchain": _toolchain(champion_workspace, environment),
        "sealed_repository_inputs": repository_entries,
        "w2_preservation_inputs": _sealed_w2_entries(root, w2),
        "historical_metrics": historical_metrics,
        "case_contract": {
            "views": case_contract["views"],
            "w1_bound_not_selected": [
                case["stable_case_id"]
                for case in case_contract["w1_bound_not_selected"]
            ],
            "frozen_and_canary_opened": False,
        },
        "cases": cases,
        "arms": arms,
        "workspaces": workspaces,
        "registry_contract": {
            "raw_sha256": EXPECTED_REGISTRY_SHA256,
            "r3_raw_sha256": R3_REGISTRY_SHA256,
            "semantic_sha256": workspaces[0]["registry_semantics"]["semantic_sha256"],
            "hardcoded_config_weight_fallback": False,
        },
        "counter_contracts": {
            "formal": FORMAL_COUNTER_CONTRACT,
            "champion": CHAMPION_COUNTER_CONTRACT,
            "r3": R3_COUNTER_CONTRACT,
        },
        "counter_fixture_proof": _counter_fixture_proof(root),
        "cells": cells,
        "greedy_preflight": preflight,
        "jobs": jobs,
        "schedule_balance": balance,
        "invocation_contract": _invocation_contract(environment),
        "analysis_contract": {
            "case_is_statistical_unit": True,
            "seed_majority": "strict_majority_win_or_loss_else_tie",
            "case_measurement": "seed_median",
            "bootstrap": {"seed": 42, "draws": 10000, "alpha": 0.05},
            "source_digests": [
                source_by_path[path] for path in PROTOCOL_ANALYSIS_SOURCES
            ],
            "protocol_gate": protocol_gate,
            "treatment_bundles_not_pure_factorial": True,
            "validation_is_posterior_diagnostic_not_fresh_confirmation": True,
        },
        "problem_layer_sources": [
            source_by_path[path] for path in PROBLEM_LAYER_SOURCES
        ],
        "prepared_closure_inventory": _prepared_closure_inventory(root),
        "preflight_passed": True,
        "formal_jobs_started": 0,
        "formal_execution_authorized": False,
    }


def assert_manifest_rederived(root: Path, manifest: Mapping[str, Any]) -> None:
    derived = derive_manifest_from_sealed_root(root)
    if derived != manifest:
        differing = sorted(
            key
            for key in set(derived) | set(manifest)
            if derived.get(key) != manifest.get(key)
        )
        raise WarehouseW3Error(
            "sealed manifest field-for-field derivation mismatch: "
            + ", ".join(differing)
        )


def verify_dry_root(root: Path) -> dict[str, Any]:
    """Independently rederive one prepared root without mutating it."""

    root = _absolute(root).resolve(strict=True)
    manifest_snapshot = read_regular(
        root / "warehouse_w3_fixed_arm_manifest.v1.json"
    )
    try:
        manifest = json.loads(manifest_snapshot.data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WarehouseW3Error("W3 manifest is not valid JSON") from exc
    if not isinstance(manifest, dict) or render_json(manifest) != manifest_snapshot.data:
        raise WarehouseW3Error("W3 manifest is not a canonical JSON mapping")
    sidecar = read_regular(
        root / "warehouse_w3_fixed_arm_manifest.v1.sha256"
    ).data
    if sidecar != (manifest_snapshot.sha256 + "\n").encode("ascii"):
        raise WarehouseW3Error("W3 manifest SHA-256 sidecar differs")
    if manifest.get("output_root") != {
        "path": str(root),
        "absent_before_creation": True,
        "parent_device": os.stat(root.parent).st_dev,
    }:
        raise WarehouseW3Error("W3 dry-root identity differs")
    if (
        manifest.get("formal_jobs_started") != 0
        or manifest.get("formal_execution_authorized") is not False
        or len(manifest.get("cells", ())) != 43
        or len(manifest.get("jobs", ())) != 172
    ):
        raise WarehouseW3Error("W3 dry-root formal-job or schedule contract differs")
    marker = read_regular(root / "PREPARED_NO_FORMAL_JOBS").data
    if marker != b"W3 dry manifest accepted; formal solver jobs started: 0\n":
        raise WarehouseW3Error("W3 prepared marker differs")
    assert_manifest_rederived(root, manifest)
    base = manifest["prepared_closure_inventory"]
    expected = {
        "directories": list(base["directories"]),
        "files": sorted(
            [
                *base["files"],
                "PREPARED_NO_FORMAL_JOBS",
                "warehouse_w3_fixed_arm_manifest.v1.json",
                "warehouse_w3_fixed_arm_manifest.v1.sha256",
            ],
            key=lambda value: value.encode("utf-8"),
        ),
    }
    if inventory_regular_tree(root) != expected:
        raise WarehouseW3Error("W3 dry-root exact inventory differs")
    return {
        "passed": True,
        "manifest_sha256": manifest_snapshot.sha256,
        "source_commit": manifest["source"]["source_commit"],
        "cell_count": 43,
        "job_count": 172,
        "formal_jobs_started": 0,
        "formal_execution_authorized": False,
        "filesystem_mutated": False,
    }


def prepare_dry_root(
    output_root: Path, *, source_commit: str | None = None
) -> dict[str, Any]:
    """Create one sealed, preflighted W3 root without executing solver jobs."""

    root = repository_root()
    output_root = _absolute(output_root)
    _assert_no_symlink_components(output_root.parent)
    _assert_no_symlink_components(output_root, allow_missing_leaf=True)
    if output_root.exists():
        raise WarehouseW3Error(f"output root already exists: {output_root}")
    resolved_commit, remote_refs = _resolve_source_commit(root, source_commit)
    design_snapshot, _design_blob = _git_blob(root, resolved_commit, DESIGN_PATH)
    if design_snapshot.sha256 != DESIGN_SHA256:
        raise WarehouseW3Error("frozen W3 design differs at the source commit")
    w2_verification = _verify_w2_before_prepare(root)
    w2_snapshot, _w2_blob = _git_blob(root, resolved_commit, W2_MANIFEST_PATH)
    if w2_snapshot.sha256 != W2_MANIFEST_SHA256:
        raise WarehouseW3Error("W2 manifest differs at the source commit")
    w2 = json.loads(w2_snapshot.data)
    arms = _arms(w2)
    case_contract, snapshots = _case_contract(root)

    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{output_root.name}.prepare-",
            dir=output_root.parent,
        )
    )
    os.chmod(staging, 0o700)
    try:
        sealed_repository = _seal_repository_inputs(root, staging, resolved_commit)
        sealed_w2_inputs = _seal_w2_preservation_inputs(
            root, staging, w2, resolved_commit
        )
        source_receipt = _source_receipt(
            resolved_commit, remote_refs, sealed_repository, sealed_w2_inputs
        )
        exclusive_write(staging / SOURCE_RECEIPT_NAME, render_json(source_receipt))
        sealed_cases, sealed_metrics = _seal_cases_and_metrics(
            staging, case_contract, snapshots
        )
        workspaces = _materialize_workspaces(staging, arms)
        for directory in ("artifacts", "control", "raw"):
            (staging / directory).mkdir(mode=0o700)
        cells = _cells(case_contract)
        counter_fixture_proof = _counter_fixture_proof(staging)
        jobs, balance = build_schedule(cells, arms)
        case_by_id = {case["stable_case_id"]: case for case in sealed_cases}
        preflight: list[dict[str, Any]] = []
        champion_workspace = staging / "workspaces" / "champion"
        with workspace_runtime(champion_workspace) as runtime:
            for cell in cells:
                case = case_by_id[cell["stable_case_id"]]
                fact = _greedy_fact(
                    runtime,
                    case,
                    staging / case["sealed_relative_path"],
                    int(cell["seed"]),
                )
                if not fact["oracle_feasible"]:
                    raise WarehouseW3Error(
                        f"greedy initial is infeasible: {cell['stable_case_id']}:{cell['seed']}"
                    )
                preflight.append(fact)

        source_by_path = {entry["source_path"]: entry for entry in sealed_repository}
        problem_layer_sources = [
            source_by_path[path] for path in PROBLEM_LAYER_SOURCES
        ]
        analysis_sources = [source_by_path[path] for path in PROTOCOL_ANALYSIS_SOURCES]
        environment = execution_environment()
        prepared_closure_inventory = inventory_regular_tree(staging)
        manifest: dict[str, Any] = {
            "schema": SCHEMA,
            "authority": {
                "design_path": DESIGN_PATH,
                "design_sha256": DESIGN_SHA256,
                "design_git_commit": DESIGN_COMMIT,
                "w1_receipt_path": W1_PATH,
                "w1_receipt_sha256": W1_SHA256,
                "w2_manifest_path": W2_MANIFEST_PATH,
                "w2_manifest_sha256": W2_MANIFEST_SHA256,
                "w2_receipt_path": W2_RECEIPT_PATH,
                "w2_receipt_sha256": W2_RECEIPT_SHA256,
            },
            "source": source_receipt,
            "protected_roots": [
                str(R3_ROOT),
                str(R3_EXPANDED_ROOT),
                str(R3_VALIDATION_ROOT),
            ],
            "output_root": {
                "path": str(output_root),
                "absent_before_creation": True,
                "parent_device": os.stat(output_root.parent).st_dev,
            },
            "execution_policy": {
                "retry": False,
                "resume": False,
                "reuse": False,
                "automatic_rerun": False,
                "interim_adaptation": False,
                "maximum_live_solver_processes": 1,
                "outer_launcher_timeout": None,
                "solver_owned_scientific_time_limit_seconds": 30,
            },
            "toolchain": _toolchain(
                champion_workspace,
                environment,
                output_root / "workspaces" / "champion",
            ),
            "sealed_repository_inputs": sealed_repository,
            "w2_preservation_inputs": sealed_w2_inputs,
            "historical_metrics": sealed_metrics,
            "case_contract": {
                "views": case_contract["views"],
                "w1_bound_not_selected": [
                    case["stable_case_id"]
                    for case in case_contract["w1_bound_not_selected"]
                ],
                "frozen_and_canary_opened": False,
            },
            "cases": sealed_cases,
            "arms": arms,
            "workspaces": workspaces,
            "registry_contract": {
                "raw_sha256": EXPECTED_REGISTRY_SHA256,
                "r3_raw_sha256": R3_REGISTRY_SHA256,
                "semantic_sha256": workspaces[0]["registry_semantics"][
                    "semantic_sha256"
                ],
                "hardcoded_config_weight_fallback": False,
            },
            "counter_contracts": {
                "formal": FORMAL_COUNTER_CONTRACT,
                "champion": CHAMPION_COUNTER_CONTRACT,
                "r3": R3_COUNTER_CONTRACT,
            },
            "counter_fixture_proof": counter_fixture_proof,
            "cells": cells,
            "greedy_preflight": preflight,
            "jobs": jobs,
            "schedule_balance": balance,
            "invocation_contract": _invocation_contract(environment),
            "analysis_contract": {
                "case_is_statistical_unit": True,
                "seed_majority": "strict_majority_win_or_loss_else_tie",
                "case_measurement": "seed_median",
                "bootstrap": {"seed": 42, "draws": 10000, "alpha": 0.05},
                "source_digests": analysis_sources,
                "protocol_gate": _protocol_gate_contract(root),
                "treatment_bundles_not_pure_factorial": True,
                "validation_is_posterior_diagnostic_not_fresh_confirmation": True,
            },
            "problem_layer_sources": problem_layer_sources,
            "prepared_closure_inventory": prepared_closure_inventory,
            "preflight_passed": True,
            "formal_jobs_started": 0,
            "formal_execution_authorized": False,
        }
        manifest_bytes = render_json(manifest)
        exclusive_write(
            staging / "warehouse_w3_fixed_arm_manifest.v1.json", manifest_bytes
        )
        manifest_sha256 = sha256_bytes(manifest_bytes)
        exclusive_write(
            staging / "warehouse_w3_fixed_arm_manifest.v1.sha256",
            (manifest_sha256 + "\n").encode("ascii"),
        )
        exclusive_write(
            staging / "PREPARED_NO_FORMAL_JOBS",
            b"W3 dry manifest accepted; formal solver jobs started: 0\n",
        )
        os.rename(staging, output_root)
        parent_descriptor = os.open(output_root.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent_descriptor)
        finally:
            os.close(parent_descriptor)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return {
        "output_root": str(output_root),
        "manifest_sha256": manifest_sha256,
        "cell_count": 43,
        "job_count": 172,
        "formal_jobs_started": 0,
        "formal_execution_authorized": False,
        "source_commit": resolved_commit,
    }


__all__ = [
    "WarehouseW3Error",
    "assert_manifest_rederived",
    "derive_manifest_from_sealed_root",
    "prepare_dry_root",
    "process_spec_for_job",
    "verify_dry_root",
]
