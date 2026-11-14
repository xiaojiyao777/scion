"""Research-support R18 preserves complete inputs and all scientific gates."""

import json

import pytest

from scion.core.research_input import normalize_research_input
from scion.tests.unit import test_r16_inputs as helpers
from scion.tests.unit import test_r17_inputs as previous

CVRP = "v04-cvrp-r18-research-context-autonomous"
WAREHOUSE = "v04-r18-warehouse-research-context-control"


@pytest.mark.parametrize(
    "prefix,old,seed_start,count",
    [(CVRP, previous.CVRP, 200000, 9), (WAREHOUSE, previous.WAREHOUSE, 210000, 5)],
)
def test_fresh_seeds_and_unchanged_protocol(prefix, old, seed_start, count):
    helpers.test_fresh_seeds_and_unchanged_protocol(prefix, old, seed_start, count)


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
    helpers.test_full_public_formal_closure(
        prefix, spec_path, split_prefix, rounds, source
    )


def test_complete_question_observations_and_screening_only_addition():
    old = json.loads(
        (helpers.INPUTS / f"{previous.CVRP}-research-input.json").read_text()
    )
    new = normalize_research_input(
        json.loads((helpers.INPUTS / f"{CVRP}-research-input.json").read_text())
    )
    assert new["observations"] == old["observations"]
    assert len(new["observations"]) == 5
    prefix = old["current_question"].replace("prospective R17", "prospective R18")
    assert new["current_question"].startswith(prefix)
    addition = new["current_question"][len(prefix) :]
    for fact in (
        "all eleven ordinary screening records",
        "seven cumulative candidates and 166 valid screening pairs",
        "No R17 candidate is selected or merged",
        "independently recomputed reference answers",
        "not new scientific evidence or acceptance gates",
        "no mandatory testing style or specific optimization is prescribed",
    ):
        assert fact in addition
    for private in (
        "B-n39-k5",
        "X-n106-k14",
        "tai385",
        "A-n62-k8",
        "X-n228-k23",
        "X-n627-k43",
        "-2933.75",
        "5808.5",
        "VALIDATION_FAIL",
        "a4823782",
        "/metrics/",
        ".py",
    ):
        assert private not in json.dumps(new)
