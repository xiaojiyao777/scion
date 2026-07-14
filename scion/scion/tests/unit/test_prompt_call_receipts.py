from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from .source_ledger_test_support import ledgerize_code_context

import scion.proposal.engine.provider_call as provider_call
import scion.proposal.engine.hypothesis_prompts as hypothesis_prompts
from scion.proposal.engine import (
    CreativeLayer,
    ProposalValidationError,
    build_prompt_turn_snapshot,
    prompt_call_receipt_from_error,
)
from scion.proposal.llm_client import (
    LLMFormatError,
    LLMClient,
    LLMProviderError,
)
from scion.proposal.prompt_manifest_accounting import _provider_prompt_hash
from scion.proposal.schemas import HYPOTHESIS_TOOL


_HYPOTHESIS_RESPONSE = {
    "hypothesis_text": "Try one bounded local improvement move.",
    "change_locus": "local_search",
    "action": "create_new",
    "target_file": "operators/bounded_receipt.py",
    "predicted_direction": "improve",
    "target_weakness": "The control lacks this bounded move.",
    "expected_effect": "Improve the primary objective when the move applies.",
}

_PATCH_RESPONSE = {
    "file_path": "operators/bounded_receipt.py",
    "action": "create",
    "edit_intent": "full_file",
    "source_digest": None,
    "content_after": "def bounded_receipt(solution):\n    return solution\n",
    "full_file_reason": "Create the approved new research-surface file.",
    "evidence_refs": [],
}


class _CaptureClient:
    model = "test-model"

    def __init__(
        self,
        *,
        error: Exception | None = None,
        response: dict | None = None,
        expected_tool: str = "generate_hypothesis",
    ) -> None:
        self.error = error
        self.response = dict(response or _HYPOTHESIS_RESPONSE)
        self.expected_tool = expected_tool
        self.calls: list[tuple[str, list[dict], str]] = []
        self.tools: list[dict] = []

    def call_with_tool(
        self,
        prompt,
        tool,
        model=None,
        system_blocks=None,
        request_kind=None,
    ):
        del model
        self.calls.append(
            (str(prompt), list(system_blocks or []), str(request_kind))
        )
        self.tools.append(json.loads(json.dumps(tool)))
        if self.error is not None:
            raise self.error
        assert tool["name"] == self.expected_tool
        return dict(self.response)


class _DirectOpenAIClient(LLMClient):
    def __init__(self, *, length_response: bool = False) -> None:
        super().__init__(model="gpt-5.6-sol")
        self.length_response = length_response
        self.calls_seen: list[str] = []

    def _tool_call_once(
        self,
        prompt,
        tool,
        model,
        system_blocks,
        timeout_sec,
    ):
        del prompt, model, system_blocks, timeout_sec
        self.calls_seen.append(str(tool["name"]))
        if self.length_response:
            return {}
        if tool["name"] == "generate_hypothesis":
            return dict(_HYPOTHESIS_RESPONSE)
        return dict(_PATCH_RESPONSE)


def _hypothesis_context() -> dict:
    return {
        "problem_summary": "Synthetic routing control.",
        "research_surfaces": [
            {
                "name": "local_search",
                "kind": "operator",
                "target_files": ["operators/*.py"],
            }
        ],
        "objective_policy_guidance": "Minimize cost while preserving feasibility.",
        "solver_mechanics": "",
        "champion_operators_code": "class Control: pass",
        "champion_stats": {"version": 1, "operators": []},
        "available_actions": ["create_new"],
        "targetable_files": ["operators/*.py"],
        "experiment_history": [],
        "branch_id": "branch-receipt",
        "champion_version": 1,
    }


def _code_context() -> dict:
    return ledgerize_code_context({
        "problem_summary": "Synthetic routing control.",
        "target_file": "operators/bounded_receipt.py",
        "target_file_code": "",
        "action": "create_new",
        "approved_hypothesis": {
            "hypothesis_text": "Try one local improvement move.",
            "change_locus": "local_search",
            "action": "create_new",
            "target_file": "operators/bounded_receipt.py",
            "predicted_direction": "improve",
            "target_weakness": "The current solver lacks this move.",
            "expected_effect": "Improve screening outcomes.",
        },
        "operator_interface_spec": "",
        "research_surface": {"name": "local_search", "kind": "operator"},
        "editable_patterns": ["operators/*.py"],
        "frozen_patterns": ["solver.py"],
        "branch_id": "branch-receipt",
        "champion_version": 1,
    })


