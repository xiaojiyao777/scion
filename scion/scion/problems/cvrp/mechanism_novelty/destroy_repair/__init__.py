"""Destroy/repair premise predicates for CVRP mechanism novelty.

This package preserves the previous module import surface while splitting the
family-specific text matchers into smaller files.
"""
from __future__ import annotations

from scion.problems.cvrp.mechanism_novelty.destroy_repair.removal_savings import (
    _claims_missing_removal_savings_destroy,
    _duplicates_removal_savings_destroy,
    _missing_removal_savings_destroy_span,
)
from scion.problems.cvrp.mechanism_novelty.destroy_repair.random_removal import (
    _claims_missing_random_removal_destroy,
    _duplicates_random_removal_destroy,
    _missing_random_removal_destroy_span,
)
from scion.problems.cvrp.mechanism_novelty.destroy_repair.regret import (
    _claims_missing_regret_insertion_repair,
    _duplicate_regret_insertion_repair_span,
    _duplicates_regret_insertion_repair,
    _missing_regret_insertion_repair_span,
    _regret_insertion_allowed_variant_guidance,
)
from scion.problems.cvrp.mechanism_novelty.destroy_repair.route import (
    _claims_missing_route_removal,
    _duplicates_route_removal,
    _missing_route_removal_span,
)
from scion.problems.cvrp.mechanism_novelty.destroy_repair.shaw import (
    _claims_missing_shaw_related_removal,
    _duplicates_shaw_related_removal,
    _missing_shaw_related_removal_span,
)

__all__ = [
    "_claims_missing_removal_savings_destroy",
    "_claims_missing_random_removal_destroy",
    "_claims_missing_regret_insertion_repair",
    "_claims_missing_route_removal",
    "_claims_missing_shaw_related_removal",
    "_duplicate_regret_insertion_repair_span",
    "_duplicates_removal_savings_destroy",
    "_duplicates_random_removal_destroy",
    "_duplicates_regret_insertion_repair",
    "_duplicates_route_removal",
    "_duplicates_shaw_related_removal",
    "_missing_removal_savings_destroy_span",
    "_missing_random_removal_destroy_span",
    "_missing_regret_insertion_repair_span",
    "_missing_route_removal_span",
    "_missing_shaw_related_removal_span",
    "_regret_insertion_allowed_variant_guidance",
]
