"""Warehouse W2 owner-equivalence and historical-preservation verification.

This is an offline, problem-owned verifier.  In particular, it reads the
historical SQLite main/WAL files as ordinary bytes and never opens SQLite.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.metadata
import json
import platform
import sys
from pathlib import Path
from typing import Any

import yaml


_ALLOWED_YAML_SCALAR_PATHS = (
    "research_surfaces[0].prompt.implementation_guidance",
    "research_surfaces[1].prompt.implementation_guidance",
)
_FROZEN_ACCEPTANCE_TOOLCHAIN = {
    "python_implementation": "CPython",
    "python_version": "3.12.12",
    "python_resolved_executable_sha256": (
        "05ac06936ba7928748b0c038908a0a3176ddc4f12b7929f5d79cb7a8625c7744"
    ),
    "pyyaml_version": "6.0.1",
    "pyyaml_loader": "SafeLoader with explicit duplicate-key rejection",
    "pyyaml_duplicate_key_policy": "reject_fail_closed_before_masking",
    "pulp_version": "3.3.0",
    "highspy_distribution_version": "1.14.0",
    "highspy_highs_py_sha256": (
        "38a03037bd16a13784b94b62e85bcba3b8b40beb766b03145b55bde4776474e3"
    ),
    "highspy_native_core_filename": "_core.cpython-312-x86_64-linux-gnu.so",
    "highspy_native_core_sha256": (
        "c9c48f69b6d6117ad8b2c4edbdf73122d1f89a4bbf1c7ffff92990be27715c3f"
    ),
    "native_status_authority": (
        "highspy.HighsModelStatus via problem.solverModel.getModelStatus()"
    ),
}


class WarehouseW2PreservationError(RuntimeError):
    """Raised when a frozen W2 owner or historical artifact no longer matches."""


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


class _StripDocstrings(ast.NodeTransformer):
    _BODY_OWNERS = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)

    def generic_visit(self, node: ast.AST) -> ast.AST:
        node = super().generic_visit(node)
        if isinstance(node, self._BODY_OWNERS):
            body = getattr(node, "body", None)
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                node.body = body[1:]
        return node


def docstring_stripped_ast_sha256(source: str) -> str:
    tree = ast.parse(source)
    stripped = _StripDocstrings().visit(tree)
    ast.fix_missing_locations(stripped)
    rendered = ast.dump(
        stripped,
        annotate_fields=True,
        include_attributes=False,
    ).encode("utf-8")
    return sha256_bytes(rendered)


class _UniqueKeySafeLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(
    loader: _UniqueKeySafeLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in result
        except TypeError as exc:
            raise WarehouseW2PreservationError(
                f"YAML mapping key is not hashable at line {key_node.start_mark.line + 1}"
            ) from exc
        if duplicate:
            raise WarehouseW2PreservationError(
                f"duplicate YAML key {key!r} at line {key_node.start_mark.line + 1}"
            )
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def load_unique_yaml(data: bytes, *, label: str) -> dict[str, Any]:
    try:
        value = yaml.load(data.decode("utf-8"), Loader=_UniqueKeySafeLoader)
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise WarehouseW2PreservationError(f"{label} is invalid YAML: {exc}") from exc
    if not isinstance(value, dict):
        raise WarehouseW2PreservationError(f"{label} must contain a YAML mapping")
    return value


def _mask_yaml_guidance(
    value: dict[str, Any],
    sentinel: Any,
    *,
    allowed_scalar_paths: Any,
) -> tuple[str, str]:
    if not isinstance(allowed_scalar_paths, list) or any(
        not isinstance(path, str) for path in allowed_scalar_paths
    ):
        raise WarehouseW2PreservationError(
            "Warehouse YAML allowed_scalar_paths must be a string list"
        )
    if tuple(allowed_scalar_paths) != _ALLOWED_YAML_SCALAR_PATHS:
        raise WarehouseW2PreservationError(
            "Warehouse YAML allowed_scalar_paths differ from the exact contract path set"
        )
    surfaces = value.get("research_surfaces")
    if not isinstance(surfaces, list) or len(surfaces) < 2:
        raise WarehouseW2PreservationError("Warehouse YAML lacks two research surfaces")
    guidance: list[str] = []
    for index in (0, 1):
        surface = surfaces[index]
        if not isinstance(surface, dict):
            raise WarehouseW2PreservationError(
                f"research_surfaces[{index}] must be a mapping"
            )
        prompt = surface.get("prompt")
        if not isinstance(prompt, dict) or "implementation_guidance" not in prompt:
            raise WarehouseW2PreservationError(
                f"research_surfaces[{index}].prompt.implementation_guidance missing"
            )
        scalar = prompt["implementation_guidance"]
        if not isinstance(scalar, str):
            raise WarehouseW2PreservationError(
                f"research_surfaces[{index}].prompt.implementation_guidance "
                "must be a YAML string scalar"
            )
        guidance.append(scalar)
        prompt["implementation_guidance"] = sentinel
    return guidance[0], guidance[1]


def _read(path: Path, *, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise WarehouseW2PreservationError(f"cannot read {label}: {path}: {exc}") from exc


def _require_hash(path: Path, expected: str, *, label: str) -> dict[str, Any]:
    data = _read(path, label=label)
    actual = sha256_bytes(data)
    if actual != expected:
        raise WarehouseW2PreservationError(
            f"{label} hash mismatch: {path}: expected {expected}, got {actual}"
        )
    return {"path": str(path), "sha256": actual, "size_bytes": len(data)}


def acceptance_toolchain() -> dict[str, str]:
    """Return the closed W2 toolchain identity, failing on any drift."""

    import highspy
    import pulp

    executable = Path(sys.executable).resolve()
    package_dir = Path(highspy.__file__).resolve().parent
    highs_py = package_dir / "highs.py"
    native_core = package_dir / _FROZEN_ACCEPTANCE_TOOLCHAIN[
        "highspy_native_core_filename"
    ]
    actual = {
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "python_resolved_executable_sha256": sha256_bytes(executable.read_bytes()),
        "pyyaml_version": yaml.__version__,
        "pyyaml_loader": "SafeLoader with explicit duplicate-key rejection",
        "pyyaml_duplicate_key_policy": "reject_fail_closed_before_masking",
        "pulp_version": pulp.__version__,
        "highspy_distribution_version": importlib.metadata.version("highspy"),
        "highspy_highs_py_sha256": sha256_bytes(highs_py.read_bytes()),
        "highspy_native_core_filename": native_core.name,
        "highspy_native_core_sha256": sha256_bytes(native_core.read_bytes()),
        "native_status_authority": (
            "highspy.HighsModelStatus via problem.solverModel.getModelStatus()"
        ),
    }
    if actual != _FROZEN_ACCEPTANCE_TOOLCHAIN:
        issues = [
            key
            for key in sorted(_FROZEN_ACCEPTANCE_TOOLCHAIN)
            if actual.get(key) != _FROZEN_ACCEPTANCE_TOOLCHAIN[key]
        ]
        raise WarehouseW2PreservationError(
            "acceptance toolchain mismatch: " + ", ".join(issues)
        )
    return actual


def _verify_toolchain(manifest: dict[str, Any]) -> dict[str, str]:
    expected = manifest["verification_toolchain"]
    py = expected["python"]
    executable = Path(sys.executable).resolve()
    actual_version = platform.python_version()
    actual_executable_sha = sha256_bytes(executable.read_bytes())
    issues: list[str] = []
    if platform.python_implementation() != py["implementation"]:
        issues.append("python implementation")
    if actual_version != py["version"]:
        issues.append("python version")
    if executable != Path(py["resolved_executable"]):
        issues.append("python executable")
    if actual_executable_sha != py["resolved_executable_sha256"]:
        issues.append("python executable hash")
    if yaml.__version__ != expected["yaml"]["version"]:
        issues.append("PyYAML version")
    if issues:
        raise WarehouseW2PreservationError(
            "verification toolchain mismatch: " + ", ".join(issues)
        )
    return acceptance_toolchain()


def _verify_allowed_owners(
    root: Path,
    manifest: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    owners = manifest["allowed_semantic_text_owners"]
    checks: list[dict[str, Any]] = []
    current_hashes: dict[str, str] = {}

    for entry in owners["python_docstring_only"]:
        path = root / entry["path"]
        data = _read(path, label=entry["path"])
        current_hashes[entry["path"]] = sha256_bytes(data)
        actual = docstring_stripped_ast_sha256(data.decode("utf-8"))
        if actual != entry["docstring_stripped_ast_sha256"]:
            raise WarehouseW2PreservationError(
                f"docstring-only AST mismatch: {entry['path']}: {actual}"
            )
        checks.append({"kind": "docstring_stripped_ast", "path": entry["path"], "sha256": actual})

    for entry in owners["python_exact_code_plus_docstrings"]:
        path = root / entry["path"]
        source = _read(path, label=entry["path"]).decode("utf-8")
        current_hashes[entry["path"]] = sha256_bytes(source.encode("utf-8"))
        before = entry["before"]
        after = entry["after"]
        if source.count(before) != 0 or source.count(after) != 1:
            raise WarehouseW2PreservationError(
                f"exact admitted code replacement mismatch: {entry['path']}"
            )
        reversed_source = source.replace(after, before, 1)
        actual = docstring_stripped_ast_sha256(reversed_source)
        if actual != entry["pre_docstring_stripped_ast_sha256"]:
            raise WarehouseW2PreservationError(
                f"reverse-normalized AST mismatch: {entry['path']}: {actual}"
            )
        checks.append({"kind": "exact_code_reverse_ast", "path": entry["path"], "sha256": actual})

    adapter = owners["adapter_exact_reverse_replacement"]
    path = root / adapter["path"]
    source = _read(path, label=adapter["path"]).decode("utf-8")
    current_hashes[adapter["path"]] = sha256_bytes(source.encode("utf-8"))
    reversed_source = source
    for replacement in adapter["replacements"]:
        if source.count(replacement["before"]) != 0 or source.count(replacement["after"]) != 1:
            raise WarehouseW2PreservationError(
                f"adapter exact replacement mismatch: {replacement['after']}"
            )
        reversed_source = reversed_source.replace(
            replacement["after"], replacement["before"], 1
        )
    actual = sha256_bytes(reversed_source.encode("utf-8"))
    if actual != adapter["pre_raw_sha256"]:
        raise WarehouseW2PreservationError(
            f"adapter reverse-normalized file mismatch: expected {adapter['pre_raw_sha256']}, got {actual}"
        )
    checks.append({"kind": "adapter_exact_reverse", "path": adapter["path"], "sha256": actual})

    sentinel = owners["yaml_mask_sentinel"]
    normalized_guidance: list[tuple[str, str]] = []
    for entry in owners["yaml_guidance_only"]:
        path = root / entry["path"]
        data = _read(path, label=entry["path"])
        current_hashes[entry["path"]] = sha256_bytes(data)
        parsed = load_unique_yaml(data, label=entry["path"])
        normalized_guidance.append(
            _mask_yaml_guidance(
                parsed,
                sentinel,
                allowed_scalar_paths=entry.get("allowed_scalar_paths"),
            )
        )
        actual = canonical_sha256(parsed)
        if actual != entry["masked_canonical_tree_sha256"]:
            raise WarehouseW2PreservationError(
                f"masked Warehouse YAML mismatch: {entry['path']}: {actual}"
            )
        checks.append({"kind": "yaml_masked_tree", "path": entry["path"], "sha256": actual})
    if len(normalized_guidance) != 2 or normalized_guidance[0] != normalized_guidance[1]:
        raise WarehouseW2PreservationError("Warehouse YAML mirrors have different guidance")

    for entry in owners["markdown"]:
        path = root / entry["path"]
        data = _read(path, label=entry["path"])
        current_hashes[entry["path"]] = sha256_bytes(data)
        checks.append(
            {
                "kind": "reviewed_markdown_owner",
                "path": entry["path"],
                "pre_sha256": entry["pre_raw_sha256"],
                "post_sha256": current_hashes[entry["path"]],
            }
        )
    return checks, current_hashes


def verify_w2_preservation(
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    root = repository_root()
    manifest_path = manifest_path or (
        root / "scion/contracts/warehouse_w2_preservation_manifest.v1.json"
    )
    manifest_bytes = _read(manifest_path, label="W2 preservation manifest")
    manifest = json.loads(manifest_bytes)
    if manifest.get("schema") != "scion.warehouse_w2_preservation_manifest.v1":
        raise WarehouseW2PreservationError("unexpected W2 preservation schema")

    toolchain = _verify_toolchain(manifest)
    owner_checks, current_owner_hashes = _verify_allowed_owners(root, manifest)
    exact_checks: list[dict[str, Any]] = []

    w1 = manifest["w1_receipt"]
    exact_checks.append(
        _require_hash(root / w1["path"], w1["sha256"], label="W1 receipt")
    )
    for entry in manifest["protected_current_runtime"]:
        exact_checks.append(
            _require_hash(root / entry["path"], entry["sha256"], label=entry["path"])
        )

    r3 = manifest["r3"]
    r3_root = Path(r3["root"])
    for entry in r3["evidence_files"]:
        checked = _require_hash(
            r3_root / entry["path"], entry["sha256"], label=f"R3 {entry['path']}"
        )
        if entry["path"] == "campaign/scion.db-wal" and checked["size_bytes"] != 0:
            raise WarehouseW2PreservationError("R3 SQLite WAL must remain empty")
        exact_checks.append(checked)
    derivation = r3["arm_derivation"]
    for entry in derivation["champion_operator_files"] + derivation["workspace_replacements"]:
        exact_checks.append(
            _require_hash(r3_root / entry["path"], entry["sha256"], label=f"R3 arm {entry['path']}")
        )
    for arm in derivation["arms"]:
        payload = {
            "domain": "scion.warehouse_w3_arm.v1",
            "items": arm["components"],
        }
        actual = canonical_sha256(payload)
        if actual != arm["arm_sha256"]:
            raise WarehouseW2PreservationError(
                f"R3 arm digest mismatch: {arm['name']}: {actual}"
            )

    return {
        "schema": "scion.warehouse_w2_preservation_verification.v1",
        "passed": True,
        "manifest_path": str(manifest_path.relative_to(root)),
        "manifest_sha256": sha256_bytes(manifest_bytes),
        "toolchain": toolchain,
        "owner_checks": owner_checks,
        "current_owner_hashes": dict(sorted(current_owner_hashes.items())),
        "exact_protected_count": len(exact_checks),
        "exact_protected_digest": canonical_sha256(exact_checks),
        "r3_database_access": "raw_bytes_only_no_sqlite_open",
    }


__all__ = [
    "WarehouseW2PreservationError",
    "acceptance_toolchain",
    "canonical_bytes",
    "canonical_sha256",
    "docstring_stripped_ast_sha256",
    "load_unique_yaml",
    "repository_root",
    "sha256_bytes",
    "verify_w2_preservation",
]
