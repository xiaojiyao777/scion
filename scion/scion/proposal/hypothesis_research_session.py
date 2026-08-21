"""Bounded problem-neutral research before one hypothesis is finalized."""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from scion.core.code_research_limits import CodeResearchLimits
from scion.proposal.bounded_research import (
    BoundedMatchCollector,
    BoundedResearchBudget,
    bounded_json,
    iter_text_lines,
    nonempty_text,
    require_exact_keys,
    text_line_count,
    tool_error,
)
from scion.proposal.engine.exceptions import ProposalValidationError
from scion.proposal.engine.hypothesis_prompts import _split_hypothesis_context
from scion.proposal.engine.parsing import _parse_hypothesis
from scion.proposal.engine.provider_call import PromptTurnSnapshot
from scion.proposal.hypothesis_research_basis import (
    MAX_HYPOTHESIS_RESEARCH_REF_CHARS,
    HypothesisResearchBasis,
    HypothesisResearchFinalized,
    hypothesis_research_basis_schema,
    parse_hypothesis_research_basis,
)
from scion.proposal.hypothesis_research_corpus import (
    build_hypothesis_research_corpus,
    iter_string_leaves,
)

_MAX_REF_CHARS = MAX_HYPOTHESIS_RESEARCH_REF_CHARS
_MAX_QUERY_CHARS = 256
_MAX_REASON_CHARS = 2000
_FINALIZE_REJECTION_REASONS = frozenset(
    {
        "finalize_payload_invalid",
        "hypothesis_invalid",
        "nearest_prior_refs_not_read_and_cited",
        "read_refs_not_read",
        "research_basis_invalid",
    }
)


@dataclass(frozen=True)
class HypothesisResearchAbstain:
    """Explicit provider decision not to submit a hypothesis."""

    reason: str


HypothesisResearchResult = HypothesisResearchFinalized | HypothesisResearchAbstain


class HypothesisResearchContextError(ValueError):
    """The frozen H corpus cannot support a safe research session."""


def bind_hypothesis_research_turn_tool(
    direct_tool: Mapping[str, Any],
    *,
    visible_refs: Collection[str] | None = None,
    visible_history_refs: Collection[str] | None = None,
    history_refs: Collection[str] | None = None,
    history_read_reserved: bool = False,
) -> dict[str, Any]:
    """Reuse the already surface-bound H schema inside the research tool."""

    if direct_tool.get("name") != "generate_hypothesis" or not isinstance(
        direct_tool.get("input_schema"), Mapping
    ):
        raise ValueError("hypothesis research requires the bound hypothesis tool")
    ref = {"type": "string", "minLength": 1, "maxLength": _MAX_REF_CHARS}
    query = {"type": "string", "minLength": 1, "maxLength": _MAX_QUERY_CHARS}
    allowed_history_refs = None if history_refs is None else sorted(set(history_refs))
    history_ref = deepcopy(ref)
    history_ref["description"] = "Choose one exact ref from history_index."
    if allowed_history_refs:
        history_ref["enum"] = allowed_history_refs
    reserve_notice = (
        " The final shared read call is currently reserved for read_history; "
        "read_source would return read_call_reserved_for_history."
        if history_read_reserved
        else ""
    )
    actions = [
        _action_schema("read_source", required={"ref": ref}),
        _action_schema(
            "search_source", required={"query": query}, optional={"ref": ref}
        ),
    ]
    if allowed_history_refs is None or allowed_history_refs:
        actions.append(_action_schema("read_history", required={"ref": history_ref}))
    actions.append(
        _action_schema(
            "search_history",
            required={"query": query},
            optional=(
                {"ref": history_ref}
                if allowed_history_refs is None or allowed_history_refs
                else None
            ),
        )
    )
    if visible_refs is None or visible_refs:
        actions.append(
            _action_schema(
                "finalize_hypothesis",
                required={
                    "hypothesis": deepcopy(direct_tool["input_schema"]),
                    "research_basis": hypothesis_research_basis_schema(
                        visible_refs=visible_refs,
                        visible_history_refs=visible_history_refs,
                    ),
                },
            )
        )
    actions.append(
        _action_schema(
            "abstain",
            required={
                "reason": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": _MAX_REASON_CHARS,
                }
            },
        )
    )
    return {
        "name": "hypothesis_research_turn",
        "description": (
            "Take one bounded source/history research action, finalize one "
            "hypothesis through the unchanged schema, or abstain. Indexes are "
            "complete ordinary inventories; read/search reveals bodies on demand. "
            "In research_basis, read_refs may cite only refs actually read in this "
            "session. nearest_prior_refs may cite only refs actually revealed by "
            "read_history and must also appear in read_refs; use [] before any "
            "history is read. A rejected finalize consumes one turn and returns "
            "only a fixed correction category." + reserve_notice
        ),
        "input_schema": {"oneOf": actions},
    }


