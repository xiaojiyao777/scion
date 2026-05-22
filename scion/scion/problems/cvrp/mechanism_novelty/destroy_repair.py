"""Destroy/repair premise predicates for CVRP mechanism novelty."""

from __future__ import annotations

import re

from scion.problems.cvrp.mechanism_novelty.text import _first_regex_span, _has_any


def _claims_missing_shaw_related_removal(text: str) -> bool:
    return bool(_missing_shaw_related_removal_span(text))


def _missing_shaw_related_removal_span(text: str) -> str:
    if not _mentions_shaw_related_removal(text):
        return ""
    if not _mentions_exact_shaw_related_fact(text):
        return ""
    if _targets_perturbation_or_restart_not_removal_family(text):
        return ""
    if _targets_worst_removal_savings_not_shaw(text):
        return ""
    if _targets_segment_chain_unit_not_related_removal(text):
        return ""
    if _is_pure_geographic_cluster_variant_acknowledging_shaw(text):
        return ""
    if (
        _scopes_change_to_existing_shaw_related_removal(text)
        or _is_existing_shaw_variant_with_negated_missing_claim(text)
    ):
        return ""
    span = _first_regex_span(text, _MISSING_SHAW_RELATED_REMOVAL_PATTERNS)
    if _span_is_shaw_contrast_not_missing_claim(span):
        return ""
    return span


