from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from scion.problems.cvrp.opportunity_review import (
    build_cvrp_opportunity_usage_summary,
)


TOOLS_DIR = Path(__file__).parents[3] / "tools"


def test_cvrp_opportunity_usage_classifies_structured_fingerprints() -> None:
    summary = build_cvrp_opportunity_usage_summary(
        problem_family="cvrp",
        current_run_evidence=True,
        prompt_context_visibility_summary=_visible_prompt_summary(),
        proposal_trajectory_manifests=[
            {
                "report": "proposal_trajectory_manifest.v1.json",
                "sessions": [
                    _session(
                        "s-large-twoopt",
                        mechanism_ids=["large_instance_intra_route_two_opt_seed"],
                        target_file="vrp/src/solver.py",
                        branch_lesson_fields={"contrasted_lessons": 1},
                    ),
                    _session(
                        "s-local-search",
                        mechanism_ids=["bounded_local_search_variant"],
                        target_file="policies/baseline_modules/local_search.py",
                    ),
                    _session(
                        "s-default-repeat",
                        mechanism_ids=["pure_alns_no_polish"],
                    ),
                    _session("s-unknown", mechanism_ids=["unmapped_new_toggle"]),
                ],
            }
        ],
    )

    assert summary["available"] is True
    assert summary["opportunity_summary_visible"] is True
    assert summary["usage_status"] == "mixed"
    assert summary["proposal_session_count"] == 4
    assert summary["interpretable_proposal_count"] == 4
    assert summary["counts"]["contrasted_opportunity"] == 1
    assert summary["counts"]["used_opportunity"] == 1
    assert summary["counts"]["default_avoid_repeat"] == 1
    assert summary["counts"]["ignored_or_unproven"] == 1
    assert "proposal_repeats_default_avoid_family" in summary["evidence_gaps"]


def test_cvrp_opportunity_usage_requires_visible_summary() -> None:
    summary = build_cvrp_opportunity_usage_summary(
        problem_family="cvrp",
        current_run_evidence=True,
        prompt_context_visibility_summary=_hidden_prompt_summary(),
        proposal_trajectory_manifests=[
            {
                "sessions": [
                    _session(
                        "s-large-twoopt",
                        mechanism_ids=["large_instance_intra_route_two_opt_seed"],
                    )
                ]
            }
        ],
    )

    assert summary["available"] is True
    assert summary["opportunity_summary_visible"] is False
    assert summary["usage_status"] == "not_applicable_no_visible_summary"
    assert summary["evidence_gaps"] == ["problem_opportunity_summary_not_visible"]


def test_postrun_brief_and_checker_rebuild_cvrp_opportunity_usage(
    tmp_path: Path,
) -> None:
    brief_tool = _load_tool("postrun_analysis_brief")
    check_tool = _load_tool("check_postrun_acceptance")
    report_dir = tmp_path / "postrun_acceptance" / "manifests"
    report_dir.mkdir(parents=True)
    report_path = report_dir / "proposal_trajectory_manifest.v1.json"
    report_path.write_text(
        json.dumps(
            {
                "counts": {
                    "prompt_manifest_ref_count": 1,
                    "prompt_manifest_loaded_count": 1,
                },
                "sessions": [
                    {
                        **_session(
                            "s-large-twoopt",
                            mechanism_ids=[
                                "large_instance_intra_route_two_opt_seed"
                            ],
                            target_file="vrp/src/solver.py",
                        ),
                        "trace_fingerprints": [
                            {
                                "call_kind": "hypothesis",
                                "problem_opportunity_visibility": (
                                    _visible_opportunity_fingerprint()
                                ),
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    inventory = {
        "phase4_evidence_coverage": {"current_run_evidence": True},
        "postrun_reports": {
            "files": {"manifests": ["manifests/proposal_trajectory_manifest.v1.json"]}
        },
        "launcher": {"prepared_run_contract": {"problem_family": "cvrp"}},
    }
    prompt_summary = brief_tool._prompt_context_visibility_summary(
        tmp_path,
        inventory,
    )
    usage_summary = build_cvrp_opportunity_usage_summary(
        problem_family="cvrp",
        current_run_evidence=True,
        prompt_context_visibility_summary=prompt_summary,
        proposal_trajectory_manifests=brief_tool._proposal_trajectory_manifests(
            tmp_path,
            inventory,
        ),
    )
    brief = {
        "lifecycle": {"current_run_evidence": True},
        "phase4_evidence_coverage": {"current_run_evidence": True},
        "prompt_context_visibility_summary": prompt_summary,
        "cvrp_opportunity_usage_summary": usage_summary,
    }

    status, detail = check_tool._cvrp_opportunity_usage_actionability(
        tmp_path,
        brief,
        inventory,
    )
    assert status == "ok", detail

    tampered = json.loads(json.dumps(brief))
    tampered["cvrp_opportunity_usage_summary"]["usage_status"] = (
        "ignored_or_unproven"
    )
    status, detail = check_tool._cvrp_opportunity_usage_actionability(
        tmp_path,
        tampered,
        inventory,
    )
    assert status == "failed"
    assert "cvrp_opportunity_usage_signature_mismatch" in detail["failures"]

    prepared_brief = {
        "lifecycle": {"current_run_evidence": False},
        "phase4_evidence_coverage": {"current_run_evidence": False},
    }
    status, detail = check_tool._cvrp_opportunity_usage_actionability(
        tmp_path,
        prepared_brief,
        inventory,
    )
    assert status == "skipped"
    assert detail["reason"] == "not_current_run_evidence"


def _visible_prompt_summary() -> dict[str, object]:
    return {
        "current_run_evidence": True,
        "aggregate": {
            "problem_opportunity_visibility": {
                "trace_count": 1,
                "section_visible_trace_count": 1,
                "hypothesis_generation_section_visible_trace_count": 1,
            }
        },
    }


def _hidden_prompt_summary() -> dict[str, object]:
    return {
        "current_run_evidence": True,
        "aggregate": {
            "problem_opportunity_visibility": {
                "trace_count": 1,
                "section_visible_trace_count": 0,
                "hypothesis_generation_section_visible_trace_count": 0,
            }
        },
    }


def _visible_opportunity_fingerprint() -> dict[str, object]:
    return {
        "schema_version": "scion.prompt_section_visibility_fingerprint.v1",
        "section_name": "problem_opportunity_summary",
        "section_status": "included",
        "section_present": True,
        "section_visible": True,
        "full_section_visible": True,
        "block_family": "research_signal",
        "context_visibility": "full",
        "decision_features_excluded": True,
    }


def _session(
    session_id: str,
    *,
    mechanism_ids: list[str],
    target_file: str = "",
    branch_lesson_fields: dict[str, int] | None = None,
) -> dict[str, object]:
    branch_lesson_fields = branch_lesson_fields or {}
    return {
        "session_id": session_id,
        "branch_id": f"branch-{session_id}",
        "proposal_fingerprint": {
            "selected_surface": "solver_design",
            "action": "modify",
            "target_file": target_file,
            "mechanism_ids": mechanism_ids,
        },
        "branch_lesson_usage_fingerprint": {
            "field_counts": branch_lesson_fields,
            "semantic_projection_present": bool(branch_lesson_fields),
        },
    }


def _load_tool(name: str):
    path = TOOLS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module