def _trace_from_ref(root: Path, trace_ref: str) -> dict:
    path_part = trace_ref.split("#", 1)[0]
    return json.loads((root / path_part).read_text(encoding="utf-8"))


def test_prompt_call_receipt_uses_one_snapshot_for_manifest_trace_and_provider(
    tmp_path: Path,
) -> None:
    client = _CaptureClient()
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    context = _hypothesis_context()
    snapshot = build_prompt_turn_snapshot("hypothesis", context)

    hypothesis, receipt = creative.generate_direct_hypothesis_with_receipt(
        context,
        snapshot,
    )

    expected_hash = _provider_prompt_hash(
        snapshot.system_blocks,
        snapshot.user_prompt,
    )
    trace = _trace_from_ref(tmp_path, receipt.trace_ref)
    assert hypothesis.hypothesis_text == _HYPOTHESIS_RESPONSE["hypothesis_text"]
    assert client.calls == [
        (snapshot.user_prompt, list(snapshot.system_blocks), "hypothesis")
    ]
    assert receipt.request_kind == "hypothesis"
    assert receipt.context_digest == snapshot.context_digest
    assert receipt.prompt_hash == expected_hash
    assert receipt.ok is True
    assert receipt.provider_ok is True
    assert receipt.error_category is None
    assert receipt.prompt_manifest_ref == f"{receipt.trace_ref}#/prompt_manifest"
    assert trace["system_blocks"] == list(snapshot.system_blocks)
    assert trace["user_prompt"] == snapshot.user_prompt
    assert trace["prompt_hash"] == expected_hash
    assert trace["prompt_manifest"]["artifact_kind"] == "api_visible_prompt_manifest"
    assert trace["prompt_manifest"]["prompt_hash"] == expected_hash
    assert trace["prompt_manifest"]["context_digest"] == snapshot.context_digest
    assert trace["prompt_manifest"]["projection"] == "direct_v3_lossless"
    assert client.tools[0]["input_schema"]["properties"]["change_locus"][
        "enum"
    ] == ["local_search"]
    assert "enum" not in HYPOTHESIS_TOOL["input_schema"]["properties"][
        "change_locus"
    ]
    assert trace["tool_schema"]["properties"]["change_locus"]["enum"] == [
        "local_search"
    ]


def test_provider_response_cannot_append_description_to_change_locus(
    tmp_path: Path,
) -> None:
    response = {
        **_HYPOTHESIS_RESPONSE,
        "change_locus": "local_search neighborhood family",
    }
    client = _CaptureClient(response=response)
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    context = _hypothesis_context()
    snapshot = build_prompt_turn_snapshot("hypothesis", context)

    with pytest.raises(
        ProposalValidationError,
        match="must exactly match one provider-visible research surface",
    ) as caught:
        creative.generate_direct_hypothesis_with_receipt(context, snapshot)

    assert len(client.calls) == 1
    assert client.tools[0]["input_schema"]["properties"]["change_locus"][
        "enum"
    ] == ["local_search"]
    receipt = prompt_call_receipt_from_error(caught.value)
    assert receipt is not None
    assert receipt.provider_ok is True
    assert receipt.ok is False
    assert receipt.error_category == "response_parse_failed"


def test_hypothesis_tool_enum_is_generic_across_visible_surfaces(
    tmp_path: Path,
) -> None:
    client = _CaptureClient()
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    context = {
        **_hypothesis_context(),
        "research_surfaces": [
            {"name": "local_search", "kind": "operator"},
            {"name": "construction", "kind": "solver_design"},
        ],
    }
    snapshot = build_prompt_turn_snapshot("hypothesis", context)

    creative.generate_direct_hypothesis_with_receipt(context, snapshot)

    assert client.tools[0]["input_schema"]["properties"]["change_locus"][
        "enum"
    ] == ["local_search", "construction"]


@pytest.mark.parametrize(
    "research_surfaces",
    [
        "local_search",
        [],
        [{"kind": "operator"}],
        [{"name": "local_search"}, {"name": "local_search"}],
        [{"name": " local_search"}],
        [{"name": "local_search "}],
    ],
)
def test_hypothesis_tool_rejects_invalid_visible_surface_contract_before_call(
    research_surfaces: object,
) -> None:
    context = {
        **_hypothesis_context(),
        "research_surfaces": research_surfaces,
    }

    with pytest.raises(ValueError, match="research"):
        build_prompt_turn_snapshot("hypothesis", context)


