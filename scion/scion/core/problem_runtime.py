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

from scion.core.problem_identity import stable_identity_hash
from scion.proposal.context_ablation import normalize_proposal_context_ablation


class ProblemRuntime:
    """Owns problem spec + adapter + ContextManager."""

    def __init__(
        self,
        *,
        problem_spec: Any,
        adapter: Optional[Any] = None,
        split_manifest: Any | None = None,
        seed_ledger: Any | None = None,
        runtime_slow_threshold: float = 2.0,
        measurement_governance: str = "on",
        proposal_context_ablation: str = "full",
    ) -> None:
        self._spec = problem_spec
        self._adapter = adapter
        self._split_manifest = split_manifest
        self._seed_ledger = seed_ledger
        self._measurement_governance = measurement_governance
        self._proposal_context_ablation = normalize_proposal_context_ablation(
            proposal_context_ablation
        )
        self._problem_spec_hash = stable_identity_hash(problem_spec)
        self._adapter_spec_hash = stable_identity_hash(_visible_adapter_spec(adapter))
        self._split_manifest_hash = stable_identity_hash(split_manifest)
        self._seed_ledger_hash = stable_identity_hash(seed_ledger)
        self._runtime_bundle_hash = stable_identity_hash(
            {
                "problem_spec_hash": self._problem_spec_hash,
                "adapter_spec_hash": self._adapter_spec_hash,
                "split_manifest_hash": self._split_manifest_hash,
                "seed_ledger_hash": self._seed_ledger_hash,
                "measurement_governance": self._measurement_governance,
                "proposal_context_ablation": self._proposal_context_ablation,
            }
        )
        from scion.proposal.context_manager import ContextManager
        self._ctx_manager = ContextManager(
            adapter=adapter,
            runtime_slow_threshold=runtime_slow_threshold,
            measurement_governance=measurement_governance,
            proposal_context_ablation=self._proposal_context_ablation,
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
    def measurement_governance(self) -> str:
        return self._measurement_governance

    @property
    def proposal_context_ablation(self) -> str:
        return self._proposal_context_ablation

    @property
    def ctx_manager(self) -> Any:
        return self._ctx_manager

    @property
    def problem_spec_hash(self) -> str | None:
        return self._problem_spec_hash

    @property
    def adapter_spec_hash(self) -> str | None:
        return self._adapter_spec_hash

    @property
    def split_manifest_hash(self) -> str | None:
        return self._split_manifest_hash

    @property
    def seed_ledger_hash(self) -> str | None:
        return self._seed_ledger_hash

    @property
    def runtime_bundle_hash(self) -> str | None:
        return self._runtime_bundle_hash

    # ------------------------------------------------------------------
    # Context-render wrappers — pre-fill problem_spec
    # ------------------------------------------------------------------

    def build_hypothesis_context(self, **kwargs):
        kwargs.setdefault("problem_spec", self._spec)
        return self._ctx_manager.build_hypothesis_context(**kwargs)

    def build_code_context(self, **kwargs):
        kwargs.setdefault("problem_spec", self._spec)
        compat_kwargs = dict(kwargs)
        optional_keys = ("branch_workspace", "step_history")
        while True:
            try:
                return self._ctx_manager.build_code_context(**compat_kwargs)
            except TypeError as exc:
                removed = False
                for key in optional_keys:
                    if key in str(exc) and key in compat_kwargs:
                        compat_kwargs.pop(key, None)
                        removed = True
                if not removed:
                    raise

    def build_fix_context(self, **kwargs):
        kwargs.setdefault("problem_spec", self._spec)
        return self._ctx_manager.build_fix_context(**kwargs)


def _visible_adapter_spec(adapter: Any | None) -> Any | None:
    if adapter is None:
        return None
    spec = getattr(adapter, "spec", None)
    if spec is None:
        spec = getattr(adapter, "_spec", None)
    if callable(spec):
        try:
            spec = spec()
        except TypeError:
            return None
    return spec
