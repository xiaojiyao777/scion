"""Exact R22 C3 confirmation keeps adverse cases, gates and fixed fresh samples."""

from math import isqrt

import pytest
import yaml

import run_fixed_candidate_funnel as driver
from scion.config.problem import ProtocolConfig, SeedLedgerConfig, SplitManifest
from scion.tests.unit import test_r16_inputs as helpers
from scion.tests.unit.test_r21_inputs import invocation

PREFIX = "v04-cvrp-r23-r22-final-local-fixed"
PREVIOUS = "v04-cvrp-r22-retained-path-autonomous"


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


def test_only_version_and_canary_seed_change_from_r22():
    old = yaml.safe_load((helpers.INPUTS / f"{PREVIOUS}-protocol.yaml").read_text())
    new = yaml.safe_load((helpers.INPUTS / f"{PREFIX}-protocol.yaml").read_text())
    assert new["version"] == "0.4-cvrp-r23-r22-final-local-fixed"
    old["version"] = new["version"]
    old["canary"]["seeds"] = [290183]
    assert new == old


def test_seed_choice_is_fresh_disjoint_and_outcome_independent():
    config, _split, seeds, _retained_split, retained = inputs()
    values = [*seeds.screening, *seeds.validation, *seeds.frozen, *seeds.canary,
              *retained.frozen]
    assert values == [
        n for n in range(290001, 290600)
        if all(n % d for d in range(2, isqrt(n) + 1))
    ][:21]
    assert len(set(values)) == 21
    assert config.canary.seeds == seeds.canary
    own = {f"{PREFIX}-seeds.yaml", f"{PREFIX}-retained-seeds.yaml"}
    for path in helpers.INPUTS.glob("*-seeds.yaml"):
        if path.name not in own:
            other = SeedLedgerConfig.from_yaml(path)
            assert set(values).isdisjoint(
                [*other.screening, *other.validation, *other.frozen, *other.canary]
            )


def test_full_matrix_resources_and_adverse_cases_preserved():
    config, split, seeds, retained_split, retained = inputs()
    driver.validate_population_shape(config, split, seeds, retained_split, retained)
    assert split.screening == [
        "cvrplib/B/B-n34-k5.vrp", "cvrplib/tai/tai100a.vrp",
        "cvrplib/X/X-n351-k40.vrp", "cvrplib/A/A-n54-k7.vrp",
        "cvrplib/X/X-n190-k8.vrp", "cvrplib/X/X-n513-k21.vrp",
    ]
    assert [len(split.screening) * len(seeds.screening),
            len(split.validation) * len(seeds.validation),
            len(split.frozen) * len(seeds.frozen),
            len(retained_split.frozen) * len(retained.frozen)] == [48, 24, 48, 48]
    envelope = driver.build_resource_envelope(
        config, split, seeds, retained_split, retained,
        fallback_time_limit_sec=60, timeout_guard_sec=30,
        outer_hardwall_sec=86400, memory_mb=4096,
    )
    assert envelope.max_solver_subprocesses == 338
    assert envelope.nominal_subject_seconds == 40580
    assert envelope.guarded_subject_seconds == 50720
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


def test_frozen_invocation_uses_complete_local_sources_and_existing_driver():
    command, tokens = invocation(PREFIX, "20261018")
    script = str(helpers.ROOT / "scion/run_fixed_candidate_funnel.py")
    args = driver._parser().parse_args(tokens[tokens.index(script) + 1:])
    root = "/home/clawd/research/scion-experiments/"
    old = root + PREVIOUS + "-20261011/"
    assert str(args.baseline_source) == old + "champions/champion_v1"
    assert str(args.candidate_source) == old + "candidate_workspaces/candidate-_oqy_blc"
    assert args.changed_file == ["policies/baseline_modules/local_search.py"]
    assert args.selected_surface == "solver_design"
    assert args.label == PREFIX + "-20261018"
    assert str(args.output_dir) == root + args.label
    assert args.protocol == helpers.INPUTS / f"{PREFIX}-protocol.yaml"
    assert args.seeds == helpers.INPUTS / f"{PREFIX}-seeds.yaml"
    assert args.retained_seeds == helpers.INPUTS / f"{PREFIX}-retained-seeds.yaml"
    assert args.split.name == "v04-cvrp-r7-autonomous-source-continuation-split.yaml"
    assert args.retained_split.name == "v04-cvrp-r6-minus-2for1-b0-retained-split.yaml"
    assert (args.time_limit_sec, args.timeout_guard_sec, args.memory_mb,
            args.outer_hardwall_sec) == (60, 30, 4096, 86400)
    assert not args.check
    for forbidden in ("SCION_MODEL", "API_KEY", "--research-history", "--resume"):
        assert forbidden not in command
