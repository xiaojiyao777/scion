"""Problem-neutral postrun acceptance check ports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class PostrunAcceptanceCheck:
    """Legacy-compatible postrun acceptance check payload."""

    name: str
    status: str
    detail: Any = ""
    required: bool = True

    def to_payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "required": bool(self.required),
            "detail": self.detail,
        }


@dataclass(frozen=True)
class PostrunAcceptanceCheckBundle:
    """Ordered collection of legacy-compatible acceptance checks."""

    checks: tuple[PostrunAcceptanceCheck, ...]

    def to_payloads(self) -> dict[str, dict[str, Any]]:
        return {check.name: check.to_payload() for check in self.checks}


class PostrunLifecycleAcceptancePort:
    """Build generic lifecycle and wrapper-marker checks."""

    def summarize(
        self,
        inventory: Mapping[str, Any],
        analysis_brief: Mapping[str, Any],
    ) -> PostrunAcceptanceCheckBundle:
        lifecycle = _mapping_or_empty(inventory.get("lifecycle"))
        validity = _mapping_or_empty(inventory.get("validity"))
        phase4 = _mapping_or_empty(inventory.get("phase4_evidence_coverage"))
        launcher = _mapping_or_empty(inventory.get("launcher"))
        run_log_markers = _mapping_or_empty(launcher.get("run_log_markers"))
        wrapper_status, wrapper_detail = _launcher_wrapper_status_ok(inventory)
        marker_status, marker_detail = _launcher_wrapper_marker_status_ok(
            inventory
        )
        return PostrunAcceptanceCheckBundle(
            checks=(
                PostrunAcceptanceCheck(
                    name="current_run_evidence",
                    status=(
                        "ok"
                        if lifecycle.get("current_run_evidence") is True
                        and phase4.get("current_run_evidence") is True
                        else "failed"
                    ),
                    detail={
                        "lifecycle": lifecycle,
                        "phase4": {
                            "current_run_evidence": phase4.get(
                                "current_run_evidence"
                            ),
                            "evidence_scope": phase4.get("evidence_scope"),
                        },
                    },
                ),
                PostrunAcceptanceCheck(
                    name="analysis_brief_current_run_evidence",
                    status=(
                        "ok"
                        if _brief_current_run_evidence(analysis_brief)
                        else "failed"
                    ),
                    detail={
                        "lifecycle": _mapping_or_empty(
                            analysis_brief.get("lifecycle")
                        ),
                        "phase4": _mapping_or_empty(
                            analysis_brief.get("phase4_evidence_coverage")
                        ),
                    },
                ),
                PostrunAcceptanceCheck(
                    name="launcher_wrapper_status_ok",
                    status=wrapper_status,
                    detail=wrapper_detail,
                ),
                PostrunAcceptanceCheck(
                    name="launcher_wrapper_marker_status_ok",
                    status=marker_status,
                    detail=marker_detail,
                ),
                PostrunAcceptanceCheck(
                    name="not_invalid_infra_only",
                    status=(
                        "ok"
                        if validity.get("invalid_infra_only") is not True
                        and lifecycle.get("invalid_infra_only") is not True
                        else "failed"
                    ),
                    detail={"lifecycle": lifecycle, "validity": validity},
                ),
                PostrunAcceptanceCheck(
                    name="not_prepared_only",
                    status=(
                        "ok"
                        if lifecycle.get("prepared_only") is not True
                        else "failed"
                    ),
                    detail=lifecycle,
                ),
                PostrunAcceptanceCheck(
                    name="not_pre_campaign_preflight_failed",
                    status=(
                        "ok"
                        if lifecycle.get(
                            "pre_campaign_completion_preflight_failed"
                        )
                        is not True
                        else "failed"
                    ),
                    detail=lifecycle,
                ),
                PostrunAcceptanceCheck(
                    name="postrun_report_status_marker",
                    status=(
                        "ok"
                        if _int_or_zero(
                            run_log_markers.get("POSTRUN_REPORTS_EXIT_STATUS")
                        )
                        > 0
                        else "missing"
                    ),
                    detail=run_log_markers,
                    required=False,
                ),
            )
        )


def _brief_current_run_evidence(brief: Mapping[str, Any]) -> bool:
    lifecycle = _mapping_or_empty(brief.get("lifecycle"))
    phase4 = _mapping_or_empty(brief.get("phase4_evidence_coverage"))
    return (
        lifecycle.get("current_run_evidence") is True
        and phase4.get("current_run_evidence") is True
    )


def _launcher_wrapper_status_ok(
    inventory: Mapping[str, Any],
) -> tuple[str, dict[str, Any]]:
    launcher = _mapping_or_empty(inventory.get("launcher"))
    status_fields = _mapping_or_empty(launcher.get("status_fields"))
    failures: list[str] = []

    wrapper_exit = _int_or_none(status_fields.get("wrapper_exit_status"))
    if wrapper_exit is None:
        failures.append("wrapper_exit_status_missing")
    elif wrapper_exit != 0:
        failures.append("wrapper_exit_status_nonzero")

    campaign_exit = _int_or_none(status_fields.get("campaign_wrapper_exit_status"))
    if campaign_exit not in (None, 0):
        failures.append("campaign_wrapper_exit_status_nonzero")

    if status_fields.get("postrun_acceptance_failed") is True:
        failures.append("postrun_acceptance_failed")
    if str(status_fields.get("postrun_acceptance_status") or "").lower() == "failed":
        failures.append("postrun_acceptance_status_failed")

    for key in ("postrun_readiness_exit_status", "postrun_reports_exit_status"):
        value = _int_or_none(status_fields.get(key))
        if value not in (None, 0):
            failures.append(f"{key}_nonzero")

    return (
        "ok" if not failures else "failed",
        {
            "failures": failures,
            "status_fields": status_fields,
        },
    )


def _launcher_wrapper_marker_status_ok(
    inventory: Mapping[str, Any],
) -> tuple[str, dict[str, Any]]:
    launcher = _mapping_or_empty(inventory.get("launcher"))
    run_log_markers = _mapping_or_empty(launcher.get("run_log_markers"))
    exit_markers = _mapping_or_empty(launcher.get("exit_markers"))
    failures: list[str] = []

    if _int_or_zero(run_log_markers.get("POSTRUN_STATUS_WRITE_EXIT_STATUS")) > 0:
        failures.append("postrun_status_write_exit_status_marker_present")
    if _int_or_zero(exit_markers.get("POSTRUN_ACCEPTANCE_FAILED")) > 0:
        failures.append("postrun_acceptance_failed_marker_present")
    if _int_or_zero(exit_markers.get("POSTRUN_REPORTS_EFFECTIVE_EXIT_STATUS")) > 0:
        failures.append("postrun_reports_effective_exit_status_marker_present")
    if _int_or_zero(exit_markers.get("POSTRUN_READINESS_EFFECTIVE_EXIT_STATUS")) > 0:
        failures.append("postrun_readiness_effective_exit_status_marker_present")
    if _int_or_zero(exit_markers.get("WRAPPER_EXIT_STATUS_EFFECTIVE")) > 0:
        failures.append("wrapper_exit_status_effective_marker_present")

    return (
        "ok" if not failures else "failed",
        {
            "failures": failures,
            "run_log_markers": run_log_markers,
            "exit_markers": exit_markers,
        },
    )


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _int_or_zero(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _int_or_none(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


__all__ = [
    "PostrunAcceptanceCheck",
    "PostrunAcceptanceCheckBundle",
    "PostrunLifecycleAcceptancePort",
]
