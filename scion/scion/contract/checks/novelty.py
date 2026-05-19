"""Static novelty and duplicate-hypothesis checks."""
from __future__ import annotations

import hashlib
import time
from typing import Any

from scion.config.problem import ProblemSpec
from scion.contract.result_payload import check_result
from scion.contract.schema import (
    WEAK_SIGNATURE_FIELDS,
    normalize_signature_field,
    objective_metric_names,
)
from scion.contract.surface_access import SurfaceAccess
from scion.core.models import CheckResult, HypothesisProposal, HypothesisRecord


class NoveltyChecker:
    """Evaluate C10 novelty using generic surface metadata."""

    def __init__(self, problem_spec: ProblemSpec, surface_access: SurfaceAccess) -> None:
        self._spec = problem_spec
        self._surface_access = surface_access

    def check(
        self,
        h: HypothesisProposal,
        active_hypotheses: list[HypothesisRecord],
        blacklist: list[HypothesisRecord],
        *,
        current_champion_version: int = 0,
    ) -> CheckResult:
        t0 = time.monotonic_ns()
        novelty_error = self._novelty_strategy_error(h)
        if novelty_error is not None:
            return check_result("C10_novelty", False, "light", novelty_error, t0)
        semantic_identity_error = self._semantic_signature_identity_error(h)
        if semantic_identity_error is not None:
            return check_result(
                "C10_novelty",
                False,
                "light",
                semantic_identity_error,
                t0,
            )
        key = self._novelty_key(h)
        for existing in active_hypotheses + blacklist:
            # Rejected hypotheses only block if they come from the same champion version;
            # a champion upgrade opens the door to retry previously rejected modify paths.
            if existing.status == "rejected":
                if existing.base_champion_version != current_champion_version:
                    continue
            duplicate_key = self._duplicate_novelty_key(
                h,
                existing,
                candidate_key=key,
            )
            if duplicate_key is not None:
                return check_result(
                    "C10_novelty",
                    False,
                    "light",
                    self._duplicate_novelty_detail(h, existing, duplicate_key),
                    t0,
                )
        return check_result("C10_novelty", True, "light", "novel", t0)

    def _duplicate_novelty_detail(
        self,
        h: HypothesisProposal,
        existing: HypothesisRecord,
        duplicate_key: tuple[Any, ...],
    ) -> str:
        base = f"duplicate of existing hypothesis (key={duplicate_key})"
        if not self._uses_same_semantic_modify_surface(h, existing):
            return base
        surface = self._surface_access.surface_for_hypothesis(h)
        fields = self._surface_access.surface_signature_fields(surface)
        candidate_missing = self._missing_semantic_signature_fields(h, surface)
        existing_missing = self._missing_semantic_signature_fields(existing, surface)
        if candidate_missing or existing_missing:
            parts = [
                "semantic_signature surface lacks usable structured identity; "
                "C10 fell back to target-file identity"
            ]
            if candidate_missing:
                parts.append(
                    "candidate missing novelty_signature fields: "
                    + ", ".join(candidate_missing)
                )
            if existing_missing:
                parts.append(
                    "existing hypothesis missing novelty_signature fields: "
                    + ", ".join(existing_missing)
                )
            return base + "; " + "; ".join(parts)
        if len(duplicate_key) >= 4 and duplicate_key[2] == "semantic_signature":
            return (
                base
                + "; duplicate structured novelty_signature for declared fields: "
                + ", ".join(fields)
            )
        return base

    def _duplicate_novelty_key(
        self,
        h: HypothesisProposal,
        existing: HypothesisRecord,
        *,
        candidate_key: tuple[Any, ...],
    ) -> tuple[Any, ...] | None:
        if self._uses_same_semantic_modify_surface(h, existing):
            surface = self._surface_access.surface_for_hypothesis(h)
            candidate_semantic = self._semantic_signature_key(h, surface)
            existing_semantic = self._semantic_signature_key(existing, surface)
            if candidate_semantic is None:
                strict_key = self._strict_novelty_key(h)
                if strict_key == self._strict_novelty_key(existing):
                    return strict_key
                return None
            if existing_semantic is None:
                return None
            if candidate_semantic == existing_semantic:
                return (
                    h.change_locus,
                    h.action,
                    "semantic_signature",
                    candidate_semantic,
                )
            return None

        existing_key = self._novelty_key(existing)
        if candidate_key == existing_key:
            return candidate_key
        return None

    def _uses_same_semantic_modify_surface(
        self,
        h: HypothesisProposal,
        existing: HypothesisRecord,
    ) -> bool:
        if h.action != "modify" or existing.action != "modify":
            return False
        if h.change_locus != existing.change_locus:
            return False
        surface = self._surface_access.surface_for_hypothesis(h)
        return (
            self._surface_access.surface_novelty_strategy(surface)
            == "semantic_signature"
        )

    def _novelty_key(self, h: HypothesisProposal | HypothesisRecord) -> tuple[Any, ...]:
        strict_key = self._strict_novelty_key(h)
        if h.action == "create_new":
            return (
                h.change_locus,
                h.action,
                h.target_file,
                (h.hypothesis_text or "")[:50],
            )

        if h.action == "modify":
            surface = self._surface_access.surface_for_hypothesis(h)
            if (
                self._surface_access.surface_novelty_strategy(surface)
                == "semantic_signature"
            ):
                semantic_key = self._semantic_signature_key(h, surface)
                if semantic_key is not None:
                    return (h.change_locus, h.action, "semantic_signature", semantic_key)
                return strict_key

        return strict_key

    @staticmethod
    def _strict_novelty_key(
        h: HypothesisProposal | HypothesisRecord,
    ) -> tuple[Any, ...]:
        return (h.change_locus, h.action, h.target_file)

    def _novelty_strategy_error(
        self,
        h: HypothesisProposal | HypothesisRecord,
    ) -> str | None:
        surface = self._surface_access.surface_for_hypothesis(h)
        strategy = self._surface_access.surface_novelty_strategy(surface)
        if strategy in ("", "target_file", "semantic_signature"):
            return None
        return (
            f"unsupported novelty.strategy '{strategy}' for research surface "
            f"'{h.change_locus}'"
        )

    def _semantic_signature_identity_error(
        self,
        h: HypothesisProposal | HypothesisRecord,
    ) -> str | None:
        if h.action != "modify":
            return None
        surface = self._surface_access.surface_for_hypothesis(h)
        if (
            self._surface_access.surface_novelty_strategy(surface)
            != "semantic_signature"
        ):
            return None
        fields = self._surface_access.surface_signature_fields(surface)
        if not fields:
            return (
                "semantic_signature surface "
                f"'{h.change_locus}' declares no usable novelty.signature_fields"
            )
        missing = self._missing_semantic_signature_fields(h, surface)
        if missing:
            return (
                "semantic_signature surface "
                f"'{h.change_locus}' requires usable structured "
                "novelty_signature identity; candidate missing or invalid "
                "novelty_signature fields: "
                + ", ".join(missing)
            )
        if self._semantic_signature_key(h, surface) is None:
            return (
                "semantic_signature surface "
                f"'{h.change_locus}' requires at least one strong structured "
                "identity field beyond weak defaults such as predicted_direction"
            )
        return None

    def _semantic_signature_key(
        self,
        h: HypothesisProposal | HypothesisRecord,
        surface: Any | None,
    ) -> str | None:
        fields = self._surface_access.surface_signature_fields(surface)
        if not fields:
            return None
        names = objective_metric_names(self._spec)
        parts: list[str] = []
        sufficient = False
        for field in fields:
            normalized = normalize_signature_field(field, h, objective_names=names)
            if normalized is None:
                return None
            if field not in WEAK_SIGNATURE_FIELDS:
                sufficient = True
            parts.append(f"{field}:{normalized}")
        if not parts or not sufficient:
            return None
        normalized = "|".join(parts)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]

    def _missing_semantic_signature_fields(
        self,
        h: HypothesisProposal | HypothesisRecord,
        surface: Any | None,
    ) -> list[str]:
        missing: list[str] = []
        names = objective_metric_names(self._spec)
        for field in self._surface_access.surface_signature_fields(surface):
            if normalize_signature_field(field, h, objective_names=names) is None:
                missing.append(field)
        return missing
