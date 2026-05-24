"""Local-search mechanism premise predicates for CVRP mechanism novelty."""

from __future__ import annotations

import re

from scion.problems.cvrp.mechanism_novelty.text import _first_regex_span, _has_any


def _claims_missing_or_opt_2_3(text: str) -> bool:
    if not _mentions_cross_route_or_opt_segment_relocation(text):
        return False
    if _is_three_opt_chain_variant_scope(text):
        return False
    if _is_ejection_chain_variant_scope(text):
        return False
    if _mentions_intra_two_opt(text) and _acknowledges_existing_or_opt(text):
        return False
    if _claims_unsystematic_cross_route_segment_relocation_gap(text):
        return True
    if _describes_existing_or_opt_improvement(text):
        return False
    return bool(_missing_or_opt_2_3_span(text))


def _missing_or_opt_2_3_span(text: str) -> str:
    if not _mentions_cross_route_or_opt_segment_relocation(text):
        return ""
    if _is_three_opt_chain_variant_scope(text):
        return ""
    if _is_ejection_chain_variant_scope(text):
        return ""
    if _mentions_intra_two_opt(text) and _acknowledges_existing_or_opt(text):
        return ""
    if _claims_unsystematic_cross_route_segment_relocation_gap(text):
        return _unsystematic_cross_route_segment_gap_span(text)
    if _describes_existing_or_opt_improvement(text):
        return ""
    return _first_regex_span(text, _MISSING_OR_OPT_2_3_PATTERNS)


