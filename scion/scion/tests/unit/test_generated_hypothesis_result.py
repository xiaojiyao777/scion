from __future__ import annotations

import contextvars
import copy
import hashlib
import json
import pickle
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import pytest

from scion.lineage import proposal_attempt_owner
from scion.lineage import sqlite_connection as sqlite_boundary
from scion.proposal.engine.facade import build_prompt_turn_snapshot
from scion.proposal.engine import provider_call as subject
from scion.proposal.prompt_manifest import stable_digest

_RESPONSE = {
    "hypothesis_text": "Add one bounded local improvement move.",
    "change_locus": "local_search",
    "action": "create_new",
    "target_file": "operators/bounded_generated_result.py",
    "predicted_direction": "improve",
    "target_weakness": "The current control lacks this bounded move.",
    "expected_effect": "Improve the primary objective when the move applies.",
    "suggested_weight": 1.25,
}


class _DeterministicTransport:
    def __init__(
        self,
        response: dict[str, object] | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self.response = dict(_RESPONSE if response is None else response)
        self.error = error
        self.calls = 0

    def call_with_tool(
        self,
        _prompt: str,
        _tool: dict[str, object],
        _model: str,
        *,
        system_blocks: list[dict[str, object]],
        request_kind: str,
    ) -> dict[str, object]:
        assert system_blocks
        assert request_kind == "hypothesis"
        self.calls += 1
        if self.error is not None:
            raise self.error
        return dict(self.response)


def _context() -> dict[str, object]:
    return {
        "problem_summary": "Synthetic routing control.",
        "research_surfaces": [
            {
                "name": "local_search",
                "kind": "operator",
                "target_files": ["operators/*.py"],
            }
        ],
        "objective_policy_guidance": ("Minimize cost while preserving feasibility."),
        "solver_mechanics": "",
        "champion_operators_code": "class Control: pass",
        "champion_stats": {"version": 3, "operators": []},
        "available_actions": ["create_new"],
        "targetable_files": ["operators/*.py"],
        "experiment_history": [],
        "branch_id": "branch-generated-result",
        "champion_version": 3,
    }


def _started_payload(snapshot: subject.PromptTurnSnapshot) -> dict[str, object]:
    return {
        "schema_version": "proposal-attempt-transition.v1",
        "attempt_id": "attempt-generated-result",
        "campaign_id": "test-campaign",
        "branch_id": "branch-generated-result",
        "runtime_mode": "direct_v3",
        "phase": "hypothesis",
        "status": "started",
        "transition_reason": "provider_call_started",
        "failure_lane": None,
        "hypothesis_id": None,
        "hypothesis_digest": None,
        "patch_digest": None,
        "attempt_kind": "initial",
        "continuation_of_attempt_id": None,
        "prompt_call": {
            "request_kind": "hypothesis",
            "context_digest": snapshot.context_digest,
            "prompt_hash": subject._provider_prompt_hash(
                snapshot.system_blocks,
                snapshot.user_prompt,
            ),
            "trace_ref": None,
            "prompt_manifest_ref": None,
            "raw_response_ref": None,
            "provider_ok": None,
            "ok": None,
            "error_category": None,
            "error_type": None,
        },
        "anchors": {
            "problem_id": "cvrp",
            "problem_spec_hash": "spec-hash",
            "split_manifest_hash": "split-hash",
            "seed_ledger_hash": "seed-hash",
            "champion_version": 3,
            "champion_weight_revision": 0,
            "champion_code_snapshot_hash": "champion-hash",
            "branch_base_champion_id": 3,
            "branch_base_champion_hash": "branch-hash",
        },
        "tainted_artifact_refs": [],
    }


def _issue_started_attempt(
    tmp_path: Path,
    snapshot: subject.PromptTurnSnapshot,
) -> tuple[
    proposal_attempt_owner.StartedHypothesisAttempt,
    sqlite_boundary.CampaignDatabaseAuthority,
]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    database_path = tmp_path / "started-attempt.db"
    connection = sqlite_boundary._connect_sqlite(database_path)
    try:
        connection.execute("""
            CREATE TABLE experiment_events (
                event_id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                branch_id TEXT NOT NULL,
                hypothesis_id TEXT,
                timestamp TEXT NOT NULL,
                event_kind TEXT NOT NULL,
                stage TEXT NOT NULL,
                audit_payload_json TEXT NOT NULL
            )
            """)
        connection.commit()
    finally:
        connection.close()
    authority = sqlite_boundary._issue_test_campaign_database_authority(
        database_path,
        campaign_id="test-campaign",
    )
    owner = proposal_attempt_owner.ProposalAttemptOwner(authority)
    with sqlite_boundary.immediate_transaction(authority) as transaction:
        started = owner.append_started_hypothesis_attempt_in(
            transaction,
            _started_payload(snapshot),
        )
    return started, authority


def _permit(
    tmp_path: Path,
    snapshot: subject.PromptTurnSnapshot,
) -> tuple[
    proposal_attempt_owner.StartedHypothesisAttempt,
    subject.ProviderGenerationPermit,
]:
    started_attempt, authority = _issue_started_attempt(tmp_path, snapshot)
    with sqlite_boundary._independent_authority_read_snapshot(
        authority
    ) as committed_snapshot:
        permit = subject._issue_provider_generation_permit(
            started_attempt=started_attempt,
            committed_snapshot=committed_snapshot,
        )
    return started_attempt, permit


def _issue(
    tmp_path: Path,
    *,
    response: dict[str, object] | None = None,
) -> tuple[
    object,
    subject.PromptTurnSnapshot,
    subject.PromptCallReceipt,
    subject.GeneratedHypothesisResult,
    object,
    subject.ProviderGenerationPermit,
    _DeterministicTransport,
]:
    context = _context()
    snapshot = build_prompt_turn_snapshot("hypothesis", context)
    transport = _DeterministicTransport(response)
    owner = subject.ProviderCallOwner(
        transport,
        "test-model",
        trace_dir=str(tmp_path / "traces"),
    )
    started_attempt, permit = _permit(tmp_path / "started", snapshot)
    hypothesis, receipt, result = subject._generate_hypothesis_result_with_receipt(
        owner,
        context=context,
        snapshot=snapshot,
        permit=permit,
    )
    return (
        hypothesis,
        snapshot,
        receipt,
        result,
        started_attempt,
        permit,
        transport,
    )


def test_real_persisted_provider_and_parse_path_issues_complete_bound_result(
    tmp_path: Path,
) -> None:
    hypothesis, snapshot, receipt, result, started_attempt, permit, transport = _issue(
        tmp_path
    )

    consumed = subject._consume_generated_hypothesis_result(
        result,
        permit=permit,
        started_attempt=started_attempt,
        receipt=receipt,
    )

    assert transport.calls == 1
    assert consumed.attempt_id == "attempt-generated-result"
    assert consumed.started_event_id == receipt.attempt_started_event_id
    assert consumed.started_event_id
    assert consumed.context_digest == snapshot.context_digest
    assert consumed.prompt_hash == receipt.prompt_hash
    assert consumed.receipt is receipt
    assert consumed.trace_ref == receipt.trace_ref
    assert consumed.prompt_manifest_ref == receipt.prompt_manifest_ref
    assert consumed.raw_response_ref == receipt.raw_response_ref
    assert receipt.trace_ref is not None
    persisted_trace = json.loads(
        (tmp_path / receipt.trace_ref.split("#", 1)[0]).read_text(encoding="utf-8")
    )
    assert persisted_trace["ok"] is True
    assert persisted_trace["response"] == _RESPONSE
    assert persisted_trace["prompt_manifest"]["context_digest"] == (
        snapshot.context_digest
    )
    assert (
        consumed.proposal_sha256
        == hashlib.sha256(consumed.proposal_canonical_bytes).hexdigest()
    )
    assert consumed.proposal_sha256 == stable_digest(asdict(hypothesis), length=64)
    assert consumed.detached_hypothesis() == hypothesis
    assert consumed.detached_hypothesis() is not hypothesis


def test_public_proposal_mutation_cannot_change_issued_canonical_result(
    tmp_path: Path,
) -> None:
    hypothesis, _, receipt, result, started_attempt, permit, _ = _issue(tmp_path)
    original_text = hypothesis.hypothesis_text
    hypothesis.hypothesis_text = "caller substituted text"
    hypothesis.target_file = "operators/substituted.py"

    consumed = subject._consume_generated_hypothesis_result(
        result,
        permit=permit,
        started_attempt=started_attempt,
        receipt=receipt,
    )

    detached = consumed.detached_hypothesis()
    assert detached.hypothesis_text == original_text
    assert detached.target_file == _RESPONSE["target_file"]
    assert consumed.proposal_sha256 != stable_digest(asdict(hypothesis), length=64)


def test_result_requires_exact_started_capability_and_receipt_identity(
    tmp_path: Path,
) -> None:
    _, _, receipt, result, started_attempt, permit, _ = _issue(tmp_path)
    equal_but_distinct_receipt = replace(receipt)
    assert equal_but_distinct_receipt == receipt
    assert equal_but_distinct_receipt is not receipt

    with pytest.raises(
        subject.InvalidGeneratedHypothesisResultError,
        match="another started attempt",
    ):
        subject._consume_generated_hypothesis_result(
            result,
            permit=permit,
            started_attempt=object(),
            receipt=receipt,
        )
    with pytest.raises(
        subject.InvalidGeneratedHypothesisResultError,
        match="exact provider receipt",
    ):
        subject._consume_generated_hypothesis_result(
            result,
            permit=permit,
            started_attempt=started_attempt,
            receipt=equal_but_distinct_receipt,
        )

    consumed = subject._consume_generated_hypothesis_result(
        result,
        permit=permit,
        started_attempt=started_attempt,
        receipt=receipt,
    )
    assert consumed.receipt is receipt


def test_permit_reverse_binding_rejects_another_issued_result(
    tmp_path: Path,
) -> None:
    _, _, first_receipt, first_result, first_start, first_permit, _ = _issue(
        tmp_path / "first"
    )
    _, _, _, _, _, second_permit, _ = _issue(tmp_path / "second")

    with pytest.raises(
        subject.InvalidGeneratedHypothesisResultError,
        match="not bound to the exact result",
    ):
        subject._consume_generated_hypothesis_result(
            first_result,
            permit=second_permit,
            started_attempt=first_start,
            receipt=first_receipt,
        )

    assert (
        subject._consume_generated_hypothesis_result(
            first_result,
            permit=first_permit,
            started_attempt=first_start,
            receipt=first_receipt,
        ).receipt
        is first_receipt
    )


def test_result_is_one_shot(
    tmp_path: Path,
) -> None:
    _, _, receipt, result, started_attempt, permit, _ = _issue(tmp_path)
    subject._consume_generated_hypothesis_result(
        result,
        permit=permit,
        started_attempt=started_attempt,
        receipt=receipt,
    )

    with pytest.raises(
        subject.GeneratedHypothesisResultLifecycleError,
        match="already consumed",
    ):
        subject._consume_generated_hypothesis_result(
            result,
            permit=permit,
            started_attempt=started_attempt,
            receipt=receipt,
        )


def test_result_rejects_copied_context_without_being_spent(
    tmp_path: Path,
) -> None:
    _, _, receipt, result, started_attempt, permit, _ = _issue(tmp_path)
    copied_context = contextvars.copy_context()

    with pytest.raises(
        subject.GeneratedHypothesisResultLifecycleError,
        match="cross Contexts",
    ):
        copied_context.run(
            subject._consume_generated_hypothesis_result,
            result,
            permit=permit,
            started_attempt=started_attempt,
            receipt=receipt,
        )

    assert (
        subject._consume_generated_hypothesis_result(
            result,
            permit=permit,
            started_attempt=started_attempt,
            receipt=receipt,
        ).attempt_id
        == "attempt-generated-result"
    )


def test_result_rejects_another_thread_without_being_spent(
    tmp_path: Path,
) -> None:
    _, _, receipt, result, started_attempt, permit, _ = _issue(tmp_path)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            subject._consume_generated_hypothesis_result,
            result,
            permit=permit,
            started_attempt=started_attempt,
            receipt=receipt,
        )
        with pytest.raises(
            subject.GeneratedHypothesisResultLifecycleError,
            match="cross threads",
        ):
            future.result()

    assert (
        subject._consume_generated_hypothesis_result(
            result,
            permit=permit,
            started_attempt=started_attempt,
            receipt=receipt,
        ).attempt_id
        == "attempt-generated-result"
    )


