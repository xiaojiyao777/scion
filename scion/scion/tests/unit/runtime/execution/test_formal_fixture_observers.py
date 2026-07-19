from __future__ import annotations

import ast
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import threading
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest


_FIXTURE_ROOT = Path(__file__).parents[3] / "fixtures" / "runtime" / "execution"


def _load_fixture(name: str) -> ModuleType:
    path = _FIXTURE_ROOT / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"test_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def observer() -> ModuleType:
    return _load_fixture("generic_backend_unit_observer")


@pytest.fixture(scope="module")
def adversary() -> ModuleType:
    return _load_fixture("generic_backend_adversary")


@pytest.fixture(scope="module")
def formal_case() -> ModuleType:
    return _load_fixture("generic_backend_formal_case")


def _canonical(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")


def _write_canonical(path: Path, value: Any) -> None:
    path.write_bytes(_canonical(value))


def _fifo(path: Path) -> dict[str, str]:
    os.mkfifo(path, 0o600)
    identity = path.lstat()
    return {
        "path": str(path),
        "device": str(identity.st_dev),
        "inode": str(identity.st_ino),
    }


def _acquisition(tmp_path: Path) -> dict[str, Any]:
    return {
        "armed_receipt_path": str(tmp_path / "armed.json"),
        "ready_fifo": _fifo(tmp_path / "ready.fifo"),
        "release_fifo": _fifo(tmp_path / "release.fifo"),
    }


def _observer_plan(
    tmp_path: Path,
    acquisition: dict[str, Any],
    *,
    mode: str = "run-main",
    source_selector_path: str | None = None,
) -> dict[str, Any]:
    binding = "source" if mode == "closer" else "current"
    query_unit = "source.service" if binding == "source" else "run.service"
    return {
        "schema": "scion.generic_backend.systemd_observer_plan.v1",
        "mode": mode,
        "program_path": str(_FIXTURE_ROOT / "generic_backend_unit_observer.py"),
        "program_sha256": "a" * 64,
        "request_path": str(tmp_path / "request.json"),
        "output_path": str(tmp_path / "receipt.json"),
        "unit": "closer.service" if mode == "closer" else "run.service",
        "source_selector_path": source_selector_path,
        "cgroup_roots": [
            {"label": "service", "path": "/sys/fs/cgroup/example.service"}
        ],
        "property_inputs": [
            {
                "label": "properties",
                "kind": "systemd-properties-authority",
                "query_owner": "system-manager-dbus",
                "query_binding": binding,
                "query_unit": query_unit,
                "raw_authority_path": str(tmp_path / "properties.json"),
            }
        ],
        "acquisition": acquisition,
    }


def _systemd_authority(
    *, boot_id: str, unit: str, invocation_id: str
) -> dict[str, Any]:
    owner = ":1.255"
    object_path = "/org/freedesktop/systemd1/unit/run_2eservice"

    def text(value: str) -> dict[str, Any]:
        return {"signature": "s", "kind": "text", "value": value}

    def boolean(value: bool) -> dict[str, Any]:
        return {"signature": "b", "kind": "boolean", "value": value}

    def integer(signature: str, value: int) -> dict[str, Any]:
        return {"signature": signature, "kind": "integer", "value": str(value)}

    def strings(values: list[str]) -> dict[str, Any]:
        return {
            "signature": "as",
            "kind": "array",
            "items": [text(value) for value in values],
        }

    def exec_stop_post() -> dict[str, Any]:
        signature = "(sasbttttuii)"
        return {
            "signature": "a(sasbttttuii)",
            "kind": "array",
            "items": [
                {
                    "signature": signature,
                    "kind": "struct",
                    "items": [
                        text("/bin/true"),
                        strings(["/bin/true", "--post"]),
                        boolean(False),
                        integer("t", 1),
                        integer("t", 2),
                        integer("t", 3),
                        integer("t", 4),
                        integer("u", 5),
                        integer("i", 1),
                        integer("i", 0),
                    ],
                }
            ],
        }

    invocation_raw = bytes.fromhex(invocation_id)
    binary_invocation = {
        "signature": "ay",
        "kind": "binary",
        "length": str(len(invocation_raw)),
        "base64": base64.b64encode(invocation_raw).decode("ascii"),
        "sha256": hashlib.sha256(invocation_raw).hexdigest(),
    }
    values = [
        ("org.freedesktop.systemd1.Unit", "Id", "s", text(unit)),
        (
            "org.freedesktop.systemd1.Unit",
            "InvocationID",
            "ay",
            binary_invocation,
        ),
        ("org.freedesktop.systemd1.Unit", "LoadState", "s", text("loaded")),
        ("org.freedesktop.systemd1.Unit", "ActiveState", "s", text("active")),
        ("org.freedesktop.systemd1.Unit", "SubState", "s", text("running")),
        ("org.freedesktop.systemd1.Unit", "After", "as", strings(["basic.target"])),
        (
            "org.freedesktop.systemd1.Unit",
            "CollectMode",
            "s",
            text("inactive"),
        ),
        (
            "org.freedesktop.systemd1.Unit",
            "FragmentPath",
            "s",
            text("/run/systemd/system/run.service"),
        ),
        (
            "org.freedesktop.systemd1.Unit",
            "NeedDaemonReload",
            "b",
            boolean(False),
        ),
        ("org.freedesktop.systemd1.Unit", "OnSuccess", "as", strings([])),
        ("org.freedesktop.systemd1.Unit", "OnFailure", "as", strings([])),
        (
            "org.freedesktop.systemd1.Service",
            "ControlGroup",
            "s",
            text("/system.slice/run.service"),
        ),
        ("org.freedesktop.systemd1.Service", "Delegate", "b", boolean(True)),
        (
            "org.freedesktop.systemd1.Service",
            "DelegateControllers",
            "as",
            strings(["pids"]),
        ),
        (
            "org.freedesktop.systemd1.Service",
            "DelegateSubgroup",
            "s",
            text("supervisor"),
        ),
        (
            "org.freedesktop.systemd1.Service",
            "ExecMainCode",
            "i",
            integer("i", 0),
        ),
        (
            "org.freedesktop.systemd1.Service",
            "ExecMainStatus",
            "i",
            integer("i", 0),
        ),
        (
            "org.freedesktop.systemd1.Service",
            "ExecStopPost",
            "a(sasbttttuii)",
            exec_stop_post(),
        ),
        ("org.freedesktop.systemd1.Service", "Group", "s", text("scion-fixture")),
        (
            "org.freedesktop.systemd1.Service",
            "KillMode",
            "s",
            text("control-group"),
        ),
        (
            "org.freedesktop.systemd1.Service",
            "MainPID",
            "u",
            integer("u", 17),
        ),
        ("org.freedesktop.systemd1.Service", "Restart", "s", text("no")),
        ("org.freedesktop.systemd1.Service", "Result", "s", text("success")),
        (
            "org.freedesktop.systemd1.Service",
            "TimeoutStartUSec",
            "t",
            integer("t", (1 << 64) - 1),
        ),
        (
            "org.freedesktop.systemd1.Service",
            "TimeoutStopUSec",
            "t",
            integer("t", (1 << 64) - 1),
        ),
        ("org.freedesktop.systemd1.Service", "User", "s", text("scion-fixture")),
    ]
    return {
        "schema": "scion.generic_backend.systemd_raw_query.v1",
        "boot_id": boot_id,
        "unit": unit,
        "object_path": object_path,
        "manager_owner": owner,
        "invocation_id": invocation_id,
        "properties": [
            {
                "destination_owner": owner,
                "object_path": object_path,
                "interface": interface,
                "property": name,
                "variant_signature": signature,
                "value": value,
            }
            for interface, name, signature, value in values
        ],
        "normalization": {"configured": {"status": "accepted"}},
    }


def _adversary_plan(
    tmp_path: Path,
    *,
    scenario: str,
    acquisition: dict[str, Any] | None,
    hold_release_fifo: dict[str, str] | None,
) -> dict[str, Any]:
    unit = "closer.service" if scenario == "h9-failed-closer" else "run.service"
    expected_job_name = (
        "job-1-eeeeeeeeeeeeeeee"
        if scenario in {"h6-setsid-descendant", "b7-double-fork-closed-stdio"}
        else None
    )
    return {
        "schema": "scion.generic_backend.systemd_adversary_plan.v1",
        "scenario": scenario,
        "unit": unit,
        "expected_job_name": expected_job_name,
        "program_path": str(_FIXTURE_ROOT / "generic_backend_adversary.py"),
        "program_sha256": "b" * 64,
        "request_path": str(tmp_path / "request.json"),
        "receipt_path": str(tmp_path / "receipt.json"),
        "acquisition": acquisition,
        "hold_release_fifo": hold_release_fifo,
    }


def test_observer_plan_is_canonical_exact_and_rejects_unknowns(
    tmp_path: Path, observer: ModuleType
) -> None:
    plan_path = tmp_path / "plan.json"
    plan = _observer_plan(tmp_path, _acquisition(tmp_path))
    _write_canonical(plan_path, plan)

    decoded, raw = observer._decode_plan(plan_path)
    assert raw == _canonical(plan)
    assert decoded["mode"] == "run-main"
    assert decoded["property_inputs"][0]["query_binding"] == "current"

    plan["unknown"] = True
    _write_canonical(plan_path, plan)
    with pytest.raises(observer.ObserverError, match="unknown"):
        observer._decode_plan(plan_path)

    plan_path.write_text('{"schema":"one","schema":"two"}\n', encoding="ascii")
    with pytest.raises(observer.ObserverError, match="duplicate"):
        observer._decode_plan(plan_path)


def test_observer_plan_has_one_raw_authority_path(
    tmp_path: Path, observer: ModuleType
) -> None:
    plan_path = tmp_path / "plan.json"
    plan = _observer_plan(tmp_path, _acquisition(tmp_path))
    _write_canonical(plan_path, plan)

    decoded, _ = observer._decode_plan(plan_path)

    assert frozenset(decoded["property_inputs"][0]) == frozenset(
        {
            "label",
            "kind",
            "query_owner",
            "query_binding",
            "query_unit",
            "raw_authority_path",
        }
    )
    assert decoded["property_inputs"][0]["raw_authority_path"] == str(
        tmp_path / "properties.json"
    )

    legacy = plan["property_inputs"][0]
    legacy["raw_json_path"] = legacy.pop("raw_authority_path")
    legacy["raw_text_path"] = str(tmp_path / "properties.txt")
    _write_canonical(plan_path, plan)
    with pytest.raises(observer.ObserverError, match="schema mismatch"):
        observer._decode_plan(plan_path)


@pytest.mark.parametrize("mode", ["run-main", "closer"])
def test_observer_real_post_release_materialization_uses_one_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    observer: ModuleType,
    mode: str,
) -> None:
    acquisition = _acquisition(tmp_path)
    selector_path = tmp_path / "selector.json"
    plan = _observer_plan(
        tmp_path,
        acquisition,
        mode=mode,
        source_selector_path=str(selector_path) if mode == "closer" else None,
    )
    plan_path = tmp_path / "plan.json"
    _write_canonical(plan_path, plan)
    authority_path = Path(plan["property_inputs"][0]["raw_authority_path"])
    boot_id = "11111111-2222-3333-4444-555555555555"
    source_invocation = "a" * 32
    identity = {
        "boot_id": boot_id,
        "invocation_id": "d" * 32,
        "pid": 17,
        "proc_cgroup_raw": f"0::/system.slice/{plan['unit']}/supervisor\n",
        "starttime": 19,
        "unified_cgroup": f"/system.slice/{plan['unit']}/supervisor",
    }
    selector = {
        "schema": "scion.generic_backend.systemd_source_selector.v1",
        "boot_id": boot_id,
        "source_unit": "source.service",
        "source_invocation_id": source_invocation,
        "source_receipt_sha256": "c" * 64,
    }
    query_unit = "source.service" if mode == "closer" else "run.service"
    query_invocation = (
        source_invocation if mode == "closer" else identity["invocation_id"]
    )
    authority = _systemd_authority(
        boot_id=identity["boot_id"],
        unit=query_unit,
        invocation_id=query_invocation,
    )
    monkeypatch.setenv("INVOCATION_ID", identity["invocation_id"])
    monkeypatch.setattr(
        observer,
        "_verify_program",
        lambda _plan: {
            "path": _plan["program_path"],
            "sha256": _plan["program_sha256"],
            "identity": {"device": 1, "inode": 2, "mode": 0o444},
        },
    )

    def process_identity(mode: str, expected: str) -> dict[str, Any]:
        assert mode in {"run-main", "closer"}
        assert expected == identity["invocation_id"]
        return dict(identity)

    monkeypatch.setattr(observer, "_process_identity", process_identity)
    monkeypatch.setattr(observer, "_stop_post_environment", lambda _mode: None)
    monkeypatch.setattr(
        observer,
        "_capture_cgroup_root",
        lambda label, path: {"label": label, "path": str(path), "inventory": []},
    )
    armed_receipts: list[dict[str, Any]] = []

    def release_after_authority(
        value: dict[str, Any], *, armed_payload: dict[str, Any]
    ) -> None:
        assert value == acquisition
        assert not Path(plan["request_path"]).exists()
        assert not Path(plan["output_path"]).exists()
        assert not authority_path.exists()
        assert not selector_path.exists()
        assert armed_payload["source_selector_path"] == (
            str(selector_path) if mode == "closer" else None
        )
        assert armed_payload["raw_authority_paths"] == [str(authority_path)]
        armed_receipts.append(armed_payload)
        if mode == "closer":
            _write_canonical(selector_path, selector)
        _write_canonical(authority_path, authority)

    monkeypatch.setattr(observer, "_perform_acquisition", release_after_authority)

    observer._run_plan(plan_path)

    assert len(armed_receipts) == 1
    request = json.loads(Path(plan["request_path"]).read_text(encoding="ascii"))
    assert request["property_inputs"] == [
        {
            "kind": "systemd-properties-authority",
            "label": "properties",
            "query_invocation_id": query_invocation,
            "query_owner": "system-manager-dbus",
            "query_unit": query_unit,
            "raw_authority_path": str(authority_path),
        }
    ]
    receipt = json.loads(Path(plan["output_path"]).read_text(encoding="ascii"))
    binding = receipt["property_inputs"][0]
    assert frozenset(binding) == frozenset(
        {
            "authoritative",
            "kind",
            "label",
            "query_invocation_id",
            "query_owner",
            "query_unit",
            "raw_authority",
        }
    )
    assert binding["authoritative"] is True
    assert binding["raw_authority"]["decoded"] == authority
    assert binding["raw_authority"]["path"] == str(authority_path)
    assert binding["raw_authority"]["sha256"] == hashlib.sha256(
        _canonical(authority)
    ).hexdigest()
    source_binding = receipt["formal_plan_binding"]["source_selector"]
    if mode == "closer":
        assert source_binding["value"] == selector
        assert request["source_unit"] == selector["source_unit"]
        assert request["source_invocation_id"] == selector["source_invocation_id"]
    else:
        assert source_binding is None

    request_raw = Path(plan["request_path"]).read_bytes()
    formal_binding = receipt["formal_plan_binding"]
    observer._validate_formal_plan_binding(
        Path(plan["request_path"]),
        request,
        request_raw,
        identity,
        formal_binding,
    )
    binding_mutations = []
    missing_acquisition = json.loads(json.dumps(formal_binding))
    del missing_acquisition["acquisition"]
    binding_mutations.append(missing_acquisition)
    wrong_plan_hash = json.loads(json.dumps(formal_binding))
    wrong_plan_hash["plan_sha256"] = "0" * 64
    binding_mutations.append(wrong_plan_hash)
    wrong_program = json.loads(json.dumps(formal_binding))
    wrong_program["program"]["sha256"] = "0" * 64
    binding_mutations.append(wrong_program)
    wrong_selector = json.loads(json.dumps(formal_binding))
    wrong_selector["source_selector"] = None if mode == "closer" else {"extra": True}
    binding_mutations.append(wrong_selector)
    for mutated_binding in binding_mutations:
        with pytest.raises(observer.ObserverError):
            observer._validate_formal_plan_binding(
                Path(plan["request_path"]),
                request,
                request_raw,
                identity,
                mutated_binding,
            )

    mutated_request = json.loads(json.dumps(request))
    mutated_request["property_inputs"][0]["query_unit"] = "other.service"
    with pytest.raises(observer.ObserverError, match="materialized request"):
        observer._validate_formal_plan_binding(
            Path(plan["request_path"]),
            mutated_request,
            _canonical(mutated_request),
            identity,
            formal_binding,
        )


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("schema", "schema is not supported"),
        ("unknown", "unknown"),
        ("owner", "manager owner or object path drifted"),
        ("object", "manager owner or object path drifted"),
        ("boot", "boot ID differs"),
        ("unit", "unit differs"),
        ("invocation", "invocation differs"),
        ("property-order", "ledger order or signature drifted"),
        ("property-signature", "ledger order or signature drifted"),
        ("tag-kind", "tagged D-Bus string"),
        ("id-property", "Id property differs"),
        ("noncanonical-base64", "byte length or digest drifted"),
        ("exec-stop-post", "tagged ExecStopPost struct"),
    ],
)
def test_observer_systemd_authority_rejects_semantic_drift(
    tmp_path: Path,
    observer: ModuleType,
    mutation: str,
    error: str,
) -> None:
    boot_id = "11111111-2222-3333-4444-555555555555"
    invocation_id = "d" * 32
    authority = _systemd_authority(
        boot_id=boot_id,
        unit="run.service",
        invocation_id=invocation_id,
    )
    if mutation == "schema":
        authority["schema"] = "scion.generic_backend.systemd_raw_query.v2"
    elif mutation == "unknown":
        authority["unknown"] = True
    elif mutation == "owner":
        authority["properties"][0]["destination_owner"] = ":1.999"
    elif mutation == "object":
        authority["object_path"] = "/org/freedesktop/systemd1/unit/other_2eservice"
    elif mutation == "boot":
        authority["boot_id"] = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    elif mutation == "unit":
        authority["unit"] = "other.service"
    elif mutation == "invocation":
        authority["invocation_id"] = "e" * 32
    elif mutation == "property-order":
        authority["properties"][2], authority["properties"][3] = (
            authority["properties"][3],
            authority["properties"][2],
        )
    elif mutation == "property-signature":
        authority["properties"][2]["variant_signature"] = "b"
    elif mutation == "tag-kind":
        authority["properties"][2]["value"]["kind"] = "boolean"
    elif mutation == "id-property":
        authority["properties"][0]["value"]["value"] = "other.service"
    elif mutation == "noncanonical-base64":
        binary = authority["properties"][1]["value"]
        assert binary["base64"].endswith("Q==")
        binary["base64"] = binary["base64"][:-3] + "R=="
    else:
        assert mutation == "exec-stop-post"
        authority["properties"][17]["value"]["items"][0]["items"].pop()
    authority_path = tmp_path / "properties.json"
    _write_canonical(authority_path, authority)
    request_input = {
        "label": "properties",
        "kind": "systemd-properties-authority",
        "query_owner": "system-manager-dbus",
        "query_unit": "run.service",
        "query_invocation_id": invocation_id,
        "raw_authority_path": str(authority_path),
    }

    with pytest.raises(observer.ObserverError, match=error):
        observer._capture_property_input(
            request_input, expected_boot_id=boot_id
        )


