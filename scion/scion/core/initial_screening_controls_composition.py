"""Construction-time implementation for private initial-screening controls."""

from __future__ import annotations

from typing import Any

from scion.contract.gate import ContractGate
from scion.core.models import ChampionState
from scion.core.problem_runtime import ProblemRuntime
from scion.core.production_boundary import validate_production_campaign_boundary
from scion.core.verification_factory import CampaignVerificationFactory
from scion.verification.development import (
    declared_development_problem_package_paths,
    declared_development_suites,
    declared_development_workspace_paths,
    validate_development_closure_boundary,
)


def _prepare_initial_screening_controls_setup_impl(
    *,
    owner: Any,
    request: Any,
    problem_spec: Any,
    protocol_config: Any,
    split_manifest: Any,
    seed_ledger: Any,
    champion: Any,
    campaign_dir: str,
    experiment_protocol: Any,
    adapter: Any,
    verification_gate: Any | None,
    operator_execute_signature: str | None,
    research_input: Any | None,
    research_history: Any,
    resource_envelope: Any | None,
    code_research_limits: Any | None,
    qualification_only: Any | None,
    problem_declaration: Any | None = None,
) -> Any:
    """Publish and return one fixed-error, config-subset runtime setup."""

    from scion.core.campaign import CampaignManager
    from scion.core.campaign_composition import (
        _initial_screening_protected_roots,
        _InitialScreeningControlsSetup,
    )
    from scion.core.initial_screening_study_controls import (
        _ERROR,
        _bind_controls_publication,
        _InitialScreeningStudyControlsError,
        _prepare_initial_screening_runtime_inputs,
        _write_initial_screening_study_controls,
    )

    failed = False
    result: Any | None = None
    try:
        if type(owner) is not CampaignManager:
            raise TypeError
        if verification_gate is not None:
            raise ValueError
        runtime_inputs = _prepare_initial_screening_runtime_inputs(
            request=request,
            qualification=qualification_only,
            code_research_limits=code_research_limits,
            resource_envelope=resource_envelope,
            protocol_config=protocol_config,
            split_manifest=split_manifest,
            seed_ledger=seed_ledger,
            experiment_protocol=experiment_protocol,
            campaign_dir=campaign_dir,
        )
        frozen_config = runtime_inputs.protocol_config
        frozen_manifest = runtime_inputs.split_manifest
        frozen_ledger = runtime_inputs.seed_ledger
        frozen_protocol = runtime_inputs.experiment_protocol
        if type(champion) is not ChampionState:
            raise TypeError
        champion_storage = vars(champion)
        if type(champion_storage) is not dict or any(
            type(key) is not str for key in champion_storage
        ):
            raise TypeError
        champion_snapshot_path = champion_storage.get("code_snapshot_path")
        if (
            type(champion_snapshot_path) is not str
            or not champion_snapshot_path
            or "\x00" in champion_snapshot_path
        ):
            raise TypeError
        development_suites = declared_development_suites(problem_spec)
        development_workspace_paths = declared_development_workspace_paths(problem_spec)
        development_problem_package_paths = declared_development_problem_package_paths(
            problem_spec
        )
        validate_development_closure_boundary(
            problem_spec=problem_spec,
            suites=development_suites,
            workspace_paths=development_workspace_paths,
            problem_package_paths=development_problem_package_paths,
            split_manifest=frozen_manifest,
            champion_root=champion_snapshot_path,
        )
        problem_runtime = ProblemRuntime(
            problem_spec=problem_spec,
            adapter=adapter,
            split_manifest=frozen_manifest,
            seed_ledger=frozen_ledger,
            research_input=research_input,
            research_history=research_history,
            development_suites=development_suites,
        )
        contract_gate = ContractGate(
            problem_spec,
            operator_execute_signature=operator_execute_signature,
            adapter=adapter,
            champion_snapshot_provider=lambda: getattr(
                getattr(owner, "_champion", champion),
                "code_snapshot_path",
                None,
            ),
        )
        frozen_protocol.set_problem_adapter(adapter)
        installed_verification_gate = CampaignVerificationFactory.build(
            problem_spec=problem_spec,
            verification_gate=verification_gate,
            experiment_protocol=frozen_protocol,
            campaign_dir=campaign_dir,
            adapter=adapter,
            operator_execute_signature=operator_execute_signature,
        )
        validate_production_campaign_boundary(
            problem_spec=problem_spec,
            experiment_protocol=frozen_protocol,
            adapter=adapter,
            split_manifest=frozen_manifest,
            seed_ledger=frozen_ledger,
            verification_gate=installed_verification_gate,
        )
        protected_roots = _initial_screening_protected_roots(
            problem_spec=problem_spec,
            champion=champion,
            split_manifest=frozen_manifest,
            development_suites=development_suites,
        )
        if problem_declaration is not None:
            from scion.core.initial_screening_problem_spec_validation import (
                _validate_problem_spec_prepublication,
            )

            _validate_problem_spec_prepublication(
                problem_declaration,
                (
                    runtime_inputs,
                    problem_runtime,
                    contract_gate,
                    frozen_protocol,
                    installed_verification_gate,
                ),
            )
        publication = _write_initial_screening_study_controls(
            campaign_dir,
            runtime_inputs.payload_bytes,
            protected_roots=protected_roots,
        )
        runtime_inputs = _bind_controls_publication(runtime_inputs, publication)
        result = _InitialScreeningControlsSetup(
            code_research_limits=runtime_inputs.code_research_limits,
            resource_envelope=runtime_inputs.resource_envelope,
            qualification=runtime_inputs.qualification,
            protocol_config=frozen_config,
            split_manifest=frozen_manifest,
            seed_ledger=frozen_ledger,
            experiment_protocol=frozen_protocol,
            problem_runtime=problem_runtime,
            contract_gate=contract_gate,
            verification_gate=installed_verification_gate,
            development_suites=development_suites,
            development_workspace_paths=development_workspace_paths,
            development_problem_package_paths=development_problem_package_paths,
            runtime_inputs=runtime_inputs,
        )
    except Exception:  # noqa: BLE001 - sanitize the private opt-in boundary
        failed = True
    if failed or result is None:
        raise _InitialScreeningStudyControlsError(_ERROR)
    return result
