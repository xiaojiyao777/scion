from __future__ import annotations

import json
from pathlib import Path

import pytest

from scion.problems.warehouse_delivery.w3_root_selection import (
    RootSelectedCandidateAuthority,
    WarehouseW3RootSelectionError,
    WarehouseW3RootSelectionReceipt,
    WarehouseW3SelectionReplayInputs,
    derive_root_selection_effect_authority_sha256,
    derive_root_staging_effect_authority_sha256,
    derive_root_staging_import_authority_sha256,
    selection_replay_inputs_from_chain,
    verify_w3_selected_candidate_chain,
)
from scion.runtime.execution.external_linux import pin_absolute_directory
from scion.runtime.execution.external_installation import (
    RootPhase,
    RootPhaseIntentReceipt,
    RootPhaseReceipt,
)
from scion.tests.unit.problems.warehouse_delivery.test_w3_environment_receipts import (
    _semantic,
    semantic_inputs,
)
from scion.tests.unit.problems.warehouse_delivery.test_w3_root_installation import (
    _launch_pair,
    _sealed_store,
    _selection_receipt,
    _staging_bundle,
    _tree_import,
)


def _canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()


def _bundle(semantic_inputs: dict[str, object]):
    semantic = _semantic(semantic_inputs)
    sealed = _sealed_store()
    authority, installation = _launch_pair(
        sealed,
        semantic.generic_receipt_sha256,
    )
    candidate, ingress, verification, staged = _staging_bundle(
        authority=authority,
        installation=installation,
        sealed=sealed,
        semantic=semantic,
        imported=_tree_import(),
    )
    generic = _selection_receipt(candidate, staged)
    selected = WarehouseW3RootSelectionReceipt._create_for_test(
        selection=generic,
        staged_candidate=staged,
    )
    k0_intent = RootPhaseIntentReceipt.create(
        launch_id=selected.launch_id,
        phase=RootPhase.ROOT_STAGING_IMPORTED,
        predecessor_sha256=(),
        effect_authority_sha256=derive_root_staging_effect_authority_sha256(
            verification.candidate_gate_closure,
            ingress,
            staged.tree_import,
        ),
    )
    k0 = RootPhaseReceipt.create(
        intent=k0_intent,
        effect_sha256=staged.raw_sha256,
    )
    k1_intent = RootPhaseIntentReceipt.create(
        launch_id=selected.launch_id,
        phase=RootPhase.CANDIDATE_SELECTED,
        predecessor_sha256=(k0.raw_sha256,),
        effect_authority_sha256=derive_root_selection_effect_authority_sha256(selected),
    )
    k1 = RootPhaseReceipt.create(
        intent=k1_intent,
        effect_sha256=selected.raw_sha256,
    )
    return selected, k0_intent, k0, k1_intent, k1


def _inputs(
    selected: WarehouseW3RootSelectionReceipt,
    k0_intent: RootPhaseIntentReceipt,
    k0: RootPhaseReceipt,
    k1_intent: RootPhaseIntentReceipt,
    k1: RootPhaseReceipt,
    **overrides: bytes,
) -> WarehouseW3SelectionReplayInputs:
    staged = selected.staged_candidate
    verification = staged.root_staging_verification
    values = {
        "candidate_gate_closure_raw": (verification.candidate_gate_closure.raw),
        "candidate_gate_ingress_fact_raw": (staged.candidate_gate_ingress.raw),
        "tree_import_raw": staged.tree_import.raw,
        "candidate_receipt_raw": verification.candidate_receipt.raw,
        "source_receipt_raw": verification.source_receipt.raw,
        "sealed_store_receipt_raw": verification.sealed_store_receipt.raw,
        "environment_receipt_raw": verification.environment_receipt.raw,
        "authority_raw": verification.authority.raw,
        "installation_raw": verification.installation.raw,
        "selection_intent_raw": verification.selection_intent.raw,
        "selection_commit_raw": verification.selection_commit.raw,
        "root_staging_verification_raw": verification.raw,
        "staged_candidate_raw": staged.raw,
        "generic_selection_raw": selected.selection.raw,
        "root_selection_raw": selected.raw,
        "root_staging_intent_raw": k0_intent.raw,
        "root_staging_receipt_raw": k0.raw,
        "candidate_selected_intent_raw": k1_intent.raw,
        "candidate_selected_receipt_raw": k1.raw,
    }
    values.update(overrides)
    return WarehouseW3SelectionReplayInputs(**values)


