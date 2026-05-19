"""Local-search mechanism premise predicates for CVRP mechanism novelty."""

from __future__ import annotations

import re

from scion.problems.cvrp.mechanism_novelty.text import _has_any


def _claims_missing_or_opt_2_3(text: str) -> bool:
    if not _mentions_cross_route_or_opt_segment_relocation(text):
        return False
    if _claims_unsystematic_cross_route_segment_relocation_gap(text):
        return True
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


def _claims_missing_cross_route_tail_exchange(text: str) -> bool:
    if not _mentions_cross_route_tail_exchange(text):
        return False
    if _describes_existing_tail_exchange_improvement(text):
        return False
    patterns = (
        r"\b(?:missing|lacks?|absent|without|no|does not have|does not include|"
        r"doesn't have|doesn't include)\b.{0,100}"
        r"\b(?:tail|suffix|two opt star|2 opt star|2optstar|two-opt-star)"
        r"\b.{0,100}\b(?:swap|exchange|move|neighborhood|operator)\b",
        r"\b(?:tail|suffix|two opt star|2 opt star|2optstar|two-opt-star)"
        r"\b.{0,100}\b(?:swap|exchange|move|neighborhood|operator)\b.{0,100}"
        r"\b(?:missing|lacks?|absent|without|no|does not have|does not include|"
        r"doesn't have|doesn't include)\b",
    )
    return any(re.search(pattern, text) for pattern in patterns)


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


def _mentions_cross_route_or_opt_segment_relocation(text: str) -> bool:
    if not _has_route_scope(text):
        return False
    return _mentions_or_opt_family(text) or _mentions_segment_relocation(text)


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


def _claims_unsystematic_cross_route_segment_relocation_gap(text: str) -> bool:
    if not _mentions_cross_route_or_opt_segment_relocation(text):
        return False
    if _targets_existing_or_opt_filter_gap(text) or _adds_or_opt_improvement_control(
        text
    ):
        return False
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
    if _has_any(text, gap_terms):
        return True
    return bool(
        re.search(
            r"\b(?:missing|lacks?|without|no)\b.{0,90}"
            r"\b(?:ordered\s+)?(?:segment|chain|length\s*[23]|two customer|"
            r"three customer|2 customer|3 customer|2\s+3 customer|"
            r"k customer|multi customer)\b"
            r".{0,90}\b(?:across routes|cross route|inter route|between route|"
            r"different route)\b",
            text,
        )
        or re.search(
            r"\b(?:across routes|cross route|inter route|between route|"
            r"different route)\b.{0,90}"
            r"\b(?:missing|lacks?|without|no)\b.{0,90}"
            r"\b(?:ordered\s+)?(?:segment|chain|length\s*[23]|two customer|"
            r"three customer|2 customer|3 customer|2\s+3 customer|"
            r"k customer|multi customer)\b",
            text,
        )
    )
