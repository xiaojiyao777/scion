"""CreativeLayer facade for LLM-backed proposal generation."""

from __future__ import annotations

from typing import Any, Dict

from scion.core.models import HypothesisProposal, PatchProposal
from scion.proposal.schemas import (
    FIX_TOOL,
    HYPOTHESIS_TOOL,
    PATCH_TOOL,
    TOOL_SELECTION_TOOL,
)

from .code_prompts import _split_code_context
from .fix_context import _split_fix_context
from .hypothesis_prompts import _split_hypothesis_context
from .parsing import _parse_hypothesis, _parse_patch
from .tool_selection import _build_tool_selection_prompt, _parse_tool_selection
from .trace import _TraceWriter, _client_request_policy


class CreativeLayer:
    """Generates HypothesisProposal (Round 1) and PatchProposal (Round 2) via LLM.

    The client must implement ``call(prompt, response_schema, model) -> dict``.
    Both :class:`~scion.proposal.llm_client.LLMClient` and
    :class:`~scion.proposal.mock_client.MockLLMClient` satisfy this interface.

    Errors from the LLM client (LLMRetryExhaustedError, LLMFormatError, …)
    propagate to the caller (CampaignManager → FailureRouter).
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

    def generate_hypothesis(self, context: Dict[str, Any]) -> HypothesisProposal:
        """Generate a HypothesisProposal using tool_use."""
        system_blocks, user_prompt = _split_hypothesis_context(context)
        raw = self._call_with_trace(
            request_kind="hypothesis",
            prompt=user_prompt,
            tool=HYPOTHESIS_TOOL,
            system_blocks=system_blocks,
            context=context,
        )
        return _parse_hypothesis(raw)

    def generate_code(self, context: Dict[str, Any]) -> PatchProposal:
        """Generate a PatchProposal using tool_use (API handles JSON escape)."""
        system_blocks, user_prompt = _split_code_context(context)
        raw = self._call_with_trace(
            request_kind="code",
            prompt=user_prompt,
            tool=PATCH_TOOL,
            system_blocks=system_blocks,
            context=context,
        )
        return _parse_patch(raw)

    def fix_code(self, context: Dict[str, Any]) -> PatchProposal:
        """Generate a corrected PatchProposal after a light verification failure.

        Uses tool_use (same as generate_hypothesis/generate_code) to avoid
        JSON escape issues when code_content contains complex Python.
        """
        system_blocks, user_prompt = _split_fix_context(context)
        raw = self._call_with_trace(
            request_kind="fix",
            prompt=user_prompt,
            tool=FIX_TOOL,
            system_blocks=system_blocks,
            context=context,
        )
        return _parse_patch(raw)

    def plan_tool_call(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Ask the model to choose the next APS proposal tool.

        The model only returns a plan. APS validates the selected tool against
        its allowed list and executes through ProposalToolRegistry.
        """
        prompt = _build_tool_selection_prompt(context)
        raw = self._call_with_trace(
            request_kind="tool_selection",
            prompt=prompt,
            tool=TOOL_SELECTION_TOOL,
            system_blocks=[],
            context=context,
        )
        return _parse_tool_selection(raw)

    def _call_with_trace(
        self,
        *,
        request_kind: str,
        prompt: str,
        tool: Dict[str, Any],
        system_blocks: "list[dict]",
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        trace = _TraceWriter(self._trace_dir)
        request_policy = _client_request_policy(
            self._client,
            request_kind=request_kind,
            tool=tool,
        )
        trace_path = trace.write_start(
            request_kind=request_kind,
            model=self._model,
            tool=tool,
            prompt=prompt,
            system_blocks=system_blocks,
            context=context,
            request_policy=request_policy,
        )
        try:
            raw = self._client.call_with_tool(
                prompt,
                tool,
                self._model,
                system_blocks=system_blocks,
            )
        except Exception as exc:
            trace.write_finish(trace_path, ok=False, error=str(exc))
            raise
        trace.write_finish(trace_path, ok=True, response=raw)
        return raw