def test_result_cannot_be_constructed_subclassed_copied_or_pickled(
    tmp_path: Path,
) -> None:
    _, _, receipt, result, started_attempt, permit, _ = _issue(tmp_path)

    with pytest.raises(subject.InvalidGeneratedHypothesisResultError):
        subject.GeneratedHypothesisResult()
    with pytest.raises(TypeError, match="sealed"):

        class _Subclass(subject.GeneratedHypothesisResult):
            pass

    with pytest.raises(subject.InvalidGeneratedHypothesisResultError):
        copy.copy(result)
    with pytest.raises(subject.InvalidGeneratedHypothesisResultError):
        copy.deepcopy(result)
    with pytest.raises(subject.InvalidGeneratedHypothesisResultError):
        pickle.dumps(result)

    assert (
        subject._consume_generated_hypothesis_result(
            result,
            permit=permit,
            started_attempt=started_attempt,
            receipt=receipt,
        ).receipt
        is receipt
    )


def test_provider_generation_permit_is_sealed_and_non_transferable(
    tmp_path: Path,
) -> None:
    context = _context()
    snapshot = build_prompt_turn_snapshot("hypothesis", context)
    transport = _DeterministicTransport()
    owner = subject.ProviderCallOwner(
        transport,
        "test-model",
        trace_dir=str(tmp_path / "traces"),
    )
    started_attempt, permit = _permit(tmp_path / "started", snapshot)

    with pytest.raises(subject.InvalidGeneratedHypothesisResultError):
        subject.ProviderGenerationPermit()
    with pytest.raises(TypeError, match="sealed"):

        class _PermitSubclass(subject.ProviderGenerationPermit):
            pass

    with pytest.raises(subject.InvalidGeneratedHypothesisResultError):
        copy.copy(permit)
    with pytest.raises(subject.InvalidGeneratedHypothesisResultError):
        copy.deepcopy(permit)
    with pytest.raises(subject.InvalidGeneratedHypothesisResultError):
        pickle.dumps(permit)

    subject._generate_hypothesis_result_with_receipt(
        owner,
        context=context,
        snapshot=snapshot,
        permit=permit,
    )
    assert transport.calls == 1