_MISSING_SHAW_RELATED_REMOVAL_PATTERNS = (
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


def _duplicates_shaw_related_removal(text: str) -> bool:
    if not _mentions_shaw_related_removal(text):
        return False
    if _targets_perturbation_or_restart_not_removal_family(text):
        return False
    if _is_shaw_contrast_or_negated_addition(text):
        return False
    if _is_positional_or_arc_destroy_variant(text):
        return False
    if _is_random_or_noise_removal_variant(text) and not _mentions_exact_shaw_related_fact(
        text
    ):
        return False
    if _targets_worst_removal_savings_not_shaw(text):
        return False
    if _targets_segment_chain_unit_not_related_removal(text):
        return False
    if _is_pure_geographic_cluster_variant_acknowledging_shaw(text):
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


def _span_is_shaw_contrast_not_missing_claim(span: str) -> bool:
    if not span:
        return False
    return _has_any(
        span,
        (
            " unlike ",
            " different from ",
            " rather than ",
            " not a related ",
            " not related ",
            " does not add ",
            " does not add shaw ",
            " without adding shaw ",
            " not shaw removal ",
            " not a proximity cluster ",
            " not proximity cluster ",
        ),
    )


def _is_shaw_contrast_or_negated_addition(text: str) -> bool:
    return _has_any(
        text,
        (
            " unlike shaw ",
            " unlike _shaw_removal ",
            " unlike shaw related ",
            " different from shaw ",
            " rather than shaw ",
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


def _claims_missing_removal_savings_destroy(text: str) -> bool:
    return bool(_missing_removal_savings_destroy_span(text))


def _missing_removal_savings_destroy_span(text: str) -> str:
    if not _mentions_removal_savings_destroy(text):
        return ""
    if _is_pure_geographic_cluster_variant_acknowledging_removal_savings(text):
        return ""
    if _describes_existing_removal_savings_improvement(text):
        return ""
    return _first_regex_span(text, _MISSING_REMOVAL_SAVINGS_DESTROY_PATTERNS)


_MISSING_REMOVAL_SAVINGS_DESTROY_PATTERNS = (
        r"\b(?:missing|lacks?|absent|without|no)\b.{0,120}"
        r"\b(?:removal savings?|savings removal|detour cost|marginal distance contribution|cost of remove)\b",
        r"\b(?:removal savings?|savings removal|detour cost|marginal distance contribution|cost of remove)\b.{0,120}"
        r"\b(?:missing|lacks?|absent|without|no)\b",
        r"\b(?:worst removal|current|existing|active|baseline|solver)\b.{0,140}"
        r"\b(?:not|does not|doesn t|isn t|is not)\b.{0,80}"
        r"\b(?:removal savings?|savings from removal|cost of remove|detour cost)\b",
)


def _duplicates_removal_savings_destroy(text: str) -> bool:
    if not _mentions_removal_savings_destroy(text):
        return False
    if _is_pure_geographic_cluster_variant_acknowledging_removal_savings(text):
        return False
    if (
        _is_random_or_noise_removal_variant(text)
        and _is_removal_savings_contrast_or_negated_addition(text)
    ):
        return False
    if _is_random_or_noise_removal_variant(text) and not _explicit_removal_savings_claim(
        text
    ):
        return False
    if _describes_existing_removal_savings_improvement(text):
        return False
    patterns = (
        r"\b(?:add|introduce|implement|enable|create|build|register)\b.{0,80}"
        r"\b(?:new|novel|entirely new|fourth|additional)?\b.{0,80}"
        r"\b(?:savings removal|removal savings?|detour cost|marginal distance contribution|cost of remove)\b"
        r".{0,100}\b(?:destroy|remov(?:al|e)|operator|heuristic|capability)\b",
        r"\b(?:add|introduce|implement|enable|create|build|register)\b.{0,100}"
        r"\b(?:savings removal|savings based removal|detour based removal|position aware targeted removal)\b",
        r"\b(?:savings removal|removal savings?|detour cost|marginal distance contribution|cost of remove)\b"
        r".{0,100}\b(?:destroy|remov(?:al|e)|operator|heuristic|capability)\b.{0,80}"
        r"\b(?:new|novel|entirely new|fourth|additional|absent|missing|lacks?)\b",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def _claims_missing_route_removal(text: str) -> bool:
    return bool(_missing_route_removal_span(text))


def _missing_route_removal_span(text: str) -> str:
    if not _mentions_route_removal(text):
        return ""
    if (
        _targets_contiguous_segment_destroy_not_whole_route_removal(text)
        or _targets_perturbation_or_restart_not_removal_family(text)
    ):
        return ""
    if _describes_existing_route_removal_improvement(text):
        return ""
    return _first_regex_span(
        text,
        (
            r"\b(?:missing|lacks?|absent|without|no|does not have|does not include|"
            r"doesn't have|doesn't include)\b.{0,100}\b(?:whole route|"
            r"entire route|route level|route removal|route destroy)"
            r"\b.{0,60}\b(?:destroy|remov(?:al|e)|operator)\b",
            r"\b(?:whole route|entire route|route level|route removal|"
            r"route destroy)\b.{0,60}\b(?:destroy|remov(?:al|e)|operator)"
            r"\b.{0,100}\b(?:missing|lacks?|absent|without|no|does not have|"
            r"does not include|doesn't have|doesn't include)\b",
        ),
    )


def _duplicates_route_removal(text: str) -> bool:
    if not _mentions_route_removal(text):
        return False
    if (
        _targets_contiguous_segment_destroy_not_whole_route_removal(text)
        or _targets_perturbation_or_restart_not_removal_family(text)
    ):
        return False
    if _describes_existing_route_removal_improvement(text):
        return False
    return bool(
        re.search(
            r"\b(?:add|introduce|implement|enable|create|build|register)\b"
            r".{0,100}\b(?:whole route|entire route|route level|route removal|"
            r"route destroy)\b.{0,60}"
            r"\b(?:destroy|remov(?:al|e)|operator|capability)\b",
            text,
        )
        or re.search(
            r"\b(?:whole route|entire route|route level|route removal|"
            r"route destroy)\b.{0,60}\b(?:destroy|remov(?:al|e)|operator)"
            r"\b.{0,100}\b(?:new|novel|additional|first|missing|absent|lacks?)\b",
            text,
        )
    )


def _claims_missing_random_removal_destroy(text: str) -> bool:
    return bool(_missing_random_removal_destroy_span(text))


def _missing_random_removal_destroy_span(text: str) -> str:
    if not _mentions_random_removal_destroy(text):
        return ""
    if _describes_existing_random_removal_variant(text):
        return ""
    span = _first_regex_span(text, _MISSING_RANDOM_REMOVAL_DESTROY_PATTERNS)
    if _span_is_random_exploration_weakness_not_missing_removal(span):
        return ""
    return span


_MISSING_RANDOM_REMOVAL_DESTROY_PATTERNS = (
    r"\b(?:missing|lacks?|absent|without|no|does not have|does not include|"
    r"doesn'?t have|doesn'?t include)\b.{0,100}"
    r"\b(?:random(?: customer)? removal|random customer destroy|"
    r"random destroy|randomized removal|randomized destroy|uniform random removal)\b",
    r"\b(?:random(?: customer)? removal|random customer destroy|"
    r"random destroy|randomized removal|randomized destroy|uniform random removal)"
    r"\b.{0,100}\b(?:missing|lacks?|absent|without|no|does not have|"
    r"does not include|doesn'?t have|doesn'?t include)\b",
)


def _duplicates_random_removal_destroy(text: str) -> bool:
    if not _mentions_random_removal_destroy(text):
        return False
    if _describes_existing_random_removal_variant(text):
        return False
    patterns = (
        r"\b(?:add|introduce|implement|enable|create|build|register)\b"
        r".{0,100}\b(?:random(?: customer)? removal|random customer destroy|"
        r"random destroy|randomized removal|randomized destroy|"
        r"uniform random removal)\b",
        r"\b(?:random(?: customer)? removal|random customer destroy|"
        r"random destroy|randomized removal|randomized destroy|"
        r"uniform random removal)\b.{0,100}"
        r"\b(?:new|novel|additional|first|missing|absent|lacks?|new capability|"
        r"new operator|new destroy)\b",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def _span_is_random_exploration_weakness_not_missing_removal(span: str) -> bool:
    if not span:
        return False
    return bool(
        re.search(r"\blacks?\b.{0,40}\brandom exploration\b", span)
        or re.search(r"\bmissing\b.{0,40}\brandom exploration\b", span)
    )


def _claims_missing_regret_insertion_repair(text: str) -> bool:
    if not _mentions_regret_insertion_repair(text):
        return False
    if _is_non_regret_repair_variant(text) and not _missing_regret_insertion_repair_span(
        text
    ):
        return False
    if _uses_existing_regret_repair_after_new_destroy(text):
        return False
    if _describes_existing_regret_repair_improvement(text):
        return False
    return bool(_missing_regret_insertion_repair_span(text))


def _duplicates_regret_insertion_repair(text: str) -> bool:
    if not _mentions_regret_insertion_repair(text):
        return False
    if _is_non_regret_repair_variant(text):
        return False
    if _uses_existing_regret_repair_after_new_destroy(text):
        return False
    if _describes_existing_regret_repair_improvement(text):
        return False
    return bool(_duplicate_regret_insertion_repair_span(text))


def _missing_regret_insertion_repair_span(text: str) -> str:
    span = _first_regex_span(
        text,
        (
            r"\b(?:missing|lacks?|absent|without|no|does not have|does not include|"
            r"doesn't have|doesn't include)\b.{0,120}\b(?:regret[- ]?[23k]?|"
            r"regret insertion|regret repair)\b",
            r"\b(?:regret[- ]?[23k]?|regret insertion|regret repair)\b"
            r".{0,120}\b(?:missing|lacks?|absent|without|no|does not have|"
            r"does not include|doesn't have|doesn't include)\b",
        ),
    )
    if span and re.search(
        r"\bwithout\b.{0,80}\b(?:add|adding|introduce|introducing|create|creating|new)\b",
        span,
    ):
        return ""
    return span


def _duplicate_regret_insertion_repair_span(text: str) -> str:
    return _first_regex_span(
        text,
        (
            r"\b(?:add|introduce|implement|enable|create|build|register)\b"
            r".{0,120}\b(?:regret[- ]?[23k]?|regret insertion|regret repair)"
            r"\b.{0,80}\b(?:repair|insertion|operator|heuristic|capability)\b",
            r"\b(?:regret[- ]?[23k]?|regret insertion|regret repair)\b"
            r".{0,100}\b(?:new|novel|additional|first|missing|absent|lacks?)\b",
        ),
    )


def _uses_existing_regret_repair_after_new_destroy(text: str) -> bool:
    if not _mentions_regret_insertion_repair(text):
        return False
    if _missing_regret_insertion_repair_span(text):
        return False
    if not _has_any(
        text,
        (
            "destroy",
            "removal",
            "remove",
            "operator",
            "removed customers",
            "removed customer",
        ),
    ):
        return False
    return _has_any(
        text,
        (
            "use existing regret",
            "uses existing regret",
            "using existing regret",
            "call existing regret",
            "calls existing regret",
            "use regret repair",
            "uses regret repair",
            "using regret repair",
            "call regret repair",
            "calls regret repair",
            "apply regret repair",
            "applies regret repair",
            "reuse regret",
            "reuses regret",
            "route through regret",
            "routes through regret",
            "then regret",
            "then use regret",
            "then uses regret",
            "then calls regret",
            "after removal regret",
            "after destroy regret",
            "repair removed customers with regret",
            "reinsert removed customers with regret",
            "forces regret repair",
            "force regret repair",
            "paired with regret repair",
            "followed by regret repair",
        ),
    )


def _regret_insertion_allowed_variant_guidance(text: str) -> str:
    if not _uses_existing_regret_repair_after_new_destroy(text):
        return ""
    return (
        "Allowed variant: the proposal may add or modify a destroy/removal "
        "operator that routes removed customers through the existing regret "
        "repair portfolio; do not treat that as claiming regret repair is absent."
    )


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
            "geographic cluster",
            "spatial cluster",
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
            r"\bworst removal\b.{0,140}"
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
            r".{0,80}\bworst removal\b",
            text,
        )
    )


def _acknowledges_existing_shaw_related_removal(text: str) -> bool:
    if not _has_any(
        text,
        (
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


def _describes_existing_shaw_related_improvement(text: str) -> bool:
    if _scopes_change_to_existing_shaw_related_removal(text):
        return True
    if _is_existing_shaw_variant_with_negated_missing_claim(text):
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


def _describes_existing_removal_savings_improvement(text: str) -> bool:
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
            "new heuristic",
            "entirely new",
            "fourth destroy",
            "additional destroy",
            "savings removal",
        ),
    ):
        return False
    if not _has_any(text, ("existing", "current", "already", "worst removal")):
        return False
    return _has_any(
        text,
        (
            "refine",
            "tune",
            "adjust",
            "adapt",
            "adaptive",
            "diversify",
            "sampling",
            "noise",
            "p sampling",
            "weight",
            "weights",
            "budget",
            "candidate ordering",
        ),
    )


def _describes_existing_route_removal_improvement(text: str) -> bool:
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
            "entirely new",
        ),
    ):
        return False
    if not _has_any(text, ("existing", "current", "already", "_route_removal")):
        return False
    return _has_any(
        text,
        (
            "refine",
            "tune",
            "adjust",
            "adapt",
            "sampling",
            "weight",
            "trigger",
            "budget",
            "candidate",
        ),
    )


def _describes_existing_random_removal_variant(text: str) -> bool:
    if not _mentions_random_removal_destroy(text):
        return False
    if not _acknowledges_existing_random_removal_destroy(text):
        return False
    if _has_any(
        text,
        (
            "missing random removal",
            "lacks random removal",
            "lack random removal",
            "absent random removal",
            "no random removal",
            "without random removal",
            "missing random customer removal",
            "lacks random customer removal",
            "new random removal capability",
            "new random removal operator",
        ),
    ):
        return False
    return _has_any(
        text,
        (
            "refine",
            "tune",
            "adjust",
            "adapt",
            "adaptive",
            "variant",
            "distribution",
            "biased",
            "bias",
            "weighted",
            "weight",
            "noise",
            "schedule",
            "sampling",
            "probability",
            "probabilistic",
            "trigger",
            "budget",
            "q budget",
            "telemetry",
            "instrumentation",
        ),
    )


def _acknowledges_existing_random_removal_destroy(text: str) -> bool:
    if not _mentions_random_removal_destroy(text):
        return False
    random_family = (
        r"(?:random removal|random destroy|random customer removal|"
        r"scheduler random|randomized removal|uniform random removal)"
    )
    return bool(
        re.search(
            r"\b(?:existing|current|active|baseline|already)\b.{0,100}\b"
            + random_family
            + r"\b",
            text,
        )
        or re.search(
            r"\b"
            + random_family
            + r"\b.{0,100}\b(?:already|exists?|registered|wired|present|"
            r"available|in the portfolio|in destroy ops)\b",
            text,
        )
    )


def _describes_existing_regret_repair_improvement(text: str) -> bool:
    if _has_any(
        text,
        (
            "missing",
            "lacks",
            "lack ",
            "absent",
            "new capability",
            "new repair capability",
            "new operator",
            "new heuristic",
            "entirely new",
            "additional repair",
        ),
    ):
        return False
    if not _has_any(
        text,
        ("existing", "current", "already", "_regret2_insertion", "_regret3_insertion"),
    ):
        return False
    return _has_any(
        text,
        (
            "refine",
            "tune",
            "adjust",
            "adapt",
            "bias",
            "sampling",
            "weight",
            "candidate ordering",
            "budget",
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


def _is_existing_shaw_variant_with_negated_missing_claim(text: str) -> bool:
    if not _has_any(
        text,
        (
            "existing _shaw_removal",
            "existing shaw removal",
            "variant of the existing shaw",
            "modify existing _shaw_removal",
        ),
    ):
        return False
    if not _has_any(
        text,
        (
            "trigger",
            "scoring",
            "score",
            "schedule",
            "candidate filtering",
            "filtering",
            "adaptive",
            "weights",
        ),
    ):
        return False
    return _has_any(
        text,
        (
            "not a new missing",
            "not claiming",
            "do not claim",
            "does not claim",
            "without claiming",
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
