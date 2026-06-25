from __future__ import annotations

from scion.postrun import PostrunLifecycleAcceptancePort


def test_lifecycle_acceptance_checks_emit_legacy_ready_payloads() -> None:
    checks = PostrunLifecycleAcceptancePort().summarize(
        _ready_inventory(),
        _ready_analysis_brief(),
    ).to_payloads()

    assert checks["current_run_evidence"] == {
        "status": "ok",
        "required": True,
        "detail": {
            "lifecycle": {"current_run_evidence": True},
            "phase4": {
                "current_run_evidence": True,
                "evidence_scope": "current_run",
            },
        },
    }
    assert checks["analysis_brief_current_run_evidence"]["status"] == "ok"
    assert checks["launcher_wrapper_status_ok"]["status"] == "ok"
    assert checks["launcher_wrapper_marker_status_ok"]["status"] == "ok"
    assert checks["not_invalid_infra_only"]["status"] == "ok"
    assert checks["not_prepared_only"]["status"] == "ok"
    assert checks["not_pre_campaign_preflight_failed"]["status"] == "ok"
    assert checks["postrun_report_status_marker"] == {
        "status": "ok",
        "required": False,
        "detail": {
            "POSTRUN_REPORTS_EXIT_STATUS": 1,
            "POSTRUN_STATUS_WRITE_EXIT_STATUS": 0,
        },
    }


def test_lifecycle_acceptance_checks_fail_closed_on_wrapper_status() -> None:
    inventory = _ready_inventory()
    inventory["launcher"]["status_fields"].update(
        {
            "wrapper_exit_status": 64,
            "postrun_acceptance_failed": True,
            "postrun_readiness_exit_status": 64,
        }
    )

    checks = PostrunLifecycleAcceptancePort().summarize(
        inventory,
        _ready_analysis_brief(),
    ).to_payloads()

    wrapper = checks["launcher_wrapper_status_ok"]
    assert wrapper["status"] == "failed"
    assert wrapper["detail"]["failures"] == [
        "wrapper_exit_status_nonzero",
        "postrun_acceptance_failed",
        "postrun_readiness_exit_status_nonzero",
    ]


def test_lifecycle_acceptance_checks_fail_closed_on_marker_status() -> None:
    inventory = _ready_inventory()
    inventory["launcher"]["exit_markers"].update(
        {
            "POSTRUN_ACCEPTANCE_FAILED": 1,
            "WRAPPER_EXIT_STATUS_EFFECTIVE": 64,
        }
    )

    checks = PostrunLifecycleAcceptancePort().summarize(
        inventory,
        _ready_analysis_brief(),
    ).to_payloads()

    marker = checks["launcher_wrapper_marker_status_ok"]
    assert marker["status"] == "failed"
    assert marker["detail"]["failures"] == [
        "postrun_acceptance_failed_marker_present",
        "wrapper_exit_status_effective_marker_present",
    ]


def test_lifecycle_acceptance_checks_keep_prepared_and_infra_failures() -> None:
    inventory = _ready_inventory()
    inventory["lifecycle"].update(
        {
            "current_run_evidence": False,
            "prepared_only": True,
            "pre_campaign_completion_preflight_failed": True,
            "invalid_infra_only": True,
        }
    )
    inventory["validity"]["invalid_infra_only"] = True
    inventory["phase4_evidence_coverage"]["current_run_evidence"] = False

    checks = PostrunLifecycleAcceptancePort().summarize(
        inventory,
        _ready_analysis_brief(),
    ).to_payloads()

    assert checks["current_run_evidence"]["status"] == "failed"
    assert checks["not_invalid_infra_only"]["status"] == "failed"
    assert checks["not_prepared_only"]["status"] == "failed"
    assert checks["not_pre_campaign_preflight_failed"]["status"] == "failed"


def _ready_inventory() -> dict[str, object]:
    return {
        "lifecycle": {"current_run_evidence": True},
        "validity": {"invalid_infra_only": False},
        "phase4_evidence_coverage": {
            "current_run_evidence": True,
            "evidence_scope": "current_run",
        },
        "launcher": {
            "status_fields": {
                "wrapper_exit_status": 0,
                "campaign_wrapper_exit_status": 0,
                "postrun_acceptance_status": "ready",
                "postrun_readiness_exit_status": 0,
                "postrun_reports_exit_status": 0,
            },
            "run_log_markers": {
                "POSTRUN_REPORTS_EXIT_STATUS": 1,
                "POSTRUN_STATUS_WRITE_EXIT_STATUS": 0,
            },
            "exit_markers": {
                "POSTRUN_ACCEPTANCE_FAILED": 0,
                "POSTRUN_REPORTS_EFFECTIVE_EXIT_STATUS": 0,
                "POSTRUN_READINESS_EFFECTIVE_EXIT_STATUS": 0,
                "WRAPPER_EXIT_STATUS_EFFECTIVE": 0,
            },
        },
    }


def _ready_analysis_brief() -> dict[str, object]:
    return {
        "lifecycle": {"current_run_evidence": True},
        "phase4_evidence_coverage": {"current_run_evidence": True},
    }
