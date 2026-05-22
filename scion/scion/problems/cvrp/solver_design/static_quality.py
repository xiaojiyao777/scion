"""Static CVRP solver-design patch quality checks for algorithm smoke."""

from __future__ import annotations

import re
from typing import Any

from scion.core.models import HypothesisProposal, PatchProposal, patch_file_changes
from scion.core.paths import normalize_relative_patch_path


def static_smoke_issue(
    *,
    patch: PatchProposal,
    hypothesis: HypothesisProposal | None,
) -> str | None:
    text = _hypothesis_text(hypothesis)
    changes = _patch_contents_by_path(patch)
    return (
        _double_bridge_semantic_drift_issue(text, changes)
        or _destroy_effect_attribution_issue(hypothesis, changes)
        or _acceptance_effect_attribution_issue(hypothesis, changes)
    )


def _double_bridge_semantic_drift_issue(
    text: str,
    changes: dict[str, str],
) -> str | None:
    if "double bridge" not in text and "double_bridge" not in text:
        return None
    if not _has_any(text, ("cross route", "cross-route", "up to 4 routes", "four routes")):
        return None
    code = "\n".join(changes.values()).lower()
    if "_double_bridge" not in code:
        return None
    if _looks_cross_route_double_bridge(code):
        return None
    return (
        "solver_design static smoke rejected hypothesis/code semantic drift: "
        "the approved hypothesis claims a cross-route or up-to-four-routes "
        "double-bridge perturbation, but the patch implementation appears to "
        "operate on a single route only. Implement the declared cross-route "
        "mechanism or revise the hypothesis before screening."
    )


def _destroy_effect_attribution_issue(
    hypothesis: HypothesisProposal | None,
    changes: dict[str, str],
) -> str | None:
    destroy_code = changes.get("policies/baseline_modules/destroy_repair.py", "")
    if not destroy_code:
        return None
    for mechanism in _mechanism_ids(hypothesis):
        if not _is_destroy_or_removal_mechanism(mechanism):
            continue
        if not _records_move_effect(destroy_code, mechanism):
            continue
        return (
            "solver_design static smoke rejected non-causal destroy telemetry: "
            f"`{mechanism}` records effect telemetry inside destroy_repair.py. "
            "Destroy helpers may record activation/budget while removing "
            "customers, but effect telemetry for a destroy mechanism must be "
            "recorded after repair/acceptance on a feasible candidate or on a "
            "directly attributable accepted improvement."
        )
    return None


def _acceptance_effect_attribution_issue(
    hypothesis: HypothesisProposal | None,
    changes: dict[str, str],
) -> str | None:
    scheduler_code = changes.get("policies/baseline_modules/scheduler.py", "")
    if not scheduler_code:
        return None
    for mechanism in _mechanism_ids(hypothesis):
        if not _is_acceptance_or_temperature_mechanism(mechanism):
            continue
        if not _records_move_effect(scheduler_code, mechanism):
            continue
        return (
            "solver_design static smoke rejected broad-loop acceptance telemetry: "
            f"`{mechanism}` records effect telemetry from scheduler.py. "
            "Acceptance/temperature mechanisms may record activation/budget in "
            "the scheduler loop, but effect telemetry must be tied to the "
            "acceptance decision or a directly attributable accepted move, not "
            "to ordinary ALNS best-improvement bookkeeping."
        )
    return None


def _looks_cross_route_double_bridge(code: str) -> bool:
    if _has_any(
        code,
        (
            "route_a",
            "route_b",
            "route1",
            "route2",
            "src_route",
            "dst_route",
            "source_route",
            "target_route",
        ),
    ):
        return True
    route_refs = re.findall(r"solution\.routes\s*\[[^\]]+\]", code)
    if len(set(route_refs)) >= 2:
        return True
    if len(re.findall(r"for\s+\w+\s+in\s+range\([^)]*len\(solution\.routes\)", code)) >= 2:
        return True
    return False


def _records_move_effect(code: str, mechanism: str) -> bool:
    if not mechanism:
        return False
    pattern = (
        r"record_move\s*\(\s*['\"]"
        + re.escape(mechanism)
        + r"['\"][^)]*(?:delta\s*=|best_improved\s*=\s*1|best_improved\s*=\s*true)"
    )
    return bool(re.search(pattern, code, flags=re.IGNORECASE | re.DOTALL))


def _hypothesis_text(hypothesis: HypothesisProposal | None) -> str:
    if hypothesis is None:
        return ""
    parts = [
        getattr(hypothesis, "hypothesis_text", ""),
        getattr(hypothesis, "target_weakness", ""),
        getattr(hypothesis, "expected_effect", ""),
        getattr(hypothesis, "target_runtime_effect", ""),
    ]
    parts.extend(_mechanism_ids(hypothesis))
    return _normalize(" ".join(str(part or "") for part in parts))


def _mechanism_ids(hypothesis: HypothesisProposal | None) -> tuple[str, ...]:
    if hypothesis is None:
        return ()
    result: list[str] = []
    for change in getattr(hypothesis, "mechanism_changes", ()) or ():
        value = str(getattr(change, "id", "") or "").strip()
        if value:
            result.append(value)
    return tuple(dict.fromkeys(result))


def _patch_contents_by_path(patch: PatchProposal) -> dict[str, str]:
    contents: dict[str, str] = {}
    for change in patch_file_changes(patch):
        try:
            path = normalize_relative_patch_path(change.file_path)
        except ValueError:
            path = str(change.file_path or "")
        if path:
            contents[path] = str(change.code_content or "")
    return contents


def _is_destroy_or_removal_mechanism(mechanism: str) -> bool:
    text = _normalize(mechanism)
    return _has_any(text, ("destroy", "removal", "remove", "cluster"))


def _is_acceptance_or_temperature_mechanism(mechanism: str) -> bool:
    text = _normalize(mechanism)
    return _has_any(text, ("accept", "acceptance", "temperature", "anneal", "sa "))


def _has_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _normalize(text: Any) -> str:
    normalized = str(text or "").lower().replace("_", " ")
    normalized = re.sub(r"[-/]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return f" {normalized} "


__all__ = ["static_smoke_issue"]
