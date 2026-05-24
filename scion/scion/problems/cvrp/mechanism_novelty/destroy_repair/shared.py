from __future__ import annotations

import re

from scion.problems.cvrp.mechanism_novelty.text import _has_any

def _mentions_shaw_related_removal(text: str) -> bool:
    if _has_any(
        text,
        (
            "_shaw_removal",
            "shaw removal",
            "shaw related removal",
            "shaw related destroy",
            "shaw style removal",
            "shaw style destroy",
        ),
    ):
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

def _mentions_exact_shaw_related_fact(text: str) -> bool:
    if _has_any(
        text,
        (
            "_shaw_removal",
            "shaw removal",
            "shaw related removal",
            "shaw related destroy",
            "shaw style removal",
            "shaw style destroy",
        ),
    ):
        return True
    return _has_any(
        text,
        (
            "related removal",
            "relatedness removal",
            "related destroy",
            "relatedness destroy",
            "seed based related removal",
            "seed related removal",
        ),
    )

def _is_positional_or_arc_destroy_variant(text: str) -> bool:
    if not _mentions_shaw_related_removal(text):
        return False
    if _mentions_exact_shaw_related_fact(text) and not _is_shaw_contrast_or_negated_addition(
        text
    ):
        return False
    if not re.search(
        r"\b(?:arc|edge|positional|position|route position|geographic|"
        r"spatial|route segment)\b",
        text,
    ):
        return False
    return _has_any(
        text,
        (
            "variant",
            "trigger",
            "score",
            "scoring",
            "filter",
            "candidate",
            "new destroy",
            "destroy operator",
            "removal operator",
        ),
    )


def _is_shaw_contrast_or_negated_addition(text: str) -> bool:
    return _has_any(
        text,
        (
            " unlike shaw ",
            " unlike _shaw_removal ",
            " unlike shaw related ",
            " unlike the existing shaw ",
            " unlike existing shaw ",
            " unlike current shaw ",
            " distinct from shaw ",
            " distinct from _shaw_removal ",
            " distinct from shaw related ",
            " distinct from related removal ",
            " distinct from existing shaw ",
            " different from shaw ",
            " different from existing shaw ",
            " rather than shaw ",
            " rather than existing shaw ",
            " not a related destroy ",
            " not a related removal ",
            " not related removal ",
            " not a new shaw ",
            " not a new shaw related ",
            " not a new related removal ",
            " not shaw removal ",
            " not shaw or proximity removal ",
            " not shaw related removal ",
            " not shaw related ",
            " not shaw related removal and not proximity removal ",
            " not a proximity cluster ",
            " not proximity cluster ",
            " not proximity removal ",
            " not a cluster destroy ",
            " not cluster destroy ",
            " does not add shaw ",
            " does not add shaw/proximity ",
            " without adding shaw ",
        ),
    )


def _mentions_removal_savings_destroy(text: str) -> bool:
    if _has_any(
        text,
        (
            "savings removal",
            "removal saving",
            "removal savings",
            "savings from removal",
            "cost of remove",
            "detour cost",
            "detour based removal",
            "cost-of-remove",
            "cost of removal",
            "worst position",
            "worst-position",
            "worst-position removal",
            "position aware targeted removal",
            "marginal distance contribution",
            "geometric detour",
        ),
    ):
        return True
    return bool(
        re.search(
            r"\b(?:saving|savings|detour|marginal distance)\b.{0,70}"
            r"\b(?:destroy|remov(?:al|e)|operator|heuristic)\b",
            text,
        )
        or re.search(
            r"\b(?:worst position|worst-position|cost[- ]of[- ]remove|cost of removal)\b"
            r".{0,90}\b(?:destroy|remov(?:al|e)|operator|heuristic)\b",
            text,
        )
    )

def _is_random_or_noise_removal_variant(text: str) -> bool:
    if not _has_any(text, ("remove", "removal", "destroy")):
        return False
    return _has_any(
        text,
        (
            "random removal",
            "randomized removal",
            "random destroy",
            "randomized destroy",
            "noise removal",
            "noise based removal",
            "noise biased removal",
            "stochastic removal",
            "stochastic destroy",
            "diversity removal",
            "diversity destroy",
        ),
    )

def _explicit_removal_savings_claim(text: str) -> bool:
    return _has_any(
        text,
        (
            "savings removal",
            "removal savings",
            "savings based removal",
            "detour based removal",
            "cost of remove",
            "cost-of-remove",
            "cost of removal",
            "worst position",
            "worst-position",
            "marginal distance contribution",
        ),
    )

