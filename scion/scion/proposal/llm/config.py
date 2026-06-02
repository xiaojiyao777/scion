"""Configuration helpers for LLMClient."""
from __future__ import annotations

import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)

_BACKOFF_DELAYS = (5.0, 15.0)

# Truncation recovery
MAX_TRUNCATION_RETRIES = 2
MAX_MAX_TOKENS = 16384

# Default config — aihubmix Anthropic endpoint
_DEFAULT_BASE_URL = "https://aihubmix.com"
_DEFAULT_MODEL = "claude-opus-4-6"
_DEFAULT_TIMEOUT_SEC = 60.0
_DEFAULT_MAX_RETRIES = 2
_DEFAULT_SDK_MAX_RETRIES = 0
_DEFAULT_MAX_TOKENS = 16384
_DEFAULT_CODE_TIMEOUT_SEC = 180.0
_DEFAULT_CODE_MAX_RETRIES = 0
_DEFAULT_TRANSIENT_PROVIDER_MAX_RETRIES = 1
LLM_TRANSIENT_API_ERROR_CATEGORY = "llm_transient_api_error"

_ANTHROPIC_MODEL_PREFIXES = ("claude-",)
_DEEPSEEK_MODEL_PREFIXES = ("deepseek-",)
_GPT_CODEX_MODEL_PREFIXES = ("gpt-", "codex-")
_DEEPSEEK_MAX_ALIASES = {"v4pro-max", "deepseek-v4-pro-max"}
_CODE_REQUEST_KINDS = {"code", "fix"}
_TOOL_REQUEST_KIND_BY_NAME = {
    "generate_patch": "code",
    "fix_patch": "fix",
    "generate_hypothesis": "hypothesis",
    "select_hypothesis_target_intent": "hypothesis_target_intent",
    "plan_proposal_tool_call": "tool_selection",
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


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return int(default)
    try:
        return max(0, int(raw))
    except ValueError:
        logger.warning("Ignoring invalid %s=%r; using %d", name, raw, default)
        return int(default)


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return float(default)
    try:
        return max(0.001, float(raw))
    except ValueError:
        logger.warning("Ignoring invalid %s=%r; using %.3f", name, raw, default)
        return float(default)