def test_observer_journal_input_is_unbounded_and_record_closed(
    tmp_path: Path, observer: ModuleType
) -> None:
    boot_id = "11111111-2222-3333-4444-555555555555"
    payload = "x" * 2_000_000
    records = [
        {"MESSAGE": payload, "SEQNUM": "1"},
        {"MESSAGE": "complete", "SEQNUM": "2"},
    ]
    raw = b"".join(_canonical(record) for record in records)
    path = tmp_path / "journal.ndjson"
    path.write_bytes(raw)
    request_input = {
        "label": "journal",
        "kind": "journal-corroboration",
        "query_owner": "journalctl",
        "query_unit": "run.service",
        "query_invocation_id": "d" * 32,
        "raw_authority_path": str(path),
    }

    captured = observer._capture_property_input(
        request_input, expected_boot_id=boot_id
    )

    assert captured["authoritative"] is False
    assert captured["raw_authority"]["decoded"] == records
    assert captured["raw_authority"]["size"] == len(raw)
    assert captured["raw_authority"]["text"].encode("utf-8") == raw
    assert captured["raw_authority"]["sha256"] == hashlib.sha256(raw).hexdigest()

    malformed = [
        raw[:-1],
        raw + b"\n",
        b'{"MESSAGE":"one","MESSAGE":"two"}\n',
    ]
    for candidate in malformed:
        path.write_bytes(candidate)
        with pytest.raises(observer.ObserverError):
            observer._capture_property_input(
                request_input, expected_boot_id=boot_id
            )