def test_receipt_uses_authoritative_owner_without_exposing_audit_context(
    tmp_path: Path,
) -> None:
    client = _CaptureClient()
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    raw_context = {
        **_hypothesis_context(),
        "_scion_trace_context": {
            "host_only_marker": "trace-context-sentinel",
        },
    }
    turn = build_prompt_turn_snapshot("hypothesis", raw_context)
    authority = turn.authoritative_context
    assert authority is not None
    provider_context = authority.inputs.provider_context(
        include_renderer_inputs=True
    )

    _, receipt = creative.generate_direct_hypothesis_with_receipt(
        provider_context,
        turn,
    )

    assert receipt.context_digest == turn.context_digest
    assert turn.authoritative_context_ref == authority.snapshot_id
    assert authority.governance_envelope.to_primitive() == {}
    assert "_scion_trace_context" not in provider_context
    trace = _trace_from_ref(tmp_path, receipt.trace_ref)
    assert "trace-context-sentinel" not in json.dumps(trace, sort_keys=True)
    assert "trace-context-sentinel" not in json.dumps(vars(receipt), sort_keys=True)

    original_call_count = len(client.calls)
    with pytest.raises(ValueError, match="provider context does not match"):
        creative.generate_direct_hypothesis_with_receipt(
            {
                **provider_context,
                "_scion_trace_context": raw_context["_scion_trace_context"],
            },
            turn,
        )
    with pytest.raises(ValueError, match="not bound to authoritative context"):
        creative.generate_direct_hypothesis_with_receipt(
            provider_context,
            replace(turn, authoritative_context_ref="forged-authority-ref"),
        )
    with pytest.raises(ValueError, match="context digest does not match authority"):
        creative.generate_direct_hypothesis_with_receipt(
            provider_context,
            replace(turn, context_digest="0" * 64),
        )
    with pytest.raises(ValueError, match="does not match authority"):
        creative.generate_direct_hypothesis_with_receipt(
            provider_context,
            replace(turn, render_kind="code"),
        )
    with pytest.raises(ValueError, match="no authoritative context owner"):
        creative.generate_direct_hypothesis_with_receipt(
            provider_context,
            replace(turn, authoritative_context=None),
        )
    assert len(client.calls) == original_call_count


def test_provider_call_attempt_identity_is_host_audit_only(
    tmp_path: Path,
) -> None:
    client = _CaptureClient()
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    raw_context = _hypothesis_context()
    snapshot = build_prompt_turn_snapshot("hypothesis", raw_context)
    authority = snapshot.authoritative_context
    assert authority is not None
    provider_context = authority.inputs.provider_context(
        include_renderer_inputs=True
    )
    audit = {
        "schema_version": "provider-call-attempt-audit.v1",
        "attempt_id": "attempt-host-only-sentinel",
        "phase": "hypothesis",
        "attempt_kind": "initial",
        "continuation_of_attempt_id": None,
        "hypothesis_attempt_id": "attempt-host-only-sentinel",
        "started_lineage_event_id": "event-host-only-sentinel",
    }

    _, receipt = creative.generate_direct_hypothesis_with_receipt(
        provider_context,
        snapshot,
        attempt_audit=audit,
    )

    assert receipt.attempt_id == audit["attempt_id"]
    assert receipt.attempt_started_event_id == audit["started_lineage_event_id"]
    assert receipt.continuation_of_attempt_id is None
    provider_prompt, provider_system_blocks, _request_kind = client.calls[0]
    provider_bytes = json.dumps(
        {
            "system_blocks": provider_system_blocks,
            "user_prompt": provider_prompt,
        },
        sort_keys=True,
    )
    assert audit["attempt_id"] not in provider_bytes
    assert audit["started_lineage_event_id"] not in provider_bytes
    trace = _trace_from_ref(tmp_path, receipt.trace_ref)
    assert trace["provider_call_attempt"] == audit


