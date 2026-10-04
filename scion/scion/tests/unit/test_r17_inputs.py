"""R17 changes quota handling and safe history, not the scientific contract."""

import json

import pytest

from scion.core.research_input import normalize_research_input
from scion.tests.unit import test_r16_inputs as previous

CVRP = "v04-cvrp-r17-quota-aware-autonomous"
WAREHOUSE = "v04-r17-warehouse-quota-control"


@pytest.mark.parametrize(
    "prefix,old,seed_start,count",
    [(CVRP, previous.CVRP, 180000, 9), (WAREHOUSE, previous.WAREHOUSE, 190000, 5)],
)
def test_fresh_seeds_and_unchanged_protocol(prefix, old, seed_start, count):
    previous.test_fresh_seeds_and_unchanged_protocol(prefix, old, seed_start, count)


@pytest.mark.parametrize(
    "prefix,spec_path,split_prefix,rounds,source",
    [
        (
            CVRP,
            "scion/scion/problems/cvrp/problem-v1.yaml",
            "v04-cvrp-r7-autonomous-source-continuation",
            12,
            "scion/scion/problems/cvrp",
        ),
        (
            WAREHOUSE,
            "scion/problems/warehouse_delivery/problem-v1.yaml",
            WAREHOUSE,
            2,
            "surrogate",
        ),
    ],
)
def test_full_public_formal_closure(prefix, spec_path, split_prefix, rounds, source):
    previous.test_full_public_formal_closure(
        prefix, spec_path, split_prefix, rounds, source
    )


def test_complete_question_observations_and_screening_only_addition():
    old = json.loads(
        (previous.INPUTS / f"{previous.CVRP}-research-input.json").read_text()
    )
    new = normalize_research_input(
        json.loads((previous.INPUTS / f"{CVRP}-research-input.json").read_text())
    )
    assert new["observations"] == old["observations"]
    assert len(new["observations"]) == 5
    prefix = old["current_question"].replace("prospective R16", "prospective R17")
    assert new["current_question"].startswith(prefix)
    addition = new["current_question"][len(prefix) :]
    for fact in (
        "all six ordinary safe screening records",
        "74 valid screening pairs",
        "above 1500 customers",
        "not production-path activation evidence",
        "not real collaborator compatibility",
        "No R16 candidate is selected or merged",
        "without requiring a particular test, file, algorithm or activity gate",
    ):
        assert fact in addition
    for private in (
        "B-n39-k5",
        "X-n106-k14",
        "tai385",
        "A-n62-k8",
        "X-n228-k23",
        "X-n627-k43",
        "1302.75",
        "-12.5",
        "VALIDATION_FAIL",
        "245a4c56",
        "/metrics/",
        ".py",
        "OUTER_HARDWALL",
        "PROVIDER_TRANSIENT",
        "401",
        "429",
    ):
        assert private not in json.dumps(new)
