from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from scion.postrun.opportunity_visibility import (
    PROBLEM_OPPORTUNITY_VISIBILITY_SCHEMA,
    add_problem_opportunity_visibility,
    empty_problem_opportunity_visibility_aggregate,
    problem_opportunity_visibility_fingerprint,
)
from scion.postrun.prompt_visibility_acceptance import (
    prompt_context_visibility_consistency_failures,
)


TOOLS_DIR = Path(__file__).parents[3] / "tools"


def test_problem_opportunity_visibility_fingerprint_is_manifest_based() -> None:
    fingerprint = problem_opportunity_visibility_fingerprint(_prompt_manifest())

    assert fingerprint["schema_version"] == (
        "scion.prompt_section_visibility_fingerprint.v1"
    )
    assert fingerprint["section_name"] == "problem_opportunity_summary"
    assert fingerprint["section_present"] is True
    assert fingerprint["section_status"] == "included"
    assert fingerprint["section_visible"] is True
    assert fingerprint["full_section_visible"] is True
    assert fingerprint["block_family"] == "research_signal"
    assert fingerprint["context_visibility"] == "full"
    assert fingerprint["decision_features_excluded"] is True

    aggregate = empty_problem_opportunity_visibility_aggregate()
    add_problem_opportunity_visibility(
        aggregate,
        fingerprint,
        is_hypothesis_generation=True,
    )

    assert aggregate["schema_version"] == PROBLEM_OPPORTUNITY_VISIBILITY_SCHEMA
    assert aggregate["trace_count"] == 1
    assert aggregate["hypothesis_generation_trace_count"] == 1
    assert aggregate["section_visible_trace_count"] == 1
    assert aggregate["hypothesis_generation_section_visible_trace_count"] == 1
    assert aggregate["full_section_visible_trace_count"] == 1
    assert aggregate["section_status_counts"] == {"included": 1}
    assert aggregate["block_family_counts"] == {"research_signal": 1}


def test_postrun_brief_and_checker_compare_opportunity_visibility(
    tmp_path: Path,
) -> None:
    brief_tool = _load_tool("postrun_analysis_brief")
    fingerprint = problem_opportunity_visibility_fingerprint(_prompt_manifest())
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
                                "call_kind": "hypothesis",
                                "problem_opportunity_visibility": fingerprint,
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

    opportunity = aggregate["problem_opportunity_visibility"]
    assert opportunity["section_visible_trace_count"] == 1
    assert opportunity["hypothesis_generation_section_visible_trace_count"] == 1

    summary = {
        "current_run_evidence": True,
        "available": True,
        "manifest_report_count": 1,
        "context_report_count": 1,
        "aggregate": aggregate,
        "entries": [entry],
    }
    expected = dict(summary)
    assert (
        prompt_context_visibility_consistency_failures(
            summary=summary,
            expected=expected,
        )
        == []
    )
    tampered = json.loads(json.dumps(summary))
    tampered["aggregate"]["problem_opportunity_visibility"][
        "section_visible_trace_count"
    ] = 0
    assert "prompt_context_visibility_problem_opportunity_mismatch" in (
        prompt_context_visibility_consistency_failures(
            summary=tampered,
            expected=expected,
        )
    )


def _prompt_manifest() -> dict[str, object]:
    return {
        "context_profile_metadata": {
            "problem_opportunity_summary_visibility": "full",
            "problem_opportunity_summary_prompt_key": "problem_opportunity_summary",
        },
        "section_statuses": {
            "problem_opportunity_summary": {
                "status": "included",
                "block_family": "research_signal",
                "prompt_block_profile": "algorithm",
                "char_count": 420,
            }
        },
        "visibility_ledger": {
            "entries": [
                {
                    "entry_kind": "section",
                    "section_name": "problem_opportunity_summary",
                    "block_family": "research_signal",
                    "prompt_block_profile": "algorithm",
                    "visibility_status": "full",
                    "char_count": 420,
                    "token_estimate": 105,
                }
            ]
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