def test_direct_context_preserves_complete_authoritative_inputs(
    tmp_path: Path,
) -> None:
    client = _CaptureClient()
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    sentinels = {
        "problem_summary": "SENTINEL_STATIC_PROBLEM_SUMMARY",
        "problem_object": "SENTINEL_STATIC_PROBLEM_OBJECT",
        "solver_mechanics": "SENTINEL_STATIC_SOLVER_MECHANICS",
        "research_surfaces": "SENTINEL_STATIC_RESEARCH_SURFACES",
        "objective_policy": "SENTINEL_STATIC_OBJECTIVE_POLICY",
        "champion_code": "SENTINEL_STATIC_CHAMPION_CODE",
        "champion_stats": "SENTINEL_STATIC_CHAMPION_STATS",
        "item_9": "SENTINEL_ITEM_AFTER_8",
        "sequence_7": "SENTINEL_SEQUENCE_AFTER_6",
        "text_221": "SENTINEL_TEXT_AFTER_220",
        "line_7": "SENTINEL_LINE_AFTER_6",
        "char_361": "SENTINEL_CHAR_AFTER_360",
        "branch_code": "SENTINEL_BRANCH_CURRENT_CODE",
        "measurement": "SENTINEL_MEASUREMENT_CONTEXT",
        "research_question": "SENTINEL_RESEARCH_QUESTION",
    }

    context = {
        **_hypothesis_context(),
        "problem_summary": sentinels["problem_summary"],
        "problem_object": sentinels["problem_object"],
        "solver_mechanics": sentinels["solver_mechanics"],
        "research_surfaces": [
            {
                "name": "local_search",
                "kind": "operator",
                "marker": sentinels["research_surfaces"],
            }
        ],
        "objective_policy_guidance": sentinels["objective_policy"],
        "champion_operators_code": sentinels["champion_code"],
        "champion_stats": {"marker": sentinels["champion_stats"]},
        "branch_current_code": sentinels["branch_code"],
        "experiment_history": [
            {"round_num": index, "marker": f"round-{index}"}
            for index in range(8)
        ]
        + [
            {
                "round_num": 9,
                "marker": sentinels["item_9"],
                "long_text": "x" * 220 + sentinels["text_221"],
                "lines": [f"line-{index}" for index in range(6)]
                + [sentinels["line_7"]],
                "sequence": [f"value-{index}" for index in range(6)]
                + [sentinels["sequence_7"]],
                "long_line": "y" * 360 + sentinels["char_361"],
            }
        ],
        "problem_measurement_diagnostics": {
            "measurement_context": sentinels["measurement"],
        },
        "research_question": {
            "schema_version": "scion.typed_research_question.v1",
            "problem_family": "synthetic",
            "current_question": sentinels["research_question"],
        },
        "proposal_renderer_inputs": {
            "solver_design_prompt_guidance": {
                "hypothesis_guidance": [
                    "Use the complete source and evidence once."
                ]
            }
        },
    }
    snapshot = build_prompt_turn_snapshot("hypothesis", context)
    assert client.calls == []

    _, receipt = creative.generate_direct_hypothesis_with_receipt(context, snapshot)

    provider_prompt, provider_system_blocks, request_kind = client.calls[0]
    provider_bytes = json.dumps(
        {
            "system_blocks": provider_system_blocks,
            "user_prompt": provider_prompt,
        },
        sort_keys=True,
    )
    for sentinel in sentinels.values():
        assert sentinel in provider_bytes

    static_block = provider_system_blocks[1]["text"]
    evidence_block = provider_system_blocks[2]["text"]
    static_payload = json.loads(static_block.split("\n", 1)[1])
    evidence_payload = json.loads(evidence_block.split("\n", 1)[1])
    assert hypothesis_prompts._DIRECT_V3_STATIC_CONTEXT_KEYS == frozenset(
        {
            "problem_summary",
            "problem_object",
            "solver_mechanics",
            "research_surfaces",
            "objective_policy_guidance",
            "problem_measurement_diagnostics",
            "available_actions",
            "targetable_files",
            "champion_operators_code",
            "champion_stats",
        }
    )
    assert set(static_payload) == (
        hypothesis_prompts._DIRECT_V3_STATIC_CONTEXT_KEYS & set(context)
    )
    assert set(evidence_payload) == (
        set(context) - hypothesis_prompts._DIRECT_V3_STATIC_CONTEXT_KEYS
    )
    assert evidence_payload["branch_current_code"] == sentinels["branch_code"]
    for forbidden_marker in (
        "compact_research_signals.v1",
        "compact_cross_branch_learning.v1",
        "omitted_item_count",
        "omitted_runtime_feedback",
        "text_digest",
        "truncated",
    ):
        assert forbidden_marker not in provider_bytes.lower()

    expected_hash = _provider_prompt_hash(
        snapshot.system_blocks,
        snapshot.user_prompt,
    )
    trace = _trace_from_ref(tmp_path, receipt.trace_ref)
    assert request_kind == "hypothesis"
    assert snapshot.context_digest == receipt.context_digest
    assert client.calls == [
        (snapshot.user_prompt, list(snapshot.system_blocks), "hypothesis")
    ]
    assert trace["system_blocks"] == list(snapshot.system_blocks)
    assert trace["user_prompt"] == snapshot.user_prompt
    assert expected_hash == receipt.prompt_hash == trace["prompt_hash"]
    assert trace["prompt_manifest"]["prompt_hash"] == expected_hash
    manifest = trace["prompt_manifest"]
    assert manifest["schema_version"] == "api-visible-prompt-manifest.v4"
    assert manifest["context_digest"] == snapshot.context_digest
    assert manifest["projection"] == "direct_v3_lossless"
    assert manifest["provider_visible_size"]["system_block_count"] == len(
        snapshot.system_blocks
    )
    assert manifest["provider_visible_size"]["user_prompt_chars"] == len(
        snapshot.user_prompt
    )

    distinct_branch_code = "SENTINEL_DISTINCT_BRANCH_CODE"
    distinct_snapshot = build_prompt_turn_snapshot(
        "hypothesis",
        {**context, "branch_current_code": distinct_branch_code},
    )
    distinct_provider_bytes = json.dumps(
        {
            "system_blocks": list(distinct_snapshot.system_blocks),
            "user_prompt": distinct_snapshot.user_prompt,
        },
        sort_keys=True,
    )
    assert distinct_provider_bytes.count(sentinels["champion_code"]) == 1
    assert distinct_provider_bytes.count(distinct_branch_code) == 1


