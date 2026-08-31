"""Bounded problem-neutral research before one hypothesis is finalized."""

from __future__ import annotations

import re
from collections.abc import Callable, Collection, Mapping, Sequence
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
from scion.proposal.hypothesis_candidate_bank import (
    HypothesisCandidateBank,
    candidate_selection_tool_error,
    candidate_stage_tool_error,
    parse_hypothesis_candidate_action,
)
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
    latest_live_failure_frontier_refs,
)

_MAX_REF_CHARS = MAX_HYPOTHESIS_RESEARCH_REF_CHARS
_MAX_QUERY_CHARS = 256
_MAX_REASON_CHARS = 2000
_MAX_FRONTIER_REASON_CHARS = 1000
_FINALIZE_REJECTION_REASONS = frozenset(
    {
        "finalize_payload_invalid",
        "failure_frontier_review_required",
        "frontier_rejected_refs_cited",
        "frontier_used_refs_not_cited",
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


@dataclass(frozen=True)
class HistoryFrontierDisposition:
    """One agent-authored disposition of a live-campaign failure record."""

    ref: str
    disposition: str
    reason: str | None = None

    def to_primitive(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "ref": self.ref,
            "disposition": self.disposition,
        }
        if self.reason is not None:
            value["reason"] = self.reason
        return value


HypothesisResearchResult = HypothesisResearchFinalized | HypothesisResearchAbstain


class HypothesisResearchContextError(ValueError):
    """The frozen H corpus cannot support a safe research session."""


def _no_op_candidate_event() -> None:
    return None


def bind_hypothesis_research_turn_tool(
    direct_tool: Mapping[str, Any],
    *,
    visible_refs: Collection[str] | None = None,
    visible_source_refs: Collection[str] | None = None,
    visible_history_refs: Collection[str] | None = None,
    source_refs: Collection[str] | None = None,
    history_refs: Collection[str] | None = None,
    max_hypothesis_candidates: int = 1,
    staged_candidate_slots: Collection[int] = (),
    history_frontier_refs: Collection[str] = (),
    history_frontier_reviewed: bool = False,
) -> dict[str, Any]:
    """Reuse the already surface-bound H schema inside the research tool."""

    if direct_tool.get("name") != "generate_hypothesis" or not isinstance(
        direct_tool.get("input_schema"), Mapping
    ):
        raise ValueError("hypothesis research requires the bound hypothesis tool")
    staged_slots = HypothesisCandidateBank.normalize_slots(
        max_hypothesis_candidates,
        staged_candidate_slots,
    )
    candidate_mode = max_hypothesis_candidates == 2
    ref = {"type": "string", "minLength": 1, "maxLength": _MAX_REF_CHARS}
    query = {"type": "string", "minLength": 1, "maxLength": _MAX_QUERY_CHARS}
    allowed_history_refs = None if history_refs is None else sorted(set(history_refs))
    history_ref = deepcopy(ref)
    history_ref["description"] = "Choose one exact ref from history_index."
    if allowed_history_refs:
        history_ref["enum"] = allowed_history_refs
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
    frontier_refs = tuple(sorted(set(history_frontier_refs)))
    if frontier_refs and not history_frontier_reviewed:
        frontier_ref = deepcopy(ref)
        frontier_ref["enum"] = list(frontier_refs)
        disposition = {
            "oneOf": [
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["ref", "disposition"],
                    "properties": {
                        "ref": deepcopy(frontier_ref),
                        "disposition": {
                            "type": "string",
                            "enum": ["used"],
                        },
                    },
                },
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["ref", "disposition", "reason"],
                    "properties": {
                        "ref": deepcopy(frontier_ref),
                        "disposition": {
                            "type": "string",
                            "enum": ["rejected"],
                        },
                        "reason": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": _MAX_FRONTIER_REASON_CHARS,
                        },
                    },
                },
            ]
        }
        actions.append(
            _action_schema(
                "review_history_frontier",
                required={
                    "dispositions": {
                        "type": "array",
                        "items": disposition,
                        "minItems": len(frontier_refs),
                        "maxItems": len(frontier_refs),
                    }
                },
            )
        )
    source_read_required = source_refs is not None and bool(source_refs)
    source_read_satisfied = not source_read_required or bool(visible_source_refs)
    frontier_satisfied = not frontier_refs or history_frontier_reviewed
    if (
        (visible_refs is None or bool(visible_refs))
        and source_read_satisfied
        and frontier_satisfied
    ):
        hypothesis = deepcopy(direct_tool["input_schema"])
        research_basis = hypothesis_research_basis_schema(
            visible_refs=visible_refs,
            visible_history_refs=visible_history_refs,
            require_nearest_prior=False,
        )
        if not candidate_mode:
            actions.append(
                _action_schema(
                    "finalize_hypothesis",
                    required={
                        "hypothesis": hypothesis,
                        "research_basis": research_basis,
                    },
                )
            )
        elif len(staged_slots) < max_hypothesis_candidates:
            actions.append(
                _action_schema(
                    "stage_hypothesis_candidate",
                    required={
                        "slot": {
                            "type": "integer",
                            "enum": [len(staged_slots) + 1],
                        },
                        "hypothesis": hypothesis,
                        "research_basis": research_basis,
                    },
                )
            )
        else:
            actions.append(
                _action_schema(
                    "select_hypothesis_candidate",
                    required={
                        "slot": {
                            "type": "integer",
                            "enum": list(staged_slots),
                        }
                    },
                )
            )
    if frontier_satisfied:
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
    if candidate_mode:
        history_guidance = (
            " History reading remains agent-chosen. History use is optional outside "
            "an explicit live failure_frontier review; cite only histories "
            "actually read in this session."
        )
        description = (
            "Read/search, stage exactly two complete hypotheses through the "
            "unchanged schema, select one existing slot, or abstain. Staging "
            "exposes only the next ordinal and never resets a shared budget. "
            "Indexes are complete inventories; bodies appear only after read/search. "
            "An available source requires one successful read_source before staging."
            + history_guidance
            + " When failure_frontier is nonempty, submit one exact batch review "
            "for each candidate before staging that slot: used refs must already "
            "be read; rejected refs need a bounded reason. Each batch must cover "
            "the frontier exactly."
            + " Cite only session-read refs. nearest_prior_refs must be histories "
            "revealed by read_history and also in read_refs; use [] when no "
            "read history is relevant. Rejected staging or "
            "selection consumes one turn and returns only a fixed category."
        )
    else:
        history_guidance = (
            " History reading remains agent-chosen. History use is optional outside "
            "an explicit live failure_frontier review; cite only histories "
            "actually read in this session."
        )
        description = (
            "Take one bounded source/history research action, finalize one "
            "hypothesis through the unchanged hypothesis schema, or abstain. Indexes are "
            "complete ordinary inventories; read/search reveals bodies when requested. "
            "When source_index contains an available entry, finalize is unavailable "
            "until one successful read_source."
            + history_guidance
            + " When failure_frontier is nonempty, submit one exact batch review "
            "before finalizing: used refs must already be read; rejected refs need "
            "a bounded reason. The batch must cover the frontier exactly."
            + " In research_basis, read_refs may cite only refs actually read in this "
            "session. nearest_prior_refs may cite only refs actually revealed by "
            "read_history and must also appear in read_refs; use [] when no read "
            "history is relevant. A rejected finalize consumes one turn "
            "and returns only a fixed correction category."
        )
    return {
        "name": "hypothesis_research_turn",
        "description": description,
        "input_schema": {"oneOf": actions},
    }


