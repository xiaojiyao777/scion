from __future__ import annotations

import hashlib
from pathlib import Path

import scion.problems.warehouse_delivery.w3_candidate_gate as gate_module
from scion.problems.warehouse_delivery.w3_candidate_gate import (
    CandidateAbsenceFacts,
    CandidateAbsenceObservation,
    CandidateCompositionInspection,
    CandidateGateClosureBundle,
    CandidateGateReceipt,
    CandidateSimulatedRelocationRef,
)
from scion.problems.warehouse_delivery.w3_composition import (
    EXPECTED_SOURCE_TREE_IDENTITY_SHA256,
)
from scion.problems.warehouse_delivery.w3_environment_receipts import (
    EnvironmentProbeFact,
    WarehouseEnvironmentContentReceipt,
)
from scion.problems.warehouse_delivery.w3_installation import (
    CandidateRootIdentity,
    CandidateVerificationReceipt,
    derive_launch_id,
)
from scion.problems.warehouse_delivery.w3_wheel import OfflineDoubleWheelReceipt
from scion.runtime.execution.environment_integrity import EnvironmentContentReceipt


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8", "strict")).hexdigest()


def _probe(
    semantic: WarehouseEnvironmentContentReceipt,
    *,
    phase: str,
    root: Path,
) -> EnvironmentProbeFact:
    native_paths = tuple(
        sorted(
            root / item.path
            for item in semantic.evidence.import_table
            if item.kind == "native_extension"
        )
    )
    shared_paths = tuple(
        sorted(
            Path(item.path)
            for item in semantic.evidence.import_table
            if item.kind == "shared_library"
        )
    )
    return EnvironmentProbeFact.create(
        phase=phase,
        content_receipt_sha256=semantic.raw_sha256,
        environment_root=root,
        sys_executable=root / "bin/python",
        sys_prefix=root,
        sys_path=(root / "lib/python3.12/site-packages",),
        import_table_sha256=semantic.import_table_sha256,
        loaded_import_table=semantic.evidence.import_table,
        native_loaded_paths=native_paths,
        shared_library_paths=shared_paths,
        dbus_acquired=True,
        dbus_unique_name=":1.42",
        dispatcher_argv=(
            str(root / "bin/python"),
            "-m",
            "scion.tools.scion_w3_tool",
            "run",
        ),
    )