class HypothesisResearchSession:
    """Finite Creative-Layer source/history investigation producing one H."""

    def __init__(self, creative: Any, limits: CodeResearchLimits) -> None:
        self._creative = creative
        self._limits = limits
        self._budget = BoundedResearchBudget(
            limits,
            label="hypothesis research",
            provider_cap=limits.max_turns,
        )

    @property
    def provider_calls_used(self) -> int:
        return self._budget.provider_calls

    def run(
        self,
        full_snapshot: PromptTurnSnapshot,
        *,
        public_sources: Sequence[Mapping[str, Any]] = (),
        qualified_prefixes: tuple[str, ...] = (),
    ) -> HypothesisResearchResult:
        if full_snapshot.render_kind != "hypothesis":
            raise ValueError("hypothesis research requires a hypothesis snapshot")
        original = full_snapshot.structured_context
        try:
            sources, histories, compact = build_hypothesis_research_corpus(
                original,
                public_sources=public_sources,
                qualified_prefixes=qualified_prefixes,
            )
        except (TypeError, ValueError) as exc:
            raise HypothesisResearchContextError(
                f"hypothesis research context is invalid: {type(exc).__name__}:{exc}"
            ) from exc
        visible_sources: set[str] = set()
        visible_histories: set[str] = set()

        for turn in range(self._limits.max_turns):
            history_read_reserved = (
                bool(histories)
                and not visible_histories
                and self._limits.max_read_calls - self._budget.read_calls == 1
            )
            context = self._context(
                compact,
                sources,
                histories,
                visible_sources,
                visible_histories,
                turn,
                history_read_reserved=history_read_reserved,
            )
            snapshot = _research_snapshot(
                context,
                tool=bind_hypothesis_research_turn_tool(
                    full_snapshot.provider_tool,
                    visible_refs=visible_sources | visible_histories,
                    visible_history_refs=visible_histories,
                    history_refs=tuple(entry["ref"] for entry in histories),
                    history_read_reserved=history_read_reserved,
                ),
                allowed_loci=full_snapshot.allowed_change_loci,
            )
            raw = self._budget.call_provider(
                snapshot,
                lambda snapshot=snapshot: self._creative.call_hypothesis_research_turn(
                    snapshot
                ),
            )
            self._budget.record_action(raw)
            try:
                action, payload = _parse_action(raw)
            except ProposalValidationError:
                if raw.get("action") != "finalize_hypothesis":
                    raise
                self._budget.record_result(
                    _finalize_tool_error("finalize_payload_invalid")
                )
                continue
            if action == "finalize_hypothesis":
                try:
                    basis = parse_hypothesis_research_basis(
                        payload["research_basis"],
                        visible_refs=visible_sources | visible_histories,
                        visible_history_refs=visible_histories,
                    )
                except ProposalValidationError as exc:
                    self._budget.record_result(
                        _finalize_tool_error(_basis_validation_reason(exc))
                    )
                    continue
                try:
                    hypothesis = _parse_hypothesis(
                        payload["hypothesis"],
                        allowed_change_loci=full_snapshot.allowed_change_loci,
                    )
                except ProposalValidationError:
                    self._budget.record_result(
                        _finalize_tool_error("hypothesis_invalid")
                    )
                    continue
                return HypothesisResearchFinalized(
                    hypothesis=hypothesis,
                    research_basis=basis,
                )
            if action == "abstain":
                return HypothesisResearchAbstain(payload["reason"])
            if action == "read_source":
                result = (
                    tool_error(action, "read_call_reserved_for_history")
                    if history_read_reserved
                    else self._read(action, payload["ref"], sources, visible_sources)
                )
            elif action == "read_history":
                result = self._read(
                    action,
                    payload["ref"],
                    histories,
                    visible_histories,
                    preserve_failed_call=history_read_reserved,
                )
            else:
                result = self._search(
                    action,
                    payload["query"],
                    payload.get("ref"),
                    sources if action == "search_source" else histories,
                )
            self._budget.record_result(result)
        raise ProposalValidationError(
            "hypothesis research turn cap exhausted without finalize or abstain"
        )

    def _context(
        self,
        compact: Mapping[str, Any],
        sources: Sequence[dict[str, Any]],
        histories: Sequence[dict[str, Any]],
        visible_sources: set[str],
        visible_histories: set[str],
        turn: int,
        *,
        history_read_reserved: bool,
    ) -> dict[str, Any]:
        state = {
            **self._budget.remaining_state(turn=turn),
            "history_read_reserved": history_read_reserved,
            "source_index": [entry["index"] for entry in sources],
            "history_index": [entry["index"] for entry in histories],
            "visible_sources": [
                {"ref": e["ref"], "path": e["path"], "content": e["body"]}
                for e in sources
                if e["ref"] in visible_sources
            ],
            "visible_history": [
                {
                    "ref": e["ref"],
                    "kind": e["kind"],
                    "ordinal": e["ordinal"],
                    "record": e["record"],
                }
                for e in histories
                if e["ref"] in visible_histories
            ],
            "tool_results": deepcopy(self._budget.results),
        }
        return {**deepcopy(dict(compact)), "hypothesis_research": state}

    def _read(
        self,
        action: str,
        ref: str,
        entries: Sequence[dict[str, Any]],
        visible: set[str],
        *,
        preserve_failed_call: bool = False,
    ) -> dict[str, Any]:
        entry = None
        body = None
        if preserve_failed_call:
            entry = next((item for item in entries if item["ref"] == ref), None)
            if entry is None:
                return tool_error(
                    action,
                    f"unknown_{'source' if action.endswith('source') else 'history'}_ref",
                )
            body = entry.get("body")
            if body is None:
                return tool_error(action, "source_unavailable")
        if not self._budget.begin_read():
            return tool_error(action, "read_call_cap_exhausted")
        entry = entry or next((item for item in entries if item["ref"] == ref), None)
        if entry is None:
            return tool_error(
                action,
                f"unknown_{'source' if action.endswith('source') else 'history'}_ref",
            )
        body = body if body is not None else entry.get("body")
        if body is None:
            return tool_error(action, "source_unavailable")
        if ref in visible:
            return {"action": action, "ok": True, "ref": ref, "already_visible": True}
        lines = text_line_count(body)
        reason = self._budget.reserve_read(body, lines=lines)
        if reason:
            if preserve_failed_call:
                self._budget.read_calls -= 1
            return tool_error(action, reason)
        visible.add(ref)
        return {
            "action": action,
            "ok": True,
            "ref": ref,
            "chars": len(body),
            "bytes": len(body.encode()),
            "lines": lines,
        }

    def _search(
        self,
        action: str,
        query: str,
        ref: str | None,
        entries: Sequence[dict[str, Any]],
    ) -> dict[str, Any]:
        if not self._budget.begin_search():
            return tool_error(action, "search_call_cap_exhausted")
        selected = (
            list(entries) if ref is None else [e for e in entries if e["ref"] == ref]
        )
        if ref is not None and not selected:
            return tool_error(
                action,
                f"unknown_{'source' if action.endswith('source') else 'history'}_ref",
            )
        collector = BoundedMatchCollector(self._budget, action=action, query=query)
        if collector.exhausted:
            return tool_error(action, "search_result_cap_exhausted")
        if action == "search_source":
            for entry in selected:
                for number, line in enumerate(
                    iter_text_lines(entry.get("body") or ""), 1
                ):
                    if query in line and not collector.add(
                        {
                            "ref": entry["ref"],
                            "path": entry["path"],
                            "line_number": number,
                            "line": line,
                        }
                    ):
                        return tool_error(action, "search_result_cap_exhausted")
        else:
            for entry in selected:
                for path, text in iter_string_leaves(entry["record"]):
                    if query in text and not collector.add(
                        {
                            "ref": entry["ref"],
                            "kind": entry["kind"],
                            "ordinal": entry["ordinal"],
                            "field": path,
                        }
                    ):
                        return tool_error(action, "search_result_cap_exhausted")
        collector.commit()
        return collector.result()