def test_direct_v3_context_fails_closed_for_unsupported_non_json_value() -> None:
    with pytest.raises(TypeError, match="unsupported opaque proposal context"):
        build_prompt_turn_snapshot(
            "hypothesis",
            {**_hypothesis_context(), "unsupported_runtime_handle": object()},
        )


def test_code_prompt_call_receipt_preserves_snapshot_identity(tmp_path: Path) -> None:
    response = dict(_PATCH_RESPONSE)
    client = _CaptureClient(response=response, expected_tool="generate_patch")
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    context = _code_context()
    snapshot = build_prompt_turn_snapshot("code", context)

    patch, receipt = creative.generate_direct_code_with_receipt(context, snapshot)

    trace = _trace_from_ref(tmp_path, receipt.trace_ref)
    expected_hash = _provider_prompt_hash(
        snapshot.system_blocks,
        snapshot.user_prompt,
    )
    assert patch.file_path == response["file_path"]
    assert client.calls == [
        (snapshot.user_prompt, list(snapshot.system_blocks), "code")
    ]
    assert receipt.request_kind == "code"
    assert receipt.context_digest == snapshot.context_digest
    assert receipt.prompt_hash == expected_hash
    assert receipt.provider_ok is receipt.ok is True
    assert trace["system_blocks"] == list(snapshot.system_blocks)
    assert trace["user_prompt"] == snapshot.user_prompt
    assert trace["prompt_hash"] == expected_hash
    assert trace["prompt_manifest"]["prompt_hash"] == expected_hash


def test_direct_hypothesis_and_code_use_provider_managed_output_without_cap(
    tmp_path: Path,
) -> None:
    client = _DirectOpenAIClient()
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    hypothesis_context = _hypothesis_context()
    hypothesis_snapshot = build_prompt_turn_snapshot(
        "hypothesis",
        hypothesis_context,
    )
    _, hypothesis_receipt = creative.generate_direct_hypothesis_with_receipt(
        hypothesis_context,
        hypothesis_snapshot,
    )
    code_context = _code_context()
    code_snapshot = build_prompt_turn_snapshot("code", code_context)
    _, code_receipt = creative.generate_direct_code_with_receipt(
        code_context,
        code_snapshot,
    )

    assert client.calls_seen == ["generate_hypothesis", "generate_patch"]
    for receipt in (hypothesis_receipt, code_receipt):
        trace = _trace_from_ref(tmp_path, receipt.trace_ref)
        assert trace["request_policy"]["output_token_policy"] == (
            "provider_managed"
        )
        assert trace["request_policy"]["output_token_parameter"] == "omitted"
        assert "max_tokens" not in trace["request_policy"]
        assert "truncation_retries" not in trace["request_policy"]


