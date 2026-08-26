"""Thin composition hooks for private initial-screening declarations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, repr=False)
class _PreparedInitialScreeningDeclarations:
    provider_policy: Any | None
    problem_spec: Any | None
    runtime_problem_spec: Any
    runtime_adapter: Any
    runtime_operator_execute_signature: str | None
    runtime_experiment_protocol: Any

    def __repr__(self) -> str:
        return "_PreparedInitialScreeningDeclarations(<redacted>)"

    __str__ = __repr__


def _prepare_initial_screening_declarations(
    *,
    controls_request: Any,
    provider_request: Any,
    problem_request: Any,
    llm_client: Any,
    problem_spec: Any,
    adapter: Any,
    operator_execute_signature: str | None,
    experiment_protocol: Any,
) -> _PreparedInitialScreeningDeclarations:
    """Freeze every requested declaration before the controls root is created."""

    from scion.core.initial_screening_study_provider_policy import (
        _ERROR as _PROVIDER_POLICY_ERROR,
    )
    from scion.core.initial_screening_study_provider_policy import (
        _InitialScreeningProviderPolicyError,
        _prepare_initial_screening_provider_policy,
        _reject_reused_provider_client_without_marker,
    )

    _reject_reused_provider_client_without_marker(provider_request, llm_client)
    provider_inputs = None
    if provider_request is not None:
        if controls_request is None:
            raise _InitialScreeningProviderPolicyError(_PROVIDER_POLICY_ERROR)
        provider_inputs = _prepare_initial_screening_provider_policy(
            provider_request, llm_client
        )
    problem_inputs = None
    runtime_protocol = experiment_protocol
    if problem_request is not None:
        from scion.core.initial_screening_problem_spec import (
            _prepare_initial_screening_problem_spec,
            _problem_spec_protocol_input,
        )

        problem_inputs = _prepare_initial_screening_problem_spec(
            problem_request,
            controls_request,
            provider_request,
            problem_spec,
            adapter,
            operator_execute_signature,
        )
        runtime_protocol = _problem_spec_protocol_input(
            experiment_protocol, problem_inputs
        )
        problem_spec = problem_inputs.problem_spec
        adapter = problem_inputs.adapter
        operator_execute_signature = problem_inputs.operator_execute_signature
    return _PreparedInitialScreeningDeclarations(
        provider_policy=provider_inputs,
        problem_spec=problem_inputs,
        runtime_problem_spec=problem_spec,
        runtime_adapter=adapter,
        runtime_operator_execute_signature=operator_execute_signature,
        runtime_experiment_protocol=runtime_protocol,
    )


def _publish_initial_screening_declarations(
    prepared: _PreparedInitialScreeningDeclarations,
    controls_setup: Any,
) -> _PreparedInitialScreeningDeclarations:
    """Publish provider second and problem declaration third."""

    provider_inputs = prepared.provider_policy
    problem_inputs = prepared.problem_spec
    if provider_inputs is not None:
        from scion.core.initial_screening_study_provider_policy import (
            _publish_initial_screening_provider_policy,
        )

        provider_inputs = _publish_initial_screening_provider_policy(
            provider_inputs, controls_setup.runtime_inputs.publication
        )
    if problem_inputs is not None:
        from scion.core.initial_screening_problem_spec import (
            _publish_initial_screening_problem_spec,
        )

        problem_inputs = _publish_initial_screening_problem_spec(
            problem_inputs,
            controls_setup.runtime_inputs,
            provider_inputs,
        )
    return _PreparedInitialScreeningDeclarations(
        provider_policy=provider_inputs,
        problem_spec=problem_inputs,
        runtime_problem_spec=prepared.runtime_problem_spec,
        runtime_adapter=prepared.runtime_adapter,
        runtime_operator_execute_signature=(
            prepared.runtime_operator_execute_signature
        ),
        runtime_experiment_protocol=prepared.runtime_experiment_protocol,
    )


def _install_initial_screening_declaration_carriers(
    owner: Any,
    prepared: _PreparedInitialScreeningDeclarations,
) -> None:
    """Install only carriers that were explicitly requested and published."""

    if prepared.provider_policy is not None:
        owner._initial_screening_provider_policy_active = True
        owner._initial_screening_provider_policy = prepared.provider_policy
    if prepared.problem_spec is not None:
        owner._initial_screening_problem_spec_active = True
        owner._initial_screening_problem_spec = prepared.problem_spec


def _finalize_initial_screening_declarations(
    owner: Any,
    controls_setup: Any,
    prepared: _PreparedInitialScreeningDeclarations,
) -> None:
    """Register controls/problem first and install provider policy last."""

    if controls_setup is not None:
        from scion.core.initial_screening_study_controls import (
            _register_initial_screening_controls_owner,
        )

        _register_initial_screening_controls_owner(
            owner,
            owner._initial_screening_study_controls,
        )
    if prepared.problem_spec is not None:
        from scion.core.initial_screening_problem_spec import (
            _register_initial_screening_problem_spec_owner,
        )

        _register_initial_screening_problem_spec_owner(owner, prepared.problem_spec)
    if prepared.provider_policy is not None:
        from scion.core.initial_screening_study_provider_policy import (
            _finalize_initial_screening_provider_policy,
        )

        _finalize_initial_screening_provider_policy(owner, prepared.provider_policy)
