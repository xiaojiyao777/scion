"""Fresh research-support experiments preserve gates and public/private closure."""

import json
from math import isqrt
from pathlib import Path

import pytest
import yaml

from scion.cli.commands.init_run import _load_cli_problem_adapter
from scion.config.problem import SeedLedgerConfig, SplitManifest
from scion.config.protocol_config import ProtocolConfig
from scion.core.research_input import normalize_research_input
from scion.protocol.experiment.selection import validate_requested_screening_expansion
from scion.verification.development import (
    declared_development_problem_package_paths,
    declared_development_suites,
    declared_development_workspace_paths,
    validate_development_closure_boundary,
)

ROOT = Path(__file__).resolve().parents[4]
INPUTS = ROOT / "scion/docs/experiments/v0.4/inputs"
CVRP = "v04-cvrp-r16-probe-diagnostics-autonomous"
WAREHOUSE = "v04-r16-warehouse-probe-control"


@pytest.mark.parametrize(
    "prefix,previous,seed_start,count",
    [
        (CVRP, "v04-cvrp-r15-feedback-repair-autonomous", 160000, 9),
        (WAREHOUSE, "v04-r15-warehouse-feedback-control-r2", 170000, 5),
    ],
)
def test_fresh_seeds_and_unchanged_protocol(prefix, previous, seed_start, count):
    read = lambda name, suffix: yaml.safe_load(
        (INPUTS / f"{name}-{suffix}.yaml").read_text()
    )
    new, old = read(prefix, "protocol"), read(previous, "protocol")
    for value in (new, old):
        value.pop("version")
        value["canary"].pop("seeds")
    assert new == old
    ledger = SeedLedgerConfig.from_yaml(INPUTS / f"{prefix}-seeds.yaml")
    seeds = [*ledger.screening, *ledger.validation, *ledger.frozen, *ledger.canary]
    assert (
        seeds
        == [
            n
            for n in range(seed_start + 1, seed_start + 500)
            if all(n % d for d in range(2, isqrt(n) + 1))
        ][:count]
    )
    assert read(prefix, "protocol")["canary"]["seeds"] == ledger.canary
    for path in INPUTS.glob("*-seeds.yaml"):
        if path.name == f"{prefix}-seeds.yaml":
            continue
        prior = SeedLedgerConfig.from_yaml(path)
        assert set(seeds).isdisjoint(
            [*prior.screening, *prior.validation, *prior.frozen, *prior.canary]
        )


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
    spec = _load_cli_problem_adapter(ROOT / spec_path).spec
    split = SplitManifest.from_yaml(INPUTS / f"{split_prefix}-split.yaml")
    split.validate_disjoint()
    validate_requested_screening_expansion(
        config=ProtocolConfig.from_yaml(INPUTS / f"{prefix}-protocol.yaml"),
        split_manifest=split,
        requested_rounds=rounds,
    )
    validate_development_closure_boundary(
        problem_spec=spec,
        split_manifest=split,
        suites=declared_development_suites(spec),
        workspace_paths=declared_development_workspace_paths(spec),
        problem_package_paths=declared_development_problem_package_paths(spec),
        champion_root=str(ROOT / source),
    )


def test_r16_input_keeps_all_observations_and_no_private_outcomes():
    old = json.loads(
        (
            INPUTS / "v04-cvrp-r15-feedback-repair-autonomous-research-input.json"
        ).read_text()
    )
    new = normalize_research_input(
        json.loads((INPUTS / f"{CVRP}-research-input.json").read_text())
    )
    assert new["observations"] == old["observations"]
    assert len(new["observations"]) == 5
    question = new["current_question"]
    assert (
        old["current_question"].replace("prospective R15", "prospective R16")
        in question
    )
    assert "R15 SCREENING AND VERIFICATION ONLY" in question
    assert "all twelve ordinary safe records" in question
    assert "no target file" in question
    for private in (
        "B-n39-k5",
        "X-n106-k14",
        "tai385",
        "A-n62-k8",
        "X-n228-k23",
        "X-n627-k43",
        "-39.75",
        "-459.5",
        "VALIDATION_FAIL",
        "4e5b9aba",
        "/metrics/",
        ".py",
    ):
        assert private not in json.dumps(new)
