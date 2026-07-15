"""Single owner for direct proposal-attempt state and durable transitions."""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from scion.core.evidence_recording.replay_identity import stable_patch_digest
from scion.core.execution_outcome import (
    ExecutionOutcome,
    ExecutionOutcomeRecord,
    install_branch_execution_hold,
    record_execution_outcome_event,
)
from scion.core.models import (
    Branch,
    ChampionState,
    FailureEvent,
    HypothesisProposal,
    PatchProposal,
)
from scion.proposal.engine import (
    PromptCallReceipt,
    PromptTurnSnapshot,
    prompt_call_receipt_from_error,
)
from scion.proposal.llm_client import is_llm_infra_error
from scion.proposal.prompt_manifest import stable_digest
from scion.proposal.prompt_manifest_accounting import _provider_prompt_hash

from .attempts import ProposalAttemptRecorder


@dataclass
class DirectAttemptState:
    """All branch-local mutable state for the direct attempt lifecycle."""

    prompt_call_receipts: dict[str, dict[str, PromptCallReceipt]] = field(
        default_factory=dict
    )
    attempt_ids: dict[str, str] = field(default_factory=dict)
    attempt_phases: dict[str, str] = field(default_factory=dict)
    attempt_kinds: dict[str, str] = field(default_factory=dict)
    continuation_ids: dict[str, str] = field(default_factory=dict)
    started_event_ids: dict[str, str] = field(default_factory=dict)
    started_prompt_calls: dict[str, Mapping[str, Any]] = field(default_factory=dict)
    hypothesis_ids: dict[str, str] = field(default_factory=dict)
    attempt_refs: dict[str, Mapping[str, Any]] = field(default_factory=dict)
    attempt_refs_by_id: dict[str, Mapping[str, Any]] = field(default_factory=dict)
    phase_attempt_refs: dict[str, dict[str, Mapping[str, Any]]] = field(
        default_factory=dict
    )
    approved_hypothesis_bindings: dict[str, Mapping[str, Any]] = field(
        default_factory=dict
    )
    execution_outcomes: dict[str, ExecutionOutcomeRecord] = field(
        default_factory=dict
    )