def test_observer_closer_binds_only_root_sealed_source_selector(
    tmp_path: Path, observer: ModuleType
) -> None:
    acquisition = _acquisition(tmp_path)
    selector_path = tmp_path / "selector.json"
    boot_id = "11111111-2222-3333-4444-555555555555"
    source_invocation = "a" * 32
    selector = {
        "schema": "scion.generic_backend.systemd_source_selector.v1",
        "boot_id": boot_id,
        "source_unit": "source.service",
        "source_invocation_id": source_invocation,
        "source_receipt_sha256": "c" * 64,
    }
    _write_canonical(selector_path, selector)
    plan_path = tmp_path / "plan.json"
    _write_canonical(
        plan_path,
        _observer_plan(
            tmp_path,
            acquisition,
            mode="closer",
            source_selector_path=str(selector_path),
        ),
    )
    plan, _ = observer._decode_plan(plan_path)
    identity = {
        "boot_id": boot_id,
        "invocation_id": "d" * 32,
        "pid": 17,
        "starttime": 19,
    }

    request, binding = observer._materialize_request(plan, identity)

    assert request["expected_invocation_id"] == "d" * 32
    assert request["source_unit"] == "source.service"
    assert request["source_invocation_id"] == source_invocation
    assert request["property_inputs"][0]["query_invocation_id"] == source_invocation
    assert binding is not None
    assert binding["value"] == selector


