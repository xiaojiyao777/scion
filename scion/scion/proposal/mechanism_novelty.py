"""Conservative mechanism-premise gate for active solver-design proposals."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from scion.core.models import HypothesisProposal
from scion.proposal.tools import ProposalObservation


@dataclass(frozen=True)
class MechanismNoveltyResult:
    premise_check: str
    failure_category: str
    mechanism: str
    reason: str
    evidence: tuple[str, ...] = ()
    snapshot_digest: str | None = None

    def to_rejection(self, hypothesis: HypothesisProposal) -> dict[str, Any]:
        return {
            "artifact_kind": "agentic_mechanism_novelty_rejection",
            "premise_check": self.premise_check,
            "failure_category": self.failure_category,
            "reason": self.reason,
            "selected_surface": hypothesis.change_locus,
            "target_file": hypothesis.target_file,
            "mechanism": self.mechanism,
            "evidence": list(self.evidence),
            "snapshot_digest": self.snapshot_digest,
            "patch_generated": False,
            "screening_allowed": False,
            "gate_name": "MechanismNoveltyGate",
        }


@dataclass(frozen=True)
class _ActiveMechanismFacts:
    has_diverse_construction: bool = False
    has_adaptive_weights: bool = False
    has_cross_route_or_opt_2_3: bool = False
    has_shaw_related_removal: bool = False
    construction_evidence: tuple[str, ...] = ()
    adaptive_weight_evidence: tuple[str, ...] = ()
    or_opt_evidence: tuple[str, ...] = ()
    shaw_related_evidence: tuple[str, ...] = ()
    snapshot_digest: str | None = None


class MechanismNoveltyGate:
    """Block only explicit duplicate or contradicted active solver premises."""

    def evaluate(
        self,
        hypothesis: HypothesisProposal,
        *,
        active_solver_snapshot: Mapping[str, Any] | None = None,
        observations: Sequence[ProposalObservation] = (),
    ) -> MechanismNoveltyResult | None:
        if str(hypothesis.change_locus or "").strip() != "solver_design":
            return None
        snapshot = active_solver_snapshot or _active_solver_snapshot_from_observations(
            observations
        )
        if not isinstance(snapshot, Mapping):
            return None
        facts = _facts_from_snapshot(snapshot)
        text = _hypothesis_text(hypothesis)

        if facts.has_diverse_construction and _claims_nearest_neighbor_only(text):
            return MechanismNoveltyResult(
                premise_check="contradicted",
                failure_category="premise_contradicted",
                mechanism="construction_seed_strategy",
                reason=(
                    "Hypothesis claims the active baseline uses only a single "
                    "nearest-neighbor seed, but the active solver snapshot shows "
                    "sweep construction, Clarke-Wright savings, capacity-balanced "
                    "repair, and nearest-neighbor only as fallback."
                ),
                evidence=facts.construction_evidence,
                snapshot_digest=facts.snapshot_digest,
            )

        if facts.has_adaptive_weights and _claims_weights_non_adaptive(text):
            return MechanismNoveltyResult(
                premise_check="contradicted",
                failure_category="premise_contradicted",
                mechanism="adaptive_operator_weights",
                reason=(
                    "Hypothesis claims operator weights are uniform or "
                    "non-adaptive throughout, but the active solver snapshot "
                    "shows _AdaptiveWeights record/update behavior."
                ),
                evidence=facts.adaptive_weight_evidence,
                snapshot_digest=facts.snapshot_digest,
            )

        if facts.has_cross_route_or_opt_2_3 and _claims_missing_or_opt_2_3(text):
            return MechanismNoveltyResult(
                premise_check="contradicted",
                failure_category="premise_contradicted",
                mechanism="cross_route_or_opt_2_3",
                reason=(
                    "Hypothesis claims inter-route/cross-route Or-opt segment "
                    "relocation is missing, but the active solver snapshot "
                    "shows _or_opt_1/_or_opt_2/_or_opt_3 and _or_opt skipping "
                    "same-route destinations, so length-2/3 cross-route "
                    "segment relocation already exists."
                ),
                evidence=facts.or_opt_evidence,
                snapshot_digest=facts.snapshot_digest,
            )

        if facts.has_cross_route_or_opt_2_3 and _duplicates_or_opt_2_3(text):
            return MechanismNoveltyResult(
                premise_check="duplicate",
                failure_category="duplicate_mechanism",
                mechanism="cross_route_or_opt_2_3",
                reason=(
                    "Hypothesis proposes adding inter-route/cross-route Or-opt "
                    "segment relocation as a new mechanism, but the active "
                    "solver snapshot already contains _or_opt_1/_or_opt_2/"
                    "_or_opt_3 cross-route segment relocation."
                ),
                evidence=facts.or_opt_evidence,
                snapshot_digest=facts.snapshot_digest,
            )

        if facts.has_shaw_related_removal and _claims_missing_shaw_related_removal(text):
            return MechanismNoveltyResult(
                premise_check="contradicted",
                failure_category="premise_contradicted",
                mechanism="shaw_related_removal",
                reason=(
                    "Hypothesis claims related/proximity-cluster destroy removal "
                    "is missing, but the active solver snapshot shows "
                    "_shaw_removal: a seed-based destroy operator using "
                    "distance, demand, and original-route relatedness."
                ),
                evidence=facts.shaw_related_evidence,
                snapshot_digest=facts.snapshot_digest,
            )

        if facts.has_shaw_related_removal and _duplicates_shaw_related_removal(text):
            return MechanismNoveltyResult(
                premise_check="duplicate",
                failure_category="duplicate_mechanism",
                mechanism="shaw_related_removal",
                reason=(
                    "Hypothesis proposes adding related/proximity-cluster "
                    "removal as a new destroy capability, but the active solver "
                    "already contains _shaw_removal with distance, demand, and "
                    "route relatedness criteria."
                ),
                evidence=facts.shaw_related_evidence,
                snapshot_digest=facts.snapshot_digest,
            )

        return None


def _active_solver_snapshot_from_observations(
    observations: Sequence[ProposalObservation],
) -> Mapping[str, Any] | None:
    for observation in reversed(tuple(observations)):
        if observation.is_error:
            continue
        if observation.tool_name != "context.read_active_solver_design":
            continue
        payload = observation.structured_payload
        if isinstance(payload, Mapping) and isinstance(
            payload.get("mechanism_summary"), Mapping
        ):
            return payload
    return None


def _facts_from_snapshot(snapshot: Mapping[str, Any]) -> _ActiveMechanismFacts:
    mechanism_summary = snapshot.get("mechanism_summary")
    mechanism_summary = mechanism_summary if isinstance(mechanism_summary, Mapping) else {}
    construction_text = _normalized_join(
        _flatten_strings(mechanism_summary.get("construction"))
    )
    acceptance_text = _normalized_join(_flatten_strings(mechanism_summary.get("acceptance")))
    local_search_text = _normalized_join(
        _flatten_strings(mechanism_summary.get("local_search"))
    )
    destroy_repair_text = _normalized_join(
        _flatten_strings(mechanism_summary.get("destroy_repair"))
    )
    call_graph_text = _normalized_join(_flatten_strings(snapshot.get("call_graph")))

    construction_combined = f"{construction_text} {call_graph_text}"
    acceptance_combined = f"{acceptance_text} {call_graph_text}"
    local_search_combined = f"{local_search_text} {call_graph_text}"
    destroy_repair_combined = f"{destroy_repair_text} {call_graph_text}"

    return _ActiveMechanismFacts(
        has_diverse_construction=(
            _has_any(construction_combined, ("sweep", "_sweep_construction"))
            and _has_any(construction_combined, ("clarke wright", "clarke-wright"))
            and "capacity balanced" in construction_combined
            and _has_any(construction_combined, ("nearest neighbor", "_nearest_neighbor"))
        ),
        has_adaptive_weights=(
            "adaptiveweights" in acceptance_combined.replace(" ", "")
            and "update" in acceptance_combined
            and _has_any(acceptance_combined, ("record", "score", "usage"))
        ),
        has_cross_route_or_opt_2_3=(
            _has_or_opt_token(local_search_combined, "2")
            and _has_or_opt_token(local_search_combined, "3")
            and _has_any(
                local_search_combined,
                (
                    "cross route",
                    "cross-route",
                    "skips same route",
                    "same-route destinations",
                    "intra and cross route moves",
                ),
            )
        ),
        has_shaw_related_removal=(
            "shaw removal" in destroy_repair_combined
            and _has_any(
                destroy_repair_combined,
                ("related", "relatedness", "proximity", "cluster"),
            )
            and _has_any(
                destroy_repair_combined,
                ("destroy", "removal", "remove"),
            )
            and "distance" in destroy_repair_combined
            and "demand" in destroy_repair_combined
            and "route" in destroy_repair_combined
        ),
        construction_evidence=_evidence(
            mechanism_summary.get("construction"),
            fallback=(
                "_sweep_construction",
                "_clarke_wright_savings",
                "_capacity_balanced_construction",
                "_nearest_neighbor",
            ),
        ),
        adaptive_weight_evidence=_evidence(
            mechanism_summary.get("acceptance"),
            fallback=(
                "_AdaptiveWeights.choose",
                "_AdaptiveWeights.record",
                "_AdaptiveWeights.update",
            ),
        ),
        or_opt_evidence=_evidence(
            mechanism_summary.get("local_search"),
            fallback=(
                "_or_opt",
                "_or_opt_1",
                "_or_opt_2",
                "_or_opt_3",
                "cross-route Or-opt segment relocation",
            ),
        ),
        shaw_related_evidence=_evidence(
            mechanism_summary.get("destroy_repair"),
            fallback=(
                "_shaw_removal",
                "seed-based related removal",
                "distance + demand + original-route relatedness",
            ),
        ),
        snapshot_digest=_snapshot_digest(snapshot),
    )


def _hypothesis_text(hypothesis: HypothesisProposal) -> str:
    parts: list[str] = [
        hypothesis.hypothesis_text,
        hypothesis.target_weakness,
        hypothesis.expected_effect,
        hypothesis.no_op_condition,
        hypothesis.risk_to_higher_priority,
        hypothesis.complexity_claim or "",
        hypothesis.runtime_budget_strategy or "",
    ]
    parts.extend(_flatten_leaf_strings(hypothesis.novelty_signature))
    return _normalize_text(" ".join(part for part in parts if part))


def _claims_nearest_neighbor_only(text: str) -> bool:
    if not _has_any(text, ("nearest neighbor", " nn ")):
        return False
    patterns = (
        r"\b(?:baseline|current|existing|active|champion|solver)\b.{0,90}"
        r"\b(?:only|single|sole|just|exclusively)\b.{0,60}"
        r"\b(?:nearest neighbor|nn)\b.{0,50}\b(?:seed|construction|initial)",
        r"\b(?:single|only|sole|just|exclusively)\b.{0,30}"
        r"\b(?:nearest neighbor|nn)\b.{0,40}\b(?:seed|construction|initial)",
        r"\b(?:nearest neighbor|nn)\b.{0,25}\b(?:only|single|sole)\b",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def _claims_weights_non_adaptive(text: str) -> bool:
    if "weight" not in text:
        return False
    if (
        "uniform" in text
        and _has_any(text, ("initial", "initialize", "start"))
        and not _has_any(text, ("throughout", "entire", "whole", "always", "remain"))
    ):
        return False
    patterns = (
        r"\b(?:adaptive|operator|destroy|repair)\b.{0,40}\bweights?\b.{0,35}"
        r"\b(?:remain|stays?|are|is|currently|still|always)\b.{0,25}"
        r"\b(?:uniform|static|fixed|non adaptive|nonadaptive|not adaptive)\b"
        r"(?:.{0,45}\b(?:throughout|entire|whole|all iterations|all run)\b)?",
        r"\bweights?\b.{0,35}\b(?:never|do not|does not|don't|without)\b.{0,25}"
        r"\b(?:update|adapt|record|learn)\b",
        r"\b(?:non adaptive|nonadaptive|not adaptive|static|fixed)\b.{0,35}"
        r"\b(?:operator|destroy|repair|adaptive)\b.{0,20}\bweights?\b",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def _claims_missing_or_opt_2_3(text: str) -> bool:
    if not _mentions_cross_route_or_opt_segment_relocation(text):
        return False
    if _describes_existing_or_opt_improvement(text):
        return False
    patterns = (
        r"\b(?:missing|lacks?|absent|without|no|does not have|does not include|"
        r"doesn't have|doesn't include)\b.{0,80}"
        r"\b(?:cross route|inter route|between route|across routes|different route)"
        r"\b.{0,80}\b(?:or opt|oropt|segment relocat(?:e|ion)?|"
        r"relocat(?:e|ion) segment)\b",
        r"\b(?:cross route|inter route|between route|across routes|different route)"
        r"\b.{0,80}\b(?:or opt|oropt|segment relocat(?:e|ion)?|"
        r"relocat(?:e|ion) segment)"
        r"\b.{0,80}\b(?:missing|lacks?|absent|without|no|does not have|"
        r"does not include|doesn't have|doesn't include)\b",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def _duplicates_or_opt_2_3(text: str) -> bool:
    if not _mentions_cross_route_or_opt_segment_relocation(text):
        return False
    if _describes_existing_or_opt_improvement(text):
        return False
    add_pattern = (
        r"\b(?:add|introduce|implement|enable|create|build)\b.{0,120}"
        r"\b(?:cross route|inter route|between route|across routes|different route)"
        r"\b.{0,120}\b(?:or opt|oropt|segment relocat(?:e|ion)?|"
        r"relocat(?:e|ion) segment)\b"
    )
    add_reversed_pattern = (
        r"\b(?:add|introduce|implement|enable|create|build)\b.{0,120}"
        r"\b(?:or opt|oropt|segment relocat(?:e|ion)?|"
        r"relocat(?:e|ion) segment)\b.{0,120}"
        r"\b(?:cross route|inter route|between route|across routes|different route)"
        r"\b"
    )
    new_pattern = (
        r"\b(?:new|novel|entirely new|first)\b.{0,100}"
        r"\b(?:cross route|inter route|between route|across routes|different route)"
        r"\b.{0,100}\b(?:or opt|oropt|segment relocat(?:e|ion)?|"
        r"relocat(?:e|ion) segment)"
        r"\b.{0,80}\b(?:neighborhood|operator|mechanism|capability|move)\b"
    )
    return any(
        re.search(pattern, text)
        for pattern in (add_pattern, add_reversed_pattern, new_pattern)
    )


def _claims_missing_shaw_related_removal(text: str) -> bool:
    if not _mentions_shaw_related_removal(text):
        return False
    if _scopes_change_to_existing_shaw_related_removal(text):
        return False
    patterns = (
        r"\b(?:missing|lacks?|absent|without|no)\b.{0,80}"
        r"\b(?:shaw|related|relatedness|proximity|cluster(?:ed)?)\b.{0,80}"
        r"\b(?:destroy|remov(?:al|e)|operator|mechanism)\b",
        r"\b(?:shaw|related|relatedness|proximity|cluster(?:ed)?)\b.{0,80}"
        r"\b(?:destroy|remov(?:al|e)|operator|mechanism)\b.{0,80}"
        r"\b(?:missing|lacks?|absent|without|no)\b",
        r"\b(?:current|existing|active|champion|baseline|solver)\b.{0,90}"
        r"\b(?:missing|lacks?|absent|without|no)\b.{0,90}"
        r"\b(?:shaw|related|relatedness|proximity|cluster(?:ed)?)\b",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def _duplicates_shaw_related_removal(text: str) -> bool:
    if not _mentions_shaw_related_removal(text):
        return False
    if _describes_existing_shaw_related_improvement(text):
        return False
    patterns = (
        r"\b(?:add|introduce|implement|enable|create|build)\b.{0,50}"
        r"\b(?:new|novel|entirely new|first)\b.{0,60}"
        r"\b(?:shaw|related|relatedness|proximity|cluster(?:ed)?)\b.{0,80}"
        r"\b(?:destroy|remov(?:al|e)|operator|mechanism|capability)\b",
        r"\b(?:add|introduce|implement|enable|create|build)\b.{0,80}"
        r"\b(?:shaw style|shaw|related removal|relatedness removal|"
        r"proximity cluster|proximity based|cluster removal|clustered removal)\b"
        r".{0,80}\b(?:destroy|remov(?:al|e)|operator|mechanism|capability)\b",
        r"\b(?:shaw|related|relatedness|proximity|cluster(?:ed)?)\b.{0,80}"
        r"\b(?:destroy|remov(?:al|e)|operator|mechanism|capability)\b.{0,80}"
        r"\b(?:new|novel|entirely new|first)\b",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def _mentions_shaw_related_removal(text: str) -> bool:
    if "shaw" in text and _has_any(text, ("removal", "remove", "destroy")):
        return True
    phrases = (
        "related removal",
        "relatedness removal",
        "related destroy",
        "relatedness destroy",
        "proximity cluster",
        "proximity based removal",
        "proximity removal",
        "cluster removal",
        "clustered removal",
        "cluster destroy",
        "clustered destroy",
        "nearby customer removal",
        "neighbor removal",
        "neighbour removal",
    )
    if _has_any(text, phrases):
        return True
    return bool(
        re.search(
            r"\b(?:related|relatedness|proximity|cluster(?:ed)?|nearby|neighbou?r)\b"
            r".{0,50}\b(?:destroy|remov(?:al|e)|operator)\b",
            text,
        )
        or re.search(
            r"\b(?:destroy|remov(?:al|e)|operator)\b.{0,50}"
            r"\b(?:related|relatedness|proximity|cluster(?:ed)?|nearby|neighbou?r)\b",
            text,
        )
    )


def _describes_existing_shaw_related_improvement(text: str) -> bool:
    if _scopes_change_to_existing_shaw_related_removal(text):
        return True
    if _has_any(
        text,
        (
            "missing",
            "lacks",
            "lack ",
            "absent",
            "new capability",
            "new destroy capability",
            "new operator",
            "new mechanism",
            "entirely new",
        ),
    ):
        return False
    if _has_any(text, ("existing", "current", "already", "_shaw_removal", "shaw removal")):
        return True
    return _has_any(
        text,
        (
            "refine",
            "tune",
            "adjust",
            "adapt",
            "adaptive",
            "diversify",
            "stochastic",
            "sampling",
            "p sampling",
            "weight",
            "weights",
            "relatedness criteria",
            "score",
            "scoring",
            "phi",
        ),
    )


def _scopes_change_to_existing_shaw_related_removal(text: str) -> bool:
    return _has_any(
        text,
        (
            "without adding",
            "without introducing",
            "without creating",
            "without building",
            "without changing the operator set",
        ),
    ) and _has_any(
        text,
        (
            "existing",
            "current",
            "improve",
            "refine",
            "tune",
            "adjust",
            "adapt",
            "adaptive",
            "diversify",
            "stochastic",
            "sampling",
            "weight",
            "weights",
        ),
    )


def _mentions_or_opt_2_3(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:or opt|oropt)\b.{0,35}(?:2\s*/\s*3|2\s+and\s+3|length\s+2|"
            r"length\s+3|\b2\b|\b3\b|two|three)",
            text,
        )
        or re.search(
            r"(?:2\s*/\s*3|2\s+and\s+3|length\s+2|length\s+3|\b2\b|\b3\b|two|three)"
            r".{0,35}\b(?:or opt|oropt)\b",
            text,
        )
    )


def _mentions_cross_route_or_opt_segment_relocation(text: str) -> bool:
    if not _has_route_scope(text):
        return False
    return _mentions_or_opt_family(text) or _mentions_segment_relocation(text)


def _mentions_or_opt_family(text: str) -> bool:
    return _has_any(text, ("or opt", "oropt"))


def _mentions_segment_relocation(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:segment|chain|length\s*[23]|two customer|three customer|"
            r"2 customer|3 customer|k customer|multi customer)\b.{0,35}"
            r"\b(?:relocat(?:e|ion)|move)\b",
            text,
        )
        or re.search(
            r"\b(?:relocat(?:e|ion)|move)\b.{0,35}"
            r"\b(?:segment|chain|length\s*[23]|two customer|three customer|"
            r"2 customer|3 customer|k customer|multi customer)\b",
            text,
        )
    )


def _has_route_scope(text: str) -> bool:
    return _has_any(
        text,
        (
            "cross route",
            "inter route",
            "between route",
            "across routes",
            "different route",
            "route pair",
            "route pairs",
        ),
    )


def _describes_existing_or_opt_improvement(text: str) -> bool:
    mentions_or_opt = (
        _mentions_cross_route_or_opt_segment_relocation(text)
        or _mentions_or_opt_family(text)
    )
    if not mentions_or_opt:
        return False
    if _targets_existing_or_opt_filter_gap(text):
        return True
    if _adds_or_opt_improvement_control(text):
        return True
    if _has_any(
        text,
        (
            "without adding",
            "without introducing",
            "without creating",
            "without building",
            "without changing the operator set",
            "without adding a new operator",
            "without adding a new neighborhood",
        ),
    ) and _has_or_opt_improvement_terms(text):
        return True
    if not _has_any(
        text,
        (
            "existing",
            "current",
            "already",
            "present",
            "built in",
            "built-in",
        ),
    ):
        return False
    if not _has_or_opt_improvement_terms(text):
        return False
    return not _has_any(
        text,
        (
            "new neighborhood",
            "new operator",
            "new mechanism",
            "new capability",
            "entirely new",
            "first cross route",
            "first inter route",
        ),
    )


def _targets_existing_or_opt_filter_gap(text: str) -> bool:
    existing_or_opt = (
        r"\b(?:existing|current|already present|built in|built-in)\b"
        r".{0,80}\b(?:or opt|oropt)\b"
    )
    filter_gap = (
        r"\b(?:missing|lacks?|without|no|does not have|does not include|"
        r"doesn't have|doesn't include)\b.{0,60}"
        r"\b(?:filter|filtered|candidate|nearest neighbor|nn|prun(?:e|ing)|"
        r"ordering|score|scoring|delta)\b"
    )
    return bool(
        re.search(existing_or_opt + r".{0,100}" + filter_gap, text)
        or re.search(filter_gap + r".{0,100}" + existing_or_opt, text)
    )


def _adds_or_opt_improvement_control(text: str) -> bool:
    if not re.search(r"\b(?:add|introduce|implement|enable)\b", text):
        return False
    if _has_any(
        text,
        (
            "new neighborhood",
            "new operator",
            "new mechanism",
            "new capability",
            "segment relocation neighborhood",
            "relocation neighborhood",
        ),
    ):
        return False
    return bool(
        re.search(
            r"\b(?:add|introduce|implement|enable)\b.{0,80}"
            r"\b(?:candidate|filter(?:ing)?|prun(?:e|ing)|ordering|score|"
            r"scoring|delta|budget|cache|nearest neighbor|nn)\b.{0,120}"
            r"\b(?:or opt|oropt)\b",
            text,
        )
        or re.search(
            r"\b(?:or opt|oropt)\b.{0,120}"
            r"\b(?:add|introduce|implement|enable)\b.{0,80}"
            r"\b(?:candidate|filter(?:ing)?|prun(?:e|ing)|ordering|score|"
            r"scoring|delta|budget|cache|nearest neighbor|nn)\b",
            text,
        )
    )


def _has_or_opt_improvement_terms(text: str) -> bool:
    return _has_any(
        text,
        (
            "improve",
            "refine",
            "tune",
            "adjust",
            "optimize",
            "optimise",
            "strengthen",
            "score",
            "scoring",
            "formula",
            "rate",
            "prune",
            "pruning",
            "candidate",
            "ordering",
            "filter",
            "filtered",
            "nearest neighbor",
            " nn ",
            "budget",
            "delta",
            "cache",
            "early exit",
        ),
    )


def _has_or_opt_token(text: str, length: str) -> bool:
    compact = text.replace(" ", "").replace("-", "_")
    return f"_or_opt_{length}" in compact or f"oropt{length}" in compact


def _flatten_strings(value: Any) -> list[str]:
    if isinstance(value, Mapping):
        strings: list[str] = []
        for key, child in value.items():
            strings.append(str(key))
            strings.extend(_flatten_strings(child))
        return strings
    if isinstance(value, (list, tuple, set)):
        strings = []
        for child in value:
            strings.extend(_flatten_strings(child))
        return strings
    if value is None:
        return []
    return [str(value)]


def _flatten_leaf_strings(value: Any) -> list[str]:
    if isinstance(value, Mapping):
        strings: list[str] = []
        for child in value.values():
            strings.extend(_flatten_leaf_strings(child))
        return strings
    if isinstance(value, (list, tuple, set)):
        strings = []
        for child in value:
            strings.extend(_flatten_leaf_strings(child))
        return strings
    if value is None:
        return []
    return [str(value)]


def _evidence(value: Any, *, fallback: tuple[str, ...]) -> tuple[str, ...]:
    strings = [
        item
        for item in _flatten_strings(value)
        if item and len(item) <= 220 and not item.lower() in {"true", "false"}
    ]
    result = tuple(dict.fromkeys(strings[:8]))
    return result or fallback


def _snapshot_digest(snapshot: Mapping[str, Any]) -> str | None:
    source_digest = snapshot.get("source_digest")
    if isinstance(source_digest, Mapping):
        digest = source_digest.get("snapshot_digest")
        if digest:
            return str(digest)
    digest = snapshot.get("snapshot_digest")
    return str(digest) if digest else None


def _normalized_join(values: Sequence[str]) -> str:
    return _normalize_text(" ".join(values))


def _normalize_text(text: str) -> str:
    normalized = str(text or "").lower()
    normalized = normalized.replace("_", " ")
    normalized = re.sub(r"[-/]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return f" {normalized.strip()} "


def _has_any(text: str, needles: Sequence[str]) -> bool:
    return any(needle in text for needle in needles)


__all__ = ["MechanismNoveltyGate", "MechanismNoveltyResult"]
