"""Generic postrun readiness orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from scion.postrun.ports import (
    ExposureSummary,
    PostrunInventory,
    PostrunInventoryPort,
    PostrunReadinessSummary,
    ProblemReviewRegistry,
    RunEvidenceLifecycle,
)


@dataclass(frozen=True)
class MappingPostrunInventoryPort:
    """Inventory port for tests and adapters that already hold a mapping."""

    inventory: PostrunInventory

    def load(self, run_root: Path) -> PostrunInventory:
        return self.inventory


class DefaultRunEvidenceLifecyclePort:
    """Reduce common inventory fields into generic lifecycle readiness."""

    def evaluate(self, inventory: PostrunInventory) -> RunEvidenceLifecycle:
        lifecycle = _mapping(inventory.get("lifecycle"))
        validity = _mapping(inventory.get("validity"))
        launcher = _mapping(inventory.get("launcher"))
        phase4 = _mapping(inventory.get("phase4_evidence_coverage"))
        proposal_runtime = _mapping(inventory.get("proposal_runtime"))
        execution_outcomes = _mapping(inventory.get("execution_outcomes"))
        outcome_counts = _mapping(
            execution_outcomes.get("execution_outcome_counts")
        )
        eligibility = _mapping(
            execution_outcomes.get("research_conclusion_eligibility")
        )
        status_fields = _mapping(launcher.get("status_fields"))

        wrapper_exit_status = _optional_int(
            status_fields.get("wrapper_exit_status")
            if "wrapper_exit_status" in status_fields
            else lifecycle.get("wrapper_exit_status")
        )
        postrun_acceptance_status = str(
            status_fields.get("postrun_acceptance_status")
            or lifecycle.get("postrun_acceptance_status")
            or ""
        )
        current_run_evidence = _bool_from_any(
            phase4.get("current_run_evidence"),
            default=_bool_from_any(lifecycle.get("current_run_evidence")),
        )
        explicit_outcome_count = _int_from_any(
            execution_outcomes.get("evaluated_count")
        ) + _int_from_any(execution_outcomes.get("non_evaluated_count"))
        if explicit_outcome_count > 0:
            invalid_infra_only = (
                _int_from_any(outcome_counts.get("blocked_infra"))
                == explicit_outcome_count
            )
        else:
            invalid_infra_only = _bool_from_any(
                phase4.get("invalid_infra_only"),
                default=_bool_from_any(validity.get("invalid_infra_only")),
            )

        failed: list[str] = []
        if wrapper_exit_status not in (None, 0):
            failed.append("wrapper_exit_status_nonzero")
        if postrun_acceptance_status.lower() == "failed":
            failed.append("postrun_acceptance_failed")
        if invalid_infra_only:
            failed.append("invalid_infra_only")
        if not current_run_evidence:
            failed.append("missing_current_run_evidence")
        if eligibility.get("eligible") is False:
            failed.append("no_evaluated_execution_outcome")
        runtime_status = str(proposal_runtime.get("status") or "unknown")
        if runtime_status == "unsupported_historical":
            failed.append("proposal_runtime_mode_unsupported_historical")
        elif (
            runtime_status != "resolved"
            or proposal_runtime.get("resolved_mode") != "direct_v3"
        ):
            failed.append("proposal_runtime_mode_unresolved")

        return RunEvidenceLifecycle(
            status="ready" if not failed else "not_ready",
            current_run_evidence=current_run_evidence,
            run_validity_status=str(
                validity.get("run_validity_status")
                or lifecycle.get("run_validity_status")
                or ""
            ),
            run_completeness_status=str(
                validity.get("run_completeness_status")
                or lifecycle.get("run_completeness_status")
                or ""
            ),
            wrapper_exit_status=wrapper_exit_status,
            postrun_acceptance_status=postrun_acceptance_status,
            invalid_infra_only=invalid_infra_only,
            execution_outcomes=dict(execution_outcomes),
            research_conclusion_eligibility=dict(eligibility),
            failed_required_checks=tuple(failed),
            detail={
                "source": "postrun_inventory_common_fields",
                "proposal_runtime": dict(proposal_runtime),
            },
        )


class DefaultExposurePolicyPort:
    """Summarize generic exposure policy from inventory fields."""

    def summarize(self, inventory: PostrunInventory) -> ExposureSummary:
        prompt_context = _mapping(inventory.get("prompt_context_visibility_summary"))
        analysis = _mapping(inventory.get("analysis_brief"))

        raw_prompt_excluded = _bool_from_any(
            prompt_context.get("raw_prompt_excluded"),
            default=_bool_from_any(analysis.get("raw_prompt_excluded"), default=True),
        )
        raw_response_excluded = _bool_from_any(
            prompt_context.get("raw_response_excluded"),
            default=_bool_from_any(analysis.get("raw_response_excluded"), default=True),
        )
        patch_body_excluded = _bool_from_any(
            prompt_context.get("patch_body_excluded"),
            default=_bool_from_any(analysis.get("patch_body_excluded"), default=True),
        )
        source_body_excluded = _bool_from_any(
            prompt_context.get("source_body_excluded"),
            default=True,
        )

        failed: list[str] = []
        if not raw_prompt_excluded:
            failed.append("raw_prompt_not_excluded")
        if not raw_response_excluded:
            failed.append("raw_response_not_excluded")
        if not patch_body_excluded:
            failed.append("patch_body_not_excluded")
        if not source_body_excluded:
            failed.append("source_body_not_excluded")

        return ExposureSummary(
            status="ready" if not failed else "not_ready",
            raw_prompt_excluded=raw_prompt_excluded,
            raw_response_excluded=raw_response_excluded,
            patch_body_excluded=patch_body_excluded,
            source_body_excluded=source_body_excluded,
            failed_required_checks=tuple(failed),
            detail={
                "source": "postrun_inventory_exposure_fields",
            },
        )


class PostrunReadinessOrchestrator:
    """Compose generic readiness ports with optional problem-owned review."""

    def __init__(
        self,
        inventory_port: PostrunInventoryPort,
        *,
        lifecycle_port: DefaultRunEvidenceLifecyclePort | None = None,
        exposure_port: DefaultExposurePolicyPort | None = None,
        problem_reviews: ProblemReviewRegistry | None = None,
    ) -> None:
        self._inventory_port = inventory_port
        self._lifecycle_port = lifecycle_port or DefaultRunEvidenceLifecyclePort()
        self._exposure_port = exposure_port or DefaultExposurePolicyPort()
        self._problem_reviews = problem_reviews or ProblemReviewRegistry()

    def build(self, run_root: Path | str) -> PostrunReadinessSummary:
        root = Path(run_root)
        inventory = self._inventory_port.load(root)
        lifecycle = self._lifecycle_port.evaluate(inventory)
        exposure = self._exposure_port.summarize(inventory)
        problem_review = None
        problem_family = _problem_family(inventory)
        if problem_family:
            port = self._problem_reviews.get(problem_family)
            if port is not None:
                problem_review = port.review(inventory)

        failed_required = list(lifecycle.failed_required_checks)
        failed_required.extend(exposure.failed_required_checks)
        failed_optional = list(lifecycle.failed_optional_checks)
        failed_optional.extend(exposure.failed_optional_checks)
        if problem_review is not None:
            failed_required.extend(problem_review.failed_required_checks)
            failed_optional.extend(problem_review.failed_optional_checks)

        current_ready = lifecycle.ready and exposure.ready
        if problem_review is not None:
            current_ready = current_ready and problem_review.ready

        return PostrunReadinessSummary(
            run_root=str(root),
            inventory_status="loaded",
            lifecycle=lifecycle,
            exposure=exposure,
            problem_review=problem_review,
            failed_required_checks=tuple(failed_required),
            failed_optional_checks=tuple(failed_optional),
            current_run_analysis_ready=current_ready,
            delegation_ready=current_ready,
        )


def _problem_family(inventory: PostrunInventory) -> str:
    for key in ("problem_family", "family"):
        value = inventory.get(key)
        if value:
            return str(value).strip().lower()
    prepared = _mapping(inventory.get("prepared_run_contract"))
    value = prepared.get("problem_family")
    if value:
        return str(value).strip().lower()
    launcher = _mapping(inventory.get("launcher"))
    contract = _mapping(launcher.get("prepared_run_contract"))
    value = contract.get("problem_family")
    if value:
        return str(value).strip().lower()
    manifest = _mapping(inventory.get("prepared_manifest"))
    return str(manifest.get("problem_family") or "").strip().lower()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _optional_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _int_from_any(value: Any) -> int:
    parsed = _optional_int(value)
    return max(0, parsed) if parsed is not None else 0


def _bool_from_any(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "ok"}:
            return True
        if normalized in {"0", "false", "no", "failed"}:
            return False
    return bool(value)
