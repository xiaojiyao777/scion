from __future__ import annotations

from scion.tests.unit.agentic_solver_design_test_support import *


def test_cvrp_active_solver_map_exposes_entrypoint_scheduler_and_registries(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context_with_champion(tmp_path)

    observation = registry.call(
        "context.read_active_solver_map",
        {"surface": "solver_design"},
        context,
    )

    assert observation.is_error is False
    payload = observation.structured_payload
    rendered = json.dumps(payload, sort_keys=True)
    assert payload["available"] is True
    assert payload["surface"] == "solver_design"
    assert payload["subject_id"] == "cvrp.solver_design.active_baseline"
    assert payload["snapshot_digest"]
    assert payload["entrypoints"][0]["file_path"] == "policies/baseline_algorithm.py"
    assert payload["entrypoints"][0]["symbol"] == "solve"
    assert "cvrp.scheduler.alns_vns_loop" in rendered
    assert "_ALNSVNSSolver.solve" in rendered
    assert "ALNS" in rendered
    assert "VNS" in rendered

    registry_ids = {item["registry_id"] for item in payload["operator_registries"]}
    assert {
        "cvrp.registry.construction",
        "cvrp.registry.destroy",
        "cvrp.registry.repair",
        "cvrp.registry.local_search_vns",
        "cvrp.registry.acceptance",
    } <= registry_ids
    editable_by_path = {item["file_path"]: item for item in payload["editable_files"]}
    assert editable_by_path["policies/baseline_algorithm.py"]["digest"]
    assert payload["source_policy"]["allowed_files_digest"]
    telemetry_by_field = {
        item["field"]: item
        for item in payload["telemetry_fields"]
    }
    assert telemetry_by_field[
        "solver_algorithm_context_records.{mechanism}_iterations"
    ]["role"] == "activation"
    assert telemetry_by_field[
        "solver_algorithm_phase_runtime_ms"
    ]["role"] == "budget"


def test_cvrp_vns_local_search_registry_is_readable(tmp_path: Path) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context_with_champion(tmp_path)

    observation = registry.call(
        "context.read_operator_registry",
        {
            "surface": "solver_design",
            "registry_id": "cvrp.registry.local_search_vns",
        },
        context,
    )

    assert observation.is_error is False
    payload = observation.structured_payload
    assert payload["available"] is True
    assert payload["owner_symbol"] == "_default_vns_operators"
    symbols = {operator["symbol"] for operator in payload["operators"]}
    assert {
        "_two_opt_intra",
        "_relocate",
        "_or_opt_1",
        "_or_opt_2",
        "_or_opt_3",
        "_swap",
        "_two_opt_star",
    } <= symbols
    assert payload["integration_points"][0]["file_path"] == (
        "policies/baseline_modules/local_search.py"
    )
    assert payload["read_receipt"]["digest"]


def test_cvrp_algorithm_slice_reads_registry_block_with_digest_and_bounds(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context_with_champion(tmp_path)

    observation = registry.call(
        "context.read_algorithm_slice",
        {
            "surface": "solver_design",
            "slice_id": "cvrp.slice.scheduler.destroy_ops",
            "max_chars": 24000,
        },
        context,
    )

    assert observation.is_error is False
    payload = observation.structured_payload
    assert payload["available"] is True
    assert payload["slice_kind"] == "registry_block"
    assert payload["file_path"] == "policies/baseline_modules/scheduler.py"
    assert payload["line_start"] is not None
    assert payload["line_end"] >= payload["line_start"]
    assert "destroy_ops = [" in payload["content"]
    assert "_random_removal" in payload["content"]
    assert "_shaw_removal" in payload["content"]
    assert payload["content_digest"]
    assert payload["read_receipt"]["content_digest"] == payload["content_digest"]
    assert payload["source_policy_receipt"]["allowed"] is True


def test_cvrp_algorithm_slice_reads_target_function_with_bounded_content(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context_with_champion(tmp_path)

    observation = registry.call(
        "context.read_algorithm_slice",
        {
            "surface": "solver_design",
            "slice_id": "cvrp.slice.local_search.default_vns_operators",
            "max_chars": 160,
        },
        context,
    )

    assert observation.is_error is False
    payload = observation.structured_payload
    assert payload["available"] is True
    assert payload["slice_kind"] == "symbol_body"
    assert payload["line_start"] is not None
    assert payload["line_end"] >= payload["line_start"]
    assert payload["truncated"] is True
    assert len(payload["content"]) == 160
    assert "def _default_vns_operators" in payload["content"]
    assert payload["content_digest"]
    assert payload["source_policy_receipt"]["allowed"] is True


def test_cvrp_unknown_algorithm_slice_returns_structured_unavailable(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context_with_champion(tmp_path)

    observation = registry.call(
        "context.read_algorithm_slice",
        {
            "surface": "solver_design",
            "slice_id": "cvrp.slice.missing",
        },
        context,
    )

    assert observation.is_error is False
    payload = observation.structured_payload
    assert payload["available"] is False
    assert payload["unavailable"]["reason"] == "algorithm_slice_not_found"
    assert payload["read_receipt"]["available"] is False


def test_cvrp_active_solver_map_payloads_do_not_expose_holdout_details(
    tmp_path: Path,
) -> None:
    generic_context = _context(tmp_path)
    context = replace(
        _cvrp_context_with_champion(tmp_path),
        step_history=generic_context.step_history,
        split_manifest={"SECRET_HOLDOUT": "do not expose"},
    )
    registry = ProposalToolRegistry.default_read_only()

    observations = [
        registry.call("context.read_active_solver_map", {}, context),
        registry.call(
            "context.read_operator_registry",
            {"registry_id": "cvrp.registry.destroy"},
            context,
        ),
        registry.call(
            "context.read_algorithm_slice",
            {"slice_id": "cvrp.slice.scheduler.destroy_ops"},
            context,
        ),
    ]

    rendered = json.dumps(
        [observation.structured_payload for observation in observations],
        sort_keys=True,
    )
    assert all(observation.is_error is False for observation in observations)
    assert all(
        observation.structured_payload["available"] for observation in observations
    )
    for token in (
        "SECRET_HOLDOUT",
        "SECRET_VALIDATION",
        "SECRET_FROZEN",
        "validation raw",
        "frozen raw",
        "split_manifest",
        "holdout",
    ):
        assert token not in rendered
