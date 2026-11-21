"""P1a data/compatibility checks; no candidate or observation runner executes."""
from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from scion.problem.public_input import PublicInputError, decode_public_json
from scion.problem.public_observation import (
    PublicObservationConfigurationError, resolve_public_observation_provider,
)
from scion.problems.cvrp.adapter import CvrpAdapter
from scion.problems.cvrp.public_observation import CvrpPublicObservationProvider
from scion.problems.warehouse_delivery.adapter import WarehouseDeliveryAdapter
from scion.problems.warehouse_delivery.public_observation import (
    WarehousePublicObservationProvider,
)

ROOT = Path(__file__).resolve().parents[3]


def decode(raw: bytes, **limits):
    return decode_public_json(raw, **{
        "max_bytes": 32_768, "max_depth": 16, "max_collection_items": 1024,
        **limits,
    })


@pytest.fixture
def cvrp_input():
    return json.loads((ROOT / "scion/scion/problems/cvrp/data/tiny_development.json").read_text())


@pytest.fixture
def warehouse_input():
    return json.loads((ROOT / "surrogate/data/instance_development.json").read_text())


def test_disabled_resolution_never_touches_adapter():
    class ExplosiveAdapter:
        def __getattribute__(self, name):
            raise AssertionError("disabled capability touched adapter")

    assert resolve_public_observation_provider(ExplosiveAdapter()) is None
    assert resolve_public_observation_provider(object()) is None
    with pytest.raises(PublicObservationConfigurationError) as error:
        resolve_public_observation_provider(object(), enabled=True)
    assert error.value.reason_code == "OBS_CAPABILITY_UNAVAILABLE"


@pytest.mark.parametrize("factory", [None, 1, lambda: object()])
def test_invalid_factory_is_typed_failure(factory):
    with pytest.raises(PublicObservationConfigurationError):
        resolve_public_observation_provider(
            SimpleNamespace(public_observation_provider=factory), enabled=True,
        )


def test_factory_exception_does_not_echo_private_diagnostic():
    def broken():
        raise RuntimeError("/private/input secret")

    with pytest.raises(PublicObservationConfigurationError) as error:
        resolve_public_observation_provider(
            SimpleNamespace(public_observation_provider=broken), enabled=True,
        )
    assert str(error.value) == "OBS_PROVIDER_INVALID"
    assert error.value.__suppress_context__


def test_provider_with_non_spec_description_is_rejected():
    provider = SimpleNamespace(
        describe=lambda: {"schema_version": 1},
        validate_input=lambda value: value,
        validate_args=lambda value: value,
        validate_source_config=lambda value, files: value,
    )
    with pytest.raises(PublicObservationConfigurationError) as error:
        resolve_public_observation_provider(
            SimpleNamespace(public_observation_provider=lambda: provider), enabled=True,
        )
    assert error.value.reason_code == "OBS_DESCRIPTOR_INVALID"


def test_factories_and_validators_require_no_solver_or_files(monkeypatch, cvrp_input, warehouse_input):
    import builtins

    def forbidden(*args, **kwargs):
        raise AssertionError("pure validation performed I/O or imported solver")

    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if "solver" in name or name.startswith("surrogate"):
            forbidden()
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(builtins, "__import__", guarded_import)
    for adapter, value in (
        (CvrpAdapter(None), cvrp_input),
        (WarehouseDeliveryAdapter(SimpleNamespace(root_dir="/not/read")), warehouse_input),
    ):
        provider = resolve_public_observation_provider(adapter, enabled=True)
        saved = deepcopy(value)
        result = provider.validate_input(value)
        assert result == saved and result is not value
        nested = "nodes" if "nodes" in result else "orders"
        result[nested][0].clear()
        assert value == saved


@pytest.mark.parametrize("path", ["/etc/passwd", "../data.json", "data/../x", "a//b", "a\\b", ".", "*.py", "x\x00y"])
def test_descriptor_rejects_noncanonical_paths(path):
    spec = CvrpPublicObservationProvider().describe()
    with pytest.raises(PublicObservationConfigurationError):
        replace(spec, fixture_paths=(path,))


def test_descriptor_type_is_not_execution_or_filesystem_validation():
    # P1a cannot certify existence, symlinks or formal-data aliases.
    spec = CvrpPublicObservationProvider().describe()
    assert replace(spec, fixture_paths=("not-yet-created.json",)).fixture_paths
    for change in ({"schema_version": True}, {"runner_module": "os:system"},
                   {"fixture_paths": ("x", "x")}, {"fixture_paths": ["x"]}):
        with pytest.raises(PublicObservationConfigurationError):
            replace(spec, **change)


@pytest.mark.parametrize(("raw", "code"), [
    (b'{"x":1,"x":2}', "JSON_DUPLICATE_KEY"),
    (b'{"nested":{"x":1,"x":2}}', "JSON_DUPLICATE_KEY"),
    (b'{"x":NaN}', "JSON_NONFINITE"),
    (b'{"x":1e999}', "JSON_NONFINITE"),
    (b'{"x":"\\ud800"}', "JSON_INVALID"),
    (b'{"x":"\xff"}', "JSON_INVALID"),
    (b'{} {}', "JSON_INVALID"),
    (b'[]', "OBJECT_REQUIRED"),
])
def test_strict_decoder(raw, code):
    with pytest.raises(PublicInputError) as error:
        decode(raw)
    assert error.value.reason_code == code


