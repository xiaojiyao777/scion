"""MockLLMClient — deterministic stand-in for tests."""
from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from scion.proposal.llm_client import (
    LLMFormatError,
    LLMTimeoutError,
)

# ---------------------------------------------------------------------------
# Default canned responses
# ---------------------------------------------------------------------------

_DEFAULT_HYPOTHESIS_RESPONSE: Dict[str, Any] = {
    "hypothesis_text": "Mock hypothesis: try improved local search.",
    "change_locus": "local_search",
    "action": "modify",
    "target_file": "operators/local_search.py",
    "predicted_direction": "improve",
    "target_weakness": "Slow convergence on dense instances.",
    "expected_effect": "Reduce average cost by 2%.",
    "suggested_weight": 0.3,
}

_DEFAULT_LOCAL_SEARCH_SOURCE = (
    "class LocalSearch:\n"
    "    def execute(self, solution, rng):\n"
    "        return solution\n\n"
)

_DEFAULT_PATCH_RESPONSE: Dict[str, Any] = {
    "file_path": "operators/local_search.py",
    "action": "modify",
    "edit_intent": "exact_replace",
    "old_string": "        return solution\n",
    "new_string": "        return solution\n",
    "test_hint": "Test with small instances.",
}


# ---------------------------------------------------------------------------
# Mock client
# ---------------------------------------------------------------------------

class MockLLMClient:
    """LLM client for unit / integration tests.

    Args:
        mode: Controls the failure scenario.
              ``"success"``       — always return a valid response.
              ``"format_error"``  — always raise :class:`LLMFormatError`.
              ``"timeout"``       — always raise :class:`LLMTimeoutError`.
        hypothesis_response: Override the default hypothesis proposal JSON.
        patch_response: Override the default patch proposal JSON.
        mode_sequence: If given, cycle through modes in this order (one per call).
    """

    def __init__(
        self,
        mode: Literal["success", "format_error", "timeout"] = "success",
        hypothesis_response: Optional[Dict[str, Any]] = None,
        patch_response: Optional[Dict[str, Any]] = None,
        mode_sequence: Optional[list] = None,
    ) -> None:
        self.mode = mode
        self._hypothesis_response = hypothesis_response or dict(_DEFAULT_HYPOTHESIS_RESPONSE)
        self._patch_response = _normalise_patch_response_for_edit_protocol(
            patch_response or dict(_DEFAULT_PATCH_RESPONSE)
        )
        self._mode_sequence = list(mode_sequence) if mode_sequence else None
        self._call_count = 0

    def call_with_tool(
        self,
        prompt: str,
        tool: Dict[str, Any],
        model: Optional[str] = None,
        system_blocks: "list[dict] | None" = None,
        request_kind: str | None = None,
    ) -> Dict[str, Any]:
        """Return one canned typed tool response or configured leaf fault."""
        del prompt, model, system_blocks, request_kind
        current_mode = self._current_mode()
        self._call_count += 1
        if current_mode == "timeout":
            raise LLMTimeoutError("MockLLMClient: simulated timeout")
        if current_mode == "format_error":
            raise LLMFormatError("MockLLMClient: simulated format error")
        tool_name = str(tool.get("name") or "")
        if tool_name == "code_research_turn":
            return {"action": "ready", "patch": dict(self._patch_response)}
        if tool_name == "finalize_code_research":
            return {"outcome": "finalize_patch"}
        schema = tool.get("input_schema", {})
        return self._pick_response(schema)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _current_mode(self) -> str:
        if self._mode_sequence:
            idx = min(self._call_count, len(self._mode_sequence) - 1)
            return self._mode_sequence[idx]
        return self.mode

    def _pick_response(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Return hypothesis or patch response depending on schema required fields."""
        required = set(schema.get("required", []))
        if "hypothesis_text" in required or "change_locus" in required:
            return dict(self._hypothesis_response)
        # Default: patch proposal
        return dict(self._patch_response)

    @property
    def call_count(self) -> int:
        return self._call_count


def _normalise_patch_response_for_edit_protocol(
    patch_response: Dict[str, Any],
) -> Dict[str, Any]:
    """Keep older unit fixtures compatible with the typed edit protocol."""

    patch = dict(patch_response)
    if (
        patch.get("file_path") == "operators/local_search.py"
        and patch.get("action") == "modify"
        and "edit_intent" not in patch
        and isinstance(patch.get("code_content"), str)
    ):
        patch.pop("code_content", None)
        patch.setdefault("edit_intent", "exact_replace")
        patch.setdefault("old_string", "        return solution\n")
        patch.setdefault("new_string", "        return solution\n")
    return patch