def test_direct_provider_response_rejects_removed_governance_fields(
    tmp_path: Path,
) -> None:
    long_a = "shared-prefix-" + ("x" * 140) + "-TAIL-A"
    long_b = "shared-prefix-" + ("x" * 140) + "-TAIL-B"
    structured = {
        "claim_a": long_a,
        "claim_b": long_b,
        "items": [f"item-{index}" for index in range(15)],
        "mapping": {f"key-{index}": index for index in range(26)},
        "deep": {"d1": {"d2": {"d3": {"d4": {"d5": "DEEP_TAIL"}}}}},
    }
    response = {
        **_HYPOTHESIS_RESPONSE,
        "novelty_signature": structured,
        "material_difference": structured,
        "branch_lesson_usage": structured,
    }
    client = _CaptureClient(response=response)
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    context = _hypothesis_context()
    snapshot = build_prompt_turn_snapshot("hypothesis", context)

    with pytest.raises(ProposalValidationError, match="extra_forbidden"):
        creative.generate_direct_hypothesis_with_receipt(context, snapshot)


def test_direct_hypothesis_and_code_receipts_use_provider_managed_output(
    tmp_path: Path,
) -> None:
    client = _DirectOpenAIClient()
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    context = _hypothesis_context()
    snapshot = build_prompt_turn_snapshot("hypothesis", context)

    _, hypothesis_receipt = creative.generate_direct_hypothesis_with_receipt(
        context,
        snapshot,
    )
    code_context = _code_context()
    code_snapshot = build_prompt_turn_snapshot("code", code_context)
    _, code_receipt = creative.generate_direct_code_with_receipt(
        code_context,
        code_snapshot,
    )

    assert client.calls_seen == ["generate_hypothesis", "generate_patch"]
    for receipt in (hypothesis_receipt, code_receipt):
        trace = _trace_from_ref(tmp_path, receipt.trace_ref)
        assert trace["request_policy"]["output_token_policy"] == "provider_managed"
        assert trace["request_policy"]["output_token_parameter"] == "omitted"
        assert "max_tokens" not in trace["request_policy"]
        assert "truncation_retries" not in trace["request_policy"]


def test_provider_length_response_typed_failure_has_no_truncation_retry(
    tmp_path: Path,
) -> None:
    client = _DirectOpenAIClient(length_response=True)
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    context = _hypothesis_context()
    snapshot = build_prompt_turn_snapshot("hypothesis", context)

    with pytest.raises(LLMFormatError) as caught:
        creative.generate_direct_hypothesis_with_receipt(context, snapshot)

    assert client.calls_seen == ["generate_hypothesis"]
    receipt = prompt_call_receipt_from_error(caught.value)
    assert receipt is not None
    assert receipt.provider_ok is False
    assert receipt.ok is False
    assert receipt.error_category == "provider_call_failed"
    assert receipt.error_type == "LLMFormatError"
    trace = _trace_from_ref(tmp_path, receipt.trace_ref)
    assert trace["request_policy"]["output_token_policy"] == "provider_managed"
    assert "max_tokens" not in trace["request_policy"]
    assert "truncation_retries" not in trace["request_policy"]
    assert "llm_retry_events" not in trace
    assert "llm_retry_summary" not in trace


def test_consecutive_calls_attach_current_error_receipt_without_shared_stale_state(
    tmp_path: Path,
) -> None:
    client = _CaptureClient()
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    first_context = _hypothesis_context()
    first_snapshot = build_prompt_turn_snapshot("hypothesis", first_context)
    _, first_receipt = creative.generate_direct_hypothesis_with_receipt(
        first_context,
        first_snapshot,
    )

    client.error = LLMProviderError("synthetic provider interruption")
    second_context = {**first_context, "branch_id": "branch-receipt-second"}
    second_snapshot = build_prompt_turn_snapshot("hypothesis", second_context)

    with pytest.raises(LLMProviderError) as caught:
        creative.generate_direct_hypothesis_with_receipt(
            second_context,
            second_snapshot,
        )

    receipt = prompt_call_receipt_from_error(caught.value)
    assert receipt is not None
    trace = _trace_from_ref(tmp_path, receipt.trace_ref)
    assert receipt is not first_receipt
    assert receipt.context_digest != first_receipt.context_digest
    assert receipt.request_kind == "hypothesis"
    assert receipt.context_digest == second_snapshot.context_digest
    assert receipt.ok is False
    assert receipt.provider_ok is False
    assert receipt.error_category == "provider_call_failed"
    assert receipt.error_type == "LLMProviderError"
    assert trace["ok"] is False
    assert trace["prompt_manifest"]["prompt_hash"] == receipt.prompt_hash
    assert trace["error"] == "synthetic provider interruption"


