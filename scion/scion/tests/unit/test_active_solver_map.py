from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from scion.proposal.active_solver_map import ActiveSolverMap
from scion.proposal.tools import ProposalToolContext, ProposalToolRegistry


def _map_payload(surface: str = "generic_solver") -> dict:
    return {
        "surface": surface,
        "subject_id": "subject.primary",
        "snapshot_digest": "snapshot-digest-1",
        "entrypoints": [
            {
                "id": "entry.solve",
                "file_path": "solver/main.py",
                "symbol": "solve",
                "summary": "Primary solve entrypoint.",
                "calls": [
                    {
                        "target_id": "scheduler.run",
                        "evidence": ["solve delegates to scheduler"],
                    }
                ],
            }
        ],
        "editable_files": [
            {
                "file_path": "solver/main.py",
                "role": "entrypoint",
                "digest": "file-digest-1",
                "read_budget_hint": 800,
            }
        ],
        "operator_registries": [
            {
                "registry_id": "registry.primary",
                "owner_file": "solver/operators.py",
                "owner_symbol": "build_registry",
                "registry_kind": "custom",
                "operators": [
                    {
                        "id": "operator.alpha",
                        "symbol": "alpha",
                        "file_path": "solver/operators.py",
                        "order": 0,
                        "role": "improvement",
                        "summary": "Generic improvement operator.",
                        "mechanism_tags": ["generic_move"],
                        "telemetry_ids": ["telemetry.alpha"],
                    }
                ],
            }
        ],
        "scheduler_integrations": [
            {
                "integration_id": "scheduler.run",
                "file_path": "solver/scheduler.py",
                "symbol": "run",
                "phase": "search",
                "summary": "Runs a bounded search phase.",
                "calls": ["operator.alpha"],
                "guard_conditions": ["budget_remaining"],
                "state_variables": ["best_score"],
                "telemetry_events": ["telemetry.alpha"],
            }
        ],
        "algorithm_slices": [
            {
                "slice_id": "slice.alpha",
                "file_path": "solver/operators.py",
                "symbols": ["alpha"],
                "purpose": "Show operator body.",
                "exposure_level": "body",
                "source_digest": "slice-source-digest",
                "token_estimate": 12,
                "redaction_reason": None,
            }
        ],
        "telemetry_fields": [
            {
                "field": "telemetry.alpha",
                "role": "activation",
                "mechanism_id_template": "alpha",
                "declared_by": "provider",
            }
        ],
        "known_mechanism_facts": [
            {
                "fact_id": "fact.alpha",
                "claim": "The alpha operator is wired into the scheduler.",
                "evidence": ["registry.primary includes operator.alpha"],
                "provenance": "provider",
            }
        ],
        "source_policy": {
            "max_total_tokens": 2000,
            "max_body_tokens_per_tool_call": 800,
            "allowed_files_digest": "allowed-files-digest",
            "redaction_policy": "summary_then_slice",
        },
    }


class _MapOnlyProvider:
    def read_active_solver_map(self, context, *, surface=None, subject_id=None):
        del context, subject_id
        return _map_payload(surface or "generic_solver")


class _FullProvider(_MapOnlyProvider):
    def read_operator_registry(
        self,
        context,
        *,
        registry_id,
        surface=None,
        subject_id=None,
    ):
        del context
        registry = _map_payload(surface or "generic_solver")["operator_registries"][0]
        return {
            **registry,
            "registry_id": registry_id,
            "surface": surface or "generic_solver",
            "subject_id": subject_id or "subject.primary",
            "snapshot_digest": "snapshot-digest-1",
            "integration_points": [
                {
                    "file_path": "solver/scheduler.py",
                    "symbol": "run",
                    "insert_policy": "append one registry item",
                    "required_telemetry_pattern": "telemetry.<mechanism>",
                }
            ],
        }

    def read_algorithm_slice(
        self,
        context,
        *,
        slice_id,
        surface=None,
        subject_id=None,
        max_chars=None,
    ):
        del context, max_chars
        return {
            "slice_id": slice_id,
            "surface": surface or "generic_solver",
            "subject_id": subject_id or "subject.primary",
            "snapshot_digest": "snapshot-digest-1",
            "file_path": "solver/operators.py",
            "symbols": ["alpha"],
            "slice_kind": "symbol_body",
            "content": "def alpha(state):\n    return state\n",
            "line_start": 10,
            "line_end": 11,
            "token_estimate": 8,
            "why_visible": "Provider allowlisted this operator body.",
            "source_policy_receipt": {
                "allowed": True,
                "reason": "provider allowlist",
                "remaining_budget": 100,
            },
        }


class _BadProvider:
    def read_active_solver_map(self, context, *, surface=None, subject_id=None):
        del context, surface, subject_id
        payload = _map_payload()
        payload["validation_cases"] = ["secret"]
        payload["frozen_metrics"] = {"secret": True}
        return payload


class _Adapter:
    def __init__(self, provider) -> None:
        self._provider = provider

    def active_solver_map_provider(self):
        return self._provider