def test_forged_cross_context_and_cross_thread_permits_fail_before_transport(
    tmp_path: Path,
) -> None:
    context = _context()
    snapshot = build_prompt_turn_snapshot("hypothesis", context)
    transport = _DeterministicTransport()
    owner = subject.ProviderCallOwner(
        transport,
        "test-model",
        trace_dir=str(tmp_path / "traces"),
    )
    forged = object.__new__(subject.ProviderGenerationPermit)
    with pytest.raises(
        subject.InvalidGeneratedHypothesisResultError,
        match="was not issued",
    ):
        subject._generate_hypothesis_result_with_receipt(
            owner,
            context=context,
            snapshot=snapshot,
            permit=forged,
        )
    assert transport.calls == 0

    _, context_permit = _permit(tmp_path / "context-started", snapshot)
    copied_context = contextvars.copy_context()
    with pytest.raises(
        subject.GeneratedHypothesisResultLifecycleError,
        match="cross Contexts",
    ):
        copied_context.run(
            subject._generate_hypothesis_result_with_receipt,
            owner,
            context=context,
            snapshot=snapshot,
            permit=context_permit,
        )
    assert transport.calls == 0
    subject._generate_hypothesis_result_with_receipt(
        owner,
        context=context,
        snapshot=snapshot,
        permit=context_permit,
    )
    assert transport.calls == 1

    _, thread_permit = _permit(tmp_path / "thread-started", snapshot)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            subject._generate_hypothesis_result_with_receipt,
            owner,
            context=context,
            snapshot=snapshot,
            permit=thread_permit,
        )
        with pytest.raises(
            subject.GeneratedHypothesisResultLifecycleError,
            match="cross threads",
        ):
            future.result()
    assert transport.calls == 1
    subject._generate_hypothesis_result_with_receipt(
        owner,
        context=context,
        snapshot=snapshot,
        permit=thread_permit,
    )
    assert transport.calls == 2


