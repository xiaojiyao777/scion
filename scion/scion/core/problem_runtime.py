"""Problem-owned inputs and context assembly for the direct V3 runtime.

Owns:

  - ``_spec``          — the static ``ProblemSpec``
  - ``_adapter``       — optional problem adapter
  - ``_ctx_manager``   — adapter-aware ``ContextManager``

Also provides thin context-render wrappers (``build_hypothesis_context`` /
``build_code_context``) that pre-fill the
``problem_spec`` argument when delegating to the underlying ContextManager,
so campaign-side callers do not thread ``self._spec`` through every call.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Optional

from scion.core.research_input import normalize_research_input


class ProblemRuntime:
    """Owns problem spec + adapter + ContextManager."""

    def __init__(
        self,
        *,
        problem_spec: Any,
        adapter: Optional[Any] = None,
        split_manifest: Any | None = None,
        seed_ledger: Any | None = None,
        research_input: Any | None = None,
        development_suites: tuple[Any, ...] = (),
    ) -> None:
        self._spec = problem_spec
        self._adapter = adapter
        self._split_manifest = split_manifest
        self._seed_ledger = seed_ledger
        self._research_input = (
            normalize_research_input(research_input)
            if research_input is not None
            else None
        )
        self._development_suites = tuple(development_suites)
        from scion.proposal.context_manager import ContextManager

        self._ctx_manager = ContextManager(
            adapter=adapter,
            research_input=self._research_input,
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
    def split_manifest(self) -> Any | None:
        return self._split_manifest

    @property
    def seed_ledger(self) -> Any | None:
        return self._seed_ledger

    @property
    def research_input(self) -> dict[str, Any] | None:
        return deepcopy(self._research_input)

    @property
    def development_suites(self) -> tuple[Any, ...]:
        """Host-owned public development suite manifest, never prompt context."""

        return self._development_suites

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