_MISSING_OR_OPT_2_3_PATTERNS = (
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


def _duplicates_or_opt_2_3(text: str) -> bool:
    if not _mentions_cross_route_or_opt_segment_relocation(text):
        return False
    if _is_three_opt_chain_variant_scope(text):
        return False
    if _is_ejection_chain_variant_scope(text):
        return False
    if _mentions_intra_two_opt(text) and _acknowledges_existing_or_opt(text):
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


def _claims_missing_or_opt_1(text: str) -> bool:
    if not _mentions_or_opt_1(text):
        return False
    if _is_adaptive_vns_operator_selection_scope(text):
        return False
    explicit = bool(_missing_or_opt_1_span(text))
    if explicit:
        return True
    if _describes_existing_or_opt_improvement(text):
        return False
    return False


def _missing_or_opt_1_span(text: str) -> str:
    if not _mentions_or_opt_1(text):
        return ""
    if _is_adaptive_vns_operator_selection_scope(text):
        return ""
    if _describes_existing_or_opt_improvement(text):
        return ""
    span = _first_regex_span(
        text,
        (
            r"\b(?:missing|lacks?|absent|without|no|does not have|does not include|"
            r"doesn't have|doesn't include)\b.{0,100}\b(?:or opt 1|or-opt-1|"
            r"oropt1|single customer relocat(?:e|ion)|one customer relocat(?:e|ion))\b",
            r"\b(?:or opt 1|or-opt-1|oropt1|single customer relocat(?:e|ion)|"
            r"one customer relocat(?:e|ion))\b.{0,100}\b(?:missing|lacks?|"
            r"absent|without|no|does not have|does not include|doesn't have|"
            r"doesn't include)\b",
        ),
    )
    if _span_lists_existing_operator_then_other_gap(span):
        return ""
    if _span_targets_existing_or_opt_filter_gap(span):
        return ""
    return span


def _duplicates_or_opt_1(text: str) -> bool:
    if not _mentions_or_opt_1(text):
        return False
    if _is_adaptive_vns_operator_selection_scope(text):
        return False
    explicit = bool(
        re.search(
            r"\b(?:add|introduce|implement|enable|create|build|register)\b"
            r".{0,100}\b(?:or opt 1|or-opt-1|oropt1|single customer "
            r"relocat(?:e|ion)|one customer relocat(?:e|ion))\b",
            text,
        )
        or re.search(
            r"\b(?:or opt 1|or-opt-1|oropt1|single customer relocat(?:e|ion)|"
            r"one customer relocat(?:e|ion))\b.{0,100}\b(?:new|novel|first|"
            r"additional|missing|absent|lacks?)\b",
            text,
        )
    )
    if explicit:
        return True
    if _describes_existing_or_opt_improvement(text):
        return False
    return False


def _claims_missing_intra_two_opt(text: str) -> bool:
    return bool(_missing_intra_two_opt_span(text))


def _missing_intra_two_opt_span(text: str) -> str:
    if not _mentions_intra_two_opt(text):
        return ""
    if _is_adaptive_vns_neighborhood_ordering_scope(text):
        return ""
    if _describes_existing_intra_two_opt_improvement(text):
        return ""
    span = _has_missing_gap_near(
        text,
        _INTRA_TWO_OPT_TERMS,
    )
    if _span_targets_existing_intra_two_opt_filter_gap(span):
        return ""
    if _span_targets_cross_route_or_non_intra_variant(span):
        return ""
    if _span_lists_existing_operator_then_other_gap(span):
        return ""
    return span


_INTRA_TWO_OPT_TERMS = (
    "intra route 2 opt",
    "intra-route 2-opt",
    "intra route two opt",
    "within route 2 opt",
    "within-route 2-opt",
    "two opt intra",
    "_two_opt_intra",
    "route internal 2 opt",
    "route-internal 2-opt",
    "segment reversal",
    "arc reversal",
)


def _duplicates_intra_two_opt(text: str) -> bool:
    if not _mentions_intra_two_opt(text):
        return False
    if _mentions_existing_intra_two_opt_as_context_for_variant(text):
        return False
    if _describes_existing_intra_two_opt_improvement(text):
        return False
    return bool(
        re.search(
            r"\b(?:add|introduce|implement|enable|create|build|register)\b"
            r".{0,120}\b(?:intra route|intra-route|within route|within-route|"
            r"route internal|route-internal|_two_opt_intra|two opt intra)"
            r"\b.{0,120}\b(?:2 opt|2-opt|two opt|reversal|operator|neighborhood)\b",
            text,
        )
        or re.search(
            r"\b(?:intra route|intra-route|within route|within-route|route internal|"
            r"route-internal|_two_opt_intra|two opt intra)\b.{0,120}"
            r"\b(?:2 opt|2-opt|two opt|reversal|operator|neighborhood)\b.{0,80}"
            r"\b(?:new|novel|first|additional|missing|absent|lacks?)\b",
            text,
        )
    )


def _mentions_intra_two_opt(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:_two_opt_intra|two opt intra|intra route 2 opt|"
            r"intra-route 2-opt|intra route two opt|within route 2 opt|"
            r"within-route 2-opt|route internal 2 opt|route-internal 2-opt)\b",
            text,
        )
        or (
            _has_any(text, ("intra route", "intra-route", "within route", "within-route"))
            and _has_any(text, ("2 opt", "2-opt", "two opt", "segment reversal"))
        )
    )


def _describes_existing_intra_two_opt_improvement(text: str) -> bool:
    if not _mentions_intra_two_opt(text):
        return False
    if not _has_any(text, ("existing", "current", "already", "_two_opt_intra")):
        return False
    return _has_any(
        text,
        (
            "refine",
            "tune",
            "adjust",
            "filter",
            "candidate",
            "budget",
            "score",
            "scoring",
            "delta",
        ),
    )


def _mentions_existing_intra_two_opt_as_context_for_variant(text: str) -> bool:
    if not _mentions_intra_two_opt(text):
        return False
    if not _has_any(text, ("existing", "current", "already", "present")):
        return False
    return _has_any(
        text,
        (
            "cross route",
            "inter route",
            "between route",
            "across routes",
            "different route",
            "3 opt",
            "three opt",
            "double bridge",
            "neighborhood order",
            "neighborhood scheduling",
            "candidate",
            "filter",
            "scoring",
        ),
    )


