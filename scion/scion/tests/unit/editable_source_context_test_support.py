from __future__ import annotations

import re
from typing import Any, Mapping

_SOURCE_RE = re.compile(
    r"(?m)^(?:###\s+|File:\s*)([^\n]+?)(?:\s+\([^\n]*\))?\n"
    r"(?:[^\n]*\n)*?```(?:python|py)?\n(.*?)\n```",
    re.DOTALL,
)


def editable_code_context(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Convert historical source strings into ordinary editable source context."""

    context = dict(raw)
    if "editable_source_context" in context:
        return context
    target = (
        str(context.get("target_file") or "test_target.py")
        .replace("\\", "/")
        .lstrip("/")
    )
    action = str(
        context.get("action")
        or ("create_new" if context.get("target_file_exists") is False else "modify")
    )
    sources: dict[str, str | None] = {}

    def collect(value: Any, fallback: str = "") -> list[str]:
        if not isinstance(value, str):
            return []
        paths: list[str] = []
        for match in _SOURCE_RE.finditer(value):
            path = match.group(1).strip().replace("\\", "/").lstrip("/")
            content = match.group(2) + "\n"
            sources[path] = (
                None if content.lstrip().startswith("# could not read") else content
            )
            paths.append(path)
        if fallback and not paths and value and not value.startswith("("):
            sources[fallback] = value
            paths.append(fallback)
        return paths

    collect(context.pop("target_file_code", ""), target)
    collect(context.pop("champion_operators_code", ""))
    collect(context.pop("reference_operators", ""))
    integration_text = context.pop("solver_design_branch_current_integration_files", "")
    integration = collect(integration_text)
    if isinstance(integration_text, str) and integration_text and not integration:
        integration_path = target + ".integration_fixture.py"
        sources[integration_path] = integration_text
    collect(context.pop("agentic_required_full_integration_files", ""))
    api_text = str(context.pop("solver_design_api_manifest", "") or "")
    if str(
        context.get("research_surface_kind")
        or context.get("research_surface_name")
        or ""
    ) in {
        "solver_design",
        "solver_algorithm",
    }:
        context.setdefault("solver_design_prompt_provider", {})
    if target not in sources:
        sources[target] = None if action in {"create", "create_new"} else ""
    ordered_paths = [target, *(path for path in sources if path != target)]
    if "approved_hypothesis" not in context:
        context["approved_hypothesis"] = {
            "hypothesis_text": str(
                context.get("hypothesis_text") or "Test hypothesis."
            ),
            "change_locus": str(context.get("change_locus") or "local_search"),
            "action": action,
            "target_file": target,
            "predicted_direction": str(
                context.get("predicted_direction") or "exploratory"
            ),
            "target_weakness": str(context.get("target_weakness") or "test weakness"),
            "expected_effect": str(context.get("expected_effect") or "test effect"),
        }
    for legacy_key in (
        "action",
        "change_locus",
        "expected_effect",
        "hypothesis_detail",
        "hypothesis_implementation_brief",
        "hypothesis_text",
        "predicted_direction",
        "target_file",
        "target_file_exists",
        "target_weakness",
    ):
        context.pop(legacy_key, None)
    context["editable_source_context"] = {
        "approved_target": target,
        "sources": [{"path": path, "content": sources[path]} for path in ordered_paths],
        "target_api_guidance": api_text,
    }
    return context
