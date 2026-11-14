"""R19 increases screening seed coverage without relaxing scientific gates."""

import json
from math import isqrt

import pytest
import yaml

from scion.config.problem import SeedLedgerConfig
from scion.core.research_input import normalize_research_input
from scion.tests.unit import test_r16_inputs as helpers
from scion.tests.unit import test_r18_inputs as previous

CVRP = "v04-cvrp-r19-reliable-probes-autonomous"
WAREHOUSE = "v04-r19-warehouse-reliable-probes-control"
WAREHOUSE_SOL61 = "v04-r19-warehouse-reliable-probes-sol61-control"
WAREHOUSE_IMPORT = "v04-r19-warehouse-import-feedback-control"


def test_only_cvrp_screening_seed_counts_change():
    def protocol(prefix):
        value = yaml.safe_load((helpers.INPUTS / f"{prefix}-protocol.yaml").read_text())
        value.pop("version")
        value["canary"].pop("seeds")
        return value

    old, new = protocol(previous.CVRP), protocol(CVRP)
    for suffix in ("protocol", "seeds"):
        raw = yaml.safe_load((helpers.INPUTS / f"{CVRP}-{suffix}.yaml").read_text())
        assert raw["version"] == "0.4-cvrp-r19-reliable-probes-autonomous"
    assert old["screening"]["n_seeds"] == 2
    assert old["screening"]["expand_n_seeds"] == 4
    assert new["screening"]["n_seeds"] == 4
    assert new["screening"]["expand_n_seeds"] == 6
    old["screening"].update(n_seeds=4, expand_n_seeds=6)
    assert new == old
    ledger = SeedLedgerConfig.from_yaml(helpers.INPUTS / f"{CVRP}-seeds.yaml")
    seeds = [*ledger.screening, *ledger.validation, *ledger.frozen, *ledger.canary]
    assert (
        seeds
        == [
            n
            for n in range(220001, 220500)
            if all(n % d for d in range(2, isqrt(n) + 1))
        ][:11]
    )
    assert len(ledger.screening) == 6
    raw = yaml.safe_load((helpers.INPUTS / f"{CVRP}-protocol.yaml").read_text())
    assert raw["canary"]["seeds"] == ledger.canary
    for path in helpers.INPUTS.glob("*-seeds.yaml"):
        if path.name == f"{CVRP}-seeds.yaml":
            continue
        other = SeedLedgerConfig.from_yaml(path)
        assert set(seeds).isdisjoint(
            [*other.screening, *other.validation, *other.frozen, *other.canary]
        )


def test_warehouse_protocol_unchanged_and_seeds_fresh():
    helpers.test_fresh_seeds_and_unchanged_protocol(
        WAREHOUSE, previous.WAREHOUSE, 230000, 5
    )


def test_sol61_control_preserves_protocol_and_uses_fresh_seeds():
    helpers.test_fresh_seeds_and_unchanged_protocol(
        WAREHOUSE_SOL61, WAREHOUSE, 240000, 5
    )
    for suffix in ("protocol", "seeds"):
        raw = yaml.safe_load(
            (helpers.INPUTS / f"{WAREHOUSE_SOL61}-{suffix}.yaml").read_text()
        )
        assert raw["version"] == "0.4-r19-warehouse-reliable-probes-sol61-control"


def test_import_feedback_control_preserves_protocol_and_uses_fresh_seeds():
    helpers.test_fresh_seeds_and_unchanged_protocol(
        WAREHOUSE_IMPORT, WAREHOUSE_SOL61, 250000, 5
    )
    for suffix in ("protocol", "seeds"):
        raw = yaml.safe_load(
            (helpers.INPUTS / f"{WAREHOUSE_IMPORT}-{suffix}.yaml").read_text()
        )
        assert raw["version"] == "0.4-r19-warehouse-import-feedback-control"


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
        (
            WAREHOUSE_SOL61,
            "scion/problems/warehouse_delivery/problem-v1.yaml",
            WAREHOUSE,
            2,
            "surrogate",
        ),
        (
            WAREHOUSE_IMPORT,
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


def test_complete_input_preserved_and_new_sampling_explicit():
    old = json.loads(
        (helpers.INPUTS / f"{previous.CVRP}-research-input.json").read_text()
    )
    new = normalize_research_input(
        json.loads((helpers.INPUTS / f"{CVRP}-research-input.json").read_text())
    )
    assert new["observations"] == old["observations"]
    assert len(new["observations"]) == 5
    prefix = (
        old["current_question"]
        .replace("prospective R18", "prospective R19")
        .replace(
            "at two seeds each; expansion adds A-n54-k7 and uses four seeds for all six cases.",
            "at four seeds each; expansion adds A-n54-k7 and uses six seeds for all six cases.",
        )
    )
    assert new["current_question"].startswith(prefix)
    addition = new["current_question"][len(prefix) :]
    for fact in (
        "all twelve ordinary screening records",
        "eight cumulative candidates",
        "176 valid paired observations",
        "+3791,+1537,-2714,-2540",
        "genuine multi-step displacement returns no materialized candidate",
        "unchanged case populations, thresholds, per-solve limits",
        "not evidence of stability",
        "H/C retain algorithm and test choice",
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
        "/metrics/",
        ".py",
    ):
        assert private not in json.dumps(new)
