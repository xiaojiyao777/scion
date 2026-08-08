"""Evaluate recorded candidates without reopening the research campaign.

This module deliberately has one small job: select a recorded candidate from a
campaign, reconstruct it from full-file replacements, and run the
problem-owned Protocol.  Candidate identifiers are selectors, not authority;
replay identity, attribution, leases, signatures, and digest chains are not
part of this eval-only path.
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import yaml


SCHEMA_VERSION = "scion.fixed_candidate_replay_manifest.v1"
COMPARISON_SCHEMA_VERSION = "scion.fixed_candidate_replay_comparison.v1"
DEFAULT_MANIFEST_FILENAME = "fixed_candidate_replay_manifest.v1.json"
DEFAULT_COMPARISON_FILENAME = "fixed_candidate_replay_comparison.v1.json"
REPLAY_ARMS = ["on"]
REPLAY_STAGES = ["screening", "validation", "frozen"]
DEFAULT_REPLAY_STAGES = ["screening"]

_CHAMPION_REF_RE = re.compile(r"champions/champion_v(?P<version>[0-9]+)")
_OPAQUE_CHAMPION_REF_RE = re.compile(
    r"artifact:champion_v(?P<version>[0-9]+)(?:#[^/]*)?"
)
_PLAIN_ID_FIELDS = ("candidate_id", "hypothesis_id", "branch_id")


def build_fixed_candidate_replay_manifest(
    source: str | Path,
    *,
    source_arm: str,
    comparison_id: str,
    max_candidates: int | None = None,
    candidate_ids: Sequence[str] | None = None,
    hypothesis_ids: Sequence[str] | None = None,
    stages: Sequence[str] | None = None,
    replay_arms: Sequence[str] | None = None,
    conditional_stage_progression: bool = False,
    expand_screening: bool = False,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a manifest from candidates recorded inside one source campaign."""

    _require_on_arm(source_arm, label="source_arm")
    arm_filter = _replay_arm_filter(replay_arms)
    stage_filter = _stage_filter(stages)
    if max_candidates is not None and max_candidates < 0:
        raise ValueError("max_candidates must be non-negative")
    if not _clean_str(comparison_id):
        raise ValueError("comparison_id must be non-empty")

    index_path, campaign_dir = resolve_formal_candidate_index(source)
    candidate_filter = _candidate_filter(
        candidate_ids=candidate_ids,
        hypothesis_ids=hypothesis_ids,
    )
    selected: list[dict[str, Any]] = []
    omitted: list[dict[str, Any]] = []
    filtered_out = 0

    for row_index, row in enumerate(_read_index_rows(index_path)):
        if not _row_matches_candidate_filter(row, candidate_filter):
            filtered_out += 1
            continue
        reasons, artifact_ref, metadata = _inspect_index_candidate(
            row,
            campaign_dir=campaign_dir,
            explicit_stage_filter=stages is not None,
        )
        if reasons:
            omitted.append(_omitted_row(row_index, row, reasons))
            continue
        assert metadata is not None
        if max_candidates is not None and len(selected) >= max_candidates:
            omitted.append(_omitted_row(row_index, row, ["max_candidates_exceeded"]))
            continue
        selected.append(
            _candidate_source_entry(
                row_index=row_index,
                row=row,
                metadata=metadata,
                artifact_ref=artifact_ref,
            )
        )

    candidates = [
        {
            **candidate,
            "stage": stage,
            "replay_stage": stage,
        }
        for candidate in selected
        for stage in stage_filter
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "comparison_id": _clean_str(comparison_id),
        "source_campaign_dir": str(campaign_dir),
        "source_arm": "on",
        "generated_at": generated_at or _utc_now_iso(),
        "candidate_filter": candidate_filter,
        "stage_filter": stage_filter,
        "filtered_out_row_count": filtered_out,
        "candidate_count": len(candidates),
        "source_candidate_count": len(selected),
        "replay_arms": arm_filter,
        "conditional_stage_progression": bool(conditional_stage_progression),
        "expand_screening": bool(expand_screening),
        "candidates": candidates,
        "omitted_rows": omitted,
    }