def test_root_selection_round_trip_and_deep_k0_k1_replay(
    semantic_inputs: dict[str, object],
) -> None:
    selected, k0_intent, k0, k1_intent, k1 = _bundle(semantic_inputs)

    assert (
        WarehouseW3RootSelectionReceipt.from_bytes(
            selected.raw,
            selection=selected.selection,
            staged_candidate=selected.staged_candidate,
        )
        == selected
    )
    chain = verify_w3_selected_candidate_chain(
        _inputs(selected, k0_intent, k0, k1_intent, k1)
    )

    assert chain.root_selection == selected
    assert chain.root_staging_receipt == k0
    assert chain.candidate_selected_receipt == k1
    assert chain.closure.raw_sha256 == selected.candidate_gate_closure_sha256
    assert (
        verify_w3_selected_candidate_chain(selection_replay_inputs_from_chain(chain))
        == chain
    )


def test_k0_authority_is_fully_known_before_tree_import(
    semantic_inputs: dict[str, object],
) -> None:
    selected, k0_intent, _k0, _k1_intent, _k1 = _bundle(semantic_inputs)
    staged = selected.staged_candidate

    assert k0_intent.effect_authority_sha256 == (
        derive_root_staging_import_authority_sha256(
            staged.root_staging_verification.candidate_gate_closure,
            staged.candidate_gate_ingress,
            staging_leaf=staged.tree_import.staging_leaf,
            target_uid=0,
            target_gid=0,
        )
    )
    assert k0_intent.effect_authority_sha256 == (
        derive_root_staging_effect_authority_sha256(
            staged.root_staging_verification.candidate_gate_closure,
            staged.candidate_gate_ingress,
            staged.tree_import,
        )
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("staging_leaf", "../other", "leaf differs"),
        ("target_uid", 1001, "producer differs"),
        ("target_gid", 1001, "producer differs"),
    ),
)
def test_k0_pre_effect_authority_rejects_non_root_plan(
    semantic_inputs: dict[str, object],
    field: str,
    value: object,
    message: str,
) -> None:
    selected, _k0_intent, _k0, _k1_intent, _k1 = _bundle(semantic_inputs)
    staged = selected.staged_candidate
    arguments = {
        "staging_leaf": staged.tree_import.staging_leaf,
        "target_uid": 0,
        "target_gid": 0,
    }
    arguments[field] = value

    with pytest.raises(WarehouseW3RootSelectionError, match=message):
        derive_root_staging_import_authority_sha256(
            staged.root_staging_verification.candidate_gate_closure,
            staged.candidate_gate_ingress,
            **arguments,
        )


def test_root_selection_construction_is_root_gated(
    semantic_inputs: dict[str, object],
) -> None:
    selected, _k0_intent, _k0, _k1_intent, _k1 = _bundle(semantic_inputs)

    with pytest.raises(PermissionError, match="effective UID zero"):
        WarehouseW3RootSelectionReceipt.create(
            selection=selected.selection,
            staged_candidate=selected.staged_candidate,
        )


def test_root_selected_authority_reopens_one_fixed_selection_file(
    tmp_path: Path,
    semantic_inputs: dict[str, object],
) -> None:
    selected, k0_intent, k0, k1_intent, k1 = _bundle(semantic_inputs)
    inputs = _inputs(selected, k0_intent, k0, k1_intent, k1)
    parent = tmp_path / "selections"
    parent.mkdir()
    selection_path = parent / f"{selected.selection_key}.json"
    selection_path.write_bytes(selected.raw)
    selection_path.chmod(0o444)

    with (
        pin_absolute_directory(str(parent)) as pinned,
        RootSelectedCandidateAuthority._acquire_for_test(
            pinned,
            inputs,
        ) as authority,
    ):
        assert authority.chain.root_selection == selected