def test_result_bound_permit_cannot_call_transport_twice(
    tmp_path: Path,
) -> None:
    context = _context()
    snapshot = build_prompt_turn_snapshot("hypothesis", context)
    transport = _DeterministicTransport()
    owner = subject.ProviderCallOwner(
        transport,
        "test-model",
        trace_dir=str(tmp_path / "traces"),
    )
    _, permit = _permit(tmp_path / "started", snapshot)
    subject._generate_hypothesis_result_with_receipt(
        owner,
        context=context,
        snapshot=snapshot,
        permit=permit,
    )

    with pytest.raises(
        subject.GeneratedHypothesisResultLifecycleError,
        match="already bound",
    ):
        subject._generate_hypothesis_result_with_receipt(
            owner,
            context=context,
            snapshot=snapshot,
            permit=permit,
        )
    assert transport.calls == 1


@pytest.mark.parametrize("failure_kind", ["provider", "parse", "persistence"])
def test_start_bound_permit_cannot_retry_after_any_call_failure(
    tmp_path: Path,
    failure_kind: str,
) -> None:
    context = _context()
    snapshot = build_prompt_turn_snapshot("hypothesis", context)
    response = (
        {**_RESPONSE, "change_locus": "unknown"} if failure_kind == "parse" else None
    )
    transport = _DeterministicTransport(
        response,
        error=(RuntimeError("provider failed") if failure_kind == "provider" else None),
    )
    owner = subject.ProviderCallOwner(
        transport,
        "test-model",
        trace_dir=(
            None
            if failure_kind == "persistence"
            else str(tmp_path / f"traces-{failure_kind}")
        ),
    )
    _, permit = _permit(tmp_path / "started", snapshot)

    with pytest.raises(Exception):
        subject._generate_hypothesis_result_with_receipt(
            owner,
            context=context,
            snapshot=snapshot,
            permit=permit,
        )
    assert transport.calls == 1

    transport.error = None
    transport.response = dict(_RESPONSE)
    with pytest.raises(
        subject.GeneratedHypothesisResultLifecycleError,
        match="already bound",
    ):
        subject._generate_hypothesis_result_with_receipt(
            owner,
            context=context,
            snapshot=snapshot,
            permit=permit,
        )
    assert transport.calls == 1


