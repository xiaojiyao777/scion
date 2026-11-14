"""Prospective fixed-candidate confirmation: more samples, unchanged gates."""

from math import isqrt

import pytest
import yaml

import run_fixed_candidate_funnel as driver
from scion.config.problem import ProtocolConfig, SeedLedgerConfig, SplitManifest
from scion.tests.unit import test_r16_inputs as helpers

PREFIX = "v04-cvrp-r20-r19-final-b0-fixed"


def inputs():
    return (
        ProtocolConfig.from_yaml(helpers.INPUTS / f"{PREFIX}-protocol.yaml"),
        SplitManifest.from_yaml(
            helpers.INPUTS / "v04-cvrp-r7-autonomous-source-continuation-split.yaml"
        ),
        SeedLedgerConfig.from_yaml(helpers.INPUTS / f"{PREFIX}-seeds.yaml"),
        SplitManifest.from_yaml(
            helpers.INPUTS / "v04-cvrp-r6-minus-2for1-b0-retained-split.yaml"
        ),
        SeedLedgerConfig.from_yaml(helpers.INPUTS / f"{PREFIX}-retained-seeds.yaml"),
    )


def test_only_sample_counts_version_and_canary_seed_change():
    old = yaml.safe_load(
        (helpers.INPUTS / "v04-cvrp-r19-reliable-probes-autonomous-protocol.yaml").read_text()
    )
    new = yaml.safe_load((helpers.INPUTS / f"{PREFIX}-protocol.yaml").read_text())
    assert new["version"] == "0.4-cvrp-r20-r19-final-b0-fixed"
    old["version"] = new["version"]
    old["canary"]["seeds"] = [260209]
    old["screening"]["expand_n_seeds"] = 8
    old["validation"]["n_seeds"] = 4
    old["frozen"]["n_seeds"] = 4
    assert new == old


def test_seed_choice_is_prospective_disjoint_and_not_favorable_selection():
    config, _split, seeds, _retained_split, retained = inputs()
    values = [*seeds.screening, *seeds.validation, *seeds.frozen, *seeds.canary, *retained.frozen]
    assert values == [
        n for n in range(260001, 260600)
        if all(n % d for d in range(2, isqrt(n) + 1))
    ][:21]
    assert len(set(values)) == 21
    assert config.canary.seeds == seeds.canary
    own = {f"{PREFIX}-seeds.yaml", f"{PREFIX}-retained-seeds.yaml"}
    for path in helpers.INPUTS.glob("*-seeds.yaml"):
        if path.name in own:
            continue
        other = SeedLedgerConfig.from_yaml(path)
        assert set(values).isdisjoint(
            [*other.screening, *other.validation, *other.frozen, *other.canary]
        )


def test_full_conditional_matrix_and_resource_envelope():
    config, split, seeds, retained_split, retained = inputs()
    driver.validate_population_shape(config, split, seeds, retained_split, retained)
    assert [len(split.screening) * len(seeds.screening),
            len(split.validation) * len(seeds.validation),
            len(split.frozen) * len(seeds.frozen),
            len(retained_split.frozen) * len(retained.frozen)] == [48, 24, 48, 48]
    envelope = driver.build_resource_envelope(
        config, split, seeds, retained_split, retained,
        fallback_time_limit_sec=60, timeout_guard_sec=30,
        outer_hardwall_sec=86400, memory_mb=4096,
    )
    assert envelope.max_solver_subprocesses == 338  # Includes paired canary.
    assert envelope.guarded_subject_seconds == (
        envelope.nominal_subject_seconds + 338 * 30
    )
    assert envelope.guarded_subject_seconds < envelope.outer_hardwall_sec
    assert envelope.max_time_limit_sec == 240


@pytest.mark.parametrize("stage", ["screening", "validation", "frozen", "retained"])
def test_each_case_has_balanced_ab_ba_ordinals(stage):
    _config, split, seeds, retained_split, retained = inputs()
    ordinal = ["screening", "validation", "frozen", "retained"].index(stage)
    cases = retained_split.frozen if stage == "retained" else getattr(split, stage)
    values = retained.frozen if stage == "retained" else getattr(seeds, stage)
    spec = driver._paired_spec(label=PREFIX, ordinal=ordinal, cases=cases, seeds=values)
    for case in cases:
        parity = [(spec.candidate_ordinal + spec.block_ordinal
                   + spec.case_ordinals[case] + spec.seed_ordinals[seed]) % 2
                  for seed in values]
        assert parity.count(0) == parity.count(1) == len(values) // 2


def test_public_development_closure_preserved():
    helpers.test_full_public_formal_closure(
        PREFIX, "scion/scion/problems/cvrp/problem-v1.yaml",
        "v04-cvrp-r7-autonomous-source-continuation", 12,
        "scion/scion/problems/cvrp",
    )