def _acknowledges_existing_or_opt(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:existing|current|already|present|contains?|covers?|has|built in|"
            r"built-in)\b.{0,80}\b(?:or opt|oropt|_or_opt_[123])\b",
            text,
        )
        or re.search(
            r"\b(?:or opt|oropt|_or_opt_[123])\b.{0,80}\b(?:existing|current|"
            r"already|present|contains?|covers?|built in|built-in)\b",
            text,
        )
    )


def _span_lists_existing_operator_then_other_gap(span: str) -> bool:
    if not span:
        return False
    if not _has_any(
        span,
        (
            "existing",
            "already",
            "present",
            "contains",
            "registered",
        ),
    ):
        return False
    if not _has_any(span, ("missing", "lacks", "lack ", "absent", "without", " no ")):
        return False
    return _has_any(
        span,
        (
            "but",
            "however",
            "while",
            "although",
            "whereas",
            "rather than",
            "instead",
        ),
    )


def _span_targets_cross_route_or_non_intra_variant(span: str) -> bool:
    if not span:
        return False
    if _has_any(span, ("intra route", "within route", "route internal", "two opt intra")):
        return False
    return _has_any(
        span,
        (
            "cross route",
            "inter route",
            "between route",
            "across routes",
            "different route",
            "3 opt",
            "three opt",
            "double bridge",
        ),
    )


def _has_missing_gap_near(text: str, terms: tuple[str, ...]) -> str:
    missing = (
        r"\b(?:missing|lacks?|absent|without|no|does not have|does not include|"
        r"doesn't have|doesn't include)\b"
    )
    term_pattern = r"\b(?:" + "|".join(re.escape(term) for term in terms) + r")\b"
    return _first_regex_span(
        text,
        (
            missing + r".{0,120}" + term_pattern,
            term_pattern + r".{0,120}" + missing,
        ),
    )


def _claims_missing_cross_route_tail_exchange(text: str) -> bool:
    return bool(_missing_cross_route_tail_exchange_span(text))


def _missing_cross_route_tail_exchange_span(text: str) -> str:
    if not _mentions_cross_route_tail_exchange(text):
        return ""
    if _describes_existing_tail_exchange_improvement(text):
        return ""
    return _first_regex_span(text, _MISSING_CROSS_ROUTE_TAIL_EXCHANGE_PATTERNS)


_MISSING_CROSS_ROUTE_TAIL_EXCHANGE_PATTERNS = (
        r"\b(?:missing|lacks?|absent|without|no|does not have|does not include|"
        r"doesn't have|doesn't include)\b.{0,100}"
        r"\b(?:tail|suffix|two opt star|2 opt star|2optstar|two-opt-star)"
        r"\b.{0,100}\b(?:swap|exchange|move|neighborhood|operator)\b",
        r"\b(?:tail|suffix|two opt star|2 opt star|2optstar|two-opt-star)"
        r"\b.{0,100}\b(?:swap|exchange|move|neighborhood|operator)\b.{0,100}"
        r"\b(?:missing|lacks?|absent|without|no|does not have|does not include|"
        r"doesn't have|doesn't include)\b",
)


def _duplicates_cross_route_tail_exchange(text: str) -> bool:
    if not _mentions_cross_route_tail_exchange(text):
        return False
    if _describes_existing_tail_exchange_improvement(text):
        return False
    return bool(
        re.search(
            r"\b(?:add|introduce|implement|enable|create|build)\b.{0,100}"
            r"\b(?:new|novel|first|cross route|inter route|between route|"
            r"across routes|different route)\b.{0,120}"
            r"\b(?:tail|suffix|two opt star|2 opt star|2optstar|two-opt-star)"
            r"\b.{0,80}\b(?:swap|exchange|move|neighborhood|operator)\b",
            text,
        )
    )


def _mentions_cross_route_tail_exchange(text: str) -> bool:
    return _has_route_scope(text) and _has_any(
        text,
        (
            "tail swap",
            "tail exchange",
            "suffix swap",
            "suffix exchange",
            "cross route tail",
            "cross route suffix",
            "inter route tail",
            "inter route suffix",
            "two opt star",
            "2 opt star",
            "2optstar",
            "two-opt-star",
        ),
    )


