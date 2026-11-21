"""Warehouse-owned public input validation, independent of candidate imports."""
from __future__ import annotations

from copy import deepcopy

from scion.problem.public_input import (
    PublicInputError, array, boolean, integer, number, object_fields, text,
)
from scion.problem.public_observation import JsonObject, PublicObservationSpec

# Input vocabulary mirrors frozen surrogate.models; regression tests check it.
_PACKING_TYPES = frozenset({
    "FULL_PLT", "TAILGATE", "WOOD_CASE", "整板", "FULL_CTN", "LOOSE_CTN",
})
_TEXT_FIELDS = frozenset({
    "order_id", "pickup_name", "pickup_province", "pickup_city", "lsp",
    "ship_method", "destination_country",
})
_INT_FIELDS = frozenset({"vehicle_category", "vehicle_subcategory", "hazard_quantity"})
_BOOL_FIELDS = frozenset({"urgent", "hazard_flag"})


class WarehousePublicObservationProvider:
    def source_config(self, available_files, *, initial):
        if "registry.yaml" in available_files:
            return {"operator_selection": "registry"}
        if initial:
            return {"operator_selection": "defaults"}
        raise PublicInputError("SOURCE_UNAVAILABLE")

    def describe(self) -> PublicObservationSpec:
        return PublicObservationSpec(
            schema_version=1,
            fixture_paths=("data/instance_development.json",),
            subject_workspace_paths=(
                "config.py", "greedy_init.py", "models.py", "oracle.py", "pool.py",
                "solver.py", "vns.py", "operators",
            ),
            subject_package_paths=(),
            # Absence does not authorize defaults; P1b/P2 checks source config.
            subject_optional_workspace_paths=("registry.yaml",),
            checker_package_paths=("models.py", "oracle.py"),
            neutral_support_paths=(),
            checker_neutral_support_paths=(),
            subject_dependencies=("yaml",),
            runner_module="scion.problems.warehouse_delivery.public_runner",
            checker_module="scion.problems.warehouse_delivery.public_checker",
            input_description=(
                "Phase-1 JSON: orders with complete public order/SPU fields, "
                "amount_limits mapping. No vehicle price/capacity overrides."
            ),
            args_description=(
                "Exactly {time_limit_sec: positive finite number, "
                "max_iterations: positive integer}."
            ),
        )

    def validate_input(self, value: JsonObject) -> JsonObject:
        data = object_fields(value, {"orders", "amount_limits"})
        seen: set[str] = set()
        for index, order in enumerate(array(data["orders"], "$.orders")):
            path = f"$.orders[{index}]"
            object_fields(
                order,
                set(_TEXT_FIELDS | _INT_FIELDS | _BOOL_FIELDS)
                | {"declaration_amount", "spu_list"},
                path, optional=frozenset({"locked_vehicle_id"}),
            )
            for field in sorted(_TEXT_FIELDS):
                text(order[field], path + "." + field)
            if order["order_id"] in seen:
                raise PublicInputError("DUPLICATE_ORDER", path + ".order_id")
            seen.add(order["order_id"])
            for field in sorted(_INT_FIELDS):
                integer(order[field], path + "." + field, minimum=0)
            for field in sorted(_BOOL_FIELDS):
                boolean(order[field], path + "." + field)
            number(order["declaration_amount"], path + ".declaration_amount", minimum=0)
            if order.get("locked_vehicle_id") is not None:
                text(order["locked_vehicle_id"], path + ".locked_vehicle_id")
            for spu_index, spu in enumerate(array(order["spu_list"], path + ".spu_list")):
                spu_path = f"{path}.spu_list[{spu_index}]"
                object_fields(spu, {"packing_type", "quantity"}, spu_path)
                packing = text(spu["packing_type"], spu_path + ".packing_type")
                if packing not in _PACKING_TYPES:
                    raise PublicInputError("PACKING_TYPE_INVALID", spu_path + ".packing_type")
                integer(spu["quantity"], spu_path + ".quantity", minimum=0)
        amounts = data["amount_limits"]
        if type(amounts) is not dict:
            raise PublicInputError("OBJECT_REQUIRED", "$.amount_limits")
        for key, value in amounts.items():
            # Do not echo user-provided keys into the diagnostic path.
            text(key, "$.amount_limits.<key>")
            number(value, "$.amount_limits.<value>", minimum=0)
        return deepcopy(data)

    def validate_args(self, value: JsonObject) -> JsonObject:
        data = object_fields(value, {"time_limit_sec", "max_iterations"})
        number(data["time_limit_sec"], "$.time_limit_sec", positive=True)
        integer(data["max_iterations"], "$.max_iterations", minimum=1)
        return deepcopy(data)

    def validate_source_config(self, value: JsonObject, available_files: tuple[str, ...]) -> JsonObject:
        data = object_fields(value, {"operator_selection"})
        mode = data["operator_selection"]
        if mode not in ("registry", "defaults"):
            raise PublicInputError("SOURCE_CONFIG_INVALID")
        present = "registry.yaml" in available_files
        if present != (mode == "registry"):
            raise PublicInputError("SOURCE_CONFIG_UNAVAILABLE")
        return deepcopy(data)
