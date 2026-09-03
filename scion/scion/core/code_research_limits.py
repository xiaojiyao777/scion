"""Ordinary bounded limits for an optional code research session."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MAX_CODE_RESEARCH_LIMITS_BYTES = 4096
MAX_CODE_RESEARCH_PROBE_SOURCE_CHARS = 20_000
MAX_CODE_RESEARCH_PROBE_TIMEOUT_SEC = 10


@dataclass(frozen=True)
class CodeResearchLimits:
    """Host-enforced limits for one hypothesis/code research session."""

    max_turns: int = 12
    max_read_calls: int = 8
    max_search_calls: int = 8
    max_read_chars: int = 120_000
    max_read_bytes: int = 240_000
    max_search_matches: int = 80
    max_search_chars: int = 20_000
    max_search_bytes: int = 40_000
    max_read_lines: int = 10_000
    max_action_bytes: int = 100_000
    max_patch_files: int = 8
    max_patch_chars: int = 200_000
    max_test_calls: int = 2
    max_test_suite_timeout_sec: int = 30
    max_test_total_timeout_sec: int = 60
    max_test_files: int = 64
    max_test_copy_bytes: int = 5_000_000
    max_test_result_chars: int = 20_000
    max_tool_result_chars: int = 200_000
    max_transcript_chars: int | None = None
    max_hypothesis_candidates: int = 1

    def __post_init__(self) -> None:
        _bounded_int(
            self.max_hypothesis_candidates,
            field="max_hypothesis_candidates",
            minimum=1,
            maximum=2,
        )
        _bounded_int(self.max_turns, field="max_turns", minimum=1, maximum=64)
        _bounded_int(
            self.max_read_calls,
            field="max_read_calls",
            minimum=0,
            maximum=64,
        )
        _bounded_int(
            self.max_search_calls,
            field="max_search_calls",
            minimum=0,
            maximum=64,
        )
        _bounded_int(
            self.max_read_chars,
            field="max_read_chars",
            minimum=1,
            maximum=1_000_000,
        )
        _bounded_int(
            self.max_read_bytes,
            field="max_read_bytes",
            minimum=1,
            maximum=2_000_000,
        )
        _bounded_int(
            self.max_search_matches,
            field="max_search_matches",
            minimum=1,
            maximum=500,
        )
        _bounded_int(
            self.max_search_chars,
            field="max_search_chars",
            minimum=1,
            maximum=100_000,
        )
        _bounded_int(
            self.max_search_bytes,
            field="max_search_bytes",
            minimum=1,
            maximum=200_000,
        )
        _bounded_int(
            self.max_read_lines,
            field="max_read_lines",
            minimum=1,
            maximum=100_000,
        )
        _bounded_int(
            self.max_action_bytes,
            field="max_action_bytes",
            minimum=1_000,
            maximum=500_000,
        )
        _bounded_int(
            self.max_patch_files,
            field="max_patch_files",
            minimum=1,
            maximum=32,
        )
        _bounded_int(
            self.max_patch_chars,
            field="max_patch_chars",
            minimum=1_000,
            maximum=1_000_000,
        )
        _bounded_int(
            self.max_test_calls,
            field="max_test_calls",
            minimum=1,
            maximum=8,
        )
        _bounded_int(
            self.max_test_suite_timeout_sec,
            field="max_test_suite_timeout_sec",
            minimum=1,
            maximum=120,
        )
        _bounded_int(
            self.max_test_total_timeout_sec,
            field="max_test_total_timeout_sec",
            minimum=1,
            maximum=240,
        )
        if self.max_test_total_timeout_sec < self.max_test_suite_timeout_sec:
            raise ValueError(
                "max_test_total_timeout_sec must be at least max_test_suite_timeout_sec"
            )
        _bounded_int(
            self.max_test_files,
            field="max_test_files",
            minimum=1,
            maximum=128,
        )
        _bounded_int(
            self.max_test_copy_bytes,
            field="max_test_copy_bytes",
            minimum=1_000,
            maximum=20_000_000,
        )
        _bounded_int(
            self.max_test_result_chars,
            field="max_test_result_chars",
            minimum=256,
            maximum=100_000,
        )
        _bounded_int(
            self.max_tool_result_chars,
            field="max_tool_result_chars",
            minimum=1_000,
            maximum=1_000_000,
        )
        if self.max_transcript_chars is not None:
            _positive_int(
                self.max_transcript_chars,
                field="max_transcript_chars",
            )

    def to_primitive(self) -> dict[str, int | None]:
        return {
            "max_hypothesis_candidates": self.max_hypothesis_candidates,
            "max_turns": self.max_turns,
            "max_read_calls": self.max_read_calls,
            "max_search_calls": self.max_search_calls,
            "max_read_chars": self.max_read_chars,
            "max_read_bytes": self.max_read_bytes,
            "max_search_matches": self.max_search_matches,
            "max_search_chars": self.max_search_chars,
            "max_search_bytes": self.max_search_bytes,
            "max_read_lines": self.max_read_lines,
            "max_action_bytes": self.max_action_bytes,
            "max_patch_files": self.max_patch_files,
            "max_patch_chars": self.max_patch_chars,
            "max_test_calls": self.max_test_calls,
            "max_test_suite_timeout_sec": self.max_test_suite_timeout_sec,
            "max_test_total_timeout_sec": self.max_test_total_timeout_sec,
            "max_test_files": self.max_test_files,
            "max_test_copy_bytes": self.max_test_copy_bytes,
            "max_test_result_chars": self.max_test_result_chars,
            "max_tool_result_chars": self.max_tool_result_chars,
            "max_transcript_chars": self.max_transcript_chars,
        }


def normalize_code_research_limits(value: Any) -> CodeResearchLimits:
    """Return one strict limits value without aliases or implicit enablement."""

    if isinstance(value, CodeResearchLimits):
        return value
    if not isinstance(value, Mapping):
        raise TypeError("code research limits must be a mapping")
    allowed = {
        "max_hypothesis_candidates",
        "max_turns",
        "max_read_calls",
        "max_search_calls",
        "max_read_chars",
        "max_read_bytes",
        "max_search_matches",
        "max_search_chars",
        "max_search_bytes",
        "max_read_lines",
        "max_action_bytes",
        "max_patch_files",
        "max_patch_chars",
        "max_test_calls",
        "max_test_suite_timeout_sec",
        "max_test_total_timeout_sec",
        "max_test_files",
        "max_test_copy_bytes",
        "max_test_result_chars",
        "max_tool_result_chars",
        "max_transcript_chars",
    }
    unknown = [key for key in value if key not in allowed]
    if unknown:
        raise ValueError(f"unsupported code research limits field: {unknown[0]}")
    return CodeResearchLimits(**dict(value))


def load_code_research_limits(path: Path) -> CodeResearchLimits:
    """Load one small UTF-8 JSON limits value from an explicit path."""

    try:
        size = path.stat().st_size
    except OSError as exc:
        raise ValueError(f"cannot read code research limits: {path}: {exc}") from exc
    if size > MAX_CODE_RESEARCH_LIMITS_BYTES:
        raise ValueError(
            "code research limits file is too large: "
            f"{size} bytes > {MAX_CODE_RESEARCH_LIMITS_BYTES}"
        )
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"cannot read code research limits: {path}: {exc}") from exc
    if len(raw) > MAX_CODE_RESEARCH_LIMITS_BYTES:
        raise ValueError(
            "code research limits file is too large: "
            f"{len(raw)} bytes > {MAX_CODE_RESEARCH_LIMITS_BYTES}"
        )
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid code research limits JSON: {exc}") from exc
    return normalize_code_research_limits(decoded)


def write_code_research_limits(campaign_dir: str, value: Any) -> Path:
    """Write the enabled ordinary limits value in a fresh campaign root."""

    limits = normalize_code_research_limits(value)
    path = Path(campaign_dir) / "code_research_limits.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as output:
        json.dump(limits.to_primitive(), output, indent=2, sort_keys=True)
        output.write("\n")
    return path


def _bounded_int(
    value: Any,
    *,
    field: str,
    minimum: int,
    maximum: int,
) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{field} must be between {minimum} and {maximum}")


def _positive_int(value: Any, *, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field} must be an integer or null")
    if value <= 0:
        raise ValueError(f"{field} must be greater than zero")


__all__ = [
    "MAX_CODE_RESEARCH_LIMITS_BYTES",
    "MAX_CODE_RESEARCH_PROBE_SOURCE_CHARS",
    "MAX_CODE_RESEARCH_PROBE_TIMEOUT_SEC",
    "CodeResearchLimits",
    "load_code_research_limits",
    "normalize_code_research_limits",
    "write_code_research_limits",
]