class DirectAttemptLifecycle:
    """Own direct attempt identity, binding, persistence, and failure routing."""

    def __init__(self, owner: Any) -> None:
        self.owner = owner
        self.state = DirectAttemptState()

    @staticmethod
    def hypothesis_digest(hypothesis: HypothesisProposal) -> str:
        return stable_digest(asdict(hypothesis), length=64)

    @staticmethod
    def failure_reason(
        error: BaseException,
        receipt: PromptCallReceipt | None,
    ) -> str:
        if receipt is not None and receipt.error_category:
            return receipt.error_category
        if is_llm_infra_error(error):
            return "provider_call_failed"
        return "proposal_response_invalid"

    def record_receipt(
        self,
        branch_id: str,
        phase: str,
        receipt: PromptCallReceipt | None,
    ) -> None:
        if receipt is not None:
            self.state.prompt_call_receipts.setdefault(branch_id, {})[phase] = receipt

    def clear_receipt(self, branch_id: str, phase: str) -> None:
        branch_receipts = self.state.prompt_call_receipts.get(branch_id)
        if not branch_receipts:
            return
        branch_receipts.pop(phase, None)
        if not branch_receipts:
            self.state.prompt_call_receipts.pop(branch_id, None)

    def clear_execution_outcome(self, branch_id: str) -> None:
        self.state.execution_outcomes.pop(branch_id, None)

    def pop_execution_outcome(
        self,
        branch_id: str,
    ) -> ExecutionOutcomeRecord | None:
        return self.state.execution_outcomes.pop(branch_id, None)

    def record_execution_outcome(
        self,
        branch: Branch,
        *,
        phase: str,
        outcome: ExecutionOutcome,
        reason_code: str,
        detail: str,
        error_type: str | None = None,
        error_category: str | None = None,
        provenance: Mapping[str, Any] | None = None,
    ) -> ExecutionOutcomeRecord:
        resolved_provenance = {
            "owner": "direct_proposal_provider",
            "stage": phase if phase == "proposal" else f"proposal_{phase}",
            "phase": phase,
        }
        if error_type:
            resolved_provenance["error_type"] = error_type
        if error_category:
            resolved_provenance["error_category"] = error_category
        resolved_provenance.update(dict(provenance or {}))
        record = ExecutionOutcomeRecord(
            outcome=outcome,
            reason_code=reason_code,
            detail=str(detail or ""),
            provenance=resolved_provenance,
        )
        self.state.execution_outcomes[branch.branch_id] = record
        return record

    def start_provider_call(
        self,
        *,
        branch: Branch,
        champion: ChampionState,
        phase: str,
        snapshot: PromptTurnSnapshot,
    ) -> Mapping[str, Any] | None:
        """Persist one provider-call start before any SDK invocation."""

        owner = self.owner
        state = self.state
        bid = branch.branch_id
        self.clear_execution_outcome(bid)
        if owner.lineage_registry is None:
            self._fail_lineage_write(
                branch,
                "proposal_attempt_started_lineage_unavailable",
            )
            return None

        if phase == "hypothesis":
            attempt_kind = "initial"
            continuation_of_attempt_id = None
            hypothesis_id = None
            hypothesis_digest = None
            state.approved_hypothesis_bindings.pop(bid, None)
        elif phase == "code":
            binding = state.approved_hypothesis_bindings.get(bid)
            if not isinstance(binding, Mapping):
                self.fail_integrity(
                    branch,
                    "approved_hypothesis_binding_missing_for_direct_code",
                    clear_approved_binding=True,
                )
                return None
            attempt_kind = "approved_code_continuation"
            continuation_of_attempt_id = str(binding.get("last_attempt_id") or "")
            hypothesis_id = str(binding.get("hypothesis_id") or "")
            hypothesis_digest = str(binding.get("hypothesis_digest") or "")
            if not continuation_of_attempt_id or not hypothesis_id or not hypothesis_digest:
                self.fail_integrity(
                    branch,
                    "approved_hypothesis_attempt_lineage_missing_for_direct_code",
                    clear_approved_binding=False,
                )
                return None
        else:
            raise ValueError(f"unsupported direct provider phase: {phase}")

        attempt_id = str(uuid.uuid4())
        state.attempt_ids[bid] = attempt_id
        state.attempt_phases[bid] = phase
        state.attempt_kinds[bid] = attempt_kind
        if continuation_of_attempt_id is None:
            state.continuation_ids.pop(bid, None)
        else:
            state.continuation_ids[bid] = continuation_of_attempt_id
        if hypothesis_id is None:
            state.hypothesis_ids.pop(bid, None)
        else:
            state.hypothesis_ids[bid] = hypothesis_id
        state.attempt_refs.pop(bid, None)
        self.clear_receipt(bid, phase)

        prompt_hash = _provider_prompt_hash(
            snapshot.system_blocks,
            snapshot.user_prompt,
        )
        payload = self._transition_payload(
            branch=branch,
            champion=champion,
            phase=phase,
            status="started",
            transition_reason="provider_call_started",
            failure_lane=None,
            hypothesis=None,
            patch=None,
            hypothesis_id=hypothesis_id,
            bound_hypothesis_digest=hypothesis_digest,
            prompt_call={
                "request_kind": phase,
                "context_digest": snapshot.context_digest,
                "prompt_hash": prompt_hash,
                "trace_ref": None,
                "prompt_manifest_ref": None,
                "raw_response_ref": None,
                "provider_ok": None,
                "ok": None,
                "error_category": None,
                "error_type": None,
            },
        )
        try:
            event_id = ProposalAttemptRecorder(owner.lineage_registry).record_transition(
                payload
            )
        except Exception as exc:
            self._fail_lineage_write(
                branch,
                f"proposal_attempt_started_lineage_write_failed:{type(exc).__name__}",
            )
            return None
        state.started_event_ids[bid] = event_id
        state.started_prompt_calls[bid] = dict(payload["prompt_call"])
        started_ref = _proposal_attempt_ref(payload, event_id=event_id)
        state.attempt_refs_by_id[attempt_id] = started_ref
        state.phase_attempt_refs.setdefault(bid, {})[phase] = started_ref
        if phase == "code":
            binding = state.approved_hypothesis_bindings.get(bid)
            if isinstance(binding, Mapping):
                state.approved_hypothesis_bindings[bid] = {
                    **dict(binding),
                    "last_attempt_id": attempt_id,
                }
        return {
            "schema_version": "provider-call-attempt-audit.v1",
            "attempt_id": attempt_id,
            "phase": phase,
            "attempt_kind": attempt_kind,
            "continuation_of_attempt_id": continuation_of_attempt_id,
            "hypothesis_attempt_id": (
                str(
                    state.approved_hypothesis_bindings.get(bid, {}).get(
                        "hypothesis_attempt_id"
                    )
                    or ""
                )
                if phase == "code"
                else attempt_id
            ),
            "started_lineage_event_id": event_id,
        }

    def bind_approved_hypothesis(
        self,
        branch_id: str,
        *,
        hypothesis_id: str,
        hypothesis_digest: str,
        hypothesis: HypothesisProposal | None = None,
    ) -> None:
        hypothesis_attempt_id = self.state.attempt_ids[branch_id]
        self.state.hypothesis_ids[branch_id] = hypothesis_id
        self.state.approved_hypothesis_bindings[branch_id] = {
            "hypothesis_id": hypothesis_id,
            "hypothesis_digest": hypothesis_digest,
            "hypothesis_attempt_id": hypothesis_attempt_id,
            "last_attempt_id": hypothesis_attempt_id,
            "proposal_fingerprint": _hypothesis_proposal_fingerprint(hypothesis),
        }

    def discard_approved_binding(self, branch_id: str) -> None:
        self.state.approved_hypothesis_bindings.pop(branch_id, None)

    def commit(
        self,
        *,
        branch: Branch,
        champion: ChampionState,
        phase: str,
        status: str,
        transition_reason: str,
        failure_lane: str | None,
        hypothesis: HypothesisProposal | None,
        patch: PatchProposal | None = None,
        hypothesis_id: str | None = None,
        bound_hypothesis_digest: str | None = None,
        non_resumable: bool = False,
    ) -> bool:
        """Commit a direct attempt phase before publishing or routing its result."""

        owner = self.owner
        state = self.state
        bid = branch.branch_id
        attempt_id = state.attempt_ids.get(bid)
        if not attempt_id:
            self.fail_integrity(
                branch,
                f"proposal_attempt_started_missing_for_{phase}_terminal",
                clear_approved_binding=(phase == "hypothesis"),
            )
            return False
        if state.attempt_phases.get(bid) != phase:
            self.fail_integrity(
                branch,
                "proposal_attempt_phase_mismatch_for_terminal",
                clear_approved_binding=(phase == "hypothesis"),
            )
            return False
        receipt = state.prompt_call_receipts.get(bid, {}).get(phase)
        if receipt is not None:
            if receipt.attempt_id is not None and receipt.attempt_id != attempt_id:
                self.fail_integrity(
                    branch,
                    "prompt_receipt_attempt_identity_mismatch",
                    clear_approved_binding=(phase == "hypothesis"),
                )
                return False
            started_event_id = state.started_event_ids.get(bid)
            if (
                receipt.attempt_started_event_id is not None
                and receipt.attempt_started_event_id != started_event_id
            ):
                self.fail_integrity(
                    branch,
                    "prompt_receipt_started_event_identity_mismatch",
                    clear_approved_binding=(phase == "hypothesis"),
                )
                return False
            continuation_id = state.continuation_ids.get(bid)
            if (
                receipt.continuation_of_attempt_id is not None
                and receipt.continuation_of_attempt_id != continuation_id
            ):
                self.fail_integrity(
                    branch,
                    "prompt_receipt_continuation_identity_mismatch",
                    clear_approved_binding=(phase == "hypothesis"),
                )
                return False
        payload = self._transition_payload(
            branch=branch,
            champion=champion,
            phase=phase,
            status=status,
            transition_reason=transition_reason,
            failure_lane=failure_lane,
            hypothesis=hypothesis,
            patch=patch,
            hypothesis_id=hypothesis_id,
            bound_hypothesis_digest=bound_hypothesis_digest,
            prompt_call=_prompt_call_payload(receipt),
            non_resumable=non_resumable,
        )
        trace_error = _trace_persistence_error_payload(receipt)
        if trace_error is not None:
            payload["trace_persistence_error"] = trace_error
        try:
            event_id = ProposalAttemptRecorder(owner.lineage_registry).record_transition(
                payload
            )
        except Exception as exc:
            self._fail_lineage_write(
                branch,
                f"proposal_attempt_terminal_lineage_write_failed:{type(exc).__name__}",
            )
            return False
        binding = state.approved_hypothesis_bindings.get(bid)
        hypothesis_attempt_id = (
            str(binding.get("hypothesis_attempt_id") or "")
            if isinstance(binding, Mapping)
            else ""
        )
        terminal_ref = _proposal_attempt_ref(
            payload,
            event_id=event_id,
            started_event_id=state.started_event_ids.get(bid),
            hypothesis_attempt_id=hypothesis_attempt_id or None,
        )
        state.attempt_refs[bid] = terminal_ref
        state.attempt_refs_by_id[attempt_id] = terminal_ref
        state.phase_attempt_refs.setdefault(bid, {})[phase] = terminal_ref
        self._invalidate_cache(bid)
        self._finish(bid, phase=phase, status=status)
        return True

    def _transition_payload(
        self,
        *,
        branch: Branch,
        champion: ChampionState,
        phase: str,
        status: str,
        transition_reason: str,
        failure_lane: str | None,
        hypothesis: HypothesisProposal | None,
        patch: PatchProposal | None,
        hypothesis_id: str | None,
        bound_hypothesis_digest: str | None,
        prompt_call: Mapping[str, Any] | None,
        non_resumable: bool = False,
    ) -> dict[str, Any]:
        owner = self.owner
        state = self.state
        bid = branch.branch_id
        resolved_hypothesis_id = hypothesis_id or state.hypothesis_ids.get(bid)
        hypothesis_digest = bound_hypothesis_digest or (
            self.hypothesis_digest(hypothesis) if hypothesis is not None else None
        )
        patch_digest = (
            stable_patch_digest(patch.iter_file_changes())
            if patch is not None
            else None
        )
        proposal_fingerprint = _hypothesis_proposal_fingerprint(hypothesis)
        if not proposal_fingerprint and phase == "code":
            binding = state.approved_hypothesis_bindings.get(bid)
            if isinstance(binding, Mapping):
                proposal_fingerprint = dict(
                    binding.get("proposal_fingerprint") or {}
                )
        payload = {
            "schema_version": "proposal-attempt-transition.v1",
            "attempt_id": state.attempt_ids[bid],
            "campaign_id": owner.campaign_id,
            "branch_id": bid,
            "runtime_mode": "direct_v3",
            "phase": phase,
            "status": status,
            "transition_reason": transition_reason,
            "failure_lane": failure_lane,
            "hypothesis_id": resolved_hypothesis_id,
            "hypothesis_digest": hypothesis_digest,
            "patch_digest": patch_digest,
            "prompt_call": dict(prompt_call) if prompt_call is not None else None,
            "anchors": {
                "problem_id": owner.problem_id,
                "problem_spec_hash": owner.problem_spec_hash,
                "split_manifest_hash": owner.split_manifest_hash,
                "seed_ledger_hash": owner.seed_ledger_hash,
                "champion_version": champion.version,
                "champion_weight_revision": champion.weight_revision,
                "champion_code_snapshot_hash": champion.code_snapshot_hash,
                "branch_base_champion_id": branch.base_champion_id,
                "branch_base_champion_hash": branch.base_champion_hash,
            },
            "tainted_artifact_refs": _prompt_call_artifact_refs_from_payload(
                prompt_call
            ),
        }
        if proposal_fingerprint:
            payload["proposal_fingerprint"] = proposal_fingerprint
        attempt_kind = state.attempt_kinds.get(bid)
        if attempt_kind is not None:
            payload["attempt_kind"] = attempt_kind
        continuation_id = state.continuation_ids.get(bid)
        if continuation_id is not None:
            payload["continuation_of_attempt_id"] = continuation_id
        if non_resumable:
            payload["non_resumable"] = True
        return payload

    def interrupt_provider_call(
        self,
        *,
        branch: Branch,
        champion: ChampionState,
        phase: str,
        error: KeyboardInterrupt,
        hypothesis: HypothesisProposal | None,
        bound_hypothesis_digest: str | None = None,
    ) -> None:
        """Terminalize one started direct call without making it resumable.

        An operator signal and a local ``KeyboardInterrupt`` share this path:
        both stop the campaign invocation, retain durable evidence, and never
        schedule another provider call or enter an alternate control path.
        """

        owner = self.owner
        state = self.state
        bid = branch.branch_id
        attempt_id = state.attempt_ids.get(bid)
        if not attempt_id or state.attempt_phases.get(bid) != phase:
            return
        receipt = prompt_call_receipt_from_error(error)
        if receipt is None:
            started_prompt_call = state.started_prompt_calls.get(bid, {})
            receipt = PromptCallReceipt(
                request_kind=phase,
                trace_ref=None,
                prompt_manifest_ref=None,
                raw_response_ref=None,
                prompt_hash=str(started_prompt_call.get("prompt_hash") or ""),
                context_digest=str(
                    started_prompt_call.get("context_digest") or ""
                ),
                provider_ok=False,
                ok=False,
                error_category="provider_call_interrupted",
                error_type=type(error).__name__,
                attempt_id=attempt_id,
                attempt_started_event_id=state.started_event_ids.get(bid),
                continuation_of_attempt_id=state.continuation_ids.get(bid),
            )
        self.record_receipt(bid, phase, receipt)
        hypothesis_id = state.hypothesis_ids.get(bid)
        if not self.commit(
            branch=branch,
            champion=champion,
            phase=phase,
            status="interrupted",
            transition_reason="provider_call_interrupted",
            failure_lane=None,
            hypothesis=hypothesis,
            hypothesis_id=hypothesis_id,
            bound_hypothesis_digest=bound_hypothesis_digest,
            non_resumable=True,
        ):
            return
        record = self.record_execution_outcome(
            branch,
            phase=phase,
            outcome=ExecutionOutcome.INTERRUPTED,
            reason_code="PROPOSAL_PROVIDER_INTERRUPTED",
            detail=f"provider_call_interrupted:{type(error).__name__}",
            error_type=type(error).__name__,
            error_category="provider_call_interrupted",
            provenance={
                "attempt_id": attempt_id,
                "non_resumable": True,
                "candidate_preserved": True,
            },
        )
        install_branch_execution_hold(branch, record)
        try:
            record_execution_outcome_event(
                registry=owner.lineage_registry,
                campaign_id=owner.campaign_id,
                branch_id=bid,
                record=record,
                hypothesis_id=hypothesis_id,
                event_kind="proposal_execution_outcome",
            )
        except Exception:
            # The terminal attempt transition is already durable.  Never turn
            # an operator interruption into a replacement exception while
            # final campaign artifacts are written.
            pass

    def prepare_code(
        self,
        branch: Branch,
        hypothesis: HypothesisProposal,
    ) -> str | None:
        owner = self.owner
        state = self.state
        bid = branch.branch_id
        binding = state.approved_hypothesis_bindings.get(bid)
        if not isinstance(binding, Mapping):
            self.fail_integrity(
                branch,
                "approved_hypothesis_binding_missing_for_direct_code",
                clear_approved_binding=True,
            )
            return None
        expected_id = str(binding.get("hypothesis_id") or "")
        expected_digest = str(binding.get("hypothesis_digest") or "")
        actual_digest = self.hypothesis_digest(hypothesis)
        durable_record = owner.hypothesis_store.get_one(expected_id) if expected_id else None
        if (
            not expected_id
            or not expected_digest
            or actual_digest != expected_digest
            or durable_record is None
            or durable_record.branch_id != bid
        ):
            if durable_record is not None and expected_id:
                owner.hypothesis_store.mark_status(expected_id, "rejected")
            self.fail_integrity(
                branch,
                "approved_hypothesis_binding_mismatch_for_direct_code",
                clear_approved_binding=True,
            )
            return None
        return expected_digest

    def require_receipt_api(self, branch: Branch, phase: str) -> bool:
        owner = self.owner
        if owner.lineage_registry is None:
            return True
        method_name = (
            "generate_direct_hypothesis_with_receipt"
            if phase == "hypothesis"
            else "generate_direct_code_with_receipt"
        )
        if callable(getattr(owner.creative, method_name, None)):
            return True
        self.fail_integrity(
            branch,
            f"direct_{phase}_receipt_api_required_for_lineage",
            clear_approved_binding=(phase == "hypothesis"),
        )
        return False

    def handle_unexpected_receipt_exception(
        self,
        *,
        branch: Branch,
        champion: ChampionState,
        phase: str,
        error: BaseException,
        hypothesis: HypothesisProposal | None,
        patch: PatchProposal | None = None,
        bound_hypothesis_digest: str | None = None,
        transition_reason_override: str | None = None,
    ) -> bool:
        owner = self.owner
        bid = branch.branch_id
        receipt = prompt_call_receipt_from_error(error) or self.state.prompt_call_receipts.get(
            bid,
            {},
        ).get(phase)
        if receipt is None:
            return False
        self.record_receipt(bid, phase, receipt)
        transition_reason = transition_reason_override or receipt.error_category or (
            "post_provider_processing_failed"
            if receipt.provider_ok
            else "provider_call_failed"
        )
        committed = self.commit(
            branch=branch,
            champion=champion,
            phase=phase,
            status="failed",
            transition_reason=transition_reason,
            failure_lane="infra",
            hypothesis=hypothesis,
            patch=patch,
            bound_hypothesis_digest=bound_hypothesis_digest,
        )
        if not committed:
            return True
        detail = f"{transition_reason}:{type(error).__name__}"
        blocked = transition_reason in {
            "provider_call_failed",
            "trace_start_failed",
            "trace_finish_failed",
            "hypothesis_store_write_failed",
        }
        self.record_execution_outcome(
            branch,
            phase=phase,
            outcome=(
                ExecutionOutcome.BLOCKED_INFRA
                if blocked
                else ExecutionOutcome.NOT_EVALUATED
            ),
            reason_code=(
                "PROPOSAL_INFRA_BLOCKED"
                if blocked
                else "PROPOSAL_POST_PROVIDER_INVALID"
            ),
            detail=detail,
            error_type=type(error).__name__,
            error_category=transition_reason,
        )
        owner.hypothesis_failure_details[bid] = detail
        if blocked:
            owner.handle_failure(
                branch,
                FailureEvent(category="infra", detail=detail),
            )
        return True

    def fail_integrity(
        self,
        branch: Branch,
        detail: str,
        *,
        clear_approved_binding: bool,
    ) -> None:
        owner = self.owner
        bid = branch.branch_id
        self._clear_pending(bid)
        self.clear_ref(bid)
        if clear_approved_binding:
            self.state.approved_hypothesis_bindings.pop(bid, None)
        self.record_execution_outcome(
            branch,
            phase="proposal",
            outcome=ExecutionOutcome.BLOCKED_INFRA,
            reason_code="PROPOSAL_INTEGRITY_BLOCKED",
            detail=detail,
        )
        owner.hypothesis_failure_details[bid] = detail
        owner.handle_failure(
            branch,
            FailureEvent(category="infra", detail=detail),
        )

    def clear_ref(self, branch_id: str) -> None:
        self.state.attempt_refs.pop(branch_id, None)
        self._invalidate_cache(branch_id)

    def _fail_lineage_write(self, branch: Branch, detail: str) -> None:
        owner = self.owner
        bid = branch.branch_id
        phase = self.state.attempt_phases.get(bid) or "proposal"
        self._clear_pending(bid)
        self.clear_ref(bid)
        self.state.approved_hypothesis_bindings.pop(bid, None)
        self.record_execution_outcome(
            branch,
            phase=phase,
            outcome=ExecutionOutcome.BLOCKED_INFRA,
            reason_code="PROPOSAL_LINEAGE_BLOCKED",
            detail=detail,
            error_category="lineage_write_failed",
        )
        owner.hypothesis_failure_details[bid] = detail
        owner.handle_failure(
            branch,
            FailureEvent(category="infra", detail=detail),
        )

    def _clear_pending(self, branch_id: str) -> None:
        state = self.state
        state.attempt_ids.pop(branch_id, None)
        state.attempt_phases.pop(branch_id, None)
        state.attempt_kinds.pop(branch_id, None)
        state.continuation_ids.pop(branch_id, None)
        state.started_event_ids.pop(branch_id, None)
        state.started_prompt_calls.pop(branch_id, None)
        state.hypothesis_ids.pop(branch_id, None)

    def _finish(self, branch_id: str, *, phase: str, status: str) -> None:
        state = self.state
        attempt_id = state.attempt_ids.get(branch_id)
        if status == "interrupted":
            state.approved_hypothesis_bindings.pop(branch_id, None)
        elif phase == "code" and status in {"failed", "generated"}:
            state.approved_hypothesis_bindings.pop(branch_id, None)
        elif phase == "hypothesis" and status == "failed":
            state.approved_hypothesis_bindings.pop(branch_id, None)
        self._clear_pending(branch_id)

    def _invalidate_cache(self, branch_id: str) -> None:
        cache = getattr(self.owner, "_proposal_session_ref_cache", None)
        if isinstance(cache, dict):
            cache.pop(branch_id, None)


