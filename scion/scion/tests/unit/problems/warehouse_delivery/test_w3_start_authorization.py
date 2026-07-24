from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest

import scion.problems.warehouse_delivery.w3_start_authorization as start_authorization_module
from scion.problems.warehouse_delivery.w3_start_authorization import (
    ProspectiveStartAuthorizationIntent,
    WarehouseW3StartAuthorizationError,
    _bind_start_authorization_for_test,
    bind_start_authorization,
)
from scion.problems.warehouse_delivery.w3_installed_replay import (
    RootInstalledAcceptanceAuthority,
    WarehouseW3InstalledAcceptanceBundle,
    WarehouseW3InstalledReplayInputs,
    verify_w3_installed_replay,
)
from scion.problems.warehouse_delivery.w3_root_selection import (
    RootSelectedCandidateAuthority,
    WarehouseW3RootSelectionError,
)
from scion.problems.warehouse_delivery.w3_root_installation import (
    WAREHOUSE_W3_PRESTART_EVIDENCE_SCHEMA,
    WarehouseW3PreStartEvidence,
)
from scion.runtime.execution.external_installation import (
    INSTALL_PHASES,
    InstalledAcceptance,
    ReceiptDagError,
    RootPhaseIntentReceipt,
    RootPhaseReceipt,
    StartAuthorizationReceipt,
)
from scion.runtime.execution.external_linux import pin_absolute_directory
from scion.tests.unit.problems.warehouse_delivery.test_w3_environment_receipts import (
    semantic_inputs,
)
from scion.tests.unit.problems.warehouse_delivery.test_w3_root_installation import (
    _evidence_kwargs,
    _prestart_inputs,
)
from scion.tests.unit.problems.warehouse_delivery.test_w3_root_selection import (
    _inputs as _selection_replay_inputs,
)


def _prospective_raw() -> bytes:
    path = (
        Path(__file__).parents[5]
        / "docs"
        / "experiments"
        / "v0.4"
        / "v04-w3-prospective-start-authorization-intent-20260723.json"
    )
    return path.read_bytes()


def _installed_bundle(
    semantic_inputs: dict[str, object],
    *,
    problem_state_schema: str = WAREHOUSE_W3_PRESTART_EVIDENCE_SCHEMA,
):
    values = _prestart_inputs(semantic_inputs)
    evidence = WarehouseW3PreStartEvidence.create(**_evidence_kwargs(values))
    phase_intents = list(values["phase_intents"])
    phase_receipts = list(values["phase_receipts"])
    instances_loaded = RootPhaseReceipt.create(
        intent=phase_intents[-1],
        effect_sha256=evidence.raw_sha256,
    )
    phase_receipts.append(instances_loaded)
    installed = InstalledAcceptance.create(
        launch_id=values["installation"].launch_id,
        authority_sha256=values["authority"].authority_sha256,
        installation_sha256=values["installation"].installation_sha256,
        phase_intents=tuple(phase_intents),
        phase_receipts=tuple(phase_receipts),
        problem_state_schema=problem_state_schema,
        problem_state_sha256=evidence.raw_sha256,
    )
    accepted_intent = RootPhaseIntentReceipt.create(
        launch_id=installed.launch_id,
        phase=INSTALL_PHASES[-1],
        predecessor_sha256=(instances_loaded.raw_sha256,),
        effect_authority_sha256=installed.raw_sha256,
    )
    accepted_receipt = RootPhaseReceipt.create(
        intent=accepted_intent,
        effect_sha256=installed.raw_sha256,
    )
    phase_intents.append(accepted_intent)
    phase_receipts.append(accepted_receipt)
    selected = values["selection"]
    replay = _selection_replay_inputs(
        selected,
        phase_intents[0],
        phase_receipts[0],
        phase_intents[1],
        phase_receipts[1],
    )
    return (
        values,
        replay,
        evidence,
        installed,
        tuple(phase_intents),
        tuple(phase_receipts),
    )