@pytest.mark.parametrize(
    ("scenario", "uses_acquisition", "uses_hold"),
    [
        ("h2-main-nonzero", True, False),
        ("h3-main-signal", True, False),
        ("h4-stoppost-failure", True, False),
        ("h6-setsid-descendant", False, True),
        ("h7-guardian-hold", True, False),
        ("h8-extra-topology-hold", True, False),
        ("h9-failed-closer", True, False),
        ("h10-gc-negative", True, False),
        ("h11-unbounded-hold", True, False),
        ("b7-double-fork-closed-stdio", False, True),
    ],
)
def test_adversary_plan_has_one_exact_scenario_fifo_owner(
    tmp_path: Path,
    adversary: ModuleType,
    scenario: str,
    uses_acquisition: bool,
    uses_hold: bool,
) -> None:
    acquisition = _acquisition(tmp_path) if uses_acquisition else None
    hold = _fifo(tmp_path / "hold.fifo") if uses_hold else None
    plan_path = tmp_path / "plan.json"
    plan = _adversary_plan(
        tmp_path,
        scenario=scenario,
        acquisition=acquisition,
        hold_release_fifo=hold,
    )
    _write_canonical(plan_path, plan)

    decoded, raw = adversary._decode_plan(plan_path)

    assert raw == _canonical(plan)
    assert decoded["unit"] == (
        "closer.service" if scenario == "h9-failed-closer" else "run.service"
    )
    assert (decoded["acquisition"] is not None) is uses_acquisition
    assert (decoded["hold_release_fifo"] is not None) is uses_hold
    actor = {"invocation_id": "e" * 32}
    if uses_hold:
        actor["unified_cgroup"] = (
            f"/system.slice/{decoded['unit']}/{decoded['expected_job_name']}"
        )
    request_value = adversary._materialize_request(decoded, actor)
    assert request_value["scenario"] == scenario
    assert request_value["unit"] == decoded["unit"]
    assert request_value["expected_invocation_id"] == actor["invocation_id"]
    assert request_value["expected_job_name"] == decoded["expected_job_name"]
    assert (request_value["expected_job_cgroup"] is not None) is uses_hold
    assert (request_value["hold_release_fifo"] is not None) is uses_hold
    if uses_hold:
        assert request_value["hold_release_fifo"] == hold


