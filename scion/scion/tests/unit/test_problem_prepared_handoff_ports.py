from __future__ import annotations

from pathlib import Path

from scion.problems.cvrp.postrun_handoff import CvrpPreparedHandoffReviewPort
from scion.problems.cvrp.research_guidance import build_cvrp_legacy_research_focus
from scion.problems.warehouse_delivery.postrun_handoff import (
    WarehousePreparedHandoffReviewPort,
)
from scion.problems.warehouse_delivery.research_guidance import (
    build_warehouse_legacy_research_focus,
)


def test_cvrp_prepared_handoff_port_builds_legacy_checks_and_phase4(
    tmp_path: Path,
) -> None:
    split_path = tmp_path / "split.yaml"
    split_path.write_text("screening:\n  - CMT2\n  - CMT4\n", encoding="utf-8")
    manifest = {
        "problem_family": "cvrp",
        "decision_features_excluded": True,
        "config": {"split": str(split_path)},
        "research_focus": build_cvrp_legacy_research_focus(
            measurement_opportunity_diagnostics=_measurement(
                reason_codes=[
                    "CVRP_MDE_EXCEEDS_PRACTICAL_DELTA",
                    "TRAJECTORY_DIVERGENT_LOW_SNR",
                ],
            )
        ),
    }
    port = CvrpPreparedHandoffReviewPort()

    checks = port.prepared_contract_checks(
        manifest,
        local_run_root=tmp_path,
        repo_dir=Path(__file__).resolve().parents[4],
        scion_project_dir=Path(__file__).resolve().parents[4] / "scion",
    )
    phase4 = port.phase4_requirements(manifest, _coverage_item)
    signals = port.prepared_prompt_context_signals(
        manifest,
        manifest["research_focus"],
    )

    assert checks["cvrp_measurement_handoff_present"]["passed"] is True
    assert checks["cvrp_protected_cases_in_split"]["passed"] is True
    assert checks["cvrp_large_twoopt_bounded_constraints_present"]["passed"] is True
    assert phase4["cvrp_large_twoopt_seed_handoff"]["available"] is True
    assert phase4["cvrp_cmt_case_protection_handoff"]["available"] is True
    assert signals["cvrp_measurement_opportunity_handoff"]["available"] is True
    assert signals["cvrp_resume_continuity_requirements"]["available"] is True


def test_warehouse_prepared_handoff_port_builds_legacy_checks_and_phase4() -> None:
    manifest = {
        "problem_family": "warehouse_delivery",
        "decision_features_excluded": True,
        "research_focus": build_warehouse_legacy_research_focus(
            ".",
            ".",
            measurement_diagnostics=_measurement(
                reason_codes=[
                    "WAREHOUSE_MDE_EXCEEDS_PRACTICAL_DELTA",
                    "TRAJECTORY_DIVERGENT_LOW_SNR",
                ],
                schema_version="warehouse_measurement_runtime_handoff.v1",
            ),
        ),
    }
    port = WarehousePreparedHandoffReviewPort()

    checks = port.prepared_contract_checks(manifest)
    phase4 = port.phase4_requirements(manifest, _coverage_item)
    signals = port.prepared_prompt_context_signals(
        manifest,
        manifest["research_focus"],
    )

    assert checks["warehouse_followup_handoff_present"]["passed"] is True
    assert checks["warehouse_followup_required_evidence_complete"]["passed"] is True
    assert checks["warehouse_measurement_handoff_reason_codes"]["passed"] is True
    assert phase4["warehouse_v2_checkpoint_handoff"]["available"] is True
    assert phase4["warehouse_required_evidence_handoff"]["available"] is True
    assert signals["warehouse_measurement_runtime_handoff"]["available"] is True
    assert signals["warehouse_required_evidence"]["available"] is True


def _measurement(
    *,
    reason_codes: list[str],
    schema_version: str = "cvrp_measurement_opportunity_handoff.v1",
) -> dict[str, object]:
    return {
        "schema_version": schema_version,
        "source": "problem_v1.measurement.calibration_ref",
        "proposal_visibility_only": True,
        "decision_features_excluded": True,
        "screening_mde_at_power_80": 9.9,
        "practical_screen_delta": 5.0,
        "reason_codes": reason_codes,
        "screening_headroom": {"status": "available"},
        "mechanism_effect_ranking": [{"mechanism": "example"}],
        "opportunity_diagnostics": [{"kind": "example"}],
        "measurable_opportunity_classes": [{"id": "example"}],
        "transfer_risk": {"status": "bounded"},
        "required_diagnostics": {"items": ["example"]},
        "metric": "objective",
        "runtime_model": "bounded",
        "pairing_validity": "valid",
        "measurement_readiness": {
            "status": "ready",
            "reason_code": "ok",
        },
        "calibration": {
            "schema": "scion.aa_noise_floor.v1",
            "ref": "calibration.json",
            "decision_features_excluded": True,
        },
    }


def _coverage_item(count: int | None, source: str) -> dict[str, object]:
    safe_count = int(count or 0)
    return {"available": safe_count > 0, "count": safe_count, "source": source}
