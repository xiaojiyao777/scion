"""WarehouseDeliveryAdapter — ProblemAdapter for the warehouse delivery problem.

Wraps surrogate/oracle.py and surrogate/models.py. All warehouse-specific logic
(Vehicle/Solution/Instance reconstruction, feasibility checks, objective
recomputation) is encapsulated here so Scion core never imports surrogate directly.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import os
import sys
from collections import defaultdict
from typing import Any, Mapping, Sequence

from scion.problem.contracts import CheckReport, LowerBoundEstimate, SolverArtifact
from scion.problem.spec import ProblemSpecV1


class WarehouseDeliveryAdapter:
    def __init__(self, spec: ProblemSpecV1) -> None:
        self._spec = spec
        self._root = spec.root_dir
        self._oracle_mod: Any = None
        self._models_mod: Any = None

    @property
    def spec(self) -> ProblemSpecV1:
        return self._spec

    def active_subject_policy_provider(self) -> "WarehouseDeliveryAdapter":
        return self

    def active_subject_taxonomy(
        self,
        context: Any = None,
        *,
        surface: str | None = None,
        subject_id: str | None = None,
    ) -> Mapping[str, Any]:
        del context, surface, subject_id
        return {
            "telemetry_activation_refs": (
                "operator_diagnostics",
                "validation_transfer_diagnostics",
                "validation_transfer",
                "operator_invocations",
                "eligible_vehicle_or_order_groups_seen",
                "accepted_moves",
            )
        }

    def active_subject_code_constraints(
        self,
        context: Any = None,
        *,
        surface: str | None = None,
        subject_id: str | None = None,
    ) -> Mapping[str, Any] | None:
        del context, subject_id
        selected = str(surface or "").strip()
        if selected not in {"", "order_level", "vehicle_level"}:
            return None
        return {
            "surface": selected or "warehouse_operator",
            "subject_id": "warehouse_delivery.operator.validation_transfer",
            "version": "warehouse_operator_validation_transfer_code_constraints.v1",
            "constraints": (
                {
                    "id": "exportable_validation_transfer_diagnostics",
                    "summary": (
                        "Warehouse operator diagnostics must be stored on the "
                        "operator instance for solver/runtime export."
                    ),
                    "constraint": (
                        "Initialize or update `self.validation_transfer_diagnostics` "
                        "with the exact standard keys `operator_invocations`, "
                        "`eligible_vehicle_or_order_groups_seen`, `accepted_moves`, "
                        "`split_delta_sum`, `cost_delta_sum`, and "
                        "`improving_move_count`; a helper such as "
                        "`self._new_diagnostics()` or `new_diagnostics()` may "
                        "return that standard dict literal, but its result must "
                        "be assigned to `self.validation_transfer_diagnostics`, "
                        "not only a local dict or undeclared expected_telemetry "
                        "names."
                    ),
                },
                {
                    "id": "activation_and_effect_mutations",
                    "summary": (
                        "Code must mutate both activation and effect counters before "
                        "the patch reaches protocol."
                    ),
                    "constraint": (
                        "Increment activation counters such as `operator_invocations` "
                        "and `eligible_vehicle_or_order_groups_seen`, then mutate "
                        "`self.validation_transfer_diagnostics` or an alias of "
                        "that operator-instance field for effect counters such as "
                        "`split_delta_sum`, `cost_delta_sum`, or "
                        "`improving_move_count` from computed candidate/base deltas."
                    ),
                },
                {
                    "id": "screening_only_lexicographic_guard",
                    "summary": (
                        "Accepted moves must be guarded against screening-only or "
                        "lexicographically dominated changes."
                    ),
                    "constraint": (
                        "Compute split and cost deltas, or candidate/base split and "
                        "cost values, and return the original solution when the "
                        "candidate worsens subcategory splits or only offers a "
                        "lower-priority cost gain after harming splits. Comments or "
                        "string mentions of a lexicographic guard are not sufficient."
                    ),
                },
            ),
            "forbidden_patterns": (
                "local-only validation_transfer_diagnostics dict",
                "comments or strings as the only screening/lexicographic guard",
                "accepting cost-only moves that worsen subcategory_splits",
            ),
        }

    # --- lazy import of surrogate modules ---

    def _ensure_modules(self) -> None:
        if self._oracle_mod is not None:
            return
        oracle_dir = os.path.dirname(
            os.path.abspath(os.path.join(self._root, self._spec.oracle_path))
        )
        self._oracle_mod = _import_module(oracle_dir, "oracle.py", "_wd_oracle")
        self._models_mod = _import_module(oracle_dir, "models.py", "_wd_models")

    # --- Prompt / context ---

    def render_problem_summary(self) -> str:
        cats = ", ".join(
            c.name for c in self._spec.operator_interface.categories
        ) if self._spec.operator_interface else "vehicle_level, order_level"
        editable = ", ".join(self._spec.search_space.editable)
        frozen = ", ".join(self._spec.search_space.frozen)
        objective_policy = _render_objective_policy(self._spec)
        objective_implication = _render_objective_implication(self._spec)

        return f"""\
Name: {self._spec.display_name}
Description: {self._spec.description or 'Warehouse Delivery Assignment'}

### Objective Function
{objective_policy}

Metric definitions:
- subcategory_splits: For each unique `vehicle_subcategory` value across all orders,
  count how many distinct vehicles contain orders of that subcategory, subtract 1,
  then sum. Formula: sum(len(vehicles_containing_subcat) - 1 for each subcategory)
- total_cost: sum(VEHICLE_TYPES[v.vehicle_type].cost for all non-empty vehicles)
  Vehicle costs: T3=800, T5=1200, T10=1800, HQ40=3300, HQ40_DG=6600

{objective_implication}

### Validation Transfer Risk and Operator Diagnostics
{_render_validation_transfer_guidance()}

### How the Initial Solution is Built (greedy_init)
Orders are grouped by (vehicle_category, vehicle_subcategory, pickup_city).
Within each group, orders are packed sequentially into vehicles using first-fit.
When a vehicle reaches capacity (pallet limit), a new vehicle is opened for the same group.
Subcategory splits occur when a subcategory group's total pallets exceed one vehicle's capacity.
Example: if subcategory 3 has 50 pallets and HQ40 capacity is 40, it needs 2 vehicles -> 1 split.

To reduce splits, an operator typically consolidates orders so a subcategory fits in
fewer vehicles: merging partially-filled vehicles of the SAME vehicle_subcategory,
or moving orders between vehicles to free up space for same-subcategory consolidation.
To reduce cost while preserving splits, an operator typically downsizes, merges
under-filled compatible vehicles, or removes vehicles without spreading a subcategory
across more vehicles. Random order moves between arbitrary vehicles are unlikely to
improve either metric reliably.