@pytest.mark.parametrize(
    ("scenario", "require_live_descendant"),
    [
        pytest.param("h6-setsid-descendant", False, id="B5-setsid"),
        pytest.param(
            "b7-double-fork-closed-stdio", True, id="B6-double-fork"
        ),
    ],
)
def test_adversary_real_descendant_chain_cross_binds_every_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    adversary: ModuleType,
    formal_case: ModuleType,
    scenario: str,
    require_live_descendant: bool,
) -> None:
    hold = _fifo(tmp_path / "hold.fifo")
    plan = _adversary_plan(
        tmp_path,
        scenario=scenario,
        acquisition=None,
        hold_release_fifo=hold,
    )
    program_path = Path(plan["program_path"])
    plan["program_sha256"] = hashlib.sha256(program_path.read_bytes()).hexdigest()
    plan_path = tmp_path / "plan.json"
    _write_canonical(plan_path, plan)
    invocation_id = "e" * 32
    boot_id = "11111111-2222-3333-4444-555555555555"
    job_cgroup = "/system.slice/run.service/job-1-eeeeeeeeeeeeeeee"
    monkeypatch.setenv("INVOCATION_ID", invocation_id)
    monkeypatch.setenv("LC_ALL", "C")
    monkeypatch.setattr(
        adversary,
        "sys",
        SimpleNamespace(
            version_info=(3, 12, 0),
            flags=SimpleNamespace(isolated=1, dont_write_bytecode=1),
        ),
    )

    def identity(**_kwargs: Any) -> dict[str, Any]:
        pid = os.getpid()
        return {
            "boot_id": boot_id,
            "invocation_id": invocation_id,
            "pid": pid,
            "proc_cgroup_raw": f"0::{job_cgroup}\n",
            "session_id": os.getsid(0),
            "starttime": adversary._starttime(pid),
            "stop_selector_environment": {},
            "unified_cgroup": job_cgroup,
        }

    monkeypatch.setattr(adversary, "_identity", identity)
    monkeypatch.setattr(formal_case, "_child_cgroup", lambda _pid: job_cgroup)
    original_fork = os.fork
    direct_children: list[int] = []

    def observed_fork() -> int:
        child = original_fork()
        if child > 0:
            direct_children.append(child)
        return child

    monkeypatch.setattr(adversary.os, "fork", observed_fork)
    process_spec_sha256 = "a" * 64
    process_spec = {
        "environment": tuple(
            sorted((f"INVOCATION_ID={invocation_id}".encode("ascii"), b"LC_ALL=C"))
        ),
        "spec_sha256": process_spec_sha256,
    }
    actor = identity()
    receipt_path = Path(plan["receipt_path"])
    request_path = Path(plan["request_path"])

    try:
        assert adversary._run_plan(plan_path) == 0
        sealed_request = json.loads(request_path.read_text(encoding="ascii"))
        sealed_receipt = json.loads(receipt_path.read_text(encoding="ascii"))
        sealed_request_raw = request_path.read_bytes()
        plan_sha256 = hashlib.sha256(_canonical(plan)).hexdigest()
        config = {
            "control_fifo": hold,
            "descendant_adversary_plan": {"path": str(plan_path)},
        }
        adversary._validate_formal_plan_binding(
            request_path,
            sealed_request,
            sealed_request_raw,
            actor,
            None,
            sealed_receipt["formal_plan_binding"],
        )
        producer_binding_mutations = []
        missing_acquisition = json.loads(
            json.dumps(sealed_receipt["formal_plan_binding"])
        )
        del missing_acquisition["acquisition"]
        producer_binding_mutations.append(missing_acquisition)
        wrong_plan_hash = json.loads(
            json.dumps(sealed_receipt["formal_plan_binding"])
        )
        wrong_plan_hash["plan_sha256"] = "0" * 64
        producer_binding_mutations.append(wrong_plan_hash)
        wrong_fifo = json.loads(json.dumps(sealed_receipt["formal_plan_binding"]))
        wrong_fifo["hold_release_fifo"]["inode"] = "1"
        producer_binding_mutations.append(wrong_fifo)
        for mutated_binding in producer_binding_mutations:
            with pytest.raises(adversary.AdversaryError):
                adversary._validate_formal_plan_binding(
                    request_path,
                    sealed_request,
                    sealed_request_raw,
                    actor,
                    None,
                    mutated_binding,
                )

        producer_request_mutation = json.loads(json.dumps(sealed_request))
        producer_request_mutation["unit"] = "other.service"
        with pytest.raises(adversary.AdversaryError, match="materialized request"):
            adversary._validate_formal_plan_binding(
                request_path,
                producer_request_mutation,
                _canonical(producer_request_mutation),
                actor,
                None,
                sealed_receipt["formal_plan_binding"],
            )

        def validate(
            *,
            plan_hash: str = plan_sha256,
            spec_hash: str = process_spec_sha256,
            spec: dict[str, Any] = process_spec,
        ) -> dict[str, Any]:
            return formal_case._validate_descendant_receipt(
                config,
                plan=plan,
                plan_sha256=plan_hash,
                receipt_path=str(receipt_path),
                invocation_id=invocation_id,
                boot_id=boot_id,
                blocked_process={
                    "pid": actor["pid"],
                    "starttime": actor["starttime"],
                },
                expected_job_cgroup=job_cgroup,
                process_spec_sha256=spec_hash,
                process_spec=spec,
                require_live_descendant=require_live_descendant,
            )

        evidence = validate()
        assert evidence["process_spec_sha256"] == process_spec_sha256
        assert evidence["receipt_sha256"] == hashlib.sha256(
            receipt_path.read_bytes()
        ).hexdigest()
        assert evidence["actor"] == sealed_receipt["actor"]
        assert evidence["descendant"] == sealed_receipt["descendant"]

        mutations: list[
            tuple[dict[str, Any], dict[str, Any], str, str, dict[str, Any]]
        ] = []
        request_mutation = json.loads(json.dumps(sealed_request))
        request_mutation["unit"] = "other.service"
        mutations.append(
            (
                request_mutation,
                sealed_receipt,
                plan_sha256,
                process_spec_sha256,
                process_spec,
            )
        )
        receipt_request_hash = json.loads(json.dumps(sealed_receipt))
        receipt_request_hash["request_sha256"] = "0" * 64
        mutations.append(
            (
                sealed_request,
                receipt_request_hash,
                plan_sha256,
                process_spec_sha256,
                process_spec,
            )
        )
        receipt_fifo = json.loads(json.dumps(sealed_receipt))
        receipt_fifo["formal_plan_binding"]["hold_release_fifo"]["inode"] = "1"
        mutations.append(
            (
                sealed_request,
                receipt_fifo,
                plan_sha256,
                process_spec_sha256,
                process_spec,
            )
        )
        receipt_actor = json.loads(json.dumps(sealed_receipt))
        receipt_actor["actor"]["boot_id"] = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        mutations.append(
            (
                sealed_request,
                receipt_actor,
                plan_sha256,
                process_spec_sha256,
                process_spec,
            )
        )
        receipt_descendant = json.loads(json.dumps(sealed_receipt))
        receipt_descendant["descendant"]["unified_cgroup"] = "/system.slice/other.service"
        mutations.append(
            (
                sealed_request,
                receipt_descendant,
                plan_sha256,
                process_spec_sha256,
                process_spec,
            )
        )
        bad_environment = dict(process_spec)
        bad_environment["environment"] = (
            f"INVOCATION_ID={invocation_id}".encode("ascii"),
        )
        mutations.append(
            (
                sealed_request,
                sealed_receipt,
                plan_sha256,
                process_spec_sha256,
                bad_environment,
            )
        )
        mutations.append(
            (
                sealed_request,
                sealed_receipt,
                "0" * 64,
                process_spec_sha256,
                process_spec,
            )
        )
        mutations.append(
            (
                sealed_request,
                sealed_receipt,
                plan_sha256,
                "0" * 64,
                process_spec,
            )
        )

        for request_value, receipt_value, plan_hash, spec_hash, spec_value in mutations:
            _write_canonical(request_path, request_value)
            _write_canonical(receipt_path, receipt_value)
            with pytest.raises(formal_case.FixtureError):
                validate(plan_hash=plan_hash, spec_hash=spec_hash, spec=spec_value)
        _write_canonical(request_path, sealed_request)
        _write_canonical(receipt_path, sealed_receipt)
        assert validate()["receipt_sha256"] == hashlib.sha256(
            receipt_path.read_bytes()
        ).hexdigest()
    finally:
        release_writer = os.open(
            hold["path"], os.O_WRONLY | os.O_NOFOLLOW | os.O_CLOEXEC
        )
        try:
            assert os.write(release_writer, adversary.RELEASE_BYTES) == len(
                adversary.RELEASE_BYTES
            )
        finally:
            os.close(release_writer)
        for child in direct_children:
            try:
                os.waitpid(child, 0)
            except ChildProcessError:
                pass