def _context(provider=None) -> ProposalToolContext:
    adapter = _Adapter(provider) if provider is not None else None
    return ProposalToolContext(
        session_id="session-active-map",
        campaign_id="campaign-active-map",
        adapter=adapter,
    )


def test_active_solver_map_schema_is_generic_and_forbids_extra_fields() -> None:
    model = ActiveSolverMap.model_validate(_map_payload())
    schema_text = json.dumps(ActiveSolverMap.model_json_schema(), sort_keys=True)

    assert model.surface == "generic_solver"
    assert model.operator_registries[0].operators[0].symbol == "alpha"
    for token in ("cvrp", "vehicle", "customer", "route_cap", "depot"):
        assert token not in schema_text.lower()

    invalid = _map_payload()
    invalid["vehicle_count"] = 3
    with pytest.raises(ValidationError):
        ActiveSolverMap.model_validate(invalid)

    nested_invalid = _map_payload()
    nested_invalid["operator_registries"][0]["operators"][0]["customer_count"] = 2
    with pytest.raises(ValidationError):
        ActiveSolverMap.model_validate(nested_invalid)


def test_active_solver_map_tools_are_registered_and_return_receipts() -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(_FullProvider())

    allowed_tools = registry.allowed_tools(context)
    map_observation = registry.call(
        "context.read_active_solver_map",
        {"surface": "generic_solver"},
        context,
    )
    registry_observation = registry.call(
        "context.read_operator_registry",
        {"surface": "generic_solver", "registry_id": "registry.primary"},
        context,
    )
    slice_observation = registry.call(
        "context.read_algorithm_slice",
        {"surface": "generic_solver", "slice_id": "slice.alpha", "max_chars": 10},
        context,
    )

    assert "context.read_active_solver_map" in allowed_tools
    assert "context.read_operator_registry" in allowed_tools
    assert "context.read_algorithm_slice" in allowed_tools
    for observation in (map_observation, registry_observation, slice_observation):
        assert observation.is_error is False
        assert observation.structured_payload["available"] is True
        receipt = observation.structured_payload["read_receipt"]
        assert receipt["digest"]
        assert receipt["snapshot_digest"] == "snapshot-digest-1"
        assert receipt["available"] is True

    map_payload = map_observation.structured_payload
    assert map_payload["operator_registries"][0]["registry_id"] == "registry.primary"
    assert "source_policy" in map_payload
    assert registry_observation.structured_payload["operators"][0]["id"] == (
        "operator.alpha"
    )
    slice_payload = slice_observation.structured_payload
    assert slice_payload["content"] == "def alpha("
    assert slice_payload["content_digest"]
    assert slice_payload["read_receipt"]["content_digest"] == (
        slice_payload["content_digest"]
    )


def test_operator_registry_can_fallback_to_active_solver_map() -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(_MapOnlyProvider())

    observation = registry.call(
        "context.read_operator_registry",
        {"surface": "generic_solver", "registry_id": "registry.primary"},
        context,
    )
    slice_observation = registry.call(
        "context.read_algorithm_slice",
        {"surface": "generic_solver", "slice_id": "slice.alpha"},
        context,
    )

    assert observation.is_error is False
    assert observation.structured_payload["available"] is True
    assert observation.structured_payload["owner_symbol"] == "build_registry"
    assert observation.structured_payload["read_receipt"]["digest"]

    assert slice_observation.is_error is False
    assert slice_observation.structured_payload["available"] is False
    assert slice_observation.structured_payload["unavailable"]["reason"] == (
        "algorithm_slice_content_unavailable"
    )
    assert slice_observation.structured_payload["read_receipt"]["available"] is False


def test_missing_provider_returns_structured_unavailable() -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context()

    observation = registry.call("context.read_active_solver_map", {}, context)

    assert observation.is_error is False
    payload = observation.structured_payload
    assert payload["available"] is False
    assert payload["unavailable"]["reason"] == "active_solver_map_provider_unavailable"
    assert payload["read_receipt"]["available"] is False
    assert payload["read_receipt"]["digest"]


def test_invalid_provider_payload_does_not_expose_holdout_keys() -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(_BadProvider())

    observation = registry.call("context.read_active_solver_map", {}, context)
    rendered = json.dumps(observation.structured_payload, sort_keys=True)

    assert observation.is_error is False
    assert observation.structured_payload["available"] is False
    assert observation.structured_payload["unavailable"]["reason"] == (
        "active_solver_map_payload_invalid"
    )
    assert "validation_cases" not in rendered
    assert "frozen_metrics" not in rendered
    assert "secret" not in rendered


def test_active_solver_map_core_source_has_no_problem_specific_tokens() -> None:
    package_root = Path(__file__).resolve().parents[2] / "proposal" / "active_solver_map"
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(package_root.glob("*.py"))
    )

    for token in ("CVRP", "vehicle", "customer", "depot", "route_cap"):
        assert token not in source
