"""Small validation helpers shared by bounded Creative-Layer research loops."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator, Mapping
from copy import deepcopy
from typing import Any

from scion.core.code_research_limits import CodeResearchLimits
from scion.core.resource_envelope import ProviderCallCapExhausted
from scion.proposal.engine.exceptions import ProposalValidationError


def bounded_json(value: Any, *, label: str = "research") -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (RecursionError, TypeError, ValueError) as exc:
        raise ProposalValidationError(
            f"{label} value is not bounded JSON: {type(exc).__name__}"
        ) from exc


def nonempty_text(value: Any, *, field: str, maximum: int) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ProposalValidationError(f"{field} must be non-empty trimmed text")
    if len(value) > maximum:
        raise ProposalValidationError(f"{field} exceeds its character bound")
    return value


def require_exact_keys(
    value: Mapping[str, Any], expected: set[str], *, label: str
) -> None:
    if set(value) != expected:
        raise ProposalValidationError(f"{label} response has unknown or missing fields")


def tool_error(action: str, reason: str) -> dict[str, Any]:
    return {"action": action, "ok": False, "reason": reason}


def iter_text_lines(text: str) -> Iterator[str]:
    """Yield normal source lines without allocating a corpus-sized list."""

    boundaries = "\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029"
    start = cursor = 0
    while cursor < len(text):
        marker = text[cursor]
        if marker not in boundaries:
            cursor += 1
            continue
        yield text[start:cursor]
        cursor += 1
        if marker == "\r" and cursor < len(text) and text[cursor] == "\n":
            cursor += 1
        start = cursor
    if start < len(text):
        yield text[start:]


def text_line_count(text: str) -> int:
    return sum(1 for _line in iter_text_lines(text))


class BoundedResearchBudget:
    """Shared finite transcript, read, search, and provider accounting."""

    def __init__(
        self,
        limits: CodeResearchLimits,
        *,
        label: str,
        provider_cap: int,
    ) -> None:
        self.limits = limits
        self.label = label
        self.provider_cap = provider_cap
        self.provider_calls = self.read_calls = self.search_calls = 0
        self.read_chars = self.read_bytes = self.read_lines = 0
        self.search_matches = self.search_chars = self.search_bytes = 0
        self.tool_chars = self.transcript_chars = 0
        self.results: list[dict[str, Any]] = []

    def call_provider(
        self,
        snapshot: Any,
        call: Callable[[], Mapping[str, Any]],
    ) -> dict[str, Any]:
        if self.provider_calls >= self.provider_cap:
            raise ProposalValidationError(
                f"{self.label} local provider call cap exhausted before dispatch"
            )
        prompt_chars = len(
            bounded_json(
                {
                    "system_blocks": list(snapshot.system_blocks),
                    "user_prompt": snapshot.user_prompt,
                    "provider_tool": snapshot.provider_tool,
                }
            )
        )
        if self.transcript_chars + prompt_chars > self.limits.max_transcript_chars:
            raise ProposalValidationError(
                f"{self.label} transcript exceeds max_transcript_chars before dispatch"
            )
        try:
            raw = call()
        except ProviderCallCapExhausted:
            raise
        except BaseException:
            self.transcript_chars += prompt_chars
            self.provider_calls += 1
            raise
        self.transcript_chars += prompt_chars
        self.provider_calls += 1
        if not isinstance(raw, Mapping):
            raise ProposalValidationError(f"{self.label} response must be an object")
        return dict(raw)

    def record_action(self, raw: Mapping[str, Any]) -> None:
        rendered = bounded_json(raw)
        if len(rendered.encode()) > self.limits.max_action_bytes:
            raise ProposalValidationError(
                f"{self.label} action exceeds max_action_bytes"
            )
        self._reserve_transcript(len(rendered))

    def record_result(self, result: dict[str, Any]) -> None:
        size = len(bounded_json(result))
        if self.tool_chars + size > self.limits.max_tool_result_chars:
            raise ProposalValidationError(
                f"{self.label} tool results exceed max_tool_result_chars"
            )
        self._reserve_transcript(size)
        self.tool_chars += size
        self.results.append(deepcopy(result))

    def begin_read(self) -> bool:
        if self.read_calls >= self.limits.max_read_calls:
            return False
        self.read_calls += 1
        return True

    def reserve_read(self, body: str, *, lines: int | None = None) -> str | None:
        chars, body_bytes = len(body), len(body.encode())
        lines = text_line_count(body) if lines is None else lines
        checks = (
            (
                self.read_chars + chars,
                self.limits.max_read_chars,
                "read_char_cap_exhausted",
            ),
            (
                self.read_bytes + body_bytes,
                self.limits.max_read_bytes,
                "read_byte_cap_exhausted",
            ),
            (
                self.read_lines + lines,
                self.limits.max_read_lines,
                "read_line_cap_exhausted",
            ),
            (
                self.tool_chars + chars,
                self.limits.max_tool_result_chars,
                "tool_result_cap_exhausted",
            ),
            (
                self.transcript_chars + chars,
                self.limits.max_transcript_chars,
                "tool_result_cap_exhausted",
            ),
        )
        reason = next(
            (reason for value, maximum, reason in checks if value > maximum), None
        )
        if reason:
            return reason
        self.read_chars += chars
        self.read_bytes += body_bytes
        self.read_lines += lines
        self.tool_chars += chars
        self._reserve_transcript(chars)
        return None

    def begin_search(self) -> bool:
        if self.search_calls >= self.limits.max_search_calls:
            return False
        self.search_calls += 1
        return True

    def search_capacity(self) -> tuple[int, int, int]:
        return (
            self.limits.max_search_matches - self.search_matches,
            self.limits.max_search_chars - self.search_chars,
            self.limits.max_search_bytes - self.search_bytes,
        )

    def commit_search(self, *, matches: int, chars: int, size_bytes: int) -> bool:
        capacity = self.search_capacity()
        if any(
            value > maximum
            for value, maximum in zip((matches, chars, size_bytes), capacity)
        ):
            return False
        self.search_matches += matches
        self.search_chars += chars
        self.search_bytes += size_bytes
        return True

    def remaining_state(self, *, turn: int) -> dict[str, int]:
        return {
            "max_action_bytes": self.limits.max_action_bytes,
            "turn_index": turn,
            "remaining_research_turns": max(0, self.limits.max_turns - turn),
            "remaining_read_calls": max(
                0, self.limits.max_read_calls - self.read_calls
            ),
            "remaining_search_calls": max(
                0, self.limits.max_search_calls - self.search_calls
            ),
        }

    def _reserve_transcript(self, chars: int) -> None:
        if self.transcript_chars + chars > self.limits.max_transcript_chars:
            raise ProposalValidationError(
                f"{self.label} transcript exceeds max_transcript_chars"
            )
        self.transcript_chars += chars


class BoundedMatchCollector:
    """Stop literal-match collection before any configured result bound."""

    def __init__(
        self,
        budget: BoundedResearchBudget,
        *,
        action: str,
        query: str,
        extra: Mapping[str, Any] | None = None,
    ) -> None:
        self._budget = budget
        self._action = action
        self._query = query
        self._extra = dict(extra or {})
        self._matches: list[dict[str, Any]] = []
        rendered = bounded_json(self.result())
        self._chars = len(rendered)
        self._match_chars = self._match_bytes = 0
        self.exhausted = (
            any(value <= 0 for value in self._budget.search_capacity())
            or self._chars
            > self._budget.limits.max_tool_result_chars - self._budget.tool_chars
            or self._chars
            > self._budget.limits.max_transcript_chars - self._budget.transcript_chars
        )

    def add(
        self,
        match: Mapping[str, Any],
        *,
        search_chars: int | None = None,
        search_bytes: int | None = None,
    ) -> bool:
        if self.exhausted:
            return False
        rendered = bounded_json(match)
        separator = 1 if self._matches else 0
        next_chars = self._chars + len(rendered) + separator
        matched_chars = len(rendered) if search_chars is None else search_chars
        matched_bytes = len(rendered.encode()) if search_bytes is None else search_bytes
        next_match_chars = self._match_chars + matched_chars
        next_match_bytes = self._match_bytes + matched_bytes
        match_cap, char_cap, byte_cap = self._budget.search_capacity()
        tool_cap = self._budget.limits.max_tool_result_chars - self._budget.tool_chars
        transcript_cap = (
            self._budget.limits.max_transcript_chars - self._budget.transcript_chars
        )
        if (
            len(self._matches) + 1 > match_cap
            or next_match_chars > char_cap
            or next_match_bytes > byte_cap
            or next_chars > tool_cap
            or next_chars > transcript_cap
        ):
            self.exhausted = True
            return False
        self._matches.append(dict(match))
        self._chars = next_chars
        self._match_chars = next_match_chars
        self._match_bytes = next_match_bytes
        return True

    def result(self) -> dict[str, Any]:
        return {
            "action": self._action,
            "ok": True,
            "query": self._query,
            "matches": deepcopy(self._matches),
            **deepcopy(self._extra),
        }

    def commit(self) -> None:
        if not self._budget.commit_search(
            matches=len(self._matches),
            chars=self._match_chars,
            size_bytes=self._match_bytes,
        ):
            raise ProposalValidationError(
                f"{self._budget.label} search accounting exceeded reserved capacity"
            )


__all__ = [
    "BoundedMatchCollector",
    "BoundedResearchBudget",
    "bounded_json",
    "iter_text_lines",
    "nonempty_text",
    "require_exact_keys",
    "text_line_count",
    "tool_error",
]