def test_adversary_plan_rejects_wrong_fifo_role(
    tmp_path: Path, adversary: ModuleType
) -> None:
    plan_path = tmp_path / "plan.json"
    plan = _adversary_plan(
        tmp_path,
        scenario="h11-unbounded-hold",
        acquisition=None,
        hold_release_fifo=_fifo(tmp_path / "hold.fifo"),
    )
    _write_canonical(plan_path, plan)

    with pytest.raises(adversary.AdversaryError, match="requires acquisition"):
        adversary._decode_plan(plan_path)


def test_adversary_plan_rejects_duplicate_and_unknown_keys(
    tmp_path: Path, adversary: ModuleType
) -> None:
    plan_path = tmp_path / "plan.json"
    plan = _adversary_plan(
        tmp_path,
        scenario="h2-main-nonzero",
        acquisition=None,
        hold_release_fifo=None,
    )
    plan["unknown"] = True
    _write_canonical(plan_path, plan)
    with pytest.raises(adversary.AdversaryError, match="unknown"):
        adversary._decode_plan(plan_path)

    plan_path.write_text('{"schema":"one","schema":"two"}\n', encoding="ascii")
    with pytest.raises(adversary.AdversaryError, match="duplicate"):
        adversary._decode_plan(plan_path)


def test_adversary_plan_requires_canonical_service_unit(
    tmp_path: Path, adversary: ModuleType
) -> None:
    plan_path = tmp_path / "plan.json"
    plan = _adversary_plan(
        tmp_path,
        scenario="h2-main-nonzero",
        acquisition=_acquisition(tmp_path),
        hold_release_fifo=None,
    )
    plan["unit"] = "not-a-service"
    _write_canonical(plan_path, plan)

    with pytest.raises(adversary.AdversaryError, match="canonical .service"):
        adversary._decode_plan(plan_path)


@pytest.mark.parametrize("fixture_name", ["observer", "adversary"])
@pytest.mark.parametrize("extra", [b"", b"extra"])
def test_acquisition_uses_ready_then_release_and_requires_exact_eof(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
    fixture_name: str,
    extra: bytes,
) -> None:
    module = request.getfixturevalue(fixture_name)
    acquisition = _acquisition(tmp_path)
    ready = acquisition["ready_fifo"]
    release = acquisition["release_fifo"]
    ready_reader = os.open(
        ready["path"],
        os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC,
    )
    failures: list[BaseException] = []
    if fixture_name == "observer":
        armed = {"schema": "test", "process_identity": {"starttime": 1}}
        error_type = module.ObserverError
    else:
        armed = {"schema": "test", "actor": {"starttime": 1}}
        error_type = module.AdversaryError

    ready_written = threading.Event()
    allow_ready_close = threading.Event()
    original_write_all = module._write_all_fd

    def write_all_then_hold_ready(
        fd: int, payload: bytes, *args: Any, **kwargs: Any
    ) -> None:
        original_write_all(fd, payload, *args, **kwargs)
        if payload == module.READY_BYTES:
            ready_written.set()
            allow_ready_close.wait()

    monkeypatch.setattr(module, "_write_all_fd", write_all_then_hold_ready)

    def acquire() -> None:
        try:
            module._perform_acquisition(acquisition, armed_payload=armed)
        except BaseException as exc:  # captured for the owning test thread
            failures.append(exc)
            ready_written.set()

    worker = threading.Thread(target=acquire)
    worker.start()
    try:
        ready_written.wait()
        if failures:
            raise failures[0]
        os.set_blocking(ready_reader, True)
        allow_ready_close.set()
        assert module._read_all_fd(ready_reader) == module.READY_BYTES

        release_writer = os.open(
            release["path"], os.O_WRONLY | os.O_NOFOLLOW | os.O_CLOEXEC
        )
        try:
            payload = module.RELEASE_BYTES + extra
            assert os.write(release_writer, payload) == len(payload)
        finally:
            os.close(release_writer)
    finally:
        allow_ready_close.set()
        os.close(ready_reader)
    worker.join()

    assert Path(acquisition["armed_receipt_path"]).is_file()
    if extra:
        assert len(failures) == 1
        assert isinstance(failures[0], error_type)
        assert "exact one-shot token and EOF" in str(failures[0])
    else:
        assert failures == []


