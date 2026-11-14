"""Prospective common-repair comparison; scientific gates stay unchanged."""

from copy import deepcopy
from math import isqrt
from pathlib import Path

import yaml

import run_fixed_candidate_funnel as driver
from scion.config.problem import ProtocolConfig, SeedLedgerConfig, SplitManifest

_INPUTS = Path(__file__).resolve().parents[3] / "docs/experiments/v0.4/inputs"
_R13 = "v04-cvrp-r13-constructor-fixed-b0"


def _path(prefix, kind):
    return _INPUTS / f"{prefix}-{kind}.yaml"


def test_r13_common_repair_does_not_change_scientific_gates_or_limits():
    old = yaml.safe_load(_path("v04-cvrp-r10-wide-budget-b0", "protocol").read_text())
    new = yaml.safe_load(_path(_R13, "protocol").read_text())
    expected = deepcopy(old)
    expected["version"] = new["version"]
    expected["canary"]["seeds"] = [120103]
    assert new == expected


def test_r13_fresh_seeds_and_unchanged_conditional_population():
    main = SeedLedgerConfig.from_yaml(_path(_R13, "seeds"))
    retained = SeedLedgerConfig.from_yaml(_path(_R13, "retained-seeds"))
    ordered = [*main.screening, *main.validation, *main.frozen,
               *retained.frozen, *main.canary]
    assert ordered == [
        n for n in range(120001, 120300)
        if all(n % d for d in range(2, isqrt(n) + 1))
    ][:11]
    assert len(set(ordered)) == 11
    for prefix in (
        "v04-cvrp-r6-minus-2for1-b0",
        "v04-cvrp-r7-autonomous-source-continuation",
        "v04-cvrp-r8-r7-final-b0",
        "v04-cvrp-r9-post-b0-autonomous",
        "v04-cvrp-r10-wide-budget-b0",
        "v04-cvrp-r11-wide-budget-autonomous",
        "v04-cvrp-r12-post-r11-autonomous",
    ):
        for kind in ("seeds", "retained-seeds"):
            path = _path(prefix, kind)
            if path.exists():
                prior = SeedLedgerConfig.from_yaml(path)
                assert set(ordered).isdisjoint(
                    [*prior.screening, *prior.validation, *prior.frozen, *prior.canary]
                )
    config = ProtocolConfig.from_yaml(_path(_R13, "protocol"))
    split = SplitManifest.from_yaml(
        _path("v04-cvrp-r7-autonomous-source-continuation", "split")
    )
    retained_split = SplitManifest.from_yaml(
        _path("v04-cvrp-r6-minus-2for1-b0", "retained-split")
    )
    driver.validate_population_shape(config, split, main, retained_split, retained)
    envelope = driver.build_resource_envelope(
        config, split, main, retained_split, retained,
        fallback_time_limit_sec=60, timeout_guard_sec=30,
        outer_hardwall_sec=43200, memory_mb=4096,
    )
    assert envelope.max_solver_subprocesses == 170
    assert envelope.nominal_subject_seconds == 20300
    assert envelope.guarded_subject_seconds == 25400
    assert envelope.max_time_limit_sec == 240
    spec = driver._paired_spec(
        label=_R13, ordinal=0, cases=split.screening, seeds=main.screening
    )
    parity = [
        (spec.candidate_ordinal + spec.block_ordinal + case + seed) % 2
        for case in spec.case_ordinals.values()
        for seed in spec.seed_ordinals.values()
    ]
    assert parity.count(0) == parity.count(1) == 12
