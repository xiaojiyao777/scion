"""Structured response parsing and narrow schema repair helpers."""
from __future__ import annotations

import json
from typing import Any, Dict

from .config import _normalize_request_kind
from .errors import LLMFormatError


class ParsingMixin:
    def _normalize_tool_call_result(
        self,
        result: Dict[str, Any],
        *,
        tool: Dict[str, Any],
        request_kind: str | None,
    ) -> Dict[str, Any]:
        """Normalize narrow provider drift in tool-call arguments.

        Some OpenAI-compatible providers cannot use named/required tool choice
        for reasoning models and may omit JSON-schema fields that also have
        downstream semantic defaults. Keep the repair limited to Scion's
        proposal tool planner: ``ToolSelectionInput`` already defaults
        ``intent`` to ``call_tool``, so accepting ``tool_name`` + ``args`` is
        equivalent to what the typed parser would do.
        """
        if not isinstance(result, dict):
            return result
        kind = _normalize_request_kind(request_kind=request_kind, tool=tool)
        tool_name = tool.get("name")
        if kind != "tool_selection" and tool_name != "plan_proposal_tool_call":
            return result

        normalized = dict(result)
        if "tool_name" not in normalized:
            alias = normalized.get("name") or normalized.get("tool")
            if isinstance(alias, str) and alias.strip():
                normalized["tool_name"] = alias.strip()
        if "args" not in normalized:
            if isinstance(normalized.get("arguments"), dict):
                normalized["args"] = dict(normalized["arguments"])
            elif isinstance(normalized.get("input"), dict):
                normalized["args"] = dict(normalized["input"])
        if (
            "intent" not in normalized
            and isinstance(normalized.get("tool_name"), str)
            and normalized["tool_name"].strip()
        ):
            normalized["intent"] = "call_tool"
        return normalized



    def _parse_and_validate(
        self, raw: str, schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract JSON from raw text and check required fields."""
        text = raw.strip()

        # Strip markdown code fences if present
        if "```json" in text:
            try:
                start = text.index("```json") + 7
                end = text.index("```", start)
                text = text[start:end].strip()
            except ValueError:
                pass
        elif "```" in text:
            try:
                start = text.index("```") + 3
                end = text.index("```", start)
                text = text[start:end].strip()
            except ValueError:
                pass

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # LLM often puts raw newlines/tabs inside JSON string values
            # (e.g. code_content with actual line breaks). Try strict=False.
            try:
                data = json.loads(text, strict=False)
            except json.JSONDecodeError as exc:
                raise LLMFormatError(
                    f"Response is not valid JSON: {exc}. Preview: {raw[:300]!r}"
                ) from exc

        if not isinstance(data, dict):
            raise LLMFormatError(
                f"Expected a JSON object, got {type(data).__name__}: {raw[:200]!r}"
            )

        required = schema.get("required", [])
        missing = [k for k in required if k not in data]
        if missing:
            raise LLMFormatError(
                f"Response missing required fields {missing}. Got keys: {list(data.keys())}"
            )

        return data


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
