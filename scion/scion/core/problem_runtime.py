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

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any, Optional

from scion.core.research_history import (
    normalize_research_history_record,
    problem_id_from_spec,
)
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
        research_history: Sequence[Mapping[str, Any]] = (),
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
        problem_id = problem_id_from_spec(problem_spec)
        self._research_history = tuple(
            normalize_research_history_record(record, expected_problem_id=problem_id)
            for record in research_history
        )
        self._development_suites = tuple(development_suites)
        from scion.proposal.context_manager import ContextManager

        self._ctx_manager = ContextManager(
            adapter=adapter,
            research_input=self._research_input,
            research_history=self._research_history,
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
    def research_history(self) -> tuple[dict[str, Any], ...]:
        return deepcopy(self._research_history)

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
        kwargs.setdefault("development_suites", self._development_suites)
        return self._ctx_manager.build_code_context(**kwargs)

    def hypothesis_research_public_sources(self) -> tuple[dict[str, str], ...]:
        """Read only explicitly declared public development test files."""

        from scion.core.paths import normalize_relative_patch_path
        from scion.proposal.context_manager.io import (
            _read_solver_design_context_artifact,
        )
        from scion.verification.development import (
            validate_development_closure_boundary,
        )

        records: list[dict[str, str]] = []
        seen: set[str] = set()
        validate_development_closure_boundary(
            problem_spec=self._spec,
            suites=self._development_suites,
            workspace_paths=(),
            problem_package_paths=(),
            split_manifest=self._split_manifest,
            champion_root=None,
        )
        for suite in self._development_suites:
            path = normalize_relative_patch_path(suite.test_path)
            if path != suite.test_path or path in seen:
                raise ValueError(f"invalid or duplicate development test path: {path}")
            check_name = suite.check_name
            if check_name not in {"D3_unit_tests", "D4_regression_tests"}:
                raise ValueError(f"invalid development check name: {check_name}")
            artifact = _read_solver_design_context_artifact(
                path,
                source_root=suite.source_root,
                champion_root="",
                allow_champion_fallback=False,
            )
            if not artifact["readable"]:
                raise ValueError(f"declared development test is unreadable: {path}")
            seen.add(path)
            records.append(
                {"path": path, "check_name": check_name, "content": artifact["content"]}
            )
        return tuple(records)

    def hypothesis_research_source_prefixes(self) -> tuple[str, ...]:
        """Return the host-known problem package prefix for source adjacency."""

        return (f"scion.problems.{problem_id_from_spec(self._spec)}.",)
