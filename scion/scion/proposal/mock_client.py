"""MockLLMClient — deterministic stand-in for tests."""
from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from scion.proposal.llm_client import (
    LLMFormatError,
    LLMTimeoutError,
    LLMRetryExhaustedError,
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

_DEFAULT_PATCH_RESPONSE: Dict[str, Any] = {
    "file_path": "operators/local_search.py",
    "action": "modify",
    "code_content": (
        "class LocalSearch:\n"
        "    def execute(self, solution, rng):\n"
        "        return solution\n"
    ),
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
              ``"exhausted"``     — always raise :class:`LLMRetryExhaustedError`.
        hypothesis_response: Override the default hypothesis proposal JSON.
        patch_response: Override the default patch proposal JSON.
        mode_sequence: If given, cycle through modes in this order (one per call).
    """

    def __init__(
        self,
        mode: Literal["success", "format_error", "timeout", "exhausted"] = "success",
        hypothesis_response: Optional[Dict[str, Any]] = None,
        patch_response: Optional[Dict[str, Any]] = None,
        mode_sequence: Optional[list] = None,
    ) -> None:
        self.mode = mode
        self._hypothesis_response = hypothesis_response or dict(_DEFAULT_HYPOTHESIS_RESPONSE)
        self._patch_response = patch_response or dict(_DEFAULT_PATCH_RESPONSE)
        self._mode_sequence = list(mode_sequence) if mode_sequence else None
        self._call_count = 0

    # ------------------------------------------------------------------
    # Public API (same signature as LLMClient.call)
    # ------------------------------------------------------------------

    def call(
        self,
        prompt: str,
        response_schema: Dict[str, Any],
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return a canned response or raise a configured error."""
        current_mode = self._current_mode()
        self._call_count += 1

        if current_mode == "timeout":
            raise LLMTimeoutError("MockLLMClient: simulated timeout")
        if current_mode == "format_error":
            raise LLMFormatError("MockLLMClient: simulated format error")
        if current_mode == "exhausted":
            raise LLMRetryExhaustedError("MockLLMClient: simulated retry exhausted")

        # "success" — pick response based on required fields in schema
        return self._pick_response(response_schema)

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