def _describes_existing_tail_exchange_improvement(text: str) -> bool:
    if not _mentions_cross_route_tail_exchange(text):
        return False
    if _has_any(text, ("existing", "current", "already", "_two_opt_star")) and _has_any(
        text,
        (
            "improve",
            "refine",
            "tune",
            "adjust",
            "filter",
            "candidate",
            "budget",
            "score",
            "scoring",
        ),
    ):
        return True
    return False


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


def _mentions_or_opt_1(text: str) -> bool:
    return bool(
        re.search(r"\b(?:or opt 1|or-opt-1|oropt1|_or_opt_1)\b", text)
        or (
            _has_any(text, ("or opt", "oropt"))
            and _has_any(
                text,
                (
                    "single customer",
                    "one customer",
                    "length 1",
                    "1 customer",
                    "customer relocation",
                ),
            )
        )
    )


def _mentions_cross_route_or_opt_segment_relocation(text: str) -> bool:
    if not _has_route_scope(text):
        return False
    return _mentions_or_opt_family(text) or _mentions_segment_relocation(text)


def _is_three_opt_chain_variant_scope(text: str) -> bool:
    """Return true when Or-opt is contextual evidence for a 3-opt* variant.

    The active Or-opt fact proves length-1/2/3 cross-route segment relocation.
    It does not by itself prove a three-route / triple-edge 3-opt* chain
    reconnection neighborhood. Treat hypotheses that acknowledge or contrast
    existing Or-opt while proposing that 3-opt* family as variants, not missing
    Or-opt premises.
    """
    if not _mentions_three_opt_chain_exchange(text):
        return False
    return (
        _acknowledges_existing_or_opt(text)
        or _contrasts_three_opt_against_or_opt(text)
        or _existing_cross_route_operator_context_mentions_or_opt(text)
    )


def _is_ejection_chain_variant_scope(text: str) -> bool:
    """Return true when Or-opt is context for a compound ejection-chain variant."""
    if not _mentions_ejection_chain_variant(text):
        return False
    return (
        _acknowledges_existing_or_opt(text)
        or _contrasts_ejection_chain_against_or_opt(text)
        or _existing_cross_route_operator_context_mentions_or_opt(text)
    )


def _mentions_ejection_chain_variant(text: str) -> bool:
    return _has_any(
        text,
        (
            "ejection chain",
            "ejection-chain",
            "ejection_chain",
            "chained displacement",
            "compound displacement",
            "compound relocation",
            "compound relocate",
            "chained relocate",
            "chained relocation",
            "displaced customer",
            "displaced customers",
            "ejects one",
            "ejecting one",
            "ejected customer",
            "ejected customers",
        ),
    )


def _contrasts_ejection_chain_against_or_opt(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:or opt|oropt|_or_opt_[123])\b.{0,180}"
            r"\b(?:but|while|although|whereas|rather than|distinct|different|"
            r"beyond|not covered|not reachable)\b.{0,180}"
            r"\b(?:ejection chain|ejection-chain|chained displacement|"
            r"compound displacement|compound relocat(?:e|ion)|displaced "
            r"customer|eject(?:s|ing|ed) customer)\b",
            text,
        )
        or re.search(
            r"\b(?:ejection chain|ejection-chain|chained displacement|"
            r"compound displacement|compound relocat(?:e|ion)|displaced "
            r"customer|eject(?:s|ing|ed) customer)\b.{0,180}"
            r"\b(?:distinct|different|beyond|not covered|not reachable|rather "
            r"than)\b.{0,180}\b(?:or opt|oropt|_or_opt_[123])\b",
            text,
        )
    )


def _mentions_three_opt_chain_exchange(text: str) -> bool:
    return _has_any(
        text,
        (
            "3 opt",
            "3-opt",
            "three opt",
            "three-opt",
            "three_opt",
            "3opt",
            "three way",
            "three-way",
            "three route",
            "three-route",
            "triple edge",
            "triple-edge",
            "triple route",
            "triple-route",
            "multi route chain",
            "multi-route chain",
            "chain reconnection",
            "lin-kernighan",
            "lin kernighan",
        ),
    )