@pytest.mark.parametrize(
    ("scenario", "expected_code", "receipt_exists_during_acquisition"),
    [
        ("h2-main-nonzero", 23, True),
        ("h4-stoppost-failure", 47, True),
        ("h8-extra-topology-hold", 0, True),
        ("h9-failed-closer", 61, False),
        ("h10-gc-negative", 29, True),
        ("h11-unbounded-hold", 0, True),
    ],
)
def test_adversary_acquisition_receipt_order_and_outcome(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    adversary: ModuleType,
    scenario: str,
    expected_code: int,
    receipt_exists_during_acquisition: bool,
) -> None:
    request_path = tmp_path / "request.json"
    receipt_path = tmp_path / "receipt.json"
    unit = "closer.service" if scenario == "h9-failed-closer" else "run.service"
    _write_canonical(
        request_path,
        {
            "schema": adversary.REQUEST_SCHEMA,
            "scenario": scenario,
            "unit": unit,
            "expected_invocation_id": "e" * 32,
            "expected_job_name": None,
            "expected_job_cgroup": None,
            "receipt_path": str(receipt_path),
            "hold_release_fifo": None,
        },
    )
    actor = {
        "boot_id": "11111111-2222-3333-4444-555555555555",
        "invocation_id": "e" * 32,
        "pid": 23,
        "proc_cgroup_raw": (
            "0::/system.slice/run.service/.control\n"
            if scenario == "h4-stoppost-failure"
            else (
                "0::/system.slice/closer.service\n"
                if scenario == "h9-failed-closer"
                else (
                    "0::/system.slice/run.service\n"
                    if scenario == "h10-gc-negative"
                    else "0::/system.slice/run.service/supervisor\n"
                )
            )
        ),
        "session_id": 23,
        "starttime": 29,
        "stop_selector_environment": (
            {
                "INVOCATION_ID": "e" * 32,
                "SERVICE_RESULT": "success",
                "EXIT_CODE": "exited",
                "EXIT_STATUS": "0",
            }
            if scenario == "h4-stoppost-failure"
            else {}
        ),
        "unified_cgroup": (
            "/system.slice/run.service/.control"
            if scenario == "h4-stoppost-failure"
            else (
                "/system.slice/closer.service"
                if scenario == "h9-failed-closer"
                else (
                    "/system.slice/run.service"
                    if scenario == "h10-gc-negative"
                    else "/system.slice/run.service/supervisor"
                )
            )
        ),
    }
    monkeypatch.setattr(adversary, "_identity", lambda **_kwargs: actor)
    monkeypatch.setattr(
        adversary, "_validate_formal_plan_binding", lambda *_args: None
    )

    observed: list[bool] = []

    def acquire(_value: Any, *, armed_payload: dict[str, Any]) -> None:
        assert armed_payload["actor"] == actor
        assert armed_payload["unit"] == unit
        assert armed_payload["actor"]["boot_id"] == actor["boot_id"]
        assert armed_payload["actor"]["unified_cgroup"] == actor["unified_cgroup"]
        observed.append(receipt_path.exists())

    monkeypatch.setattr(adversary, "_perform_acquisition", acquire)
    formal_binding = {
        "scenario": scenario,
        "unit": unit,
        "expected_job_name": None,
        "plan_path": str(tmp_path / "plan.json"),
        "plan_sha256": "f" * 64,
        "program": {"path": str(tmp_path / "program.py"), "sha256": "a" * 64},
    }

    code = adversary.run(
        request_path,
        acquisition={
            "armed_receipt_path": str(tmp_path / "armed.json"),
            "ready_fifo": {},
            "release_fifo": {},
        },
        formal_plan_binding=formal_binding,
        expected_actor=actor,
        expected_unit=unit,
    )

    assert code == expected_code
    assert observed == [receipt_exists_during_acquisition]
    assert receipt_path.is_file()
    receipt = json.loads(receipt_path.read_text(encoding="ascii"))
    assert receipt["unit"] == unit
    assert receipt["expected_invocation_id"] == actor["invocation_id"]
    assert receipt["formal_plan_binding"]["scenario"] == scenario
    assert receipt["formal_plan_binding"]["unit"] == unit
    assert receipt["actor"]["boot_id"] == actor["boot_id"]
    assert receipt["actor"]["unified_cgroup"] == actor["unified_cgroup"]


def test_adversary_h7_rejects_any_fifo_release_return(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    adversary: ModuleType,
) -> None:
    request_path = tmp_path / "request.json"
    receipt_path = tmp_path / "receipt.json"
    _write_canonical(
        request_path,
        {
            "schema": adversary.REQUEST_SCHEMA,
            "scenario": "h7-guardian-hold",
            "unit": "run.service",
            "expected_invocation_id": "e" * 32,
            "expected_job_name": None,
            "expected_job_cgroup": None,
            "receipt_path": str(receipt_path),
            "hold_release_fifo": None,
        },
    )
    actor = {
        "boot_id": "11111111-2222-3333-4444-555555555555",
        "invocation_id": "e" * 32,
        "pid": 23,
        "proc_cgroup_raw": "0::/system.slice/run.service/supervisor\n",
        "session_id": 23,
        "starttime": 29,
        "stop_selector_environment": {},
        "unified_cgroup": "/system.slice/run.service/supervisor",
    }
    monkeypatch.setattr(adversary, "_identity", lambda **_kwargs: actor)
    monkeypatch.setattr(
        adversary, "_validate_formal_plan_binding", lambda *_args: None
    )

    def forbidden_release(_value: Any, *, armed_payload: dict[str, Any]) -> None:
        assert armed_payload["unit"] == "run.service"
        assert receipt_path.is_file()

    monkeypatch.setattr(adversary, "_perform_acquisition", forbidden_release)
    binding = {
        "scenario": "h7-guardian-hold",
        "unit": "run.service",
        "expected_job_name": None,
        "plan_path": str(tmp_path / "plan.json"),
        "plan_sha256": "f" * 64,
        "program": {"path": str(tmp_path / "program.py"), "sha256": "a" * 64},
    }

    with pytest.raises(adversary.AdversaryError, match="StopUnit"):
        adversary.run(
            request_path,
            acquisition={
                "armed_receipt_path": str(tmp_path / "armed.json"),
                "ready_fifo": {},
                "release_fifo": {},
            },
            formal_plan_binding=binding,
            expected_actor=actor,
            expected_unit="run.service",
        )


def test_adversary_h3_aborts_only_after_acquisition_release(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    adversary: ModuleType,
) -> None:
    class AbortCalled(RuntimeError):
        pass

    request_path = tmp_path / "request.json"
    receipt_path = tmp_path / "receipt.json"
    _write_canonical(
        request_path,
        {
            "schema": adversary.REQUEST_SCHEMA,
            "scenario": "h3-main-signal",
            "unit": "run.service",
            "expected_invocation_id": "e" * 32,
            "expected_job_name": None,
            "expected_job_cgroup": None,
            "receipt_path": str(receipt_path),
            "hold_release_fifo": None,
        },
    )
    actor = {
        "boot_id": "11111111-2222-3333-4444-555555555555",
        "invocation_id": "e" * 32,
        "pid": 23,
        "proc_cgroup_raw": "0::/system.slice/run.service/supervisor\n",
        "session_id": 23,
        "starttime": 29,
        "stop_selector_environment": {},
        "unified_cgroup": "/system.slice/run.service/supervisor",
    }
    monkeypatch.setattr(adversary, "_identity", lambda **_kwargs: actor)
    monkeypatch.setattr(
        adversary, "_validate_formal_plan_binding", lambda *_args: None
    )
    monkeypatch.setattr(
        adversary,
        "_perform_acquisition",
        lambda _value, *, armed_payload: receipt_path.is_file()
        or pytest.fail("H3 receipt was not sealed before acquisition"),
    )
    monkeypatch.setattr(adversary.os, "abort", lambda: (_ for _ in ()).throw(AbortCalled()))
    binding = {
        "scenario": "h3-main-signal",
        "unit": "run.service",
        "expected_job_name": None,
        "plan_path": str(tmp_path / "plan.json"),
        "plan_sha256": "f" * 64,
        "program": {"path": str(tmp_path / "program.py"), "sha256": "a" * 64},
    }

    with pytest.raises(AbortCalled):
        adversary.run(
            request_path,
            acquisition={
                "armed_receipt_path": str(tmp_path / "armed.json"),
                "ready_fifo": {},
                "release_fifo": {},
            },
            formal_plan_binding=binding,
            expected_actor=actor,
            expected_unit="run.service",
        )


