"""Failure attribution helpers for campaign summaries."""
from __future__ import annotations

from typing import Any, Mapping

from scion.core.models import StepRecord
from scion.evidence.final_evidence_refs import (
    FINAL_EVIDENCE_REASON_NORMAL_COMPLETION,
    FINAL_EVIDENCE_REASON_PENDING_EXTERNAL,
    FINAL_EVIDENCE_STATUS_PENDING_EXTERNAL,
    build_final_evidence_closure_refs,
)

from .common import (
    _DEFAULT_NON_FORMAL_FINAL_EVIDENCE_REASON,
    _DEFAULT_PENDING_FINAL_EVIDENCE_REASON,
    _NON_FORMAL_FINAL_EVIDENCE_STOP_REASONS,
    _drop_empty_summary_items,
)


def _contract_not_run_reason(step: StepRecord) -> str | None:
    if step.patch is not None:
        return None
    if step.failure_stage == "agent_quality_blocked":
        return "proposal_only_agent_quality_blocked"
    if step.failure_stage == "proposal":
        return "proposal_generation_failed"
    if step.failure_stage == "code_generation":
        return "patch_not_generated"
    return None


def _primary_failure_attribution(step: StepRecord) -> dict[str, Any] | None:
    ref = step.proposal_session_ref
    if isinstance(ref, Mapping):
        session_observation = _proposal_session_failure_observation(ref)
        if (
            session_observation
            and (
                str(session_observation.get("stage") or "")
                == "agent_quality_blocked"
                or str(session_observation.get("category") or "")
                == "llm_transient_api_error"
            )
        ):
            return _drop_empty_summary_items(
                {
                    key: value
                    for key, value in session_observation.items()
                    if key != "source"
                }
            )
    if not step.failure_stage and not step.failure_detail:
        return None
    stage = step.failure_stage or "unknown"
    reason = step.failure_detail or stage
    return _drop_empty_summary_items(
        {
            "stage": stage,
            "reason": reason,
            "category": _failure_category_for_stage(stage, reason),
        }
    )


def _secondary_failure_observations(
    step: StepRecord,
    primary: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    ref = step.proposal_session_ref
    if isinstance(ref, Mapping):
        session_observation = _proposal_session_failure_observation(ref)
        if session_observation and not _same_failure_observation(
            session_observation,
            primary,
        ):
            observations.append(session_observation)
    return observations


def _proposal_session_failure_observation(
    ref: Mapping[str, Any],
) -> dict[str, Any] | None:
    primary = ref.get("primary_failure")
    if isinstance(primary, Mapping):
        observation = dict(primary)
        observation.setdefault("source", "proposal_session")
        return _drop_empty_summary_items(observation)

    failure_code = str(ref.get("failure_code") or "").strip()
    failure_category = str(ref.get("failure_category") or "").strip()
    block_reason = str(ref.get("agent_block_reason") or "").strip()
    if not (failure_code or failure_category or block_reason):
        return None
    return _drop_empty_summary_items(
        {
            "source": "proposal_session",
            "stage": block_reason or str(ref.get("termination_reason") or ""),
            "reason": failure_code or failure_category,
            "category": failure_category,
            "code": failure_code,
        }
    )


def _same_failure_observation(
    observation: Mapping[str, Any],
    primary: Mapping[str, Any] | None,
) -> bool:
    if not primary:
        return False
    primary_stage = str(primary.get("stage") or "")
    primary_reason = str(primary.get("reason") or "")
    primary_category = str(primary.get("category") or "")
    observation_stage = str(observation.get("stage") or "")
    observation_reason = str(observation.get("reason") or "")
    observation_category = str(observation.get("category") or "")
    return bool(
        primary_stage
        and primary_stage == observation_stage
        and (
            (primary_reason and primary_reason == observation_reason)
            or (primary_category and primary_category == observation_category)
        )
    )


def _failure_category_for_stage(stage: str, reason: str) -> str:
    if stage in {"hypothesis_contract", "patch_contract"}:
        return "contract"
    if stage == "agent_quality_blocked":
        return "agent_grounding_failure"
    if stage in {"proposal", "code_generation"}:
        return "proposal"
    if stage == "verification":
        return "verification"
    if stage == "workspace":
        return "workspace"
    if "contract" in reason:
        return "contract"
    return stage or "unknown"



def _default_final_evidence_closure_refs(
    stopped_reason: str | None,
) -> dict[str, Any]:
    if stopped_reason in _NON_FORMAL_FINAL_EVIDENCE_STOP_REASONS:
        return build_final_evidence_closure_refs(
            reason=_DEFAULT_NON_FORMAL_FINAL_EVIDENCE_REASON,
            reason_code=FINAL_EVIDENCE_REASON_NORMAL_COMPLETION,
            required_for_formal_readiness=False,
        )
    return build_final_evidence_closure_refs(
        reason=_DEFAULT_PENDING_FINAL_EVIDENCE_REASON,
        reason_code=FINAL_EVIDENCE_REASON_PENDING_EXTERNAL,
        status=FINAL_EVIDENCE_STATUS_PENDING_EXTERNAL,
        required_for_formal_readiness=True,
    )
