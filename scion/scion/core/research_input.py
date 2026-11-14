"""Bounded ordinary inputs for continuing a research campaign.

The framework validates only the transport shape.  Observation semantics stay
opaque until an optional problem-owned provider projects them for hypothesis
generation.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

MAX_RESEARCH_INPUT_BYTES = 256 * 1024
MAX_RESEARCH_OBSERVATIONS = 64
MAX_RESEARCH_INPUT_DEPTH = 16

_SENSITIVE_INPUT_KEY = re.compile(
    r"(^|_)(access_token|api_key|auth_token|credential|password|secret|token)($|_)"
    r"|(^|_)(raw_prompt|prompt_(text|message|messages))($|_)"
)


def is_sensitive_research_key(key: str) -> bool:
    """Return whether a generic input/context key can carry private material."""

    normalized = re.sub(
        r"[^a-z0-9]+",
        "_",
        key.strip().lower(),
    ).strip("_")
    return normalized == "prompt" or _SENSITIVE_INPUT_KEY.search(normalized) is not None


def normalize_research_input(value: Any) -> dict[str, Any]:
    """Return a detached JSON-compatible research input or raise.

    The accepted envelope is ``{"current_question": str, "observations":
    [mapping, ...]}``.  Observation fields are deliberately not interpreted by
    core code.
    """

    if not isinstance(value, Mapping):
        raise TypeError("research input must be a JSON mapping")
    unknown = [key for key in value if key not in {"current_question", "observations"}]
    if unknown:
        raise ValueError(f"unsupported research input field: {unknown[0]}")
    missing = [key for key in ("current_question", "observations") if key not in value]
    if missing:
        raise ValueError(f"research input requires field: {missing[0]}")

    question = value["current_question"]
    if not isinstance(question, str) or not question.strip():
        raise ValueError("research input current_question must be a nonempty string")
    observations = value["observations"]
    if not isinstance(observations, list):
        raise TypeError("research input observations must be a JSON array")
    if len(observations) > MAX_RESEARCH_OBSERVATIONS:
        raise ValueError(
            "research input has too many observations: "
            f"{len(observations)} > {MAX_RESEARCH_OBSERVATIONS}"
        )

    normalized_observations: list[dict[str, Any]] = []
    for index, observation in enumerate(observations):
        if not isinstance(observation, Mapping):
            raise TypeError(
                f"research input observation {index} must be a JSON mapping"
            )
        normalized = _copy_json_value(
            observation,
            path=f"$.observations[{index}]",
            depth=2,
        )
        if not isinstance(normalized, dict):  # pragma: no cover - guarded above
            raise TypeError(
                f"research input observation {index} must be a JSON mapping"
            )
        normalized_observations.append(normalized)

    normalized_input = {
        "current_question": question,
        "observations": normalized_observations,
    }
    try:
        encoded = json.dumps(
            normalized_input,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise TypeError(f"research input must contain only JSON values: {exc}") from exc
    if len(encoded) > MAX_RESEARCH_INPUT_BYTES:
        raise ValueError(
            "research input is too large: "
            f"{len(encoded)} bytes > {MAX_RESEARCH_INPUT_BYTES}"
        )
    return normalized_input


def write_research_input(campaign_dir: str, value: Any) -> Path:
    """Write the ordinary research input exactly once in a fresh campaign."""

    normalized = normalize_research_input(value)
    path = Path(campaign_dir) / "research_input.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as output:
        json.dump(
            normalized,
            output,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
        output.write("\n")
    return path


def _copy_json_value(value: Any, *, path: str, depth: int) -> Any:
    if depth > MAX_RESEARCH_INPUT_DEPTH:
        raise ValueError(
            f"research input exceeds maximum depth at {path}: "
            f"{MAX_RESEARCH_INPUT_DEPTH}"
        )
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"research input contains non-finite number at {path}")
        return value
    if isinstance(value, Mapping):
        copied: dict[str, Any] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise TypeError(f"research input key at {path} must be a string")
            if is_sensitive_research_key(key):
                raise ValueError(
                    f"forbidden sensitive research input field at {path}.{key}"
                )
            copied[key] = _copy_json_value(
                child,
                path=f"{path}.{key}",
                depth=depth + 1,
            )
        return copied
    if isinstance(value, list):
        return [
            _copy_json_value(
                child,
                path=f"{path}[{index}]",
                depth=depth + 1,
            )
            for index, child in enumerate(value)
        ]
    raise TypeError(
        f"research input contains unsupported value at {path}: {type(value).__name__}"
    )


__all__ = [
    "MAX_RESEARCH_INPUT_BYTES",
    "MAX_RESEARCH_INPUT_DEPTH",
    "MAX_RESEARCH_OBSERVATIONS",
    "is_sensitive_research_key",
    "normalize_research_input",
    "write_research_input",
]
