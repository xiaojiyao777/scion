"""Static patch target, path, and action checks for ContractGate."""
from __future__ import annotations

import time

from scion.config.problem import ProblemSpec
from scion.contract.patch_paths import (
    hypothesis_action_for_patch_action,
    matches_config_pattern,
    patch_action_for_hypothesis_action,
)
from scion.contract.result_payload import check_result
from scion.contract.surface_access import SurfaceAccess
from scion.core.models import CheckResult, HypothesisProposal, HypothesisRecord, PatchProposal
from scion.core.paths import normalize_relative_patch_path


def check_file_whitelist(patch: PatchProposal, problem_spec: ProblemSpec) -> CheckResult:
    t0 = time.monotonic_ns()
    try:
        file_rel = normalize_relative_patch_path(patch.file_path)
    except ValueError as exc:
        return check_result("C4_file_whitelist", False, "heavy", str(exc), t0)

    editable = problem_spec.search_space.editable
    passed = any(matches_config_pattern(file_rel, pat) for pat in editable)
    detail = (
        "file in whitelist"
        if passed
        else f"'{file_rel}' not in editable patterns {editable}"
    )
    return check_result("C4_file_whitelist", passed, "heavy", detail, t0)


def check_frozen_files(patch: PatchProposal, problem_spec: ProblemSpec) -> CheckResult:
    t0 = time.monotonic_ns()
    try:
        file_rel = normalize_relative_patch_path(patch.file_path)
    except ValueError as exc:
        return check_result("C5_frozen_files", False, "heavy", str(exc), t0)

    frozen = problem_spec.search_space.frozen
    violated = [pat for pat in frozen if matches_config_pattern(file_rel, pat)]
    passed = len(violated) == 0
    detail = "not frozen" if passed else f"'{file_rel}' matches frozen patterns {violated}"
    return check_result("C5_frozen_files", passed, "heavy", detail, t0)


def check_patch_action_target(
    patch: PatchProposal,
    hypothesis: HypothesisProposal | HypothesisRecord | None,
    *,
    surface_access: SurfaceAccess,
    selected_surface: str | None = None,
    enforce_hypothesis_target: bool = True,
) -> CheckResult:
    t0 = time.monotonic_ns()
    try:
        file_rel = normalize_relative_patch_path(patch.file_path)
    except ValueError as exc:
        return check_result("C4b_patch_action_target", False, "heavy", str(exc), t0)

    surface = None
    if hypothesis is not None and enforce_hypothesis_target:
        expected_patch_action = patch_action_for_hypothesis_action(hypothesis.action)
        if expected_patch_action is None:
            return check_result(
                "C4b_patch_action_target",
                False,
                "heavy",
                f"hypothesis action '{hypothesis.action}' has no patch action mapping",
                t0,
            )
        if patch.action != expected_patch_action:
            return check_result(
                "C4b_patch_action_target",
                False,
                "heavy",
                f"patch action '{patch.action}' does not match approved "
                f"hypothesis action '{hypothesis.action}'",
                t0,
            )

        target_file = getattr(hypothesis, "target_file", None)
        if target_file:
            try:
                target_rel = normalize_relative_patch_path(target_file)
            except ValueError as exc:
                return check_result(
                    "C4b_patch_action_target",
                    False,
                    "heavy",
                    str(exc),
                    t0,
                )
            if file_rel != target_rel:
                return check_result(
                    "C4b_patch_action_target",
                    False,
                    "heavy",
                    f"patch file_path '{file_rel}' does not match approved "
                    f"hypothesis target_file '{target_rel}'",
                    t0,
                )
        selected_name = _selected_surface_name(hypothesis) or selected_surface
        surface = surface_access.surface_by_name(selected_name or "")
        if selected_name and surface_access.research_surfaces() and surface is None:
            return check_result(
                "C4b_patch_action_target",
                False,
                "heavy",
                f"selected research surface '{selected_name}' is not declared "
                "in problem_spec.research_surfaces",
                t0,
            )
        if surface is None:
            surface = surface_access.surface_for_hypothesis(hypothesis)
    elif selected_surface:
        surface = surface_access.surface_by_name(selected_surface)
        if surface_access.research_surfaces() and surface is None:
            return check_result(
                "C4b_patch_action_target",
                False,
                "heavy",
                f"selected research surface '{selected_surface}' is not declared "
                "in problem_spec.research_surfaces",
                t0,
            )

    if surface is None:
        surface = surface_access.surface_for_patch_path(file_rel)

    if surface is not None:
        kind_error = surface_access.surface_kind_error(surface)
        if kind_error is not None:
            return check_result(
                "C4b_patch_action_target",
                False,
                "heavy",
                kind_error,
                t0,
            )
        surface_action = hypothesis_action_for_patch_action(patch.action)
        if surface_action is None:
            return check_result(
                "C4b_patch_action_target",
                False,
                "heavy",
                f"patch action '{patch.action}' is not valid",
                t0,
            )
        if not surface_access.surface_action_allowed(surface, surface_action):
            return check_result(
                "C4b_patch_action_target",
                False,
                "heavy",
                f"patch action '{patch.action}' maps to surface action "
                f"'{surface_action}', which is not allowed for research "
                f"surface '{getattr(surface, 'name', '<unknown>')}'",
                t0,
            )
        if not surface_access.target_matches_surface(file_rel, surface):
            return check_result(
                "C4b_patch_action_target",
                False,
                "heavy",
                f"patch file_path '{file_rel}' is not in target files "
                f"{surface_access.surface_target_files(surface)}",
                t0,
            )

    return check_result(
        "C4b_patch_action_target",
        True,
        "heavy",
        "patch action-target ok",
        t0,
    )


def _selected_surface_name(
    hypothesis: HypothesisProposal | HypothesisRecord | None,
) -> str | None:
    if hypothesis is None:
        return None
    name = str(getattr(hypothesis, "change_locus", "") or "").strip()
    return name or None
