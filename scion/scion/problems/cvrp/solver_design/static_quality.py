"""Static CVRP solver-design patch quality checks for algorithm smoke."""

from __future__ import annotations

import ast
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
        _unknown_context_helper_issue(changes)
        or _double_bridge_semantic_drift_issue(text, changes)
        or _destroy_effect_attribution_issue(hypothesis, changes)
        or _acceptance_effect_attribution_issue(hypothesis, changes)
        or _construction_seed_effect_attribution_issue(hypothesis, changes)
    )


def _unknown_context_helper_issue(changes: dict[str, str]) -> str | None:
    code = "\n".join(changes.values())
    match = re.search(
        r"(?:context|self\.context)\.record_context\s*\(\s*['\"]"
        r"([A-Za-z][A-Za-z0-9_]{1,63})_iterations['\"]",
        code,
    )
    if not match and not re.search(
        r"(?:context|self\.context)\.record_context\s*\(",
        code,
    ):
        return None
    example_mechanism = match.group(1) if match else "<mechanism>"
    return (
        "solver_design static smoke rejected unknown telemetry helper "
        "`context.record_context(...)`. The active solver context exposes "
        "`context.record_phase(name, elapsed_ms)`, "
        "`context.record_iteration(phase, count)`, and "
        "`context.record_move(phase, attempted=..., accepted=..., delta=..., "
        "best_improved=...)`. To populate "
        "`solver_algorithm_context_records.<mechanism>_iterations`, call "
        f"`context.record_iteration('{example_mechanism}', count)`."
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


def _construction_seed_effect_attribution_issue(
    hypothesis: HypothesisProposal | None,
    changes: dict[str, str],
) -> str | None:
    if not _is_construction_seed_hypothesis(hypothesis):
        return None
    code_by_path = {
        path: code
        for path, code in changes.items()
        if _is_construction_seed_patch_path(path)
    }
    if not code_by_path:
        return None
    code = "\n".join(code_by_path.values())
    mechanisms = _mechanism_ids(hypothesis)
    if any(_records_move_effect(code, mechanism) for mechanism in mechanisms):
        return None
    mechanism_hint = ", ".join(mechanisms) or "<declared construction seed mechanism>"
    return (
        "solver_design static smoke rejected construction seed activation-only "
        "telemetry: construction seed/portfolio patches must provide direct "
        "same-mechanism objective-effect attribution before downstream ALNS/VNS "
        "can claim the effect. Record a selected-seed-vs-baseline delta with "
        "`context.record_move('<mechanism>', attempted=1, accepted=..., "
        "delta=..., best_improved=...)` under the declared mechanism id. "
        f"Missing direct effect telemetry for: {mechanism_hint}."
    )


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
    if re.search(pattern, code, flags=re.IGNORECASE | re.DOTALL):
        return True
    return _records_move_effect_via_local_alias(code, mechanism)


def _records_move_effect_via_local_alias(code: str, mechanism: str) -> bool:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False

    def visit_block(statements: list[ast.stmt]) -> bool:
        aliases = _local_string_aliases(statements)
        for statement in statements:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if visit_block(statement.body):
                    return True
                continue
            if isinstance(statement, ast.ClassDef):
                continue
            for node in _walk_without_nested_scopes(statement):
                if not isinstance(node, ast.Call):
                    continue
                if _call_name(node) != "record_move":
                    continue
                if not _first_arg_matches(node, mechanism, aliases):
                    continue
                call = ast.unparse(node)
                if re.search(
                    r"(?:delta\s*=|best_improved\s*=\s*1|best_improved\s*=\s*true)",
                    call,
                    flags=re.IGNORECASE | re.DOTALL,
                ):
                    return True
        return False

    return isinstance(tree, ast.Module) and visit_block(tree.body)


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def _first_arg_matches(
    node: ast.Call,
    mechanism: str,
    aliases: dict[str, str],
) -> bool:
    if not node.args:
        return False
    first = node.args[0]
    if isinstance(first, ast.Constant) and first.value == mechanism:
        return True
    if isinstance(first, ast.Name) and aliases.get(first.id) == mechanism:
        return True
    return False


def _local_string_aliases(statements: list[ast.stmt]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    invalid: set[str] = set()
    for statement in statements:
        for node in _walk_without_nested_scopes(statement):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = list(getattr(node, "targets", ())) or [getattr(node, "target", None)]
            value = getattr(node, "value", None)
            literal = value.value if isinstance(value, ast.Constant) and isinstance(value.value, str) else None
            for target in targets:
                if not isinstance(target, ast.Name):
                    continue
                if literal is None:
                    invalid.add(target.id)
                    aliases.pop(target.id, None)
                elif target.id not in invalid:
                    aliases[target.id] = literal
    for name in invalid:
        aliases.pop(name, None)
    return aliases


def _walk_without_nested_scopes(node: ast.AST) -> list[ast.AST]:
    nodes: list[ast.AST] = []

    def visit(current: ast.AST) -> None:
        if current is not node and isinstance(
            current,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
        ):
            return
        nodes.append(current)
        for child in ast.iter_child_nodes(current):
            visit(child)

    visit(node)
    return nodes


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


def _is_construction_seed_hypothesis(
    hypothesis: HypothesisProposal | None,
) -> bool:
    if hypothesis is None:
        return False
    text = _hypothesis_text(hypothesis)
    novelty_text = _normalize(getattr(hypothesis, "novelty_signature", ""))
    combined = f"{text} {novelty_text}"
    return (
        _has_any(
            combined,
            (
                " construction seed ",
                " seed portfolio ",
                " seed selection ",
                " construction portfolio ",
                " initial solution ",
                " clarke wright ",
                " savings seed ",
                " savings selection ",
            ),
        )
        or " construction " in combined
        and _has_any(combined, (" seed ", " portfolio ", " initializer "))
    )


def _is_construction_seed_patch_path(path: str) -> bool:
    try:
        normalized = normalize_relative_patch_path(path)
    except ValueError:
        normalized = str(path or "")
    return normalized in {
        "policies/baseline_modules/construction.py",
        "policies/baseline_modules/scheduler.py",
        "policies/baseline_algorithm.py",
    }


def _has_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _normalize(text: Any) -> str:
    normalized = str(text or "").lower().replace("_", " ")
    normalized = re.sub(r"[-/]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return f" {normalized} "


__all__ = ["static_smoke_issue"]