def _is_removal_savings_contrast_or_negated_addition(text: str) -> bool:
    return _has_any(
        text,
        (
            "rather than adding a new savings-removal",
            "rather than adding a new savings removal",
            "rather than adding savings-removal",
            "rather than adding savings removal",
            "rather than adding a savings-removal",
            "rather than adding a savings removal",
            "rather than a new savings-removal",
            "rather than a new savings removal",
            "not a savings removal",
            "not savings removal",
            "not a new savings removal",
            "not a new savings-removal",
            "not removal savings",
            "not another removal savings",
            "not another savings removal",
            "not another removal-savings",
            "not another savings-removal",
            "not a removal savings",
            "not a removal-savings",
            "does not add savings removal",
            "does not add removal savings",
            "without adding savings removal",
            "without adding removal savings",
        ),
    )

def _is_pure_geographic_cluster_variant_acknowledging_removal_savings(
    text: str,
) -> bool:
    if not _proposes_pure_geographic_cluster_destroy_variant(text):
        return False
    if _proposes_removal_savings_as_new_destroy_capability(text):
        return False
    return _acknowledges_existing_removal_savings_destroy(
        text
    ) or _is_removal_savings_contrast_or_negated_addition(text)

def _is_insertion_aware_variant_acknowledging_removal_savings(text: str) -> bool:
    if not _proposes_insertion_aware_position_cost_destroy_variant(text):
        return False
    return _acknowledges_existing_removal_savings_destroy(text)

def _proposes_insertion_aware_position_cost_destroy_variant(text: str) -> bool:
    if not _has_any(text, ("destroy", "removal", "remove")):
        return False
    return _has_any(
        text,
        (
            "position-cost",
            "position cost",
            "position-aware",
            "position aware",
            "costly position",
            "costly-position",
            "insertion opportunity",
            "reinsertion-aware",
            "reinsertion aware",
            "best alternative insertion",
            "alternative insertion",
            "best insertion",
            "insertion cost",
            "reinsert",
            "reinsertion",
            "regret-1",
            "regret 1",
            "current position",
            "badly placed",
        ),
    )

def _is_pure_geographic_cluster_variant_acknowledging_shaw(text: str) -> bool:
    if not _proposes_pure_geographic_cluster_destroy_variant(text):
        return False
    return _acknowledges_existing_shaw_related_removal(
        text
    ) or _is_shaw_contrast_or_negated_addition(text)

def _proposes_pure_geographic_cluster_destroy_variant(text: str) -> bool:
    if not _has_any(text, ("destroy", "removal", "remove")):
        return False
    if not _has_any(
        text,
        (
            "cluster removal",
            "cluster destroy",
            "clustered removal",
            "clustered destroy",
            "zone removal",
            "zone destroy",
            "zone clustered removal",
            "zone-clustered removal",
            "geographic cluster",
            "spatial cluster",
            "geographic zone",
            "spatial zone",
            "proximity variant",
            "nearby customer",
            "nearest customer",
            "nearest customers",
        ),
    ):
        return False
    return _has_any(
        text,
        (
            "pure geographic",
            "geographic",
            "spatial",
            "zone",
            "zonal",
            "euclidean",
            "coordinate",
            "coordinates",
            "distance only",
            "nearest customer",
            "nearest customers",
            "orthogonal",
            "independent of route",
        ),
    )

def _acknowledges_existing_removal_savings_destroy(text: str) -> bool:
    if not _has_any(
        text,
        (
            "_worst_removal",
            "worst removal",
            "existing removal savings",
            "current removal savings",
            "active removal savings",
        ),
    ):
        return False
    savings_terms = (
        r"removal savings?",
        r"savings from removal",
        r"cost of remove",
        r"cost of removal",
        r"detour cost",
    )
    savings = r"(?:%s)" % "|".join(savings_terms)
    return bool(
        re.search(
            r"\b(?:existing|current|active|baseline|already)?\b.{0,80}"
            r"\b(?:_worst_removal|worst removal)\b.{0,140}"
            r"\b(?:already|uses?|ranks?|seeds?|sorts?|orders?|targets?|"
            r"based|by|with)\b.{0,100}\b"
            + savings
            + r"\b",
            text,
        )
        or re.search(
            r"\b"
            + savings
            + r"\b.{0,140}\b(?:existing|current|active|baseline|already)?"
            r".{0,80}\b(?:_worst_removal|worst removal)\b",
            text,
        )
    )

