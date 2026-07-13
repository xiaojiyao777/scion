from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping


_SOURCE_RE = re.compile(
    r"(?m)^(?:###\s+|File:\s*)([^\n]+?)(?:\s+\([^\n]*\))?\n"
    r"(?:[^\n]*\n)*?```(?:python|py)?\n(.*?)\n```",
    re.DOTALL,
)


def ledgerize_code_context(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Convert historical unit-test source strings into a typed SourceLedger."""

    context = dict(raw)
    if "proposal_source_ledger" in context:
        return context
    target = str(context.get("target_file") or "test_target.py").replace("\\", "/").lstrip("/")
    action = str(
        context.get("action")
        or ("create_new" if context.get("target_file_exists") is False else "modify")
    )
    sources: dict[str, str] = {}
    missing_sources: set[str] = set()

    def collect(value: Any, fallback: str = "") -> list[str]:
        if not isinstance(value, str):
            return []
        paths: list[str] = []
        for match in _SOURCE_RE.finditer(value):
            path = match.group(1).strip().replace("\\", "/").lstrip("/")
            content = match.group(2) + "\n"
            if content.lstrip().startswith("# could not read"):
                missing_sources.add(path)
                sources.setdefault(path, "")
            else:
                sources[path] = content
            paths.append(path)
        if fallback and not paths and value and not value.startswith("("):
            sources[fallback] = value
            paths.append(fallback)
        return paths

    target_paths = collect(context.pop("target_file_code", ""), target)
    champion = collect(context.pop("champion_operators_code", ""))
    references = collect(context.pop("reference_operators", ""))
    integration_text = context.pop(
        "solver_design_branch_current_integration_files", ""
    )
    integration = collect(integration_text)
    if isinstance(integration_text, str) and integration_text and not integration:
        integration_path = target + ".integration_fixture.py"
        sources[integration_path] = integration_text
        integration = [integration_path]
    required = collect(context.pop("agentic_required_full_integration_files", ""))
    api_text = str(context.pop("solver_design_api_manifest", "") or "")
    if str(context.get("research_surface_kind") or context.get("research_surface_name") or "") in {
        "solver_design",
        "solver_algorithm",
    }:
        context.setdefault("solver_design_prompt_provider", {})
    if target not in sources:
        sources[target] = "" if action not in {"create", "create_new"} else ""
    entries = []
    for path, content in sources.items():
        create = path == target and action in {"create", "create_new"}
        visible = bool(content) and not create
        owner = (
            "approved_target"
            if path == target
            else "branch_current_integration"
            if path in {*integration, *required}
            else "champion_api_support"
            if path in {*champion, *references}
            else "branch_helper"
        )
        entries.append(
            {
                "path": path,
                "content": content if visible else None,
                "digest": hashlib.sha256(content.encode()).hexdigest() if visible else None,
                "owner": owner,
                "provenance": "branch_workspace" if visible else "new_file_placeholder" if create else "missing_current_source",
                "visibility": "full_current" if visible else "new_file_placeholder" if create else "not_visible",
                "reason": "ok" if visible else "not_found",
            }
        )
    ledger = {
        "schema_version": "proposal-source-ledger.v2",
        "approved_target": target,
        "entries": entries,
        "views": {
            "champion_research": champion,
            "reference": references,
            "api_reference": list(dict.fromkeys([target, *integration])),
            "integration_full": list(
                dict.fromkeys(([] if action in {"create", "create_new"} else [target]) + integration)
            ),
            "integration_summary": [],
            "branch_current": integration,
            "required_full": required,
        },
        "target_api_guidance": api_text,
    }
    if "approved_hypothesis" not in context:
        context["approved_hypothesis"] = {
            "hypothesis_text": str(context.get("hypothesis_text") or "Test hypothesis."),
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
    context["proposal_source_ledger"] = ledger
    return context