def test_keyboard_interrupt_is_receipted_without_a_second_provider_call(
    tmp_path: Path,
) -> None:
    interruption = KeyboardInterrupt("operator interrupt")
    client = _CaptureClient(error=interruption)
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    raw_context = _hypothesis_context()
    snapshot = build_prompt_turn_snapshot("hypothesis", raw_context)
    authority = snapshot.authoritative_context
    assert authority is not None
    context = authority.inputs.provider_context(include_renderer_inputs=True)

    with pytest.raises(KeyboardInterrupt) as caught:
        creative.generate_direct_hypothesis_with_receipt(
            context,
            snapshot,
            attempt_audit={
                "schema_version": "provider-call-attempt-audit.v1",
                "attempt_id": "attempt-interrupted",
                "phase": "hypothesis",
                "attempt_kind": "initial",
                "continuation_of_attempt_id": None,
                "hypothesis_attempt_id": "attempt-interrupted",
                "started_lineage_event_id": "event-started",
            },
        )

    assert caught.value is interruption
    assert len(client.calls) == 1
    receipt = prompt_call_receipt_from_error(caught.value)
    assert receipt is not None
    assert receipt.attempt_id == "attempt-interrupted"
    assert receipt.attempt_started_event_id == "event-started"
    assert receipt.provider_ok is False
    assert receipt.ok is False
    assert receipt.error_category == "provider_call_interrupted"
    assert receipt.error_type == "KeyboardInterrupt"
    assert receipt.raw_response_ref is None
    trace = _trace_from_ref(tmp_path, receipt.trace_ref)
    assert trace["ok"] is False
    assert trace["error"] == "provider_call_interrupted"


def test_parse_failure_keeps_successful_provider_trace_receipt(
    tmp_path: Path,
) -> None:
    client = _CaptureClient(response={"hypothesis_text": "missing required fields"})
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    context = _hypothesis_context()
    snapshot = build_prompt_turn_snapshot("hypothesis", context)

    with pytest.raises(ProposalValidationError) as caught:
        creative.generate_direct_hypothesis_with_receipt(context, snapshot)

    receipt = prompt_call_receipt_from_error(caught.value)
    assert receipt is not None
    trace = _trace_from_ref(tmp_path, receipt.trace_ref)
    assert receipt.provider_ok is True
    assert receipt.ok is False
    assert receipt.error_category == "response_parse_failed"
    assert receipt.error_type == "ProposalValidationError"
    assert receipt.raw_response_ref == f"{receipt.trace_ref}#/response"
    assert trace["ok"] is True
    assert trace["response"] == {"hypothesis_text": "missing required fields"}
    assert trace["prompt_manifest"]["prompt_hash"] == receipt.prompt_hash


def test_direct_strict_parse_failure_is_terminal_and_receipted(
    tmp_path: Path,
) -> None:
    response = {
        **_HYPOTHESIS_RESPONSE,
        "material_difference": {"raw_trace": "provider-private reasoning"},
    }
    client = _CaptureClient(response=response)
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    context = _hypothesis_context()
    snapshot = build_prompt_turn_snapshot("hypothesis", context)

    with pytest.raises(ProposalValidationError, match="forbidden") as caught:
        creative.generate_direct_hypothesis_with_receipt(context, snapshot)

    receipt = prompt_call_receipt_from_error(caught.value)
    assert len(client.calls) == 1
    assert receipt is not None
    assert receipt.provider_ok is True
    assert receipt.ok is False
    assert receipt.error_category == "response_parse_failed"
    assert receipt.error_type == "ProposalValidationError"
    trace = _trace_from_ref(tmp_path, receipt.trace_ref)
    assert trace["ok"] is True
    assert trace["response"] == response


