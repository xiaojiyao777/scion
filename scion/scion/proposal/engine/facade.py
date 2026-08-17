"""CreativeLayer facade for LLM-backed proposal generation."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from scion.core.models import HypothesisProposal, PatchProposal
from scion.core.resource_envelope import ProviderCallBudget
from scion.proposal.context_snapshot import (
    ProposalContextSnapshot,
    freeze_proposal_context,
)
from scion.proposal.prompt_projection import project_prompt
from scion.proposal.schemas import PATCH_TOOL, bind_hypothesis_tool_to_context

from .parsing import _parse_hypothesis, _parse_patch
from .provider_call import PromptTurnSnapshot, ProviderCaller


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
        else freeze_proposal_context(kind, context)
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
        structured_context_json=projection.structured_context_json,
    )


class CreativeLayer:
    """Generates HypothesisProposal (Round 1) and PatchProposal (Round 2) via LLM.

    The client must implement ``call_with_tool(...) -> dict``.
    Both :class:`~scion.proposal.llm_client.LLMClient` and
    :class:`~scion.proposal.mock_client.MockLLMClient` satisfy this interface.

    Typed leaf faults from the single-attempt LLM client propagate to the
    outer campaign attempt.
    """

    def __init__(
        self,
        llm_client: Any,
        model: str | None = None,
        *,
        trace_dir: str | None = None,
        provider_call_budget: ProviderCallBudget | None = None,
    ) -> None:
        self._client = llm_client
        self._model = model or getattr(llm_client, "model", None) or "claude-opus-4-6"
        self._provider_calls = ProviderCaller(
            self._client,
            self._model,
            trace_dir=trace_dir,
            provider_call_budget=provider_call_budget,
        )

    def generate_direct_hypothesis(
        self,
        snapshot: PromptTurnSnapshot,
    ) -> HypothesisProposal:
        """Generate one direct-v3 hypothesis without a Scion output cap."""
        raw = self._provider_calls.call(
            request_kind="hypothesis",
            tool=dict(snapshot.provider_tool),
            snapshot=snapshot,
        )
        return _parse_hypothesis(
            raw,
            allowed_change_loci=snapshot.allowed_change_loci,
        )

    def generate_direct_code(
        self,
        snapshot: PromptTurnSnapshot,
    ) -> PatchProposal:
        """Generate one direct-v3 patch without a Scion output cap."""
        raw = self._provider_calls.call(
            request_kind="code",
            tool=dict(snapshot.provider_tool),
            snapshot=snapshot,
        )
        return _parse_patch(raw, context=snapshot.structured_context)
