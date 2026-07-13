from __future__ import annotations

import json
from pathlib import Path

import pytest

from scion.problems.cvrp.postrun_handoff import CvrpPreparedHandoffReviewPort
from scion.problems.warehouse_delivery.postrun_handoff import (
    WarehousePreparedHandoffReviewPort,
)
from scion.postrun.handoff.prompt_context_readiness import (
    build_prepared_prompt_context_readiness,
)


@pytest.mark.parametrize(
    ("port", "problem_family", "check_name", "signal_name", "problem_v1"),
    (
        (
            CvrpPreparedHandoffReviewPort(),
            "cvrp",
            "cvrp_problem_guidance_non_gating",
            "cvrp_problem_guidance_context",
            "scion/scion/problems/cvrp/problem-v1.yaml",
        ),
        (
            WarehousePreparedHandoffReviewPort(),
            "warehouse_delivery",
            "warehouse_problem_guidance_non_gating",
            "warehouse_problem_guidance_context",
            "scion/scion/problems/warehouse_delivery/problem-v1.yaml",
        ),
    ),
)
def test_problem_prepared_handoff_guidance_is_report_only(
    port: object,
    problem_family: str,
    check_name: str,
    signal_name: str,
    problem_v1: str,
) -> None:
    research_focus = {
        "current_question": "Choose a source-grounded algorithmic direction.",
        "decision_boundary": "Excluded from decisions and protocol.",
    }
    manifest = {
        "problem_family": problem_family,
        "research_focus": research_focus,
    }

    checks = port.prepared_contract_checks(
        manifest,
        repo_dir=Path.cwd(),
        scion_project_dir=Path.cwd() / "scion",
    )
    phase4 = port.phase4_requirements(manifest, _coverage_item)
    signals = port.prepared_prompt_context_signals(manifest, research_focus)
    spec = port.prompt_bridge_spec()
    prompt_summary = spec.measurement_prompt_summary(
        problem_v1_path=Path(problem_v1)
    )

    assert checks == {
        check_name: {
            "passed": True,
            "detail": {
                "report_only": True,
                "decision_features_excluded": True,
                "content_required_for_launch": False,
            },
        }
    }
    assert phase4 == {}
    assert signals[signal_name]["available"] is True
    assert signals[signal_name]["required"] is False
    assert spec.measurement_signal_name.startswith(problem_family.split("_")[0])
    assert not any(name.startswith("active_subject_") for name in vars(spec))
    assert prompt_summary["available"] is True
    assert prompt_summary["lossless_context_handoff"] is True
    assert prompt_summary["forbidden_prompt_tokens_present"] == []


def _coverage_item(count: int | None, source: str) -> dict[str, object]:
    safe_count = int(count or 0)
    return {"available": safe_count > 0, "count": safe_count, "source": source}


@pytest.mark.parametrize(
    ("problem_family", "port"),
    (
        ("cvrp", CvrpPreparedHandoffReviewPort()),
        ("warehouse_delivery", WarehousePreparedHandoffReviewPort()),
    ),
)
def test_missing_problem_guidance_does_not_block_prompt_readiness(
    tmp_path: Path,
    problem_family: str,
    port: object,
) -> None:
    manifest = {
        "problem_family": problem_family,
        "execution": {"proposal_runtime_mode": "direct_v3"},
    }
    (tmp_path / "prepared_run_manifest.v1.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )

    report = build_prepared_prompt_context_readiness(
        tmp_path,
        repo_dir=Path.cwd(),
        ports_by_family={problem_family: port},
    )

    assert report["readiness"]["ready_for_launch_prompt_audit"] is True
    assert report["readiness"]["missing_required"] == []
    assert report["signals"]["prepared_research_focus"]["required"] is False
    assert report["signals"]["research_focus_decision_boundary"]["required"] is False
    assert report["signals"]["prepared_research_focus_projection"]["required"] is False