def _hypothesis_proposal_fingerprint(
    hypothesis: HypothesisProposal | None,
) -> dict[str, Any]:
    if hypothesis is None:
        return {}
    return {
        "selected_surface": str(hypothesis.change_locus),
        "action": str(hypothesis.action),
        "target_file": (
            str(hypothesis.target_file)
            if hypothesis.target_file is not None
            else None
        ),
    }


def _prompt_call_payload(receipt: PromptCallReceipt | None) -> dict[str, Any] | None:
    if receipt is None:
        return None
    return {
        "request_kind": receipt.request_kind,
        "context_digest": receipt.context_digest,
        "prompt_hash": receipt.prompt_hash,
        "trace_ref": receipt.trace_ref,
        "prompt_manifest_ref": receipt.prompt_manifest_ref,
        "raw_response_ref": receipt.raw_response_ref,
        "provider_ok": receipt.provider_ok,
        "ok": receipt.ok,
        "error_category": receipt.error_category,
        "error_type": receipt.error_type,
    }


def _prompt_call_artifact_refs_from_payload(
    prompt_call: Mapping[str, Any] | None,
) -> list[str]:
    if not isinstance(prompt_call, Mapping):
        return []
    refs = (
        prompt_call.get("trace_ref"),
        prompt_call.get("prompt_manifest_ref"),
        prompt_call.get("raw_response_ref"),
    )
    return list(dict.fromkeys(str(ref) for ref in refs if ref))


