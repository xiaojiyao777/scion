from __future__ import annotations

import copy
import json

import pytest

from scion.core.proposal_pipeline.attempts import ProposalAttemptRecorder


class _MemoryRegistry:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def record_event(self, event: dict) -> str:
        self.events.append(dict(event))
        return str(event["event_id"])


def _generated_hypothesis_payload() -> dict:
    trace_ref = "artifacts/llm_traces/hypothesis.json"
    return {
        "schema_version": "proposal-attempt-transition.v1",
        "attempt_id": "attempt-1",
        "campaign_id": "campaign-1",
        "branch_id": "branch-1",
        "runtime_mode": "direct_v3",
        "phase": "hypothesis",
        "status": "generated",
        "transition_reason": "generated",
        "failure_lane": None,
        "hypothesis_id": "hypothesis-1",
        "hypothesis_digest": "hypothesis-digest",
        "patch_digest": None,
        "prompt_call": {
            "request_kind": "hypothesis",
            "context_digest": "context-digest",
            "prompt_hash": "prompt-hash",
            "trace_ref": trace_ref,
            "prompt_manifest_ref": f"{trace_ref}#/prompt_manifest",
            "raw_response_ref": f"{trace_ref}#/response",
            "provider_ok": True,
            "ok": True,
            "error_category": None,
            "error_type": None,
        },
        "anchors": {
            "problem_id": "cvrp",
            "problem_spec_hash": "spec-hash",
            "split_manifest_hash": "split-hash",
            "seed_ledger_hash": "seed-hash",
            "champion_version": 1,
            "champion_weight_revision": 0,
            "champion_code_snapshot_hash": "champion-hash",
            "branch_base_champion_id": 1,
            "branch_base_champion_hash": "branch-hash",
        },
        "tainted_artifact_refs": [
            trace_ref,
            f"{trace_ref}#/prompt_manifest",
            f"{trace_ref}#/response",
        ],
    }


def _started_hypothesis_payload() -> dict:
    payload = _generated_hypothesis_payload()
    payload.update(
        status="started",
        transition_reason="provider_call_started",
        hypothesis_id=None,
        hypothesis_digest=None,
        tainted_artifact_refs=[],
    )
    payload["prompt_call"].update(
        trace_ref=None,
        prompt_manifest_ref=None,
        raw_response_ref=None,
        provider_ok=None,
        ok=None,
    )
    return payload


def _record(payload: dict) -> tuple[_MemoryRegistry, str]:
    registry = _MemoryRegistry()
    event_id = ProposalAttemptRecorder(registry).record_transition(payload)
    return registry, event_id


def test_exact_schema_accepts_compact_generated_transition() -> None:
    payload = _generated_hypothesis_payload()

    registry, event_id = _record(payload)

    assert registry.events[0]["event_id"] == event_id
    assert json.loads(registry.events[0]["audit_payload_json"]) == payload


def test_exact_schema_accepts_compact_started_transition() -> None:
    payload = _started_hypothesis_payload()

    registry, event_id = _record(payload)

    assert registry.events[0]["event_id"] == event_id
    assert json.loads(registry.events[0]["audit_payload_json"]) == payload


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda payload: payload.update(transition_reason="generated"),
            "requires provider_call_started reason",
        ),
        (
            lambda payload: payload["prompt_call"].update(provider_ok=True),
            "cannot claim provider outcome",
        ),
        (
            lambda payload: payload["prompt_call"].update(
                error_category="provider_call_failed"
            ),
            "cannot contain provider error",
        ),
        (
            lambda payload: payload["prompt_call"].update(
                trace_ref="artifacts/llm_traces/premature.json"
            ),
            "cannot contain completed prompt refs",
        ),
        (
            lambda payload: payload.update(patch_digest="premature"),
            "cannot contain patch_digest",
        ),
        (
            lambda payload: payload.update(
                tainted_artifact_refs=["artifacts/llm_traces/premature.json"]
            ),
            "cannot contain artifact refs",
        ),
        (
            lambda payload: payload.update(hypothesis_id="premature"),
            "cannot claim model output identity",
        ),
    ],
)
def test_started_transition_cannot_claim_terminal_outcome(
    mutation,
    message: str,
) -> None:
    payload = _started_hypothesis_payload()
    mutation(payload)

    with pytest.raises(ValueError, match=message):
        _record(payload)


