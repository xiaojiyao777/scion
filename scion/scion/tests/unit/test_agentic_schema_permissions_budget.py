"""Focused tests split from test_agentic_proposal_tools_schema.py."""

from .agentic_schema_test_support import *  # noqa: F401,F403
from pydantic import BaseModel
from scion.proposal.tools.models import (
    ProposalExposureLevel,
    ProposalToolContext,
    ProposalToolPermission,
)


class _EmptyMaliciousInput(BaseModel):
    pass


class _SuccessfulPayloadTool:
    name = "malicious.success_payload"
    input_schema = _EmptyMaliciousInput
    permission = ProposalToolPermission.READ_PUBLIC_CONTEXT
    read_only = True
    concurrency_safe = True
    max_result_chars = 4000

    def __init__(self, payload: dict, summary: str = "malicious payload") -> None:
        self._payload = payload
        self._summary = summary

    def call(
        self,
        args: _EmptyMaliciousInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        del args
        return ProposalObservation(
            observation_id="malicious-observation",
            session_id=context.session_id,
            tool_name=self.name,
            tool_call_id="before-registry",
            observation_type="malicious_success",
            summary=self._summary,
            structured_payload=self._payload,
            exposure_level=ProposalExposureLevel.PUBLIC_SPEC,
        )


def test_registry_sanitizes_successful_tool_payload_forbidden_keys(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry(
        [
            _SuccessfulPayloadTool(
                {
                    "safe": {"field": "kept"},
                    "raw_metrics_ref": "/SECRET/raw/screening.json",
                    "nested": {
                        "case_ids": ["case-1"],
                        "kept": 1,
                    },
                }
            )
        ]
    )
    context = _context(tmp_path)

    observation = registry.call("malicious.success_payload", {}, context)

    assert observation.is_error is False
    assert observation.structured_payload == {
        "safe": {"field": "kept"},
        "nested": {"kept": 1},
    }
    rendered = json.dumps(observation.structured_payload, sort_keys=True)
    assert "raw_metrics_ref" not in rendered
    assert "case_ids" not in rendered
    assert "SECRET" not in rendered


def test_registry_rejects_successful_tool_payload_raw_markers(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry(
        [
            _SuccessfulPayloadTool(
                {
                    "safe": "screening aggregate",
                    "leaked_ref": "raw://frozen_raw/promotion_raw.json",
                }
            )
        ]
    )
    context = _context(tmp_path)

    observation = registry.call("malicious.success_payload", {}, context)

    assert observation.is_error is True
    assert observation.failure_code == ProposalToolFailureCode.EXPOSURE_DENIED
    assert observation.structured_payload["reason"] == "forbidden_raw_marker"


def test_registry_phase_policy_separates_model_tools_from_framework_previews(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path, policy=_tool_enabled_policy())

    hypothesis_policy = registry.phase_policy_projection(
        context,
        "hypothesis_planning",
    )
    code_policy = registry.phase_policy_projection(context, "code_planning")

    assert "proposal.contract_preview" not in hypothesis_policy[
        "model_selectable_tools"
    ]
    assert "proposal.algorithm_smoke" not in hypothesis_policy[
        "model_selectable_tools"
    ]
    assert "proposal.contract_preview" in hypothesis_policy[
        "framework_preview_tools"
    ]
    assert "proposal.algorithm_smoke" in hypothesis_policy[
        "framework_preview_tools"
    ]
    assert "feedback.query_holdout_summary" not in hypothesis_policy[
        "model_selectable_tools"
    ]
    assert "proposal.contract_preview" not in code_policy["model_selectable_tools"]
    assert "context.read_algorithm_file" in code_policy["model_selectable_tools"]
    assert "proposal.draft_patch" not in code_policy["model_selectable_tools"]


def test_unsupported_or_unsafe_file_targets_fail_closed(tmp_path: Path) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path, policy=_tool_enabled_policy())

    draft = registry.call(
        "proposal.draft_patch",
        _valid_policy_patch_payload(file_path="../secret.py"),
        context,
    )
    preview = registry.call(
        "proposal.contract_preview",
        {"patch": _valid_policy_patch_payload(file_path="/tmp/secret.py")},
        context,
    )

    assert draft.is_error is True
    assert draft.failure_code == ProposalToolFailureCode.PERMISSION_DENIED
    assert preview.is_error is False
    assert preview.structured_payload["passed"] is False
    assert preview.structured_payload["patch"]["passed"] is False


def test_aps3_tool_permissions_default_deny_draft_and_contract_preview(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path, policy=ContextExposurePolicy())

    draft = registry.call(
        "proposal.draft_hypothesis",
        _valid_hypothesis_payload(),
        context,
    )
    preview = registry.call(
        "proposal.contract_preview",
        {"patch": _valid_policy_patch_payload()},
        context,
    )

    assert draft.is_error is True
    assert draft.failure_code == ProposalToolFailureCode.PERMISSION_DENIED
    assert preview.is_error is True
    assert preview.failure_code == ProposalToolFailureCode.PERMISSION_DENIED


def test_aps3_tool_permissions_explicit_allow_passes(tmp_path: Path) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path, policy=_tool_enabled_policy())

    draft = registry.call(
        "proposal.draft_hypothesis",
        _valid_hypothesis_payload(),
        context,
    )
    preview = registry.call(
        "proposal.contract_preview",
        {
            "hypothesis": _valid_hypothesis_payload(),
            "patch": _valid_policy_patch_payload(),
        },
        context,
    )

    assert draft.is_error is False
    assert preview.is_error is False
    assert preview.structured_payload["passed"] is True


def test_contract_preview_patch_only_is_incomplete_without_hypothesis(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path, policy=_tool_enabled_policy())

    preview = registry.call(
        "proposal.contract_preview",
        {"patch": _valid_policy_patch_payload()},
        context,
    )

    assert preview.is_error is False
    assert preview.structured_payload["passed"] is False
    assert preview.structured_payload["needs_hypothesis"] is True
    assert preview.structured_payload["patch"]["needs_hypothesis"] is True
    assert preview.structured_payload["validation_mode"] == "preview"
    assert preview.structured_payload["stateful_checks_excluded"] == [
        "C10_active_blacklist_rejected"
    ]
    assert "C12_patch_mechanism_echo" in preview.structured_payload[
        "hypothesis_bound_checks_skipped"
    ]
    assert "C12_patch_mechanism_echo" in preview.structured_payload["patch"][
        "hypothesis_bound_checks_skipped"
    ]


def test_contract_preview_rejects_nested_wildcard_target_and_allows_direct(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path, policy=_tool_enabled_policy())
    operator_hypothesis = _valid_hypothesis_payload(
        change_locus="route_local",
        action="modify",
        target_file="operators/local_a.py",
    )
    operator_patch = {
        "file_path": "operators/local_a.py",
        "action": "modify",
        "code_content": (
            "class LocalA:\n"
            "    def execute(self, solution, rng):\n"
            "        return solution\n"
        ),
    }

    direct = registry.call(
        "proposal.contract_preview",
        {"hypothesis": operator_hypothesis, "patch": operator_patch},
        context,
    )
    nested = registry.call(
        "proposal.contract_preview",
        {
            "hypothesis": {
                **operator_hypothesis,
                "target_file": "operators/archive/evil.py",
            },
            "patch": {
                **operator_patch,
                "file_path": "operators/archive/evil.py",
            },
        },
        context,
    )

    assert direct.structured_payload["passed"] is True
    assert nested.structured_payload["passed"] is False


def test_contract_preview_compacts_pass_fail_summary_when_full_payload_exceeds_budget() -> (
    None
):
    observation = ProposalObservation(
        observation_id="contract-preview-1",
        session_id="session-1",
        tool_name="proposal.contract_preview",
        tool_call_id="tool-9",
        observation_type="contract_preview",
        summary="Static contract preview passed.",
        structured_payload={
            "passed": True,
            "static_only": False,
            "workspace_materialized": False,
            "verification_run": False,
            "protocol_run": False,
            "decision_run": False,
            "hypothesis": {
                "passed": True,
                "hypothesis_text": "x" * 8000,
                "contract": {"passed": True, "check_count": 6},
                "checks": [{"name": "C2_locus", "passed": True}],
            },
            "patch": {
                "passed": True,
                "code_content": "x" * 24000,
                "contract": {"passed": True, "check_count": 10},
                "checks": [{"name": "C7_interface", "passed": True}],
                "problem_preview": {
                    "passed": True,
                    "surface": "solver_design",
                    "checks": [{"name": "preview", "passed": True}],
                    "workspace_materialized": False,
                },
            },
        },
    )

    compact = _compact_contract_preview_observation(observation)

    assert compact is not None
    assert compact.is_error is False
    assert _json_size(_observation_prompt_payload(compact)) < 1200
    assert compact.structured_payload["passed"] is True
    assert compact.structured_payload["patch"]["contract"]["check_count"] == 10
    assert compact.structured_payload["patch"]["problem_preview"]["passed"] is True
    assert compact.structured_payload["compact_due_to_budget"] is True
    assert _self_check_from_previews([compact]).contract_preview_passed is True


def test_agentic_session_keeps_minimal_contract_preview_at_budget_edge(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path, policy=_tool_enabled_policy())
    config = AgenticToolLoopConfig(max_observation_chars=64000)
    state = AgenticProposalSessionState(
        session_id="session-contract-budget",
        campaign_id="camp-1",
        branch_id="branch-1",
        observation_chars_used=62200,
    )
    session = AgenticProposalSession(
        FakeCreative(),
        tool_registry=ProposalToolRegistry.default_read_only(),
        tool_loop_config=config,
    )
    observation = ProposalObservation(
        observation_id="contract-preview-edge",
        session_id=state.session_id,
        tool_name="proposal.contract_preview",
        tool_call_id="tool-10",
        observation_type="contract_preview",
        summary="Static contract preview found issues.",
        structured_payload={
            "passed": False,
            "hypothesis": {
                "passed": True,
                "hypothesis_text": "x" * 12000,
                "checks": [{"name": "C2_locus", "passed": True}],
            },
            "patch": {
                "passed": False,
                "code_content": "x" * 50000,
                "checks": [
                    {
                        "name": f"C{i}_large_failure",
                        "passed": False,
                        "detail": "x" * 1000,
                    }
                    for i in range(8)
                ],
            },
        },
    )

    compact = session._enforce_observation_budget(context, state, observation)

    assert compact.is_error is False
    assert compact.failure_code is None
    assert compact.structured_payload["passed"] is False
    assert (
        compact.structured_payload.get("minimal_due_to_budget") is True
        or compact.structured_payload.get("compact_due_to_budget") is True
    )
    assert _json_size(_observation_prompt_payload(compact)) <= (
        config.max_observation_chars - state.observation_chars_used
    )
    self_check = _self_check_from_previews([compact])
    assert self_check.contract_preview_passed is False
    assert any("C0_large_failure" in code for code in self_check.contract_preview_codes)


def test_contract_preview_failure_issues_become_self_check_codes() -> None:
    observation = ProposalObservation(
        observation_id="contract-preview-fail",
        session_id="session-1",
        tool_name="proposal.contract_preview",
        tool_call_id="tool-9",
        observation_type="contract_preview",
        summary="Static contract preview found issues: bad lifecycle field.",
        structured_payload={
            "passed": False,
            "static_only": False,
            "patch": {
                "passed": False,
                "problem_preview": {
                    "passed": False,
                    "issues": [
                        "algorithm_body.baseline_budget_policy returned unknown value 'legacy_floor'",
                    ],
                },
            },
        },
    )

    self_check = _self_check_from_previews([observation])
    compact = _compact_contract_preview_observation(observation)

    assert self_check.contract_preview_passed is False
    assert any(
        "baseline_budget_policy" in code for code in self_check.contract_preview_codes
    )
    assert compact is not None
    assert "baseline_budget_policy" in json.dumps(compact.structured_payload)


def test_contract_preview_hypothesis_c11_failure_marks_schema_invalid() -> None:
    observation = ProposalObservation(
        observation_id="contract-preview-c11-fail",
        session_id="session-1",
        tool_name="proposal.contract_preview",
        tool_call_id="tool-9",
        observation_type="contract_preview",
        summary="Static contract preview found issues: C11_expected_telemetry.",
        structured_payload={
            "passed": False,
            "hypothesis": {
                "passed": False,
                "checks": [
                    {
                        "name": "C11_expected_telemetry",
                        "passed": False,
                        "detail": (
                            "expected_telemetry category 'attribution' is not "
                            "supported"
                        ),
                    }
                ],
            },
        },
    )

    self_check = _self_check_from_previews([observation])

    assert self_check.schema_valid is False
    assert any(
        "C11_expected_telemetry" in code
        for code in self_check.schema_preview_codes
    )
    assert self_check.contract_preview_passed is False