def test_forged_and_same_shaped_values_are_not_results(
    tmp_path: Path,
) -> None:
    _, _, receipt, _, started_attempt, permit, _ = _issue(tmp_path)
    forged = object.__new__(subject.GeneratedHypothesisResult)

    @dataclass
    class _SameShape:
        attempt_id: str
        started_event_id: str
        context_digest: str
        prompt_hash: str

    same_shape = _SameShape(
        attempt_id="attempt-generated-result",
        started_event_id="event-started-generated-result",
        context_digest=receipt.context_digest,
        prompt_hash=receipt.prompt_hash,
    )

    with pytest.raises(
        subject.InvalidGeneratedHypothesisResultError,
        match="not bound to the exact result",
    ):
        subject._consume_generated_hypothesis_result(
            forged,
            permit=permit,
            started_attempt=started_attempt,
            receipt=receipt,
        )
    with pytest.raises(
        subject.InvalidGeneratedHypothesisResultError,
        match="exact GeneratedHypothesisResult",
    ):
        subject._consume_generated_hypothesis_result(
            same_shape,  # type: ignore[arg-type]
            permit=permit,
            started_attempt=started_attempt,
            receipt=receipt,
        )


def test_dormant_path_requires_real_durable_refs_after_provider_success(
    tmp_path: Path,
) -> None:
    context = _context()
    snapshot = build_prompt_turn_snapshot("hypothesis", context)
    transport = _DeterministicTransport()
    owner = subject.ProviderCallOwner(
        transport,
        "test-model",
        trace_dir=None,
    )
    _, permit = _permit(tmp_path / "started", snapshot)

    with pytest.raises(
        subject.InvalidGeneratedHypothesisResultError,
        match="durable trace ref",
    ) as caught:
        subject._generate_hypothesis_result_with_receipt(
            owner,
            context=context,
            snapshot=snapshot,
            permit=permit,
        )

    receipt = subject.prompt_call_receipt_from_error(caught.value)
    assert transport.calls == 1
    assert receipt is not None
    assert receipt.provider_ok is True
    assert receipt.ok is False
    assert receipt.error_category == "generated_result_issuance_failed"


