"""Test helpers for loading problem-defined family taxonomies."""
from __future__ import annotations

from pathlib import Path

import yaml

from scion.problem.spec import FamilyTaxonomySpec


def problem_family_taxonomy(problem_id: str) -> FamilyTaxonomySpec:
    path = Path(__file__).resolve().parents[1] / "problems" / problem_id / "problem-v1.yaml"
    with open(path, encoding="utf-8") as fh:
        payload = yaml.safe_load(fh) or {}
    return FamilyTaxonomySpec(**payload["family_taxonomy"])


def warehouse_family_taxonomy() -> FamilyTaxonomySpec:
    return problem_family_taxonomy("warehouse_delivery")


def cvrp_family_taxonomy() -> FamilyTaxonomySpec:
    return problem_family_taxonomy("cvrp")
