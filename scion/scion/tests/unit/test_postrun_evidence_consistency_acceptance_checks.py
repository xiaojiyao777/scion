from __future__ import annotations

from scion.postrun import (
    PHASE4_EVIDENCE_COVERAGE_SCHEMA,
    PostrunEvidenceConsistencyAcceptancePort,
)


def test_evidence_consistency_checks_emit_legacy_ready_payloads() -> None:
    analysis_brief, inventory = _ready_inputs()

    checks = PostrunEvidenceConsistencyAcceptancePort().summarize(
        analysis_brief=analysis_brief,
        inventory=inventory,
    ).to_payloads()

    assert checks["phase4_evidence_coverage_actionability"]["status"] == "ok"
    assert (
        checks["analysis_brief_prepared_contract_consistency"]["status"] == "ok"
    )
    assert checks["current_run_report_families_present"] == {
        "status": "ok",
        "required": True,
        "detail": {
            "summaries": 1,
            "failures": 1,
            "research_efficiency": 1,
            "manifests": 1,
        },
    }


def test_evidence_consistency_checks_reject_drift() -> None:
    analysis_brief, inventory = _ready_inputs()
    analysis_brief["phase4_evidence_coverage"]["prepared_only"] = True
    analysis_brief["phase4_evidence_coverage"]["problem_specific_requirements"] = {
        "warehouse_followup": {
            "available": False,
            "count": 1,
            "source": "warehouse_report",
        }
    }
    analysis_brief["prepared_run_contract"]["model"] = "other-model"
    inventory["postrun_reports"]["counts"]["manifests"] = 0

    checks = PostrunEvidenceConsistencyAcceptancePort().summarize(
        analysis_brief=analysis_brief,
        inventory=inventory,
    ).to_payloads()

    phase4 = checks["phase4_evidence_coverage_actionability"]
    contract = checks["analysis_brief_prepared_contract_consistency"]
    reports = checks["current_run_report_families_present"]

    assert phase4["status"] == "failed"
    assert phase4["detail"]["failures"] == [
        "phase4_evidence_coverage_inventory_mismatch",
        "phase4_problem_specific_requirements_mismatch",
        "phase4_problem_specific_requirements_unavailable",
    ]
    assert phase4["detail"]["coverage_field_mismatches"] == [
        {
            "field": "prepared_only",
            "expected": False,
            "actual": True,
        }
    ]
    assert contract["status"] == "failed"
    assert contract["detail"]["failures"] == ["prepared_contract_model_mismatch"]
    assert reports["status"] == "failed"
    assert reports["detail"]["manifests"] == 0


def test_direct_mode_not_applicable_agentic_requirements_are_ready() -> None:
    analysis_brief, inventory = _ready_inputs()
    requirements = {
        key: {
            "status": "not_applicable",
            "applicable": False,
            "required": False,
            "source": "mode-aware fixture",
        }
        for key in (
            "agentic_session_index",
            "target_intent_trace",
            "tool_selection_trace",
            "agentic_transcript",
            "agentic_planner",
            "agentic_resume_context",
        )
    }
    analysis_brief["phase4_evidence_coverage"]["requirements"] = requirements
    inventory["phase4_evidence_coverage"]["requirements"] = requirements

    check = PostrunEvidenceConsistencyAcceptancePort().summarize(
        analysis_brief=analysis_brief,
        inventory=inventory,
    ).to_payloads()["phase4_evidence_coverage_actionability"]

    assert check["status"] == "ok"
    assert check["detail"]["required_evidence_unavailable"] == []


def test_unknown_mode_required_agentic_requirements_fail_closed() -> None:
    analysis_brief, inventory = _ready_inputs()
    requirements = {
        "agentic_session_index": {
            "status": "invalid_runtime_mode",
            "applicable": True,
            "required": True,
            "available": False,
            "source": "mode-aware fixture",
        }
    }
    analysis_brief["phase4_evidence_coverage"]["requirements"] = requirements
    inventory["phase4_evidence_coverage"]["requirements"] = requirements

    check = PostrunEvidenceConsistencyAcceptancePort().summarize(
        analysis_brief=analysis_brief,
        inventory=inventory,
    ).to_payloads()["phase4_evidence_coverage_actionability"]

    assert check["status"] == "failed"
    assert "phase4_required_evidence_unavailable" in check["detail"]["failures"]


def _ready_inputs() -> tuple[dict[str, object], dict[str, object]]:
    phase4_inventory = {
        "evidence_scope": "current_run",
        "prepared_only": False,
        "pre_campaign_completion_preflight_failed": False,
        "invalid_infra_only": False,
        "current_run_evidence": True,
        "problem_specific_requirements": {
            "warehouse_followup": {
                "available": True,
                "count": 1,
                "source": "warehouse_report",
            }
        },
    }
    phase4_brief = {
        **phase4_inventory,
        "schema_version": PHASE4_EVIDENCE_COVERAGE_SCHEMA,
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
    }
    prepared_contract = {
        "schema_version": "scion.prepared_run_contract.v1",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "manifest_present": True,
        "contract_complete": True,
        "problem_family": "warehouse_delivery",
        "model": "gpt-5.5",
        "resume_from_campaign": "",
        "control_pair_key": "",
        "completion_preflight": {"status": "ok"},
        "postrun_reports": {"required": True},
        "execution": {"runner": "wsl"},
        "git": {"commit": "abc1234"},
    }
    analysis_brief: dict[str, object] = {
        "phase4_evidence_coverage": phase4_brief,
        "prepared_run_contract": dict(prepared_contract),
    }
    inventory: dict[str, object] = {
        "phase4_evidence_coverage": phase4_inventory,
        "launcher": {
            "prepared_run_contract": dict(prepared_contract),
        },
        "postrun_reports": {
            "counts": {
                "summaries": 1,
                "failures": 1,
                "research_efficiency": 1,
                "manifests": 1,
            }
        },
    }
    return analysis_brief, inventory
