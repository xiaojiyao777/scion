"""Bounded source-only research before one direct code proposal is finalized."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal

from scion.core.code_research_limits import CodeResearchLimits
from scion.core.models import PatchProposal
from scion.core.paths import normalize_relative_patch_path
from scion.proposal.bounded_research import (
    BoundedMatchCollector,
    BoundedResearchBudget,
    iter_text_lines,
    text_line_count,
)
from scion.proposal.bounded_research import bounded_json as _bounded_json
from scion.proposal.bounded_research import nonempty_text as _nonempty_text
from scion.proposal.bounded_research import require_exact_keys as _require_exact_keys
from scion.proposal.bounded_research import tool_error as _tool_error
from scion.proposal.edit_protocol.source_discovery import (
    all_source_files_from_context,
    public_test_files_from_context,
    research_files_from_context,
)
from scion.proposal.engine.code_prompts import _split_code_context
from scion.proposal.engine.exceptions import ProposalValidationError
from scion.proposal.engine.parsing import _parse_patch
from scion.proposal.engine.provider_call import PromptTurnSnapshot
from scion.proposal.schemas import PATCH_PROPOSAL_SCHEMA

_MAX_PATH_CHARS = 4096
_MAX_QUERY_CHARS = 256
_MAX_ABANDON_REASON_CHARS = 2000
_MAX_EVIDENCE_REFS_PER_CHANGE = 32


@dataclass(frozen=True)
class CodeResearchCommand:
    """One strictly parsed source research action."""

    action: Literal[
        "read_source",
        "search_source",
        "revise",
        "test_patch",
        "ready",
    ]
    path: str | None = None
    query: str | None = None
    patch: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class CodeResearchFinalDecision:
    """Independent confirmation of the frozen ready candidate, or abandon."""

    outcome: Literal["finalize_patch", "abandon"]
    reason: str | None = None


@dataclass(frozen=True)
class CodeResearchAbandon:
    """Explicit provider decision not to submit a code candidate."""

    reason: str


CodeResearchResult = PatchProposal | CodeResearchAbandon


def bind_code_research_turn_tool(limits: CodeResearchLimits) -> dict[str, Any]:
    """Bind the ready patch schema to the host-enforced session limits."""

    patch_schema = deepcopy(PATCH_PROPOSAL_SCHEMA)
    patch_schema["properties"]["additional_changes"]["maxItems"] = max(
        0, limits.max_patch_files - 1
    )
    _bound_patch_string_fields(patch_schema, limits.max_patch_chars)
    return {
        "name": "code_research_turn",
        "description": (
            "Take exactly one bounded source-research action. read_source reveals "
            "one exact source from the listed source corpus; search_source performs "
            "case-sensitive literal search only; revise stages a typed draft; "
            "test_patch runs host-selected public development checks on that frozen "
            "draft; ready (with no patch field) freezes only the latest draft whose "
            "latest test_patch outcome passed; "
            "patch that a later independent final decision may confirm."
        ),
        "input_schema": {
            "oneOf": [
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["action", "patch"],
                    "properties": {
                        "action": {"type": "string", "enum": ["revise"]},
                        "patch": patch_schema,
                    },
                },
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["action"],
                    "properties": {
                        "action": {"type": "string", "enum": ["test_patch"]},
                    },
                },
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["action", "path"],
                    "properties": {
                        "action": {"type": "string", "enum": ["read_source"]},
                        "path": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": _MAX_PATH_CHARS,
                        },
                    },
                },
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["action", "query"],
                    "properties": {
                        "action": {"type": "string", "enum": ["search_source"]},
                        "query": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": _MAX_QUERY_CHARS,
                        },
                        "path": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": _MAX_PATH_CHARS,
                        },
                    },
                },
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["action"],
                    "properties": {
                        "action": {"type": "string", "enum": ["ready"]},
                    },
                },
            ]
        },
    }


CODE_RESEARCH_FINALIZE_TOOL: dict[str, Any] = {
    "name": "finalize_code_research",
    "description": (
        "Either confirm the exact candidate already frozen by ready, without "
        "supplying or changing it, or explicitly abandon the code proposal."
    ),
    "input_schema": {
        "oneOf": [
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["outcome"],
                "properties": {
                    "outcome": {"type": "string", "enum": ["finalize_patch"]}
                },
            },
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["outcome", "reason"],
                "properties": {
                    "outcome": {"type": "string", "enum": ["abandon"]},
                    "reason": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": _MAX_ABANDON_REASON_CHARS,
                    },
                },
            },
        ]
    },
}


class CodeResearchSession:
    """Run finite provider-backed source research, then one final decision."""

    def __init__(
        self,
        creative: Any,
        limits: CodeResearchLimits,
        *,
        test_patch: Callable[
            [PatchProposal, float, Mapping[str, str]], Mapping[str, Any]
        ]
        | None = None,
    ) -> None:
        self._creative = creative
        self._limits = limits
        self._budget = BoundedResearchBudget(
            limits,
            label="code research",
            provider_cap=limits.max_turns + 1,
        )
        self._test_patch = test_patch
        self._test_calls = 0
        self._test_result_chars = 0
        self._test_elapsed_sec = 0.0

    @property
    def provider_calls_used(self) -> int:
        """Number of locally admitted calls that reached provider dispatch."""

        return self._budget.provider_calls

    def run(self, full_snapshot: PromptTurnSnapshot) -> CodeResearchResult:
        """Research only the frozen source map and return a patch or abandon."""

        if full_snapshot.render_kind != "code":
            raise ValueError("code research requires a code prompt snapshot")
        full_context = full_snapshot.structured_context
        approved_hypothesis = deepcopy(full_context.get("approved_hypothesis"))
        source_context = deepcopy(full_context.get("editable_source_context"))
        if not isinstance(approved_hypothesis, Mapping):
            raise TypeError("code research requires an approved hypothesis")
        if not isinstance(source_context, Mapping):
            raise TypeError("code research requires editable source context")

        editable_corpus = all_source_files_from_context(
            {"editable_source_context": source_context}
        )
        public_test_corpus = public_test_files_from_context(
            {"editable_source_context": source_context}
        )
        corpus = research_files_from_context(
            {"editable_source_context": source_context}
        )
        target, initial_paths = _source_inventory(source_context)
        visible_paths = {path for path in initial_paths if path in corpus}
        draft_patch: PatchProposal | None = None
        draft_raw: Mapping[str, Any] | None = None
        draft_revision = 0
        last_tested_revision = 0
        last_test_outcome: str | None = None
        ready_patch: PatchProposal | None = None
        ready_raw: Mapping[str, Any] | None = None

        for turn_index in range(self._limits.max_turns):
            context = self._provider_context(
                approved_hypothesis=approved_hypothesis,
                source_context=source_context,
                corpus=corpus,
                visible_paths=visible_paths,
                turn_index=turn_index,
                draft_patch=draft_raw,
                draft_revision=draft_revision,
                ready_patch=None,
            )
            snapshot = _research_snapshot(
                context,
                provider_tool=bind_code_research_turn_tool(self._limits),
                user_prompt=(
                    "Choose exactly one bounded research action. Use read_source "
                    "for exact current source, search_source for case-sensitive "
                    "literal discovery, revise to stage a complete typed draft, "
                    "test_patch to run the host-selected public checks on that "
                    "draft, or ready to freeze the latest candidate. Do not assume "
                    "filesystem or command access. ready has no patch field and is "
                    "valid only after the latest draft passes test_patch."
                ),
            )
            raw = self._call_provider(
                snapshot,
                lambda snapshot=snapshot: self._creative.call_code_research_turn(
                    snapshot
                ),
            )
            self._record_action(raw)
            command = _parse_research_command(raw)
            if command.action == "read_source":
                result = self._read_source(command.path, corpus, visible_paths)
            elif command.action == "search_source":
                result = self._search_source(command.path, command.query, corpus)
            elif command.action == "revise":
                assert command.patch is not None
                try:
                    _validate_patch_bounds(command.patch, self._limits)
                    _require_existing_patch_sources_visible(
                        command.patch,
                        existing_paths=frozenset(editable_corpus),
                        visible_paths=frozenset(visible_paths),
                        public_test_paths=frozenset(public_test_corpus),
                    )
                    parsed = _parse_patch(
                        command.patch,
                        context=snapshot.structured_context,
                    )
                except ProposalValidationError as exc:
                    result = _tool_error(
                        "revise",
                        _patch_validation_reason(exc),
                    )
                else:
                    draft_patch = deepcopy(parsed)
                    draft_raw = deepcopy(dict(command.patch))
                    draft_revision += 1
                    last_test_outcome = None
                    ready_patch = None
                    ready_raw = None
                    result = {
                        "action": command.action,
                        "ok": True,
                        "draft_revision": draft_revision,
                    }
            elif command.action == "test_patch":
                result = self._run_test_patch(
                    draft_patch,
                    draft_revision=draft_revision,
                    corpus=editable_corpus,
                )
                last_tested_revision = draft_revision
                last_test_outcome = (
                    str(result.get("outcome")) if result.get("ok") else None
                )
                if last_test_outcome == "passed" and draft_patch is not None:
                    ready_patch = deepcopy(draft_patch)
                    ready_raw = deepcopy(dict(draft_raw or {}))
                else:
                    ready_patch = None
                    ready_raw = None
            else:
                if draft_patch is None:
                    result = _tool_error("ready", "draft_required")
                elif (
                    last_tested_revision != draft_revision
                    or last_test_outcome != "passed"
                ):
                    result = _tool_error("ready", "latest_draft_not_passing")
                else:
                    ready_patch = deepcopy(draft_patch)
                    ready_raw = deepcopy(dict(draft_raw or {}))
                    result = {
                        "action": "ready",
                        "ok": True,
                        "draft_revision": draft_revision,
                    }
            self._record_tool_result(result)
            if command.action == "ready" and result.get("ok") is True:
                break

        final_context = self._provider_context(
            approved_hypothesis=approved_hypothesis,
            source_context=source_context,
            corpus=corpus,
            visible_paths=visible_paths,
            turn_index=min(self._limits.max_turns, len(self._budget.results)),
            draft_patch=draft_raw,
            draft_revision=draft_revision,
            ready_patch=ready_raw,
        )
        final_snapshot = _research_snapshot(
            final_context,
            provider_tool=deepcopy(CODE_RESEARCH_FINALIZE_TOOL),
            user_prompt=(
                "Make one independent final decision. Confirm the exact frozen "
                "ready candidate with finalize_patch, or explicitly abandon it. "
                "You cannot supply or alter a patch in this turn."
            ),
        )
        final_raw = self._call_provider(
            final_snapshot,
            lambda: self._creative.call_code_research_finalize(final_snapshot),
        )
        self._record_action(final_raw)
        decision = _parse_final_decision(final_raw)
        if decision.outcome == "abandon":
            return CodeResearchAbandon(reason=decision.reason or "abandoned")
        if ready_patch is None:
            raise ProposalValidationError(
                "finalize_patch requires the latest draft to pass development checks"
            )
        return deepcopy(ready_patch)

    def _provider_context(
        self,
        *,
        approved_hypothesis: Mapping[str, Any],
        source_context: Mapping[str, Any],
        corpus: Mapping[str, str],
        visible_paths: set[str],
        turn_index: int,
        draft_patch: Mapping[str, Any] | None,
        draft_revision: int,
        ready_patch: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        visible_source_context = {
            "approved_target": source_context["approved_target"],
            "sources": [
                {
                    **dict(entry),
                    "visible": str(entry["path"]) in visible_paths,
                    "content": (
                        corpus[str(entry["path"])]
                        if str(entry["path"]) in visible_paths
                        and str(entry["path"]) in corpus
                        else None
                    ),
                }
                for entry in source_context["sources"]
            ],
            "public_tests": [
                {
                    **dict(entry),
                    "visible": str(entry["path"]) in visible_paths,
                    "content": (
                        corpus[str(entry["path"])]
                        if str(entry["path"]) in visible_paths
                        and str(entry["path"]) in corpus
                        else None
                    ),
                }
                for entry in source_context["public_tests"]
            ],
            "target_api_guidance": source_context["target_api_guidance"],
        }
        state: dict[str, Any] = {
            "max_action_bytes": self._limits.max_action_bytes,
            "turn_index": turn_index,
            "remaining_research_turns": max(0, self._limits.max_turns - turn_index),
            "remaining_read_calls": max(
                0, self._limits.max_read_calls - self._budget.read_calls
            ),
            "remaining_search_calls": max(
                0, self._limits.max_search_calls - self._budget.search_calls
            ),
            "remaining_test_calls": max(
                0, self._limits.max_test_calls - self._test_calls
            ),
            "draft_revision": draft_revision,
            "remaining_test_timeout_sec": max(
                0,
                int(self._limits.max_test_total_timeout_sec - self._test_elapsed_sec),
            ),
            "tool_results": deepcopy(self._budget.results),
        }
        if draft_patch is not None:
            state["latest_draft_patch"] = deepcopy(dict(draft_patch))
        if ready_patch is not None:
            state["frozen_ready_patch"] = deepcopy(dict(ready_patch))
        return {
            "approved_hypothesis": deepcopy(dict(approved_hypothesis)),
            "editable_source_context": visible_source_context,
            "code_research": state,
        }

    def _run_test_patch(
        self,
        patch: PatchProposal | None,
        *,
        draft_revision: int,
        corpus: Mapping[str, str],
    ) -> dict[str, Any]:
        if patch is None:
            return _tool_error("test_patch", "draft_required")
        if self._test_calls >= self._limits.max_test_calls:
            return _tool_error("test_patch", "test_call_cap_exhausted")
        remaining_timeout = (
            float(self._limits.max_test_total_timeout_sec) - self._test_elapsed_sec
        )
        if remaining_timeout <= 0:
            return _tool_error("test_patch", "test_total_timeout_exhausted")
        self._test_calls += 1
        if self._test_patch is None:
            projection: Mapping[str, Any] = {
                "outcome": "unavailable",
                "checks": [],
                "counts": {"total": 0, "passed": 0, "failed": 0},
            }
        else:
            started = time.monotonic()
            try:
                projection = self._test_patch(
                    deepcopy(patch),
                    remaining_timeout,
                    deepcopy(dict(corpus)),
                )
            finally:
                elapsed = max(0.0, time.monotonic() - started)
                self._test_elapsed_sec += elapsed
            if elapsed >= remaining_timeout and projection.get("outcome") == "passed":
                projection = {
                    "outcome": "timeout",
                    "checks": [],
                    "counts": {"total": 0, "passed": 0, "failed": 0},
                }
        result = _bounded_test_projection(
            projection,
            draft_revision=draft_revision,
        )
        rendered_chars = len(_bounded_json(result))
        if (
            self._test_result_chars + rendered_chars
            > self._limits.max_test_result_chars
        ):
            raise ProposalValidationError(
                "code research test results exceed max_test_result_chars"
            )
        self._test_result_chars += rendered_chars
        return result

    def _call_provider(
        self,
        snapshot: PromptTurnSnapshot,
        call: Callable[[], Mapping[str, Any]],
    ) -> dict[str, Any]:
        return self._budget.call_provider(snapshot, call)

    def _record_action(self, raw: Mapping[str, Any]) -> None:
        self._budget.record_action(raw)

    def _record_tool_result(self, result: dict[str, Any]) -> None:
        self._budget.record_result(result)

    def _read_source(
        self,
        path: str | None,
        corpus: Mapping[str, str],
        visible_paths: set[str],
    ) -> dict[str, Any]:
        if not self._budget.begin_read():
            return _tool_error("read_source", "read_call_cap_exhausted")
        canonical = _requested_source_path(path)
        if canonical is None:
            return _tool_error("read_source", "invalid_path")
        content = corpus.get(canonical)
        if content is None:
            return _tool_error("read_source", "source_not_visible")
        chars = len(content)
        content_bytes = len(content.encode("utf-8"))
        lines = text_line_count(content)
        if reason := self._budget.reserve_read(content, lines=lines):
            return _tool_error("read_source", reason)
        visible_paths.add(canonical)
        return {
            "action": "read_source",
            "ok": True,
            "path": canonical,
            "chars": chars,
            "bytes": content_bytes,
            "lines": lines,
        }

    def _search_source(
        self,
        path: str | None,
        query: str | None,
        corpus: Mapping[str, str],
    ) -> dict[str, Any]:
        if not self._budget.begin_search():
            return _tool_error("search_source", "search_call_cap_exhausted")
        assert query is not None
        if path is None:
            candidates = tuple(corpus.items())
        else:
            canonical = _requested_source_path(path)
            if canonical is None:
                return _tool_error("search_source", "invalid_path")
            content = corpus.get(canonical)
            if content is None:
                return _tool_error("search_source", "source_not_visible")
            candidates = ((canonical, content),)

        collector = BoundedMatchCollector(
            self._budget,
            action="search_source",
            query=query,
            extra={"truncated": False},
        )
        if collector.exhausted:
            return _tool_error("search_source", "search_result_cap_exhausted")
        truncated = False
        for candidate_path, content in candidates:
            for line_number, line in enumerate(iter_text_lines(content), start=1):
                if query not in line:
                    continue
                if not collector.add(
                    {
                        "path": candidate_path,
                        "line_number": line_number,
                        "line": line,
                    },
                    search_chars=len(candidate_path) + len(line),
                    search_bytes=len(candidate_path.encode("utf-8"))
                    + len(line.encode("utf-8")),
                ):
                    truncated = True
                    break
            if truncated:
                break
        collector.commit()
        return {**collector.result(), "truncated": truncated}


def _research_snapshot(
    context: dict[str, Any],
    *,
    provider_tool: dict[str, Any],
    user_prompt: str,
) -> PromptTurnSnapshot:
    system_blocks, _base_user_prompt = _split_code_context(context)
    research_state = context["code_research"]
    system_blocks.append(
        {
            "type": "text",
            "text": "## Bounded Code Research State\n" + _bounded_json(research_state),
        }
    )
    return PromptTurnSnapshot(
        render_kind="code",
        system_blocks=tuple(system_blocks),
        user_prompt=user_prompt,
        provider_tool=provider_tool,
        structured_context_json=_bounded_json(context),
    )


def _parse_research_command(
    raw: Mapping[str, Any],
) -> CodeResearchCommand:
    action = raw.get("action")
    if action == "read_source":
        _require_exact_keys(raw, {"action", "path"}, label="read_source")
        path = _nonempty_text(raw.get("path"), field="path", maximum=_MAX_PATH_CHARS)
        return CodeResearchCommand(action="read_source", path=path)
    if action == "search_source":
        keys = set(raw)
        if keys not in ({"action", "query"}, {"action", "query", "path"}):
            raise ProposalValidationError(
                "search_source response has unknown or missing fields"
            )
        query = _nonempty_text(
            raw.get("query"), field="query", maximum=_MAX_QUERY_CHARS
        )
        path = None
        if "path" in raw:
            path = _nonempty_text(
                raw.get("path"), field="path", maximum=_MAX_PATH_CHARS
            )
        return CodeResearchCommand(action="search_source", path=path, query=query)
    if action == "revise":
        _require_exact_keys(raw, {"action", "patch"}, label=action)
        patch = raw.get("patch")
        if not isinstance(patch, Mapping):
            raise ProposalValidationError(f"{action} patch must be an object")
        return CodeResearchCommand(action=action, patch=dict(patch))
    if action == "test_patch":
        _require_exact_keys(raw, {"action"}, label="test_patch")
        return CodeResearchCommand(action="test_patch")
    if action == "ready":
        _require_exact_keys(raw, {"action"}, label="ready")
        return CodeResearchCommand(action="ready")
    raise ProposalValidationError(
        "code research action must be read_source, search_source, revise, "
        "test_patch, or ready"
    )


def _parse_final_decision(raw: Mapping[str, Any]) -> CodeResearchFinalDecision:
    outcome = raw.get("outcome")
    if outcome == "finalize_patch":
        _require_exact_keys(raw, {"outcome"}, label="finalize_patch")
        return CodeResearchFinalDecision(outcome="finalize_patch")
    if outcome == "abandon":
        _require_exact_keys(raw, {"outcome", "reason"}, label="abandon")
        reason = _nonempty_text(
            raw.get("reason"),
            field="reason",
            maximum=_MAX_ABANDON_REASON_CHARS,
        )
        return CodeResearchFinalDecision(outcome="abandon", reason=reason)
    raise ProposalValidationError(
        "code research final outcome must be finalize_patch or abandon"
    )


def _source_inventory(source_context: Mapping[str, Any]) -> tuple[str, frozenset[str]]:
    target = source_context.get("approved_target")
    sources = source_context.get("sources")
    public_tests = source_context.get("public_tests")
    if (
        not isinstance(target, str)
        or not isinstance(sources, list)
        or not isinstance(public_tests, list)
    ):
        raise TypeError("editable source context is invalid")
    paths = tuple(
        entry["path"]
        for entry in sources
        if isinstance(entry, Mapping) and isinstance(entry.get("path"), str)
    )
    if len(paths) != len(sources) or target not in paths:
        raise ValueError("editable source context inventory is invalid")
    public_paths = tuple(
        entry["path"]
        for entry in public_tests
        if isinstance(entry, Mapping) and isinstance(entry.get("path"), str)
    )
    if len(public_paths) != len(public_tests) or set(paths) & set(public_paths):
        raise ValueError("editable source context inventory is invalid")
    initial_paths = frozenset(
        str(entry["path"])
        for entry in (*sources, *public_tests)
        if isinstance(entry, Mapping) and entry.get("visible") is True
    )
    return target, initial_paths


def _requested_source_path(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        canonical = normalize_relative_patch_path(value)
    except ValueError:
        return None
    return canonical if canonical == value else None


def _validate_patch_bounds(
    patch: Mapping[str, Any], limits: CodeResearchLimits
) -> None:
    additional = patch.get("additional_changes", [])
    if not isinstance(additional, list):
        raise ProposalValidationError("draft patch additional_changes must be an array")
    if 1 + len(additional) > limits.max_patch_files:
        raise ProposalValidationError("draft patch exceeds max_patch_files")
    if _string_chars(patch) > limits.max_patch_chars:
        raise ProposalValidationError("draft patch exceeds max_patch_chars")
    for change in (patch, *additional):
        if not isinstance(change, Mapping):
            continue
        evidence_refs = change.get("evidence_refs", [])
        if (
            isinstance(evidence_refs, list)
            and len(evidence_refs) > _MAX_EVIDENCE_REFS_PER_CHANGE
        ):
            raise ProposalValidationError(
                "draft patch evidence_refs exceeds the per-change bound"
            )


def _require_existing_patch_sources_visible(
    patch: Mapping[str, Any],
    *,
    existing_paths: frozenset[str],
    visible_paths: frozenset[str],
    public_test_paths: frozenset[str],
) -> None:
    additional = patch.get("additional_changes", [])
    changes = [patch, *(additional if isinstance(additional, list) else [])]
    for change in changes:
        if not isinstance(change, Mapping):
            continue
        path_value = change.get("file_path")
        if not isinstance(path_value, str):
            continue
        path = _requested_source_path(path_value)
        if path is None:
            raise ProposalValidationError(
                "draft patch file_path must be a strict canonical relative path"
            )
        if path in public_test_paths:
            raise ProposalValidationError(
                "draft patch cannot modify a read-only public development test"
            )
        if path in existing_paths and path not in visible_paths:
            raise ProposalValidationError(
                "draft patch references a current source that was not read"
            )


def _bound_patch_string_fields(schema: dict[str, Any], maximum: int) -> None:
    for name, field_schema in schema.get("properties", {}).items():
        if not isinstance(field_schema, dict):
            continue
        if field_schema.get("type") == "string":
            field_schema["maxLength"] = maximum
        if name == "evidence_refs":
            field_schema["maxItems"] = _MAX_EVIDENCE_REFS_PER_CHANGE
            item_schema = field_schema.get("items")
            if isinstance(item_schema, dict):
                item_schema["maxLength"] = min(maximum, 4096)
    additional = schema.get("properties", {}).get("additional_changes")
    if not isinstance(additional, dict):
        return
    item_schema = additional.get("items")
    if isinstance(item_schema, dict):
        _bound_patch_string_fields(item_schema, maximum)


def _string_chars(value: Any) -> int:
    total = 0
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, str):
            total += len(item)
        elif isinstance(item, Mapping):
            stack.extend(item.keys())
            stack.extend(item.values())
        elif isinstance(item, (list, tuple)):
            stack.extend(item)
    return total


def _bounded_test_projection(
    value: Mapping[str, Any],
    *,
    draft_revision: int,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ProposalValidationError("development test result must be an object")
    outcomes = {
        "passed",
        "failed",
        "timeout",
        "launch_error",
        "preflight_rejected",
        "unavailable",
    }
    check_names = {
        "D1_syntax",
        "D1b_undefined_names",
        "D2_interface",
        "D3_unit_tests",
        "D4_regression_tests",
    }
    reason_codes = {
        "syntax_invalid",
        "undefined_names",
        "interface_mismatch",
        "pytest_test_failure",
        "pytest_interrupted",
        "pytest_internal_error",
        "pytest_usage_error",
        "pytest_no_tests_collected",
        "pytest_terminated",
        "suite_timeout",
        "suite_launch_error",
        "suite_preflight_rejected",
        "suite_unavailable",
    }
    outcome = value.get("outcome")
    raw_checks = value.get("checks")
    if outcome not in outcomes or not isinstance(raw_checks, list):
        raise ProposalValidationError("development test result has invalid fields")
    if len(raw_checks) > len(check_names):
        raise ProposalValidationError("development test result has too many checks")
    checks: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw_check in raw_checks:
        if (
            not isinstance(raw_check, Mapping)
            or not set(raw_check).issubset(
                {"name", "outcome", "reason_code", "test_path"}
            )
            or not {"name", "outcome"}.issubset(raw_check)
        ):
            raise ProposalValidationError("development check result is invalid")
        name = raw_check.get("name")
        check_outcome = raw_check.get("outcome")
        reason_code = raw_check.get("reason_code")
        test_path = raw_check.get("test_path")
        if name not in check_names or name in seen or check_outcome not in outcomes:
            raise ProposalValidationError("development check result is invalid")
        if reason_code is not None and reason_code not in reason_codes:
            raise ProposalValidationError("development check result is invalid")
        if test_path is not None:
            try:
                canonical_test_path = normalize_relative_patch_path(test_path)
            except (TypeError, ValueError):
                canonical_test_path = None
            if (
                not isinstance(test_path, str)
                or len(test_path) > _MAX_PATH_CHARS
                or canonical_test_path != test_path
            ):
                raise ProposalValidationError("development check result is invalid")
        checks.append(
            {
                "name": name,
                "outcome": check_outcome,
                **({"reason_code": reason_code} if reason_code is not None else {}),
                **({"test_path": test_path} if test_path is not None else {}),
            }
        )
        seen.add(name)
    passed = sum(check["outcome"] == "passed" for check in checks)
    return {
        "action": "test_patch",
        "ok": True,
        "draft_revision": draft_revision,
        "outcome": outcome,
        "checks": checks,
        "counts": {
            "total": len(checks),
            "passed": passed,
            "failed": len(checks) - passed,
        },
    }


def _patch_validation_reason(error: ProposalValidationError) -> str:
    """Return one safe correction category without echoing provider text."""

    message = str(error).lower()
    categories = (
        ("duplicate file_path", "duplicate_file_path"),
        ("old_string_not_found", "selector_not_found"),
        ("old_line_not_found", "selector_not_found"),
        ("old_string_not_unique", "selector_not_unique"),
        ("old_line_not_unique", "selector_not_unique"),
        ("source unavailable", "source_not_visible"),
        ("was not read", "source_not_read"),
        ("read-only public", "public_test_read_only"),
        ("max_patch_files", "patch_file_cap_exhausted"),
        ("max_patch_chars", "patch_char_cap_exhausted"),
        ("canonical relative path", "invalid_patch_path"),
        ("unknown", "patch_schema_invalid"),
        ("missing", "patch_schema_invalid"),
    )
    return next(
        (reason for token, reason in categories if token in message),
        "patch_validation_failed",
    )


__all__ = [
    "CODE_RESEARCH_FINALIZE_TOOL",
    "CodeResearchAbandon",
    "CodeResearchCommand",
    "CodeResearchFinalDecision",
    "CodeResearchResult",
    "CodeResearchSession",
    "bind_code_research_turn_tool",
]
