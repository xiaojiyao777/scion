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
    has_usable_history_headline,
    iter_string_leaves,
    nearest_history_headline_ref,
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
    visible_source_refs: Collection[str] | None = None,
    visible_history_refs: Collection[str] | None = None,
    source_refs: Collection[str] | None = None,
    history_refs: Collection[str] | None = None,
    history_read_reserved: bool = False,
    history_headline_audit_available: bool = False,
    max_hypothesis_candidates: int = 1,
    staged_candidate_slots: Collection[int] = (),
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
    source_read_required = source_refs is not None and bool(source_refs)
    history_read_required = bool(allowed_history_refs)
    source_read_satisfied = not source_read_required or bool(visible_source_refs)
    history_read_satisfied = not history_read_required or bool(visible_history_refs)
    if (
        (visible_refs is None or bool(visible_refs))
        and source_read_satisfied
        and (history_read_satisfied or history_headline_audit_available)
    ):
        hypothesis = deepcopy(direct_tool["input_schema"])
        research_basis = hypothesis_research_basis_schema(
            visible_refs=visible_refs,
            visible_history_refs=visible_history_refs,
            require_nearest_prior=(
                history_read_required and bool(visible_history_refs)
            ),
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
            " When history_index has usable headline fields and "
            "stage_hypothesis_candidate is exposed before any history is visible, "
            "that stage may use nearest_prior_refs=[]. If staging is not exposed, "
            "complete an allowed read first. The host first validates that basis, "
            "then may return only one required_history_ref; read and cite that "
            "exact ref before re-staging. Every stage recomputes the ref, so a "
            "pivot may require a different history."
            if history_headline_audit_available
            else (
                " When history_index is nonempty, staging is unavailable until one "
                "successful read_history."
            )
        )
        description = (
            "Read/search, stage exactly two complete hypotheses through the "
            "unchanged schema, select one existing slot, or abstain. Staging "
            "exposes only the next ordinal and never resets a shared budget. "
            "Indexes are complete inventories; bodies appear only after read/search. "
            "An available source requires one successful read_source before staging."
            + history_guidance
            + " Cite only session-read refs. nearest_prior_refs must be histories "
            "revealed by read_history and also in read_refs; use [] only when the "
            "headline audit permits it or history is empty. Rejected staging or "
            "selection consumes one turn and returns only a fixed category."
            + reserve_notice
        )
    else:
        history_guidance = (
            " When history_index has usable headline fields and finalize_hypothesis "
            "is exposed before any history is visible, that finalize may use "
            "nearest_prior_refs=[]. If finalize_hypothesis is not exposed, complete "
            "an allowed read first. The host first "
            "validates that basis, then may return only one required_history_ref; "
            "read and cite that exact ref before re-finalizing. Every finalize "
            "recomputes the ref, so a pivot may require a different history."
            if history_headline_audit_available
            else (
                " When history_index is nonempty, finalize is unavailable until one "
                "successful read_history."
            )
        )
        description = (
            "Take one bounded source/history research action, finalize one "
            "hypothesis through the unchanged hypothesis schema, or abstain. Indexes are "
            "complete ordinary inventories; read/search reveals bodies on demand. "
            "When source_index contains an available entry, finalize is unavailable "
            "until one successful read_source."
            + history_guidance
            + " In research_basis, read_refs may cite only refs actually read in this "
            "session. nearest_prior_refs may cite only refs actually revealed by "
            "read_history and must also appear in read_refs; before the first "
            "history read, use [] only when the headline-audit guidance permits it "
            "or the history inventory is empty. A rejected finalize consumes one "
            "turn and returns a fixed correction category plus, only for this "
            "audit, one existing required_history_ref." + reserve_notice
        )
    return {
        "name": "hypothesis_research_turn",
        "description": description,
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
        readable_sources = [entry for entry in sources if entry.get("body") is not None]
        history_indexes = tuple(entry["index"] for entry in histories)
        history_headline_audit_available = has_usable_history_headline(history_indexes)
        required_read_kinds = int(bool(readable_sources)) + int(bool(histories))
        if self._limits.max_read_calls < required_read_kinds:
            raise HypothesisResearchContextError(
                "hypothesis research max_read_calls cannot satisfy mandatory reads"
            )
        candidate_mode = self._limits.max_hypothesis_candidates == 2
        if candidate_mode and self._limits.max_turns < required_read_kinds + 3:
            raise HypothesisResearchContextError(
                "hypothesis research max_turns cannot satisfy mandatory reads, "
                "two candidate slots, and selection"
            )
        visible_sources: set[str] = set()
        visible_histories: set[str] = set()
        candidate_bank = HypothesisCandidateBank() if candidate_mode else None

        for turn in range(self._limits.max_turns):
            pending_required_history_ref = _pending_required_history_ref(
                self._budget.results,
                visible_histories=visible_histories,
            )
            history_read_reserved = (
                bool(histories)
                and self._limits.max_read_calls - self._budget.read_calls == 1
                and (not visible_histories or pending_required_history_ref is not None)
            )
            context = self._context(
                compact,
                sources,
                histories,
                visible_sources,
                visible_histories,
                turn,
                history_read_reserved=history_read_reserved,
                history_headline_audit_available=history_headline_audit_available,
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
                    history_read_reserved=history_read_reserved,
                    history_headline_audit_available=history_headline_audit_available,
                    max_hypothesis_candidates=(self._limits.max_hypothesis_candidates),
                    staged_candidate_slots=(
                        candidate_bank.staged_slots
                        if candidate_bank is not None
                        else ()
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
            resolution = _resolve_hypothesis_action(
                action,
                payload,
                candidate_bank=candidate_bank,
                allowed_change_loci=full_snapshot.allowed_change_loci,
                visible_sources=visible_sources,
                visible_histories=visible_histories,
                readable_sources=readable_sources,
                histories=histories,
                history_indexes=history_indexes,
            )
            if isinstance(resolution, dict):
                self._budget.record_result(resolution)
                continue
            if isinstance(resolution, HypothesisResearchFinalized):
                return resolution
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
        turn: int,
        *,
        history_read_reserved: bool,
        history_headline_audit_available: bool,
        candidate_bank: HypothesisCandidateBank | None,
    ) -> dict[str, Any]:
        state = {
            **self._budget.remaining_state(turn=turn),
            "history_read_reserved": history_read_reserved,
            "history_headline_audit_available": history_headline_audit_available,
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
        if candidate_bank is not None:
            state["candidate_bank"] = candidate_bank.to_research_projection()
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
    audit_available = bool(
        context["hypothesis_research"].get("history_headline_audit_available")
    )
    history_guidance = (
        "When history_index has usable headline fields, no history is yet visible, "
        "and finalize_hypothesis is exposed, submit the candidate with "
        "nearest_prior_refs=[]. If it is not exposed, complete an allowed read "
        "first. After "
        "the host returns required_history_ref, read it and include it in both "
        "read_refs and nearest_prior_refs before re-finalizing. The host "
        "recomputes this ref from the current candidate on every finalize, so a "
        "pivot may require a different ref. "
        if audit_available
        else (
            "When history_index is nonempty, read at least one history and cite "
            "at least one nearest prior before finalizing. "
        )
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
            "Observe remaining_read_calls "
            "and history_read_reserved: when "
            "the latter is true, the final shared read call is available only to "
            "read_history."
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
    audit_available = bool(
        context["hypothesis_research"].get("history_headline_audit_available")
    )
    history_guidance = (
        "When history_index has usable headline fields, no history is yet visible, "
        "and stage_hypothesis_candidate is exposed, submit the candidate with "
        "nearest_prior_refs=[]. If staging is not exposed, complete an allowed read "
        "first. After the host returns required_history_ref, read it and include it "
        "in both read_refs and nearest_prior_refs before re-staging. The host "
        "recomputes this ref from the current candidate on every stage, so a pivot "
        "may require a different ref. "
        if audit_available
        else (
            "When history_index is nonempty, read at least one history and cite "
            "at least one nearest prior before staging. "
        )
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
            "budgets; history_read_reserved dedicates the final shared read to "
            "read_history."
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
        "stage_hypothesis_candidate, select_hypothesis_candidate, or abstain"
        if candidate_mode
        else (
            "read_source, search_source, read_history, search_history, "
            "finalize_hypothesis, or abstain"
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


def _resolve_hypothesis_action(
    action: str,
    payload: Mapping[str, Any],
    *,
    candidate_bank: HypothesisCandidateBank | None,
    allowed_change_loci: tuple[str, ...],
    visible_sources: set[str],
    visible_histories: set[str],
    readable_sources: Sequence[Mapping[str, Any]],
    histories: Sequence[Mapping[str, Any]],
    history_indexes: Sequence[Mapping[str, Any]],
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
        histories=histories,
        history_indexes=history_indexes,
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
    histories: Sequence[Mapping[str, Any]],
    history_indexes: Sequence[Mapping[str, Any]],
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
            require_nearest_prior=bool(visible_histories),
        )
    except ProposalValidationError as exc:
        return _candidate_validation_tool_error(
            action,
            _basis_validation_reason(exc),
        )
    required_history_ref = nearest_history_headline_ref(
        {
            "hypothesis_text": hypothesis.hypothesis_text,
            "target_file": hypothesis.target_file,
            "change_locus": hypothesis.change_locus,
            "action": hypothesis.action,
            "predicted_direction": hypothesis.predicted_direction,
            "target_weakness": hypothesis.target_weakness,
            "expected_effect": hypothesis.expected_effect,
        },
        history_indexes,
    )
    if (
        required_history_ref is not None
        and required_history_ref not in visible_histories
    ):
        return _nearest_history_audit_tool_error(
            required_history_ref,
            action=action,
        )
    if histories and not visible_histories:
        return _candidate_validation_tool_error(
            action,
            "nearest_prior_refs_not_read_and_cited",
        )
    if required_history_ref is not None and (
        required_history_ref not in basis.read_refs
        or required_history_ref not in basis.nearest_prior_refs
    ):
        return _nearest_history_audit_tool_error(
            required_history_ref,
            action=action,
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


def _nearest_history_audit_tool_error(
    required_ref: str,
    *,
    action: str = "finalize_hypothesis",
) -> dict[str, Any]:
    """Route one headline-ranked ref without replaying candidate or match text."""

    if action not in {"finalize_hypothesis", "stage_hypothesis_candidate"}:
        raise AssertionError("unknown nearest-history audit action")
    return {
        "action": action,
        "ok": False,
        "reason": "nearest_history_audit_required",
        "required_history_ref": required_ref,
    }


def _pending_required_history_ref(
    results: Sequence[Mapping[str, Any]],
    *,
    visible_histories: set[str],
) -> str | None:
    """Return the latest unread host-routed audit ref, if one exists."""

    for result in reversed(results):
        if (
            result.get("action")
            in {"finalize_hypothesis", "stage_hypothesis_candidate"}
            and result.get("reason") == "nearest_history_audit_required"
        ):
            ref = result.get("required_history_ref")
            return (
                ref if isinstance(ref, str) and ref not in visible_histories else None
            )
    return None


__all__ = [
    "HypothesisResearchAbstain",
    "HypothesisResearchBasis",
    "HypothesisResearchContextError",
    "HypothesisResearchFinalized",
    "HypothesisResearchResult",
    "HypothesisResearchSession",
    "bind_hypothesis_research_turn_tool",
]