def _installed_replay_inputs(
    values: dict[str, object],
    evidence: WarehouseW3PreStartEvidence,
    installed: InstalledAcceptance,
    intents: tuple[RootPhaseIntentReceipt, ...],
    receipts: tuple[RootPhaseReceipt, ...],
) -> WarehouseW3InstalledReplayInputs:
    dependencies = values["_replay_dependencies"]
    return WarehouseW3InstalledReplayInputs(
        phase_intent_raws=tuple(item.raw for item in intents),
        phase_receipt_raws=tuple(item.raw for item in receipts),
        stores_published_raw=values["stores_published"].raw,
        sealed_publication_raw=dependencies["sealed_publication"].raw,
        environment_publication_raw=(dependencies["environment_publication"].raw),
        environment_relocation_raw=(dependencies["environment_relocation"].raw),
        authority_published_raw=values["authority_published"].raw,
        authority_publication_raw=dependencies["authority_publication"].raw,
        installation_publication_raw=(dependencies["installation_publication"].raw),
        nonce_directory_raw=dependencies["nonce_directory"].raw,
        projection_raw=values["projection"].raw,
        projection_parent_raws=tuple(
            item.raw for item in dependencies["projection_parent_chain"]
        ),
        run_mount_raw=dependencies["run_mount"].raw,
        sealed_mount_raw=dependencies["sealed_mount"].raw,
        environment_mount_raw=dependencies["environment_mount"].raw,
        nonce_claims_mount_raw=dependencies["nonce_claims_mount"].raw,
        projection_authority_publication_raw=(
            dependencies["projection_authority_publication"].raw
        ),
        projection_installation_publication_raw=(
            dependencies["projection_installation_publication"].raw
        ),
        run_template_raw=dependencies["run_template_raw"],
        close_template_raw=dependencies["close_template_raw"],
        run_unit_publication_raw=dependencies["run_publication"].raw,
        close_unit_publication_raw=dependencies["close_publication"].raw,
        unit_publication_raw=values["unit_publication"].raw,
        configured_pair_readback_raw=(dependencies["configured_readback"].raw),
        manager_reload_raw=values["manager_reload"].raw,
        loaded_manager_raw=values["loaded_manager"].raw,
        environment_rehash_raw=values["environment_rehash"].raw,
        dry_root_raw=values["dry_root"].raw,
        prestart_absence_raw=values["prestart_absence"].raw,
        runtime_account_raw=values["runtime_account"].raw,
        prestart_evidence_raw=evidence.raw,
        installed_acceptance_raw=installed.raw,
    )


def test_prospective_intent_binds_only_after_deep_k0_selection_replay(
    semantic_inputs: dict[str, object],
) -> None:
    values, replay, evidence, installed, intents, receipts = _installed_bundle(
        semantic_inputs
    )
    prospective = ProspectiveStartAuthorizationIntent.from_bytes(_prospective_raw())

    authorization = _bind_start_authorization_for_test(
        prospective,
        selection_replay_inputs=replay,
        prestart_evidence=evidence,
        installed_acceptance=installed,
        phase_intents=intents,
        phase_receipts=receipts,
        recorded_at_utc="2026-07-23T17:00:00Z",
        unit=values["installation"].run_unit,
    )

    assert StartAuthorizationReceipt.from_bytes(authorization.raw) == authorization
    assert authorization.user_statement == prospective.statement
    assert authorization.root_selection_sha256 == (values["selection"].raw_sha256)
    assert authorization.installed_acceptance_sha256 == installed.raw_sha256


def test_installed_acceptance_deep_replay_closes_k0_through_k8(
    semantic_inputs: dict[str, object],
) -> None:
    values, replay, evidence, installed, intents, receipts = _installed_bundle(
        semantic_inputs
    )

    chain = verify_w3_installed_replay(
        _installed_replay_inputs(
            values,
            evidence,
            installed,
            intents,
            receipts,
        ),
        replay,
    )

    assert chain.installed_acceptance == installed
    assert chain.prestart_evidence == evidence
    assert chain.loaded_manager == values["loaded_manager"]