def _contrasts_three_opt_against_or_opt(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:different|distinct|separate|not achievable|not covered|"
            r"not reachable|beyond)\b.{0,120}\b(?:or opt|oropt|_or_opt_[123])\b",
            text,
        )
        or re.search(
            r"\b(?:or opt|oropt|_or_opt_[123])\b.{0,120}\b(?:different|distinct|"
            r"separate|not achievable|not covered|not reachable|beyond)\b",
            text,
        )
    )


def _existing_cross_route_operator_context_mentions_or_opt(text: str) -> bool:
    return bool(
        re.search(
            r"\bexisting\b.{0,80}\b(?:cross route|cross-route|inter route|"
            r"inter-route|between route|across routes)\b.{0,160}"
            r"\b(?:or opt|oropt|_or_opt_[123])\b",
            text,
        )
        or re.search(
            r"\b(?:or opt|oropt|_or_opt_[123])\b.{0,160}\bexisting\b.{0,80}"
            r"\b(?:cross route|cross-route|inter route|inter-route|between route|"
            r"across routes)\b",
            text,
        )
    )


def _mentions_or_opt_family(text: str) -> bool:
    return _has_any(text, ("or opt", "oropt"))


def _mentions_segment_relocation(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:ordered\s+)?(?:segment|chain|length\s*[23]|two customer|"
            r"three customer|2 customer|3 customer|2\s+3 customer|"
            r"k customer|multi customer)\b.{0,50}"
            r"\b(?:relocat(?:e|ion)|mov(?:e|ing)|exchang(?:e|ing))\b",
            text,
        )
        or re.search(
            r"\b(?:relocat(?:e|ion)|mov(?:e|ing)|exchang(?:e|ing))\b.{0,50}"
            r"\b(?:ordered\s+)?(?:segment|chain|length\s*[23]|two customer|"
            r"three customer|2 customer|3 customer|2\s+3 customer|"
            r"k customer|multi customer)\b",
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
    if _claims_unsystematic_cross_route_segment_relocation_gap(text):
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
        r"\b(?:existing|current|already present|built in|built-in|uses?|"
        r"contains?|registered|listed|includes?|applies?|runs?)\b.{0,140}"
        r"\b(?:or opt|oropt|_or_opt_[123])\b"
    )
    filter_gap = (
        r"\b(?:missing|lacks?|without|no|does not have|does not include|"
        r"doesn't have|doesn't include)\b.{0,90}"
        r"\b(?:filter|filtered|candidate|nearest neighbor|nn|prun(?:e|ing)|"
        r"ordering|order|adapt(?:ive|ation)?|success feedback|success rate|"
        r"score|scoring|delta)\b"
    )
    return bool(
        re.search(existing_or_opt + r".{0,180}" + filter_gap, text)
        or re.search(filter_gap + r".{0,180}" + existing_or_opt, text)
    )


def _span_targets_existing_or_opt_filter_gap(span: str) -> bool:
    if not span:
        return False
    if not _mentions_or_opt_family(span):
        return False
    if not _has_any(
        span,
        (
            "filter",
            "filtered",
            "candidate",
            "nearest neighbor",
            " nn ",
            "prune",
            "pruning",
            "ordering",
            "order",
            "adapt",
            "adaptive",
            "adaptation",
            "success feedback",
            "success rate",
            "score",
            "scoring",
            "delta",
        ),
    ):
        return False
    if not _has_any(
        span,
        ("without", "lacks", "lack ", "missing", "no ", "does not have"),
    ):
        return False
    return _has_any(
        span,
        (
            "_or_opt_",
            "existing",
            "current",
            "already",
            "present",
            "uses",
            "contains",
            "registered",
            "listed",
            "includes",
            "without adding a new",
        ),
    )