class HypothesisResearchSession:
    """Finite Creative-Layer source/history investigation producing one H."""

    def __init__(
        self,
        creative: Any,
        limits: CodeResearchLimits,
        *,
        record_candidate_completed: Callable[[], None] | None = None,
        record_candidate_selected: Callable[[], None] | None = None,
    ) -> None:
        self._creative = creative
        self._limits = limits
        self._record_candidate_completed = (
            record_candidate_completed
            if record_candidate_completed is not None
            else _no_op_candidate_event
        )
        self._record_candidate_selected = (
            record_candidate_selected
            if record_candidate_selected is not None
            else _no_op_candidate_event
        )
        self._budget = BoundedResearchBudget(
            limits,
            label="hypothesis research",
            provider_cap=limits.max_turns,
        )
        self._selected_history_frontier_review: tuple[
            HistoryFrontierDisposition, ...
        ] = ()

    @property
    def provider_calls_used(self) -> int:
        return self._budget.provider_calls

    @property
    def selected_history_frontier_review(
        self,
    ) -> tuple[HistoryFrontierDisposition, ...]:
        """Return the selected session's agent-authored frontier dispositions.

        This is tainted H-session state.  It is intentionally not a Protocol or
        Decision input.  The lineage owner may project it into the selected H
        research basis without changing how the host chooses a hypothesis.
        """

        return self._selected_history_frontier_review

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
            frontier_refs = latest_live_failure_frontier_refs(original)
        except (TypeError, ValueError) as exc:
            raise HypothesisResearchContextError(
                f"hypothesis research context is invalid: {type(exc).__name__}:{exc}"
            ) from exc
        readable_sources = [entry for entry in sources if entry.get("body") is not None]
        frontier_review: tuple[HistoryFrontierDisposition, ...] = ()
        required_read_kinds = int(bool(readable_sources))
        if self._limits.max_read_calls < required_read_kinds:
            raise HypothesisResearchContextError(
                "hypothesis research max_read_calls cannot satisfy mandatory reads"
            )
        candidate_mode = self._limits.max_hypothesis_candidates == 2
        required_frontier_review = int(bool(frontier_refs))
        if candidate_mode and self._limits.max_turns < (
            required_read_kinds + (2 * required_frontier_review) + 3
        ):
            raise HypothesisResearchContextError(
                "hypothesis research max_turns cannot satisfy mandatory reads, "
                "failure-frontier review, two candidate slots, and selection"
            )
        if not candidate_mode and self._limits.max_turns < (
            required_read_kinds + required_frontier_review + 1
        ):
            raise HypothesisResearchContextError(
                "hypothesis research max_turns cannot satisfy mandatory reads, "
                "failure-frontier review when required, and a terminal action"
            )
        visible_sources: set[str] = set()
        visible_histories: set[str] = set()
        candidate_bank = HypothesisCandidateBank() if candidate_mode else None
        candidate_frontier_reviews: dict[
            int, tuple[HistoryFrontierDisposition, ...]
        ] = {}

        for turn in range(self._limits.max_turns):
            all_candidates_reviewed = _candidate_frontier_reviews_are_exact(
                frontier_refs,
                candidate_bank=candidate_bank,
                candidate_frontier_reviews=candidate_frontier_reviews,
            )
            context = self._context(
                compact,
                sources,
                histories,
                visible_sources,
                visible_histories,
                frontier_refs,
                frontier_review,
                candidate_frontier_reviews,
                turn,
                candidate_bank=candidate_bank,
            )
            snapshot_builder = (
                _candidate_research_snapshot if candidate_mode else _research_snapshot
            )
            snapshot = snapshot_builder(
                context,
                tool=bind_hypothesis_research_turn_tool(
                    full_snapshot.provider_tool,
                    visible_refs=visible_sources | visible_histories,
                    visible_source_refs=visible_sources,
                    visible_history_refs=visible_histories,
                    source_refs=tuple(entry["ref"] for entry in readable_sources),
                    history_refs=tuple(entry["ref"] for entry in histories),
                    max_hypothesis_candidates=(self._limits.max_hypothesis_candidates),
                    staged_candidate_slots=(
                        candidate_bank.staged_slots
                        if candidate_bank is not None
                        else ()
                    ),
                    history_frontier_refs=frontier_refs,
                    history_frontier_reviewed=(
                        _frontier_review_is_exact(frontier_refs, frontier_review)
                        or all_candidates_reviewed
                    ),
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
            ordinal_error = _prevalidate_candidate_ordinal(
                raw,
                candidate_bank=candidate_bank,
            )
            if ordinal_error is not None:
                self._budget.record_result(ordinal_error)
                continue
            try:
                action, payload = _parse_action(raw, candidate_mode=candidate_mode)
            except ProposalValidationError:
                correction = _malformed_action_tool_error(
                    raw,
                    candidate_mode=candidate_mode,
                )
                if correction is None:
                    raise
                self._budget.record_result(correction)
                continue
            frontier_action_error = _frontier_action_error(
                action,
                frontier_refs=frontier_refs,
                frontier_review=frontier_review,
                candidate_bank=candidate_bank,
                candidate_frontier_reviews=candidate_frontier_reviews,
            )
            if frontier_action_error is not None:
                self._budget.record_result(frontier_action_error)
                continue
            resolution = _resolve_hypothesis_action(
                action,
                payload,
                candidate_bank=candidate_bank,
                allowed_change_loci=full_snapshot.allowed_change_loci,
                visible_sources=visible_sources,
                visible_histories=visible_histories,
                readable_sources=readable_sources,
                frontier_used_refs={
                    item.ref for item in frontier_review if item.disposition == "used"
                },
                frontier_rejected_refs={
                    item.ref
                    for item in frontier_review
                    if item.disposition == "rejected"
                },
            )
            if isinstance(resolution, dict):
                if (
                    action == "stage_hypothesis_candidate"
                    and resolution.get("ok") is True
                ):
                    self._record_candidate_completed()
                    if frontier_refs:
                        candidate_frontier_reviews[int(payload["slot"])] = (
                            frontier_review
                        )
                    # K2 candidates own independent scientific dispositions. A
                    # second slot must review the same live frontier for itself.
                    frontier_review = ()
                self._budget.record_result(resolution)
                continue
            if isinstance(resolution, HypothesisResearchFinalized):
                if action == "finalize_hypothesis":
                    self._record_candidate_completed()
                self._record_candidate_selected()
                self._selected_history_frontier_review = (
                    candidate_frontier_reviews.get(int(payload["slot"]), ())
                    if action == "select_hypothesis_candidate"
                    else frontier_review
                )
                return resolution
            if action == "abstain":
                return HypothesisResearchAbstain(payload["reason"])
            if action == "review_history_frontier":
                review_result = _review_history_frontier(
                    payload["dispositions"],
                    frontier_refs=frontier_refs,
                    visible_histories=visible_histories,
                )
                if isinstance(review_result, dict):
                    self._budget.record_result(review_result)
                    continue
                frontier_review = review_result
                self._budget.record_result(
                    {
                        "action": action,
                        "ok": True,
                        "reviewed_refs": len(review_result),
                        "used_refs": sum(
                            item.disposition == "used" for item in review_result
                        ),
                    }
                )
                continue
            if action == "read_source":
                result = self._read(action, payload["ref"], sources, visible_sources)
            elif action == "read_history":
                result = self._read(
                    action,
                    payload["ref"],
                    histories,
                    visible_histories,
                )
            else:
                result = self._search(
                    action,
                    payload["query"],
                    payload.get("ref"),
                    sources if action == "search_source" else histories,
                )
            self._budget.record_result(result)
        if candidate_mode:
            raise ProposalValidationError(
                "hypothesis research turn cap exhausted without two staged "
                "candidates and selection or abstain"
            )
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
        frontier_refs: tuple[str, ...],
        frontier_review: tuple[HistoryFrontierDisposition, ...],
        candidate_frontier_reviews: Mapping[
            int, tuple[HistoryFrontierDisposition, ...]
        ],
        turn: int,
        *,
        candidate_bank: HypothesisCandidateBank | None,
    ) -> dict[str, Any]:
        all_candidates_reviewed = _candidate_frontier_reviews_are_exact(
            frontier_refs,
            candidate_bank=candidate_bank,
            candidate_frontier_reviews=candidate_frontier_reviews,
        )
        state = {
            **self._budget.remaining_state(turn=turn),
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
            "failure_frontier": {
                "scope": "latest_live_relation_round_failures",
                "refs": list(frontier_refs),
                "required": bool(frontier_refs),
                "reviewed": (
                    _frontier_review_is_exact(frontier_refs, frontier_review)
                    or all_candidates_reviewed
                ),
                "dispositions": [item.to_primitive() for item in frontier_review],
                "candidate_dispositions": [
                    {
                        "slot": slot,
                        "dispositions": [
                            item.to_primitive()
                            for item in candidate_frontier_reviews[slot]
                        ],
                    }
                    for slot in sorted(candidate_frontier_reviews)
                ],
            },
            "tool_results": deepcopy(self._budget.results),
        }
        if candidate_bank is not None:
            state["candidate_bank"] = candidate_bank.to_research_projection()
        return {**deepcopy(dict(compact)), "hypothesis_research": state}

    def _read(
        self,
        action: str,
        ref: str,
        entries: Sequence[dict[str, Any]],
        visible: set[str],
    ) -> dict[str, Any]:
        if not self._budget.begin_read():
            return tool_error(action, "read_call_cap_exhausted")
        entry = next((item for item in entries if item["ref"] == ref), None)
        if entry is None:
            return tool_error(
                action,
                f"unknown_{'source' if action.endswith('source') else 'history'}_ref",
            )
        body = entry.get("body")
        if body is None:
            return tool_error(action, "source_unavailable")
        if ref in visible:
            return {"action": action, "ok": True, "ref": ref, "already_visible": True}
        lines = text_line_count(body)
        reason = self._budget.reserve_read(body, lines=lines)
        if reason:
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
        history_tokens = (
            _history_search_tokens(query) if action == "search_history" else ()
        )
        collector = BoundedMatchCollector(
            self._budget,
            action=action,
            query=query,
            extra=(
                {
                    "match_mode": "case_insensitive_token_or",
                    "query_tokens": list(history_tokens),
                }
                if action == "search_history"
                else None
            ),
        )
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
                    if not _history_text_matches(text, history_tokens):
                        continue
                    if not collector.add(
                        {
                            "ref": entry["ref"],
                            "kind": entry["kind"],
                            "ordinal": entry["ordinal"],
                            "field": path,
                        }
                    ):
                        return tool_error(action, "search_result_cap_exhausted")
                    # Search is a ref-discovery surface. One deterministic hit per
                    # ordered record prevents a broad token from exhausting the
                    # bounded result budget on many fields of the same history.
                    break
        collector.commit()
        return collector.result()


def _review_history_frontier(
    raw_dispositions: Sequence[Any],
    *,
    frontier_refs: tuple[str, ...],
    visible_histories: set[str],
) -> tuple[HistoryFrontierDisposition, ...] | dict[str, Any]:
    action = "review_history_frontier"
    if not frontier_refs or len(raw_dispositions) != len(frontier_refs):
        return tool_error(action, "frontier_coverage_invalid")
    parsed: list[HistoryFrontierDisposition] = []
    try:
        for raw in raw_dispositions:
            if not isinstance(raw, Mapping):
                raise ProposalValidationError("frontier disposition must be an object")
            disposition = raw.get("disposition")
            expected = (
                {"ref", "disposition"}
                if disposition == "used"
                else {"ref", "disposition", "reason"}
            )
            require_exact_keys(raw, expected, label="frontier disposition")
            ref = nonempty_text(raw["ref"], field="ref", maximum=_MAX_REF_CHARS)
            if disposition == "used":
                parsed.append(HistoryFrontierDisposition(ref, disposition))
            elif disposition == "rejected":
                parsed.append(
                    HistoryFrontierDisposition(
                        ref,
                        disposition,
                        nonempty_text(
                            raw["reason"],
                            field="reason",
                            maximum=_MAX_FRONTIER_REASON_CHARS,
                        ),
                    )
                )
            else:
                raise ProposalValidationError("frontier disposition is invalid")
    except (KeyError, ProposalValidationError):
        return tool_error(action, "frontier_dispositions_invalid")
    refs = tuple(item.ref for item in parsed)
    if len(refs) != len(set(refs)) or set(refs) != set(frontier_refs):
        return tool_error(action, "frontier_coverage_invalid")
    if any(
        item.disposition == "used" and item.ref not in visible_histories
        for item in parsed
    ):
        return tool_error(action, "frontier_used_refs_not_read")
    order = {ref: ordinal for ordinal, ref in enumerate(frontier_refs)}
    return tuple(sorted(parsed, key=lambda item: order[item.ref]))


def _history_search_tokens(query: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(re.findall(r"\w+", query.casefold())))


def _history_text_matches(text: str, tokens: tuple[str, ...]) -> bool:
    folded = text.casefold()
    return bool(tokens) and any(token in folded for token in tokens)


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
    history_guidance = (
        "History reading remains agent-chosen. If failure_frontier is required, "
        "review every exact frontier ref once as used or rejected before finalizing; "
        "read used refs and cite them in nearest_prior_refs, while rejected refs need "
        "a bounded reason but need not be read. History use is optional outside "
        "that frontier. "
    )
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
            "when source_index contains an available entry, read at least one source "
            "before finalizing; "
            "nearest_prior_refs must be histories actually revealed by read_history "
            "and also listed in read_refs. "
            + history_guidance
            + "When history_index is empty, nearest_prior_refs must be []. "
            "Observe the remaining bounded research budgets."
        ),
        provider_tool=tool,
        structured_context_json=bounded_json(context),
        allowed_change_loci=allowed_loci,
    )


