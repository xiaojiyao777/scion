"""Compact promotion dossier artifacts for replay and audit."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from scion.core.models import ExperimentStage, StepRecord
from scion.core.promotion_service import PromotionPlan
from scion.core.public_refs import public_artifact_ref


PROMOTION_DOSSIER_SCHEMA_VERSION = "scion.promotion_dossier.v1"


def promotion_dossier_path(campaign_dir: str | Path, champion_version: int) -> Path:
    return (
        Path(campaign_dir)
        / "artifacts"
        / "promotions"
        / f"champion_v{champion_version}_promotion_dossier.json"
    )


def promotion_dossier_ref(
    campaign_dir: str | Path,
    champion_version: int,
) -> str | None:
    return public_artifact_ref(
        promotion_dossier_path(campaign_dir, champion_version),
        base_dir=campaign_dir,
    )


def write_promotion_dossier(
    *,
    campaign_dir: str | Path,
    campaign_id: str,
    plan: PromotionPlan,
    step_history: Sequence[StepRecord],
) -> str | None:
    """Write the compact promotion dossier and return its public artifact ref."""
    path = promotion_dossier_path(campaign_dir, plan.new_champion_version)
    ref = public_artifact_ref(path, base_dir=campaign_dir)
    dossier = build_promotion_dossier(
        campaign_dir=campaign_dir,
        campaign_id=campaign_id,
        plan=plan,
        step_history=step_history,
        dossier_ref=ref,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_jsonable(dossier), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return ref


def build_promotion_dossier(
    *,
    campaign_dir: str | Path,
    campaign_id: str,
    plan: PromotionPlan,
    step_history: Sequence[StepRecord],
    dossier_ref: str | None,
) -> dict[str, Any]:
    metadata = dict(plan.metadata or {})
    branch_id = plan.branch_id
    stage_chain = _stage_chain_refs(
        campaign_dir=campaign_dir,
        branch_id=branch_id,
        step_history=step_history,
        current_protocol_result=metadata.get("protocol_result"),
    )
    current_protocol = metadata.get("protocol_result")
    metric_refs = _metric_artifact_refs(
        campaign_dir=campaign_dir,
        stage_chain=stage_chain,
        protocol_result=current_protocol,
    )
    patch_payload = metadata.get("patch")
    patch_hash = _patch_hash(patch_payload)
    code_hash = _first_text(
        metadata.get("candidate_code_hash"),
        getattr(plan.champion, "code_snapshot_hash", None),
    )
    formal_candidate_refs = _formal_candidate_refs(metadata, stage_chain)
    return {
        "schema_version": PROMOTION_DOSSIER_SCHEMA_VERSION,
        "campaign_id": campaign_id,
        "promotion_dossier_ref": dossier_ref,
        "champion_version": plan.new_champion_version,
        "promotion_experiment_id": getattr(
            plan.champion,
            "promotion_experiment_id",
            None,
        ),
        "branch_id": branch_id,
        "hypothesis_id": metadata.get("hypothesis_id"),
        "base_champion_version": metadata.get("base_champion_version"),
        "stage_chain_refs": stage_chain,
        "metric_artifact_refs": metric_refs,
        "code_snapshot_hash": getattr(plan.champion, "code_snapshot_hash", None),
        "patch_hash": patch_hash,
        "code_hash": code_hash,
        "champion_snapshot": {
            "path": getattr(plan.champion, "code_snapshot_path", None),
            "ref": public_artifact_ref(
                getattr(plan.champion, "code_snapshot_path", None),
                base_dir=campaign_dir,
            ),
            "hash": getattr(plan.champion, "code_snapshot_hash", None),
        },
        "decision_reason_codes": list(metadata.get("decision_reason_codes") or ()),
        "runtime_evidence_summary": _runtime_evidence_summary(
            stage_chain,
            current_protocol,
        ),
        "replay_refs": {
            "formal_candidate_refs": formal_candidate_refs,
            "replay_identity_refs": _replay_identity_refs(formal_candidate_refs),
        },
        "artifact_refs": {
            "promotion_dossier_ref": dossier_ref,
            "champion_snapshot_ref": public_artifact_ref(
                getattr(plan.champion, "code_snapshot_path", None),
                base_dir=campaign_dir,
            ),
            "registry_hash": getattr(plan, "registry_hash", None),
        },
    }


def _stage_chain_refs(
    *,
    campaign_dir: str | Path,
    branch_id: str,
    step_history: Sequence[StepRecord],
    current_protocol_result: Any,
) -> dict[str, Any]:
    by_stage: dict[str, dict[str, Any]] = {}
    for step in step_history:
        if step.branch_id != branch_id or step.protocol_result is None:
            continue
        stage = _stage_value(step.protocol_result)
        if stage:
            by_stage[stage] = _protocol_ref(
                campaign_dir=campaign_dir,
                protocol_result=step.protocol_result,
                step=step,
            )
    if current_protocol_result is not None:
        stage = _stage_value(current_protocol_result)
        if stage:
            by_stage[stage] = _protocol_ref(
                campaign_dir=campaign_dir,
                protocol_result=current_protocol_result,
                step=None,
            )
    return {
        stage.value: by_stage.get(stage.value)
        for stage in (
            ExperimentStage.SCREENING,
            ExperimentStage.VALIDATION,
            ExperimentStage.FROZEN,
        )
    }


def _protocol_ref(
    *,
    campaign_dir: str | Path,
    protocol_result: Any,
    step: StepRecord | None,
) -> dict[str, Any]:
    stats = getattr(protocol_result, "stats", None)
    return {
        "stage": _stage_value(protocol_result),
        "raw_metrics_ref": public_artifact_ref(
            getattr(protocol_result, "raw_metrics_ref", None),
            base_dir=campaign_dir,
        ),
        "gate_outcome": getattr(protocol_result, "gate_outcome", None),
        "reason_codes": list(getattr(protocol_result, "reason_codes", ()) or ()),
        "runtime_evidence_status": str(
            getattr(protocol_result, "runtime_evidence_status", "") or ""
        ),
        "runtime_confidence": str(
            getattr(protocol_result, "runtime_confidence", "") or ""
        ),
        "stats": _stats_ref(stats),
        "step": (
            {
                "round_num": step.round_num,
                "decision": (
                    getattr(step.decision, "value", step.decision)
                    if step.decision is not None
                    else None
                ),
                "hypothesis_id": step.hypothesis_id,
            }
            if step is not None
            else None
        ),
    }


def _metric_artifact_refs(
    *,
    campaign_dir: str | Path,
    stage_chain: Mapping[str, Any],
    protocol_result: Any,
) -> dict[str, Any]:
    refs: dict[str, Any] = {}
    for stage, item in stage_chain.items():
        if isinstance(item, Mapping) and item.get("raw_metrics_ref"):
            refs[stage] = item["raw_metrics_ref"]
    if protocol_result is not None:
        stage = _stage_value(protocol_result)
        raw_ref = public_artifact_ref(
            getattr(protocol_result, "raw_metrics_ref", None),
            base_dir=campaign_dir,
        )
        if stage and raw_ref:
            refs[stage] = raw_ref
    return refs


def _runtime_evidence_summary(
    stage_chain: Mapping[str, Any],
    protocol_result: Any,
) -> dict[str, Any]:
    by_stage: dict[str, Any] = {}
    statuses: list[str] = []
    confidences: list[str] = []
    for stage, item in stage_chain.items():
        if not isinstance(item, Mapping):
            continue
        status = str(item.get("runtime_evidence_status") or "")
        confidence = str(item.get("runtime_confidence") or "")
        if status:
            statuses.append(status)
        if confidence:
            confidences.append(confidence)
        by_stage[stage] = {
            "status": status,
            "confidence": confidence,
        }
    current_status = str(
        getattr(protocol_result, "runtime_evidence_status", "") or ""
    )
    current_confidence = str(getattr(protocol_result, "runtime_confidence", "") or "")
    return {
        "status": current_status or (statuses[-1] if statuses else "unknown"),
        "confidence": (
            current_confidence or (confidences[-1] if confidences else "unknown")
        ),
        "by_stage": by_stage,
    }


def _formal_candidate_refs(
    metadata: Mapping[str, Any],
    stage_chain: Mapping[str, Any],
) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    summary = metadata.get("branch_evidence_summary")
    if isinstance(summary, Mapping):
        _append_formal_ref(refs, summary)
    for item in stage_chain.values():
        if isinstance(item, Mapping):
            formal = item.get("formal_candidate")
            if isinstance(formal, Mapping):
                _append_formal_ref(refs, formal)
    return refs


def _append_formal_ref(refs: list[dict[str, Any]], source: Mapping[str, Any]) -> None:
    artifact_ref = str(source.get("formal_candidate_patch_artifact_ref") or "")
    replay_ref = str(source.get("formal_replay_identity_ref") or "")
    if not artifact_ref and not replay_ref:
        report = source.get("formal_candidate_artifact_report")
        if isinstance(report, Mapping):
            artifact_ref = str(report.get("artifact_ref") or "")
    if artifact_ref or replay_ref:
        item = {
            "artifact_ref": artifact_ref or None,
            "replay_identity_ref": replay_ref or None,
        }
        if item not in refs:
            refs.append(item)


def _replay_identity_refs(refs: Sequence[Mapping[str, Any]]) -> list[str]:
    return [
        str(ref.get("replay_identity_ref"))
        for ref in refs
        if str(ref.get("replay_identity_ref") or "")
    ]


def _stats_ref(stats: Any) -> dict[str, Any]:
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


def _stage_value(protocol_result: Any) -> str:
    stage = getattr(protocol_result, "stage", None)
    return str(getattr(stage, "value", stage) or "")


def _patch_hash(patch: Any) -> str | None:
    if patch is None:
        return None
    try:
        payload = _jsonable(patch)
        text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    except Exception:
        text = str(patch)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _first_text(*values: Any) -> str | None:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return None


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, set):
        return sorted(_jsonable(item) for item in value)
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "value"):
        return value.value
    return value