def test_public_start_authorization_requires_root_selected_authority(
    tmp_path: Path,
    semantic_inputs: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values, replay, evidence, installed, intents, receipts = _installed_bundle(
        semantic_inputs
    )
    installed_replay = _installed_replay_inputs(
        values,
        evidence,
        installed,
        intents,
        receipts,
    )
    installed_bundle = WarehouseW3InstalledAcceptanceBundle._create_for_test(
        selection_replay_inputs=replay,
        installed_replay_inputs=installed_replay,
    )
    selected = values["selection"]
    parent = tmp_path / "selections"
    parent.mkdir()
    path = parent / f"{selected.selection_key}.json"
    path.write_bytes(selected.raw)
    path.chmod(0o444)
    install = tmp_path / "install"
    install.mkdir()
    replay_path = install / "INSTALLED_REPLAY.v1.json"
    replay_path.write_bytes(installed_bundle.raw)
    replay_path.chmod(0o444)

    with (
        pin_absolute_directory(str(parent)) as pinned,
        pin_absolute_directory(str(install)) as pinned_install,
        RootSelectedCandidateAuthority._acquire_for_test(
            pinned,
            replay,
        ) as authority,
        RootInstalledAcceptanceAuthority._acquire_for_test(
            pinned_install,
            expected_launch_id=installed.launch_id,
        ) as installed_authority,
    ):
        with pytest.raises(PermissionError, match="effective UID zero"):
            bind_start_authorization(
                ProspectiveStartAuthorizationIntent.from_bytes(_prospective_raw()),
                root_selection_authority=authority,
                installed_acceptance_authority=installed_authority,
                recorded_at_utc="2026-07-23T17:00:00Z",
                unit=values["installation"].run_unit,
            )
        monkeypatch.setattr(
            start_authorization_module.os,
            "geteuid",
            lambda: 0,
        )
        authorization = bind_start_authorization(
            ProspectiveStartAuthorizationIntent.from_bytes(_prospective_raw()),
            root_selection_authority=authority,
            installed_acceptance_authority=installed_authority,
            recorded_at_utc="2026-07-23T17:00:00Z",
            unit=values["installation"].run_unit,
        )
        assert authorization.installed_acceptance_sha256 == installed.raw_sha256

        original_bind = start_authorization_module._bind_start_authorization_from_chain

        def replace_selection_after_binding(
            *args: object,
            **kwargs: object,
        ) -> StartAuthorizationReceipt:
            receipt = original_bind(*args, **kwargs)
            path.unlink()
            path.write_bytes(selected.raw)
            path.chmod(0o444)
            return receipt

        monkeypatch.setattr(
            start_authorization_module,
            "_bind_start_authorization_from_chain",
            replace_selection_after_binding,
        )
        with pytest.raises(
            WarehouseW3RootSelectionError,
            match="authority drifted",
        ):
            bind_start_authorization(
                ProspectiveStartAuthorizationIntent.from_bytes(_prospective_raw()),
                root_selection_authority=authority,
                installed_acceptance_authority=installed_authority,
                recorded_at_utc="2026-07-23T17:00:01Z",
                unit=values["installation"].run_unit,
            )


def test_prospective_parser_rejects_authority_drift() -> None:
    value = json.loads(_prospective_raw())
    value["retry"] = True
    raw = (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()

    with pytest.raises(
        WarehouseW3StartAuthorizationError,
        match="authority differs",
    ):
        ProspectiveStartAuthorizationIntent.from_bytes(raw)


def test_binding_rejects_ingress_closure_drift_before_authorization_creation(
    semantic_inputs: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values, replay, evidence, installed, intents, receipts = _installed_bundle(
        semantic_inputs
    )
    ingress = json.loads(replay.candidate_gate_ingress_fact_raw)
    ingress["closure_sha256"] = "0" * 64
    drifted = replace(
        replay,
        candidate_gate_ingress_fact_raw=(
            json.dumps(
                ingress,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode(),
    )
    called = False

    def unexpected_create(
        cls: type[StartAuthorizationReceipt],
        **_kwargs: object,
    ) -> StartAuthorizationReceipt:
        nonlocal called
        del cls
        called = True
        raise AssertionError("authorization creation must not be reached")

    monkeypatch.setattr(
        StartAuthorizationReceipt,
        "create",
        classmethod(unexpected_create),
    )
    with pytest.raises(
        WarehouseW3StartAuthorizationError,
        match="producer replay differs",
    ):
        _bind_start_authorization_for_test(
            ProspectiveStartAuthorizationIntent.from_bytes(_prospective_raw()),
            selection_replay_inputs=drifted,
            prestart_evidence=evidence,
            installed_acceptance=installed,
            phase_intents=intents,
            phase_receipts=receipts,
            recorded_at_utc="2026-07-23T17:00:00Z",
            unit=values["installation"].run_unit,
        )
    assert called is False


def test_binding_requires_exact_w3_problem_state(
    semantic_inputs: dict[str, object],
) -> None:
    values, replay, evidence, installed, intents, receipts = _installed_bundle(
        semantic_inputs,
        problem_state_schema="scion.test-problem-state.v1",
    )

    with pytest.raises(WarehouseW3StartAuthorizationError, match="differ"):
        _bind_start_authorization_for_test(
            ProspectiveStartAuthorizationIntent.from_bytes(_prospective_raw()),
            selection_replay_inputs=replay,
            prestart_evidence=evidence,
            installed_acceptance=installed,
            phase_intents=intents,
            phase_receipts=receipts,
            recorded_at_utc="2026-07-23T17:00:00Z",
            unit=values["installation"].run_unit,
        )


def test_binding_rejects_alternate_full_dag_before_authorization(
    semantic_inputs: dict[str, object],
) -> None:
    values, replay, evidence, installed, intents, receipts = _installed_bundle(
        semantic_inputs
    )
    changed = list(receipts)
    changed[0] = RootPhaseReceipt.create(
        intent=intents[0],
        effect_sha256="0" * 64,
    )

    with pytest.raises(ReceiptDagError, match="differs"):
        _bind_start_authorization_for_test(
            ProspectiveStartAuthorizationIntent.from_bytes(_prospective_raw()),
            selection_replay_inputs=replay,
            prestart_evidence=evidence,
            installed_acceptance=installed,
            phase_intents=intents,
            phase_receipts=tuple(changed),
            recorded_at_utc="2026-07-23T17:00:00Z",
            unit=values["installation"].run_unit,
        )
