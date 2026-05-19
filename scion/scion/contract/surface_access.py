"""Research-surface metadata access for contract checks."""
from __future__ import annotations

from typing import Any

from scion.contract.patch_paths import matches_config_pattern
from scion.core.models import HypothesisProposal, HypothesisRecord
from scion.core.paths import normalize_relative_patch_path
from scion.problem.spec import SUPPORTED_RESEARCH_SURFACE_KINDS


class SurfaceAccess:
    """Read generic research-surface metadata from a problem spec."""

    def __init__(self, problem_spec: Any) -> None:
        self._spec = problem_spec

    def research_surfaces(self) -> list[Any]:
        return list(getattr(self._spec, "research_surfaces", []) or [])

    def surface_by_name(self, name: str) -> Any | None:
        for surface in self.research_surfaces():
            if getattr(surface, "name", None) == name:
                return surface
        return None

    def surface_kind_error(self, surface: Any | None) -> str | None:
        if surface is None:
            return None
        kind = str(getattr(surface, "kind", "") or "").strip()
        if kind in SUPPORTED_RESEARCH_SURFACE_KINDS:
            return None
        allowed = ", ".join(sorted(SUPPORTED_RESEARCH_SURFACE_KINDS))
        return (
            f"unsupported research surface kind '{kind}' for surface "
            f"'{getattr(surface, 'name', '<unknown>')}', expected one of: {allowed}"
        )

    def surface_for_hypothesis(
        self,
        h: HypothesisProposal | HypothesisRecord,
    ) -> Any | None:
        surface = self.surface_by_name(h.change_locus)
        if surface is not None:
            return surface
        if h.target_file:
            return self.surface_for_patch_path(h.target_file)
        return None

    def surface_for_patch_path(self, file_rel: str) -> Any | None:
        for surface in self.research_surfaces():
            if self.target_matches_surface(file_rel, surface):
                return surface
        return None

    def surface_for_patch_selection(
        self,
        file_rel: str,
        *,
        selected_surface: str | None,
    ) -> tuple[Any | None, str | None]:
        surfaces = self.research_surfaces()
        selected = str(selected_surface or "").strip()
        if not selected or not surfaces:
            return self.surface_for_patch_path(file_rel), None

        surface = self.surface_by_name(selected)
        if surface is None:
            return (
                None,
                f"selected research surface '{selected}' is not declared "
                "in problem_spec.research_surfaces",
            )
        if not self.target_matches_surface(file_rel, surface):
            return (
                None,
                f"patch file_path '{file_rel}' is not in target files "
                f"{self.surface_target_files(surface)} for selected research "
                f"surface '{selected}'",
            )
        return surface, None

    def target_matches_surface(self, file_rel: str, surface: Any) -> bool:
        try:
            normalized = normalize_relative_patch_path(file_rel)
        except ValueError:
            return False
        target_files = self.surface_target_files(surface)
        return any(
            matches_config_pattern(normalized, str(pattern).lstrip("/"))
            for pattern in target_files
        )

    @staticmethod
    def surface_targets(surface: Any | None) -> Any | None:
        if surface is None:
            return None
        return getattr(surface, "targets", None)

    def surface_target_files(self, surface: Any | None) -> list[str]:
        targets = self.surface_targets(surface)
        if targets is not None:
            files = getattr(targets, "files", None)
            if files is not None:
                return [str(path) for path in files]
        return [str(path) for path in (getattr(surface, "target_files", []) or [])]

    def surface_action_allowed(self, surface: Any | None, action: str) -> bool:
        attr = {
            "create_new": "create_new_allowed",
            "modify": "modify_allowed",
            "remove": "remove_allowed",
        }.get(action)
        if attr is None:
            return False
        targets = self.surface_targets(surface)
        if targets is not None and hasattr(targets, attr):
            return bool(getattr(targets, attr))
        return bool(getattr(surface, attr, True))

    @staticmethod
    def surface_novelty_strategy(surface: Any | None) -> str:
        novelty = getattr(surface, "novelty", None) if surface is not None else None
        strategy = getattr(novelty, "strategy", "") if novelty is not None else ""
        return str(strategy or "")

    @staticmethod
    def surface_signature_fields(surface: Any | None) -> list[str]:
        novelty = getattr(surface, "novelty", None) if surface is not None else None
        fields = (
            getattr(novelty, "signature_fields", None)
            if novelty is not None
            else None
        )
        normalized: list[str] = []
        for field in fields or []:
            value = str(field).strip()
            if value:
                normalized.append(value)
        return normalized