### Worked Example (Small Instance)
Instance: 6 orders, 2 subcategories, all Shenzhen region
  Orders: A1(subcat=1,8plt), A2(subcat=1,6plt), A3(subcat=1,10plt),
          A4(subcat=1,12plt), B1(subcat=2,5plt), B2(subcat=2,4plt)
  Vehicle types: T10(cap=14,cost=1800), HQ40(cap=40,cost=3300)

Greedy init (groups by subcategory, first-fit):
  V1[T10]: A1(8)+A2(6)=14plt -> full
  V2[T10]: A3(10) -> 10plt (A4 won't fit: 10+12=22 > 14)
  V3[T10]: A4(12) -> 12plt
  V4[T10]: B1(5)+B2(4)=9plt
  Objective: splits=2 (subcat 1 in V1,V2,V3 -> split=2; subcat 2 in V4 -> split=0)
             cost=4*1800=7200

Improved (merge subcat-1 vehicles into HQ40):
  V1[HQ40]: A1+A2+A3+A4=36plt
  V4[T10]: B1+B2=9plt
  Objective: splits=0, cost=3300+1800=5100 -> BETTER on both objectives

The key move: merging V2+V3 orders into V1 (upgrading to HQ40).
This is what a good subcategory-consolidation operator should do.

Operator categories: {cats}
Editable files: {editable}
Frozen files (do not modify): {frozen}"""

    def render_operator_interface(self) -> str:
        base_py_path = os.path.join(self._root, "operators", "base.py")
        try:
            with open(base_py_path, encoding="utf-8") as fh:
                base_class_src = fh.read()
        except OSError:
            base_class_src = (
                "class Operator(ABC):\n"
                "    @abstractmethod\n"
                "    def execute(self, solution: Solution, rng: Random) -> Solution:\n"
                "        ..."
            )

        return f"""\
### Operator Base Class (from operators/base.py)
```python
{base_class_src}
```

### Key Data Structures (from models.py)
- `Solution`: contains `vehicles: dict[str, Vehicle]` and `assignment: dict[str, str]` (order_id → vehicle_id)
  - Call `solution.deep_copy()` to get a deep copy before modifying
  - `solution.remove_empty_vehicles()` to clean up empty vehicles in-place
- `Vehicle`: `vehicle_id`, `vehicle_type` (HQ40_DG|HQ40|T10|T5|T3), `region`, `order_ids: list[str]`
- `Order` (complete field list — use these EXACT attribute names):
  - `order_id: str` — unique identifier
  - `vehicle_category: int` — large category (feasibility H4: same vehicle must have same category)
  - `vehicle_subcategory: int` — sub-category used by the priority-1 split metric
  - `urgent: bool` — urgency flag
  - `hazard_flag: bool` — True if order contains hazardous goods
  - `hazard_quantity: int` — hazardous goods quantity in pcs (>1800 requires HQ40_DG)
  - `pickup_name: str` — pickup point name (constraint H3: max pickups per vehicle per region)
  - `pickup_city: str` — "Dongguan" or "Shenzhen" (constraint H2: same region per vehicle)
  - `declaration_amount: float` — customs declaration amount (constraint H6)
  - `lsp: str` — logistics service provider
  - `ship_method: str` — shipping method (H6 grouping key with destination_country)
  - `destination_country: str` — destination country (H6 grouping key with ship_method)
  - `spu_list: list[SPU]` — packing units; use `calc_pallets(order.spu_list)` from models.py
  - `locked_vehicle_id: Optional[str]` — None = freely assignable; non-None = MUST stay in that vehicle
- `Instance`: accessed via `self.instance` (set in __init__); contains `orders: dict[str, Order]`, `amount_limits: dict[str, float]`
- Helper: `select_minimum_vehicle_type(total_pallets, total_hazard) -> str` from models.py
- Helper: `get_max_pickups(region) -> int` from models.py (Dongguan=2, Shenzhen=3)

### Validation Transfer Risk and Operator Diagnostics
{_render_validation_transfer_guidance()}

### Critical Constraints
1. **Deep copy first**: always call `new_sol = solution.deep_copy()` before any modification
2. **Locked orders**: never move orders where `order.locked_vehicle_id is not None`
3. **rng**: use `rng` (a `random.Random` instance) for all randomness — do NOT import `random` directly
4. **Determinism**: NEVER use `uuid.uuid4()` or any system entropy source. Generate vehicle IDs with `generate_vehicle_id(rng)` from `operators.base`. NEVER use `list(set(...))` or iterate over `set`/`dict` in an order-dependent way. Use `sorted()` when you need a stable order from sets or dict keys/values. The solver runs twice with the same seed to verify determinism — any non-deterministic output causes rejection.
5. **Return value**: return the modified solution (or the original if no valid move was found)
6. **Imports**: only use modules from the import whitelist; no external packages

### Feasibility Constraints (MUST NOT violate — will cause immediate rejection)
7. **Every order assigned**: every order in the instance MUST appear in exactly one vehicle's order_ids AND in the assignment dict. Never drop or duplicate orders.
8. **Consistency**: `solution.assignment[order_id] == vehicle_id` must match `order_id in vehicle.order_ids` for ALL orders. After any modification, update BOTH.
9. **Vehicle capacity**: total pallets in a vehicle must not exceed its type's capacity
10. **Hazardous goods**: orders with `hazard_flag=True` and total hazard_quantity > 1800 MUST be in HQ40_DG
11. **No empty vehicles**: after modifications, call `new_sol.remove_empty_vehicles()` to clean up
12. **Same region**: all orders in a vehicle must have the same `pickup_city` region
13. **Same category**: all orders in a vehicle must have the same `vehicle_category`
14. **Pickup limit**: number of distinct `pickup_name` values in a vehicle must not exceed `get_max_pickups(region)`"""

    def render_research_surface_interface(self, surface_name: str) -> str:
        """Render the operator interface plus surface-local prompt guidance."""

        interface = self.render_operator_interface()
        guidance = _render_surface_prompt_guidance(self._spec, surface_name)
        if not guidance:
            return interface
        return f"{interface}\n\n{guidance}"

    def preview_research_surface_patch(
        self,
        *,
        patch: Any,
        surface: Any | None = None,
        base_workspace: str | None = None,
        branch_workspace: str | None = None,
    ) -> Mapping[str, Any]:
        """Problem-owned cheap preview for warehouse operator patches.

        This deliberately stays short of running verification.  It catches
        warehouse-specific structural risks before the candidate reaches heavy
        solution-consistency checks.
        """

        del base_workspace, branch_workspace
        surface_name = str(getattr(surface, "name", "") or "").strip()
        issues: list[str] = []
        checks: list[dict[str, Any]] = []
        for change in _patch_changes(patch):
            file_path = _normalize_patch_path(getattr(change, "file_path", ""))
            action = str(getattr(change, "action", "") or "").strip()
            code = str(getattr(change, "code_content", "") or "")
            if _is_existing_operator_module(file_path) and action in {
                "delete",
                "remove",
            }:
                detail = (
                    f"{file_path} is statically imported by the warehouse "
                    "operator package, solver, and registry. Use a guarded "
                    "modify/no-op or an explicit registry/weight mechanism; "
                    "do not delete an existing operator module."
                )
                issues.append(
                    f"warehouse_operator_module_delete: {detail}"
                )
                checks.append(
                    {
                        "name": "warehouse_operator_module_delete",
                        "passed": False,
                        "detail": detail,
                    }
                )
                continue
            if file_path.startswith("operators/") and file_path.endswith(".py"):
                _preview_operator_code_static_state(
                    code,
                    issues=issues,
                    checks=checks,
                )
        if not checks:
            checks.append(
                {
                    "name": "warehouse_operator_surface_preview",
                    "passed": True,
                    "detail": "no warehouse-specific preview issues detected",
                }
            )
        return {
            "passed": not issues,
            "surface": surface_name,
            "checks": checks,
            "issues": issues,
            "workspace_materialized": False,
            "verification_run": False,
        }

    def render_problem_measurement_diagnostics(self) -> Mapping[str, Any]:
        """Return warehouse proposal-only transfer diagnostics.

        This is problem-owned planning context.  It intentionally exposes the
        aggregate failure shape but not validation/frozen case details.
        """

        return {
            "schema_version": "warehouse_validation_transfer_diagnostic.v1",
            "taint": "problem_owned_proposal_diagnostic",
            "decision_features_excluded": True,
            "transfer_risk": {
                "risk_model": (
                    "screening-positive operator changes may activate on the "
                    "small screening distribution while producing no "
                    "hierarchical gain on formal validation aggregates"
                ),
                "historical_pattern": (
                    "same_subcategory_consolidate-style operator: screening "
                    "positive, formal aggregate 2/3/0, paired 6/9/0, median "
                    "delta 0, failure VALIDATION_FAIL_NO_HIERARCHICAL_GAIN"
                ),
                "required_hypothesis_claims": [
                    "why the mechanism should transfer beyond screening cases",
                    "what operator activation counter should become positive",
                    "what effect counter should prove subcategory split or cost gain",
                    "how the operator avoids screening-only activation",
                ],
            },
            "required_diagnostics": {
                "activation": [
                    "operator_invocations",
                    "eligible_vehicle_or_order_groups_seen",
                    "accepted_moves",
                ],
                "effect": [
                    "split_delta_sum",
                    "cost_delta_sum",
                    "improving_move_count",
                ],
            },
            "policy": (
                "Use these diagnostics to shape warehouse proposals before "
                "code generation. They are not promotion evidence and are not "
                "DecisionFeatures."
            ),
        }

    def validate_hypothesis_quality(
        self,
        *,
        branch: Any | None,
        hypothesis: Any,
        step_history: Sequence[Any] | None = None,
    ) -> Mapping[str, Any]:
        """Problem-owned proposal-only quality check for warehouse operators."""

        del step_history
        if not _is_high_risk_warehouse_hypothesis(branch, hypothesis):
            return {"allowed": True}
        missing = _missing_transfer_quality_claims(hypothesis)
        if not missing:
            return {
                "allowed": True,
                "gate_name": "warehouse_validation_transfer_quality",
            }
        detail = (
            f"{WAREHOUSE_VALIDATION_TRANSFER_QUALITY_FAILURE}: warehouse "
            "operator proposal must explain validation-case transfer risk, "
            "expected activation/effect diagnostics, and how it avoids "
            "screening-only gains before code generation; missing="
            + ",".join(missing)
        )
        return {
            "allowed": False,
            "detail": detail,
            "gate_name": "warehouse_validation_transfer_quality",
            "structured_rejection": {
                "source": "warehouse_problem_adapter",
                "gate_name": "warehouse_validation_transfer_quality",
                "failure_code": WAREHOUSE_VALIDATION_TRANSFER_QUALITY_FAILURE,
                "agent_block_reason": "agent_quality_blocked",
                "retry_constraint": (
                    "Rewrite the warehouse operator hypothesis before code: "
                    "state the screening-to-validation transfer risk, declare "
                    "expected activation/effect diagnostics, and explain the "
                    "guard against screening-only improvements."
                ),
                "repair_template": _warehouse_hypothesis_quality_repair_template(
                    missing
                ),
                "missing_claims": list(missing),
                "decision_features_excluded": True,
            },
        }

    def validate_patch_quality(
        self,
        *,
        branch: Any | None,
        hypothesis: Any,
        patch: Any,
        step_history: Sequence[Any] | None = None,
    ) -> Mapping[str, Any]:
        """Problem-owned code quality check for warehouse operator patches."""

        del step_history
        if not _is_high_risk_warehouse_hypothesis(branch, hypothesis):
            return {"allowed": True}
        code, changed_files = _warehouse_operator_patch_code(patch, hypothesis)
        missing = list(_missing_transfer_patch_quality(code))
        if not changed_files:
            missing.insert(0, "warehouse_operator_patch_code")
        if not missing:
            return {
                "allowed": True,
                "gate_name": "warehouse_validation_transfer_patch_quality",
            }
        detail = (
            f"{WAREHOUSE_VALIDATION_TRANSFER_PATCH_QUALITY_FAILURE}: warehouse "
            "operator patch must implement proposal/code-visible validation "
            "transfer diagnostics before protocol: activation/effect counters "
            "or an explicit instrumentation path, plus a screening-only or "
            "lexicographic guard; missing="
            + ",".join(dict.fromkeys(missing))
        )
        return {
            "allowed": False,
            "detail": detail,
            "gate_name": "warehouse_validation_transfer_patch_quality",
            "structured_rejection": {
                "source": "warehouse_problem_adapter",
                "gate_name": "warehouse_validation_transfer_patch_quality",
                "failure_code": WAREHOUSE_VALIDATION_TRANSFER_PATCH_QUALITY_FAILURE,
                "agent_block_reason": "agent_quality_blocked",
                "retry_constraint": (
                    "Revise the warehouse operator patch before protocol: "
                    "add code-visible activation/effect diagnostic counters or "
                    "a named instrumentation path, and include a guard that "
                    "prevents screening-only or lexicographically dominated "
                    "moves."
                ),
                "repair_template": _warehouse_patch_quality_repair_template(missing),
                "missing_code_elements": list(dict.fromkeys(missing)),
                "target_file": _normalize_patch_path(
                    getattr(hypothesis, "target_file", "")
                ),
                "changed_files": list(changed_files),
                "counts_as_screened_round": False,
                "counts_as_proposal_quality_attempt": True,
                "decision_features_excluded": True,
            },
        }

    # --- Instance / output ---

    def load_instance(self, instance_path: str) -> Any:
        self._ensure_modules()
        models = self._models_mod
        with open(instance_path, encoding="utf-8") as f:
            idata = json.load(f)
        orders = {}
        for o in idata["orders"]:
            spu_list = [
                models.SPU(packing_type=s["packing_type"], quantity=s["quantity"])
                for s in o["spu_list"]
            ]
            order = models.Order(
                order_id=o["order_id"],
                vehicle_category=o["vehicle_category"],
                vehicle_subcategory=o["vehicle_subcategory"],
                urgent=o["urgent"],
                hazard_flag=o["hazard_flag"],
                hazard_quantity=o["hazard_quantity"],
                pickup_name=o["pickup_name"],
                pickup_province=o["pickup_province"],
                pickup_city=o["pickup_city"],
                declaration_amount=o["declaration_amount"],
                lsp=o["lsp"],
                ship_method=o["ship_method"],
                destination_country=o["destination_country"],
                spu_list=spu_list,
                locked_vehicle_id=o.get("locked_vehicle_id"),
            )
            orders[order.order_id] = order
        amount_limits = idata.get("amount_limits", {})
        instance = models.Instance(
            orders=orders,
            amount_limits=amount_limits,
            phase=1,
        )
        return instance

    def deserialize_solver_output(
        self,
        raw_output: Mapping[str, Any],
        instance: Any,
    ) -> SolverArtifact:
        self._ensure_modules()
        models = self._models_mod

        vehicles = {}
        for vid, vdata in raw_output.get("vehicles", {}).items():
            vehicles[vid] = models.Vehicle(
                vehicle_id=vdata["vehicle_id"],
                vehicle_type=vdata["vehicle_type"],
                region=vdata["region"],
                order_ids=list(vdata["order_ids"]),
            )
        solution = models.Solution(
            vehicles=vehicles,
            assignment=dict(raw_output.get("assignment", {})),
        )

        objective_raw = raw_output.get("objective", {})
        feasible_raw = raw_output.get("feasible", False)

        return SolverArtifact(
            raw_output=dict(raw_output),
            objective={
                "subcategory_splits": objective_raw.get("subcategory_splits", 0),
                "total_cost": objective_raw.get("total_cost", 0),
            },
            feasible=feasible_raw,
            normalized_solution=solution,
        )

    # --- Verification ---

    def check_solution_consistency(
        self,
        artifact: SolverArtifact,
        instance: Any,
    ) -> CheckReport:
        """C0a structural completeness check — every order assigned exactly once."""
        solution = artifact.normalized_solution
        if solution is None:
            return CheckReport(passed=False, reasons=("no normalized_solution",))

        reasons: list[str] = []
        all_order_ids = set(instance.orders.keys())
        placed: dict[str, str] = {}
        for vid, vehicle in solution.vehicles.items():
            for oid in vehicle.order_ids:
                if oid not in all_order_ids:
                    reasons.append(f"vehicle {vid} contains unknown order {oid}")
                elif oid in placed:
                    reasons.append(f"order {oid} in both {placed[oid]} and {vid}")
                else:
                    placed[oid] = vid

        missing = all_order_ids - set(placed.keys())
        if missing:
            reasons.append(f"{len(missing)} orders not assigned: {sorted(missing)[:5]}")

        return CheckReport(passed=len(reasons) == 0, reasons=tuple(reasons))

    def check_feasibility(
        self,
        artifact: SolverArtifact,
        instance: Any,
    ) -> CheckReport:
        self._ensure_modules()
        solution = artifact.normalized_solution
        if solution is None:
            return CheckReport(passed=False, reasons=("no normalized_solution",))

        feas = self._oracle_mod.check_feasibility(solution, instance, phase=1)
        return CheckReport(
            passed=feas.is_feasible,
            reasons=tuple(feas.violations[:10]),
        )

    def recompute_objective(
        self,
        artifact: SolverArtifact,
        instance: Any,
    ) -> Mapping[str, int | float]:
        self._ensure_modules()
        solution = artifact.normalized_solution
        obj = self._oracle_mod.recompute_objective(solution, instance, solve_time_ms=0)
        return {
            "subcategory_splits": obj.subcategory_splits,
            "total_cost": obj.total_cost,
        }

    # --- Lower bound ---

    def estimate_lower_bound(
        self,
        metric_name: str,
        instance_paths: Sequence[str],
    ) -> LowerBoundEstimate | None:
        """Load precomputed MILP bounds if available.

        Looks for a JSON file at <root_dir>/milp_bounds/<instance_stem>.json
        containing {"subcategory_splits": ..., "total_cost": ..., "status": ...}.
        CPLEX-generated non-optimal incumbents are report-only references and
        therefore return kind="instance" rather than kind="exact".
        """
        bounds_dir = os.path.join(self._root, "milp_bounds")
        if not os.path.isdir(bounds_dir):
            return None

        values: list[float] = []
        kind = "exact"
        for path in instance_paths:
            stem = os.path.splitext(os.path.basename(path))[0]
            bound_file = os.path.join(bounds_dir, f"{stem}.json")
            if not os.path.isfile(bound_file):
                continue
            with open(bound_file) as f:
                data = json.load(f)
            if metric_name in data:
                values.append(data[metric_name])
                if data.get("status") != "optimal":
                    kind = "instance"

        if not values:
            return None

        return LowerBoundEstimate(
            metric_name=metric_name,
            value=sum(values) / len(values),
            kind=kind,
            note=f"MILP {kind} from {len(values)} instances",
        )


def _render_objective_policy(spec: ProblemSpecV1) -> str:
    ordered = sorted(spec.objectives, key=lambda obj: obj.priority)
    if spec.objective_policy.mode == "weighted_sum":
        lines = [
            "Policy: weighted_sum. The decision objective is one weighted scalar; "
            "any positive weighted aggregate improvement is valuable."
        ]
        if spec.objective_policy.expose_weights_to_llm:
            for obj in ordered:
                lines.append(
                    f"- {obj.name}: direction={obj.direction}, "
                    f"weight={obj.weight}, tie_tolerance={obj.tie_tolerance}"
                )
        else:
            for obj in ordered:
                lines.append(
                    f"- {obj.name}: direction={obj.direction}, "
                    f"tie_tolerance={obj.tie_tolerance}"
                )
        return "\n".join(lines)

    if spec.objective_policy.mode == "single":
        obj = ordered[0]
        return (
            f"Policy: single objective. Decision metric is `{obj.name}` "
            f"({obj.direction}, tie_tolerance={obj.tie_tolerance})."
        )

    lines = [
        "Policy: lexicographic. Compare objectives in priority order; a lower-priority "
        "objective matters only when all higher-priority objectives tie within tolerance."
    ]
    for obj in ordered:
        lines.append(
            f"- priority {obj.priority}: {obj.name} "
            f"({obj.direction}, tie_tolerance={obj.tie_tolerance})"
        )
    return "\n".join(lines)


def _render_objective_implication(spec: ProblemSpecV1) -> str:
    if spec.objective_policy.mode == "weighted_sum":
        return (
            "Key implication for weighted-sum specs: an operator may improve any "
            "component if the weighted aggregate improves. Higher-weight components "
            "have larger marginal value, but feasibility constraints remain hard."
        )
    if spec.objective_policy.mode == "single":
        return (
            "Key implication for single-objective specs: an operator is useful when "
            "it measurably improves the decision metric without violating hard constraints."
        )
    return (
        "Key implication for lexicographic specs: an operator may improve any metric, "
        "but lower-priority gains are only decision-relevant when all higher-priority "
        "metrics are preserved within tolerance. Lower-priority moves should include "
        "a guard that returns the original solution if they would harm a protected metric."
    )


def _render_validation_transfer_guidance() -> str:
    return (
        "Warehouse operator proposals must handle screening-to-validation "
        "transfer explicitly. A recent high-risk pattern was a "
        "same_subcategory_consolidate-style operator that looked positive in "
        "screening but failed formal validation with aggregate 2/3/0, paired "
        "6/9/0, median delta 0, and "
        "VALIDATION_FAIL_NO_HIERARCHICAL_GAIN. Before code generation, state "
        "why the mechanism should generalize beyond screening cases, which "
        "operator activation counters should become positive, which effect "
        "counters should show subcategory split or cost improvement, and what "
        "guard prevents a screening-only no-effect move from being accepted. "
        "Store runtime counters on the operator instance under "
        "`self.validation_transfer_diagnostics` using the declared standard "
        "keys (`operator_invocations`, "
        "`eligible_vehicle_or_order_groups_seen`, `accepted_moves`, "
        "`split_delta_sum`, `cost_delta_sum`, `improving_move_count`) so the "
        "warehouse solver exports them as "
        "`runtime.operator_diagnostics.{mechanism}.*`. Do not use a local "
        "dict or undeclared expected_telemetry keys that cannot be consumed by "
        "the telemetry guard."
    )


def _render_surface_prompt_guidance(spec: ProblemSpecV1, surface_name: str) -> str:
    surface = None
    for candidate in spec.research_surfaces or []:
        if getattr(candidate, "name", "") == surface_name:
            surface = candidate
            break
    if surface is None:
        return ""
    prompt = getattr(surface, "prompt", None)
    if prompt is None:
        return ""
    lines = [f"### Active Surface Prompt Guidance: {surface_name}"]
    hypothesis = str(getattr(prompt, "hypothesis_guidance", "") or "").strip()
    implementation = str(
        getattr(prompt, "implementation_guidance", "") or ""
    ).strip()
    anti_patterns = str(getattr(prompt, "anti_patterns", "") or "").strip()
    if hypothesis:
        lines.append(f"- hypothesis_guidance: {hypothesis}")
    if implementation:
        lines.append(f"- implementation_guidance: {implementation}")
    if anti_patterns:
        lines.append(f"- anti_patterns: {anti_patterns}")
    return "\n".join(lines) if len(lines) > 1 else ""


WAREHOUSE_VALIDATION_TRANSFER_QUALITY_FAILURE = (
    "agent_quality_blocked:warehouse_validation_transfer_quality_missing"
)
WAREHOUSE_VALIDATION_TRANSFER_PATCH_QUALITY_FAILURE = (
    "agent_quality_blocked:warehouse_validation_transfer_patch_quality_missing"
)

_EXISTING_OPERATOR_MODULES = frozenset(
    {
        "operators/change_vehicle_type.py",
        "operators/destroy_rebuild.py",
        "operators/merge_vehicles.py",
        "operators/move_order.py",
        "operators/split_vehicle.py",
        "operators/swap_orders.py",
    }
)


def _is_high_risk_warehouse_hypothesis(branch: Any | None, hypothesis: Any) -> bool:
    if hypothesis is None:
        return False
    if not _is_warehouse_operator_hypothesis(hypothesis):
        return False
    if _is_screening_positive_followup(branch):
        return True
    action = str(getattr(hypothesis, "action", "") or "").strip()
    return action in {"modify", "create_new", "remove"}


def _is_warehouse_operator_hypothesis(hypothesis: Any) -> bool:
    locus = str(getattr(hypothesis, "change_locus", "") or "").strip()
    target_file = _normalize_patch_path(getattr(hypothesis, "target_file", ""))
    return locus in {"order_level", "vehicle_level"} or (
        target_file.startswith("operators/") and target_file.endswith(".py")
    )


def _is_screening_positive_followup(branch: Any | None) -> bool:
    if branch is None:
        return False
    status = str(getattr(branch, "branch_code_status", "") or "")
    tier = str(getattr(branch, "last_screening_feedback_tier", "") or "")
    summary = getattr(branch, "branch_evidence_summary", {}) or {}
    return (
        status in {"active_weak_positive", "screening_positive"}
        or tier in {"weak_positive", "screening_positive", "strong_positive"}
        or str(summary.get("screening_tier") or "") in {
            "weak_positive",
            "screening_positive",
            "strong_positive",
        }
    )


def _missing_transfer_quality_claims(hypothesis: Any) -> tuple[str, ...]:
    text = _hypothesis_quality_text(hypothesis)
    missing: list[str] = []
    if not _mentions_validation_transfer_risk(text):
        missing.append("validation_transfer_risk")
    if not _has_activation_effect_diagnostics(hypothesis, text):
        missing.append("activation_effect_diagnostics")
    if not _mentions_screening_only_guard(text):
        missing.append("screening_only_guard")
    return tuple(missing)


def _warehouse_hypothesis_quality_repair_template(
    missing: Sequence[str],
) -> Mapping[str, Any]:
    return {
        "repair_type": "warehouse_validation_transfer_hypothesis_quality",
        "purpose": (
            "Make the next warehouse operator hypothesis explicitly measurable "
            "for screening-to-validation transfer before code generation."
        ),
        "missing_items": list(dict.fromkeys(str(item) for item in missing)),
        "required_claims": [
            (
                "validation_transfer_risk: name why a screening-positive "
                "operator can fail formal validation or holdout cases"
            ),
            (
                "activation_effect_diagnostics: name at least one activation "
                "counter such as operator_invocations, eligible_*_seen, or "
                "accepted_moves and one effect counter such as split_delta_sum, "
                "cost_delta_sum, or improving_move_count"
            ),
            (
                "screening_only_guard: state the no-op, case-general, or "
                "lexicographic guard that prevents screening-only gains"
            ),
        ],
        "hypothesis_field_hints": {
            "target_weakness": (
                "Mention validation/formal transfer risk, not only the "
                "screening symptom."
            ),
            "expected_effect": (
                "Declare activation and effect diagnostics that should move if "
                "the mechanism is real."
            ),
            "no_op_condition": (
                "State the guard that returns the original solution when the "
                "move is screening-only, not case-general, or lexicographically "
                "dominated."
            ),
            "risk_to_higher_priority": (
                "Acknowledge no hierarchical gain / median-delta-zero formal "
                "failure risk."
            ),
        },
        "must_not": [
            "Do not propose another warehouse operator hypothesis that only says it may improve screening.",
            "Do not defer diagnostics to analysis prose; put them in hypothesis fields.",
        ],
        "decision_features_excluded": True,
    }


def _missing_transfer_patch_quality(code: str) -> tuple[str, ...]:
    if not str(code or "").strip():
        return ("activation_effect_diagnostic_code", "screening_or_lexicographic_guard")
    signal_text = _code_signal_text(code)
    missing: list[str] = []
    if not _patch_has_activation_effect_diagnostics(code, signal_text):
        missing.append("activation_effect_diagnostic_code")
    if not _patch_has_screening_or_lexicographic_guard(code, signal_text):
        missing.append("screening_or_lexicographic_guard")
    return tuple(missing)


def _warehouse_patch_quality_repair_template(
    missing: Sequence[str],
) -> Mapping[str, Any]:
    return {
        "repair_type": "warehouse_validation_transfer_patch_quality",
        "purpose": (
            "Make the warehouse operator patch visibly measurable for "
            "activation/effect transfer and guarded against screening-only or "
            "lexicographically dominated moves."
        ),
        "missing_items": list(dict.fromkeys(str(item) for item in missing)),
        "required_code_signals": {
            "activation": [
                "operator_invocations",
                "eligible_vehicle_or_order_groups_seen",
                "accepted_moves",
            ],
            "effect": [
                "split_delta_sum",
                "cost_delta_sum",
                "improving_move_count",
            ],
            "guard": [
                "screening_only_guard",
                "validation_transfer_guard",
                "no_op_condition",
                "lexicographic guard comparing subcategory_splits and total_cost",
            ],
        },
        "minimal_shape": [
            "Initialize or update self.validation_transfer_diagnostics on the operator instance; local dictionaries are not exportable telemetry.",
            "Increment operator_invocations before evaluating the move.",
            "Increment an eligible_* counter only when the case-general precondition is true.",
            "Compute split_delta and cost_delta before accepting a move.",
            "Only accept when the move improves subcategory_splits or preserves splits and improves total_cost.",
            "Return the original solution when the move is screening-only, not case-general, or lexicographically dominated.",
        ],
        "example_identifiers": [
            "validation_transfer_diagnostics",
            "operator_invocations",
            "eligible_vehicle_or_order_groups_seen",
            "accepted_moves",
            "split_delta_sum",
            "cost_delta_sum",
            "improving_move_count",
            "screening_only_guard",
        ],
        "must_not": [
            "Do not add counters in comments only; identifiers must appear in executable code.",
            "Do not store diagnostics only in a local dict; the solver exports self.validation_transfer_diagnostics from operator instances.",
            "Do not accept moves that worsen subcategory_splits for a cost-only gain.",
        ],
        "decision_features_excluded": True,
    }


def _warehouse_operator_patch_code(
    patch: Any,
    hypothesis: Any,
) -> tuple[str, tuple[str, ...]]:
    target_file = _normalize_patch_path(getattr(hypothesis, "target_file", ""))
    chunks: list[str] = []
    changed_files: list[str] = []
    for change in _patch_changes(patch):
        file_path = _normalize_patch_path(getattr(change, "file_path", ""))
        if not _is_warehouse_operator_patch_file(file_path, target_file):
            continue
        changed_files.append(file_path)
        action = str(getattr(change, "action", "") or "").strip()
        if action in {"delete", "remove"}:
            continue
        chunks.append(str(getattr(change, "code_content", "") or ""))
    return "\n\n".join(chunks), tuple(dict.fromkeys(changed_files))


def _is_warehouse_operator_patch_file(file_path: str, target_file: str) -> bool:
    normalized = _normalize_patch_path(file_path)
    if not normalized.startswith("operators/") or not normalized.endswith(".py"):
        return False
    if not target_file:
        return True
    return normalized == target_file or _is_existing_operator_module(normalized)


def _code_signal_text(code: str) -> str:
    try:
        tree = ast.parse(code or "")
    except SyntaxError:
        return str(code or "").lower()
    parts: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            parts.append(node.id)
        elif isinstance(node, ast.Attribute):
            parts.append(node.attr)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            parts.append(node.name)
        elif isinstance(node, ast.arg):
            parts.append(node.arg)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            parts.append(node.value)
    return " ".join(parts).lower()


def _patch_has_activation_effect_diagnostics(code: str, signal_text: str) -> bool:
    del signal_text
    return _patch_has_exportable_validation_transfer_diagnostics(code)


_STANDARD_VALIDATION_TRANSFER_KEYS = frozenset(
    {
        "operator_invocations",
        "eligible_vehicle_or_order_groups_seen",
        "accepted_moves",
        "split_delta_sum",
        "cost_delta_sum",
        "improving_move_count",
    }
)
_ACTIVATION_DIAGNOSTIC_KEYS = frozenset(
    {
        "operator_invocations",
        "eligible_vehicle_or_order_groups_seen",
        "accepted_moves",
    }
)
_EFFECT_DIAGNOSTIC_KEYS = frozenset(
    {
        "split_delta_sum",
        "cost_delta_sum",
        "improving_move_count",
    }
)


def _patch_has_exportable_validation_transfer_diagnostics(code: str) -> bool:
    try:
        tree = ast.parse(code or "")
    except SyntaxError:
        return False

    aliases: set[str] = set()
    declared_keys: set[str] = set()
    mutating_keys: set[str] = set()
    helper_return_keys = _diagnostic_helper_return_keys(tree)

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            if any(_is_self_validation_transfer_attr(target) for target in node.targets):
                declared_keys.update(
                    _diagnostic_initializer_keys(node.value, helper_return_keys)
                )
            if _is_self_validation_transfer_attr(node.value):
                aliases.update(_name_targets(node.targets))
            for target in node.targets:
                if _is_exportable_diagnostic_target(target, aliases):
                    mutating_keys.update(_diagnostic_keys_from_node(target))
        elif isinstance(node, ast.AnnAssign):
            if _is_self_validation_transfer_attr(node.target):
                declared_keys.update(
                    _diagnostic_initializer_keys(node.value, helper_return_keys)
                )
            if _is_self_validation_transfer_attr(node.value):
                aliases.update(_name_targets((node.target,)))
            if _is_exportable_diagnostic_target(node.target, aliases):
                mutating_keys.update(_diagnostic_keys_from_node(node.target))
        elif isinstance(node, ast.AugAssign):
            if _is_exportable_diagnostic_target(node.target, aliases):
                mutating_keys.update(_diagnostic_keys_from_node(node.target))

    return (
        _STANDARD_VALIDATION_TRANSFER_KEYS <= declared_keys
        and bool(mutating_keys & _ACTIVATION_DIAGNOSTIC_KEYS)
        and bool(mutating_keys & _EFFECT_DIAGNOSTIC_KEYS)
    )


def _name_targets(targets: Sequence[ast.AST]) -> set[str]:
    return {target.id for target in targets if isinstance(target, ast.Name)}


def _diagnostic_helper_return_keys(tree: ast.AST) -> dict[str, set[str]]:
    helpers: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        returned_keys: set[str] = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Return):
                returned_keys.update(_literal_dict_string_keys(child.value))
        if returned_keys:
            helpers[node.name] = returned_keys
    return helpers


def _diagnostic_initializer_keys(
    node: ast.AST | None,
    helper_return_keys: Mapping[str, set[str]],
) -> set[str]:
    keys = _literal_dict_string_keys(node)
    if keys:
        return keys
    helper_name = _diagnostic_helper_call_name(node)
    if not helper_name:
        return set()
    return set(helper_return_keys.get(helper_name, set()))


def _diagnostic_helper_call_name(node: ast.AST | None) -> str | None:
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _is_self_validation_transfer_attr(node: ast.AST | None) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "validation_transfer_diagnostics"
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    )


def _is_exportable_diagnostic_target(node: ast.AST, aliases: set[str]) -> bool:
    if not isinstance(node, ast.Subscript):
        return False
    root = node.value
    return _is_self_validation_transfer_attr(root) or (
        isinstance(root, ast.Name) and root.id in aliases
    )


def _diagnostic_keys_from_node(node: ast.AST) -> set[str]:
    keys: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            value = child.value.strip()
            if value in _STANDARD_VALIDATION_TRANSFER_KEYS:
                keys.add(value)
    return keys


def _literal_dict_string_keys(node: ast.AST | None) -> set[str]:
    if not isinstance(node, ast.Dict):
        return set()
    keys: set[str] = set()
    for key in node.keys:
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            keys.add(key.value.strip())
    return keys


def _patch_has_screening_or_lexicographic_guard(
    code: str,
    signal_text: str,
) -> bool:
    del signal_text
    try:
        tree = ast.parse(code or "")
    except SyntaxError:
        return False
    executable_guard_names = _executable_transfer_guard_names(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        if _is_string_only_guard_value(node.test):
            continue
        test_text = _ast_signal_text(node.test)
        test_names = _ast_name_texts(node.test)
        if not _guard_test_is_transfer_relevant(
            test_text,
            test_names=test_names,
            executable_guard_names=executable_guard_names,
        ):
            continue
        if any(_returns_original_solution(child) for child in ast.walk(node)):
            return True
    return False


def _executable_transfer_guard_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        targets: Sequence[ast.AST]
        value: ast.AST | None
        if isinstance(node, ast.Assign):
            targets = tuple(node.targets)
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = (node.target,)
            value = node.value
        elif isinstance(node, ast.NamedExpr):
            targets = (node.target,)
            value = node.value
        else:
            continue
        if value is None or _is_string_only_guard_value(value):
            continue
        value_text = _ast_signal_text(value)
        if not _guard_expression_has_metric_pair(value_text):
            continue
        for target in targets:
            names.update(_assigned_name_texts(target))
    return names


def _assigned_name_texts(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Name):
        return {node.id.lower()}
    if isinstance(node, (ast.Tuple, ast.List)):
        names: set[str] = set()
        for child in node.elts:
            names.update(_assigned_name_texts(child))
        return names
    return set()


def _is_string_only_guard_value(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str)
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return all(_is_string_only_guard_value(child) for child in node.elts)
    return False


def _ast_signal_text(node: ast.AST) -> str:
    parts: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            parts.append(child.id)
        elif isinstance(child, ast.Attribute):
            parts.append(child.attr)
        elif isinstance(child, ast.Constant) and isinstance(child.value, str):
            parts.append(child.value)
    return " ".join(parts).lower()


def _ast_name_texts(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.add(child.id.lower())
    return names


def _guard_test_is_transfer_relevant(
    test_text: str,
    *,
    test_names: set[str],
    executable_guard_names: set[str],
) -> bool:
    if test_names & executable_guard_names:
        return True
    return _guard_expression_has_metric_pair(test_text)


def _guard_expression_has_metric_pair(test_text: str) -> bool:
    has_split = any(
        term in test_text
        for term in (
            "subcategory_splits",
            "candidate_splits",
            "base_splits",
            "split_delta",
            "split_delta_sum",
            "splits",
            "split",
        )
    )
    has_cost = any(
        term in test_text
        for term in (
            "total_cost",
            "candidate_cost",
            "base_cost",
            "cost_delta",
            "cost_delta_sum",
            "cost",
        )
    )
    return has_split and has_cost


def _returns_original_solution(node: ast.AST) -> bool:
    if not isinstance(node, ast.Return):
        return False
    value = node.value
    if isinstance(value, ast.Name):
        return value.id in {"solution", "original_solution", "base_solution"}
    if isinstance(value, ast.Attribute):
        return value.attr in {"solution", "original_solution", "base_solution"}
    return False


def _hypothesis_quality_text(hypothesis: Any) -> str:
    fields = [
        getattr(hypothesis, "hypothesis_text", ""),
        getattr(hypothesis, "target_weakness", ""),
        getattr(hypothesis, "expected_effect", ""),
        getattr(hypothesis, "objective_tradeoff_policy", ""),
        getattr(hypothesis, "no_op_condition", ""),
        getattr(hypothesis, "risk_to_higher_priority", ""),
        getattr(hypothesis, "runtime_budget_strategy", ""),
        getattr(hypothesis, "target_file", ""),
        _jsonish(getattr(hypothesis, "branch_lesson_usage", {}) or {}),
        _jsonish(getattr(hypothesis, "mechanism_changes", ()) or ()),
    ]
    return " ".join(str(field or "") for field in fields).lower()


def _jsonish(value: Any) -> str:
    try:
        return json.dumps(value, default=str, sort_keys=True)
    except TypeError:
        return str(value)


def _mentions_validation_transfer_risk(text: str) -> bool:
    has_formal_stage = any(
        term in text for term in ("validation", "formal", "holdout")
    )
    has_transfer = any(
        term in text
        for term in (
            "transfer",
            "generaliz",
            "screening-to-validation",
            "screening to validation",
            "screening-positive",
            "screening positive",
            "screening-only",
            "screening only",
            "no hierarchical gain",
            "median delta 0",
            "2/3/0",
            "6/9/0",
        )
    )
    return has_formal_stage and has_transfer


def _has_activation_effect_diagnostics(hypothesis: Any, text: str) -> bool:
    has_activation_terms = any(
        term in text
        for term in (
            "activation",
            "operator_invocation",
            "operator invocation",
            "accepted_moves",
            "eligible_vehicle",
            "eligible_order",
        )
    )
    has_effect_terms = any(
        term in text
        for term in (
            "effect",
            "split_delta",
            "cost_delta",
            "improving_move",
            "record_move",
            "counter",
            "diagnostic",
        )
    )
    return has_activation_terms and has_effect_terms


def _mentions_screening_only_guard(text: str) -> bool:
    return any(
        term in text
        for term in (
            "screening-only",
            "screening only",
            "not only screening",
            "avoid overfit",
            "overfitting",
            "case-general",
            "general condition",
            "validation cases",
            "formal cases",
            "return the original solution",
            "no-op",
            "no op",
            "guard",
        )
    )


def _patch_changes(patch: Any) -> tuple[Any, ...]:
    iter_changes = getattr(patch, "iter_file_changes", None)
    if callable(iter_changes):
        try:
            return tuple(iter_changes())
        except Exception:
            return (patch,)
    additional = getattr(patch, "additional_changes", ()) or ()
    return (patch, *tuple(additional))


def _normalize_patch_path(value: Any) -> str:
    return str(value or "").replace("\\", "/").lstrip("/").strip()


def _is_existing_operator_module(file_path: str) -> bool:
    return _normalize_patch_path(file_path) in _EXISTING_OPERATOR_MODULES


def _preview_operator_code_static_state(
    code: str,
    *,
    issues: list[str],
    checks: list[dict[str, Any]],
) -> None:
    try:
        tree = ast.parse(code or "")
    except SyntaxError as exc:
        detail = f"operator code does not parse: {exc.msg}"
        issues.append(f"warehouse_operator_static_parse: {detail}")
        checks.append(
            {
                "name": "warehouse_operator_static_parse",
                "passed": False,
                "detail": detail,
            }
        )
        return
    declared_keys = _declared_dict_literal_keys(tree)
    unknown_refs = _unknown_nested_dict_key_refs(tree, declared_keys)
    if unknown_refs:
        detail = (
            "candidate operator references internal state keys not declared "
            f"in their local dict literals: {', '.join(unknown_refs[:5])}"
        )
        issues.append(f"warehouse_operator_internal_state_key: {detail}")
        checks.append(
            {
                "name": "warehouse_operator_internal_state_key",
                "passed": False,
                "detail": detail,
            }
        )
        return
    checks.append(
        {
            "name": "warehouse_operator_static_state_keys",
            "passed": True,
            "detail": "local dict state key references are internally declared",
        }
    )


def _declared_dict_literal_keys(tree: ast.AST) -> dict[str, set[str]]:
    declared: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            keys = _dict_literal_string_keys(node.value)
            if not keys:
                continue
            for target in node.targets:
                name = _assigned_state_name(target)
                if name:
                    declared.setdefault(name, set()).update(keys)
        elif isinstance(node, ast.AnnAssign):
            keys = _dict_literal_string_keys(node.value)
            name = _assigned_state_name(node.target)
            if name and keys:
                declared.setdefault(name, set()).update(keys)
    return declared


def _assigned_state_name(target: ast.AST) -> str:
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name):
        return target.value.id
    return ""


def _dict_literal_string_keys(value: ast.AST | None) -> set[str]:
    if isinstance(value, ast.Dict):
        return {
            key.value
            for key in value.keys
            if isinstance(key, ast.Constant) and isinstance(key.value, str)
        }
    if isinstance(value, ast.DictComp) and isinstance(value.value, ast.Dict):
        return _dict_literal_string_keys(value.value)
    return set()


def _unknown_nested_dict_key_refs(
    tree: ast.AST,
    declared_keys: Mapping[str, set[str]],
) -> list[str]:
    unknown: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Subscript):
            continue
        key = _constant_subscript_key(node.slice)
        if not key:
            continue
        base = node.value
        if not isinstance(base, ast.Subscript) or not isinstance(base.value, ast.Name):
            continue
        state_name = base.value.id
        known = declared_keys.get(state_name)
        if known is None or key in known:
            continue
        unknown.append(f"{state_name}[...][{key!r}]")
    return sorted(dict.fromkeys(unknown))


def _constant_subscript_key(slice_node: ast.AST) -> str:
    if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
        return slice_node.value
    return ""


# ---------------------------------------------------------------------------
# Module import helper (extracted from verification/feasibility.py)
# ---------------------------------------------------------------------------

def _import_module(directory: str, filename: str, sys_key: str) -> Any:
    path = os.path.join(directory, filename)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"{filename} not found at {path}")

    saved = list(sys.path)
    if directory not in sys.path:
        sys.path.insert(0, directory)
    try:
        spec = importlib.util.spec_from_file_location(sys_key, path)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        sys.modules[sys_key] = mod
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod
    finally:
        sys.path[:] = saved