def _candidate_research_snapshot(
    context: dict[str, Any], *, tool: dict[str, Any], allowed_loci: tuple[str, ...]
) -> PromptTurnSnapshot:
    """Render the K2-only ordinal staging and selection instructions."""

    base = _research_snapshot(context, tool=tool, allowed_loci=allowed_loci)
    history_guidance = (
        "History reading remains agent-chosen. If failure_frontier is required, "
        "review every exact frontier ref independently for each candidate before "
        "staging that slot; read used refs and cite them in nearest_prior_refs, "
        "while rejected refs need a bounded reason but need not be read. Only the "
        "selected slot's review is retained. History use is optional outside that "
        "frontier. "
    )
    return PromptTurnSnapshot(
        render_kind=base.render_kind,
        system_blocks=base.system_blocks,
        user_prompt=(
            "Read/search, stage the next ordinal candidate after comparing evidence, "
            "select an existing slot only after both slots, or abstain. Do not "
            "assume filesystem, Protocol, Decision, benchmark, or hidden holdout "
            "access; staging never resets a budget. Cite only session-read refs. "
            "An available source requires one read before staging; "
            "nearest_prior_refs must be read histories also in read_refs. "
            + history_guidance
            + "With no history, nearest_prior_refs must be []. Observe all remaining "
            "bounded research budgets."
        ),
        provider_tool=base.provider_tool,
        structured_context_json=base.structured_context_json,
        allowed_change_loci=base.allowed_change_loci,
    )