@pytest.mark.parametrize(
    "field",
    (
        "staged_candidate_sha256",
        "root_staging_verification_sha256",
        "candidate_gate_ingress_fact_sha256",
        "candidate_gate_closure_sha256",
        "tree_import_sha256",
        "preparation_intent_sha256",
        "preparation_commit_sha256",
    ),
)
def test_root_selection_rejects_each_explicit_producer_hash_drift(
    semantic_inputs: dict[str, object],
    field: str,
) -> None:
    selected, _k0_intent, _k0, _k1_intent, _k1 = _bundle(semantic_inputs)
    value = json.loads(selected.raw)
    value[field] = "0" * 64

    with pytest.raises(
        WarehouseW3RootSelectionError,
        match="producer binding differs",
    ):
        WarehouseW3RootSelectionReceipt.from_bytes(
            _canonical(value),
            selection=selected.selection,
            staged_candidate=selected.staged_candidate,
        )


@pytest.mark.parametrize("phase", ("K0", "K1"))
def test_selected_chain_rejects_phase_effect_drift(
    semantic_inputs: dict[str, object],
    phase: str,
) -> None:
    selected, k0_intent, k0, k1_intent, k1 = _bundle(semantic_inputs)
    target = k0 if phase == "K0" else k1
    value = json.loads(target.raw)
    value["effect_sha256"] = "0" * 64
    overrides = {
        (
            "root_staging_receipt_raw"
            if phase == "K0"
            else "candidate_selected_receipt_raw"
        ): _canonical(value)
    }

    with pytest.raises(
        WarehouseW3RootSelectionError,
        match="transaction differs",
    ):
        verify_w3_selected_candidate_chain(
            _inputs(
                selected,
                k0_intent,
                k0,
                k1_intent,
                k1,
                **overrides,
            )
        )


@pytest.mark.parametrize("phase", ("K0", "K1"))
def test_selected_chain_rejects_phase_effect_authority_drift(
    semantic_inputs: dict[str, object],
    phase: str,
) -> None:
    selected, k0_intent, k0, k1_intent, k1 = _bundle(semantic_inputs)
    target = k0_intent if phase == "K0" else k1_intent
    value = json.loads(target.raw)
    value["effect_authority_sha256"] = "0" * 64
    overrides = {
        (
            "root_staging_intent_raw"
            if phase == "K0"
            else "candidate_selected_intent_raw"
        ): _canonical(value)
    }

    with pytest.raises(
        WarehouseW3RootSelectionError,
        match="transaction differs",
    ):
        verify_w3_selected_candidate_chain(
            _inputs(
                selected,
                k0_intent,
                k0,
                k1_intent,
                k1,
                **overrides,
            )
        )


def test_selected_chain_rejects_ingress_closure_substitution(
    semantic_inputs: dict[str, object],
) -> None:
    selected, k0_intent, k0, k1_intent, k1 = _bundle(semantic_inputs)
    ingress = json.loads(selected.staged_candidate.candidate_gate_ingress.raw)
    ingress["closure_sha256"] = "0" * 64

    with pytest.raises(
        WarehouseW3RootSelectionError,
        match="producer replay failed",
    ):
        verify_w3_selected_candidate_chain(
            _inputs(
                selected,
                k0_intent,
                k0,
                k1_intent,
                k1,
                candidate_gate_ingress_fact_raw=_canonical(ingress),
            )
        )


def test_selected_chain_rejects_k1_predecessor_not_exact_k0(
    semantic_inputs: dict[str, object],
) -> None:
    selected, k0_intent, k0, k1_intent, k1 = _bundle(semantic_inputs)
    value = json.loads(k1_intent.raw)
    value["predecessor_sha256"] = ["0" * 64]

    with pytest.raises(
        WarehouseW3RootSelectionError,
        match="transaction differs",
    ):
        verify_w3_selected_candidate_chain(
            _inputs(
                selected,
                k0_intent,
                k0,
                k1_intent,
                k1,
                candidate_selected_intent_raw=_canonical(value),
            )
        )
