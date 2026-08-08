"""Hypothesis and mechanism-binding checks for ContractGate."""
from __future__ import annotations

import time
from typing import Callable

from scion.config.problem import ProblemSpec
from scion.core.models import (
    CheckResult,
    HypothesisProposal,
)
from scion.contract.result_payload import check_result as _cr
from scion.contract.schema import PREDICTED_DIRECTIONS as _PREDICTED_DIRECTIONS
from scion.contract.surface_access import SurfaceAccess


def check_hypothesis_schema(
    h: HypothesisProposal,
    problem_spec: ProblemSpec,
) -> CheckResult:
    t0 = time.monotonic_ns()
    passed = True
    detail = "schema ok"

    if not h.hypothesis_text or not h.hypothesis_text.strip():
        passed = False
        detail = "hypothesis_text is empty"
    elif not h.change_locus or not h.change_locus.strip():
        passed = False
        detail = "change_locus is empty"
    elif h.action not in ("modify", "create_new", "remove"):
        passed = False
        detail = f"action '{h.action}' is not valid"
    elif h.predicted_direction not in _PREDICTED_DIRECTIONS:
        passed = False
        detail = "predicted_direction must be one of improve/tradeoff/exploratory"
    return _cr("C1_schema", passed, "heavy", detail, t0)


def check_change_locus(
    h: HypothesisProposal,
    *,
    problem_spec: ProblemSpec,
    surface_access: SurfaceAccess,
) -> CheckResult:
    t0 = time.monotonic_ns()
    categories = problem_spec.operator_categories
    passed = h.change_locus in categories
    if passed:
        surface = surface_access.surface_by_name(h.change_locus)
        kind_error = surface_access.surface_kind_error(surface)
        if kind_error is not None:
            return _cr("C2_change_locus", False, "heavy", kind_error, t0)
    detail = (
        "change_locus ok"
        if passed
        else f"change_locus '{h.change_locus}' not in research loci {categories}"
    )
    return _cr("C2_change_locus", passed, "heavy", detail, t0)


def check_action_target(
    h: HypothesisProposal,
    *,
    surface_access: SurfaceAccess,
    file_exists: Callable[[str], bool] | None = None,
) -> CheckResult:
    t0 = time.monotonic_ns()
    passed = True
    detail = "action-target ok"

    surface = surface_access.surface_by_name(h.change_locus)
    if surface is not None:
        kind_error = surface_access.surface_kind_error(surface)
        if kind_error is not None:
            return _cr("C3_action_target", False, "heavy", kind_error, t0)
        if not surface_access.surface_action_allowed(surface, h.action):
            return _cr(
                "C3_action_target",
                False,
                "heavy",
                f"action='{h.action}' is not allowed for research surface "
                f"'{h.change_locus}'",
                t0,
            )

    target_file = str(h.target_file or "")
    if target_file and any(character in target_file for character in "*?["):
        passed = False
        detail = "target_file must name one concrete file, not a glob pattern"
    elif h.action in ("modify", "remove"):
        if not h.target_file:
            passed = False
            detail = f"action='{h.action}' requires target_file"
        elif surface is not None and not surface_access.target_matches_surface(
            h.target_file,
            surface,
        ):
            passed = False
            detail = (
                f"target_file '{h.target_file}' is not in target files "
                f"{surface_access.surface_target_files(surface)}"
            )
        elif file_exists is not None and not file_exists(h.target_file):
            passed = False
            detail = f"action='{h.action}' requires an existing target_file"
    elif h.action == "create_new" and not h.target_file:
        passed = False
        detail = "action='create_new' requires target_file"
    elif (
        h.action == "create_new"
        and h.target_file
        and surface is not None
        and not surface_access.target_matches_surface(h.target_file, surface)
    ):
        passed = False
        detail = (
            f"target_file '{h.target_file}' is not in target files "
            f"{surface_access.surface_target_files(surface)}"
        )
    elif (
        h.action == "create_new"
        and h.target_file
        and file_exists is not None
        and file_exists(h.target_file)
    ):
        passed = False
        detail = "action='create_new' requires a target_file that does not exist"

    return _cr("C3_action_target", passed, "heavy", detail, t0)
