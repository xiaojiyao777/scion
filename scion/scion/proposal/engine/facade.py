"""CreativeLayer facade for LLM-backed proposal generation."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Any, Dict, Mapping

from scion.core.models import HypothesisProposal, PatchProposal
from scion.proposal.context_owner_maps import proposal_context_snapshot
from scion.proposal.context_snapshot import ProposalContextSnapshot
from scion.proposal.prompt_projection import project_prompt
from scion.proposal.schemas import PATCH_TOOL, bind_hypothesis_tool_to_context

from .parsing import _parse_hypothesis, _parse_patch
from .provider_call import (
    ProviderCallDiagnostics,
    PromptTurnSnapshot,
    ProviderCaller,
    _attach_provider_call_diagnostics,
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
    projection = project_prompt(kind, authoritative)
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
        provider_tool=provider_tool,
        allowed_change_loci=allowed_change_loci,
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
        self._provider_calls = ProviderCaller(
            self._client,
            self._model,
            trace_dir=self._trace_dir,
        )

    def generate_direct_hypothesis(
        self,
        context: Dict[str, Any],
        snapshot: PromptTurnSnapshot,
        *,
        call_context: Mapping[str, Any] | None = None,
    ) -> tuple[HypothesisProposal, ProviderCallDiagnostics]:
        """Generate one direct-v3 hypothesis without a Scion output cap."""
        return self._generate_hypothesis(
            context,
            snapshot,
            call_context=call_context,
        )

    def _generate_hypothesis(
        self,
        context: Dict[str, Any],
        snapshot: PromptTurnSnapshot,
        *,
        call_context: Mapping[str, Any] | None = None,
    ) -> tuple[HypothesisProposal, ProviderCallDiagnostics]:
        raw, diagnostics = self._provider_calls.call(
            request_kind="hypothesis",
            tool=dict(snapshot.provider_tool),
            context=context,
            snapshot=snapshot,
            call_context=call_context,
        )
        try:
            return (
                _parse_hypothesis(
                    raw,
                    allowed_change_loci=snapshot.allowed_change_loci,
                ),
                diagnostics,
            )
        except Exception as exc:
            failed = replace(
                diagnostics,
                ok=False,
                error_category="response_parse_failed",
                error_type=type(exc).__name__,
            )
            _attach_provider_call_diagnostics(exc, failed)
            raise

    def generate_direct_code(
        self,
        context: Dict[str, Any],
        snapshot: PromptTurnSnapshot,
        *,
        call_context: Mapping[str, Any] | None = None,
    ) -> tuple[PatchProposal, ProviderCallDiagnostics]:
        """Generate one direct-v3 patch without a Scion output cap."""
        return self._generate_code(
            context,
            snapshot,
            call_context=call_context,
        )

    def _generate_code(
        self,
        context: Dict[str, Any],
        snapshot: PromptTurnSnapshot,
        *,
        call_context: Mapping[str, Any] | None = None,
    ) -> tuple[PatchProposal, ProviderCallDiagnostics]:
        raw, diagnostics = self._provider_calls.call(
            request_kind="code",
            tool=dict(snapshot.provider_tool),
            context=context,
            snapshot=snapshot,
            call_context=call_context,
        )
        try:
            return _parse_patch(raw, context=context), diagnostics
        except Exception as exc:
            failed = replace(
                diagnostics,
                ok=False,
                error_category="response_parse_failed",
                error_type=type(exc).__name__,
            )
            _attach_provider_call_diagnostics(exc, failed)
            raise
