"""Configuration helpers for LLMClient."""
from __future__ import annotations

import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Default config — aihubmix Anthropic endpoint
_DEFAULT_BASE_URL = "https://aihubmix.com"
_DEFAULT_MODEL = "claude-opus-4-6"
_DEFAULT_TIMEOUT_SEC = 60.0
_DEFAULT_CODE_TIMEOUT_SEC = 180.0
_ANTHROPIC_REQUIRED_MAX_TOKENS = 16384
_ANTHROPIC_MODEL_PREFIXES = ("claude-",)
_DEEPSEEK_MODEL_PREFIXES = ("deepseek-",)
_GPT_CODEX_MODEL_PREFIXES = ("gpt-", "codex-")
_DEEPSEEK_MAX_ALIASES = {"v4pro-max", "deepseek-v4-pro-max"}
_CODE_REQUEST_KINDS = {"code", "code_research_finalize", "code_research_turn"}
_TOOL_REQUEST_KIND_BY_NAME = {
    "code_research_turn": "code_research_turn",
    "finalize_code_research": "code_research_finalize",
    "generate_patch": "code",
    "generate_hypothesis": "hypothesis",
}


def _is_openai_model(model: str) -> bool:
    """Non-Anthropic models use the OpenAI-compatible API via aihubmix."""
    return not any(model.startswith(p) for p in _ANTHROPIC_MODEL_PREFIXES)


def _is_deepseek_model(model: str) -> bool:
    return any(model.startswith(p) for p in _DEEPSEEK_MODEL_PREFIXES)


def _is_gpt_codex_model(model: str) -> bool:
    value = str(model or "").strip().lower()
    return any(value.startswith(p) for p in _GPT_CODEX_MODEL_PREFIXES)


def _normalize_model_alias(model: str) -> tuple[str, str]:
    """Return normalized model id plus implied reasoning effort, if any."""
    value = str(model or "").strip()
    if value.lower() in _DEEPSEEK_MAX_ALIASES:
        return "deepseek-v4-pro", "max"
    return value, ""


def _normalize_request_kind(
    *,
    request_kind: str | None = None,
    tool: Dict[str, Any] | None = None,
) -> str | None:
    if request_kind:
        return str(request_kind).strip().lower() or None
    if not tool:
        return None
    name = tool.get("name")
    if not name and isinstance(tool.get("function"), dict):
        name = tool["function"].get("name")
    if name is None:
        return None
    return _TOOL_REQUEST_KIND_BY_NAME.get(str(name), None)


def _request_kind_env_key(request_kind: str | None) -> str | None:
    if not request_kind:
        return None
    cleaned = "".join(
        char.upper() if char.isalnum() else "_"
        for char in str(request_kind)
    ).strip("_")
    return cleaned or None


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return float(default)
    try:
        return max(0.001, float(raw))
    except ValueError:
        logger.warning("Ignoring invalid %s=%r; using %.3f", name, raw, default)
        return float(default)
