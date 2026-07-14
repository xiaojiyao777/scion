"""CreativeLayer facade for LLM-backed proposal generation."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Any, Dict, Mapping

from scion.core.models import HypothesisProposal, PatchProposal
from scion.proposal.context_owner_maps import proposal_context_snapshot
from scion.proposal.context_snapshot import ProposalContextSnapshot
from scion.proposal.prompt_projection_authority import (
    ProposalPromptProjectionAuthority,
)
from scion.proposal.prompt_manifest import stable_digest
from scion.proposal.schemas import PATCH_TOOL, bind_hypothesis_tool_to_context

from .parsing import _parse_hypothesis, _parse_patch
from .provider_call import (
    PromptCallReceipt,
    PromptTurnSnapshot,
    ProviderCallOwner,
    _attach_prompt_call_receipt,
    prompt_call_receipt_from_error,
)


def build_prompt_turn_snapshot(
    render_kind: str,
    context: Mapping[str, Any] | ProposalContextSnapshot,
) -> PromptTurnSnapshot:
    """Render one provider-visible prompt turn from its structured context."""
    kind = str(render_kind)
    if kind not in {"hypothesis", "code"}:
        raise ValueError(f"unsupported prompt render kind: {render_kind}")
    authoritative = (
        context
        if isinstance(context, ProposalContextSnapshot)
        else proposal_context_snapshot(kind, context)
    )
    projection = ProposalPromptProjectionAuthority.project(kind, authoritative)
    render_context = projection.structured_context
    if kind == "hypothesis":
        provider_tool, allowed_change_loci = bind_hypothesis_tool_to_context(
            render_context
        )
    else:
        provider_tool = deepcopy(PATCH_TOOL)
        allowed_change_loci = ()
    return PromptTurnSnapshot(
        render_kind=kind,
        system_blocks=tuple(dict(block) for block in projection.system_blocks),
        user_prompt=str(projection.user_prompt),
        context_digest=stable_digest(render_context, length=64),
        provider_tool=provider_tool,
        allowed_change_loci=allowed_change_loci,
        authoritative_context_ref=authoritative.snapshot_id,
        authoritative_context=authoritative,
    )


class CreativeLayer:
    """Generates HypothesisProposal (Round 1) and PatchProposal (Round 2) via LLM.

    The client must implement ``call_with_tool(...) -> dict``.
    Both :class:`~scion.proposal.llm_client.LLMClient` and
    :class:`~scion.proposal.mock_client.MockLLMClient` satisfy this interface.

    Typed leaf faults from the single-attempt LLM client propagate to the
    caller (CampaignManager → FailureRouter).
    """

    def __init__(
        self,
        llm_client: Any,
        model: str | None = None,
        *,
        trace_dir: str | None = None,
    ) -> None:
        self._client = llm_client
        self._model = model or getattr(llm_client, "model", None) or "claude-opus-4-6"
        self._trace_dir = trace_dir
        self._provider_calls = ProviderCallOwner(
            self._client,
            self._model,
            trace_dir=self._trace_dir,
        )

    def generate_direct_hypothesis_with_receipt(
        self,
        context: Dict[str, Any],
        snapshot: PromptTurnSnapshot,
        *,
        attempt_audit: Mapping[str, Any] | None = None,
    ) -> tuple[HypothesisProposal, PromptCallReceipt]:
        """Generate one direct-v3 hypothesis without a Scion output cap."""
        return self._generate_hypothesis_with_receipt(
            context,
            snapshot,
            attempt_audit=attempt_audit,
        )

    def _generate_hypothesis_with_receipt(
        self,
        context: Dict[str, Any],
        snapshot: PromptTurnSnapshot,
        *,
        attempt_audit: Mapping[str, Any] | None = None,
    ) -> tuple[HypothesisProposal, PromptCallReceipt]:
        raw, receipt = self._provider_calls.call_with_receipt(
            request_kind="hypothesis",
            tool=dict(snapshot.provider_tool),
            context=context,
            snapshot=snapshot,
            attempt_audit=attempt_audit,
        )
        try:
            return (
                _parse_hypothesis(
                    raw,
                    allowed_change_loci=snapshot.allowed_change_loci,
                ),
                receipt,
            )
        except Exception as exc:
            failed = replace(
                receipt,
                ok=False,
                error_category="response_parse_failed",
                error_type=type(exc).__name__,
            )
            _attach_prompt_call_receipt(exc, failed)
            raise

    def generate_direct_code_with_receipt(
        self,
        context: Dict[str, Any],
        snapshot: PromptTurnSnapshot,
        *,
        attempt_audit: Mapping[str, Any] | None = None,
    ) -> tuple[PatchProposal, PromptCallReceipt]:
        """Generate one direct-v3 patch without a Scion output cap."""
        return self._generate_code_with_receipt(
            context,
            snapshot,
            attempt_audit=attempt_audit,
        )

    def _generate_code_with_receipt(
        self,
        context: Dict[str, Any],
        snapshot: PromptTurnSnapshot,
        *,
        attempt_audit: Mapping[str, Any] | None = None,
    ) -> tuple[PatchProposal, PromptCallReceipt]:
        raw, receipt = self._provider_calls.call_with_receipt(
            request_kind="code",
            tool=dict(snapshot.provider_tool),
            context=context,
            snapshot=snapshot,
            attempt_audit=attempt_audit,
        )
        try:
            return _parse_patch(raw, context=context), receipt
        except Exception as exc:
            failed = replace(
                receipt,
                ok=False,
                error_category="response_parse_failed",
                error_type=type(exc).__name__,
            )
            _attach_prompt_call_receipt(exc, failed)
            raise
