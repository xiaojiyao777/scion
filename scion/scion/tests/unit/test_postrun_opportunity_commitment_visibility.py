from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from scion.core import proposal_trajectory_artifacts as trajectory
from scion.postrun.opportunity_visibility import (
    OPPORTUNITY_COMMITMENT_VISIBILITY_SCHEMA,
    add_opportunity_commitment_visibility,
    empty_opportunity_commitment_visibility_aggregate,
    opportunity_commitment_visibility_fingerprint,
)
from scion.postrun.prompt_visibility_acceptance import (
    prompt_context_visibility_consistency_failures,
)


TOOLS_DIR = Path(__file__).parents[3] / "tools"


def test_opportunity_commitment_visibility_fingerprint_is_manifest_based() -> None:
    fingerprint = opportunity_commitment_visibility_fingerprint(_prompt_manifest())

    assert fingerprint["schema_version"] == (
        "scion.prompt_section_visibility_fingerprint.v1"
    )
    assert fingerprint["section_name"] == "opportunity_evidence_commitment"
    assert fingerprint["section_present"] is True
    assert fingerprint["section_visible"] is True
    assert fingerprint["block_family"] == "research_signal"
    assert fingerprint["decision_features_excluded"] is True
    assert fingerprint["commitment_summary"]["selected_mechanism_ids"] == [
        "bounded_operator"
    ]

    aggregate = empty_opportunity_commitment_visibility_aggregate()
    add_opportunity_commitment_visibility(
        aggregate,
        fingerprint,
        is_code_generation=True,
    )

    assert aggregate["schema_version"] == OPPORTUNITY_COMMITMENT_VISIBILITY_SCHEMA
    assert aggregate["trace_count"] == 1
    assert aggregate["code_trace_count"] == 1
    assert aggregate["code_section_visible_trace_count"] == 1
    assert aggregate["commitment_summary_trace_count"] == 1
    assert aggregate["commitment_summary_without_section_count"] == 0
    assert aggregate["code_commitment_summary_without_section_count"] == 0
    assert aggregate["selected_mechanism_id_counts"] == {"bounded_operator": 1}
    assert aggregate["requirement_id_counts"] == {"bounded_required_evidence": 1}


def test_opportunity_commitment_visibility_reports_summary_without_section() -> None:
    fingerprint = opportunity_commitment_visibility_fingerprint(
        _prompt_manifest_without_commitment_section()
    )
    aggregate = empty_opportunity_commitment_visibility_aggregate()
    add_opportunity_commitment_visibility(
        aggregate,
        fingerprint,
        is_code_generation=True,
    )

    assert fingerprint["section_present"] is False
    assert fingerprint["commitment_summary_available"] is True
    assert aggregate["commitment_summary_trace_count"] == 1
    assert aggregate["commitment_summary_without_section_count"] == 1
    assert aggregate["code_commitment_summary_without_section_count"] == 1
    assert aggregate["omitted_or_absent_trace_count"] == 1
    assert aggregate["selected_mechanism_id_counts"] == {"bounded_operator": 1}
    assert aggregate["requirement_id_counts"] == {"bounded_required_evidence": 1}


def test_proposal_trajectory_fingerprint_carries_commitment_visibility(
    tmp_path: Path,
) -> None:
    campaign_dir = tmp_path / "campaign"
    agentic_dir = campaign_dir / "agentic_sessions"
    prompt_dir = agentic_dir / "prompt_manifests"
    prompt_dir.mkdir(parents=True)
    prompt_ref = "agentic_sessions/prompt_manifests/code.json"
    (campaign_dir / prompt_ref).write_text(
        json.dumps(_prompt_manifest(), indent=2),
        encoding="utf-8",
    )

    fingerprints, ref_count, loaded_count = trajectory._trace_fingerprints(
        {
            "traces": [
                {
                    "trace_id": "trace-code",
                    "call_kind": "code",
                    "prompt_manifest_artifact_ref": prompt_ref,
                }
            ]
        },
        session_prompt_refs=[],
        campaign_dir=campaign_dir,
        agentic_dir=agentic_dir,
    )

    assert ref_count == 1
    assert loaded_count == 1
    visibility = fingerprints[0]["opportunity_commitment_visibility"]
    assert visibility["section_name"] == "opportunity_evidence_commitment"
    assert visibility["section_visible"] is True
    assert visibility["commitment_summary"]["requirement_ids"] == [
        "bounded_required_evidence"
    ]


