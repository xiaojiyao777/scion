from __future__ import annotations

import json
from pathlib import Path

from scion.tests.test_postrun_analysis_brief import (
    _write_cvrp_large_twoopt_manifest,
    _write_cvrp_protocol_run,
    _write_json,
    brief_tool,
)


def test_cvrp_opportunity_usage_accepts_complete_requirement_evidence_below_mde(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "cvrp-twoopt-complete-evidence-below-mde"
    campaign_dir = run_root / "campaign"
    campaign_dir.mkdir(parents=True)
    _write_cvrp_large_twoopt_manifest(run_root, campaign_dir, rounds=1)
    _write_cvrp_protocol_run(
        run_root,
        campaign_dir,
        mechanism_family="bounded_large_twoopt",
    )
    _make_top_row_below_mde(run_root)
    _write_large_twoopt_proposal_manifest(run_root)

    brief = brief_tool.build_brief(run_root)

    large_twoopt = brief["cvrp_large_twoopt_summary"]
    mechanism = large_twoopt["evidence"]["large_twoopt_mechanism"]
    requirements = large_twoopt["evidence"]["evidence_requirement_statuses"]
    usage = brief["cvrp_opportunity_usage_summary"]

    assert large_twoopt["interpretation"] == (
        "protocol_evaluated_without_large_twoopt_direct_evidence"
    )
    assert mechanism["direct_evidence_ready"] is False
    assert mechanism["direct_evidence"]["positive_effect_row_count"] == 0
    assert requirements["complete"] is True
    assert requirements["requirements"][
        "large_instance_two_opt_objective_runtime_requirement"
    ]["outcome_status"] == "measured_no_positive_at_mde"
    assert usage["usage_status"] == "used"
    assert usage["counts"]["used_opportunity"] == 1
    assert usage["counts"]["opportunity_evidence_checklist_unproven"] == 0
    assert usage["required_evidence_proof"]["checklist_status"] == "proven"
    assert usage["required_evidence_proof"].get("missing", []) == []
    assert usage["required_evidence_proof"][
        "outcome_direct_evidence_ready"
    ] is False


def _make_top_row_below_mde(run_root: Path) -> None:
    report_path = (
        run_root
        / "postrun_acceptance"
        / "research_efficiency"
        / "cvrp.research_efficiency.v1.json"
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    effects = report["protocol_effects_vs_mde"]
    effects["interpretation"] = "no_positive_protocol_effect_at_or_above_mde"
    effects["rows_at_or_above_mde"] = 0
    effects["positive_rows"] = 0
    effects["nonpositive_rows"] = 2
    effects["max_effect_to_mde_ratio"] = 0.2
    family = effects["mechanism_family_effect_summary"]["by_family"][
        "bounded_large_twoopt"
    ]
    family["positive_rows"] = 0
    family["nonpositive_rows"] = 2
    family["rows_at_or_above_mde"] = 0
    family["rows_below_mde"] = 2
    family["max_median_delta"] = 2.0
    family["max_effect_to_mde_ratio"] = 0.2
    top_row = effects["top_rows_by_effect_to_mde"][0]
    top_row["median_delta"] = 2.0
    top_row["effect_to_mde_ratio"] = 0.2
    top_row["positive_effect_at_or_above_mde"] = False
    report_path.write_text(json.dumps(report), encoding="utf-8")


def _write_large_twoopt_proposal_manifest(run_root: Path) -> None:
    _write_json(
        run_root
        / "postrun_acceptance"
        / "manifests"
        / "proposal_trajectory_manifest.v1.json",
        {
            "counts": {
                "prompt_manifest_ref_count": 1,
                "prompt_manifest_loaded_count": 1,
            },
            "sessions": [
                {
                    "session_id": "s-large-twoopt",
                    "branch_id": "branch-1",
                    "proposal_fingerprint": {
                        "selected_surface": "solver_design",
                        "action": "modify",
                        "target_file": (
                            "policies/baseline_modules/local_search.py"
                        ),
                        "mechanism_ids": [
                            "large_instance_intra_route_two_opt_seed"
                        ],
                    },
                    "trace_fingerprints": [
                        {
                            "call_kind": "hypothesis",
                            "visibility_ledger_digest": "visibility-ledger-1",
                            "problem_opportunity_visibility": {
                                "schema_version": (
                                    "scion.prompt_section_visibility_fingerprint.v1"
                                ),
                                "section_name": "problem_opportunity_summary",
                                "section_status": "included",
                                "section_present": True,
                                "section_visible": True,
                                "full_section_visible": True,
                                "block_family": "research_signal",
                                "context_visibility": "full",
                                "decision_features_excluded": True,
                            },
                            "block_family_summary": {
                                "families": {
                                    "research_signal": {
                                        "char_count": 100,
                                        "token_estimate": 25,
                                    }
                                }
                            },
                        }
                    ],
                }
            ],
        },
    )