def _parse_action(
    raw: Mapping[str, Any], *, candidate_mode: bool = False
) -> tuple[str, dict[str, Any]]:
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
    if action == "review_history_frontier":
        require_exact_keys(raw, {"action", "dispositions"}, label=action)
        dispositions = raw["dispositions"]
        if not isinstance(dispositions, list):
            raise ProposalValidationError(
                "review_history_frontier dispositions must be an array"
            )
        return action, {"dispositions": deepcopy(dispositions)}
    if not candidate_mode and action == "finalize_hypothesis":
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
    if candidate_mode:
        candidate_action = parse_hypothesis_candidate_action(raw)
        if candidate_action is not None:
            return candidate_action
    if action == "abstain":
        require_exact_keys(raw, {"action", "reason"}, label=action)
        return action, {
            "reason": nonempty_text(
                raw["reason"], field="reason", maximum=_MAX_REASON_CHARS
            )
        }
    allowed = (
        "read_source, search_source, read_history, search_history, "
        "review_history_frontier, stage_hypothesis_candidate, "
        "select_hypothesis_candidate, or abstain"
        if candidate_mode
        else (
            "read_source, search_source, read_history, search_history, "
            "review_history_frontier, finalize_hypothesis, or abstain"
        )
    )
    raise ProposalValidationError(f"hypothesis research action must be {allowed}")


