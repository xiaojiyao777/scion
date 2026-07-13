"""Hypothesis and mechanism-binding checks for ContractGate."""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Mapping

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


def check_governance_constraints(
    h: HypothesisProposal,
    *,
    governance_envelope: Any | None,
) -> CheckResult:
    """Fail closed only on host-owned target and active-surface constraints."""

    t0 = time.monotonic_ns()
    if governance_envelope is None:
        return _cr(
            "C0_governance_constraints",
            True,
            "light",
            "no host governance constraints declared",
            t0,
        )
    to_primitive = getattr(governance_envelope, "to_primitive", None)
    if not callable(to_primitive):
        return _cr(
            "C0_governance_constraints",
            False,
            "heavy",
            "governance envelope does not expose to_primitive()",
            t0,
        )
    payload = to_primitive()
    if not isinstance(payload, dict):
        return _cr(
            "C0_governance_constraints",
            False,
            "heavy",
            "governance envelope primitive must be an object",
            t0,
        )

    actual_surface = str(h.change_locus or "").strip()
    actual_action = str(h.action or "").strip()
    actual_target = str(h.target_file or "").strip()
    task_authority = payload.get("provider_task_constraint_authority")
    forced_constraint_active = False
    if task_authority is not None:
        if not isinstance(task_authority, Mapping):
            return _cr(
                "C0_governance_constraints",
                False,
                "heavy",
                "provider task constraint authority must be an object",
                t0,
            )
        provider_keys = task_authority.get("provider_keys")
        expected_digest = str(
            task_authority.get("provider_values_digest") or ""
        ).strip()
        allowed_keys = {
            "forced_surface",
            "forced_action",
            "forced_target_file",
        }
        if (
            not isinstance(provider_keys, list)
            or not provider_keys
            or any(key not in allowed_keys for key in provider_keys)
            or not expected_digest
        ):
            return _cr(
                "C0_governance_constraints",
                False,
                "heavy",
                "provider task constraint authority is incomplete",
                t0,
            )
        inactive_digests = {
            hashlib.sha256(
                json.dumps(
                    {key: inactive for key in provider_keys},
                    ensure_ascii=True,
                    separators=(",", ":"),
                    sort_keys=False,
                ).encode("utf-8")
            ).hexdigest()
            for inactive in (None, "")
        }
        if expected_digest in inactive_digests:
            task_authority = None
        actual_values = {
            key: {
                "forced_surface": actual_surface,
                "forced_action": actual_action,
                "forced_target_file": actual_target or None,
            }[key]
            for key in provider_keys
        }
        actual_digest = hashlib.sha256(
            json.dumps(
                actual_values,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=False,
            ).encode("utf-8")
        ).hexdigest()
        if task_authority is not None and actual_digest != expected_digest:
            return _cr(
                "C0_governance_constraints",
                False,
                "heavy",
                "formal hypothesis contradicts provider-visible host task constraints",
                t0,
            )
        forced_constraint_active = (
            task_authority is not None and "forced_surface" in provider_keys
        )

    boundary_value = payload.get("active_problem_boundary_surfaces")
    if isinstance(boundary_value, str):
        active_surfaces = (boundary_value.strip(),) if boundary_value.strip() else ()
    elif isinstance(boundary_value, (list, tuple, set, frozenset)):
        active_surfaces = tuple(
            str(item or "").strip()
            for item in boundary_value
            if str(item or "").strip()
        )
    else:
        active_surfaces = ()
    if (
        not forced_constraint_active
        and active_surfaces
        and actual_surface not in active_surfaces
    ):
        return _cr(
            "C0_governance_constraints",
            False,
            "heavy",
            "change_locus must stay inside active problem surfaces "
            f"{list(active_surfaces)!r}; got {actual_surface!r}",
            t0,
        )
    return _cr(
        "C0_governance_constraints",
        True,
        "light",
        "host target and active-surface constraints satisfied",
        t0,
    )


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