def write_fixed_candidate_replay_manifest(
    source: str | Path,
    *,
    source_arm: str,
    comparison_id: str,
    output_path: str | Path | None = None,
    max_candidates: int | None = None,
    candidate_ids: Sequence[str] | None = None,
    hypothesis_ids: Sequence[str] | None = None,
    stages: Sequence[str] | None = None,
    replay_arms: Sequence[str] | None = None,
    conditional_stage_progression: bool = False,
    expand_screening: bool = False,
) -> Path:
    """Build and write an eval-only manifest."""

    index_path, _ = resolve_formal_candidate_index(source)
    destination = (
        Path(output_path).expanduser().resolve()
        if output_path is not None
        else index_path.parent / DEFAULT_MANIFEST_FILENAME
    )
    manifest = build_fixed_candidate_replay_manifest(
        source,
        source_arm=source_arm,
        comparison_id=comparison_id,
        max_candidates=max_candidates,
        candidate_ids=candidate_ids,
        hypothesis_ids=hypothesis_ids,
        stages=stages,
        replay_arms=replay_arms,
        conditional_stage_progression=conditional_stage_progression,
        expand_screening=expand_screening,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(_manifest_json(manifest), encoding="utf-8")
    return destination


def resolve_formal_candidate_index(source: str | Path) -> tuple[Path, Path]:
    """Resolve the standard candidate index and its owning campaign."""

    source_path = Path(source).expanduser().resolve()
    if source_path.is_dir():
        campaign_dir = source_path
        index_path = campaign_dir / "artifacts" / "formal_candidates" / "index.jsonl"
    else:
        index_path = source_path
        if index_path.name != "index.jsonl":
            raise ValueError(
                "source must be a campaign directory or formal_candidates/index.jsonl"
            )
        campaign_dir = _infer_campaign_dir_from_index(index_path)
    expected = (
        campaign_dir / "artifacts" / "formal_candidates" / "index.jsonl"
    ).resolve()
    if index_path != expected:
        raise ValueError("candidate index must be inside its source campaign")
    if not index_path.is_file():
        raise FileNotFoundError(f"formal candidate index not found: {index_path}")
    return index_path, campaign_dir.resolve()


def execute_fixed_candidate_replay(
    manifest_path: str | Path,
    *,
    problem_yaml_path: str | Path,
    output_dir: str | Path,
    protocol_path: str | Path | None = None,
    split_path: str | Path | None = None,
    seeds_path: str | Path | None = None,
    max_candidates: int | None = None,
    time_limit_sec: int | None = None,
    protocol_factory: Callable[..., Any] | None = None,
    comparison_output_path: str | Path | None = None,
) -> Path:
    """Run the fixed candidate through the problem-owned Protocol only."""

    manifest_file = Path(manifest_path).expanduser().resolve()
    manifest = _load_manifest(manifest_file)
    _require_on_arm(_required_str(manifest, "source_arm"), label="source_arm")
    arms = _manifest_replay_arms(manifest)
    source_campaign_dir = Path(
        _required_str(manifest, "source_campaign_dir")
    ).expanduser().resolve()
    if not source_campaign_dir.is_dir():
        raise FileNotFoundError(f"source campaign not found: {source_campaign_dir}")
    candidates = _manifest_candidates(manifest)
    conditional = bool(manifest.get("conditional_stage_progression", False))
    expand_screening = bool(manifest.get("expand_screening", False))
    problem_path = Path(problem_yaml_path).expanduser().resolve()
    if protocol_factory is None:
        _require_problem_spec_v1_for_fixed_replay(problem_path)
    if max_candidates is not None and max_candidates < 0:
        raise ValueError("max_candidates must be non-negative")

    groups = (
        _candidate_stage_groups(candidates)
        if conditional
        else [[candidate] for candidate in candidates]
    )
    if max_candidates is not None:
        if conditional:
            groups = groups[:max_candidates]
        else:
            groups = groups[:max_candidates]
    evaluated_candidates = [candidate for group in groups for candidate in group]

    out_dir = Path(output_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    comparison_path = (
        Path(comparison_output_path).expanduser().resolve()
        if comparison_output_path is not None
        else out_dir / DEFAULT_COMPARISON_FILENAME
    )
    protocol_path_resolved = _optional_resolved_path(protocol_path)
    split_path_resolved = _optional_resolved_path(split_path)
    seeds_path_resolved = _optional_resolved_path(seeds_path)
    rows: list[dict[str, Any]] = []

    def run(candidate: Mapping[str, Any], *, expand: bool) -> dict[str, Any]:
        return _execute_replay_row(
            manifest_path=manifest_file,
            candidate=candidate,
            arm=arms[0],
            source_campaign_dir=source_campaign_dir,
            problem_yaml_path=problem_path,
            protocol_path=protocol_path_resolved,
            split_path=split_path_resolved,
            seeds_path=seeds_path_resolved,
            output_dir=out_dir,
            time_limit_sec=time_limit_sec,
            protocol_factory=protocol_factory,
            expand=expand,
        )

    for group in groups:
        blocked_by: Mapping[str, Any] | None = None
        for candidate in group:
            stage = _stage_name(candidate)
            expanded = expand_screening and stage == "screening"
            if blocked_by is not None:
                rows.append(
                    _skipped_replay_row(
                        candidate,
                        expanded=expanded,
                        blocked_by=blocked_by,
                    )
                )
                continue
            row = run(candidate, expand=expanded)
            rows.append(row)
            if (
                conditional
                and stage == "validation"
                and row.get("status") == "completed"
                and _clean_str(row.get("gate_outcome")) == "expand"
            ):
                row = run(candidate, expand=True)
                rows.append(row)
            if conditional and (
                row.get("status") != "completed"
                or _clean_str(row.get("gate_outcome")) != "pass"
            ):
                blocked_by = row

    artifact = {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "source_manifest_ref": str(manifest_file),
        "source_campaign_dir": str(source_campaign_dir),
        "comparison_id": _clean_str(manifest.get("comparison_id")),
        "generated_at": _utc_now_iso(),
        "replay_arm": "on",
        "conditional_stage_progression": conditional,
        "expand_screening": expand_screening,
        "stage_filter": _string_list(manifest.get("stage_filter"))
        or list(DEFAULT_REPLAY_STAGES),
        "candidate_count": len(evaluated_candidates),
        "row_count": len(rows),
        "evaluation_only": True,
        "rows": rows,
    }
    comparison_path.parent.mkdir(parents=True, exist_ok=True)
    comparison_path.write_text(_manifest_json(artifact), encoding="utf-8")
    return comparison_path


def materialize_candidate_workspace(
    *,
    candidate: Mapping[str, Any],
    candidate_patch: Mapping[str, Any],
    source_campaign_dir: str | Path,
    output_dir: str | Path,
    arm: str,
) -> Path:
    """Copy ``champions/champion_vN`` and apply safe full-file replacements."""

    _require_on_arm(arm, label="arm")
    _validate_plain_candidate_fields(candidate, candidate_patch)
    source_dir = Path(source_campaign_dir).expanduser().resolve()
    base_workspace = resolve_candidate_base_workspace(
        candidate_patch,
        source_campaign_dir=source_dir,
    )
    files = _candidate_files(candidate_patch)
    candidate_id = _safe_path_token(
        _required_str(candidate_patch, "candidate_id")
    )
    destination_root = Path(output_dir).expanduser().resolve()
    workspace = destination_root / "materialized" / candidate_id / "on"
    _assert_descendant(workspace, destination_root)
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(base_workspace, workspace)
    _make_tree_user_writable(workspace)
    for entry in files:
        _apply_full_file_patch_entry(workspace, entry)
    return workspace


def resolve_candidate_base_workspace(
    candidate_patch: Mapping[str, Any],
    *,
    source_campaign_dir: str | Path,
) -> Path:
    """Resolve only a champion snapshot owned by the source campaign."""

    source_dir = Path(source_campaign_dir).expanduser().resolve()
    base = candidate_patch.get("base")
    if not isinstance(base, Mapping):
        raise ValueError("candidate patch missing base metadata")
    base_ref = _required_str(base, "base_workspace_ref")
    match = _CHAMPION_REF_RE.fullmatch(base_ref)
    if match is None:
        match = _OPAQUE_CHAMPION_REF_RE.fullmatch(base_ref)
    if match is None:
        raise ValueError("candidate base must be champions/champion_vN in source campaign")
    version = match.group("version")
    declared_version = _clean_str(base.get("base_champion_id"))
    if declared_version and declared_version != version:
        raise ValueError("base_champion_id does not match base workspace")
    base_workspace = (source_dir / "champions" / f"champion_v{version}").resolve()
    _assert_descendant(base_workspace, source_dir)
    if not base_workspace.is_dir():
        raise FileNotFoundError(f"base workspace not found: {base_workspace}")
    return base_workspace


def _inspect_index_candidate(
    row: Mapping[str, Any],
    *,
    campaign_dir: Path,
    explicit_stage_filter: bool,
) -> tuple[list[str], str, Mapping[str, Any] | None]:
    reasons: list[str] = []
    if _clean_str(row.get("artifact_status")) not in {"", "recorded"}:
        reasons.append("artifact_not_recorded")
    if not explicit_stage_filter and (
        _clean_str(row.get("stage")) or "screening"
    ) != "screening":
        reasons.append("non_screening_stage")
    artifact_ref = _clean_str(row.get("artifact_ref"))
    if not artifact_ref:
        return _dedupe([*reasons, "missing_artifact_ref"]), "", None
    try:
        artifact_path = _resolve_campaign_artifact(artifact_ref, campaign_dir)
    except ValueError:
        return _dedupe([*reasons, "artifact_path_outside_campaign"]), artifact_ref, None
    if not artifact_path.is_file():
        return _dedupe([*reasons, "candidate_patch_missing"]), artifact_ref, None
    try:
        metadata = _load_json_object(artifact_path)
    except (OSError, json.JSONDecodeError, ValueError):
        return _dedupe([*reasons, "candidate_patch_unreadable"]), artifact_ref, None
    for key in _PLAIN_ID_FIELDS:
        row_value = _clean_str(row.get(key))
        artifact_value = _clean_str(metadata.get(key))
        if not row_value or not artifact_value or row_value != artifact_value:
            reasons.append(f"candidate_patch_{key}_mismatch")
    try:
        resolve_candidate_base_workspace(
            metadata,
            source_campaign_dir=campaign_dir,
        )
        _candidate_files(metadata)
    except (OSError, ValueError):
        reasons.append("candidate_patch_not_materializable")
    return _dedupe(reasons), artifact_ref, metadata


def _candidate_source_entry(
    *,
    row_index: int,
    row: Mapping[str, Any],
    metadata: Mapping[str, Any],
    artifact_ref: str,
) -> dict[str, Any]:
    source_stage = _clean_str(metadata.get("stage") or row.get("stage")) or "screening"
    replay_metadata = metadata.get("replay_metadata")
    if not isinstance(replay_metadata, Mapping):
        replay_metadata = {}
    return {
        "candidate_order_index": row_index,
        "candidate_id": _required_str(metadata, "candidate_id"),
        "branch_id": _required_str(metadata, "branch_id"),
        "lineage_id": _clean_str(metadata.get("lineage_id")),
        "hypothesis_id": _required_str(metadata, "hypothesis_id"),
        "source_stage": source_stage,
        "artifact_ref": artifact_ref,
        "target_files": [
            _required_entry_path(entry) for entry in _candidate_files(metadata)
        ],
        "selected_surface": _clean_str(
            replay_metadata.get("selected_surface")
            or metadata.get("selected_surface")
        ),
        "hypothesis_action": _hypothesis_action(metadata),
        "source_raw_metrics_ref": _clean_str(
            replay_metadata.get("raw_metrics_ref") or metadata.get("experiment_ref")
        ),
    }


def _candidate_files(candidate_patch: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    materialization = candidate_patch.get("replay_materialization")
    if isinstance(materialization, Mapping):
        representation = _clean_str(materialization.get("representation"))
        if representation and representation != "cumulative_full_file_replacement":
            raise ValueError("unsupported replay materialization representation")
        raw_files = materialization.get("files")
        allow_empty = True
    else:
        patch = candidate_patch.get("patch")
        raw_files = patch.get("files") if isinstance(patch, Mapping) else None
        allow_empty = False
    if not isinstance(raw_files, list) or (not raw_files and not allow_empty):
        raise ValueError("candidate artifact has no full-file replacements")
    files: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    for raw_entry in raw_files:
        if not isinstance(raw_entry, Mapping):
            raise ValueError("candidate file entry must be an object")
        path = _required_entry_path(raw_entry)
        if path in seen:
            raise ValueError(f"duplicate candidate file: {path}")
        seen.add(path)
        action = _clean_str(raw_entry.get("action")) or "modify"
        if action not in {"create", "modify", "delete"}:
            raise ValueError(f"unsupported candidate file action: {action}")
        if action != "delete" and "code_content" not in raw_entry:
            raise ValueError(f"candidate file missing code_content: {path}")
        files.append(raw_entry)
    return files


def _apply_full_file_patch_entry(workspace: Path, entry: Mapping[str, Any]) -> None:
    relative_path = _required_entry_path(entry)
    target = _workspace_child(workspace, relative_path)
    action = _clean_str(entry.get("action")) or "modify"
    if action == "create":
        if target.exists():
            raise ValueError(f"candidate create target already exists: {relative_path}")
    elif action in {"modify", "delete"}:
        if not target.is_file():
            raise ValueError(f"candidate {action} target is missing: {relative_path}")
    else:
        raise ValueError(f"unsupported candidate file action: {action}")
    if action == "delete":
        target.unlink()
        return
    content = entry.get("code_content")
    if not isinstance(content, str):
        raise ValueError(f"candidate file content must be text: {relative_path}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _resolve_campaign_artifact(artifact_ref: str, campaign_dir: Path) -> Path:
    ref = artifact_ref.split("#", 1)[0].strip()
    if not ref:
        raise ValueError("empty artifact path")
    path = Path(ref).expanduser()
    resolved = path.resolve() if path.is_absolute() else (campaign_dir / path).resolve()
    _assert_descendant(resolved, campaign_dir)
    return resolved


def _validate_plain_candidate_fields(
    candidate: Mapping[str, Any],
    candidate_patch: Mapping[str, Any],
) -> None:
    for key in _PLAIN_ID_FIELDS:
        manifest_value = _required_str(candidate, key)
        artifact_value = _required_str(candidate_patch, key)
        if manifest_value != artifact_value:
            raise ValueError(f"candidate artifact {key} does not match manifest")


def _execute_replay_row(
    *,
    manifest_path: Path,
    candidate: Mapping[str, Any],
    arm: str,
    source_campaign_dir: Path,
    problem_yaml_path: Path,
    protocol_path: Path | None,
    split_path: Path | None,
    seeds_path: Path | None,
    output_dir: Path,
    time_limit_sec: int | None,
    protocol_factory: Callable[..., Any] | None,
    expand: bool,
) -> dict[str, Any]:
    row = _base_comparison_row(candidate)
    row["expanded"] = expand
    try:
        artifact_ref = _required_str(candidate, "artifact_ref")
        patch_path = _resolve_campaign_artifact(artifact_ref, source_campaign_dir)
        if not patch_path.is_file():
            raise FileNotFoundError(f"candidate.patch.json not found: {artifact_ref}")
        candidate_patch = _load_json_object(patch_path)
        workspace = materialize_candidate_workspace(
            candidate=candidate,
            candidate_patch=candidate_patch,
            source_campaign_dir=source_campaign_dir,
            output_dir=output_dir,
            arm=arm,
        )
        champion_workspace = resolve_candidate_base_workspace(
            candidate_patch,
            source_campaign_dir=source_campaign_dir,
        )
        protocol = _build_protocol(
            problem_yaml_path=problem_yaml_path,
            protocol_path=protocol_path,
            split_path=split_path,
            seeds_path=seeds_path,
            output_dir=output_dir,
            candidate=candidate,
            arm=arm,
            time_limit_sec=time_limit_sec,
            protocol_factory=protocol_factory,
        )
        selected_surface = _clean_str(candidate.get("selected_surface")) or None
        action = _clean_str(candidate.get("hypothesis_action")) or "modify"
        canary = protocol.run_canary(
            str(workspace),
            str(champion_workspace),
            selected_surface=selected_surface,
        )
        result = protocol.run_experiment(
            _stage_from_candidate(candidate),
            str(workspace),
            str(champion_workspace),
            action,
            expand=expand,
            selected_surface=selected_surface,
        )
        row.update(
            {
                "status": "completed",
                "materialized_workspace_ref": str(workspace),
                "raw_metrics_ref": _clean_str(getattr(result, "raw_metrics_ref", "")),
                "stats": _stats_payload(getattr(result, "stats", None)),
                "gate_outcome": _clean_str(getattr(result, "gate_outcome", "")),
                "reason_codes": list(getattr(result, "reason_codes", ()) or ()),
                "canary": _canary_payload(canary),
                "objective_semantics": _clean_str(
                    getattr(result, "objective_semantics", "")
                ),
            }
        )
    except Exception as exc:  # one bad row remains visible without losing the report
        row.update(
            {
                "status": "error",
                "error": {"type": type(exc).__name__, "message": str(exc)},
            }
        )
    return row


def _candidate_stage_groups(
    candidates: Sequence[Mapping[str, Any]],
) -> list[list[Mapping[str, Any]]]:
    grouped: dict[tuple[int, str], list[Mapping[str, Any]]] = {}
    for candidate in candidates:
        key = (
            int(candidate.get("candidate_order_index", 0)),
            _clean_str(candidate.get("artifact_ref")),
        )
        grouped.setdefault(key, []).append(candidate)
    stage_order = {stage: index for index, stage in enumerate(REPLAY_STAGES)}
    result: list[list[Mapping[str, Any]]] = []
    for group in grouped.values():
        names = [_stage_name(candidate) for candidate in group]
        if len(names) != len(set(names)):
            raise ValueError("conditional replay candidate has duplicate stages")
        result.append(sorted(group, key=lambda item: stage_order[_stage_name(item)]))
    return result


def _skipped_replay_row(
    candidate: Mapping[str, Any],
    *,
    expanded: bool,
    blocked_by: Mapping[str, Any],
) -> dict[str, Any]:
    row = _base_comparison_row(candidate)
    row.update(
        {
            "status": "skipped",
            "expanded": expanded,
            "skip_reason": "PREVIOUS_STAGE_NOT_PASSED",
            "blocked_by_stage": _clean_str(blocked_by.get("stage")),
            "blocked_by_status": _clean_str(blocked_by.get("status")),
            "blocked_by_gate_outcome": _clean_str(blocked_by.get("gate_outcome")),
        }
    )
    return row


def _base_comparison_row(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "candidate_order_index": candidate.get("candidate_order_index"),
        "candidate_id": _clean_str(candidate.get("candidate_id")),
        "branch_id": _clean_str(candidate.get("branch_id")),
        "hypothesis_id": _clean_str(candidate.get("hypothesis_id")),
        "stage": _stage_name(candidate),
        "source_stage": _clean_str(candidate.get("source_stage")),
        "replay_stage": _stage_name(candidate),
        "arm": "on",
        "artifact_ref": _clean_str(candidate.get("artifact_ref")),
        "selected_surface": _clean_str(candidate.get("selected_surface")),
        "hypothesis_action": _clean_str(candidate.get("hypothesis_action")) or "modify",
        "source_raw_metrics_ref": _clean_str(candidate.get("source_raw_metrics_ref")),
    }


def _build_protocol(
    *,
    problem_yaml_path: Path,
    protocol_path: Path | None,
    split_path: Path | None,
    seeds_path: Path | None,
    output_dir: Path,
    candidate: Mapping[str, Any],
    arm: str,
    time_limit_sec: int | None,
    protocol_factory: Callable[..., Any] | None,
) -> Any:
    if protocol_factory is not None:
        return protocol_factory(
            problem_yaml_path=problem_yaml_path,
            protocol_path=protocol_path,
            split_path=split_path,
            seeds_path=seeds_path,
            output_dir=output_dir,
            candidate=candidate,
            arm=arm,
            time_limit_sec=time_limit_sec,
        )

    from scion.config.problem import ProtocolConfig, SeedLedgerConfig, SplitManifest
    from scion.problem.bridge import (
        bridge_problem_spec_v1,
        load_problem_spec_v1_from_yaml,
    )
    from scion.protocol.experiment import ExperimentProtocol, SeedLedger, SplitManager
    from scion.runtime.runner import ResourceLimits
    from scion.runtime.subprocess_runner import LocalSubprocessRunner

    _require_problem_spec_v1_for_fixed_replay(problem_yaml_path)
    bridge = bridge_problem_spec_v1(load_problem_spec_v1_from_yaml(problem_yaml_path))
    config_dir = problem_yaml_path.parent
    protocol_config = ProtocolConfig.from_yaml(
        protocol_path or config_dir / "protocol.yaml"
    ).with_problem_measurement(bridge.problem_spec, governance_mode="on")
    split_manifest = SplitManifest.from_yaml(
        split_path or config_dir / "split_manifest.yaml"
    )
    seed_ledger = SeedLedgerConfig.from_yaml(
        seeds_path or config_dir / "seed_ledger.yaml"
    )
    metrics_dir = (
        output_dir
        / "metrics"
        / _safe_path_token(_clean_str(candidate.get("candidate_id")) or "candidate")
        / _safe_path_token(_stage_name(candidate))
        / "on"
    )
    limit = int(time_limit_sec) if time_limit_sec is not None else 300
    return ExperimentProtocol(
        protocol_config=protocol_config,
        split_manager=SplitManager(split_manifest),
        seed_ledger=SeedLedger(seed_ledger),
        runner=LocalSubprocessRunner(ResourceLimits(timeout_sec=limit)),
        time_limit_sec=limit,
        metrics_dir=str(metrics_dir),
        metric_specs=bridge.metric_specs,
        objective_policy=bridge.objective_policy,
        require_metric_specs=True,
        problem_spec=bridge.problem_spec,
    )


def _require_problem_spec_v1_for_fixed_replay(problem_yaml_path: Path) -> None:
    try:
        payload = yaml.safe_load(problem_yaml_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ValueError(
            "fixed replay requires ProblemSpecV1; use problem-v1.yaml for "
            f"--problem (failed to parse {problem_yaml_path}: {exc})"
        ) from exc
    if not isinstance(payload, Mapping) or payload.get("spec_version") != "problem-v1":
        raise ValueError(
            "fixed replay requires ProblemSpecV1; use problem-v1.yaml for --problem"
        )


def _infer_campaign_dir_from_index(index_path: Path) -> Path:
    parts = index_path.parts
    if len(parts) >= 3 and parts[-3:-1] == ("artifacts", "formal_candidates"):
        return index_path.parents[2].resolve()
    raise ValueError("candidate index must be artifacts/formal_candidates/index.jsonl")


def _read_index_rows(index_path: Path) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    with index_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid JSON in formal candidate index line {line_number}"
                ) from exc
            if not isinstance(row, Mapping):
                raise ValueError(
                    f"formal candidate index line {line_number} is not an object"
                )
            rows.append(row)
    return rows


def _candidate_filter(
    *,
    candidate_ids: Sequence[str] | None,
    hypothesis_ids: Sequence[str] | None,
) -> dict[str, list[str]]:
    return {
        "candidate_ids": sorted(set(_string_list(candidate_ids))),
        "hypothesis_ids": sorted(set(_string_list(hypothesis_ids))),
    }


def _row_matches_candidate_filter(
    row: Mapping[str, Any],
    candidate_filter: Mapping[str, Sequence[str]],
) -> bool:
    candidate_ids = set(candidate_filter.get("candidate_ids") or ())
    hypothesis_ids = set(candidate_filter.get("hypothesis_ids") or ())
    if not candidate_ids and not hypothesis_ids:
        return True
    return (
        _clean_str(row.get("candidate_id")) in candidate_ids
        or _clean_str(row.get("hypothesis_id")) in hypothesis_ids
    )


def _stage_filter(stages: Sequence[str] | None) -> list[str]:
    clean = list(dict.fromkeys(_string_list(stages or DEFAULT_REPLAY_STAGES)))
    if not clean:
        clean = list(DEFAULT_REPLAY_STAGES)
    unsupported = [stage for stage in clean if stage not in REPLAY_STAGES]
    if unsupported:
        raise ValueError(f"unsupported replay stage(s): {unsupported}")
    return clean


def _replay_arm_filter(replay_arms: Sequence[str] | None) -> list[str]:
    clean = list(dict.fromkeys(_string_list(replay_arms or REPLAY_ARMS)))
    if clean != ["on"]:
        raise ValueError("fixed replay supports only the on arm")
    return clean


def _manifest_replay_arms(manifest: Mapping[str, Any]) -> list[str]:
    arms = manifest.get("replay_arms")
    if not isinstance(arms, list):
        raise ValueError("manifest replay_arms must be a list")
    return _replay_arm_filter(arms)


def _manifest_candidates(manifest: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    candidates = manifest.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("manifest candidates must be a list")
    if any(not isinstance(candidate, Mapping) for candidate in candidates):
        raise ValueError("manifest candidate entries must be objects")
    return list(candidates)


def _load_manifest(path: Path) -> Mapping[str, Any]:
    manifest = _load_json_object(path)
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported fixed-candidate replay manifest: {path}")
    return manifest


def _load_json_object(path: Path) -> Mapping[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, Mapping):
        raise ValueError(f"JSON artifact is not an object: {path}")
    return loaded


def _hypothesis_action(metadata: Mapping[str, Any]) -> str:
    action = _clean_str(metadata.get("hypothesis_action"))
    if action:
        return action
    hypothesis = metadata.get("hypothesis")
    if isinstance(hypothesis, Mapping) and _clean_str(hypothesis.get("action")):
        return _clean_str(hypothesis.get("action"))
    actions = {
        _clean_str(entry.get("action"))
        for entry in _candidate_files(metadata)
        if _clean_str(entry.get("action"))
    }
    if actions == {"create"}:
        return "create_new"
    if actions == {"delete"}:
        return "remove"
    return "modify"


def _required_entry_path(entry: Mapping[str, Any]) -> str:
    value = _clean_str(entry.get("file_path") or entry.get("path"))
    rel = Path(value)
    if (
        not value
        or "\\" in value
        or rel.is_absolute()
        or any(part in {"", ".", ".."} for part in rel.parts)
    ):
        raise ValueError(f"unsafe candidate file path: {value}")
    return value


def _workspace_child(workspace: Path, relative_path: str) -> Path:
    target = (workspace / relative_path).resolve()
    _assert_descendant(target, workspace.resolve())
    return target


def _assert_descendant(path: Path, root: Path) -> None:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"path escapes allowed root: {path}") from exc


def _make_tree_user_writable(root: Path) -> None:
    for path in [root, *root.rglob("*")]:
        try:
            mode = path.stat().st_mode
            path.chmod(mode | (0o700 if path.is_dir() else 0o600))
        except OSError:
            continue


def _stage_name(candidate: Mapping[str, Any]) -> str:
    stage = _clean_str(candidate.get("stage")) or "screening"
    if stage not in REPLAY_STAGES:
        raise ValueError(f"unsupported replay stage: {stage}")
    return stage


def _stage_from_candidate(candidate: Mapping[str, Any]) -> Any:
    from scion.core.models import ExperimentStage

    return {
        "screening": ExperimentStage.SCREENING,
        "validation": ExperimentStage.VALIDATION,
        "frozen": ExperimentStage.FROZEN,
    }[_stage_name(candidate)]


def _stats_payload(stats: Any) -> dict[str, Any]:
    if stats is None:
        return {}
    return {
        "n_cases": getattr(stats, "n_cases", None),
        "wins": getattr(stats, "wins", None),
        "losses": getattr(stats, "losses", None),
        "ties": getattr(stats, "ties", None),
        "win_rate": getattr(stats, "win_rate", None),
        "median_delta": getattr(stats, "median_delta", None),
        "ci_low": getattr(stats, "ci_low", None),
        "ci_high": getattr(stats, "ci_high", None),
    }


def _canary_payload(canary: Any) -> dict[str, Any]:
    return {
        "passed": bool(getattr(canary, "passed", False)),
        "reason": getattr(canary, "reason", None),
    }


def _omitted_row(
    row_index: int,
    row: Mapping[str, Any],
    reasons: Sequence[str],
) -> dict[str, Any]:
    return {
        "candidate_order_index": row_index,
        "candidate_id": _clean_str(row.get("candidate_id")),
        "branch_id": _clean_str(row.get("branch_id")),
        "hypothesis_id": _clean_str(row.get("hypothesis_id")),
        "stage": _clean_str(row.get("stage")),
        "artifact_ref": _clean_str(row.get("artifact_ref")),
        "reasons": _dedupe(list(reasons)),
    }


def _required_str(data: Mapping[str, Any], key: str) -> str:
    value = _clean_str(data.get(key))
    if not value:
        raise ValueError(f"missing required field: {key}")
    return value


def _require_on_arm(value: str, *, label: str) -> None:
    if _clean_str(value) != "on":
        raise ValueError(f"{label} must be on for eval-only fixed replay")


def _optional_resolved_path(value: str | Path | None) -> Path | None:
    return Path(value).expanduser().resolve() if value is not None else None


def _safe_path_token(value: str) -> str:
    token = "".join(
        char if char.isalnum() or char in {"-", "_", "."} else "_"
        for char in value.strip()
    ).strip("._")
    return token or "item"


def _manifest_json(manifest: Mapping[str, Any]) -> str:
    return json.dumps(manifest, indent=2, sort_keys=True) + "\n"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _clean_str(value: Any) -> str:
    return str(value or "").strip()


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, (list, tuple, set)):
        return [_clean_str(item) for item in value if _clean_str(item)]
    return []


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


__all__ = [
    "COMPARISON_SCHEMA_VERSION",
    "DEFAULT_COMPARISON_FILENAME",
    "DEFAULT_MANIFEST_FILENAME",
    "REPLAY_ARMS",
    "SCHEMA_VERSION",
    "build_fixed_candidate_replay_manifest",
    "execute_fixed_candidate_replay",
    "materialize_candidate_workspace",
    "resolve_candidate_base_workspace",
    "resolve_formal_candidate_index",
    "write_fixed_candidate_replay_manifest",
]