def test_started_code_requires_bound_hypothesis_and_continuation() -> None:
    payload = _started_hypothesis_payload()
    payload.update(
        attempt_id="attempt-code-1",
        attempt_kind="approved_code_continuation",
        continuation_of_attempt_id="attempt-hypothesis-1",
        phase="code",
        hypothesis_id="hypothesis-1",
        hypothesis_digest="hypothesis-digest",
    )
    payload["prompt_call"]["request_kind"] = "code"

    registry, _ = _record(payload)
    stored = json.loads(registry.events[0]["audit_payload_json"])
    assert stored["hypothesis_id"] == "hypothesis-1"
    assert stored["continuation_of_attempt_id"] == "attempt-hypothesis-1"

    payload["hypothesis_digest"] = None
    with pytest.raises(ValueError, match="requires approved hypothesis identity"):
        _record(payload)


def test_exact_schema_rejects_unknown_and_body_fields() -> None:
    payload = _generated_hypothesis_payload()
    payload["planner_state"] = {"retry": 1}
    with pytest.raises(ValueError, match="unsupported fields: planner_state"):
        _record(payload)

    payload = _generated_hypothesis_payload()
    payload["hypothesis_text"] = "must stay in the hypothesis owner"
    with pytest.raises(ValueError, match="forbidden payload field: hypothesis_text"):
        _record(payload)

    payload = _generated_hypothesis_payload()
    payload["anchors"]["source_manifest"] = {"full": "body"}
    with pytest.raises(ValueError, match="anchors contain unsupported fields"):
        _record(payload)

    payload = _generated_hypothesis_payload()
    payload["prompt_call"]["raw_response"] = {"full": "body"}
    with pytest.raises(ValueError, match="prompt_call contains unsupported fields"):
        _record(payload)


@pytest.mark.parametrize(
    "anchor_value",
    [
        {"nested": "mapping"},
        ["nested", "list"],
        float("nan"),
        float("inf"),
    ],
)
def test_anchors_accept_only_finite_json_scalars(anchor_value: object) -> None:
    payload = _generated_hypothesis_payload()
    payload["anchors"]["problem_id"] = anchor_value

    with pytest.raises(ValueError, match="anchors must be JSON scalars: problem_id"):
        _record(payload)


@pytest.mark.parametrize(
    "unsafe_ref",
    [
        "/home/clawd/trace.json",
        "file:///home/clawd/trace.json",
        "artifacts/../private/trace.json",
        "trace stored at /home/clawd/trace.json",
        r"C:\Users\clawd\trace.json",
        r"\\server\share\trace.json",
    ],
)
def test_prompt_refs_reject_private_or_traversing_paths(unsafe_ref: str) -> None:
    payload = _generated_hypothesis_payload()
    payload["prompt_call"]["trace_ref"] = unsafe_ref

    with pytest.raises(ValueError, match="proposal attempt trace_ref cannot contain"):
        _record(payload)


def test_tainted_refs_use_the_same_public_ref_boundary() -> None:
    payload = _generated_hypothesis_payload()
    payload["tainted_artifact_refs"] = ["artifacts/../private/raw.json"]

    with pytest.raises(
        ValueError,
        match="tainted_artifact_refs cannot contain parent traversal",
    ):
        _record(payload)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("provider_ok", False, "successful prompt_call"),
        ("ok", False, "successful prompt_call"),
        ("trace_ref", None, "missing durable prompt refs"),
        ("prompt_manifest_ref", "", "missing durable prompt refs"),
        ("raw_response_ref", None, "missing durable prompt refs"),
    ],
)
def test_generated_transition_requires_successful_durable_prompt_call(
    field: str,
    value: object,
    message: str,
) -> None:
    payload = _generated_hypothesis_payload()
    payload["prompt_call"][field] = value

    with pytest.raises(ValueError, match=message):
        _record(payload)