def _acknowledges_existing_shaw_related_removal(text: str) -> bool:
    if not _has_any(
        text,
        (
            "_shaw_removal",
            "shaw",
            "shaw removal",
            "existing related removal",
            "current related removal",
            "active related removal",
        ),
    ):
        return False
    return bool(
        re.search(
            r"\b(?:existing|current|active|baseline|already)?\b.{0,80}"
            r"\bshaw removal\b.{0,140}"
            r"\b(?:already|uses?|blends?|combines?|based|with)\b.{0,100}"
            r"\b(?:distance|demand|route|relatedness|proximity)\b",
            text,
        )
        or re.search(
            r"\b(?:distance|demand|route|relatedness|proximity)\b.{0,140}"
            r"\bshaw removal\b",
            text,
        )
        or re.search(
            r"\b(?:existing|current|active|baseline|already|uses?|includes?|"
            r"contains?|portfolio|phase)\b.{0,140}\b(?:_shaw_removal|shaw)\b",
            text,
        )
        or re.search(
            r"\b(?:_shaw_removal|shaw)\b.{0,140}\b(?:exists?|existing|current|"
            r"active|already|available|included|contains?|uses?)\b",
            text,
        )
        or re.search(
            r"\b(?:random|worst|route)\b.{0,80}\bshaw\b.{0,80}"
            r"\b(?:random|worst|route)\b",
            text,
        )
    )

def _proposes_removal_savings_as_new_destroy_capability(text: str) -> bool:
    if _is_removal_savings_contrast_or_negated_addition(text):
        return False
    return bool(
        re.search(
            r"\b(?:add|introduce|implement|enable|create|build|register)\b"
            r".{0,120}\b(?:removal savings?|savings removal|detour cost|"
            r"cost of remove|cost of removal|marginal distance contribution)\b"
            r".{0,100}\b(?:destroy|remov(?:al|e)|operator|heuristic|capability)\b",
            text,
        )
        or re.search(
            r"\b(?:removal savings?|savings removal|detour cost|cost of remove|"
            r"cost of removal|marginal distance contribution)\b.{0,120}"
            r"\b(?:new|novel|additional|first|missing|absent|lacks?)\b.{0,80}"
            r"\b(?:destroy|remov(?:al|e)|operator|heuristic|capability)\b",
            text,
        )
    )

def _mentions_route_removal(text: str) -> bool:
    if _has_any(
        text,
        (
            "_route_removal",
            "route removal",
            "route destroy",
            "whole route",
            "whole-route",
            "entire route",
            "route level",
            "route-level",
        ),
    ):
        return True
    return bool(
        re.search(
            r"\b(?:whole route|entire route|route-level|route level)\b"
            r".{0,45}\b(?:destroy|remov(?:al|e))\b",
            text,
        )
        or re.search(
            r"\b(?:destroy|remov(?:al|e))\b.{0,45}"
            r"\b(?:whole route|entire route|route-level|route level)\b",
            text,
        )
    )

def _mentions_random_removal_destroy(text: str) -> bool:
    if _has_any(
        text,
        (
            "_random_removal",
            "random removal",
            "random destroy",
            "randomized removal",
            "randomized destroy",
            "random customer removal",
            "random customer destroy",
            "uniform random removal",
            "uniform random destroy",
            "scheduler random",
        ),
    ):
        return True
    return bool(
        re.search(
            r"\brandom(?:ly)?\b.{0,50}\b(?:destroy|remov(?:al|e)|operator)\b",
            text,
        )
        or re.search(
            r"\b(?:destroy|remov(?:al|e)|operator)\b.{0,50}\brandom(?:ly)?\b",
            text,
        )
    )

def _mentions_regret_insertion_repair(text: str) -> bool:
    return _has_any(
        text,
        (
            "_regret2_insertion",
            "_regret3_insertion",
            "regret2",
            "regret3",
            "regret 2",
            "regret 3",
            "regret-2",
            "regret-3",
            "regret k",
            "regret-k",
            "regret insertion",
            "regret repair",
        ),
    )

def _is_non_regret_repair_variant(text: str) -> bool:
    if not _has_any(text, ("repair", "insertion", "insert")):
        return False
    if not _has_any(
        text,
        (
            "random greedy repair",
            "randomized greedy repair",
            "greedy repair",
            "position diversity repair",
            "diversity repair",
            "noise repair",
            "noise biased insertion",
            "stochastic repair",
            "stochastic insertion",
        ),
    ):
        return False
    return _has_any(
        text,
        (
            "not regret",
            "not a regret",
            "rather than regret",
            "unlike regret",
            "alongside existing regret",
            "uses existing regret",
            "existing regret",
            "regret portfolio",
        ),
    )