def test_incomplete_persisted_trace_cannot_issue_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _context()
    snapshot = build_prompt_turn_snapshot("hypothesis", context)
    transport = _DeterministicTransport()
    owner = subject.ProviderCallOwner(
        transport,
        "test-model",
        trace_dir=str(tmp_path / "traces"),
    )

    def _incomplete_finish(
        _writer: object,
        path: str | None,
        **_kwargs: object,
    ) -> None:
        assert path is not None
        Path(path).write_text('{"ok": true}\n', encoding="utf-8")

    monkeypatch.setattr(subject._TraceWriter, "write_finish", _incomplete_finish)
    _, permit = _permit(tmp_path / "started", snapshot)
    with pytest.raises(
        subject.InvalidGeneratedHypothesisResultError,
        match="prompt manifest was not persisted",
    ) as caught:
        subject._generate_hypothesis_result_with_receipt(
            owner,
            context=context,
            snapshot=snapshot,
            permit=permit,
        )

    receipt = subject.prompt_call_receipt_from_error(caught.value)
    assert transport.calls == 1
    assert receipt is not None
    assert receipt.error_category == "generated_result_issuance_failed"


def test_partial_prompt_manifest_replacement_cannot_issue_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _context()
    snapshot = build_prompt_turn_snapshot("hypothesis", context)
    transport = _DeterministicTransport()
    owner = subject.ProviderCallOwner(
        transport,
        "test-model",
        trace_dir=str(tmp_path / "traces"),
    )
    original_finish = subject._TraceWriter.write_finish

    def _partial_manifest_finish(
        writer: object,
        path: str | None,
        **kwargs: object,
    ) -> None:
        original_finish(writer, path, **kwargs)  # type: ignore[arg-type]
        assert path is not None
        trace_path = Path(path)
        persisted = json.loads(trace_path.read_text(encoding="utf-8"))
        manifest = persisted["prompt_manifest"]
        persisted["prompt_manifest"] = {
            "session_id": manifest["session_id"],
            "context_digest": manifest["context_digest"],
            "prompt_hash": manifest["prompt_hash"],
        }
        trace_path.write_text(json.dumps(persisted), encoding="utf-8")

    monkeypatch.setattr(
        subject._TraceWriter,
        "write_finish",
        _partial_manifest_finish,
    )
    _, permit = _permit(tmp_path / "started", snapshot)
    with pytest.raises(
        subject.InvalidGeneratedHypothesisResultError,
        match="trace, manifest, or raw response is incomplete",
    ):
        subject._generate_hypothesis_result_with_receipt(
            owner,
            context=context,
            snapshot=snapshot,
            permit=permit,
        )
    assert transport.calls == 1