def test_failed_trace_start_can_commit_without_artifact_refs() -> None:
    payload = _generated_hypothesis_payload()
    payload.update(
        status="failed",
        transition_reason="trace_persistence_failed",
        failure_lane="infra",
        hypothesis_id=None,
        hypothesis_digest=None,
        trace_persistence_error={"stage": "start", "error_type": "OSError"},
        tainted_artifact_refs=[],
    )
    payload["prompt_call"].update(
        trace_ref=None,
        prompt_manifest_ref=None,
        raw_response_ref=None,
        provider_ok=False,
        ok=False,
        error_category="trace_persistence_failed",
        error_type="OSError",
    )

    registry, _ = _record(payload)

    stored = json.loads(registry.events[0]["audit_payload_json"])
    assert stored["trace_persistence_error"] == {
        "stage": "start",
        "error_type": "OSError",
    }
    assert stored["tainted_artifact_refs"] == []


def test_failed_problem_quality_transition_may_reference_successful_call() -> None:
    payload = _generated_hypothesis_payload()
    payload.update(
        status="failed",
        transition_reason="problem_hypothesis_quality_rejected",
        failure_lane="invalid_response",
    )

    registry, _ = _record(payload)

    stored = json.loads(registry.events[0]["audit_payload_json"])
    assert stored["status"] == "failed"
    assert stored["prompt_call"]["ok"] is True


def test_direct_writer_rejects_legacy_proposal_repair_lane() -> None:
    payload = _generated_hypothesis_payload()
    payload.update(
        status="failed",
        transition_reason="response_parse_failed",
        failure_lane="proposal_repair",
    )

    with pytest.raises(ValueError, match="invalid proposal attempt failure_lane"):
        _record(payload)


def test_trace_persistence_error_is_small_and_failed_only() -> None:
    payload = _generated_hypothesis_payload()
    payload["trace_persistence_error"] = {
        "stage": "finish",
        "error_type": "OSError",
    }
    with pytest.raises(ValueError, match="only valid for failed transitions"):
        _record(payload)

    payload.update(status="failed", failure_lane="infra")
    payload["trace_persistence_error"]["detail"] = "do not copy exception bodies"
    with pytest.raises(ValueError, match="contains unsupported fields: detail"):
        _record(payload)


def test_code_continuation_fields_are_explicit_and_compact() -> None:
    payload = _generated_hypothesis_payload()
    payload.update(
        attempt_id="attempt-2",
        attempt_kind="approved_code_continuation",
        continuation_of_attempt_id="attempt-1",
        phase="code",
        patch_digest="patch-digest",
    )
    payload["prompt_call"]["request_kind"] = "code"

    registry, _ = _record(payload)

    stored = json.loads(registry.events[0]["audit_payload_json"])
    assert stored["attempt_kind"] == "approved_code_continuation"
    assert stored["continuation_of_attempt_id"] == "attempt-1"


@pytest.mark.parametrize(
    ("attempt_kind", "continuation_id", "phase", "message"),
    [
        ("unknown", None, "hypothesis", "invalid proposal attempt_kind"),
        (
            "approved_code_continuation",
            None,
            "code",
            "requires continuation_of_attempt_id",
        ),
        (
            "initial",
            "attempt-0",
            "code",
            "requires approved_code_continuation",
        ),
        (
            "approved_code_continuation",
            "attempt-0",
            "hypothesis",
            "only valid for code phase",
        ),
        (
            "approved_code_continuation",
            "attempt-1",
            "code",
            "cannot reference its own attempt_id",
        ),
    ],
)
def test_invalid_continuation_shapes_are_rejected(
    attempt_kind: str,
    continuation_id: str | None,
    phase: str,
    message: str,
) -> None:
    payload = _generated_hypothesis_payload()
    payload["attempt_kind"] = attempt_kind
    if continuation_id is not None:
        payload["continuation_of_attempt_id"] = continuation_id
    payload["phase"] = phase
    payload["prompt_call"]["request_kind"] = phase
    if phase == "code":
        payload["patch_digest"] = "patch-digest"

    with pytest.raises(ValueError, match=message):
        _record(payload)


def test_phase_specific_patch_digest_rules_are_strict() -> None:
    payload = _generated_hypothesis_payload()
    payload["patch_digest"] = ""
    with pytest.raises(ValueError, match="hypothesis transition cannot contain"):
        _record(payload)

    payload = _generated_hypothesis_payload()
    payload["phase"] = "code"
    payload["prompt_call"]["request_kind"] = "code"
    with pytest.raises(ValueError, match="generated code transition requires"):
        _record(payload)


def test_payload_input_is_not_mutated() -> None:
    payload = _generated_hypothesis_payload()
    original = copy.deepcopy(payload)

    _record(payload)

    assert payload == original
