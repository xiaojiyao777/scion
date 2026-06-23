from __future__ import annotations

from pathlib import Path

from scion.tests import test_check_postrun_acceptance as fixtures


def test_postrun_acceptance_prefers_stored_inventory_artifact(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_root = fixtures._write_current_run_root(
        tmp_path / "warehouse-stored-inventory"
    )
    fixtures.rebuild_tool.rebuild_postrun_acceptance(
        run_root,
        report_stem="fixture",
        observed_control_arm="on",
        control_pair_key="fixture:rep01",
        strict=True,
    )

    def fail_live_inventory_rebuild(_run_root: Path) -> dict[str, object]:
        raise AssertionError("live inventory rebuild should not be required")

    monkeypatch.setattr(
        fixtures.check_tool,
        "build_inventory",
        fail_live_inventory_rebuild,
    )

    readiness = fixtures.check_tool.build_readiness(run_root)
    contract_check = readiness["checks"][
        "analysis_brief_prepared_contract_consistency"
    ]

    assert readiness["checks"]["inventory_loaded"]["detail"]["source"] == (
        "stored_postrun_inventory"
    )
    assert "analysis_brief_prepared_contract_consistency" not in readiness[
        "failed_required_checks"
    ]
    assert contract_check["status"] == "ok"
    assert contract_check["detail"]["failures"] == []
