"""Sealed preparation and preflight for the fixed CVRP F1 ancestry matrix.

This module materializes immutable runtime and data snapshots from the accepted
R11c authorities and verifies them without writing to them.  Execution and
analysis live in separate problem-owned modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from scion.problems.cvrp.evidence.f1_contract import (
    CvrpF1Error,
    F1_ARM_HASH,
    F1_ARM_ORDER,
    F1_ARM_SYMBOL,
    F1_BRANCH_ID,
    F1_CASES,
    F1_DATA_ROOT,
    F1_DESIGN_SHA256,
    F1_ORDER_CONTRACT,
    F1_RUNTIME_COMMIT,
    F1_SCHEMA,
    F1_SEEDS,
    F1_SELECTED_SURFACE,
    F1_SOURCE_ROOT,
    F1_WILLIAMS,
    _DESIGN_RELATIVE,
    _H1_PATCH,
    _H2_PATCH,
    _ROOT_AUTHORITIES,
)
from scion.problems.cvrp.evidence.f1_io import (
    _assert_read_only,
    _assert_read_only_file,
    _canonical_sha256,
    _copy_inventory,
    _create_absent_root,
    _git_inventory_payload,
    _inventory,
    _inventory_payload,
    _inventory_sha256,
    _list,
    _load_object,
    _make_read_only,
    _object,
    _publish_json_no_replace,
    _reject_nested,
    _remove_tree,
    _require_hash,
    _root_relative,
    _sha256_bytes,
    _sha256_file,
)
from scion.problems.cvrp.evidence.f1_materialization import (
    _arm_replacement_bytes,
    _base_identity_manifest,
    _bind_case_facts,
    _build_jobs,
    _materialize_authorities,
    _materialize_cases,
    _validate_jobs,
    _validate_metric_populations,
    _validate_root_authorities,
    _verify_job_bindings,
)
from scion.problems.cvrp.evidence.f1_runtime import (
    copy_git_inventory as _copy_git_inventory,
    dependency_paths as _dependency_paths,
    editable_hash as _editable_hash,
    git_context as _git_context,
    git_package_inventory as _git_package_inventory,
    implementation_source_identities as _implementation_source_identities,
    import_probe as _import_probe,
    python_identity as _python_identity,
    verify_editable_identity as _verify_editable_identity,
)


@dataclass(frozen=True)
class F1Plan:
    root: Path
    manifest_path: Path
    manifest: Mapping[str, Any]

    @property
    def manifest_sha256(self) -> str:
        return _sha256_file(self.manifest_path)


def prepare_f1_root(
    *,
    repo_root: str | Path,
    output_root: str | Path,
    python: str | Path,
    dry_run: bool,
    source_root: str | Path = F1_SOURCE_ROOT,
    data_root: str | Path = F1_DATA_ROOT,
) -> F1Plan:
    """Materialize one absent F1 root and close its dry manifest."""

    repo = Path(repo_root).expanduser().resolve(strict=True)
    source = Path(source_root).expanduser().resolve(strict=True)
    data = Path(data_root).expanduser().resolve(strict=True)
    if source != F1_SOURCE_ROOT.resolve(strict=True):
        raise CvrpF1Error("F1 R11c source root drift")
    if data != F1_DATA_ROOT.resolve(strict=True):
        raise CvrpF1Error("F1 CVRPLIB data root drift")
    design = repo / _DESIGN_RELATIVE
    _require_hash(design, F1_DESIGN_SHA256, "accepted F1 design")
    git_context = _git_context(repo, design)
    source_identities = _implementation_source_identities(repo)
    if not dry_run and (
        git_context["tracked_at_git_commit"] is not True
        or any(row["tracked_at_git_commit"] is not True for row in source_identities)
    ):
        raise CvrpF1Error(
            "F1 formal materialization requires committed design and implementation"
        )
    py = _python_identity(python)
    root = _create_absent_root(output_root)
    _reject_nested(root, (repo, source, data))

    authority_root = root / "authority_snapshot"
    authority_rows = _materialize_authorities(
        source_root=source,
        design_path=design,
        target_root=authority_root,
    )
    root_authority_payloads = {
        name: _load_object(
            authority_root / "r11c" / name,
            label=f"sealed {name}",
        )
        for name in _ROOT_AUTHORITIES
    }
    _validate_root_authorities(root_authority_payloads)
    metrics = {
        "screening": _load_object(
            authority_root
            / "r11c"
            / "campaign/metrics/83fe3b49-df68-4b14-8c74-7e6f0d2f62a8.json",
            label="sealed screening metrics",
        ),
        "validation": _load_object(
            authority_root
            / "r11c"
            / "campaign/metrics/caf87853-0267-4f14-bcbc-f908f8e8cfbc.json",
            label="sealed validation metrics",
        ),
    }
    _validate_metric_populations(metrics)
    h1 = _load_object(authority_root / "r11c" / _H1_PATCH, label="sealed H1")
    h2 = _load_object(authority_root / "r11c" / _H2_PATCH, label="sealed H2")

    git_inventory = _git_package_inventory(repo)
    champion_source = source / "campaign/champions/champion_v1"
    champion_inventory = _inventory(champion_source, allow_generated_exclusion=True)
    if not champion_inventory:
        raise CvrpF1Error("R11c champion source inventory is empty")
    base_manifest = _base_identity_manifest(h1, h2)
    _verify_editable_identity(champion_source, base_manifest, F1_ARM_HASH["champion"])
    dependency_paths = _dependency_paths(py["executable_path"])

    runtime_rows: list[dict[str, Any]] = []
    runtime_root = root / "runtime_snapshots"
    arm_replacements = _arm_replacement_bytes(h1, h2, base_manifest)
    for arm in F1_ARM_ORDER:
        package_root = runtime_root / arm / "package"
        package = package_root / "scion"
        _copy_git_inventory(repo, git_inventory, package)
        cvrp_target = package / "problems/cvrp"
        _remove_tree(cvrp_target, root=root)
        _copy_inventory(
            champion_source,
            cvrp_target,
            champion_inventory,
        )
        for relative, content in arm_replacements[arm].items():
            target = cvrp_target / relative
            if not target.is_file() or target.is_symlink():
                raise CvrpF1Error(f"F1 replacement target is invalid: {relative}")
            target.write_bytes(content)
        observed_code_hash = _editable_hash(cvrp_target, base_manifest)
        if observed_code_hash != F1_ARM_HASH[arm]:
            raise CvrpF1Error(f"F1 {arm} editable identity drift")
        runtime_inventory = _inventory(package_root)
        runtime_identity = _inventory_sha256(runtime_inventory)
        _make_read_only(package_root)
        probe = _import_probe(
            python=py["executable_path"],
            package_root=package_root,
            workspace=cvrp_target,
            data_root=None,
            case_paths=(),
            dependency_paths=dependency_paths,
            expected_runtime_identity=runtime_identity,
        )
        after_probe = _inventory(package_root)
        if after_probe != runtime_inventory:
            raise CvrpF1Error(f"F1 import probe mutated {arm} runtime")
        runtime_rows.append(
            {
                "arm": arm,
                "symbol": F1_ARM_SYMBOL[arm],
                "editable_hash": observed_code_hash,
                "package_root": _root_relative(root, package_root),
                "workspace": _root_relative(root, cvrp_target),
                "runtime_inventory": _inventory_payload(runtime_inventory),
                "runtime_identity_sha256": runtime_identity,
                "import_probe": probe,
                "import_probe_identity_sha256": _canonical_sha256(probe),
                "dependency_identity_sha256": _canonical_sha256(
                    {
                        "schema": "scion.cvrp_f1_dependency_identity.v1",
                        "modules": probe["dependency_modules"],
                        "native_libraries": probe["native_libraries"],
                    }
                ),
                "replacement_files": [
                    {
                        "path": relative,
                        "sha256": _sha256_bytes(content),
                    }
                    for relative, content in sorted(arm_replacements[arm].items())
                ],
            }
        )

    # Seal the complete PYTHONPATH closure, including arm/package parents.
    # Leaving any ancestor writable would permit a new top-level import to be
    # injected beside ``scion`` after the recorded inventory was computed.
    _make_read_only(runtime_root)

    case_rows = _materialize_cases(
        data_root=data,
        target_root=root / "input_snapshot",
        data_identity=root_authority_payloads["prepared_cvrp_data_identity.v1.json"],
        metrics=metrics,
    )
    input_inventory = _inventory(root / "input_snapshot")
    input_identity = _inventory_sha256(input_inventory)
    _make_read_only(root / "input_snapshot")
    # Re-parse every adjacent pair with every sealed arm.  This also proves that
    # all four import closures retain the same historical loader semantics.
    parsed_by_arm: dict[str, Any] = {}
    case_paths = tuple(row["case_path"] for row in case_rows)
    for runtime in runtime_rows:
        package_root = root / str(runtime["package_root"])
        workspace = root / str(runtime["workspace"])
        probe = _import_probe(
            python=py["executable_path"],
            package_root=package_root,
            workspace=workspace,
            data_root=root / "input_snapshot",
            case_paths=case_paths,
            dependency_paths=dependency_paths,
            expected_runtime_identity=str(runtime["runtime_identity_sha256"]),
        )
        if _inventory(package_root) != tuple(
            (row["path"], row["sha256"]) for row in runtime["runtime_inventory"]
        ):
            raise CvrpF1Error(f"F1 case probe mutated {runtime['arm']} runtime")
        parsed_by_arm[str(runtime["arm"])] = probe["case_facts"]
    first_facts = parsed_by_arm[F1_ARM_ORDER[0]]
    if any(parsed_by_arm[arm] != first_facts for arm in F1_ARM_ORDER[1:]):
        raise CvrpF1Error("F1 arm loaders disagree on sealed case facts")
    _bind_case_facts(case_rows, first_facts)

    jobs = _build_jobs(root, case_rows, runtime_rows, py)
    _validate_jobs(jobs)
    root_id = _canonical_sha256(
        {
            "schema": "scion.cvrp_f1_output_root_identity.v1",
            "absolute_path": str(root),
            "absent_before_creation": True,
        }
    )
    manifest: dict[str, Any] = {
        "schema_version": F1_SCHEMA,
        "problem_id": "cvrp",
        "dry_run": bool(dry_run),
        "root_id": root_id,
        "output_root": str(root),
        "output_root_absent_before_creation": True,
        "design": {
            "snapshot_path": "authority_snapshot/design/" + Path(_DESIGN_RELATIVE).name,
            "sha256": F1_DESIGN_SHA256,
            **git_context,
        },
        "r11c": {
            "protected_source_root": str(source),
            "runtime_commit": F1_RUNTIME_COMMIT,
            "branch_id": F1_BRANCH_ID,
            "prepared_data_internal_identity_sha256": (
                "ca7e470ec8d1f3569a690d10df5a170c4994108c71fecf5aa1a7a76b42630743"
            ),
            "pre_post_split_byte_identical": True,
            "authorities": authority_rows,
            "authority_snapshot_identity_sha256": _inventory_sha256(
                _inventory(authority_root)
            ),
        },
        "policy": {
            "llm": False,
            "campaign_mutation": False,
            "retry": False,
            "resume": False,
            "reuse": False,
            "automatic_rerun": False,
            "interim_adaptation": False,
            "selected_surface": F1_SELECTED_SURFACE,
            "one_live_solver": True,
        },
        "python": py,
        "dependency_paths": list(dependency_paths),
        "runtime_git_inventory": _git_inventory_payload(git_inventory),
        "runtime_git_inventory_sha256": _canonical_sha256(
            _git_inventory_payload(git_inventory)
        ),
        "champion_source_inventory": _inventory_payload(champion_inventory),
        "champion_source_inventory_sha256": _inventory_sha256(champion_inventory),
        "editable_base_identity_manifest": base_manifest,
        "arms": runtime_rows,
        "input_snapshot": {
            "root": "input_snapshot",
            "inventory": _inventory_payload(input_inventory),
            "identity_sha256": input_identity,
            "file_count": 32,
        },
        "cases": case_rows,
        "stages": [
            {
                "stage": stage,
                "seeds": list(F1_SEEDS[stage]),
                "case_paths": [path for path, _ in F1_CASES[stage]],
                "cell_count": 32,
            }
            for stage in ("screening", "validation")
        ],
        "order_contract": F1_ORDER_CONTRACT,
        "williams_sequences": list(F1_WILLIAMS),
        "cell_count": 64,
        "job_count": 256,
        "jobs": jobs,
        "implementation_repo_root": str(repo),
        "implementation_sources": source_identities,
        "analysis": {
            "bootstrap": {
                "function": "scion.protocol.stats.bootstrap_ci",
                "n_boot": 1000,
                "alpha": 0.05,
                "seed": 42,
            },
            "case_is_primary_unit": True,
            "combined_view_diagnostic_only": True,
            "promotion_gate": None,
        },
    }
    _verify_job_bindings(manifest, root)
    manifest_path = root / "manifest.json"
    _publish_json_no_replace(manifest_path, manifest)
    manifest_path.chmod(0o444)
    _make_read_only(authority_root)
    _assert_read_only(authority_root)
    _assert_read_only(root / "input_snapshot")
    _assert_read_only(runtime_root)
    plan = F1Plan(root=root, manifest_path=manifest_path, manifest=manifest)
    verify_f1_root(root)
    return plan


def verify_f1_root(root: str | Path) -> F1Plan:
    """Re-derive the sealed F1 manifest contract without mutating the root."""

    output = Path(root).expanduser().resolve(strict=True)
    manifest_path = output / "manifest.json"
    before = _inventory(output)
    _assert_read_only_file(manifest_path)
    manifest = _load_object(manifest_path, label="F1 manifest")
    if manifest.get("schema_version") != F1_SCHEMA:
        raise CvrpF1Error("F1 manifest schema drift")
    if manifest.get("output_root") != str(output):
        raise CvrpF1Error("F1 output-root identity drift")
    if manifest.get("cell_count") != 64 or manifest.get("job_count") != 256:
        raise CvrpF1Error("F1 population cardinality drift")
    policy = _object(manifest.get("policy"), "F1 policy")
    expected_false = (
        "llm",
        "campaign_mutation",
        "retry",
        "resume",
        "reuse",
        "automatic_rerun",
        "interim_adaptation",
    )
    if any(policy.get(name) is not False for name in expected_false):
        raise CvrpF1Error("F1 no-adaptation policy drift")
    repo = Path(str(manifest.get("implementation_repo_root") or "")).resolve(
        strict=True
    )
    if not repo.is_dir():
        raise CvrpF1Error("F1 implementation repository is unavailable")
    observed_sources = _implementation_source_identities(repo)
    if observed_sources != manifest.get("implementation_sources"):
        raise CvrpF1Error("F1 implementation source identity drift")
    if manifest.get("dry_run") is False and any(
        row.get("tracked_at_git_commit") is not True for row in observed_sources
    ):
        raise CvrpF1Error("F1 formal implementation authority is not committed")
    observed_git_inventory = _git_package_inventory(repo)
    if _git_inventory_payload(observed_git_inventory) != manifest.get(
        "runtime_git_inventory"
    ):
        raise CvrpF1Error("F1 runtime git source closure drift")
    if _canonical_sha256(
        _git_inventory_payload(observed_git_inventory)
    ) != manifest.get("runtime_git_inventory_sha256"):
        raise CvrpF1Error("F1 runtime git source identity drift")
    design_context = _object(manifest["design"], "design")
    current_context = _git_context(repo, repo / _DESIGN_RELATIVE)
    if current_context != {
        "git_commit_context": design_context.get("git_commit_context"),
        "tracked_at_git_commit": design_context.get("tracked_at_git_commit"),
    }:
        raise CvrpF1Error("F1 design git context drift")
    _require_hash(
        output / str(design_context["snapshot_path"]),
        F1_DESIGN_SHA256,
        "sealed F1 design",
    )
    authorities = _list(manifest["r11c"], "authorities")
    for row in authorities:
        item = _object(row, "authority row")
        _require_hash(
            output / str(item["snapshot_path"]),
            str(item["sha256"]),
            f"sealed authority {item['source_relative_path']}",
        )
    authority_root = output / "authority_snapshot"
    expected_authority = str(manifest["r11c"]["authority_snapshot_identity_sha256"])
    if _inventory_sha256(_inventory(authority_root)) != expected_authority:
        raise CvrpF1Error("F1 authority complete inventory drift")
    _assert_read_only(authority_root)

    expected_input = tuple(
        (str(row["path"]), str(row["sha256"]))
        for row in _list(manifest["input_snapshot"], "inventory")
    )
    if _inventory(output / "input_snapshot") != expected_input:
        raise CvrpF1Error("F1 input complete inventory drift")
    if len(expected_input) != 32:
        raise CvrpF1Error("F1 input snapshot must contain 16 adjacent pairs")
    _assert_read_only(output / "input_snapshot")
    runtime_root = output / "runtime_snapshots"
    _assert_read_only(runtime_root)
    arms = _list(manifest, "arms")
    if tuple(row["arm"] for row in arms) != F1_ARM_ORDER:
        raise CvrpF1Error("F1 arm population/order drift")
    python = _object(manifest.get("python"), "Python identity")
    observed_python = _python_identity(str(python["executable_path"]))
    if observed_python != python:
        raise CvrpF1Error("F1 Python identity drift")
    dependency_paths = tuple(str(value) for value in manifest["dependency_paths"])
    case_paths = tuple(str(row["case_path"]) for row in manifest["cases"])
    common_facts: Any = None
    for arm in arms:
        item = _object(arm, "arm")
        package_root = output / str(item["package_root"])
        expected_inventory = tuple(
            (str(row["path"]), str(row["sha256"]))
            for row in _list(item, "runtime_inventory")
        )
        if _inventory(package_root) != expected_inventory:
            raise CvrpF1Error(f"F1 {item['arm']} runtime complete inventory drift")
        workspace = output / str(item["workspace"])
        code_hash = _editable_hash(
            workspace,
            _object(manifest["editable_base_identity_manifest"], "base identity"),
        )
        if code_hash != item["editable_hash"] or code_hash != F1_ARM_HASH[item["arm"]]:
            raise CvrpF1Error(f"F1 {item['arm']} editable identity drift")
        identity_probe = _import_probe(
            python=str(python["executable_path"]),
            package_root=package_root,
            workspace=workspace,
            data_root=None,
            case_paths=(),
            dependency_paths=dependency_paths,
            expected_runtime_identity=str(item["runtime_identity_sha256"]),
        )
        if _canonical_sha256(identity_probe) != item["import_probe_identity_sha256"]:
            raise CvrpF1Error(f"F1 {item['arm']} import identity drift")
        dependency_identity = _canonical_sha256(
            {
                "schema": "scion.cvrp_f1_dependency_identity.v1",
                "modules": identity_probe["dependency_modules"],
                "native_libraries": identity_probe["native_libraries"],
            }
        )
        if dependency_identity != item["dependency_identity_sha256"]:
            raise CvrpF1Error(f"F1 {item['arm']} dependency identity drift")
        probe = _import_probe(
            python=str(python["executable_path"]),
            package_root=package_root,
            workspace=workspace,
            data_root=output / "input_snapshot",
            case_paths=case_paths,
            dependency_paths=dependency_paths,
            expected_runtime_identity=str(item["runtime_identity_sha256"]),
        )
        facts = probe["case_facts"]
        if common_facts is None:
            common_facts = facts
        elif common_facts != facts:
            raise CvrpF1Error("F1 arm loader fact drift")
        if _inventory(package_root) != expected_inventory:
            raise CvrpF1Error(f"F1 verification mutated {item['arm']} runtime")
        _assert_read_only(package_root)
    observed_facts = {str(row["case_path"]): row for row in common_facts}
    for case in manifest["cases"]:
        facts = observed_facts.get(str(case["case_path"]))
        if facts is None or facts != case["parsed_facts"]:
            raise CvrpF1Error(f"F1 parsed case fact drift: {case['case_path']}")
    _validate_jobs(_list(manifest, "jobs"))
    _verify_job_bindings(manifest, output)
    after = _inventory(output)
    if before != after:
        raise CvrpF1Error("F1 verify mutated output-root bytes or membership")
    return F1Plan(root=output, manifest_path=manifest_path, manifest=manifest)


__all__ = [
    "F1Plan",
    "prepare_f1_root",
    "verify_f1_root",
]
