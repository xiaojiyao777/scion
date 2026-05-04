"""ProblemRuntime — problem spec + adapter + ContextManager bundle.

Extracted from CampaignManager (v0.3 §B3 per optimization-design doc).
Final service extraction for v0.3 minimum scope. Owns:

  - ``_spec``          — the static ``ProblemSpec``
  - ``_adapter``       — optional problem adapter
  - ``_ctx_manager``   — adapter-aware ``ContextManager``

Also provides thin context-render wrappers (``build_hypothesis_context`` /
``build_code_context`` / ``build_fix_context``) that pre-fill the
``problem_spec`` argument when delegating to the underlying ContextManager,
so campaign-side callers no longer need to thread ``self._spec`` through
every call.

Further consolidation (moving more of the problem-spec-dependent accessors
here) is v1.0 Phase 1 scope.
"""
from __future__ import annotations

from typing import Any, Optional


class ProblemRuntime:
    """Owns problem spec + adapter + ContextManager."""

    def __init__(
        self,
        *,
        problem_spec: Any,
        adapter: Optional[Any] = None,
        runtime_slow_threshold: float = 2.0,
    ) -> None:
        self._spec = problem_spec
        self._adapter = adapter
        from scion.proposal.context_manager import ContextManager
        self._ctx_manager = ContextManager(
            adapter=adapter,
            runtime_slow_threshold=runtime_slow_threshold,
        )

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def spec(self) -> Any:
        return self._spec

    @property
    def adapter(self) -> Optional[Any]:
        return self._adapter

    @property
    def ctx_manager(self) -> Any:
        return self._ctx_manager

    # ------------------------------------------------------------------
    # Context-render wrappers — pre-fill problem_spec
    # ------------------------------------------------------------------

    def build_hypothesis_context(self, **kwargs):
        kwargs.setdefault("problem_spec", self._spec)
        return self._ctx_manager.build_hypothesis_context(**kwargs)

    def build_code_context(self, **kwargs):
        kwargs.setdefault("problem_spec", self._spec)
        return self._ctx_manager.build_code_context(**kwargs)

    def build_fix_context(self, **kwargs):
        kwargs.setdefault("problem_spec", self._spec)
        return self._ctx_manager.build_fix_context(**kwargs)