def test_postrun_brief_and_checker_compare_commitment_visibility(
    tmp_path: Path,
) -> None:
    brief_tool = _load_tool("postrun_analysis_brief")
    fingerprint = opportunity_commitment_visibility_fingerprint(_prompt_manifest())
    report_path = tmp_path / "proposal_trajectory_manifest.v1.json"
    report_path.write_text(
        json.dumps(
            {
                "counts": {
                    "prompt_manifest_ref_count": 1,
                    "prompt_manifest_loaded_count": 1,
                },
                "sessions": [
                    {
                        "trace_fingerprints": [
                            {
                                "call_kind": "code",
                                "opportunity_commitment_visibility": fingerprint,
                            }
                        ]
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    entry = brief_tool._proposal_trajectory_context_entry(report_path)
    aggregate = brief_tool._empty_prompt_context_aggregate()
    brief_tool._merge_prompt_context_aggregate(aggregate, entry)

    commitment = aggregate["opportunity_commitment_visibility"]
    assert commitment["code_section_visible_trace_count"] == 1
    assert commitment["selected_mechanism_id_counts"] == {"bounded_operator": 1}

    summary = {
        "schema_version": "scion.postrun_prompt_context_visibility_summary.v1",
        "report_only": True,
        "quality_judgment": False,
        "decision_features_excluded": True,
        "raw_prompt_excluded": True,
        "raw_response_excluded": True,
        "patch_body_excluded": True,
        "current_run_evidence": True,
        "available": True,
        "manifest_report_count": 1,
        "context_report_count": 1,
        "aggregate": aggregate,
        "entries": [entry],
    }
    expected = json.loads(json.dumps(summary))
    assert (
        prompt_context_visibility_consistency_failures(
            summary=summary,
            expected=expected,
        )
        == []
    )
    tampered = json.loads(json.dumps(summary))
    tampered["aggregate"]["opportunity_commitment_visibility"][
        "code_section_visible_trace_count"
    ] = 0
    assert "prompt_context_visibility_opportunity_commitment_mismatch" in (
        prompt_context_visibility_consistency_failures(
            summary=tampered,
            expected=expected,
        )
    )
    tampered = json.loads(json.dumps(summary))
    tampered["aggregate"]["opportunity_commitment_visibility"][
        "commitment_summary_without_section_count"
    ] = 1
    assert "prompt_context_visibility_opportunity_commitment_mismatch" in (
        prompt_context_visibility_consistency_failures(
            summary=tampered,
            expected=expected,
        )
    )


def _prompt_manifest() -> dict[str, object]:
    return {
        "section_statuses": {
            "opportunity_evidence_commitment": {
                "status": "included",
                "block_family": "research_signal",
                "prompt_block_profile": "algorithm",
                "char_count": 360,
            }
        },
        "visibility_ledger": {
            "entries": [
                {
                    "entry_kind": "section",
                    "section_name": "opportunity_evidence_commitment",
                    "block_family": "research_signal",
                    "prompt_block_profile": "algorithm",
                    "visibility_status": "full",
                    "char_count": 360,
                    "token_estimate": 90,
                }
            ]
        },
        "opportunity_evidence_commitment_summary": {
            "schema_version": (
                "scion.problem_opportunity_evidence_commitment_manifest_summary.v1"
            ),
            "commitment_schema_version": (
                "scion.problem_opportunity_evidence_commitment.v1"
            ),
            "problem_family": "demo",
            "objective": "score",
            "selected_mechanism_ids": ["bounded_operator"],
            "requirement_ids": ["bounded_required_evidence"],
            "mechanism_families": ["bounded_operator"],
            "requirement_count": 1,
            "source_schema_version": "scion.problem_opportunity_summary.v1",
            "source_summary_digest": "source1234",
            "commitment_digest": "commit1234",
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
            "report_only": True,
        },
    }


def _prompt_manifest_without_commitment_section() -> dict[str, object]:
    manifest = _prompt_manifest()
    manifest["section_statuses"] = {}
    manifest["visibility_ledger"] = {"entries": []}
    return manifest


def _load_tool(name: str):
    path = TOOLS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module
