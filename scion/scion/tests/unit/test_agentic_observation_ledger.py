from __future__ import annotations

from types import SimpleNamespace

from scion.proposal.agentic_observation_ledger.reuse import (
    already_observed_from_inherited_ledger,
)
from scion.proposal.agentic_observation_ledger.payloads import (
    compact_observation_ledger_for_resume,
)
from scion.tests.unit.agentic_session_test_support import *
from scion.tests.unit.test_active_solver_map import _FullProvider, _context as _map_context


def test_code_phase_reuses_hypothesis_algorithm_file_ledger_receipt(
    tmp_path: Path,
) -> None:
    target_file = "policies/baseline_algorithm.py"
    context = replace(
        _cvrp_context_with_champion(tmp_path),
        forced_surface="solver_design",
        forced_action="modify",
        forced_target_file=target_file,
    )
    hypothesis = HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="solver_design",
            target_file=target_file,
            target_objectives=["total_distance"],
        )
    )
    hypothesis_creative = PlanningCreative(
        [
            {
                "tool_name": "context.read_algorithm_file",
                "args": {
                    "surface": "solver_design",
                    "file_path": target_file,
                    "max_chars": 24000,
                },
            },
            {"stop": True},
        ],
        hypothesis=hypothesis,
    )
    artifact_store = FileAgenticSessionArtifactStore(tmp_path / "aps-artifacts")
    hypothesis_session = AgenticProposalSession(
        hypothesis_creative,
        artifact_store=artifact_store,
        tool_registry=ProposalToolRegistry.default_read_only(),
        tool_loop_config=AgenticToolLoopConfig(max_tool_calls=18, max_steps=24),
    )

    hypothesis_output = hypothesis_session.run(
        AgenticProposalRequest(
            campaign_id="camp-cvrp",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )
    output_ref = next(
        ref for ref in hypothesis_output.tainted_artifact_refs if ref.endswith("output.json")
    )
    resume_context = {
        "source": "test",
        "resume": resume_from_artifact(output_ref, max_chars=12000),
    }
    code_creative = PlanningCreative(
        [
            {
                "tool_name": "context.read_algorithm_file",
                "args": {
                    "surface": "solver_design",
                    "file_path": target_file,
                    "max_chars": 24000,
                },
            },
            {"stop": True},
        ],
        hypothesis=hypothesis,
        patch=PatchProposal(
            file_path=target_file,
            action="modify",
            code_content=(
                "def solve(instance, rng, time_limit_sec, context):\n"
                "    context.record_iteration('search', 1)\n"
                "    return context.nearest_neighbor()\n"
            ),
        ),
    )
    code_session = AgenticProposalSession(
        code_creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
        tool_loop_config=AgenticToolLoopConfig(max_tool_calls=18, max_steps=24),
    )

    code_output = code_session.run(
        AgenticProposalRequest(
            campaign_id="camp-cvrp",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context=None,
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approved_hypothesis=hypothesis,
            resume_context=resume_context,
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    receipt_events = [
        event.metadata
        for event in code_output.transcript
        if event.metadata.get("tool_name") == "context.read_algorithm_file"
        and event.metadata.get("observation_type") == "already_observed"
    ]
    receipt_payloads = [
        observation["structured_payload"]
        for observation in code_creative.code_contexts[-1]["agentic_tool_observations"]
        if observation["tool_name"] == "context.read_algorithm_file"
        and observation["structured_payload"].get("already_observed")
    ]

    assert receipt_events
    assert receipt_payloads
    assert receipt_payloads[0]["file_path"] == target_file
    assert '"content_preview":' not in json.dumps(receipt_payloads, sort_keys=True)


def test_active_map_inherited_receipt_with_stale_digest_forces_reread() -> None:
    state = SimpleNamespace(
        _agentic_logical_phase="code",
        _inherited_observation_ledger=[
            {
                "observation_id": "obs-old-map",
                "tool_name": "context.read_active_solver_map",
                "normalized_args": {"surface": "policy_bundle"},
                "digest": "old-digest",
                "source_digest": {
                    "digest": "old-digest",
                    "snapshot_digest": "old-snapshot",
                    "source": "context.read_active_solver_map",
                },
                "snapshot_digest": "old-snapshot",
                "reusable_by_phases": ["code"],
                "coverage": {"coverage_status": "metadata_only"},
            }
        ],
    )
    context = _map_context(_FullProvider())

    reused = already_observed_from_inherited_ledger(
        state,
        context,
        tool_name="context.read_active_solver_map",
        args={"surface": "policy_bundle"},
        tool_call_id="tool-call-new",
    )

    assert reused is None


def test_resume_observation_ledger_canonicalizes_runtime_feedback_scope() -> None:
    ledger = {
        "schema_version": "agentic-observation-ledger.v1",
        "session_id": "session-1",
        "observations": [
            {
                "observation_id": "runtime-old",
                "tool_name": "feedback.query_runtime",
                "normalized_args": {"branch_id": "branch-1", "surface": "solver"},
                "summary": "old runtime feedback",
            },
            {
                "observation_id": "runtime-other-branch",
                "tool_name": "feedback.query_runtime",
                "normalized_args": {"branch_id": "branch-2", "surface": "solver"},
                "summary": "other branch runtime feedback",
            },
            {
                "observation_id": "runtime-new",
                "tool_name": "feedback.query_runtime",
                "normalized_args": {"branch_id": "branch-1", "surface": "solver"},
                "summary": "new runtime feedback",
            },
        ],
    }

    compact = compact_observation_ledger_for_resume(ledger, max_entries=10)
    observation_ids = [
        entry["observation_id"] for entry in compact["observations"]
    ]

    assert observation_ids == ["runtime-new", "runtime-other-branch"]
