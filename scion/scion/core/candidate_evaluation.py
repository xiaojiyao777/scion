"""Minimal post-verification candidate evaluation state.

This is deliberately a small branch-local marker.  It says only which
verified candidate still needs a Protocol decision; workspace promotion and
parent rollback continue to be owned by ``WorkspaceLifecycleService``.
"""

from __future__ import annotations

from typing import Literal, Mapping

from scion.core.models import Branch


CANDIDATE_EVALUATION_SUMMARY_KEY = "candidate_evaluation"
CandidateEvaluationKind = Literal["explore", "reconcile"]


def mark_candidate_evaluation_pending(
    branch: Branch,
    *,
    hypothesis_id: str,
    kind: CandidateEvaluationKind,
) -> None:
    """Record the one candidate that may advance to Protocol evaluation."""

    if not hypothesis_id:
        raise ValueError("candidate evaluation hypothesis_id is required")
    if kind not in {"explore", "reconcile"}:
        raise ValueError("candidate evaluation kind is invalid")
    summary = dict(branch.branch_evidence_summary or {})
    summary[CANDIDATE_EVALUATION_SUMMARY_KEY] = {
        "status": "pending",
        "hypothesis_id": hypothesis_id,
        "kind": kind,
    }
    branch.branch_evidence_summary = summary


def mark_candidate_evaluation_completed(branch: Branch) -> None:
    """Mark the current candidate's Protocol decision as complete."""

    marker = candidate_evaluation(branch)
    if marker is None:
        return
    if marker["status"] == "completed":
        return
    summary = dict(branch.branch_evidence_summary or {})
    summary[CANDIDATE_EVALUATION_SUMMARY_KEY] = {
        **marker,
        "status": "completed",
    }
    branch.branch_evidence_summary = summary


def candidate_evaluation_pending(branch: Branch) -> bool:
    marker = candidate_evaluation(branch)
    return marker is not None and marker["status"] == "pending"


def candidate_evaluation_kind(branch: Branch) -> CandidateEvaluationKind | None:
    marker = candidate_evaluation(branch)
    return marker["kind"] if marker is not None else None


def candidate_evaluation(branch: Branch) -> dict[str, str] | None:
    """Return a validated plain marker, rejecting ambiguous durable state."""

    raw = (branch.branch_evidence_summary or {}).get(CANDIDATE_EVALUATION_SUMMARY_KEY)
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise RuntimeError(
            f"Branch {branch.branch_id}: candidate evaluation state is invalid"
        )
    status = raw.get("status")
    hypothesis_id = raw.get("hypothesis_id")
    kind = raw.get("kind")
    if (
        status not in {"pending", "completed"}
        or not isinstance(hypothesis_id, str)
        or not hypothesis_id
        or kind not in {"explore", "reconcile"}
    ):
        raise RuntimeError(
            f"Branch {branch.branch_id}: candidate evaluation state is invalid"
        )
    return {
        "status": status,
        "hypothesis_id": hypothesis_id,
        "kind": kind,
    }