def _malformed_action_tool_error(
    raw: Mapping[str, Any],
    *,
    candidate_mode: bool,
) -> dict[str, Any] | None:
    action = raw.get("action")
    if not candidate_mode and action == "finalize_hypothesis":
        return _finalize_tool_error("finalize_payload_invalid")
    if candidate_mode and action == "stage_hypothesis_candidate":
        return candidate_stage_tool_error("candidate_payload_invalid")
    if candidate_mode and action == "select_hypothesis_candidate":
        return candidate_selection_tool_error("candidate_selection_invalid")
    if action == "review_history_frontier":
        return tool_error(action, "frontier_dispositions_invalid")
    return None


def _prevalidate_candidate_ordinal(
    raw: Mapping[str, Any],
    *,
    candidate_bank: HypothesisCandidateBank | None,
) -> dict[str, Any] | None:
    """Reject an existing or out-of-order slot before inspecting its body."""

    if candidate_bank is None or raw.get("action") != "stage_hypothesis_candidate":
        return None
    slot = raw.get("slot")
    if type(slot) is not int:
        return None
    return candidate_bank.prevalidate_stage(slot)


def _frontier_review_is_exact(
    frontier_refs: tuple[str, ...],
    review: Sequence[HistoryFrontierDisposition],
) -> bool:
    """Return whether a nonempty review covers the frontier in chronology order."""

    return bool(frontier_refs) and bool(review) and tuple(
        item.ref for item in review
    ) == frontier_refs


