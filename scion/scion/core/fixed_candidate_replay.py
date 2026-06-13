"""Build and execute fixed-candidate replay artifacts."""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import yaml

from scion.core.evidence_recording.replay_identity import (
    formal_replay_identity_missing_keys,
)


SCHEMA_VERSION = "scion.fixed_candidate_replay_manifest.v1"
COMPARISON_SCHEMA_VERSION = "scion.fixed_candidate_replay_comparison.v1"
DEFAULT_MANIFEST_FILENAME = "fixed_candidate_replay_manifest.v1.json"
DEFAULT_COMPARISON_FILENAME = "fixed_candidate_replay_comparison.v1.json"
REPLAY_ARMS = ["on", "record_only"]
MEASUREMENT_GOVERNANCE_BY_ARM = {
    "on": "on",
    "record_only": "off_record_only",
}


def build_fixed_candidate_replay_manifest(
    source: str | Path,
    *,
    source_arm: str,
    comparison_id: str,
    max_candidates: int | None = None,
    candidate_ids: Sequence[str] | None = None,
    hypothesis_ids: Sequence[str] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Return a deterministic manifest for fixed-candidate governance replay.

    The builder only reads ``formal_candidates/index.jsonl`` and referenced
    ``candidate.patch.json`` files. It never materializes workspaces, runs
    protocol replay, or mutates campaign state.
    """

    if max_candidates is not None and max_candidates < 0:
        raise ValueError("max_candidates must be non-negative")
    index_path, source_campaign_dir = resolve_formal_candidate_index(source)
    rows = _read_index_rows(index_path)
    candidate_filter = _candidate_filter(
        candidate_ids=candidate_ids,
        hypothesis_ids=hypothesis_ids,
    )
    filtered_out_row_count = 0

    candidates: list[dict[str, Any]] = []
    omitted_rows: list[dict[str, Any]] = []
    for row_index, row in enumerate(rows):
        if not _row_matches_candidate_filter(row, candidate_filter):
            filtered_out_row_count += 1
            continue
        row_reasons = _row_omission_reasons(row)
        artifact_ref = _clean_str(row.get("artifact_ref"))
        metadata_path = _resolve_artifact_path(
            artifact_ref,
            campaign_dir=source_campaign_dir,
            index_dir=index_path.parent,
        )
        metadata: Mapping[str, Any] | None = None

        if not row_reasons:
            if metadata_path is None:
                row_reasons.append("missing_artifact_ref")
            elif not metadata_path.is_file():
                row_reasons.append("candidate_patch_missing")
            else:
                try:
                    loaded = json.loads(metadata_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    row_reasons.append("candidate_patch_unreadable")
                else:
                    if not isinstance(loaded, Mapping):
                        row_reasons.append("candidate_patch_invalid")
                    else:
                        metadata = loaded
                        row_reasons.extend(_metadata_omission_reasons(metadata))

        if row_reasons:
            omitted_rows.append(_omitted_row(row_index, row, row_reasons))
            continue

        assert metadata is not None
        if max_candidates is not None and len(candidates) >= max_candidates:
            omitted_rows.append(
                _omitted_row(row_index, row, ["max_candidates_exceeded"])
            )
            continue
        candidates.append(
            _candidate_manifest_entry(
                row_index=row_index,
                row=row,
                metadata=metadata,
                artifact_ref=artifact_ref,
            )
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "comparison_id": comparison_id,
        "source_campaign_dir": str(source_campaign_dir),
        "source_arm": source_arm,
        "generated_at": generated_at or _utc_now_iso(),
        "candidate_filter": candidate_filter,
        "filtered_out_row_count": filtered_out_row_count,
        "candidate_count": len(candidates),
        "causal_candidate_pairing": bool(candidates),
        "replay_arms": list(REPLAY_ARMS),
        "candidates": candidates,
        "omitted_rows": omitted_rows,
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
) -> Path:
    """Build and write a fixed-candidate replay manifest JSON artifact."""

    index_path, _ = resolve_formal_candidate_index(source)
    destination = (
        Path(output_path)
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
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(_manifest_json(manifest), encoding="utf-8")
    return destination


def resolve_formal_candidate_index(source: str | Path) -> tuple[Path, Path]:
    """Resolve a campaign directory or formal candidate index path."""

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
    if not index_path.is_file():
        raise FileNotFoundError(f"formal candidate index not found: {index_path}")
    return index_path, campaign_dir


def _infer_campaign_dir_from_index(index_path: Path) -> Path:
    parts = index_path.parts
    if len(parts) >= 3 and parts[-3:-1] == ("artifacts", "formal_candidates"):
        return index_path.parents[2]
    return index_path.parent


def _read_index_rows(index_path: Path) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    with index_path.open(encoding="utf-8") as fh:
        for line_number, line in enumerate(fh, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid JSON in formal candidate index line {line_number}"
                ) from exc
            if not isinstance(row, Mapping):
                raise ValueError(
                    f"formal candidate index line {line_number} is not a JSON object"
                )
            rows.append(row)
    return rows


def _candidate_filter(
    *,
    candidate_ids: Sequence[str] | None,
    hypothesis_ids: Sequence[str] | None,
) -> dict[str, list[str]]:
    return {
        "candidate_ids": _sorted_clean_strings(candidate_ids),
        "hypothesis_ids": _sorted_clean_strings(hypothesis_ids),
    }


def _row_matches_candidate_filter(
    row: Mapping[str, Any],
    candidate_filter: Mapping[str, Sequence[str]],
) -> bool:
    candidate_ids = set(candidate_filter.get("candidate_ids") or ())
    hypothesis_ids = set(candidate_filter.get("hypothesis_ids") or ())
    if not candidate_ids and not hypothesis_ids:
        return True
    candidate_id = _clean_str(row.get("candidate_id"))
    hypothesis_id = _clean_str(row.get("hypothesis_id"))
    return candidate_id in candidate_ids or hypothesis_id in hypothesis_ids


def _row_omission_reasons(row: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    if _clean_str(row.get("artifact_status")) != "recorded":
        if _clean_str(row.get("artifact_status")) == "omitted":
            reasons.append(
                _clean_str(row.get("artifact_omitted_reason"))
                or "artifact_omitted"
            )
        else:
            reasons.append("artifact_not_recorded")
    if _clean_str(row.get("stage")) != "screening":
        reasons.append("non_screening_stage")
    if not _clean_str(row.get("artifact_ref")):
        reasons.append("missing_artifact_ref")
    if _clean_str(row.get("replay_identity_status")) != "complete":
        reasons.append("replay_identity_not_complete")
    missing_keys = _string_list(row.get("missing_replay_identity_keys"))
    if missing_keys:
        reasons.append("missing_replay_identity_keys")
    return _dedupe(reasons)


def _metadata_omission_reasons(metadata: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    if _clean_str(metadata.get("stage")) != "screening":
        reasons.append("candidate_patch_non_screening_stage")
    replay_identity = metadata.get("replay_identity")
    if not isinstance(replay_identity, Mapping):
        reasons.append("candidate_patch_missing_replay_identity")
        return reasons
    identity_status = _clean_str(
        replay_identity.get("identity_status") or replay_identity.get("status")
    )
    if identity_status != "complete":
        reasons.append("candidate_patch_replay_identity_not_complete")
    if formal_replay_identity_missing_keys(replay_identity):
        reasons.append("candidate_patch_missing_replay_identity_keys")
    return _dedupe(reasons)


def _candidate_manifest_entry(
    *,
    row_index: int,
    row: Mapping[str, Any],
    metadata: Mapping[str, Any],
    artifact_ref: str,
) -> dict[str, Any]:
    replay_identity = metadata.get("replay_identity")
    assert isinstance(replay_identity, Mapping)
    patch = metadata.get("patch") if isinstance(metadata.get("patch"), Mapping) else {}
    base = metadata.get("base") if isinstance(metadata.get("base"), Mapping) else {}
    replay_metadata = (
        metadata.get("replay_metadata")
        if isinstance(metadata.get("replay_metadata"), Mapping)
        else {}
    )
    patch_digest = _clean_str(
        replay_identity.get("patch_digest")
        or replay_identity.get("patch_hash")
        or patch.get("patch_digest")
        or row.get("patch_digest")
    )
    raw_metrics_ref = _clean_str(
        replay_identity.get("raw_metrics_ref")
        or replay_metadata.get("raw_metrics_ref")
        or metadata.get("experiment_ref")
    )
    return {
        "candidate_order_index": row_index,
        "candidate_id": _clean_str(
            metadata.get("candidate_id") or row.get("candidate_id")
        ),
        "branch_id": _clean_str(metadata.get("branch_id") or row.get("branch_id")),
        "lineage_id": _clean_str(metadata.get("lineage_id")),
        "hypothesis_id": _clean_str(
            metadata.get("hypothesis_id") or row.get("hypothesis_id")
        ),
        "stage": _clean_str(metadata.get("stage") or row.get("stage")),
        "artifact_ref": artifact_ref,
        "target_files": _target_files(metadata),
        "selected_surface": _clean_str(
            replay_identity.get("selected_surface")
            or replay_metadata.get("selected_surface")
        ),
        "hypothesis_action": _hypothesis_action(metadata),
        "patch_digest": patch_digest,
        "patch_hash": _clean_str(replay_identity.get("patch_hash") or patch_digest),
        "code_hash": _clean_str(replay_identity.get("code_hash")),
        "base_champion_id": _clean_str(base.get("base_champion_id")),
        "base_champion_hash": _clean_str(base.get("base_champion_hash")),
        "problem_spec_hash": _clean_str(replay_identity.get("problem_spec_hash")),
        "split_manifest_hash": _clean_str(replay_identity.get("split_manifest_hash")),
        "seed_ledger_hash": _clean_str(replay_identity.get("seed_ledger_hash")),
        "protocol_version": _clean_str(replay_identity.get("protocol_version")),
        "raw_metrics_ref": raw_metrics_ref,
        "source_raw_metrics_ref": raw_metrics_ref,
        "decision": _clean_str(metadata.get("decision")),
        "decision_reason_codes": _string_list(metadata.get("decision_reason_codes")),
        "audit_flags": {
            "decision_features_excluded": True,
            "proposal_text_excluded": True,
            "replay_materialized_from_artifact": True,
        },
    }


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
    """Replay fixed candidates under each manifest arm and write comparison JSON.

    This executor is intentionally posthoc: it materializes workspaces under
    ``output_dir`` and invokes screening protocol only.  It does not touch
    campaign state, branch lifecycle, Decision, scheduler, or promotion state.
    """

    manifest_file = Path(manifest_path).expanduser().resolve()
    manifest = _load_manifest(manifest_file)
    source_campaign_dir = Path(_required_str(manifest, "source_campaign_dir")).resolve()
    arms = _manifest_replay_arms(manifest)
    candidates = list(_manifest_candidates(manifest))
    problem_path = Path(problem_yaml_path).expanduser().resolve()
    if protocol_factory is None:
        _require_problem_spec_v1_for_fixed_replay(problem_path)
    if max_candidates is not None:
        if max_candidates < 0:
            raise ValueError("max_candidates must be non-negative")
        candidates = candidates[:max_candidates]

    out_dir = Path(output_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    comparison_path = (
        Path(comparison_output_path).expanduser().resolve()
        if comparison_output_path is not None
        else out_dir / DEFAULT_COMPARISON_FILENAME
    )
    rows: list[dict[str, Any]] = []

    for candidate in candidates:
        for arm in arms:
            rows.append(
                _execute_replay_row(
                    manifest=manifest,
                    manifest_path=manifest_file,
                    candidate=candidate,
                    arm=arm,
                    source_campaign_dir=source_campaign_dir,
                    problem_yaml_path=problem_path,
                    protocol_path=Path(protocol_path).expanduser().resolve()
                    if protocol_path is not None
                    else None,
                    split_path=Path(split_path).expanduser().resolve()
                    if split_path is not None
                    else None,
                    seeds_path=Path(seeds_path).expanduser().resolve()
                    if seeds_path is not None
                    else None,
                    output_dir=out_dir,
                    time_limit_sec=time_limit_sec,
                    protocol_factory=protocol_factory,
                )
            )

    artifact = {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "source_manifest_ref": str(manifest_file),
        "source_manifest_schema_version": _clean_str(manifest.get("schema_version")),
        "source_campaign_dir": str(source_campaign_dir),
        "comparison_id": _clean_str(manifest.get("comparison_id")),
        "generated_at": _utc_now_iso(),
        "replay_arms": arms,
        "candidate_count": len(candidates),
        "row_count": len(rows),
        "decision_features_excluded": True,
        "promotion_state_mutated": False,
        "campaign_state_mutated": False,
        "scheduler_state_mutated": False,
        "comparison_is_decision_input": False,
        "raw_paired_rows_excluded": True,
        "measurement_diagnostics_excluded": True,
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
    """Copy the base champion workspace and apply full-file patch entries."""

    source_dir = Path(source_campaign_dir).expanduser().resolve()
    base = candidate_patch.get("base")
    if not isinstance(base, Mapping):
        raise ValueError("candidate patch missing base metadata")
    base_ref = _clean_str(base.get("base_workspace_ref"))
    if not base_ref:
        raise ValueError("candidate patch missing base.base_workspace_ref")
    base_workspace = _resolve_required_relative_path(
        base_ref,
        root=source_dir,
        label="base.base_workspace_ref",
    )
    if not base_workspace.is_dir():
        raise FileNotFoundError(f"base workspace not found: {base_workspace}")

    candidate_id = _safe_path_token(_clean_str(candidate.get("candidate_id")) or "candidate")
    arm_token = _safe_path_token(arm)
    destination_root = Path(output_dir).expanduser().resolve()
    workspace = destination_root / "materialized" / candidate_id / arm_token
    _assert_descendant(workspace, destination_root)
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(base_workspace, workspace)
    _make_tree_user_writable(workspace)

    patch = candidate_patch.get("patch")
    if not isinstance(patch, Mapping):
        raise ValueError("candidate patch missing patch object")
    files = patch.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("candidate patch missing patch.files")
    for entry in files:
        if not isinstance(entry, Mapping):
            raise ValueError("patch.files entries must be objects")
        _apply_full_file_patch_entry(workspace, entry)
    return workspace


def _target_files(metadata: Mapping[str, Any]) -> list[str]:
    files = _string_list(metadata.get("target_files"))
    if files:
        return files
    patch = metadata.get("patch")
    if not isinstance(patch, Mapping):
        return []
    changes = patch.get("files")
    if not isinstance(changes, list):
        return []
    return [
        _clean_str(item.get("file_path"))
        for item in changes
        if isinstance(item, Mapping) and _clean_str(item.get("file_path"))
    ]


def _hypothesis_action(metadata: Mapping[str, Any]) -> str:
    action = _clean_str(metadata.get("hypothesis_action"))
    if action:
        return action
    hypothesis = metadata.get("hypothesis")
    if isinstance(hypothesis, Mapping):
        action = _clean_str(hypothesis.get("action"))
        if action:
            return action
    patch = metadata.get("patch")
    if isinstance(patch, Mapping):
        files = patch.get("files")
        if isinstance(files, list):
            actions = {
                _clean_str(item.get("action"))
                for item in files
                if isinstance(item, Mapping) and _clean_str(item.get("action"))
            }
            if actions == {"create"}:
                return "create_new"
            if actions == {"delete"}:
                return "remove"
    return "modify"


def _omitted_row(
    row_index: int,
    row: Mapping[str, Any],
    reasons: list[str],
) -> dict[str, Any]:
    return {
        "candidate_order_index": row_index,
        "candidate_id": _clean_str(row.get("candidate_id")),
        "branch_id": _clean_str(row.get("branch_id")),
        "hypothesis_id": _clean_str(row.get("hypothesis_id")),
        "stage": _clean_str(row.get("stage")),
        "artifact_ref": _clean_str(row.get("artifact_ref")),
        "artifact_status": _clean_str(row.get("artifact_status")),
        "replay_identity_status": _clean_str(row.get("replay_identity_status")),
        "missing_replay_identity_keys": _string_list(
            row.get("missing_replay_identity_keys")
        ),
        "reasons": _dedupe(reasons),
    }


def _resolve_artifact_path(
    artifact_ref: str,
    *,
    campaign_dir: Path,
    index_dir: Path,
) -> Path | None:
    ref = artifact_ref.split("#", 1)[0].strip()
    if not ref:
        return None
    path = Path(ref).expanduser()
    if path.is_absolute():
        return path
    campaign_candidate = campaign_dir / path
    if campaign_candidate.exists():
        return campaign_candidate
    index_candidate = index_dir / path
    if index_candidate.exists():
        return index_candidate
    return campaign_candidate


def _execute_replay_row(
    *,
    manifest: Mapping[str, Any],
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
) -> dict[str, Any]:
    row = _base_comparison_row(candidate, arm)
    try:
        artifact_ref = _required_str(candidate, "artifact_ref")
        patch_path = _resolve_artifact_path(
            artifact_ref,
            campaign_dir=source_campaign_dir,
            index_dir=manifest_path.parent,
        )
        if patch_path is None or not patch_path.is_file():
            raise FileNotFoundError(f"candidate.patch.json not found: {artifact_ref}")
        candidate_patch = _load_json_object(patch_path)
        workspace = materialize_candidate_workspace(
            candidate=candidate,
            candidate_patch=candidate_patch,
            source_campaign_dir=source_campaign_dir,
            output_dir=output_dir,
            arm=arm,
        )
        base_workspace_ref = _required_base_workspace_ref(candidate_patch)
        champion_ws = _resolve_required_relative_path(
            base_workspace_ref,
            root=source_campaign_dir,
            label="base.base_workspace_ref",
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
        hypothesis_action = _clean_str(candidate.get("hypothesis_action")) or "modify"
        canary = protocol.run_canary(
            str(workspace),
            str(champion_ws),
            selected_surface=selected_surface,
        )
        result = protocol.run_experiment(
            _screening_stage(),
            str(workspace),
            str(champion_ws),
            hypothesis_action,
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
    except Exception as exc:  # keep row-level errors audit-visible
        row.update(
            {
                "status": "error",
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
            }
        )
    return row


def _base_comparison_row(candidate: Mapping[str, Any], arm: str) -> dict[str, Any]:
    measurement_governance = _measurement_governance_for_arm(arm)
    return {
        "candidate_order_index": candidate.get("candidate_order_index"),
        "candidate_id": _clean_str(candidate.get("candidate_id")),
        "branch_id": _clean_str(candidate.get("branch_id")),
        "hypothesis_id": _clean_str(candidate.get("hypothesis_id")),
        "arm": arm,
        "measurement_governance": measurement_governance,
        "measurement_governance_off": measurement_governance == "off_record_only",
        "patch_digest": _clean_str(candidate.get("patch_digest")),
        "patch_hash": _clean_str(candidate.get("patch_hash")),
        "artifact_ref": _clean_str(candidate.get("artifact_ref")),
        "selected_surface": _clean_str(candidate.get("selected_surface")),
        "hypothesis_action": _clean_str(candidate.get("hypothesis_action")) or "modify",
        "source_raw_metrics_ref": _clean_str(candidate.get("source_raw_metrics_ref")),
        "decision_features_excluded": True,
        "promotion_state_mutated": False,
        "campaign_state_mutated": False,
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
    problem_spec_v1 = load_problem_spec_v1_from_yaml(problem_yaml_path)
    bridge = bridge_problem_spec_v1(problem_spec_v1)
    config_dir = problem_yaml_path.parent
    resolved_protocol_path = protocol_path or config_dir / "protocol.yaml"
    resolved_split_path = split_path or config_dir / "split_manifest.yaml"
    resolved_seeds_path = seeds_path or config_dir / "seed_ledger.yaml"
    protocol_config = ProtocolConfig.from_yaml(
        resolved_protocol_path
    ).with_problem_measurement(bridge.problem_spec, governance_mode=arm)
    split_manifest = SplitManifest.from_yaml(resolved_split_path)
    seed_ledger = SeedLedgerConfig.from_yaml(resolved_seeds_path)
    metrics_dir = (
        output_dir
        / "metrics"
        / _safe_path_token(_clean_str(candidate.get("candidate_id")) or "candidate")
        / _safe_path_token(arm)
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
    if not isinstance(payload, Mapping):
        raise ValueError(
            _fixed_replay_problem_spec_v1_error(problem_yaml_path, "<non-object>")
        )
    spec_version = _clean_str(payload.get("spec_version"))
    if spec_version != "problem-v1":
        raise ValueError(
            _fixed_replay_problem_spec_v1_error(
                problem_yaml_path,
                spec_version or "<missing>",
            )
        )


def _fixed_replay_problem_spec_v1_error(
    problem_yaml_path: Path,
    spec_version: str,
) -> str:
    sibling = problem_yaml_path.with_name("problem-v1.yaml")
    if sibling != problem_yaml_path and sibling.is_file():
        hint = f"suggested path: {sibling}"
    else:
        hint = "provide a ProblemSpecV1 YAML, usually problem-v1.yaml"
    return (
        "fixed replay requires ProblemSpecV1; use problem-v1.yaml for --problem "
        f"(got spec_version={spec_version!r} at {problem_yaml_path}; {hint})"
    )


def _apply_full_file_patch_entry(workspace: Path, entry: Mapping[str, Any]) -> None:
    relative_path = _clean_str(entry.get("file_path") or entry.get("path"))
    if not relative_path:
        raise ValueError("patch file entry missing file_path")
    target = _workspace_child(workspace, relative_path)
    action = _clean_str(entry.get("action")) or "modify"
    if action == "delete":
        if target.exists():
            target.unlink()
        return
    if "code_content" not in entry:
        raise ValueError(f"patch file entry missing code_content: {relative_path}")
    content = str(entry.get("code_content") or "")
    expected_sha = _clean_str(entry.get("code_sha256"))
    if expected_sha:
        actual_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if actual_sha != expected_sha:
            raise ValueError(f"code_sha256 mismatch for patch file: {relative_path}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _workspace_child(workspace: Path, relative_path: str) -> Path:
    rel = Path(relative_path)
    if rel.is_absolute() or any(part in {"", ".", ".."} for part in rel.parts):
        raise ValueError(f"unsafe patch file path: {relative_path}")
    target = (workspace / rel).resolve()
    _assert_descendant(target, workspace.resolve())
    return target


def _resolve_required_relative_path(value: str, *, root: Path, label: str) -> Path:
    rel = Path(value).expanduser()
    if rel.is_absolute() or any(part in {"", ".", ".."} for part in rel.parts):
        raise ValueError(f"{label} must be a safe relative path")
    resolved = (root / rel).resolve()
    _assert_descendant(resolved, root)
    return resolved


def _assert_descendant(path: Path, root: Path) -> None:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"path escapes allowed root: {path}") from exc


def _make_tree_user_writable(root: Path) -> None:
    """Ensure replay materialization can patch copied champion snapshots."""

    for path in [root, *root.rglob("*")]:
        try:
            mode = path.stat().st_mode
            path.chmod(mode | _user_write_bits(path))
        except OSError:
            continue


def _user_write_bits(path: Path) -> int:
    return 0o700 if path.is_dir() else 0o600


def _load_manifest(path: Path) -> Mapping[str, Any]:
    data = _load_json_object(path)
    if _clean_str(data.get("schema_version")) != SCHEMA_VERSION:
        raise ValueError(f"unsupported fixed-candidate replay manifest: {path}")
    return data


def _load_json_object(path: Path) -> Mapping[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, Mapping):
        raise ValueError(f"JSON artifact is not an object: {path}")
    return loaded


def _manifest_candidates(manifest: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    candidates = manifest.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("manifest candidates must be a list")
    return [item for item in candidates if isinstance(item, Mapping)]


def _manifest_replay_arms(manifest: Mapping[str, Any]) -> list[str]:
    arms = manifest.get("replay_arms")
    if not isinstance(arms, list) or not arms:
        raise ValueError("manifest replay_arms must be a non-empty list")
    clean = [_clean_str(arm) for arm in arms]
    unsupported = [arm for arm in clean if arm not in REPLAY_ARMS]
    if unsupported:
        raise ValueError(f"unsupported replay arm(s): {unsupported}")
    return clean


def _required_str(data: Mapping[str, Any], key: str) -> str:
    value = _clean_str(data.get(key))
    if not value:
        raise ValueError(f"missing required field: {key}")
    return value


def _required_base_workspace_ref(candidate_patch: Mapping[str, Any]) -> str:
    base = candidate_patch.get("base")
    if not isinstance(base, Mapping):
        raise ValueError("candidate patch missing base metadata")
    return _required_str(base, "base_workspace_ref")


def _measurement_governance_for_arm(arm: str) -> str:
    if arm not in MEASUREMENT_GOVERNANCE_BY_ARM:
        raise ValueError(f"unsupported replay arm: {arm}")
    return MEASUREMENT_GOVERNANCE_BY_ARM[arm]


def _screening_stage() -> Any:
    from scion.core.models import ExperimentStage

    return ExperimentStage.SCREENING


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


def _sorted_clean_strings(value: Sequence[str] | None) -> list[str]:
    return sorted(set(_string_list(value)))


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


__all__ = [
    "COMPARISON_SCHEMA_VERSION",
    "DEFAULT_MANIFEST_FILENAME",
    "DEFAULT_COMPARISON_FILENAME",
    "REPLAY_ARMS",
    "SCHEMA_VERSION",
    "build_fixed_candidate_replay_manifest",
    "execute_fixed_candidate_replay",
    "materialize_candidate_workspace",
    "resolve_formal_candidate_index",
    "write_fixed_candidate_replay_manifest",
]