def _span_targets_existing_intra_two_opt_filter_gap(span: str) -> bool:
    if not span:
        return False
    if not _mentions_intra_two_opt(span):
        return False
    if not _has_any(
        span,
        (
            "filter",
            "filtered",
            "candidate",
            "nearest neighbor",
            " nn ",
            "prune",
            "pruning",
            "ordering",
            "order",
            "adapt",
            "adaptive",
            "adaptation",
            "success feedback",
            "success rate",
            "score",
            "scoring",
            "delta",
        ),
    ):
        return False
    return _has_any(
        span,
        ("without", "lacks", "lack ", "missing", "no ", "does not have"),
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
            "order",
            "adapt",
            "adaptive",
            "adaptation",
            "success feedback",
            "success rate",
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


def _claims_unsystematic_cross_route_segment_relocation_gap(text: str) -> bool:
    return bool(_unsystematic_cross_route_segment_gap_span(text))


def _unsystematic_cross_route_segment_gap_span(text: str) -> str:
    if not _mentions_cross_route_or_opt_segment_relocation(text):
        return ""
    if _targets_existing_or_opt_filter_gap(text) or _adds_or_opt_improvement_control(
        text
    ):
        return ""
    gap_terms = (
        "not systematically",
        "not systematic",
        "does not systematically",
        "doesn't systematically",
        "no systematic",
        "not explicitly",
        "does not explicitly",
        "doesn't explicitly",
    )
    for term in gap_terms:
        if term in text:
            start = max(0, text.find(term) - 80)
            end = min(len(text), text.find(term) + len(term) + 120)
            return text[start:end].strip()
    return _first_regex_span(text, _UNSYSTEMATIC_CROSS_ROUTE_SEGMENT_GAP_PATTERNS)


_UNSYSTEMATIC_CROSS_ROUTE_SEGMENT_GAP_PATTERNS = (
    r"\b(?:missing|lacks?|without|no)\b.{0,90}"
    r"\b(?:ordered\s+)?(?:segment|chain|length\s*[23]|two customer|"
    r"three customer|2 customer|3 customer|2\s+3 customer|"
    r"k customer|multi customer)\b"
    r".{0,90}\b(?:across routes|cross route|inter route|between route|"
    r"different route)\b",
    r"\b(?:across routes|cross route|inter route|between route|"
    r"different route)\b.{0,90}"
    r"\b(?:missing|lacks?|without|no)\b.{0,90}"
    r"\b(?:ordered\s+)?(?:segment|chain|length\s*[23]|two customer|"
    r"three customer|2 customer|3 customer|2\s+3 customer|"
    r"k customer|multi customer)\b",
)


def _is_adaptive_vns_neighborhood_ordering_scope(text: str) -> bool:
    if not _has_any(text, ("adaptive", "adapt", "success counter", "probability")):
        return False
    if not _has_any(
        text,
        (
            "vns",
            "neighborhood order",
            "neighborhood ordering",
            "neighborhood scheduling",
            "operator selection",
            "neighborhood selection",
            "fixed sequence",
            "fixed order",
        ),
    ):
        return False
    explicit_missing_operator = bool(
        re.search(
            r"\b(?:missing|lacks?|absent|without|no|does not have|does not include|"
            r"doesn't have|doesn't include)\b.{0,60}"
            r"\b(?:operator|neighborhood|move)\b.{0,60}"
            r"\b(?:2 opt|2-opt|two opt|segment reversal|_two_opt_intra)\b",
            text,
        )
    )
    return not explicit_missing_operator


def _is_adaptive_vns_operator_selection_scope(text: str) -> bool:
    if not _is_adaptive_vns_neighborhood_ordering_scope(text):
        return False
    return _has_any(
        text,
        (
            "operator selection",
            "operator selector",
            "operator ordering",
            "operator order",
            "operator schedule",
            "operator scheduling",
            "neighborhood selection",
            "neighborhood ordering",
            "neighborhood order",
            "productive operator",
            "success feedback",
            "success counter",
            "recent improvement",
            "fixed sequence",
            "fixed order",
        ),
    )