def _candidate_frontier_reviews_are_exact(
    frontier_refs: tuple[str, ...],
    *,
    candidate_bank: HypothesisCandidateBank | None,
    candidate_frontier_reviews: Mapping[
        int, tuple[HistoryFrontierDisposition, ...]
    ],
) -> bool:
    """Return whether both staged K2 slots own exact nonempty reviews."""

    if (
        not frontier_refs
        or candidate_bank is None
        or candidate_bank.staged_slots != (1, 2)
        or set(candidate_frontier_reviews) != {1, 2}
    ):
        return False
    return all(
        _frontier_review_is_exact(
            frontier_refs,
            candidate_frontier_reviews[slot],
        )
        for slot in (1, 2)
    )


def _frontier_action_error(
    action: str,
    *,
    frontier_refs: tuple[str, ...],
    frontier_review: tuple[HistoryFrontierDisposition, ...],
    candidate_bank: HypothesisCandidateBank | None,
    candidate_frontier_reviews: Mapping[
        int, tuple[HistoryFrontierDisposition, ...]
    ],
) -> dict[str, Any] | None:
    """Fail closed on hidden terminal actions without the required review."""

    if not frontier_refs:
        return None
    if action == "finalize_hypothesis" and not _frontier_review_is_exact(
        frontier_refs, frontier_review
    ):
        return _finalize_tool_error("failure_frontier_review_required")
    if action == "stage_hypothesis_candidate" and not _frontier_review_is_exact(
        frontier_refs, frontier_review
    ):
        return candidate_stage_tool_error("failure_frontier_review_required")
    if action == "select_hypothesis_candidate" and not (
        _candidate_frontier_reviews_are_exact(
            frontier_refs,
            candidate_bank=candidate_bank,
            candidate_frontier_reviews=candidate_frontier_reviews,
        )
    ):
        return candidate_selection_tool_error(
            "failure_frontier_reviews_incomplete"
        )
    return None


