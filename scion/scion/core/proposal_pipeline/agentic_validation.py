"""Validation and sanitization of tainted agentic proposal output."""
from __future__ import annotations

from dataclasses import replace

from scion.core.branch_repair_policy import validate_repair_focused_hypothesis
from scion.core.models import Branch, ChampionState, HypothesisProposal
from scion.proposal.agentic_session import (
    AgenticFailureCategory,
    AgenticProposalOutput,
    AgenticProposalStatus,
    AgenticTerminationReason,
    ensure_agentic_output_audit_metadata,
)

from .classification import _agentic_self_check_failure_detail


class AgenticValidationMixin:
    def _agentic_output_can_continue(
        self,
        output: AgenticProposalOutput,
        hypothesis: HypothesisProposal,
    ) -> bool:
        return (
            output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
            and output.termination_reason
            == AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL
            and output.hypothesis == hypothesis
            and output.patch is None
        )

    def _validate_and_sanitize_agentic_output(
        self,
        *,
        branch: Branch,
        champion: ChampionState,
        output: AgenticProposalOutput,
        forced_surface: str | None = None,
        forced_action: str | None = None,
        forced_target_file: str | None = None,
        active_problem_boundary_surfaces: tuple[str, ...] = (),
    ) -> AgenticProposalOutput:
        failures: list[str] = []
        if output.branch_id != branch.branch_id:
            failures.append(
                f"branch_id expected {branch.branch_id!r} got {output.branch_id!r}"
            )
        if (
            output.champion_version is not None
            and output.champion_version != champion.version
        ):
            failures.append(
                "champion_version expected "
                f"{champion.version!r} got {output.champion_version!r}"
            )
        champion_weight_revision = getattr(champion, "weight_revision", None)
        if (
            output.champion_weight_revision is not None
            and output.champion_weight_revision != champion_weight_revision
        ):
            failures.append(
                "champion_weight_revision expected "
                f"{champion_weight_revision!r} got {output.champion_weight_revision!r}"
            )
        anchor_failures: list[dict[str, str]] = []
        for field, expected in (
            ("problem_id", self.problem_id),
            ("problem_spec_hash", self.problem_spec_hash),
            ("split_manifest_hash", self.split_manifest_hash),
            ("seed_ledger_hash", self.seed_ledger_hash),
        ):
            _validate_problem_anchor(
                field=field,
                expected=expected,
                actual=getattr(output, field, None),
                failures=failures,
                anchor_failures=anchor_failures,
            )
        if self.campaign_id and output.campaign_id != self.campaign_id:
            failures.append(
                f"campaign_id expected {self.campaign_id!r} got {output.campaign_id!r}"
            )
        if output.hypothesis is not None:
            forced_violation = self._forced_hypothesis_violation(
                output.hypothesis,
                forced_surface=forced_surface,
                forced_action=forced_action,
                forced_target_file=forced_target_file,
            )
            if forced_violation is not None:
                failures.append(forced_violation)
            boundary_violation = self._active_problem_boundary_violation(
                output.hypothesis,
                active_problem_boundary_surfaces=active_problem_boundary_surfaces,
                forced_surface=forced_surface,
            )
            if boundary_violation is not None:
                failures.append(boundary_violation)
            repair_check = validate_repair_focused_hypothesis(
                branch,
                output.hypothesis,
                step_history=self.step_history,
            )
            if not repair_check.allowed:
                failures.append(repair_check.detail)

        if output.status != AgenticProposalStatus.FAILED:
            self_check_failure = _agentic_self_check_failure_detail(output)
            if self_check_failure is not None:
                failures.append(self_check_failure)

        patch = output.patch
        failure_detail = output.failure_detail
        if output.status != AgenticProposalStatus.COMPLETED and patch is not None:
            patch = None
            if not failure_detail:
                failure_detail = "non-completed output included unchecked patch"

        if failures:
            structured_rejection = _agentic_anchor_structured_rejection(
                anchor_failures
            )
            return replace(
                ensure_agentic_output_audit_metadata(output),
                status=AgenticProposalStatus.FAILED,
                hypothesis=None,
                patch=None,
                termination_reason=AgenticTerminationReason.ANCHOR_VALIDATION_FAILED,
                failure_detail="; ".join(failures),
                failure_category=AgenticFailureCategory.SCHEMA_OUTPUT_FAILURE,
                structured_rejection=(
                    structured_rejection or output.structured_rejection
                ),
            )
        if patch is not output.patch or failure_detail != output.failure_detail:
            return ensure_agentic_output_audit_metadata(
                replace(output, patch=patch, failure_detail=failure_detail)
            )
        return ensure_agentic_output_audit_metadata(output)

    def _sanitize_pre_contract_agentic_output(
        self,
        output: AgenticProposalOutput,
    ) -> AgenticProposalOutput:
        if (
            output.status != AgenticProposalStatus.COMPLETED
            or output.patch is None
        ):
            return output
        detail = (
            output.failure_detail
            or "completed patch ignored before ContractGate-approved hypothesis"
        )
        return replace(
            output,
            status=AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY,
            patch=None,
            termination_reason=AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL,
            failure_detail=detail,
        )


def _validate_problem_anchor(
    *,
    field: str,
    expected: str | None,
    actual: str | None,
    failures: list[str],
    anchor_failures: list[dict[str, str]],
) -> None:
    if expected is None:
        return
    expected_text = str(expected)
    actual_text = str(actual or "").strip()
    if not actual_text:
        failures.append(f"{field} missing expected {expected_text!r}")
        anchor_failures.append(
            {
                "field": field,
                "reason_code": "agentic_problem_anchor_missing",
                "expected": expected_text,
            }
        )
        return
    if actual_text != expected_text:
        failures.append(f"{field} expected {expected_text!r} got {actual_text!r}")
        anchor_failures.append(
            {
                "field": field,
                "reason_code": "agentic_problem_anchor_mismatch",
                "expected": expected_text,
                "actual": actual_text,
            }
        )


def _agentic_anchor_structured_rejection(
    anchor_failures: list[dict[str, str]],
) -> dict[str, object] | None:
    if not anchor_failures:
        return None
    return {
        "schema_version": "agentic-anchor-validation.v1",
        "failure_code": "agentic_problem_anchor_validation_failed",
        "reason_code": "agentic_problem_anchor_validation_failed",
        "anchor_failures": tuple(anchor_failures),
        "counts_as_screened_round": False,
    }
