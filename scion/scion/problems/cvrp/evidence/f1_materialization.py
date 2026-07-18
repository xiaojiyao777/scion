"""Authority, input, arm, and schedule materialization for CVRP F1."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from scion.problems.cvrp.evidence.f1_contract import (
    CvrpF1Error,
    F1_ARM_HASH,
    F1_ARM_ORDER,
    F1_ARM_SYMBOL,
    F1_CASES,
    F1_DESIGN_SHA256,
    F1_RUNTIME_COMMIT,
    F1_SEEDS,
    F1_WILLIAMS,
    _DESIGN_RELATIVE,
    _PROTECTED_AUTHORITIES,
    _ROOT_AUTHORITIES,
)
from scion.problems.cvrp.evidence.f1_io import (
    _canonical_sha256,
    _capture_regular,
    _list,
    _object,
    _root_relative,
    _safe_source_file,
    _sha256_bytes,
    _sha256_file,
    _write_exclusive,
)
from scion.problems.cvrp.evidence.f1_runtime import (
    child_environment as _child_environment,
    dependency_paths as _dependency_paths,
)


def _materialize_authorities(
    *, source_root: Path, design_path: Path, target_root: Path
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    all_authorities = {**_ROOT_AUTHORITIES, **_PROTECTED_AUTHORITIES}
    for relative, expected in sorted(all_authorities.items()):
        source = source_root / relative
        captured = _capture_regular(source, label=f"R11c authority {relative}")
        if _sha256_bytes(captured) != expected:
            raise CvrpF1Error(f"R11c authority hash drift: {relative}")
        target = target_root / "r11c" / relative
        _write_exclusive(target, captured)
        rows.append(
            {
                "source_relative_path": relative,
                "snapshot_path": _root_relative(target_root.parent, target),
                "sha256": expected,
            }
        )
    design_bytes = _capture_regular(design_path, label="accepted F1 design")
    design_target = target_root / "design" / design_path.name
    _write_exclusive(design_target, design_bytes)
    rows.append(
        {
            "source_relative_path": _DESIGN_RELATIVE,
            "snapshot_path": _root_relative(target_root.parent, design_target),
            "sha256": F1_DESIGN_SHA256,
        }
    )
    if _sha256_file(
        target_root / "r11c/pre_campaign_split_data.v1.json"
    ) != _sha256_file(target_root / "r11c/post_campaign_split_data.v1.json"):
        raise CvrpF1Error("R11c pre/post split bytes differ")
    return rows


def _validate_root_authorities(payloads: Mapping[str, Mapping[str, Any]]) -> None:
    data = payloads["prepared_cvrp_data_identity.v1.json"]
    if data.get("identity_sha256") != (
        "ca7e470ec8d1f3569a690d10df5a170c4994108c71fecf5aa1a7a76b42630743"
    ):
        raise CvrpF1Error("R11c prepared data internal identity drift")
    if data.get("ok") is not True or data.get("missing_companion_count") != 0:
        raise CvrpF1Error("R11c prepared data authority is not complete")
    pre = payloads["pre_campaign_split_data.v1.json"]
    post = payloads["post_campaign_split_data.v1.json"]
    if pre != post or pre.get("identity_matches_expected") is not True:
        raise CvrpF1Error("R11c split data authority drift")
    prepared = payloads["prepared_run_manifest.v1.json"]
    if prepared.get("git", {}).get("commit") != F1_RUNTIME_COMMIT[:8]:
        raise CvrpF1Error("R11c prepared runtime commit drift")


def _validate_metric_populations(metrics: Mapping[str, Mapping[str, Any]]) -> None:
    for stage in ("screening", "validation"):
        payload = metrics[stage]
        if payload.get("stage") != stage:
            raise CvrpF1Error(f"R11c {stage} metrics stage drift")
        expected_cases = [path for path, _ in F1_CASES[stage]]
        if payload.get("case_ids") != expected_cases:
            raise CvrpF1Error(f"R11c {stage} case population/order drift")
        if payload.get("seed_set") != list(F1_SEEDS[stage]):
            raise CvrpF1Error(f"R11c {stage} seed population/order drift")
        pairs = payload.get("pairs")
        if not isinstance(pairs, list) or len(pairs) != 32:
            raise CvrpF1Error(f"R11c {stage} pair population drift")
        observed = [
            (row.get("case"), row.get("seed"), row.get("time_limit_sec"))
            for row in pairs
            if isinstance(row, dict)
        ]
        expected = [
            (case_path, seed, limit)
            for case_path, limit in F1_CASES[stage]
            for seed in F1_SEEDS[stage]
        ]
        if observed != expected:
            raise CvrpF1Error(f"R11c {stage} resolved cell identity drift")


def _base_identity_manifest(
    h1: Mapping[str, Any], h2: Mapping[str, Any]
) -> dict[str, Any]:
    first = _object(
        _object(h1.get("replay_materialization"), "H1 materialization").get(
            "base_identity_manifest"
        ),
        "H1 base identity",
    )
    second = _object(
        _object(h2.get("replay_materialization"), "H2 materialization").get(
            "base_identity_manifest"
        ),
        "H2 base identity",
    )
    if first != second or first.get("code_hash") != F1_ARM_HASH["champion"]:
        raise CvrpF1Error("F1 formal artifacts disagree on champion base identity")
    files = first.get("files")
    if not isinstance(files, list) or len(files) != 11:
        raise CvrpF1Error("F1 champion editable file closure drift")
    return dict(first)


def _arm_replacement_bytes(
    h1: Mapping[str, Any],
    h2: Mapping[str, Any],
    base_manifest: Mapping[str, Any],
) -> dict[str, dict[str, bytes]]:
    base_hashes = {
        str(row["file_path"]): str(row["sha256"])
        for row in _list(base_manifest, "files")
    }

    def rows(payload: Any, label: str) -> dict[str, bytes]:
        replacements: dict[str, bytes] = {}
        if not isinstance(payload, list):
            raise CvrpF1Error(f"{label} replacement rows are invalid")
        for raw in payload:
            row = _object(raw, f"{label} replacement")
            relative = str(row.get("file_path") or "")
            if relative not in base_hashes:
                raise CvrpF1Error(f"{label} replacement escapes editable closure")
            if (
                row.get("action") != "modify"
                or row.get("base_sha256") != base_hashes[relative]
            ):
                raise CvrpF1Error(
                    f"{label} replacement base identity drift: {relative}"
                )
            content = row.get("code_content")
            if not isinstance(content, str):
                raise CvrpF1Error(f"{label} replacement bytes are missing: {relative}")
            replacements[relative] = content.encode("utf-8")
        return replacements

    h1_patch = _object(h1.get("patch"), "H1 patch")
    h2_patch = _object(h2.get("patch"), "H2 patch")
    cumulative = _object(h2.get("replay_materialization"), "H2 materialization")
    h1_rows = rows(h1_patch.get("files"), "H1")
    swap_rows = rows(h2_patch.get("files"), "SWAP-only")
    cumulative_rows = rows(cumulative.get("files"), "cumulative")
    if tuple(sorted(h1_rows)) != (
        "policies/baseline_modules/destroy_repair.py",
        "policies/baseline_modules/scheduler.py",
    ):
        raise CvrpF1Error("F1 H1 replacement file set drift")
    if tuple(swap_rows) != ("policies/baseline_modules/local_search.py",):
        raise CvrpF1Error("F1 SWAP-only replacement file set drift")
    if set(cumulative_rows) != set(h1_rows) | set(swap_rows):
        raise CvrpF1Error("F1 cumulative replacement file set drift")
    if any(cumulative_rows[path] != content for path, content in h1_rows.items()):
        raise CvrpF1Error("F1 cumulative H1 inheritance bytes drift")
    if cumulative_rows[tuple(swap_rows)[0]] != swap_rows[tuple(swap_rows)[0]]:
        raise CvrpF1Error("F1 cumulative SWAP bytes drift")
    result = {
        "champion": {},
        "h1_only": h1_rows,
        "swap_only": swap_rows,
        "cumulative": cumulative_rows,
    }
    for arm, replacements in result.items():
        for raw in _list(base_manifest, "files"):
            row = _object(raw, "base file")
            relative = str(row["file_path"])
            content = replacements.get(relative)
            if content is None:
                continue
            if _sha256_bytes(content) == base_hashes[relative]:
                raise CvrpF1Error(f"F1 {arm} replacement is byte-identical to base")
    return result


def _materialize_cases(
    *,
    data_root: Path,
    target_root: Path,
    data_identity: Mapping[str, Any],
    metrics: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    file_rows = data_identity.get("files")
    if not isinstance(file_rows, list):
        raise CvrpF1Error("R11c data identity file closure is invalid")
    by_path = {
        str(row["relative_path"]): row
        for row in file_rows
        if isinstance(row, dict) and isinstance(row.get("relative_path"), str)
    }
    metric_cells = {
        stage: {
            (str(row["case"]), int(row["seed"])): int(row["time_limit_sec"])
            for row in metrics[stage]["pairs"]
        }
        for stage in ("screening", "validation")
    }
    result: list[dict[str, Any]] = []
    cell_ordinal = 0
    for stage in ("screening", "validation"):
        for case_ordinal, (case_path, limit) in enumerate(F1_CASES[stage]):
            vrp = Path(case_path)
            sol = vrp.with_suffix(".sol")
            pair = []
            for relative in (vrp, sol):
                relative_text = relative.as_posix()
                authority = by_path.get(relative_text)
                if authority is None or authority.get("stage") != stage:
                    raise CvrpF1Error(f"F1 data authority omitted {relative_text}")
                source = _safe_source_file(data_root, relative)
                content = _capture_regular(source, label=f"F1 input {relative_text}")
                expected = str(authority.get("sha256") or "")
                if _sha256_bytes(content) != expected or len(content) != authority.get(
                    "bytes"
                ):
                    raise CvrpF1Error(f"F1 input authority drift: {relative_text}")
                target = target_root / relative
                _write_exclusive(target, content)
                pair.append(
                    {
                        "path": relative_text,
                        "sha256": expected,
                        "bytes": len(content),
                        "kind": relative.suffix[1:],
                    }
                )
            cells = []
            for seed in F1_SEEDS[stage]:
                observed_limit = metric_cells[stage][(case_path, seed)]
                if observed_limit != limit:
                    raise CvrpF1Error(f"F1 time-limit authority drift: {case_path}")
                cells.append(
                    {
                        "cell_ordinal": cell_ordinal,
                        "stage_local_cell_ordinal": case_ordinal * 4
                        + F1_SEEDS[stage].index(seed),
                        "stage": stage,
                        "case_path": case_path,
                        "seed": seed,
                        "time_limit_sec": limit,
                    }
                )
                cell_ordinal += 1
            result.append(
                {
                    "stage": stage,
                    "case_ordinal": case_ordinal,
                    "case_path": case_path,
                    "case_display_id": vrp.stem,
                    "time_limit_sec": limit,
                    "pair_files": pair,
                    "pair_identity_sha256": _canonical_sha256(pair),
                    "cells": cells,
                }
            )
    if len(result) != 16 or cell_ordinal != 64:
        raise CvrpF1Error("F1 case/cell cardinality drift")
    return result


def _bind_case_facts(case_rows: list[dict[str, Any]], facts: Any) -> None:
    if not isinstance(facts, list) or len(facts) != 16:
        raise CvrpF1Error("F1 sealed loader did not return 16 case facts")
    by_path = {str(row.get("case_path")): row for row in facts if isinstance(row, dict)}
    for row in case_rows:
        fact = by_path.get(str(row["case_path"]))
        if fact is None:
            raise CvrpF1Error(f"F1 loader omitted {row['case_path']}")
        if (
            not isinstance(fact.get("dimension"), int)
            or not isinstance(fact.get("capacity"), int)
            or fact.get("bks") is None
            or fact.get("bks_routes") is None
        ):
            raise CvrpF1Error(
                f"F1 adjacent .sol authority was not loaded: {row['case_path']}"
            )
        row["parsed_facts"] = fact


def _build_jobs(
    root: Path,
    cases: Sequence[Mapping[str, Any]],
    arms: Sequence[Mapping[str, Any]],
    python: Mapping[str, Any],
) -> list[dict[str, Any]]:
    by_case = {str(row["case_path"]): row for row in cases}
    by_symbol = {F1_ARM_SYMBOL[str(row["arm"])]: row for row in arms}
    dependency_paths = _dependency_paths(str(python["executable_path"]))
    jobs: list[dict[str, Any]] = []
    ordinal = 0
    root_id = _canonical_sha256(
        {
            "schema": "scion.cvrp_f1_output_root_identity.v1",
            "absolute_path": str(root),
            "absent_before_creation": True,
        }
    )
    for stage in ("screening", "validation"):
        stage_cell = 0
        for case_path, limit in F1_CASES[stage]:
            case = by_case[case_path]
            files = {row["kind"]: row for row in case["pair_files"]}
            for seed in F1_SEEDS[stage]:
                sequence = F1_WILLIAMS[stage_cell % 4]
                for position, symbol in enumerate(sequence):
                    arm = _object(by_symbol[symbol], "arm")
                    job_id = f"{ordinal:03d}-{stage}-{Path(case_path).stem}-s{seed}-{arm['arm']}"
                    package_root = root / str(arm["package_root"])
                    workspace = root / str(arm["workspace"])
                    interchange = root / "interchange" / f"{job_id}.solver.json"
                    env = _child_environment(
                        package_root=package_root,
                        dependency_paths=dependency_paths,
                        data_root=root / "input_snapshot",
                    )
                    command = [
                        str(python["executable_path"]),
                        "-S",
                        "-m",
                        "scion.problems.cvrp.solver",
                        case_path,
                        "--seed",
                        str(seed),
                        "--time-limit",
                        str(limit),
                        "--output",
                        str(interchange),
                    ]
                    preimage = {
                        "schema": "scion.cvrp_f1_job_identity.v1",
                        "root_id": root_id,
                        "job_id": job_id,
                        "job_ordinal": ordinal,
                        "cell_ordinal": (0 if stage == "screening" else 32)
                        + stage_cell,
                        "stage": stage,
                        "arm": arm["arm"],
                        "arm_symbol": symbol,
                        "schedule_position": position,
                        "williams_sequence": sequence,
                        "case_path": case_path,
                        "case_identity_sha256": files["vrp"]["sha256"],
                        "solution_identity_sha256": files["sol"]["sha256"],
                        "seed": seed,
                        "time_limit_sec": limit,
                        "workspace_identity_sha256": arm["runtime_identity_sha256"],
                        "python_runtime_identity_sha256": python[
                            "runtime_identity_sha256"
                        ],
                        "command": command,
                        "environment": env,
                        "working_directory": str(workspace),
                    }
                    jobs.append(
                        {
                            **preimage,
                            "job_identity_sha256": _canonical_sha256(preimage),
                            "row_path": f"raw/{job_id}.json",
                            "interchange_path": f"interchange/{job_id}.solver.json",
                            "stdout_path": f"streams/{job_id}.stdout",
                            "stderr_path": f"streams/{job_id}.stderr",
                        }
                    )
                    ordinal += 1
                stage_cell += 1
    return jobs


def _validate_jobs(jobs: Sequence[Mapping[str, Any]]) -> None:
    if len(jobs) != 256:
        raise CvrpF1Error("F1 must declare exactly 256 jobs")
    if [int(row["job_ordinal"]) for row in jobs] != list(range(256)):
        raise CvrpF1Error("F1 job ordinals are not exact 0..255")
    job_ids = [str(row["job_id"]) for row in jobs]
    if len(set(job_ids)) != 256:
        raise CvrpF1Error("F1 job IDs are not unique")
    for stage in ("screening", "validation"):
        stage_jobs = [row for row in jobs if row["stage"] == stage]
        if len(stage_jobs) != 128:
            raise CvrpF1Error(f"F1 {stage} job cardinality drift")
        positions = {arm: [0, 0, 0, 0] for arm in F1_ARM_ORDER}
        adjacency = {(a, b): 0 for a in F1_ARM_ORDER for b in F1_ARM_ORDER if a != b}
        for cell in range(32):
            quartet = stage_jobs[cell * 4 : cell * 4 + 4]
            expected_sequence = F1_WILLIAMS[cell % 4]
            if "".join(str(row["arm_symbol"]) for row in quartet) != expected_sequence:
                raise CvrpF1Error(f"F1 {stage} Williams sequence drift")
            if len({row["arm"] for row in quartet}) != 4:
                raise CvrpF1Error(f"F1 {stage} quartet is incomplete")
            for position, row in enumerate(quartet):
                if row["schedule_position"] != position:
                    raise CvrpF1Error(f"F1 {stage} schedule position drift")
                positions[str(row["arm"])][position] += 1
            for left, right in zip(quartet, quartet[1:]):
                adjacency[(str(left["arm"]), str(right["arm"]))] += 1
        if any(counts != [8, 8, 8, 8] for counts in positions.values()):
            raise CvrpF1Error(f"F1 {stage} arm-position balance drift")
        if any(count != 8 for count in adjacency.values()):
            raise CvrpF1Error(f"F1 {stage} ordered-adjacency balance drift")


def _verify_job_bindings(manifest: Mapping[str, Any], root: Path) -> None:
    """Re-derive every frozen job field, path, argv, env, and identity."""

    jobs = _list(manifest, "jobs")
    _validate_jobs(jobs)
    root_id = _canonical_sha256(
        {
            "schema": "scion.cvrp_f1_output_root_identity.v1",
            "absolute_path": str(root),
            "absent_before_creation": True,
        }
    )
    if manifest.get("root_id") != root_id:
        raise CvrpF1Error("F1 output root identity derivation drift")
    arms = {str(row["arm"]): row for row in _list(manifest, "arms")}
    by_symbol = {F1_ARM_SYMBOL[arm]: row for arm, row in arms.items()}
    cases = {str(row["case_path"]): row for row in _list(manifest, "cases")}
    dependency_paths = tuple(str(value) for value in manifest["dependency_paths"])
    python = _object(manifest.get("python"), "Python identity")
    ordinal = 0
    cell_ordinal = 0
    for stage in ("screening", "validation"):
        stage_cell = 0
        for case_path, limit in F1_CASES[stage]:
            case = _object(cases.get(case_path), f"case {case_path}")
            pair = {str(row["kind"]): row for row in _list(case, "pair_files")}
            for seed in F1_SEEDS[stage]:
                sequence = F1_WILLIAMS[stage_cell % 4]
                for position, symbol in enumerate(sequence):
                    job = _object(jobs[ordinal], f"job {ordinal}")
                    arm = _object(by_symbol[symbol], f"arm {symbol}")
                    job_id = (
                        f"{ordinal:03d}-{stage}-{Path(case_path).stem}-"
                        f"s{seed}-{arm['arm']}"
                    )
                    package_root = root / str(arm["package_root"])
                    workspace = root / str(arm["workspace"])
                    interchange = root / "interchange" / f"{job_id}.solver.json"
                    environment = _child_environment(
                        package_root=package_root,
                        dependency_paths=dependency_paths,
                        data_root=root / "input_snapshot",
                    )
                    command = [
                        str(python["executable_path"]),
                        "-S",
                        "-m",
                        "scion.problems.cvrp.solver",
                        case_path,
                        "--seed",
                        str(seed),
                        "--time-limit",
                        str(limit),
                        "--output",
                        str(interchange),
                    ]
                    preimage = {
                        "schema": "scion.cvrp_f1_job_identity.v1",
                        "root_id": root_id,
                        "job_id": job_id,
                        "job_ordinal": ordinal,
                        "cell_ordinal": cell_ordinal,
                        "stage": stage,
                        "arm": arm["arm"],
                        "arm_symbol": symbol,
                        "schedule_position": position,
                        "williams_sequence": sequence,
                        "case_path": case_path,
                        "case_identity_sha256": pair["vrp"]["sha256"],
                        "solution_identity_sha256": pair["sol"]["sha256"],
                        "seed": seed,
                        "time_limit_sec": limit,
                        "workspace_identity_sha256": arm["runtime_identity_sha256"],
                        "python_runtime_identity_sha256": python[
                            "runtime_identity_sha256"
                        ],
                        "command": command,
                        "environment": environment,
                        "working_directory": str(workspace),
                    }
                    expected = {
                        **preimage,
                        "job_identity_sha256": _canonical_sha256(preimage),
                        "row_path": f"raw/{job_id}.json",
                        "interchange_path": f"interchange/{job_id}.solver.json",
                        "stdout_path": f"streams/{job_id}.stdout",
                        "stderr_path": f"streams/{job_id}.stderr",
                    }
                    if job != expected:
                        differing = sorted(
                            key
                            for key in set(job) | set(expected)
                            if job.get(key) != expected.get(key)
                        )
                        raise CvrpF1Error(
                            f"F1 job binding drift {ordinal}: {differing}"
                        )
                    ordinal += 1
                cell_ordinal += 1
                stage_cell += 1
    if ordinal != 256 or cell_ordinal != 64:
        raise CvrpF1Error("F1 job binding cardinality drift")


__all__ = [
    "_arm_replacement_bytes",
    "_base_identity_manifest",
    "_bind_case_facts",
    "_build_jobs",
    "_materialize_authorities",
    "_materialize_cases",
    "_validate_jobs",
    "_validate_metric_populations",
    "_validate_root_authorities",
    "_verify_job_bindings",
]