def _resolve_hypothesis_action(
    action: str,
    payload: Mapping[str, Any],
    *,
    candidate_bank: HypothesisCandidateBank | None,
    allowed_change_loci: tuple[str, ...],
    visible_sources: set[str],
    visible_histories: set[str],
    readable_sources: Sequence[Mapping[str, Any]],
    frontier_used_refs: set[str],
    frontier_rejected_refs: set[str],
) -> HypothesisResearchFinalized | dict[str, Any] | None:
    if action == "select_hypothesis_candidate":
        if candidate_bank is None:
            raise AssertionError("K2 selection requires a candidate bank")
        return candidate_bank.select(payload["slot"])
    if action not in {"finalize_hypothesis", "stage_hypothesis_candidate"}:
        return None
    slot = None
    if action == "stage_hypothesis_candidate":
        if candidate_bank is None:
            raise AssertionError("K2 staging requires a candidate bank")
        slot = payload["slot"]
        ordinal_error = candidate_bank.prevalidate_stage(slot)
        if ordinal_error is not None:
            return ordinal_error
    candidate = _validate_hypothesis_candidate(
        payload,
        action=action,
        allowed_change_loci=allowed_change_loci,
        visible_sources=visible_sources,
        visible_histories=visible_histories,
        readable_sources=readable_sources,
        frontier_used_refs=frontier_used_refs,
        frontier_rejected_refs=frontier_rejected_refs,
    )
    if isinstance(candidate, dict) or action == "finalize_hypothesis":
        return candidate
    if candidate_bank is None or slot is None:
        raise AssertionError("K2 staging requires an ordinal candidate bank")
    stage_error = candidate_bank.stage_validated(slot, candidate)
    if stage_error is not None:
        return stage_error
    return {
        "action": "stage_hypothesis_candidate",
        "ok": True,
        "slot": slot,
        "staged_count": len(candidate_bank.staged_slots),
    }


