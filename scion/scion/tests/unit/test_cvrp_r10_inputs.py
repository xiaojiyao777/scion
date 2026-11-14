"""Prospective equal-budget B0 comparison: more solve time, unchanged gates."""

from copy import deepcopy
from math import isqrt
from pathlib import Path

import yaml

import run_fixed_candidate_funnel as driver
from scion.config.problem import ProtocolConfig, SeedLedgerConfig, SplitManifest

_INPUTS = Path(__file__).resolve().parents[3] / "docs/experiments/v0.4/inputs"
_R6 = "v04-cvrp-r6-minus-2for1-b0"
_R7 = "v04-cvrp-r7-autonomous-source-continuation"
_R8 = "v04-cvrp-r8-r7-final-b0"
_R9 = "v04-cvrp-r9-post-b0-autonomous"
_R10 = "v04-cvrp-r10-wide-budget-b0"


def _path(prefix, kind):
    return _INPUTS / f"{prefix}-{kind}.yaml"


def test_r10_doubles_only_formal_solver_limits_and_preserves_science():
    old = yaml.safe_load(_path(_R9, "protocol").read_text())
    new = yaml.safe_load(_path(_R10, "protocol").read_text())
    expected = deepcopy(old)
    expected["version"] = new["version"]
    expected["canary"]["seeds"] = [90071]
    limits = expected["runtime"]["time_limits"]
    for stage in ("screening", "validation", "frozen"):
        limits["stage_defaults"][stage] *= 2
    for rule in limits["rules"]:
        rule["time_limit_sec"] *= 2
    assert new == expected
    assert limits["stage_defaults"]["canary"] == 10


def test_r10_uses_first_eleven_primes_above_90000_without_prior_seed_overlap():
    main = SeedLedgerConfig.from_yaml(_path(_R10, "seeds"))
    retained = SeedLedgerConfig.from_yaml(_path(_R10, "retained-seeds"))
    ordered = [
        *main.screening,
        *main.validation,
        *main.frozen,
        *retained.frozen,
        *main.canary,
    ]
    primes = [
        n for n in range(90001, 90201) if all(n % d for d in range(2, isqrt(n) + 1))
    ][:11]
    assert ordered == primes
    assert len(set(ordered)) == 11
    config = yaml.safe_load(_path(_R10, "protocol").read_text())
    assert config["canary"]["seeds"] == main.canary
    for prefix, kind in (
        (_R6, "seeds"),
        (_R6, "retained-seeds"),
        (_R7, "seeds"),
        (_R8, "seeds"),
        (_R8, "retained-seeds"),
        (_R9, "seeds"),
    ):
        prior = SeedLedgerConfig.from_yaml(_path(prefix, kind))
        assert set(ordered).isdisjoint(
            [*prior.screening, *prior.validation, *prior.frozen, *prior.canary]
        )


def test_r10_complete_resource_matrix_and_counterbalancing():
    config = ProtocolConfig.from_yaml(_path(_R10, "protocol"))
    split = SplitManifest.from_yaml(_path(_R7, "split"))
    seeds = SeedLedgerConfig.from_yaml(_path(_R10, "seeds"))
    retained_split = SplitManifest.from_yaml(_path(_R6, "retained-split"))
    retained_seeds = SeedLedgerConfig.from_yaml(_path(_R10, "retained-seeds"))
    driver.validate_population_shape(
        config, split, seeds, retained_split, retained_seeds
    )
    envelope = driver.build_resource_envelope(
        config,
        split,
        seeds,
        retained_split,
        retained_seeds,
        fallback_time_limit_sec=60,
        timeout_guard_sec=30,
        outer_hardwall_sec=43200,
        memory_mb=4096,
    )
    assert envelope.max_solver_subprocesses == 170
    assert envelope.nominal_subject_seconds == 20300
    assert envelope.guarded_subject_seconds == 25400
    assert envelope.max_time_limit_sec == 240
    old = ProtocolConfig.from_yaml(_path(_R9, "protocol"))
    for stage, cases in (
        ("screening", split.screening),
        ("validation", split.validation),
        ("frozen", split.frozen + retained_split.frozen),
    ):
        for case in cases:
            assert driver._time_limit(
                config, stage=stage, case_path=case, fallback=60
            ) == 2 * driver._time_limit(old, stage=stage, case_path=case, fallback=30)
    spec = driver._paired_spec(
        label=_R10, ordinal=0, cases=split.screening, seeds=seeds.screening
    )
    parities = [
        (spec.candidate_ordinal + spec.block_ordinal + case + seed) % 2
        for case in spec.case_ordinals.values()
        for seed in spec.seed_ordinals.values()
    ]
    assert parities.count(0) == parities.count(1) == 12