def _trace_persistence_error_payload(
    receipt: PromptCallReceipt | None,
) -> dict[str, str] | None:
    if receipt is None:
        return None
    encoded = str(receipt.trace_persistence_error or "").strip()
    if encoded.startswith("trace_") and ":" in encoded:
        category, error_type = encoded.split(":", 1)
        stage = category.removeprefix("trace_").removesuffix("_failed")
        if stage in {"start", "finish"} and error_type:
            return {"stage": stage, "error_type": error_type}
    if receipt.error_category in {"trace_start_failed", "trace_finish_failed"}:
        return {
            "stage": receipt.error_category.removeprefix("trace_").removesuffix(
                "_failed"
            ),
            "error_type": str(receipt.error_type or "unknown"),
        }
    return None


def _proposal_attempt_ref(
    payload: Mapping[str, Any],
    *,
    event_id: str,
    started_event_id: str | None = None,
    hypothesis_attempt_id: str | None = None,
) -> dict[str, Any]:
    prompt_call = payload.get("prompt_call")
    if not isinstance(prompt_call, Mapping):
        prompt_call = {}
    ref = {
        "schema_version": "proposal-attempt-ref.v1",
        "attempt_id": payload["attempt_id"],
        "runtime_mode": payload["runtime_mode"],
        "phase": payload["phase"],
        "status": payload["status"],
        "transition_reason": payload["transition_reason"],
        "failure_lane": payload["failure_lane"],
        "lineage_event_id": event_id,
        "hypothesis_id": payload.get("hypothesis_id"),
        "artifact_ref": prompt_call.get("trace_ref"),
        "prompt_manifest_ref": prompt_call.get("prompt_manifest_ref"),
        "prompt_hash": prompt_call.get("prompt_hash"),
    }
    for key in ("attempt_kind", "continuation_of_attempt_id"):
        if payload.get(key) is not None:
            ref[key] = payload[key]
    if payload.get("non_resumable") is True:
        ref["non_resumable"] = True
    if started_event_id:
        ref["started_lineage_event_id"] = started_event_id
    if hypothesis_attempt_id:
        ref["hypothesis_attempt_id"] = hypothesis_attempt_id
    return ref


__all__ = ["DirectAttemptLifecycle", "DirectAttemptState"]