def _validate_hypothesis_candidate(
    payload: Mapping[str, Any],
    *,
    action: str,
    allowed_change_loci: tuple[str, ...],
    visible_sources: set[str],
    visible_histories: set[str],
    readable_sources: Sequence[Mapping[str, Any]],
    frontier_used_refs: set[str],
    frontier_rejected_refs: set[str],
) -> HypothesisResearchFinalized | dict[str, Any]:
    """Validate one complete H while returning only provider-safe corrections."""

    if not isinstance(payload.get("hypothesis"), Mapping) or not isinstance(
        payload.get("research_basis"), Mapping
    ):
        reason = (
            "candidate_payload_invalid"
            if action == "stage_hypothesis_candidate"
            else "finalize_payload_invalid"
        )
        return _candidate_validation_tool_error(action, reason)
    try:
        hypothesis = _parse_hypothesis(
            payload["hypothesis"],
            allowed_change_loci=allowed_change_loci,
        )
    except ProposalValidationError:
        return _candidate_validation_tool_error(action, "hypothesis_invalid")
    try:
        basis = parse_hypothesis_research_basis(
            payload["research_basis"],
            visible_refs=visible_sources | visible_histories,
            visible_source_refs=visible_sources,
            visible_history_refs=visible_histories,
            require_source_read=bool(readable_sources),
            require_nearest_prior=False,
        )
    except ProposalValidationError as exc:
        return _candidate_validation_tool_error(
            action,
            _basis_validation_reason(exc),
        )
    if not frontier_used_refs <= set(basis.nearest_prior_refs):
        return _candidate_validation_tool_error(
            action,
            "frontier_used_refs_not_cited",
        )
    if frontier_rejected_refs & set(basis.nearest_prior_refs):
        return _candidate_validation_tool_error(
            action,
            "frontier_rejected_refs_cited",
        )
    return HypothesisResearchFinalized(
        hypothesis=hypothesis,
        research_basis=basis,
    )


def _basis_validation_reason(error: ProposalValidationError) -> str:
    """Map basis failures to provider-safe correction categories."""

    message = str(error)
    if "nearest_prior_refs must reference histories read" in message:
        return "nearest_prior_refs_not_read_and_cited"
    if (
        "successful source read" in message
        or "read_refs must reference sources" in message
    ):
        return "read_refs_not_read"
    return "research_basis_invalid"


def _finalize_tool_error(reason: str) -> dict[str, Any]:
    """Return only fixed enums, never rejected provider values or validator text."""

    if reason not in _FINALIZE_REJECTION_REASONS:
        raise AssertionError("unknown hypothesis finalize rejection category")
    return tool_error("finalize_hypothesis", reason)


def _candidate_validation_tool_error(action: str, reason: str) -> dict[str, Any]:
    if action == "finalize_hypothesis":
        return _finalize_tool_error(reason)
    if action == "stage_hypothesis_candidate":
        return candidate_stage_tool_error(reason)
    raise AssertionError("unknown hypothesis candidate validation action")


__all__ = [
    "HistoryFrontierDisposition",
    "HypothesisResearchAbstain",
    "HypothesisResearchBasis",
    "HypothesisResearchContextError",
    "HypothesisResearchFinalized",
    "HypothesisResearchResult",
    "HypothesisResearchSession",
    "bind_hypothesis_research_turn_tool",
]