def test_decode_limits_before_parsing_and_literal_brackets(monkeypatch):
    with pytest.raises(PublicInputError, match="INPUT_ITEMS_LIMIT"):
        decode(b'{"x":[1,2]}', max_collection_items=2)
    assert decode(b'{"x":"[{{]"}', max_depth=1) == {"x": "[{{]"}
    assert decode(b'{"x": "a\\\"["}', max_depth=1) == {"x": 'a"['}

    def no_parse(*args, **kwargs):
        raise AssertionError("byte/depth limit reached the parser")

    monkeypatch.setattr(json, "loads", no_parse)
    with pytest.raises(PublicInputError, match="INPUT_SIZE_LIMIT"):
        decode(b" " * 10, max_bytes=9)
    with pytest.raises(PublicInputError, match="INPUT_DEPTH_LIMIT"):
        decode(b'{"x":[[1]]}', max_depth=2)


@pytest.mark.parametrize(("field", "value"), [
    ("capacity", True), ("capacity", "5"), ("capacity", 0),
    ("allowed_routes", False), ("allowed_routes", 0),
    ("depot", 12345), ("use_integer_cost", 1), ("bks", 12),
])
def test_cvrp_rejects_ambiguous_or_hidden_fields(cvrp_input, field, value):
    cvrp_input[field] = value
    with pytest.raises(PublicInputError):
        CvrpPublicObservationProvider().validate_input(cvrp_input)


@pytest.mark.parametrize(("field", "value"), [
    ("id", 0), ("id", True), ("x", float("inf")),
    ("x", 10**1000), ("demand", -1), ("demand", 6), ("demand", 1.0),
])
def test_cvrp_bad_customer(cvrp_input, field, value):
    cvrp_input["nodes"][1][field] = value
    with pytest.raises(PublicInputError):
        CvrpPublicObservationProvider().validate_input(cvrp_input)


def test_cvrp_nullable_fleet_and_depot_zero_demand(cvrp_input):
    cvrp_input["allowed_routes"] = None
    assert CvrpPublicObservationProvider().validate_input(cvrp_input) == cvrp_input
    cvrp_input["nodes"][0]["demand"] = 1
    with pytest.raises(PublicInputError, match="DEMAND_INVALID"):
        CvrpPublicObservationProvider().validate_input(cvrp_input)


@pytest.mark.parametrize(("field", "value"), [
    ("vehicle_category", True), ("vehicle_subcategory", "1"),
    ("urgent", 0), ("hazard_quantity", 1.5), ("declaration_amount", float("nan")),
    ("locked_vehicle_id", ""), ("new_field", "secret"),
])
def test_warehouse_rejects_ambiguous_order(warehouse_input, field, value):
    warehouse_input["orders"][0][field] = value
    with pytest.raises(PublicInputError):
        WarehousePublicObservationProvider().validate_input(warehouse_input)


def test_warehouse_duplicate_and_no_price_override(warehouse_input):
    provider = WarehousePublicObservationProvider()
    warehouse_input["orders"].append(deepcopy(warehouse_input["orders"][0]))
    with pytest.raises(PublicInputError, match="DUPLICATE_ORDER"):
        provider.validate_input(warehouse_input)
    warehouse_input["orders"].pop()
    warehouse_input["vehicle_types"] = {"T3": {"cost": 1}}
    with pytest.raises(PublicInputError, match="FIELDS_INVALID"):
        provider.validate_input(warehouse_input)


def test_warehouse_packing_vocabulary_matches_frozen_model(warehouse_input):
    from surrogate.models import BOX_TYPE, PALLET_TYPE
    provider = WarehousePublicObservationProvider()
    for packing in PALLET_TYPE | BOX_TYPE:
        warehouse_input["orders"][0]["spu_list"][0]["packing_type"] = packing
        assert provider.validate_input(warehouse_input) == warehouse_input
    warehouse_input["orders"][0]["spu_list"][0]["packing_type"] = "unknown"
    with pytest.raises(PublicInputError, match="PACKING_TYPE_INVALID"):
        provider.validate_input(warehouse_input)


def test_warehouse_errors_do_not_echo_mapping_keys(warehouse_input):
    warehouse_input["amount_limits"] = {"private marker": -1}
    with pytest.raises(PublicInputError) as error:
        WarehousePublicObservationProvider().validate_input(warehouse_input)
    assert error.value.public_field_path == "$.amount_limits.<value>"
    assert "private marker" not in str(error.value)


@pytest.mark.parametrize("provider,args", [
    (CvrpPublicObservationProvider(), {"time_limit_sec": 1.0}),
    (WarehousePublicObservationProvider(), {"time_limit_sec": 1.0, "max_iterations": 3}),
])
def test_args_are_only_declared_budget_controls(provider, args):
    assert provider.validate_args(args) == args
    for extra in ("seed", "solver_path", "operator_weights", "phase"):
        with pytest.raises(PublicInputError):
            provider.validate_args({**args, extra: 1})
    for value in (True, 0, -1, float("nan"), float("inf"), "1"):
        with pytest.raises(PublicInputError):
            provider.validate_args({**args, "time_limit_sec": value})
    if "max_iterations" in args:
        with pytest.raises(PublicInputError):
            provider.validate_args({**args, "max_iterations": True})
