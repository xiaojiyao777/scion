from __future__ import annotations

from scion.tests.unit.agentic_solver_design_test_support import *

def test_active_solver_design_snapshot_exposes_active_mechanisms(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context_with_champion(tmp_path)

    observation = registry.call("context.read_active_solver_design", {}, context)

    payload = observation.structured_payload
    rendered = json.dumps(payload, sort_keys=True)
    assert observation.is_error is False
    assert payload["surface"] == "solver_design"
    assert payload["active_surface"]["entrypoint"] == (
        "policies/baseline_algorithm.py::solve"
    )
    assert payload["provenance"]["source"] == "champion_snapshot"
    assert payload["source_digest"]["snapshot_digest"]
    assert "policies/baseline_modules/scheduler.py" in payload["source_digest"]["files"]
    assert "_initial_solution" in rendered
    assert "alns_loop" in rendered
    assert "destroy_repair" in rendered
    assert "_shaw_removal" in rendered
    assert "seed-based related/proximity-cluster destroy operator" in rendered
    assert "distance" in rendered
    assert "demand" in rendered
    assert "original-route relatedness" in rendered
    assert "_AdaptiveWeights.update" in rendered
    assert "_SimulatedAnnealing.accept" in rendered
    assert "_or_opt_2" in rendered
    assert "_or_opt_3" in rendered
    assert "vns_embedded" in rendered
    assert "legacy_inactive_surface_exclusion" in payload
    assert "excluded_surface_policy" in rendered
    assert "as active evidence" in rendered
    assert "must not be used as optimization directions" in rendered
    assert payload["inactive_files"] == []
    assert "policies/solver_algorithm.py" not in rendered


def test_solver_call_graph_marks_initial_solution_alns_vns_and_acceptance(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context_with_champion(tmp_path)

    observation = registry.call("context.read_solver_call_graph", {}, context)

    payload = observation.structured_payload
    rendered = json.dumps(payload, sort_keys=True)
    assert observation.is_error is False
    assert payload["surface"] == "solver_design"
    assert "scheduler._ALNSVNSSolver._initial_solution" in rendered
    assert "ALNS destroy/repair loop" in rendered
    assert "_shaw_removal" in rendered
    assert "distance + demand + original-route relatedness" in rendered
    assert "local_search._vns" in rendered
    assert "_default_vns_operators" in rendered
    assert "_SimulatedAnnealing.accept" in rendered
    assert "_AdaptiveWeights" in rendered
    assert "legacy_inactive_surface_exclusion" in payload


def test_active_solver_algorithm_file_tools_are_allowlisted_with_provenance(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context_with_champion(tmp_path)

    listed = registry.call("context.list_algorithm_files", {}, context)
    read_file = registry.call(
        "context.read_algorithm_file",
        {
            "file_path": "policies/baseline_modules/scheduler.py",
            "max_chars": 24000,
        },
        context,
    )
    read_symbol = registry.call(
        "context.read_algorithm_symbol",
        {
            "file_path": "policies/baseline_modules/scheduler.py",
            "symbol": "_ALNSVNSSolver._initial_solution",
            "max_chars": 12000,
        },
        context,
    )
    denied = registry.call(
        "context.read_algorithm_file",
        {"file_path": "vrp/solver.py"},
        context,
    )

    files = listed.structured_payload["files"]
    by_path = {item["file_path"]: item for item in files}
    guidance = algorithm_file_path_guidance(context)
    assert listed.is_error is False
    assert files[0]["file_path"] == "policies/baseline_algorithm.py"
    assert all(item["active"] is True for item in files)
    assert "policies/solver_algorithm.py" not in by_path
    assert guidance["example_file_path"] == "policies/baseline_algorithm.py"
    assert guidance["primary_entrypoint_file_path"] == "policies/baseline_algorithm.py"
    assert "compatibility_file_paths" not in guidance
    assert "policies/solver_algorithm.py" not in guidance["path_selection_rule"]
    assert "explicitly repairs" not in guidance["path_selection_rule"]
    assert by_path["policies/baseline_algorithm.py"]["active"] is True
    assert by_path["policies/baseline_modules/scheduler.py"]["source"] == (
        "champion_snapshot"
    )
    assert by_path["policies/baseline_modules/scheduler.py"]["digest"]

    assert read_file.is_error is False
    file_payload = read_file.structured_payload
    assert file_payload["readable"] is True
    assert file_payload["provenance"]["source"] == "champion_snapshot"
    assert "class _ALNSVNSSolver" in file_payload["content_preview"]

    assert read_symbol.is_error is False
    symbol_payload = read_symbol.structured_payload
    assert symbol_payload["readable"] is True
    assert symbol_payload["symbol"] == "_ALNSVNSSolver._initial_solution"
    assert "_sweep_construction" in symbol_payload["content_preview"]
    assert "_nearest_neighbor" in symbol_payload["content_preview"]
    assert symbol_payload["digest"]

    assert denied.is_error is True
    denied_payload = denied.structured_payload
    assert denied_payload["readable"] is False
    assert denied_payload["path_rejected"] is True
    assert denied_payload["file_path"] == "<path_rejected>"
    assert denied_payload["reason"] == "file_path_not_allowed"
    assert "policies/baseline_algorithm.py" in denied_payload["allowed_files"]
    assert denied_payload["allowed_file_paths"] == denied_payload["allowed_files"]
    assert denied_payload["required_first_tool"] == "context.list_algorithm_files"
    assert denied_payload["file_path_source_tool"] == "context.list_algorithm_files"
    assert "vrp/solver.py" not in denied_payload["allowed_files"]


@pytest.mark.parametrize(
    "bad_path",
    (
        "<UNKNOWN>",
        "solver_design",
        "vrp/solver.py",
        "../policies/baseline_algorithm.py",
    ),
)
def test_active_solver_rejects_invalid_path_without_echoing_it(
    tmp_path: Path,
    bad_path: str,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context_with_champion(tmp_path)

    file_observation = registry.call(
        "context.read_algorithm_file",
        {"file_path": bad_path},
        context,
    )
    symbol_observation = registry.call(
        "context.read_algorithm_symbol",
        {"file_path": bad_path, "symbol": "solve"},
        context,
    )

    rendered = json.dumps(
        {
            "file_observation": file_observation,
            "file_prompt": _observation_prompt_payload(file_observation),
            "symbol_observation": symbol_observation,
            "symbol_prompt": _observation_prompt_payload(symbol_observation),
        },
        sort_keys=True,
        default=str,
    )
    assert file_observation.is_error is True
    assert symbol_observation.is_error is True
    for observation in (file_observation, symbol_observation):
        assert observation.structured_payload["readable"] is False
        assert observation.structured_payload["path_rejected"] is True
        assert observation.structured_payload["file_path"] == "<path_rejected>"
        assert observation.structured_payload["reason"] == "file_path_not_allowed"
        assert observation.structured_payload["required_first_tool"] == (
            "context.list_algorithm_files"
        )
        assert "policies/baseline_algorithm.py" in observation.structured_payload[
            "allowed_file_paths"
        ]
        assert "solver_design is a research surface id" in observation.structured_payload[
            "surface_id_rule"
        ]
        assert bad_path not in observation.summary
    if bad_path != "solver_design":
        assert bad_path not in rendered
    assert '"file_path": "' + bad_path + '"' not in rendered


def test_active_solver_rejects_absolute_path_without_echoing_it(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context_with_champion(tmp_path)
    absolute_path = str(tmp_path / "private" / "solver.py")

    file_observation = registry.call(
        "context.read_algorithm_file",
        {"file_path": absolute_path},
        context,
    )
    symbol_observation = registry.call(
        "context.read_algorithm_symbol",
        {"file_path": absolute_path, "symbol": "solve"},
        context,
    )

    payload = file_observation.structured_payload
    rendered = json.dumps(
        {
            "file_observation": file_observation,
            "file_prompt": _observation_prompt_payload(file_observation),
            "symbol_observation": symbol_observation,
            "symbol_prompt": _observation_prompt_payload(symbol_observation),
        },
        sort_keys=True,
        default=str,
    )
    assert file_observation.is_error is True
    assert symbol_observation.is_error is True
    for observation in (file_observation, symbol_observation):
        assert observation.structured_payload["readable"] is False
        assert observation.structured_payload["path_rejected"] is True
        assert observation.structured_payload["file_path"] == "<path_rejected>"
        assert observation.structured_payload["reason"] == "file_path_not_allowed"
        assert absolute_path not in observation.summary
        assert str(tmp_path) not in observation.summary
    assert absolute_path not in rendered
    assert str(tmp_path) not in rendered


def test_active_solver_provenance_payload_does_not_expose_absolute_paths(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context_with_champion(tmp_path)

    observations = [
        registry.call("context.read_active_solver_design", {}, context),
        registry.call("context.read_solver_call_graph", {}, context),
        registry.call(
            "context.read_algorithm_file",
            {"file_path": "policies/baseline_algorithm.py"},
            context,
        ),
        registry.call(
            "context.read_algorithm_symbol",
            {
                "file_path": "policies/baseline_algorithm.py",
                "symbol": "solve",
            },
            context,
        ),
    ]
    payloads = [observation.structured_payload for observation in observations]
    forbidden_keys = {
        "source_root",
        "branch_workspace",
        "champion_code_snapshot_path",
    }

    def keys(value):
        if isinstance(value, dict):
            found = set(value)
            for child in value.values():
                found.update(keys(child))
            return found
        if isinstance(value, list):
            found = set()
            for child in value:
                found.update(keys(child))
            return found
        return set()

    rendered = json.dumps(payloads, sort_keys=True, default=str)
    assert all(observation.is_error is False for observation in observations)
    assert str(tmp_path) not in rendered
    assert forbidden_keys.isdisjoint(keys(payloads))
