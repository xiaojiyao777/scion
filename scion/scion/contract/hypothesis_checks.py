"""Hypothesis and mechanism-binding checks for ContractGate."""
from __future__ import annotations

import time
from typing import Any

from scion.config.problem import ProblemSpec
from scion.core.models import (
    CheckResult,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
    mechanism_changes,
)
from scion.contract.result_payload import check_result as _cr
from scion.contract.schema import (
    PREDICTED_DIRECTIONS as _PREDICTED_DIRECTIONS,
    mechanism_changes_schema_error as _mechanism_changes_schema_error,
    objective_list_schema_error as _objective_list_schema_error,
    objective_metric_names as _objective_metric_names,
)
from scion.contract.surface_access import SurfaceAccess
from scion.contract.telemetry import (
    mechanism_id_matches_declaration as _mechanism_id_matches_declaration,
    surface_mechanism_telemetry_declarations as _surface_mechanism_telemetry_declarations,
)
from scion.runtime.telemetry_guard import validate_expected_telemetry_contract


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
    else:
        objective_error = _objective_list_schema_error(
            h,
            _objective_metric_names(problem_spec),
        )
        if objective_error is not None:
            passed = False
            detail = objective_error
        else:
            mechanism_error = _mechanism_changes_schema_error(h)
            if mechanism_error is not None:
                passed = False
                detail = mechanism_error

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

    if h.action in ("modify", "remove"):
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

    return _cr("C3_action_target", passed, "heavy", detail, t0)


def check_expected_telemetry(
    h: HypothesisProposal,
    *,
    problem_spec: ProblemSpec,
) -> CheckResult:
    t0 = time.monotonic_ns()
    expected = getattr(h, "expected_telemetry", None)
    if expected in (None, "", [], (), {}):
        return _cr(
            "C11_expected_telemetry",
            True,
            "light",
            "no expected telemetry declared",
            t0,
        )
    if not isinstance(expected, dict):
        return _cr(
            "C11_expected_telemetry",
            False,
            "heavy",
            "expected_telemetry must be an object",
            t0,
        )
    try:
        declared_mechanisms = mechanism_changes(h)
    except (TypeError, AttributeError):
        declared_mechanisms = ()
    errors = validate_expected_telemetry_contract(
        problem_spec=problem_spec,
        selected_surface=h.change_locus,
        expected_telemetry=expected,
        declared_mechanisms=declared_mechanisms,
    )
    if errors:
        return _cr(
            "C11_expected_telemetry",
            False,
            "heavy",
            "; ".join(errors),
            t0,
        )
    return _cr(
        "C11_expected_telemetry",
        True,
        "light",
        "expected telemetry fields declared by selected surface",
        t0,
    )


def check_hypothesis_mechanism_binding(
    h: HypothesisProposal,
    *,
    surface_access: SurfaceAccess,
) -> CheckResult:
    t0 = time.monotonic_ns()
    schema_error = _mechanism_changes_schema_error(h)
    if schema_error is not None:
        return _cr("C12_mechanism_binding", False, "heavy", schema_error, t0)

    surface = surface_access.surface_for_hypothesis(h)
    declarations = _surface_mechanism_telemetry_declarations(surface)
    if not declarations:
        return _cr(
            "C12_mechanism_binding",
            True,
            "light",
            "surface declares no mechanism telemetry",
            t0,
        )

    changes = mechanism_changes(h)
    if not changes:
        return _cr(
            "C12_mechanism_binding",
            False,
            "heavy",
            f"research surface '{h.change_locus}' declares mechanism "
            "telemetry; hypothesis must declare mechanism_changes",
            t0,
        )

    unmatched = [
        change.id
        for change in changes
        if not _mechanism_id_matches_declaration(change.id, declarations)
    ]
    if unmatched:
        return _cr(
            "C12_mechanism_binding",
            False,
            "heavy",
            "mechanism_changes id(s) do not match declared mechanism "
            f"telemetry exact/wildcard keys: {', '.join(unmatched)}",
            t0,
        )

    return _cr(
        "C12_mechanism_binding",
        True,
        "light",
        "mechanism changes match selected surface telemetry declarations",
        t0,
    )


def check_patch_mechanism_binding(
    patch: PatchProposal,
    approved_hypothesis: HypothesisProposal | HypothesisRecord | None,
    *,
    selected_surface: str | None,
    surface_access: SurfaceAccess,
) -> CheckResult:
    t0 = time.monotonic_ns()
    schema_error = _mechanism_changes_schema_error(patch)
    if schema_error is not None:
        return _cr("C12_mechanism_binding", False, "heavy", schema_error, t0)

    surface = None
    if selected_surface:
        surface = surface_access.surface_by_name(selected_surface)
    if surface is None and approved_hypothesis is not None:
        surface = surface_access.surface_for_hypothesis(approved_hypothesis)
    declarations = _surface_mechanism_telemetry_declarations(surface)
    if not declarations:
        return _cr(
            "C12_mechanism_binding",
            True,
            "light",
            "surface declares no mechanism telemetry",
            t0,
        )
    if approved_hypothesis is None:
        return _cr(
            "C12_mechanism_binding",
            True,
            "light",
            "no approved hypothesis supplied; mechanism echo skipped",
            t0,
        )

    approved_ids = {change.id for change in mechanism_changes(approved_hypothesis)}
    if not approved_ids:
        return _cr(
            "C12_mechanism_binding",
            False,
            "heavy",
            "approved hypothesis declares no mechanism_changes for a "
            "mechanism-telemetry surface",
            t0,
        )
    patch_ids = {change.id for change in mechanism_changes(patch)}
    if patch_ids != approved_ids:
        missing = sorted(approved_ids - patch_ids)
        extra = sorted(patch_ids - approved_ids)
        detail_parts: list[str] = []
        if missing:
            detail_parts.append("missing approved mechanism id(s): " + ", ".join(missing))
        if extra:
            detail_parts.append("unexpected mechanism id(s): " + ", ".join(extra))
        return _cr(
            "C12_mechanism_binding",
            False,
            "heavy",
            "patch mechanism_changes must echo approved hypothesis "
            "mechanism ids; " + "; ".join(detail_parts),
            t0,
        )

    return _cr(
        "C12_mechanism_binding",
        True,
        "light",
        "patch echoes approved mechanism ids",
        t0,
    )
