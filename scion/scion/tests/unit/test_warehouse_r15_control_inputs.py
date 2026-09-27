"""Prospective independent control stays generic and strictly expands."""

from math import isqrt
from pathlib import Path

import pytest

from scion.cli.commands.init_run import _load_cli_problem_adapter
from scion.config.problem import SeedLedgerConfig, SplitManifest
from scion.config.protocol_config import ProtocolConfig
from scion.core.models import ExperimentStage
from scion.protocol.experiment.selection import (
    SplitManager,
    select_cases,
    validate_requested_screening_expansion,
)

_INPUTS = Path(__file__).resolve().parents[3] / "docs/experiments/v0.4/inputs"
_PREFIX = "v04-r15-warehouse-feedback-control"


def test_warehouse_control_population_and_expansion_are_prospective():
    config = ProtocolConfig.from_yaml(_INPUTS / f"{_PREFIX}-protocol.yaml")
    split = SplitManifest.from_yaml(_INPUTS / f"{_PREFIX}-split.yaml")
    validate_requested_screening_expansion(
        config=config, split_manifest=split, requested_rounds=2
    )
    split.validate_disjoint()
    for action in ("modify", "create_new"):
        initial, expanded = [
            select_cases(
                config=config,
                split_manager=SplitManager(split),
                stage=ExperimentStage.SCREENING,
                hypothesis_action=action,
                expand_round=round_index,
            )
            for round_index in (0, 1)
        ]
        assert initial == ["data/instance_development.json"]
        assert set(expanded) == set(initial) | {"data/instance_small_1.json"}
    assert config.screening.require_expanded_for_pass
    assert config.screening.n_seeds == 1
    assert config.screening.expand_n_seeds == 2


def test_warehouse_control_seeds_match_canary_and_prospective_rule():
    config = ProtocolConfig.from_yaml(_INPUTS / f"{_PREFIX}-protocol.yaml")
    ledger = SeedLedgerConfig.from_yaml(_INPUTS / f"{_PREFIX}-seeds.yaml")
    values = [*ledger.screening, *ledger.validation, *ledger.frozen, *ledger.canary]
    assert (
        values
        == [
            n
            for n in range(150001, 150100)
            if all(n % divisor for divisor in range(2, isqrt(n) + 1))
        ][:5]
    )
    assert config.canary.seeds == ledger.canary


def test_r2_preserves_startup_rejection_and_separates_public_test_support():
    from scion.verification.development import (
        declared_development_problem_package_paths,
        declared_development_suites,
        declared_development_workspace_paths,
        validate_development_closure_boundary,
    )

    root = Path(__file__).resolve().parents[4]
    spec = _load_cli_problem_adapter(
        root / "scion/problems/warehouse_delivery/problem-v1.yaml"
    ).spec
    arguments = dict(
        problem_spec=spec,
        suites=declared_development_suites(spec),
        workspace_paths=declared_development_workspace_paths(spec),
        problem_package_paths=declared_development_problem_package_paths(spec),
        champion_root=str(root / "surrogate"),
    )
    first = SplitManifest.from_yaml(_INPUTS / f"{_PREFIX}-split.yaml")
    with pytest.raises(ValueError, match="development closure overlaps"):
        validate_development_closure_boundary(split_manifest=first, **arguments)
    second = SplitManifest.from_yaml(_INPUTS / f"{_PREFIX}-r2-split.yaml")
    assert second.screening == [
        "data/instance_small_1.json",
        "data/instance_small_6.json",
    ]
    assert second.validation == first.validation
    assert second.frozen == first.frozen
    assert second.canary == first.canary
    validate_development_closure_boundary(split_manifest=second, **arguments)
    for suffix, cls in (("protocol", ProtocolConfig), ("seeds", SeedLedgerConfig)):
        old = cls.from_yaml(_INPUTS / f"{_PREFIX}-{suffix}.yaml").model_dump()
        new = cls.from_yaml(_INPUTS / f"{_PREFIX}-r2-{suffix}.yaml").model_dump()
        assert old | {"version": "ignored"} == new | {"version": "ignored"}