def make_candidate_gate_closure(
    *,
    candidate: CandidateVerificationReceipt,
    candidate_root: Path,
    accepted_root: Path,
    nonce: str,
    manifest_sha256: str,
    wheel: OfflineDoubleWheelReceipt,
    semantic: WarehouseEnvironmentContentReceipt,
    environment: EnvironmentContentReceipt,
    accepted_root_identity: CandidateRootIdentity | None = None,
    accepted_root_inventory_sha256: str | None = None,
    accepted_root_inventory_count: int | None = None,
) -> CandidateGateClosureBundle:
    candidate_probe = _probe(
        semantic,
        phase="candidate",
        root=candidate_root / "environment",
    )
    launch_id = derive_launch_id(candidate.authority_sha256, nonce)
    simulated_root = (
        candidate_root.parent
        / ".simulated-final"
        / "var"
        / "lib"
        / "scion"
        / "environments"
        / "w3"
        / environment.raw_sha256
    )
    simulated_probe = _probe(
        semantic,
        phase="simulated_final",
        root=simulated_root,
    )
    relocation = CandidateSimulatedRelocationRef.create(
        evidence_receipt_sha256=_sha(f"simulated-relocation:{candidate.selection_key}"),
        selection_key=candidate.selection_key,
        launch_id=launch_id,
        authority_sha256=candidate.authority_sha256,
        installation_sha256=candidate.installation_sha256,
        semantic_environment=semantic,
        candidate_probe=candidate_probe,
        simulated_final_probe=simulated_probe,
    )
    bindings = {
        "candidate_verification_sha256": candidate.raw_sha256,
        "double_wheel_receipt_sha256": wheel.raw_sha256,
        "semantic_environment_receipt_sha256": semantic.raw_sha256,
        "candidate_probe_sha256": candidate_probe.raw_sha256,
        "simulated_final_probe_sha256": simulated_probe.raw_sha256,
        "simulated_relocation_ref_sha256": relocation.raw_sha256,
        "simulated_relocation_evidence_sha256": (relocation.evidence_receipt_sha256),
    }
    subjects = gate_module._derived_absence_subjects(
        accepted_root=str(accepted_root),
        launch_id=launch_id,
        nonce=nonce,
        authority_sha256=candidate.authority_sha256,
        installation_sha256=candidate.installation_sha256,
        environment_receipt_sha256=candidate.environment_receipt_sha256,
    )
    observations = tuple(
        CandidateAbsenceObservation(
            role=role,
            subject=subjects[role],
            observation_sha256=gate_module._absence_observation_sha256(
                role=role,
                subject=subjects[role],
                candidate_verification_sha256=candidate.raw_sha256,
                double_wheel_receipt_sha256=wheel.raw_sha256,
                semantic_environment_receipt_sha256=semantic.raw_sha256,
                simulated_relocation_ref_sha256=relocation.raw_sha256,
            ),
            state="ABSENT",
        )
        for role in gate_module._ABSENCE_ROLES
    )
    absence = CandidateAbsenceFacts.create(
        selection_key=candidate.selection_key,
        launch_id=launch_id,
        nonce=nonce,
        authority_sha256=candidate.authority_sha256,
        installation_sha256=candidate.installation_sha256,
        environment_receipt_sha256=candidate.environment_receipt_sha256,
        accepted_root=accepted_root,
        **bindings,
        observations=observations,
    )
    if accepted_root_identity is None:
        accepted_identity, inventory_sha256, inventory_count = (
            gate_module._readonly_tree_inventory(accepted_root)
        )
    else:
        accepted_identity = accepted_root_identity
        inventory_sha256 = (
            _sha(f"accepted-inventory:{accepted_root}")
            if accepted_root_inventory_sha256 is None
            else accepted_root_inventory_sha256
        )
        inventory_count = (
            0
            if accepted_root_inventory_count is None
            else accepted_root_inventory_count
        )
    inspection = CandidateCompositionInspection.create(
        selection_key=candidate.selection_key,
        launch_id=launch_id,
        nonce=nonce,
        authority_sha256=candidate.authority_sha256,
        installation_sha256=candidate.installation_sha256,
        accepted_root=accepted_root,
        accepted_root_identity=accepted_identity,
        accepted_root_inventory_sha256=inventory_sha256,
        accepted_root_inventory_count=inventory_count,
        **bindings,
        manifest_sha256=manifest_sha256,
        source_tree_identity_sha256=EXPECTED_SOURCE_TREE_IDENTITY_SHA256,
        state="COMPOSITION_READY_EXTERNAL_INSTALLATION_REQUIRED",
        external_installation_required=True,
        cell_count=43,
        job_count=172,
        formal_jobs_started=0,
        formal_execution_authorized=False,
        filesystem_mutated=False,
        absence_facts=absence,
    )
    gate = CandidateGateReceipt.create(
        candidate=candidate,
        nonce=nonce,
        candidate_root=candidate_root,
        candidate_root_identity=candidate.candidate_root_identity,
        double_wheel=wheel,
        semantic_environment=semantic,
        environment_content=environment,
        candidate_probe=candidate_probe,
        simulated_final_probe=simulated_probe,
        simulated_relocation=relocation,
        inspection=inspection,
        absence_facts=absence,
    )
    return CandidateGateClosureBundle.create(
        gate=gate,
        candidate_verification=candidate,
        double_wheel=wheel,
        semantic_environment=semantic,
        environment_content=environment,
        candidate_probe=candidate_probe,
        simulated_final_probe=simulated_probe,
        simulated_relocation=relocation,
        inspection=inspection,
        absence_facts=absence,
    )


__all__ = ["make_candidate_gate_closure"]