def test_caller_supplied_context_manifest_is_rejected_before_provider(
    tmp_path: Path,
) -> None:
    client = _CaptureClient()
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    context = {
        **_hypothesis_context(),
        "_scion_prompt_manifest": {
            "artifact_kind": "stale_manifest",
            "prompt_hash": "stale-prompt-hash",
        },
    }
    snapshot = build_prompt_turn_snapshot("hypothesis", context)

    with pytest.raises(ValueError, match="provider context does not match"):
        creative.generate_direct_hypothesis_with_receipt(context, snapshot)

    assert client.calls == []


def test_trace_start_failure_attaches_receipt_without_calling_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start_error = OSError("synthetic trace start failure")

    def fail_start(*_args, **_kwargs):
        raise start_error

    monkeypatch.setattr(provider_call._TraceWriter, "write_start", fail_start)
    client = _CaptureClient()
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    context = _hypothesis_context()
    snapshot = build_prompt_turn_snapshot("hypothesis", context)

    with pytest.raises(OSError) as caught:
        creative.generate_direct_hypothesis_with_receipt(context, snapshot)

    assert caught.value is start_error
    assert client.calls == []
    receipt = prompt_call_receipt_from_error(caught.value)
    assert receipt is not None
    assert receipt.provider_ok is False
    assert receipt.ok is False
    assert receipt.error_category == "trace_start_failed"
    assert receipt.error_type == "OSError"
    assert receipt.trace_persistence_error is None
    assert receipt.trace_ref is None
    assert receipt.prompt_manifest_ref is None
    assert receipt.raw_response_ref is None


def test_provider_failure_is_not_masked_when_trace_finish_also_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_error = LLMProviderError("synthetic provider failure")
    finish_error = PermissionError("synthetic trace finish failure")

    def fail_finish(*_args, **_kwargs):
        raise finish_error

    monkeypatch.setattr(provider_call._TraceWriter, "write_finish", fail_finish)
    client = _CaptureClient(error=provider_error)
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    context = _hypothesis_context()
    snapshot = build_prompt_turn_snapshot("hypothesis", context)

    with pytest.raises(LLMProviderError) as caught:
        creative.generate_direct_hypothesis_with_receipt(context, snapshot)

    assert caught.value is provider_error
    assert len(client.calls) == 1
    receipt = prompt_call_receipt_from_error(caught.value)
    assert receipt is not None
    assert receipt.provider_ok is False
    assert receipt.ok is False
    assert receipt.error_category == "provider_call_failed"
    assert receipt.error_type == "LLMProviderError"
    assert receipt.trace_persistence_error == "trace_finish_failed:PermissionError"
    assert receipt.trace_ref is not None
    assert receipt.prompt_manifest_ref == f"{receipt.trace_ref}#/prompt_manifest"
    assert receipt.raw_response_ref is None
    trace = _trace_from_ref(tmp_path, receipt.trace_ref)
    assert "response" not in trace
    assert "error" not in trace


def test_provider_success_trace_finish_failure_has_no_raw_response_ref(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    finish_error = OSError("synthetic trace finish failure")

    def fail_finish(*_args, **_kwargs):
        raise finish_error

    monkeypatch.setattr(provider_call._TraceWriter, "write_finish", fail_finish)
    client = _CaptureClient()
    creative = CreativeLayer(client, trace_dir=str(tmp_path / "traces"))
    context = _hypothesis_context()
    snapshot = build_prompt_turn_snapshot("hypothesis", context)

    with pytest.raises(OSError) as caught:
        creative.generate_direct_hypothesis_with_receipt(context, snapshot)

    assert caught.value is finish_error
    assert len(client.calls) == 1
    receipt = prompt_call_receipt_from_error(caught.value)
    assert receipt is not None
    assert receipt.provider_ok is True
    assert receipt.ok is False
    assert receipt.error_category == "trace_finish_failed"
    assert receipt.error_type == "OSError"
    assert receipt.trace_persistence_error == "trace_finish_failed:OSError"
    assert receipt.trace_ref is not None
    assert receipt.prompt_manifest_ref == f"{receipt.trace_ref}#/prompt_manifest"
    assert receipt.raw_response_ref is None
    trace = _trace_from_ref(tmp_path, receipt.trace_ref)
    assert "response" not in trace
    assert "error" not in trace