def test_prompt_manifest_session_identity_replacement_cannot_issue_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _context()
    snapshot = build_prompt_turn_snapshot("hypothesis", context)
    transport = _DeterministicTransport()
    owner = subject.ProviderCallOwner(
        transport,
        "test-model",
        trace_dir=str(tmp_path / "traces"),
    )
    original_finish = subject._TraceWriter.write_finish

    def _replaced_session_finish(
        writer: object,
        path: str | None,
        **kwargs: object,
    ) -> None:
        original_finish(writer, path, **kwargs)  # type: ignore[arg-type]
        assert path is not None
        trace_path = Path(path)
        persisted = json.loads(trace_path.read_text(encoding="utf-8"))
        persisted["prompt_manifest"]["session_id"] = "forged-session-id"
        trace_path.write_text(json.dumps(persisted), encoding="utf-8")

    monkeypatch.setattr(
        subject._TraceWriter,
        "write_finish",
        _replaced_session_finish,
    )
    _, permit = _permit(tmp_path / "started", snapshot)
    with pytest.raises(
        subject.InvalidGeneratedHypothesisResultError,
        match="trace, manifest, or raw response is incomplete",
    ):
        subject._generate_hypothesis_result_with_receipt(
            owner,
            context=context,
            snapshot=snapshot,
            permit=permit,
        )
    assert transport.calls == 1


def test_parse_failure_never_issues_a_result_and_keeps_failure_receipt(
    tmp_path: Path,
) -> None:
    context = _context()
    snapshot = build_prompt_turn_snapshot("hypothesis", context)
    transport = _DeterministicTransport({**_RESPONSE, "change_locus": "unknown"})
    owner = subject.ProviderCallOwner(
        transport,
        "test-model",
        trace_dir=str(tmp_path / "traces"),
    )
    _, permit = _permit(tmp_path / "started", snapshot)

    with pytest.raises(Exception) as caught:
        subject._generate_hypothesis_result_with_receipt(
            owner,
            context=context,
            snapshot=snapshot,
            permit=permit,
        )

    receipt = subject.prompt_call_receipt_from_error(caught.value)
    assert transport.calls == 1
    assert receipt is not None
    assert receipt.provider_ok is True
    assert receipt.ok is False
    assert receipt.error_category == "response_parse_failed"


def test_forged_start_and_persisted_prompt_mismatch_fail_before_transport(
    tmp_path: Path,
) -> None:
    context = _context()
    snapshot = build_prompt_turn_snapshot("hypothesis", context)
    transport = _DeterministicTransport()
    owner = subject.ProviderCallOwner(
        transport,
        "test-model",
        trace_dir=str(tmp_path / "traces"),
    )
    with pytest.raises(
        proposal_attempt_owner.InvalidStartedHypothesisAttemptError,
        match="exact StartedHypothesisAttempt",
    ):
        subject._issue_provider_generation_permit(
            started_attempt=object(),  # type: ignore[arg-type]
            committed_snapshot=object(),  # type: ignore[arg-type]
        )
    assert transport.calls == 0

    _, permit = _permit(tmp_path / "started", snapshot)
    changed_context = _context()
    changed_context["problem_summary"] = "A different persisted prompt input."
    changed_snapshot = build_prompt_turn_snapshot("hypothesis", changed_context)
    with pytest.raises(
        subject.InvalidGeneratedHypothesisResultError,
        match="does not match the persisted START",
    ):
        subject._generate_hypothesis_result_with_receipt(
            owner,
            context=changed_context,
            snapshot=changed_snapshot,
            permit=permit,
        )

    assert transport.calls == 0
