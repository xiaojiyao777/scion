"""The fixed R7 candidate's next comparison changes seeds, not science gates."""

from math import isqrt
from pathlib import Path

import yaml

import run_fixed_candidate_funnel as driver
from scion.config.problem import ProtocolConfig, SeedLedgerConfig, SplitManifest

_INPUTS = Path(__file__).resolve().parents[3] / "docs/experiments/v0.4/inputs"
_R6 = "v04-cvrp-r6-minus-2for1-b0"
_R7 = "v04-cvrp-r7-autonomous-source-continuation"
_R8 = "v04-cvrp-r8-r7-final-b0"


def _path(prefix, kind):
    return _INPUTS / f"{prefix}-{kind}.yaml"


def test_r8_preserves_gates_and_uses_prospective_disjoint_seeds():
    old = yaml.safe_load(_path(_R7, "protocol").read_text())
    new = yaml.safe_load(_path(_R8, "protocol").read_text())
    assert old.keys() == new.keys()
    for key in old.keys() - {"version", "canary"}:
        assert old[key] == new[key]
    assert new["canary"]["cases"] == old["canary"]["cases"]
    main = SeedLedgerConfig.from_yaml(_path(_R8, "seeds"))
    retained = SeedLedgerConfig.from_yaml(_path(_R8, "retained-seeds"))
    ordered = [
        *main.screening,
        *main.validation,
        *main.frozen,
        *retained.frozen,
        *main.canary,
    ]
    first_primes = [
        n for n in range(60001, 60201) if all(n % d for d in range(2, isqrt(n) + 1))
    ][:11]
    assert ordered == first_primes
    assert len(ordered) == len(set(ordered)) == 11
    assert new["canary"]["seeds"] == main.canary
    for prefix, kind in ((_R6, "seeds"), (_R6, "retained-seeds"), (_R7, "seeds")):
        prior = SeedLedgerConfig.from_yaml(_path(prefix, kind))
        assert set(ordered).isdisjoint(
            [*prior.screening, *prior.validation, *prior.frozen, *prior.canary]
        )


def test_r8_unchanged_population_and_complete_conditional_resource_matrix():
    config = ProtocolConfig.from_yaml(_path(_R8, "protocol"))
    split = SplitManifest.from_yaml(_path(_R7, "split"))
    seeds = SeedLedgerConfig.from_yaml(_path(_R8, "seeds"))
    retained_split = SplitManifest.from_yaml(_path(_R6, "retained-split"))
    retained_seeds = SeedLedgerConfig.from_yaml(_path(_R8, "retained-seeds"))
    driver.validate_population_shape(
        config, split, seeds, retained_split, retained_seeds
    )
    envelope = driver.build_resource_envelope(
        config,
        split,
        seeds,
        retained_split,
        retained_seeds,
        fallback_time_limit_sec=30,
        timeout_guard_sec=30,
        outer_hardwall_sec=21600,
        memory_mb=4096,
    )
    assert envelope.max_solver_subprocesses == 170
    assert envelope.nominal_subject_seconds == 10160
    assert envelope.guarded_subject_seconds == 15260
    spec = driver._paired_spec(
        label=_R8, ordinal=0, cases=split.screening, seeds=seeds.screening
    )
    parities = [
        (spec.candidate_ordinal + spec.block_ordinal + case + seed) % 2
        for case in spec.case_ordinals.values()
        for seed in spec.seed_ordinals.values()
    ]
    assert parities.count(0) == parities.count(1) == 12