def _targets_segment_chain_unit_not_related_removal(text: str) -> bool:
    if not _has_any(
        text,
        (
            "segment chain",
            "segment-chain",
            "segment destroy",
            "sequential destroy",
            "sequential segment",
            "contiguous segment",
            "contiguous block",
            "ordered segment",
            "route segment",
            "chain as a unit",
            "segment as a unit",
            "subroute",
            "arc window",
            "positional window",
            "contiguous customer",
        ),
    ):
        return False
    if re.search(
        r"\b(?:add|introduce|implement|create|build)\b.{0,70}"
        r"\b(?:shaw|relatedness|related removal|related destroy|"
        r"proximity cluster|cluster removal)\b",
        text,
    ):
        return False
    return True

def _targets_contiguous_segment_destroy_not_whole_route_removal(text: str) -> bool:
    if not _has_any(
        text,
        (
            "segment destroy",
            "segment removal",
            "sequential destroy",
            "sequential segment",
            "contiguous segment",
            "contiguous block",
            "route segment",
            "route order",
            "tour order",
            "subroute",
            "arc sequence",
            "arc window",
            "positional window",
            "window destroy",
        ),
    ):
        return False
    if _explicitly_adds_or_claims_missing_whole_route_removal(text):
        return False
    return True

def _targets_perturbation_or_restart_not_removal_family(text: str) -> bool:
    if not _has_any(
        text,
        (
            "double bridge",
            "doublebridge",
            "4 opt",
            "four opt",
            "perturbation",
            "perturb",
            "restart",
            "escape mechanism",
            "escape to",
            "new basin",
            "route segment reconnection",
            "topological",
        ),
    ):
        return False
    if _explicitly_adds_or_claims_missing_whole_route_removal(text):
        return False
    if _explicitly_adds_or_claims_missing_shaw_related_removal(text):
        return False
    return True

def _explicitly_adds_or_claims_missing_whole_route_removal(text: str) -> bool:
    route_family = r"(?:whole route|entire route|route level|route removal|route destroy)"
    patterns = (
        r"\b(?:missing|lacks?|absent|without|no|does not have|does not include|"
        r"doesn t have|doesn t include)\b.{0,80}\b"
        + route_family
        + r"\b",
        r"\b(?:add|introduce|implement|enable|create|build|register)\b"
        r".{0,80}\b"
        + route_family
        + r"\b.{0,50}\b(?:destroy|remov(?:al|e)|operator|capability)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        if _span_lists_existing_operator_family(match.group(0)):
            continue
        if _span_is_whole_route_contrast_not_claim(match.group(0)):
            continue
        return True
    return False

def _explicitly_adds_or_claims_missing_shaw_related_removal(text: str) -> bool:
    shaw_family = (
        r"(?:shaw removal|shaw related removal|shaw related destroy|"
        r"shaw style removal|shaw style destroy|related removal|"
        r"relatedness removal|proximity removal|proximity cluster|"
        r"cluster removal|cluster destroy)"
    )
    if _is_shaw_contrast_or_negated_addition(text):
        return False
    return bool(
        re.search(
            r"\b(?:missing|lacks?|absent|without|no|does not have|does not include|"
            r"doesn t have|doesn t include)\b.{0,80}\b"
            + shaw_family
            + r"\b",
            text,
        )
        or re.search(
            r"\b(?:add|introduce|implement|enable|create|build|register)\b"
            r".{0,80}\b"
            + shaw_family
            + r"\b.{0,60}\b(?:destroy|remov(?:al|e)|operator|capability)\b",
            text,
        )
    )

def _span_lists_existing_operator_family(span: str) -> bool:
    return bool(
        re.search(
            r"\bexisting\b.{0,50}\b(?:destroy|removal|repair)?\s*operators\b",
            span,
        )
    )

def _span_is_whole_route_contrast_not_claim(span: str) -> bool:
    return _has_any(
        span,
        (
            " not a whole route ",
            " not whole route ",
            " not a route removal ",
            " not route removal ",
            " different from whole route ",
            " rather than whole route ",
            " existing whole route removal does not ",
            " existing route removal does not ",
        ),
    )

def _targets_worst_removal_savings_not_shaw(text: str) -> bool:
    if not _mentions_removal_savings_destroy(text):
        return False
    if "shaw" in text:
        return False
    return _has_any(
        text,
        (
            "_worst_removal",
            "worst removal",
            "worst-position",
            "worst position",
            "cost_of_remove",
            "cost of remove",
            "cost-of-remove",
            "removal saving",
            "removal savings",
            "savings from removal",
            "detour cost",
        ),
    )