def test_adversary_unit_lineage_is_exact_and_unified(adversary: ModuleType) -> None:
    main = "/system.slice/run.service/supervisor"
    assert adversary._unified_cgroup(f"0::{main}\n") == main
    adversary._validate_unit_lineage(
        scenario="h2-main-nonzero", unit="run.service", lineage=main
    )
    adversary._validate_unit_lineage(
        scenario="h4-stoppost-failure",
        unit="run.service",
        lineage="/system.slice/run.service/.control",
    )
    adversary._validate_unit_lineage(
        scenario="h9-failed-closer",
        unit="closer.service",
        lineage="/system.slice/closer.service",
    )
    adversary._validate_unit_lineage(
        scenario="h10-gc-negative",
        unit="run.service",
        lineage="/system.slice/run.service",
    )
    adversary._validate_unit_lineage(
        scenario="h6-setsid-descendant",
        unit="run.service",
        lineage="/system.slice/run.service/job-1-eeeeeeeeeeeeeeee",
        expected_job_name="job-1-eeeeeeeeeeeeeeee",
        expected_job_cgroup=(
            "/system.slice/run.service/job-1-eeeeeeeeeeeeeeee"
        ),
    )
    with pytest.raises(adversary.AdversaryError, match="materialized job cgroup"):
        adversary._validate_unit_lineage(
            scenario="h6-setsid-descendant",
            unit="run.service",
            lineage="/system.slice/run.service/job-1-eeeeeeeeeeeeeeee",
            expected_job_name="job-1-eeeeeeeeeeeeeeee",
            expected_job_cgroup=(
                "/system.slice/run.service/job-2-eeeeeeeeeeeeeeee"
            ),
        )
    with pytest.raises(adversary.AdversaryError, match="outside the materialized"):
        adversary._validate_unit_lineage(
            scenario="h6-setsid-descendant",
            unit="run.service",
            lineage="/system.slice/run.service/job-2-eeeeeeeeeeeeeeee",
            expected_job_name="job-1-eeeeeeeeeeeeeeee",
            expected_job_cgroup=(
                "/system.slice/run.service/job-1-eeeeeeeeeeeeeeee"
            ),
        )
    with pytest.raises(adversary.AdversaryError, match="one unified"):
        adversary._unified_cgroup("0::/one\n0::/two\n")
    with pytest.raises(adversary.AdversaryError, match="planned run"):
        adversary._validate_unit_lineage(
            scenario="h2-main-nonzero",
            unit="other.service",
            lineage=main,
        )


@pytest.mark.parametrize(
    ("fixture_name", "allowed_process_functions"),
    [
        ("generic_backend_unit_observer", frozenset()),
        (
            "generic_backend_adversary",
            frozenset({"_setsid_descendant", "_double_fork_descendant"}),
        ),
    ],
)
def test_fixture_ast_closes_process_and_polling_authority(
    fixture_name: str, allowed_process_functions: frozenset[str]
) -> None:
    source_path = _FIXTURE_ROOT / f"{fixture_name}.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    forbidden_imports: set[str] = set()
    process_calls: list[tuple[str | None, str]] = []
    forbidden_calls: list[tuple[str | None, str]] = []

    def qualified_name(node: ast.expr) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            prefix = qualified_name(node.value)
            return None if prefix is None else f"{prefix}.{node.attr}"
        return None

    class AuthorityVisitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.functions: list[str] = []

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self.functions.append(node.name)
            self.generic_visit(node)
            self.functions.pop()

        def visit_Import(self, node: ast.Import) -> None:
            forbidden_imports.update(
                alias.name for alias in node.names if alias.name in {"select", "subprocess"}
            )

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            if node.module in {"select", "subprocess"}:
                forbidden_imports.add(str(node.module))

        def visit_Call(self, node: ast.Call) -> None:
            name = qualified_name(node.func)
            owner = self.functions[-1] if self.functions else None
            if name in {"os.fork", "os.setsid"}:
                process_calls.append((owner, str(name)))
            if name in {
                "os.forkpty",
                "os.kill",
                "os.posix_spawn",
                "os.posix_spawnp",
                "os.system",
                "os.waitpid",
                "select.poll",
                "subprocess.call",
                "subprocess.check_call",
                "subprocess.check_output",
                "subprocess.Popen",
                "subprocess.run",
                "time.sleep",
            }:
                forbidden_calls.append((owner, str(name)))
            if any(keyword.arg == "timeout" for keyword in node.keywords):
                forbidden_calls.append((owner, f"{name}:timeout"))
            self.generic_visit(node)

    AuthorityVisitor().visit(tree)

    assert forbidden_imports == set()
    assert forbidden_calls == []
    if fixture_name == "generic_backend_unit_observer":
        assert process_calls == []
    else:
        assert {owner for owner, _name in process_calls} == allowed_process_functions
        assert sum(name == "os.fork" for _owner, name in process_calls) == 3
        assert sum(name == "os.setsid" for _owner, name in process_calls) == 2


@pytest.mark.parametrize("fixture_name", ["observer", "adversary"])
def test_fifo_plan_identity_is_not_path_only(
    tmp_path: Path,
    request: pytest.FixtureRequest,
    fixture_name: str,
) -> None:
    module = request.getfixturevalue(fixture_name)
    error_type = (
        module.ObserverError if fixture_name == "observer" else module.AdversaryError
    )
    binding = _fifo(tmp_path / "identity.fifo")
    binding["inode"] = str(int(binding["inode"], 10) + 1)

    with pytest.raises(error_type):
        module._open_fifo_pin(binding, label="test FIFO")


@pytest.mark.parametrize("fixture_name", ["observer", "adversary"])
def test_program_hash_mismatch_is_fail_closed(
    request: pytest.FixtureRequest, fixture_name: str
) -> None:
    module = request.getfixturevalue(fixture_name)
    error_type = (
        module.ObserverError if fixture_name == "observer" else module.AdversaryError
    )
    path = Path(module.__file__).resolve()
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    wrong = ("0" if actual[0] != "0" else "1") + actual[1:]

    with pytest.raises(error_type, match="hash"):
        module._verify_program(
            {"program_path": str(path), "program_sha256": wrong}
        )