def _action_schema(
    action: str,
    *,
    required: Mapping[str, Any],
    optional: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    properties = {
        "action": {"type": "string", "enum": [action]},
        **deepcopy(dict(required)),
        **deepcopy(dict(optional or {})),
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["action", *required],
        "properties": properties,
    }


def _research_snapshot(
    context: dict[str, Any], *, tool: dict[str, Any], allowed_loci: tuple[str, ...]
) -> PromptTurnSnapshot:
    base = {
        key: value for key, value in context.items() if key != "hypothesis_research"
    }
    blocks, _prompt = _split_hypothesis_context(base)
    blocks.append(
        {
            "type": "text",
            "text": "## Bounded Hypothesis Research State\n"
            + bounded_json(context["hypothesis_research"]),
        }
    )
    return PromptTurnSnapshot(
        render_kind="hypothesis",
        system_blocks=tuple(blocks),
        user_prompt=(
            "Choose one bounded read/search action, finalize_hypothesis after "
            "comparing current source and prior evidence, or abstain. Do not assume "
            "filesystem, Protocol, Decision, benchmark, or hidden holdout access. "
            "For research_basis, cite only refs actually read in this session; "
            "nearest_prior_refs must be histories actually revealed by read_history "
            "and also listed in read_refs, and must be [] while no history is "
            "visible. Observe remaining_read_calls and history_read_reserved: when "
            "the latter is true, the final shared read call is available only to "
            "read_history."
        ),
        provider_tool=tool,
        structured_context_json=bounded_json(context),
        allowed_change_loci=allowed_loci,
    )


def _parse_action(raw: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    action = raw.get("action")
    if action in {"read_source", "read_history"}:
        require_exact_keys(raw, {"action", "ref"}, label=action)
        return action, {
            "ref": nonempty_text(raw["ref"], field="ref", maximum=_MAX_REF_CHARS)
        }
    if action in {"search_source", "search_history"}:
        if set(raw) not in ({"action", "query"}, {"action", "query", "ref"}):
            raise ProposalValidationError(
                f"{action} response has unknown or missing fields"
            )
        payload = {
            "query": nonempty_text(
                raw["query"], field="query", maximum=_MAX_QUERY_CHARS
            )
        }
        if "ref" in raw:
            payload["ref"] = nonempty_text(
                raw["ref"], field="ref", maximum=_MAX_REF_CHARS
            )
        return action, payload
    if action == "finalize_hypothesis":
        require_exact_keys(
            raw, {"action", "hypothesis", "research_basis"}, label=action
        )
        if not isinstance(raw["hypothesis"], Mapping) or not isinstance(
            raw["research_basis"], Mapping
        ):
            raise ProposalValidationError(
                "finalize_hypothesis requires hypothesis and research_basis objects"
            )
        return action, {
            "hypothesis": dict(raw["hypothesis"]),
            "research_basis": dict(raw["research_basis"]),
        }
    if action == "abstain":
        require_exact_keys(raw, {"action", "reason"}, label=action)
        return action, {
            "reason": nonempty_text(
                raw["reason"], field="reason", maximum=_MAX_REASON_CHARS
            )
        }
    raise ProposalValidationError(
        "hypothesis research action must be read_source, search_source, "
        "read_history, search_history, finalize_hypothesis, or abstain"
    )


def _basis_validation_reason(error: ProposalValidationError) -> str:
    """Map basis failures to provider-safe correction categories."""

    message = str(error)
    if "nearest_prior_refs must reference histories read" in message:
        return "nearest_prior_refs_not_read_and_cited"
    if "read_refs must reference sources or histories read" in message:
        return "read_refs_not_read"
    return "research_basis_invalid"


def _finalize_tool_error(reason: str) -> dict[str, Any]:
    """Return only fixed enums, never rejected provider values or validator text."""

    if reason not in _FINALIZE_REJECTION_REASONS:
        raise AssertionError("unknown hypothesis finalize rejection category")
    return tool_error("finalize_hypothesis", reason)


__all__ = [
    "HypothesisResearchAbstain",
    "HypothesisResearchBasis",
    "HypothesisResearchContextError",
    "HypothesisResearchFinalized",
    "HypothesisResearchResult",
    "HypothesisResearchSession",
    "bind_hypothesis_research_turn_tool",
]
