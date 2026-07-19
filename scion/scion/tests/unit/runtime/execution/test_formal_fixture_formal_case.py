from __future__ import annotations

import ast
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import signal
import sys
import threading
from types import SimpleNamespace
from types import ModuleType
from typing import Any

import pytest


_FIXTURE = (
    Path(__file__).parents[3]
    / "fixtures"
    / "runtime"
    / "execution"
    / "generic_backend_formal_case.py"
)
_SPAWN_BACKEND = Path(__file__).parents[4] / "runtime" / "execution" / "spawn_backend.py"
_SPAWN_BACKEND_TESTS = Path(__file__).with_name("test_spawn_backend.py")
_ADVERSARY = _FIXTURE.with_name("generic_backend_adversary.py")


def _load_fixture() -> ModuleType:
    spec = importlib.util.spec_from_file_location("test_generic_backend_formal_case", _FIXTURE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_adversary() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "test_generic_backend_adversary", _ADVERSARY
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def formal_case() -> ModuleType:
    return _load_fixture()


@pytest.fixture(scope="module")
def spawn_support() -> ModuleType:
    expected = _SPAWN_BACKEND_TESTS.resolve()
    for loaded in tuple(sys.modules.values()):
        if not isinstance(loaded, ModuleType):
            continue
        loaded_path = getattr(loaded, "__file__", None)
        if loaded_path is not None and Path(loaded_path).resolve() == expected:
            return loaded
    spec = importlib.util.spec_from_file_location(
        "formal_fixture_spawn_backend_test_support", _SPAWN_BACKEND_TESTS
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def _stable_ast_value(value: object) -> object:
    """Encode semantic AST fields without interpreter-specific dump formatting."""

    if isinstance(value, ast.AST):
        return {
            "node": type(value).__name__,
            "fields": [
                [name, _stable_ast_value(field_value)]
                for name, field_value in sorted(ast.iter_fields(value))
            ],
        }
    if type(value) is list:
        return ["list", [_stable_ast_value(item) for item in value]]
    if type(value) is tuple:
        return ["tuple", [_stable_ast_value(item) for item in value]]
    if type(value) is bytes:
        return ["bytes", value.hex()]
    if type(value) is complex:
        return ["complex", [value.real, value.imag]]
    if value is None or type(value) in {bool, int, float, str}:
        return [type(value).__name__, value]
    raise AssertionError(f"unsupported stable AST field value: {type(value).__name__}")


def _stable_ast_hash(node: ast.AST) -> str:
    raw = json.dumps(
        _stable_ast_value(node),
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


_FORBIDDEN_FIXTURE_REFERENCE_NAMES = frozenset(
    {
        "Popen",
        "subprocess",
        "system",
        "systemctl",
        "systemd_run",
        "fork",
        "forkpty",
        "posix_spawn",
        "setsid",
        "kill",
        "killpg",
        "waitpid",
        "poll",
        "select",
        "selectors",
        "sleep",
        "timeout",
        "settimeout",
        "retry",
        "alarm",
        "setitimer",
    }
)
_FORBIDDEN_FIXTURE_POLICY_NAMES = frozenset(
    {
        "cap",
        "truncate",
        "truncation",
        "cleanup",
        "restart",
        "automatic_cleanup",
        "automatic_restart",
    }
)
_OUTPUT_VALUE_NAMES = frozenset(
    {
        "body",
        "buffer",
        "bytes",
        "content",
        "data",
        "event",
        "events",
        "journal",
        "message",
        "messages",
        "output",
        "payload",
        "raw",
        "receipt",
        "record",
        "records",
        "stderr",
        "stdout",
    }
)


def _ast_callable_names(value: ast.expr) -> frozenset[str]:
    names: set[str] = set()
    cursor: ast.expr = value
    while isinstance(cursor, ast.Attribute):
        names.add(cursor.attr)
        cursor = cursor.value
    if isinstance(cursor, ast.Name):
        names.add(cursor.id)
    return frozenset(names)


def _ast_assignment_names(value: ast.expr) -> frozenset[str]:
    if isinstance(value, ast.Name):
        return frozenset({value.id})
    if isinstance(value, ast.Attribute):
        return frozenset({value.attr})
    if isinstance(value, (ast.Tuple, ast.List)):
        return frozenset(
            name
            for item in value.elts
            for name in _ast_assignment_names(item)
        )
    return frozenset()


def _is_fixed_nonnegative_integer(value: ast.expr | None) -> bool:
    if isinstance(value, ast.Constant):
        return type(value.value) is int and value.value >= 0
    if isinstance(value, ast.UnaryOp) and isinstance(value.op, ast.UAdd):
        return _is_fixed_nonnegative_integer(value.operand)
    if isinstance(value, ast.BinOp) and isinstance(
        value.op,
        (ast.Add, ast.Mult, ast.FloorDiv, ast.Mod, ast.Pow, ast.LShift, ast.RShift),
    ):
        return _is_fixed_nonnegative_integer(
            value.left
        ) and _is_fixed_nonnegative_integer(value.right)
    return False


def _output_value_names(value: ast.expr) -> frozenset[str]:
    return frozenset(
        node.id
        for node in ast.walk(value)
        if isinstance(node, ast.Name) and node.id in _OUTPUT_VALUE_NAMES
    )


def _forbidden_fixture_ast_evidence(source: str) -> frozenset[str]:
    """Return executable fixture policy violations without scanning strings."""

    tree = ast.parse(source)
    evidence: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            forbidden_calls = _ast_callable_names(node.func) & (
                _FORBIDDEN_FIXTURE_REFERENCE_NAMES
                | _FORBIDDEN_FIXTURE_POLICY_NAMES
            )
            for name in forbidden_calls:
                evidence.add(f"call:{name}")
        elif isinstance(node, ast.Name):
            if node.id in _FORBIDDEN_FIXTURE_REFERENCE_NAMES:
                evidence.add(f"reference:{node.id}")
        elif isinstance(node, ast.Attribute):
            if node.attr in _FORBIDDEN_FIXTURE_REFERENCE_NAMES:
                evidence.add(f"reference:{node.attr}")
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            imported = (
                {
                    name
                    for alias in node.names
                    for name in (alias.name.split(".", 1)[0], alias.asname)
                    if name is not None
                }
                if isinstance(node, ast.Import)
                else {
                    name
                    for alias in node.names
                    for name in (
                        str(node.module).split(".", 1)[0],
                        alias.name,
                        alias.asname,
                    )
                    if name is not None
                }
            )
            for name in imported & _FORBIDDEN_FIXTURE_REFERENCE_NAMES:
                evidence.add(f"import:{name}")
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
            targets = (
                node.targets
                if isinstance(node, ast.Assign)
                else (node.target,)
            )
            assigned = frozenset(
                name for target in targets for name in _ast_assignment_names(target)
            )
            for name in assigned & _FORBIDDEN_FIXTURE_POLICY_NAMES:
                evidence.add(f"assignment:{name}")
        elif isinstance(node, ast.AugAssign):
            for name in (
                _ast_assignment_names(node.target)
                & _FORBIDDEN_FIXTURE_POLICY_NAMES
            ):
                evidence.add(f"assignment:{name}")
        elif (
            isinstance(node, ast.Subscript)
            and isinstance(node.slice, ast.Slice)
            and node.slice.lower is None
            and node.slice.step is None
            and _is_fixed_nonnegative_integer(node.slice.upper)
            and _output_value_names(node.value)
        ):
            evidence.add("slice:fixed-output-upper-bound")
    return frozenset(evidence)


def _static(path: Path, digest: str | None = None) -> dict[str, str]:
    return {
        "path": str(path),
        "sha256": digest or hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _run_properties(run: str, closer: str) -> tuple[dict[str, str], dict[str, str]]:
    return (
        {
            "CollectMode": "inactive",
            "Delegate": "pids",
            "DelegateSubgroup": "supervisor",
            "KillMode": "control-group",
            "OnFailure": closer,
            "OnSuccess": closer,
            "Restart": "no",
            "TimeoutStopSec": "infinity",
        },
        {
            "CollectMode": "inactive",
            "Delegate": "yes",
            "DelegateControllers": "pids",
            "DelegateSubgroup": "supervisor",
            "Id": run,
            "KillMode": "control-group",
            "OnFailure": closer,
            "OnSuccess": closer,
            "Restart": "no",
            "TimeoutStopUSec": "infinity",
        },
    )


def _fifo(path: Path) -> dict[str, str]:
    os.mkfifo(path, 0o600)
    status = path.lstat()
    return {"path": str(path), "device": str(status.st_dev), "inode": str(status.st_ino)}


def _plan(
    tmp_path: Path,
    formal_case: ModuleType,
    *,
    case_id: str = "B0",
    variant: str = "blocked-sentinel",
) -> tuple[dict[str, Any], dict[str, str]]:
    receipt = tmp_path / "receipt"
    capture = tmp_path / "capture"
    scratch = tmp_path / "scratch"
    for directory in (receipt, capture, scratch):
        directory.mkdir()
    boot = tmp_path / "boot_id"
    boot.write_text("01234567-89ab-cdef-0123-456789abcdef\n", encoding="ascii")
    boot_status = boot.lstat()
    adversary = _ADVERSARY
    probe = tmp_path / "accepted-probe"
    extension = tmp_path / "accepted-extension.so"
    probe.write_bytes(b"probe")
    extension.write_bytes(b"extension")
    configured, expanded = _run_properties("run.service", "close.service")
    outer_acquisition = {
        "armed_receipt_path": str(receipt / "systemd-armed.json"),
        "ready_fifo": _fifo(tmp_path / "systemd-ready.fifo"),
        "release_fifo": _fifo(tmp_path / "systemd-release.fifo"),
    }
    formal_ref = _static(_FIXTURE)
    references = {
        str(_FIXTURE): formal_ref["sha256"],
        str(adversary): hashlib.sha256(adversary.read_bytes()).hexdigest(),
        str(probe): formal_case._EXPECTED_PROBE_SHA256,
        str(extension): formal_case._EXPECTED_EXTENSION_SHA256,
        str(_SPAWN_BACKEND): formal_case._ACCEPTED_SPAWN_BACKEND_SHA256,
    }
    plan: dict[str, Any] = {
        "accepted_extension": _static(extension, formal_case._EXPECTED_EXTENSION_SHA256),
        "accepted_probe": _static(probe, formal_case._EXPECTED_PROBE_SHA256),
        "accepted_spawn_backend": _static(
            _SPAWN_BACKEND, formal_case._ACCEPTED_SPAWN_BACKEND_SHA256
        ),
        "adversary_script": _static(adversary),
        "armed_receipt_name": "armed.json",
        "b6": None,
        "boot_id_file": {
            "path": str(boot),
            "device": str(boot_status.st_dev),
            "inode": str(boot_status.st_ino),
        },
        "capture_directory": str(capture),
        "case_id": case_id,
        "case_script": dict(formal_ref),
        "close_unit": "close.service",
        "control_fifo": None,
        "descendant_adversary_plan": None,
        "final_config_path": str(scratch / "materialized-config.json"),
        "fixture_gid": str(os.getgid()),
        "fixture_uid": str(os.getuid()),
        "formal_program": dict(formal_ref),
        "invocation_nonce": "a" * 64,
        "ordinal": "7",
        "receipt_directory": str(receipt),
        "receipt_name": "final.json",
        "role": "formal-case",
        "run_configured_directives": configured,
        "run_expanded_properties": expanded,
        "run_unit": "run.service",
        "schema": "scion.generic-backend.formal-plan.v1",
        "scratch_directory": str(scratch),
        "systemd_acquisition": outer_acquisition,
        "variant": variant,
    }
    return plan, references


def _attach_descendant_plan(
    tmp_path: Path,
    formal_case: ModuleType,
    plan: dict[str, Any],
) -> dict[str, Any]:
    control = _fifo(tmp_path / "control.fifo")
    plan["control_fifo"] = control
    descendant_path = tmp_path / "descendant-plan.json"
    descendant = {
        "schema": formal_case._DESCENDANT_PLAN_SCHEMA,
        "scenario": formal_case._expected_descendant_scenario(
            str(plan["case_id"]), str(plan["variant"])
        ),
        "unit": plan["run_unit"],
        "expected_job_name": "job-7-aaaaaaaaaaaaaaaa",
        "program_path": plan["adversary_script"]["path"],
        "program_sha256": plan["adversary_script"]["sha256"],
        "request_path": str(tmp_path / "descendant-request.json"),
        "receipt_path": str(tmp_path / "descendant-receipt.json"),
        "acquisition": None,
        "hold_release_fifo": control,
    }
    descendant_path.write_bytes(_canonical(descendant))
    plan["descendant_adversary_plan"] = _static(descendant_path)
    return descendant


def _install_static_hash_stub(
    monkeypatch: pytest.MonkeyPatch,
    formal_case: ModuleType,
    references: dict[str, str],
) -> None:
    def frozen_hash(path: str) -> str:
        return references[path]

    monkeypatch.setattr(formal_case, "_sha256_file", frozen_hash)
    monkeypatch.setattr(
        formal_case,
        "_require_sealed_fifo_authority",
        lambda reference, fixture_uid, fixture_gid, label: None,
    )


def test_plan_decode_is_canonical_exact_and_duplicate_rejecting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    formal_case: ModuleType,
) -> None:
    plan, references = _plan(tmp_path, formal_case)
    _install_static_hash_stub(monkeypatch, formal_case, references)
    path = tmp_path / "plan.json"
    path.write_bytes(_canonical(plan))

    decoded, digest = formal_case._load_plan(str(path))
    assert decoded == plan
    assert digest == hashlib.sha256(_canonical(plan)).hexdigest()

    unknown = dict(plan, unknown=True)
    path.write_bytes(_canonical(unknown))
    with pytest.raises(formal_case.FixtureError, match="unknown"):
        formal_case._load_plan(str(path))

    missing = dict(plan)
    del missing["role"]
    path.write_bytes(_canonical(missing))
    with pytest.raises(formal_case.FixtureError, match="missing"):
        formal_case._load_plan(str(path))

    path.write_bytes(b'{"schema":"one","schema":"two"}\n')
    with pytest.raises(formal_case.FixtureError, match="duplicate JSON key"):
        formal_case._load_plan(str(path))

    path.write_text(json.dumps(plan, indent=2), encoding="ascii")
    with pytest.raises(formal_case.FixtureError, match="canonical JSON"):
        formal_case._load_plan(str(path))


def test_materialized_config_adds_only_same_pid_dynamic_lineage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    formal_case: ModuleType,
) -> None:
    plan, references = _plan(tmp_path, formal_case)
    _install_static_hash_stub(monkeypatch, formal_case, references)
    formal_case._validate_plan(plan)
    assert "invocation_lineage" not in plan
    lineage = {
        "BootID": "01234567-89ab-cdef-0123-456789abcdef",
        "ControlGroup": "/system.slice/run.service",
        "Id": "run.service",
        "InvocationID": "b" * 32,
        "MainPID": "123",
        "MainStartTime": "456",
        "ServiceDevice": "7",
        "ServiceInode": "8",
        "SupervisorDevice": "7",
        "SupervisorInode": "9",
    }
    config = formal_case._materialized_config(
        plan,
        plan_sha256="c" * 64,
        invocation_lineage=lineage,
        systemd_armed_receipt_sha256="d" * 64,
    )

    formal_case._validate_config(config)
    assert config["invocation_lineage"] == lineage
    assert config["ordinal"] == 7
    assert config["plan_sha256"] == "c" * 64
    assert config["accepted_spawn_backend_sha256"] == references[str(_SPAWN_BACKEND)]
    assert set(config["directory_authorities"]) == {
        "receipt_directory",
        "capture_directory",
        "scratch_directory",
    }
    for name, authority in config["directory_authorities"].items():
        assert authority["path"] == plan[name]
        assert set(authority) == {"path", "device", "inode", "mode", "uid", "gid"}


def test_execute_plan_runs_outer_same_pid_acquisition_and_real_b8_entry_as_one_flow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    formal_case: ModuleType,
) -> None:
    import scion.runtime.execution as execution

    plan, references = _plan(
        tmp_path, formal_case, case_id="B8", variant="final-inventory"
    )
    plan_path = tmp_path / "plan.json"
    plan_path.write_bytes(_canonical(plan))
    starttime = formal_case._proc_starttime(os.getpid())
    invocation = "b" * 32
    lineage_mapping = {
        "BootID": "01234567-89ab-cdef-0123-456789abcdef",
        "ControlGroup": "/fixture.slice/run.service",
        "Id": "run.service",
        "InvocationID": invocation,
        "MainPID": str(os.getpid()),
        "MainStartTime": str(starttime),
        "ServiceDevice": "7",
        "ServiceInode": "8",
        "SupervisorDevice": "7",
        "SupervisorInode": "9",
    }
    lineage = execution.InvocationLineage.from_properties(
        tuple(lineage_mapping.items())
    )
    derive_pids: list[int] = []

    def derive_same_pid(value: object) -> dict[str, str]:
        assert value == plan
        derive_pids.append(os.getpid())
        return dict(lineage_mapping)

    real_hash = formal_case._sha256_file

    def frozen_or_live_hash(path: str) -> str:
        return references.get(path, real_hash(path))

    class Backend:
        def __init__(self) -> None:
            self.state = "IDLE"
            self.entries: list[tuple[str, int]] = []

        def close_idle(self) -> None:
            self.entries.append(("B8.close_idle", os.getpid()))
            self.state = "CLOSED"

    backend = Backend()
    inventory = {
        "fds": [{"fd": 0}],
        "tasks": [{"tid": os.getpid(), "starttime": starttime}],
        "current_unified_cgroup": "/fixture.slice/run.service/supervisor",
        "cgroups": {
            "control_group": "/fixture.slice/run.service",
            "directories": [
                {
                    "relative": ".",
                    "device": 7,
                    "inode": 8,
                    "children": ["supervisor"],
                    "cgroup.procs": b"",
                    "cgroup.events": b"populated 1\nfrozen 0\n",
                    "cgroup.controllers": b"pids\n",
                }
            ],
        },
    }
    monkeypatch.setattr(formal_case, "_sha256_file", frozen_or_live_hash)
    monkeypatch.setattr(
        formal_case,
        "_require_sealed_fifo_authority",
        lambda reference, fixture_uid, fixture_gid, label: None,
    )
    monkeypatch.setattr(formal_case, "_derive_same_pid_lineage", derive_same_pid)
    monkeypatch.setattr(formal_case, "_current_invocation_id", lambda: invocation)
    real_read_bytes = formal_case._read_bytes
    monkeypatch.setattr(
        formal_case,
        "_read_bytes",
        lambda path: (
            b"0::/fixture.slice/run.service/supervisor\n"
            if path == "/proc/self/cgroup"
            else real_read_bytes(path)
        ),
    )
    monkeypatch.setattr(
        formal_case,
        "_fixture_identity",
        lambda config, config_sha256: {
            "config_sha256": config_sha256,
            "case_script": config["case_script"],
        },
    )
    monkeypatch.setattr(formal_case, "_inventory", lambda control_group: inventory)
    monkeypatch.setattr(
        formal_case,
        "_open_backend",
        lambda actual_execution, config, allow_open_failure=False: (
            backend,
            lineage,
        ),
    )

    outer_ready = str(plan["systemd_acquisition"]["ready_fifo"]["path"])
    outer_release = str(plan["systemd_acquisition"]["release_fifo"]["path"])
    coordinator_errors: list[BaseException] = []

    def coordinate_outer_acquisition() -> None:
        try:
            ready_fd = os.open(outer_ready, os.O_RDONLY | os.O_CLOEXEC)
            try:
                assert formal_case._read_all(ready_fd) == formal_case._READY_BYTES
            finally:
                os.close(ready_fd)
            release_fd = os.open(outer_release, os.O_WRONLY | os.O_CLOEXEC)
            try:
                formal_case._write_all(release_fd, formal_case._RELEASE_BYTES)
            finally:
                os.close(release_fd)
        except BaseException as exc:
            coordinator_errors.append(exc)

    coordinator = threading.Thread(target=coordinate_outer_acquisition)
    coordinator.start()
    assert formal_case._execute_plan(str(plan_path)) == 0
    coordinator.join()
    assert coordinator_errors == []
    assert derive_pids == [os.getpid(), os.getpid()]
    assert backend.entries == [("B8.close_idle", os.getpid())]
    config = json.loads(Path(plan["final_config_path"]).read_text(encoding="ascii"))
    assert config["invocation_lineage"] == lineage_mapping
    receipt = json.loads(
        (Path(plan["receipt_directory"]) / plan["receipt_name"]).read_text(
            encoding="ascii"
        )
    )
    assert receipt["outcome"] == "PASS"
    assert receipt["case_result"] == {"hashes_verified": True}
    assert receipt["final_inventory_proof"] == {
        "fd_returned_to_baseline": True,
        "task_returned_to_baseline": True,
        "cgroup_proof": {"kind": "RETURNED_TO_BASELINE"},
    }


def test_same_pid_lineage_is_derived_from_live_environment_proc_and_dirfds(
    monkeypatch: pytest.MonkeyPatch,
    formal_case: ModuleType,
) -> None:
    real_os = formal_case.os
    open_events: list[tuple[object, ...]] = []
    descriptors = iter((10, 11, 12, 13))

    class FakeOS:
        O_RDONLY = real_os.O_RDONLY
        O_DIRECTORY = real_os.O_DIRECTORY
        O_CLOEXEC = real_os.O_CLOEXEC
        O_NOFOLLOW = getattr(real_os, "O_NOFOLLOW", 0)

        @staticmethod
        def getpid() -> int:
            return 321

        @staticmethod
        def open(path: str, flags: int, *, dir_fd: int | None = None) -> int:
            descriptor = next(descriptors)
            open_events.append(("open", path, flags, dir_fd, descriptor))
            return descriptor

        @staticmethod
        def fstat(descriptor: int) -> object:
            if descriptor == 12:
                return SimpleNamespace(st_dev=7, st_ino=8)
            if descriptor == 13:
                return SimpleNamespace(st_dev=7, st_ino=9)
            raise AssertionError(f"unexpected fstat descriptor {descriptor}")

        @staticmethod
        def close(descriptor: int) -> None:
            open_events.append(("close", descriptor))

    monkeypatch.setattr(formal_case, "os", FakeOS)
    monkeypatch.setattr(formal_case, "_proc_starttime", lambda pid: 456)
    monkeypatch.setattr(formal_case, "_current_invocation_id", lambda: "b" * 32)
    monkeypatch.setattr(
        formal_case,
        "_read_bytes",
        lambda path: b"0::/fixture.slice/run.service/supervisor\n",
    )
    monkeypatch.setattr(
        formal_case,
        "_read_pinned_boot_id",
        lambda plan: "01234567-89ab-cdef-0123-456789abcdef",
    )

    lineage = formal_case._derive_same_pid_lineage(
        {"run_unit": "run.service", "boot_id_file": {}}
    )

    assert lineage == {
        "BootID": "01234567-89ab-cdef-0123-456789abcdef",
        "Id": "run.service",
        "InvocationID": "b" * 32,
        "ControlGroup": "/fixture.slice/run.service",
        "ServiceDevice": "7",
        "ServiceInode": "8",
        "SupervisorDevice": "7",
        "SupervisorInode": "9",
        "MainPID": "321",
        "MainStartTime": "456",
    }
    flags = (
        real_os.O_RDONLY
        | real_os.O_DIRECTORY
        | real_os.O_CLOEXEC
        | real_os.O_NOFOLLOW
    )
    assert [event for event in open_events if event[0] == "open"] == [
        ("open", "/sys/fs/cgroup", flags, None, 10),
        ("open", "fixture.slice", flags, 10, 11),
        ("open", "run.service", flags, 11, 12),
        ("open", "supervisor", flags, 12, 13),
    ]


def test_atomic_publication_is_canonical_and_no_replace(
    tmp_path: Path, formal_case: ModuleType
) -> None:
    path = tmp_path / "published.json"
    digest = formal_case._write_static_json_no_replace(str(path), {"value": 1})
    assert path.read_bytes() == b'{"value":1}\n'
    assert digest == hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(FileExistsError):
        formal_case._write_static_json_no_replace(str(path), {"value": 2})
    assert path.read_bytes() == b'{"value":1}\n'
    assert not list(tmp_path.glob(".published.json.pending-*"))


def test_b6_plan_reuses_exact_fifo_schema_and_cannot_choose_a_callable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    formal_case: ModuleType,
) -> None:
    plan, references = _plan(
        tmp_path,
        formal_case,
        case_id="B6",
        variant="issuer-blocked",
    )
    acquisition = {
        "armed_receipt_path": str(Path(plan["receipt_directory"]) / "b6-armed.json"),
        "operation_receipt_path": str(
            Path(plan["receipt_directory"]) / "b6-operation.json"
        ),
        "ready_fifo": _fifo(tmp_path / "ready.fifo"),
        "release_fifo": _fifo(tmp_path / "release.fifo"),
    }
    plan["b6"] = {
        **formal_case._B6_ABI["issuer-blocked"],
        "acquisition": acquisition,
    }
    _install_static_hash_stub(monkeypatch, formal_case, references)
    formal_case._validate_plan(plan)

    wrong_hook = dict(plan["b6"])
    wrong_hook["hook"] = "caller-selected.attribute"
    plan["b6"] = wrong_hook
    with pytest.raises(formal_case.FixtureError, match="frozen ABI"):
        formal_case._validate_plan(plan)


def test_b6_unobservable_source_seam_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    formal_case: ModuleType,
) -> None:
    plan, references = _plan(
        tmp_path,
        formal_case,
        case_id="B6",
        variant="storage-blocked",
    )
    plan["b6"] = {
        **formal_case._B6_ABI["storage-blocked"],
        "acquisition": {
            "armed_receipt_path": str(
                Path(plan["receipt_directory"]) / "b6-armed.json"
            ),
            "operation_receipt_path": str(
                Path(plan["receipt_directory"]) / "b6-operation.json"
            ),
            "ready_fifo": _fifo(tmp_path / "ready.fifo"),
            "release_fifo": _fifo(tmp_path / "release.fifo"),
        },
    }
    _install_static_hash_stub(monkeypatch, formal_case, references)
    formal_case._validate_plan(plan)
    lineage = {
        "BootID": "01234567-89ab-cdef-0123-456789abcdef",
        "ControlGroup": "/system.slice/run.service",
        "Id": "run.service",
        "InvocationID": "b" * 32,
        "MainPID": "123",
        "MainStartTime": "456",
        "ServiceDevice": "7",
        "ServiceInode": "8",
        "SupervisorDevice": "7",
        "SupervisorInode": "9",
    }
    config = formal_case._materialized_config(
        plan,
        plan_sha256="c" * 64,
        invocation_lineage=lineage,
        systemd_armed_receipt_sha256="d" * 64,
    )
    controller = formal_case._B6FaultController(config, {}, None)
    with pytest.raises(formal_case.RequirementMissing) as error:
        controller.install(ModuleType("accepted_spawn_backend"))
    assert error.value.code == "B6_EXACT_GUARDED_SEAM"


def test_b6_abi_has_no_implicitly_unimplemented_hook(
    formal_case: ModuleType,
) -> None:
    advertised = {str(entry["hook"]) for entry in formal_case._B6_ABI.values()}
    unavailable = {"unobservable-source-seam", "native-spawn-no-handle"}
    assert advertised - unavailable == set(formal_case._B6_INSTALLABLE_HOOKS)
    install_source = inspect.getsource(formal_case._B6FaultController.install)
    for hook in formal_case._B6_INSTALLABLE_HOOKS:
        assert f'if hook == "{hook}"' in install_source
    assert (
        formal_case._B6_ABI["issuer-empty-before-eof"]["hook"]
        == "unobservable-source-seam"
    )


def test_sigusr1_handler_is_raise_only_and_restores_exact_state(
    formal_case: ModuleType,
) -> None:
    tree = ast.parse(inspect.getsource(formal_case._b6_sigusr1_handler))
    function = tree.body[0]
    assert isinstance(function, ast.FunctionDef)
    assert len(function.body) == 1
    assert isinstance(function.body[0], ast.Raise)
    prior_mask = frozenset(signal.pthread_sigmask(signal.SIG_BLOCK, set()))
    prior_pending = frozenset(signal.sigpending())
    if signal.SIGUSR1 in prior_mask or signal.SIGUSR1 in prior_pending:
        pytest.skip("test process already owns non-default SIGUSR1 signal state")
    prior_disposition = signal.getsignal(signal.SIGUSR1)
    context = formal_case._B6SignalContext()
    assert signal.getsignal(signal.SIGUSR1) is formal_case._b6_sigusr1_handler
    restored = context.restore()
    assert restored["restored_mask"] == sorted(int(value) for value in prior_mask)
    assert signal.getsignal(signal.SIGUSR1) is prior_disposition


def test_b6_fifo_protocol_arms_then_ready_then_release_and_proves_pending(
    monkeypatch: pytest.MonkeyPatch,
    formal_case: ModuleType,
) -> None:
    events: list[tuple[object, ...]] = []
    real_os = formal_case.os

    class FakeOS:
        path = real_os.path
        O_WRONLY = real_os.O_WRONLY
        O_RDONLY = real_os.O_RDONLY
        O_CLOEXEC = real_os.O_CLOEXEC
        O_NOFOLLOW = getattr(real_os, "O_NOFOLLOW", 0)

        @staticmethod
        def getpid() -> int:
            return real_os.getpid()

        @staticmethod
        def open(path: str, flags: int) -> int:
            descriptor = 41 if path.endswith("ready.fifo") else 42
            events.append(("open", path, flags, descriptor))
            return descriptor

        @staticmethod
        def close(descriptor: int) -> None:
            events.append(("close", descriptor))

    class FakeSignal:
        SIGUSR1 = 10
        SIG_BLOCK = 0

        def __init__(self) -> None:
            self.pending_calls = 0

        def pthread_sigmask(self, how: int, values: set[object]) -> set[int]:
            assert how == self.SIG_BLOCK and values == set()
            return {self.SIGUSR1}

        def sigpending(self) -> set[int]:
            self.pending_calls += 1
            return set() if self.pending_calls == 1 else {self.SIGUSR1}

    class SignalContext:
        @staticmethod
        def entry_fact() -> dict[str, object]:
            return {"handler_source_sha256": "a" * 64}

    acquisition = {
        "armed_receipt_path": "/work/armed.json",
        "operation_receipt_path": "/work/operation.json",
        "ready_fifo": {"path": "/fifo/ready.fifo", "device": "1", "inode": "2"},
        "release_fifo": {"path": "/fifo/release.fifo", "device": "1", "inode": "3"},
    }
    b6 = {**formal_case._B6_ABI["issuer-blocked"], "acquisition": acquisition}
    config = {
        "b6": b6,
        "case_id": "B6",
        "variant": "issuer-blocked",
        "run_unit": "run.service",
        "invocation_lineage": {},
        "plan_sha256": "c" * 64,
        "systemd_armed_receipt_sha256": "d" * 64,
    }
    controller = formal_case._B6FaultController(config, {}, SignalContext())

    monkeypatch.setattr(formal_case, "os", FakeOS)
    monkeypatch.setattr(formal_case, "signal", FakeSignal())
    monkeypatch.setattr(
        formal_case,
        "_write_static_json_no_replace",
        lambda path, receipt: events.append(("armed", path, receipt["schema"])) or "b" * 64,
    )
    monkeypatch.setattr(
        formal_case,
        "_require_open_fifo_identity",
        lambda descriptor, expected, label: events.append(
            ("identity", descriptor, expected, label)
        ),
    )
    monkeypatch.setattr(
        formal_case,
        "_write_all",
        lambda descriptor, data: events.append(("write", descriptor, data)),
    )
    monkeypatch.setattr(formal_case, "_read_all", lambda descriptor: formal_case._RELEASE_BYTES)
    monkeypatch.setattr(formal_case, "_fifo_reference", lambda value, label: value)
    monkeypatch.setattr(
        formal_case,
        "_formal_process_identity",
        lambda plan, lineage: {"pid": real_os.getpid(), "starttime": 456},
    )
    monkeypatch.setattr(formal_case, "_proc_starttime", lambda pid: 456)

    controller._arm_and_wait()

    assert events[0] == (
        "armed",
        "/work/armed.json",
        "scion.generic_backend.b6_armed.v1",
    )
    ready_open = events[1]
    assert ready_open[:2] == ("open", "/fifo/ready.fifo")
    assert ready_open[2] == real_os.O_WRONLY | real_os.O_CLOEXEC | real_os.O_NOFOLLOW
    assert ("write", 41, formal_case._READY_BYTES) in events
    release_open = next(event for event in events if event[:2] == ("open", "/fifo/release.fifo"))
    assert release_open[2] == real_os.O_RDONLY | real_os.O_CLOEXEC | real_os.O_NOFOLLOW
    assert controller.after_fact["pending_after_release"] == [10]
    assert controller.triggered is True


def test_b5_environment_transport_is_exact_and_sorted(formal_case: ModuleType) -> None:
    class GenericProcessSpec:
        @classmethod
        def create(cls, **kwargs: object) -> object:
            return kwargs

    execution = ModuleType("execution")
    execution.GenericProcessSpec = GenericProcessSpec
    config = {
        "case_id": "B5",
        "variant": "setsid-retain-stdio",
        "scratch_directory": "/tmp/scion-formal-scratch",
    }
    invocation = "d" * 32
    environment = tuple(
        sorted((b"INVOCATION_ID=" + invocation.encode("ascii"), b"LC_ALL=C"))
    )
    result = formal_case._new_spec(
        execution,
        config,
        (b"/usr/bin/python3.12", b"adversary.py"),
        environment=environment,
    )
    assert result["environment"] == (
        b"INVOCATION_ID=" + invocation.encode("ascii"),
        b"LC_ALL=C",
    )


@pytest.mark.parametrize(
    "variant", ("setsid-retain-stdio", "double-fork-close-stdio")
)
def test_b5_public_case_flow_pins_hold_fifo_but_never_opens_a_writer(
    variant: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    formal_case: ModuleType,
) -> None:
    plan, _ = _plan(tmp_path, formal_case, case_id="B5", variant=variant)
    descendant = _attach_descendant_plan(tmp_path, formal_case, plan)
    invocation = "b" * 32
    lineage_mapping = {
        "BootID": "01234567-89ab-cdef-0123-456789abcdef",
        "ControlGroup": "/fixture.slice/run.service",
        "Id": "run.service",
        "InvocationID": invocation,
        "MainPID": str(os.getpid()),
        "MainStartTime": "456",
        "ServiceDevice": "7",
        "ServiceInode": "8",
        "SupervisorDevice": "7",
        "SupervisorInode": "9",
    }
    config = formal_case._materialized_config(
        plan,
        plan_sha256="c" * 64,
        invocation_lineage=lineage_mapping,
        systemd_armed_receipt_sha256="d" * 64,
    )
    execution = ModuleType("b5_execution")

    class GenericProcessSpec:
        def __init__(self, values: dict[str, object]) -> None:
            self.values = values

        @classmethod
        def create(cls, **kwargs: object) -> "GenericProcessSpec":
            return cls(dict(kwargs))

        def to_mapping(self) -> dict[str, object]:
            return dict(self.values)

    class JobCgroupKey:
        @classmethod
        def create(cls, **kwargs: object) -> object:
            return SimpleNamespace(**kwargs)

    class BlockedSpawn:
        def __init__(self, spec: GenericProcessSpec) -> None:
            self.process_identity = SimpleNamespace(
                pid=101, proc_starttime_ticks=201
            )
            self.cgroup_identity = SimpleNamespace(
                job_name=descendant["expected_job_name"]
            )
            self.process_spec_sha256 = "e" * 64
            self.spec = spec

    descendant_reason = object()

    class ContainedSpawnFailure:
        def __init__(self, digest: str) -> None:
            self.reason = descendant_reason
            self.process_spec_sha256 = digest

    execution.GenericProcessSpec = GenericProcessSpec
    execution.JobCgroupKey = JobCgroupKey
    execution.BlockedSpawn = BlockedSpawn
    execution.ContainedSpawnFailure = ContainedSpawnFailure
    execution.ContainedSpawnReason = SimpleNamespace(
        DESCENDANT_SURVIVED=descendant_reason
    )

    class Backend:
        def __init__(self) -> None:
            self.started: list[tuple[object, GenericProcessSpec]] = []

        def start_blocked(
            self, key: object, spec: GenericProcessSpec
        ) -> BlockedSpawn:
            self.started.append((key, spec))
            return BlockedSpawn(spec)

        def release_and_collect(
            self, blocked: BlockedSpawn
        ) -> ContainedSpawnFailure:
            return ContainedSpawnFailure(blocked.process_spec_sha256)

    validated: list[dict[str, object]] = []

    def validate_descendant(*args: object, **kwargs: object) -> dict[str, object]:
        del args
        validated.append(dict(kwargs))
        return {"validated": True, "scenario": descendant["scenario"]}

    monkeypatch.setattr(
        formal_case, "_validate_descendant_receipt", validate_descendant
    )
    monkeypatch.setattr(formal_case, "_current_invocation_id", lambda: invocation)
    real_open = os.open
    hold_opens: list[int] = []

    def observed_open(
        path: object,
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        if path == plan["control_fifo"]["path"]:
            hold_opens.append(flags)
        if dir_fd is None:
            return real_open(path, flags, mode)
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(formal_case.os, "open", observed_open)
    lineage = SimpleNamespace(
        invocation_id=invocation,
        boot_id=lineage_mapping["BootID"],
        control_group=lineage_mapping["ControlGroup"],
    )
    backend = Backend()
    result = formal_case._case_b5(execution, config, backend, lineage)

    assert result["outcome"] == "PASS"
    assert type(result["failure"]) is ContainedSpawnFailure
    assert result["transported_environment"] == (
        b"INVOCATION_ID=" + invocation.encode("ascii"),
        b"LC_ALL=C",
    )
    assert len(backend.started) == 1
    transported = backend.started[0][1].values["environment"]
    assert transported == result["transported_environment"]
    assert validated[0]["require_live_descendant"] is False
    assert validated[0]["expected_job_cgroup"] == (
        lineage.control_group + "/" + descendant["expected_job_name"]
    )
    assert len(hold_opens) == 1
    assert hold_opens[0] & getattr(os, "O_PATH", 0)
    assert hold_opens[0] & os.O_ACCMODE != os.O_WRONLY


def test_outer_acquisition_publishes_exact_armed_receipt_before_release(
    monkeypatch: pytest.MonkeyPatch,
    formal_case: ModuleType,
) -> None:
    events: list[tuple[object, ...]] = []
    process_identity = {"pid": 321, "starttime": 654}
    program = {
        "path": str(_FIXTURE),
        "sha256": "a" * 64,
        "identity": {"device": 1, "inode": 2, "mode": 0o755},
    }
    acquisition = {
        "armed_receipt_path": "/receipts/systemd-armed.json",
        "ready_fifo": {"path": "/fifo/ready", "device": "7", "inode": "8"},
        "release_fifo": {"path": "/fifo/release", "device": "7", "inode": "9"},
    }
    plan = {
        "case_id": "B1",
        "variant": "clean",
        "run_unit": "run.service",
        "final_config_path": "/scratch/config.json",
        "formal_program": {"path": str(_FIXTURE), "sha256": "a" * 64},
        "systemd_acquisition": acquisition,
    }
    lineage = {"InvocationID": "b" * 32}

    class FakeOS:
        path = os.path
        O_WRONLY = os.O_WRONLY
        O_RDONLY = os.O_RDONLY
        O_CLOEXEC = os.O_CLOEXEC
        O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)

        @staticmethod
        def open(path: str, flags: int) -> int:
            descriptor = 31 if path.endswith("ready") else 32
            events.append(("open", path, flags, descriptor))
            return descriptor

        @staticmethod
        def close(descriptor: int) -> None:
            events.append(("close", descriptor))

    monkeypatch.setattr(formal_case, "os", FakeOS)
    monkeypatch.setattr(
        formal_case, "_acquisition_reference", lambda value, label: value
    )
    monkeypatch.setattr(
        formal_case,
        "_formal_process_identity",
        lambda value, current_lineage: dict(process_identity),
    )
    monkeypatch.setattr(formal_case, "_program_receipt", lambda reference: dict(program))
    monkeypatch.setattr(
        formal_case,
        "_write_static_json_no_replace",
        lambda path, receipt: events.append(("armed", path, receipt)) or "c" * 64,
    )
    monkeypatch.setattr(
        formal_case,
        "_require_open_fifo_identity",
        lambda descriptor, identity, label: events.append(
            ("identity", descriptor, identity, label)
        ),
    )
    monkeypatch.setattr(
        formal_case,
        "_write_all",
        lambda descriptor, value: events.append(("write", descriptor, value)),
    )
    monkeypatch.setattr(formal_case, "_read_all", lambda descriptor: formal_case._RELEASE_BYTES)
    monkeypatch.setattr(formal_case, "_derive_same_pid_lineage", lambda value: dict(lineage))
    monkeypatch.setattr(formal_case, "_sha256_file", lambda path: "d" * 64)

    digest = formal_case._perform_systemd_acquisition(
        plan,
        plan_path="/plans/formal.json",
        plan_sha256="d" * 64,
        lineage=lineage,
    )

    assert digest == "c" * 64
    assert events[0][0:2] == ("armed", "/receipts/systemd-armed.json")
    armed = events[0][2]
    assert set(armed) == {
        "schema",
        "case_id",
        "variant",
        "unit",
        "process_identity",
        "plan_path",
        "plan_sha256",
        "program",
        "final_config_path",
        "ready_fifo",
        "release_fifo",
        "ready_sha256",
        "release_sha256",
    }
    assert armed["schema"] == "scion.generic_backend.formal_run_armed.v1"
    assert armed["process_identity"] == process_identity
    assert next(event for event in events if event[0] == "write") == (
        "write",
        31,
        formal_case._READY_BYTES,
    )


def test_control_and_descendant_ownership_matrix_is_closed(
    formal_case: ModuleType,
) -> None:
    controls = {
        (case_id, variant)
        for case_id, variants in formal_case._CASE_VARIANTS.items()
        for variant in variants
        if formal_case._control_required(case_id, variant)
    }
    assert controls == {
        ("B4", "release-after-job-kill"),
        ("B5", "setsid-retain-stdio"),
        ("B5", "double-fork-close-stdio"),
        ("B6", "issuer-reaped-populated"),
        *(("B7", variant) for variant in formal_case._EXTERNAL_B7_VARIANTS),
    }
    descendants = {
        (case_id, variant)
        for case_id, variants in formal_case._CASE_VARIANTS.items()
        for variant in variants
        if formal_case._descendant_required(case_id, variant)
    }
    assert descendants == {
        ("B5", "setsid-retain-stdio"),
        ("B5", "double-fork-close-stdio"),
        ("B6", "issuer-reaped-populated"),
    }
    assert formal_case._INTERNAL_B7_VARIANTS.isdisjoint(
        formal_case._EXTERNAL_B7_VARIANTS
    )


def test_plan_rejects_global_asset_alias_before_outer_acquisition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    formal_case: ModuleType,
) -> None:
    plan, references = _plan(tmp_path, formal_case)
    _install_static_hash_stub(monkeypatch, formal_case, references)
    plan["final_config_path"] = str(
        Path(plan["receipt_directory"]) / plan["receipt_name"]
    )
    plan_path = tmp_path / "plan.json"
    plan_path.write_bytes(_canonical(plan))
    acquisition_calls = 0

    def forbidden_acquisition(*args: object, **kwargs: object) -> str:
        nonlocal acquisition_calls
        del args, kwargs
        acquisition_calls += 1
        raise AssertionError("outer acquisition must not begin after alias rejection")

    monkeypatch.setattr(
        formal_case, "_perform_systemd_acquisition", forbidden_acquisition
    )
    with pytest.raises(formal_case.FixtureError, match="overlap"):
        formal_case._execute_plan(str(plan_path))
    assert acquisition_calls == 0


@pytest.mark.parametrize("nested_authority", ("static_in_directory", "directories"))
def test_plan_rejects_nested_static_and_dynamic_directory_authorities(
    nested_authority: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    formal_case: ModuleType,
) -> None:
    plan, references = _plan(tmp_path, formal_case)
    if nested_authority == "static_in_directory":
        nested_probe = Path(plan["scratch_directory"]) / "accepted-probe"
        nested_probe.write_bytes(b"nested probe")
        plan["accepted_probe"] = _static(
            nested_probe, formal_case._EXPECTED_PROBE_SHA256
        )
        references[str(nested_probe)] = formal_case._EXPECTED_PROBE_SHA256
    else:
        old_capture = Path(plan["capture_directory"])
        old_capture.rmdir()
        nested_capture = Path(plan["receipt_directory"]) / "capture"
        nested_capture.mkdir()
        plan["capture_directory"] = str(nested_capture)
    _install_static_hash_stub(monkeypatch, formal_case, references)

    with pytest.raises(formal_case.FixtureError, match="nested"):
        formal_case._validate_plan(plan)


def test_existing_dynamic_output_rejects_before_outer_acquisition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    formal_case: ModuleType,
) -> None:
    plan, references = _plan(tmp_path, formal_case)
    _install_static_hash_stub(monkeypatch, formal_case, references)
    final_receipt = Path(plan["receipt_directory"]) / plan["receipt_name"]
    final_receipt.write_bytes(b"preexisting\n")
    plan_path = tmp_path / "plan.json"
    plan_path.write_bytes(_canonical(plan))
    acquisition_calls: list[object] = []
    monkeypatch.setattr(
        formal_case,
        "_perform_systemd_acquisition",
        lambda *args, **kwargs: acquisition_calls.append((args, kwargs)),
    )

    with pytest.raises(formal_case.FixtureError, match="exists before acquisition"):
        formal_case._execute_plan(str(plan_path))
    assert acquisition_calls == []


def test_existing_final_output_rejects_again_at_b_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    formal_case: ModuleType,
) -> None:
    plan, references = _plan(tmp_path, formal_case)
    _install_static_hash_stub(monkeypatch, formal_case, references)
    lineage = {
        "BootID": "01234567-89ab-cdef-0123-456789abcdef",
        "ControlGroup": "/system.slice/run.service",
        "Id": "run.service",
        "InvocationID": "b" * 32,
        "MainPID": "123",
        "MainStartTime": "456",
        "ServiceDevice": "7",
        "ServiceInode": "8",
        "SupervisorDevice": "7",
        "SupervisorInode": "9",
    }
    config = formal_case._materialized_config(
        plan,
        plan_sha256="c" * 64,
        invocation_lineage=lineage,
        systemd_armed_receipt_sha256="d" * 64,
    )
    final_receipt = Path(plan["receipt_directory"]) / plan["receipt_name"]
    final_receipt.write_bytes(b"preexisting\n")

    with pytest.raises(formal_case.FixtureError, match="already exists"):
        formal_case._validate_config(config)


@pytest.mark.parametrize("drift", ("mode", "inode"))
def test_frozen_directory_authorities_reject_drift(
    drift: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    formal_case: ModuleType,
) -> None:
    plan, references = _plan(tmp_path, formal_case)
    _install_static_hash_stub(monkeypatch, formal_case, references)
    lineage = {
        "BootID": "01234567-89ab-cdef-0123-456789abcdef",
        "ControlGroup": "/system.slice/run.service",
        "Id": "run.service",
        "InvocationID": "b" * 32,
        "MainPID": "123",
        "MainStartTime": "456",
        "ServiceDevice": "7",
        "ServiceInode": "8",
        "SupervisorDevice": "7",
        "SupervisorInode": "9",
    }
    config = formal_case._materialized_config(
        plan,
        plan_sha256="c" * 64,
        invocation_lineage=lineage,
        systemd_armed_receipt_sha256="d" * 64,
    )
    scratch = Path(plan["scratch_directory"])
    if drift == "mode":
        scratch.chmod(
            config["directory_authorities"]["scratch_directory"]["mode"] ^ 0o001
        )
    else:
        moved = tmp_path / "old-scratch"
        scratch.rename(moved)
        scratch.mkdir()

    with pytest.raises(formal_case.FixtureError, match="drifted"):
        formal_case._validate_config(config)


def test_directory_authority_is_revalidated_immediately_after_outer_acquisition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    formal_case: ModuleType,
) -> None:
    plan, references = _plan(tmp_path, formal_case)
    _install_static_hash_stub(monkeypatch, formal_case, references)
    plan_path = tmp_path / "plan.json"
    plan_path.write_bytes(_canonical(plan))
    lineage = {
        "BootID": "01234567-89ab-cdef-0123-456789abcdef",
        "ControlGroup": "/system.slice/run.service",
        "Id": "run.service",
        "InvocationID": "b" * 32,
        "MainPID": str(os.getpid()),
        "MainStartTime": str(formal_case._proc_starttime(os.getpid())),
        "ServiceDevice": "7",
        "ServiceInode": "8",
        "SupervisorDevice": "7",
        "SupervisorInode": "9",
    }
    monkeypatch.setattr(formal_case, "_derive_same_pid_lineage", lambda plan: lineage)
    case_entries: list[str] = []
    monkeypatch.setattr(
        formal_case, "_execute_case", lambda path: case_entries.append(path) or 0
    )

    def acquire_then_replace_directory(*args: object, **kwargs: object) -> str:
        del args, kwargs
        scratch = Path(plan["scratch_directory"])
        scratch.rename(tmp_path / "superseded-scratch")
        scratch.mkdir()
        return "d" * 64

    monkeypatch.setattr(
        formal_case, "_perform_systemd_acquisition", acquire_then_replace_directory
    )

    with pytest.raises(formal_case.FixtureError, match="drifted"):
        formal_case._execute_plan(str(plan_path))
    assert case_entries == []
    assert not Path(plan["final_config_path"]).exists()


@pytest.mark.parametrize(
    "aliased_asset",
    (
        "final_config",
        "outer_armed",
        "outer_ready",
        "outer_release",
        "action_armed",
        "control",
        "b6_armed",
        "b6_operation",
        "b6_ready",
        "b6_release",
        "descendant_plan",
        "descendant_request",
        "descendant_receipt",
        "formal_program_case_script",
        "adversary_script",
        "accepted_probe",
        "accepted_extension",
        "accepted_spawn_backend",
        "boot_id_file",
        "plan_path",
    ),
)
def test_global_formal_asset_path_set_is_pairwise_disjoint(
    aliased_asset: str,
    tmp_path: Path,
    formal_case: ModuleType,
) -> None:
    receipt_directory = tmp_path / "receipts"
    receipt_directory.mkdir()
    final_receipt = receipt_directory / "final.json"
    static_inputs = {
        name: str(tmp_path / name)
        for name in (
            "formal_program_case_script",
            "adversary_script",
            "accepted_probe",
            "accepted_extension",
            "accepted_spawn_backend",
        )
    }
    for name, path in static_inputs.items():
        Path(path).write_bytes(name.encode("ascii"))
    boot_path = tmp_path / "boot-id"
    boot_path.write_bytes(b"boot-id\n")
    boot_status = boot_path.lstat()
    boot_id_file = {
        "path": str(boot_path),
        "device": str(boot_status.st_dev),
        "inode": str(boot_status.st_ino),
    }
    plan_path = tmp_path / "formal-plan.json"
    plan_path.write_bytes(b"{}\n")
    descendant_path = tmp_path / "descendant-plan.json"
    descendant = {
        "schema": "unused",
        "scenario": "unused",
        "unit": "unused",
        "expected_job_name": "unused",
        "program_path": str(tmp_path / "program"),
        "program_sha256": "a" * 64,
        "request_path": str(tmp_path / "descendant-request.json"),
        "receipt_path": str(tmp_path / "descendant-receipt.json"),
        "acquisition": None,
        "hold_release_fifo": None,
    }
    descendant_path.write_bytes(_canonical(descendant))
    outer = {
        "armed_receipt_path": str(tmp_path / "outer-armed.json"),
        "ready_fifo": _fifo(tmp_path / "outer-ready.fifo"),
        "release_fifo": _fifo(tmp_path / "outer-release.fifo"),
    }
    b6 = {
        "acquisition": {
            "armed_receipt_path": str(tmp_path / "b6-armed.json"),
            "operation_receipt_path": str(tmp_path / "b6-operation.json"),
            "ready_fifo": _fifo(tmp_path / "b6-ready.fifo"),
            "release_fifo": _fifo(tmp_path / "b6-release.fifo"),
        }
    }
    control = _fifo(tmp_path / "control.fifo")
    values: dict[str, tuple[dict[str, object], str]] = {
        "outer_armed": (outer, "armed_receipt_path"),
        "outer_ready": (outer["ready_fifo"], "path"),
        "outer_release": (outer["release_fifo"], "path"),
        "b6_armed": (b6["acquisition"], "armed_receipt_path"),
        "b6_operation": (b6["acquisition"], "operation_receipt_path"),
        "b6_ready": (b6["acquisition"]["ready_fifo"], "path"),
        "b6_release": (b6["acquisition"]["release_fifo"], "path"),
        "control": (control, "path"),
        "descendant_request": (descendant, "request_path"),
        "descendant_receipt": (descendant, "receipt_path"),
    }
    final_config_path = str(tmp_path / "materialized-config.json")
    action_armed_path = str(tmp_path / "action-armed.json")
    reference = _static(descendant_path)
    if aliased_asset == "final_config":
        final_config_path = str(final_receipt)
    elif aliased_asset == "action_armed":
        action_armed_path = str(final_receipt)
    elif aliased_asset == "descendant_plan":
        reference["path"] = str(final_receipt)
        final_receipt.write_bytes(_canonical(descendant))
    elif aliased_asset in static_inputs:
        static_inputs[aliased_asset] = str(final_receipt)
        final_receipt.write_bytes(aliased_asset.encode("ascii"))
    elif aliased_asset == "boot_id_file":
        boot_id_file["path"] = str(final_receipt)
        final_receipt.write_bytes(b"boot-id\n")
        status = final_receipt.lstat()
        boot_id_file["device"] = str(status.st_dev)
        boot_id_file["inode"] = str(status.st_ino)
    elif aliased_asset == "plan_path":
        plan_path = final_receipt
        final_receipt.write_bytes(b"{}\n")
    else:
        owner, name = values[aliased_asset]
        if aliased_asset in {
            "outer_ready",
            "outer_release",
            "control",
            "b6_ready",
            "b6_release",
        }:
            os.link(str(owner[name]), final_receipt)
        owner[name] = str(final_receipt)
        if aliased_asset.startswith("descendant_"):
            descendant_path.write_bytes(_canonical(descendant))

    with pytest.raises(formal_case.FixtureError, match="overlap"):
        formal_case._validate_asset_non_aliasing(
            receipt_directory=str(receipt_directory),
            receipt_name="final.json",
            final_config_path=final_config_path,
            systemd_acquisition=outer,
            b6=b6,
            control_fifo=control,
            action_armed_path=action_armed_path,
            descendant_adversary_plan=reference,
            plan_path=str(plan_path),
            static_inputs=static_inputs,
            boot_id_file=boot_id_file,
        )


@pytest.mark.parametrize("aliased_authority", ("plan", "final_receipt"))
def test_global_formal_input_identity_set_rejects_distinct_hardlink_paths(
    aliased_authority: str,
    tmp_path: Path,
    formal_case: ModuleType,
) -> None:
    plan_path = tmp_path / "formal-plan.json"
    program_path = tmp_path / "formal-program.py"
    plan_path.write_bytes(b"{}\n")
    if aliased_authority == "plan":
        os.link(plan_path, program_path)
    else:
        program_path.write_bytes(b"program\n")
    receipt_directory = tmp_path / "receipts"
    receipt_directory.mkdir()
    if aliased_authority == "final_receipt":
        os.link(program_path, receipt_directory / "final.json")
    outer = {
        "armed_receipt_path": str(tmp_path / "outer-armed.json"),
        "ready_fifo": _fifo(tmp_path / "outer-ready.fifo"),
        "release_fifo": _fifo(tmp_path / "outer-release.fifo"),
    }

    with pytest.raises(formal_case.FixtureError, match="identities overlap"):
        formal_case._validate_asset_non_aliasing(
            receipt_directory=str(receipt_directory),
            receipt_name="final.json",
            final_config_path=str(tmp_path / "materialized-config.json"),
            systemd_acquisition=outer,
            b6=None,
            control_fifo=None,
            action_armed_path=None,
            descendant_adversary_plan=None,
            plan_path=str(plan_path),
            static_inputs={"formal_program/case_script": str(program_path)},
        )


def test_global_formal_fifo_identity_set_rejects_distinct_hardlink_paths(
    tmp_path: Path,
    formal_case: ModuleType,
) -> None:
    receipt_directory = tmp_path / "receipts"
    receipt_directory.mkdir()
    ready = _fifo(tmp_path / "ready.fifo")
    alias_path = tmp_path / "ready-hardlink.fifo"
    os.link(ready["path"], alias_path)
    alias = dict(ready, path=str(alias_path))
    with pytest.raises(formal_case.FixtureError, match="asset identities overlap"):
        formal_case._validate_asset_non_aliasing(
            receipt_directory=str(receipt_directory),
            receipt_name="final.json",
            final_config_path=str(tmp_path / "config.json"),
            systemd_acquisition={
                "armed_receipt_path": str(tmp_path / "armed.json"),
                "ready_fifo": ready,
                "release_fifo": alias,
            },
            b6=None,
            control_fifo=None,
            action_armed_path=None,
            descendant_adversary_plan=None,
        )


def test_fifo_authority_requires_0600_fixture_owner_and_root_parent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    formal_case: ModuleType,
) -> None:
    fifo = _fifo(tmp_path / "sealed.fifo")
    real_stat = os.stat

    def rooted_parent(path: object, *, follow_symlinks: bool = True) -> object:
        result = real_stat(path, follow_symlinks=follow_symlinks)
        if Path(path) == tmp_path:
            return SimpleNamespace(st_mode=result.st_mode, st_uid=0)
        return result

    monkeypatch.setattr(formal_case.os, "stat", rooted_parent)
    formal_case._require_sealed_fifo_authority(
        fifo,
        fixture_uid=os.getuid(),
        fixture_gid=os.getgid(),
        label="control_fifo",
    )
    os.chmod(fifo["path"], 0o640)
    with pytest.raises(formal_case.RequirementMissing) as error:
        formal_case._require_sealed_fifo_authority(
            fifo,
            fixture_uid=os.getuid(),
            fixture_gid=os.getgid(),
            label="control_fifo",
        )
    assert error.value.code == "SEALED_FIFO_AUTHORITY"

    b6_root = tmp_path / "b6"
    b6_root.mkdir()
    plan, references = _plan(
        b6_root, formal_case, case_id="B6", variant="issuer-blocked"
    )
    _install_static_hash_stub(monkeypatch, formal_case, references)
    plan["b6"] = {
        **formal_case._B6_ABI["issuer-blocked"],
        "acquisition": {
            "armed_receipt_path": str(Path(plan["receipt_directory"]) / "b6-armed.json"),
            "operation_receipt_path": str(
                Path(plan["receipt_directory"]) / "b6-operation.json"
            ),
            "ready_fifo": plan["systemd_acquisition"]["ready_fifo"],
            "release_fifo": _fifo(tmp_path / "b6-release.fifo"),
        },
    }
    with pytest.raises(formal_case.FixtureError, match="overlap"):
        formal_case._validate_plan(plan)


def test_descendant_receipt_is_fully_cross_bound_and_mutation_rejects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    formal_case: ModuleType,
) -> None:
    control = _fifo(tmp_path / "hold.fifo")
    plan_path = tmp_path / "descendant-plan.json"
    request_path = tmp_path / "descendant-request.json"
    receipt_path = tmp_path / "descendant-receipt.json"
    program = _FIXTURE.with_name("generic_backend_adversary.py")
    program_status = program.lstat()
    invocation = "b" * 32
    boot_id = "01234567-89ab-cdef-0123-456789abcdef"
    job_name = "job-7-aaaaaaaaaaaaaaaa"
    job_cgroup = "/fixture.slice/run.service/" + job_name
    plan = {
        "schema": formal_case._DESCENDANT_PLAN_SCHEMA,
        "scenario": "b7-double-fork-closed-stdio",
        "unit": "run.service",
        "expected_job_name": job_name,
        "program_path": str(program),
        "program_sha256": hashlib.sha256(program.read_bytes()).hexdigest(),
        "request_path": str(request_path),
        "receipt_path": str(receipt_path),
        "acquisition": None,
        "hold_release_fifo": control,
    }
    plan_path.write_bytes(_canonical(plan))
    plan_sha256 = hashlib.sha256(plan_path.read_bytes()).hexdigest()
    request = {
        "schema": formal_case._DESCENDANT_REQUEST_SCHEMA,
        "scenario": plan["scenario"],
        "unit": plan["unit"],
        "expected_invocation_id": invocation,
        "expected_job_name": job_name,
        "expected_job_cgroup": job_cgroup,
        "receipt_path": str(receipt_path),
        "hold_release_fifo": control,
    }
    request_path.write_bytes(_canonical(request))
    request_sha256 = hashlib.sha256(request_path.read_bytes()).hexdigest()

    def actor(pid: int, starttime: int, session_id: int) -> dict[str, object]:
        return {
            "boot_id": boot_id,
            "invocation_id": invocation,
            "pid": pid,
            "proc_cgroup_raw": f"0::{job_cgroup}\n",
            "session_id": session_id,
            "starttime": starttime,
            "stop_selector_environment": {},
            "unified_cgroup": job_cgroup,
        }

    program_receipt = {
        "path": str(program),
        "sha256": plan["program_sha256"],
        "identity": {
            "device": program_status.st_dev,
            "inode": program_status.st_ino,
            "mode": program_status.st_mode & 0o7777,
        },
    }
    receipt = {
        "schema": formal_case._DESCENDANT_RECEIPT_SCHEMA,
        "scenario": plan["scenario"],
        "unit": plan["unit"],
        "actor": actor(101, 201, 101),
        "expected_invocation_id": invocation,
        "expected_job_name": job_name,
        "expected_job_cgroup": job_cgroup,
        "hold_release_fifo": control,
        "release_handshake": {
            "device": int(control["device"]),
            "inode": int(control["inode"]),
            "path": control["path"],
            "permit_sha256": hashlib.sha256(formal_case._RELEASE_BYTES).hexdigest(),
        },
        "request_path": str(request_path),
        "request_sha256": request_sha256,
        "descendant": actor(102, 202, 102),
        "formal_plan_binding": {
            "schema": formal_case._DESCENDANT_PLAN_SCHEMA,
            "scenario": plan["scenario"],
            "unit": plan["unit"],
            "expected_job_name": job_name,
            "plan_path": str(plan_path),
            "plan_sha256": plan_sha256,
            "program": program_receipt,
            "acquisition": None,
            "hold_release_fifo": control,
            "materialized_request_sha256": request_sha256,
        },
    }
    receipt_path.write_bytes(_canonical(receipt))
    environment = (b"INVOCATION_ID=" + invocation.encode("ascii"), b"LC_ALL=C")
    process_spec = {"environment": environment, "spec_sha256": "e" * 64}
    config = {
        "run_unit": "run.service",
        "control_fifo": control,
        "descendant_adversary_plan": {
            "path": str(plan_path),
            "sha256": plan_sha256,
        },
    }
    evidence = formal_case._validate_descendant_receipt(
        config,
        plan=plan,
        plan_sha256=plan_sha256,
        receipt_path=str(receipt_path),
        invocation_id=invocation,
        boot_id=boot_id,
        blocked_process={"pid": 101, "starttime": 201},
        expected_job_cgroup=job_cgroup,
        process_spec_sha256="e" * 64,
        process_spec=process_spec,
        require_live_descendant=False,
    )
    assert evidence["expected_job_cgroup"] == job_cgroup
    assert evidence["process_spec"]["environment"] == environment

    monkeypatch.setattr(formal_case, "_proc_starttime", lambda pid: 202)
    monkeypatch.setattr(formal_case, "_child_cgroup", lambda pid: job_cgroup)
    monkeypatch.setattr(formal_case.os, "getsid", lambda pid: 102)
    live_evidence = formal_case._validate_descendant_receipt(
        config,
        plan=plan,
        plan_sha256=plan_sha256,
        receipt_path=str(receipt_path),
        invocation_id=invocation,
        boot_id=boot_id,
        blocked_process={"pid": 101, "starttime": 201},
        expected_job_cgroup=job_cgroup,
        process_spec_sha256="e" * 64,
        process_spec=process_spec,
        require_live_descendant=True,
    )
    assert live_evidence["descendant"]["session_id"] == 102

    receipt["descendant"]["session_id"] = 103
    receipt_path.write_bytes(_canonical(receipt))
    with pytest.raises(formal_case.RequirementMissing) as session_error:
        formal_case._validate_descendant_receipt(
            config,
            plan=plan,
            plan_sha256=plan_sha256,
            receipt_path=str(receipt_path),
            invocation_id=invocation,
            boot_id=boot_id,
            blocked_process={"pid": 101, "starttime": 201},
            expected_job_cgroup=job_cgroup,
            process_spec_sha256="e" * 64,
            process_spec=process_spec,
            require_live_descendant=True,
        )
    assert session_error.value.code == "B6_DESCENDANT_IDENTITY"
    receipt["descendant"]["session_id"] = 102
    receipt_path.write_bytes(_canonical(receipt))

    real_sha256_file = formal_case._sha256_file
    monkeypatch.setattr(
        formal_case,
        "_sha256_file",
        lambda path: "0" * 64 if path == str(program) else real_sha256_file(path),
    )
    with pytest.raises(formal_case.RequirementMissing) as program_error:
        formal_case._validate_descendant_receipt(
            config,
            plan=plan,
            plan_sha256=plan_sha256,
            receipt_path=str(receipt_path),
            invocation_id=invocation,
            boot_id=boot_id,
            blocked_process={"pid": 101, "starttime": 201},
            expected_job_cgroup=job_cgroup,
            process_spec_sha256="e" * 64,
            process_spec=process_spec,
            require_live_descendant=True,
        )
    assert program_error.value.code == "B6_DESCENDANT_PROGRAM"
    monkeypatch.setattr(formal_case, "_sha256_file", real_sha256_file)

    receipt["formal_plan_binding"]["expected_job_name"] = "job-8-aaaaaaaaaaaaaaaa"
    receipt_path.write_bytes(_canonical(receipt))
    with pytest.raises(formal_case.FixtureError, match="binding"):
        formal_case._validate_descendant_receipt(
            config,
            plan=plan,
            plan_sha256=plan_sha256,
            receipt_path=str(receipt_path),
            invocation_id=invocation,
            boot_id=boot_id,
            blocked_process={"pid": 101, "starttime": 201},
            expected_job_cgroup=job_cgroup,
            process_spec_sha256="e" * 64,
            process_spec=process_spec,
            require_live_descendant=False,
        )


def test_b6_operation_receipt_is_exact_durable_and_single_injection(
    tmp_path: Path,
    formal_case: ModuleType,
) -> None:
    operation_path = tmp_path / "b6-operation.json"
    plan = {
        **formal_case._B6_ABI["storage-just-released"],
        "acquisition": {"operation_receipt_path": str(operation_path)},
    }
    controller = formal_case._B6FaultController(
        {"b6": plan, "case_id": "B6", "variant": "storage-just-released"},
        {},
        None,
    )
    controller._arm_and_wait = lambda: None
    controller.armed_sha256 = "a" * 64
    controller.before_fact = {"phase": "just-released"}
    controller.after_fact = {
        "release_sha256": hashlib.sha256(formal_case._RELEASE_BYTES).hexdigest()
    }
    original_calls = 0

    def original() -> bool:
        nonlocal original_calls
        original_calls += 1
        raise AssertionError("capture-storage injection must not call original")

    assert controller.invoke(original) is False
    assert original_calls == 0
    operation = json.loads(operation_path.read_text(encoding="ascii"))
    assert set(operation) == {
        "schema",
        "case_id",
        "variant",
        "fault",
        "declared_phase",
        "hook",
        "target_operation",
        "planned_ordinal",
        "observed_ordinal",
        "injection_count",
        "armed_receipt_sha256",
        "actor_pid",
        "actor_starttime",
        "before_fact_sha256",
        "release_permit_sha256",
        "operation_state",
        "effect_state",
        "return_type",
        "exception_type",
        "errno",
        "postcondition",
    }
    assert operation["schema"] == "scion.generic-backend.b6-operation.v1"
    assert operation["operation_state"] == "INJECTED_RETURN"
    assert operation["effect_state"] == "ORIGINAL_STORAGE_WRITE_NOT_CALLED"
    assert operation["return_type"] == "builtins.bool"
    assert operation["observed_ordinal"] == operation["planned_ordinal"] == 1
    assert operation["injection_count"] == 1
    with pytest.raises(formal_case.RequirementMissing, match="second publication"):
        controller._publish_operation(
            operation_state="INJECTED_RETURN",
            effect_state="ORIGINAL_STORAGE_WRITE_NOT_CALLED",
            return_value=False,
            exception=None,
            postcondition="capture storage became unavailable after one injected false",
        )


_SOURCE_SEAM_CONTRACTS = {
    "service-consume": (
        "SpawnBackend.open",
        "_consume",
        "0f4015a0ee84be37b6261cbcd8eaaf7531a948d094e89922127736b8f9df19b3",
        "f02d736a0a1280da3df5e1cd8097d9d9fe7e502cadca28d7193c7db5c079edcf",
        "f97a9c01e17a0fed07ccce686ba07d012cfb31ebb61e108d31ca82b52c7690b8",
        "a06e7b56a353964f3c0ccf9a1a802992310a7870ef0fba071eb7b6dfe6b895ba",
    ),
    "capture-spool-open": (
        "_open_spool_into",
        "open",
        "8fde4ba04df16b583d6390f0eeb11565d234dd914a6fe7838b35bcd851b8b30c",
        "fe57e3b915762439745e9911ebf9e2f9e779c225585aa40ffd419528713593bd",
        "c6cfdef31e7e9219c6e7a8d2500f857339c697a7fc1cf5bc445197903db3be90",
        "647ccca07f3328861ff7c7304e77c0f484184cf94e04995b4cd91132daeb9e73",
    ),
    "pre-native-borrow": (
        "SpawnBackend._start_blocked_phases",
        "_consume_spawn_dirfd_borrow",
        "8a49138617d8c5c897fb1e3be361472310e8b2ce2c6bc3cba1d2614754d9bff4",
        "4e8dcb651091688153d871a23867b756081d04dfa9072cb41a9cdae7e9b6655d",
        "1cd87b8365cd2ef5dbb5a58263f2f4f7cd208c35f8b1bcf546c71e18fd3ae3f1",
        "339ac4fb0a08b10d3a190a6f99bfc28da8d3f3c445e25408f8f042b7955ef7ae",
    ),
    "guard-restore": (
        "_IssuerSignalGuard.restore",
        "pthread_sigmask",
        "4d677460c2b8bd873ab359307fed0568f637bc954224907fdc3cd41bbeb8f41b",
        "45b6436d9a050ec31517eb8c8ca49c4d07ed18e11b9799a2174f1470be95b71c",
        None,
        "2a6cbde084581e9ce32d28e9668752915d80b194a0889da0c13985c67a5880e0",
    ),
    "terminal-fact": (
        "_drain_terminal_snapshot",
        "from_native",
        "986c8e30c86fa129828d33f58300aa21216b17facf64f0941c6865122f39d9ec",
        "b0a17789120d83443fe65f6fed4cecc3da6f3b1bc50f0c4d1e9df5d8b120cbff",
        "a56bdf150362070ffdbb32e1c1bfa53876d0fdd308850ed7c26d8aff23f3a693",
        "7a036f9939bc3bf49a972ce7b7bcdca66768383e76535064764819ee62cbef59",
    ),
    "reaped-pidfd-close": (
        "_drain_terminal_snapshot",
        "_close_exact",
        "59d795504cf0d11216f2067eaa302ca68531f25f06d41876759eddd5027dcda8",
        "6a1de2d2db58349218f86e3ff438f93000614a47acaf8fbf9c910f0a22d530b8",
        "5aa64cef6a5591ec9fe6a12925ae2447de5517535a220ec0869855c57baaee75",
        "4c146d602175b2eb535522f85beb90f65afff14fa3ceea7324a794af982eb1aa",
    ),
    "capture-write": (
        "_StreamDrain.consume",
        "_write_spool",
        "ff72b91a69053ab158abd45a5662fd5899f90ff5f1a4a496c2a4f21903e39640",
        "a00cf31b55dc4b010d90baaa87da1bbf4015d00d14bff6f45af90efaf875a7b6",
        None,
        "313227b4317f5e9c0eaff3aaca0671150bde56ee34140ae8e8af2b1ee84a8a7c",
    ),
}

_INSTALLABLE_B6_OPERATION_CONTRACTS = {
    "issuer-backend-open": (
        "SpawnBackend.open -> ServiceCgroup._consume",
        "RETURNED",
        "AUTHORITY_MOVED",
        "scion.runtime.execution.cgroup_v2._ServiceCgroupAuthority",
        None,
        None,
        "exact target operation completed once",
    ),
    "issuer-capture-prepare": (
        "SpawnBackend.start_blocked -> _start_blocked_phases -> "
        "_open_spool_into -> os.open(O_TMPFILE)",
        "RETURNED",
        "FD_ACQUIRED",
        "builtins.int",
        None,
        None,
        "exact target operation completed once",
    ),
    "issuer-job-created-pre-native": (
        "SpawnBackend.start_blocked -> _start_blocked_phases -> "
        "_JobCgroup._consume_spawn_dirfd_borrow",
        "RETURNED",
        "PINNED_BORROW_RETURNED",
        "builtins.int",
        None,
        None,
        "exact target operation completed once",
    ),
    "issuer-blocked": (
        "SpawnBackend.release_and_collect -> _IssuerSignalGuard.restore[10]",
        "RETURNED",
        "MASK_RESTORED_HANDLER_DELIVERED",
        "builtins.bool",
        None,
        None,
        "fixed handler raised inside production restore and guard recovery returned true",
    ),
    "issuer-just-released": (
        "SpawnBackend.release_and_collect -> _IssuerSignalGuard.restore[11]",
        "RETURNED",
        "MASK_RESTORED_HANDLER_DELIVERED",
        "builtins.bool",
        None,
        None,
        "fixed handler raised inside production restore and guard recovery returned true",
    ),
    "issuer-leader-terminal": (
        "SpawnBackend.release_and_collect -> _drain_terminal_snapshot -> "
        "WaitFact.from_native",
        "RETURNED",
        "WAIT_FACT_RETURNED",
        "scion.runtime.execution.model.WaitFact",
        None,
        None,
        "exact target operation completed once",
    ),
    "issuer-reaped-populated": (
        "SpawnBackend.release_and_collect -> _drain_terminal_snapshot -> "
        "_close_exact(poll_pidfd)",
        "RETURNED",
        "PIDFD_CLOSED",
        "builtins.NoneType",
        None,
        None,
        "exact target operation completed once",
    ),
    "storage-just-released": (
        "SpawnBackend.release_and_collect -> _StreamDrain.consume -> _write_spool",
        "INJECTED_RETURN",
        "ORIGINAL_STORAGE_WRITE_NOT_CALLED",
        "builtins.bool",
        None,
        None,
        "capture storage became unavailable after one injected false",
    ),
}


def test_every_installable_b6_hook_has_frozen_ast_callsite_contract(
    formal_case: ModuleType,
) -> None:
    assert hashlib.sha256(_SPAWN_BACKEND.read_bytes()).hexdigest() == (
        formal_case._ACCEPTED_SPAWN_BACKEND_SHA256
    )
    tree = ast.parse(_SPAWN_BACKEND.read_text(encoding="utf-8"))
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    definitions: dict[str, ast.FunctionDef] = {}
    stack: list[str] = []

    class Definitions(ast.NodeVisitor):
        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            stack.append(node.name)
            self.generic_visit(node)
            stack.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            definitions[".".join((*stack, node.name))] = node
            stack.append(node.name)
            self.generic_visit(node)
            stack.pop()

    Definitions().visit(tree)

    assert set(_SOURCE_SEAM_CONTRACTS) == set(formal_case._B6_INSTALLABLE_HOOKS)
    for hook, contract in _SOURCE_SEAM_CONTRACTS.items():
        owner, target, call_hash, statement_hash, previous_hash, next_hash = contract
        function = definitions[owner]
        calls = []
        for node in ast.walk(function):
            if not isinstance(node, ast.Call):
                continue
            name = (
                node.func.attr
                if isinstance(node.func, ast.Attribute)
                else node.func.id
                if isinstance(node.func, ast.Name)
                else None
            )
            if name == target:
                calls.append(node)
        assert len(calls) == 1, hook
        call = calls[0]
        assert _stable_ast_hash(call) == call_hash, hook
        statement: ast.AST = call
        while not isinstance(statement, ast.stmt):
            statement = parents[statement]
        assert _stable_ast_hash(statement) == statement_hash, hook
        owner_node = parents[statement]
        body = next(
            values
            for name in ("body", "orelse", "finalbody")
            if isinstance((values := getattr(owner_node, name, None)), list)
            and statement in values
        )
        index = body.index(statement)
        actual_previous = None if index == 0 else _stable_ast_hash(body[index - 1])
        actual_next = (
            None if index + 1 == len(body) else _stable_ast_hash(body[index + 1])
        )
        assert actual_previous == previous_hash, hook
        assert actual_next == next_hash, hook


def test_all_eight_installable_b6_rows_freeze_phase_ordinal_and_call_chain(
    formal_case: ModuleType,
) -> None:
    assert set(_INSTALLABLE_B6_OPERATION_CONTRACTS) == {
        variant
        for variant, row in formal_case._B6_ABI.items()
        if row["hook"] in formal_case._B6_INSTALLABLE_HOOKS
    }
    assert {
        variant: (
            formal_case._B6_ABI[variant]["phase"],
            formal_case._B6_ABI[variant]["operation_ordinal"],
            _INSTALLABLE_B6_OPERATION_CONTRACTS[variant][0],
        )
        for variant in _INSTALLABLE_B6_OPERATION_CONTRACTS
    } == {
        "issuer-backend-open": (
            "backend-open",
            "1",
            "SpawnBackend.open -> ServiceCgroup._consume",
        ),
        "issuer-capture-prepare": (
            "capture-prepare",
            "1",
            "SpawnBackend.start_blocked -> _start_blocked_phases -> "
            "_open_spool_into -> os.open(O_TMPFILE)",
        ),
        "issuer-job-created-pre-native": (
            "job-created-pre-native",
            "1",
            "SpawnBackend.start_blocked -> _start_blocked_phases -> "
            "_JobCgroup._consume_spawn_dirfd_borrow",
        ),
        "issuer-blocked": (
            "blocked",
            "10",
            "SpawnBackend.release_and_collect -> _IssuerSignalGuard.restore[10]",
        ),
        "issuer-just-released": (
            "just-released",
            "11",
            "SpawnBackend.release_and_collect -> _IssuerSignalGuard.restore[11]",
        ),
        "issuer-leader-terminal": (
            "leader-terminal",
            "1",
            "SpawnBackend.release_and_collect -> _drain_terminal_snapshot -> "
            "WaitFact.from_native",
        ),
        "issuer-reaped-populated": (
            "reaped-but-populated",
            "1",
            "SpawnBackend.release_and_collect -> _drain_terminal_snapshot -> "
            "_close_exact(poll_pidfd)",
        ),
        "storage-just-released": (
            "just-released",
            "1",
            "SpawnBackend.release_and_collect -> _StreamDrain.consume -> _write_spool",
        ),
    }


@pytest.mark.parametrize(
    ("variant", "terminal_mode"),
    (
        ("issuer-backend-open", "open"),
        ("issuer-capture-prepare", "start"),
        ("issuer-job-created-pre-native", "start"),
        ("issuer-blocked", "release"),
        ("issuer-just-released", "release"),
        ("issuer-leader-terminal", "release"),
        ("storage-just-released", "release"),
    ),
)
def test_installable_b6_hooks_execute_through_real_production_public_flow(
    variant: str,
    terminal_mode: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    formal_case: ModuleType,
    spawn_support: ModuleType,
) -> None:
    from scion.runtime.execution import cgroup_v2

    backend_implementation = spawn_support.spawn_backend
    hook = formal_case._B6_ABI[variant]["hook"]
    if hook != "service-consume":
        monkeypatch.setattr(
            backend_implementation, "ServiceCgroup", spawn_support._FakeServiceCgroup
        )

    if hook == "service-consume":
        target_owner, target_name = cgroup_v2.ServiceCgroup, "_consume"
    elif hook == "capture-spool-open":
        target_owner, target_name = backend_implementation, "os"
    elif hook == "pre-native-borrow":
        target_owner, target_name = cgroup_v2._JobCgroup, "_consume_spawn_dirfd_borrow"
    elif hook == "guard-restore":
        target_owner, target_name = backend_implementation._IssuerSignalGuard, "restore"
    elif hook == "terminal-fact":
        target_owner, target_name = backend_implementation.WaitFact, "from_native"
    elif hook == "reaped-pidfd-close":
        target_owner, target_name = backend_implementation, "_close_exact"
    else:
        assert hook == "capture-write"
        target_owner, target_name = backend_implementation, "_write_spool"
    target_original = (
        vars(target_owner)[target_name]
        if isinstance(target_owner, type)
        else getattr(target_owner, target_name)
    )

    operation_path = tmp_path / "operation.json"
    armed_path = tmp_path / "armed.json"
    ready_fifo = _fifo(tmp_path / "ready.fifo")
    release_fifo = _fifo(tmp_path / "release.fifo")
    b6 = {
        **formal_case._B6_ABI[variant],
        "acquisition": {
            "armed_receipt_path": str(armed_path),
            "operation_receipt_path": str(operation_path),
            "ready_fifo": ready_fifo,
            "release_fifo": release_fifo,
        },
    }
    issuer = b6["fault"] == "issuer-signal"
    starttime = formal_case._proc_starttime(os.getpid())
    invocation_lineage = {
        "BootID": "01234567-89ab-cdef-0123-456789abcdef",
        "ControlGroup": "/fixture.slice/run.service",
        "Id": "run.service",
        "InvocationID": "b" * 32,
        "MainPID": str(os.getpid()),
        "MainStartTime": str(starttime),
        "ServiceDevice": "7",
        "ServiceInode": "8",
        "SupervisorDevice": "7",
        "SupervisorInode": "9",
    }
    config = {
        "b6": b6,
        "case_id": "B6",
        "variant": variant,
        "run_unit": "run.service",
        "invocation_lineage": invocation_lineage,
        "plan_sha256": "c" * 64,
        "systemd_armed_receipt_sha256": "d" * 64,
    }
    signal_context = formal_case._B6SignalContext() if issuer else None
    controller = formal_case._B6FaultController(
        config, {}, signal_context
    )
    monkeypatch.setattr(backend_implementation, "_single_threaded", lambda: True)
    real_read_bytes = formal_case._read_bytes
    monkeypatch.setattr(
        formal_case,
        "_read_bytes",
        lambda path: (
            b"0::/fixture.slice/run.service/supervisor\n"
            if path == "/proc/self/cgroup"
            else real_read_bytes(path)
        ),
    )
    coordinator_errors: list[BaseException] = []
    cancel_coordinator = threading.Event()

    def coordinate_b6() -> None:
        try:
            signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGUSR1})
            ready_fd = os.open(ready_fifo["path"], os.O_RDONLY | os.O_CLOEXEC)
            try:
                ready = formal_case._read_all(ready_fd)
            finally:
                os.close(ready_fd)
            if cancel_coordinator.is_set():
                return
            assert ready == formal_case._READY_BYTES
            if issuer:
                os.kill(os.getpid(), signal.SIGUSR1)
            release_fd = os.open(
                release_fifo["path"], os.O_WRONLY | os.O_CLOEXEC
            )
            try:
                formal_case._write_all(release_fd, formal_case._RELEASE_BYTES)
            finally:
                os.close(release_fd)
        except BaseException as exc:
            coordinator_errors.append(exc)

    coordinator = threading.Thread(target=coordinate_b6)
    coordinator.start()
    capture_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    owner = None
    result = None
    controller.install(backend_implementation)
    try:
        if hook == "service-consume":
            service = object.__new__(cgroup_v2.ServiceCgroup)
            service._state = cgroup_v2.ServiceCgroup._OPEN
            service._creator_pid = os.getpid()
            service._creator_starttime = cgroup_v2._current_starttime()
            service._service_fd = os.dup(capture_fd)
            service._supervisor_fd = os.dup(capture_fd)
            service._configured = None
            service._invocation = SimpleNamespace(
                main_starttime=service._creator_starttime
            )
            service._lineage = spawn_support._lineage()
            service._available_controllers = ("pids",)

            def close_consumed_authority(authority: object) -> None:
                assert authority._state == authority._OPEN
                os.close(authority._supervisor_fd)
                os.close(authority._service_fd)
                authority._supervisor_fd = authority._service_fd = -1
                authority._state = authority._CLOSED

            monkeypatch.setattr(
                cgroup_v2._ServiceCgroupAuthority,
                "_close",
                close_consumed_authority,
            )
            authority = None
            opened = backend_implementation.SpawnBackend.open(service, capture_fd)
        else:
            authority = spawn_support._FakeAuthority(capture_fd)
            if hook == "pre-native-borrow":
                empty_events = cgroup_v2.CgroupEventsFact.decode(
                    b"populated 0\nfrozen 0\n"
                )
                events_path = tmp_path / "pre-native.events"
                events_path.write_bytes(b"populated 0\nfrozen 0\n")

                def exact_job_factory(key: object, directory_fd: int) -> object:
                    fake_identity = spawn_support._FakeJob(key, directory_fd).identity
                    job = object.__new__(cgroup_v2._JobCgroup)
                    job._state = cgroup_v2._JobCgroup._OPEN
                    job._creator_pid = os.getpid()
                    job._creator_starttime = cgroup_v2._current_starttime()
                    job._owner = authority
                    job._key = key
                    job._identity = fake_identity
                    job._initial_events = empty_events
                    job._job_fd = os.dup(directory_fd)
                    job._events_fd = os.open(
                        events_path, os.O_RDONLY | os.O_CLOEXEC
                    )
                    job._spawn_dirfd_issued = False
                    return job

                authority._job_factory = exact_job_factory
                authority._validate_inventory = lambda expected: None
                monkeypatch.setattr(
                    cgroup_v2._JobCgroup, "_verify_identity", lambda job: None
                )
                monkeypatch.setattr(
                    cgroup_v2, "_child_directories", lambda directory_fd: ()
                )
                monkeypatch.setattr(
                    cgroup_v2,
                    "_read_at",
                    lambda directory_fd, name: b""
                    if name == "cgroup.procs"
                    else (_ for _ in ()).throw(AssertionError(name)),
                )

                def close_exact_job(job: object) -> object:
                    assert job._state == job._OPEN
                    os.close(job._events_fd)
                    os.close(job._job_fd)
                    job._events_fd = job._job_fd = -1
                    job._state = job._CLOSED_RETAINED
                    return empty_events

                monkeypatch.setattr(
                    cgroup_v2._JobCgroup, "close_retained", close_exact_job
                )
            opened = backend_implementation.SpawnBackend.open(
                spawn_support._FakeServiceCgroup(authority), capture_fd
            )
        if terminal_mode == "open":
            result = opened
        else:
            assert type(opened) is backend_implementation.SpawnBackend
            owner = opened
            child = spawn_support._SuccessfulBlockedChild(stdout=b"public-flow-byte")
            monkeypatch.setattr(backend_implementation, "_failstop", spawn_support._raise_failstop)
            monkeypatch.setattr(backend_implementation, "_single_threaded", lambda: True)
            monkeypatch.setattr(
                backend_implementation.native,
                "BlockedChild",
                spawn_support._SuccessfulBlockedChild,
            )
            monkeypatch.setattr(
                backend_implementation.native, "spawn_blocked", lambda *_args: child
            )
            started = owner.start_blocked(spawn_support._key(), spawn_support._spec())
            if terminal_mode == "start":
                result = started
                owner = None
            else:
                assert type(started) is backend_implementation.BlockedSpawn
                blocked = started
                assert authority is not None
                job = authority.last_job
                assert job is not None
                spawn_support._install_poll_steps(
                    monkeypatch,
                    spawn_support._independent_completion_steps(blocked, job),
                )
                result = owner.release_and_collect(blocked)
                if type(result) is backend_implementation.SettledJob:
                    permit = backend_implementation._issue_cleanup_permit_for_tests(
                        result._cleanup_identity()
                    )
                    owner.remove_after_durable_cleanup(result, permit)
                    owner.close_idle()
                owner = None
    finally:
        if coordinator.is_alive():
            cancel_coordinator.set()
            for fifo in (ready_fifo, release_fifo):
                unblock_fd = os.open(
                    fifo["path"], os.O_RDWR | os.O_NONBLOCK | os.O_CLOEXEC
                )
                os.close(unblock_fd)
        coordinator.join()
        controller.uninstall()
        target_restored = (
            vars(target_owner)[target_name]
            if isinstance(target_owner, type)
            else getattr(target_owner, target_name)
        )
        assert target_restored is target_original
        if owner is not None and owner.state == "IDLE":
            owner.close_idle()
        os.close(capture_fd)
        if signal_context is not None and not signal_context.restored:
            signal_context.restore()

    assert result is not None
    assert coordinator_errors == []
    assert not coordinator.is_alive()
    assert armed_path.exists()
    armed = json.loads(armed_path.read_text(encoding="ascii"))
    assert armed["process_identity"]["pid"] == os.getpid()
    assert armed["process_identity"]["starttime"] == starttime
    assert armed["ready_fifo"] == ready_fifo
    assert armed["release_fifo"] == release_fifo
    assert armed["operation_receipt_path"] == str(operation_path)
    assert controller.before_fact["pid"] == os.getpid()
    assert controller.before_fact["starttime"] == starttime
    assert controller.after_fact["release_sha256"] == hashlib.sha256(
        formal_case._RELEASE_BYTES
    ).hexdigest()
    if issuer:
        assert int(signal.SIGUSR1) in controller.before_fact["guarded_mask"]
        assert int(signal.SIGUSR1) not in controller.before_fact["pending_before"]
        assert int(signal.SIGUSR1) in controller.after_fact["pending_after_release"]
        assert int(signal.SIGUSR1) in controller.after_fact[
            "guarded_mask_after_release"
        ]
        assert signal_context is not None and signal_context.restored
    assert type(result).__name__ == b6["expected_fact_type"]
    assert getattr(result.phase, "value", None) == b6["expected_phase"]
    assert getattr(result.reason, "value", None) == b6["expected_reason"]
    operation = json.loads(operation_path.read_text(encoding="ascii"))
    assert operation["hook"] == hook
    assert operation["planned_ordinal"] == int(b6["operation_ordinal"])
    assert operation["observed_ordinal"] == operation["planned_ordinal"]
    assert operation["injection_count"] == 1
    (
        _call_chain,
        operation_state,
        effect_state,
        return_type,
        exception_type,
        error_number,
        postcondition,
    ) = _INSTALLABLE_B6_OPERATION_CONTRACTS[variant]
    assert operation["declared_phase"] == b6["phase"]
    assert operation["operation_state"] == operation_state
    assert operation["effect_state"] == effect_state
    assert operation["return_type"] == return_type
    assert operation["exception_type"] == exception_type
    assert operation["errno"] == error_number
    assert operation["postcondition"] == postcondition
    assert controller.injection_count == 1
    assert controller._patches == []
    with pytest.raises(formal_case.RequirementMissing) as second:
        formal_case._B6FaultController._arm_and_wait(controller)
    assert second.value.code == "B6_EXTRA_INJECTION"


def test_reaped_populated_public_pidfd_close_runs_real_arm_and_proof(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    formal_case: ModuleType,
    spawn_support: ModuleType,
) -> None:
    import scion.runtime.execution as execution
    from scion.runtime.execution import cgroup_v2

    adversary_implementation = _load_adversary()
    backend_implementation = spawn_support.spawn_backend
    monkeypatch.setattr(
        backend_implementation, "ServiceCgroup", spawn_support._FakeServiceCgroup
    )
    monkeypatch.setattr(
        backend_implementation, "_failstop", spawn_support._raise_failstop
    )
    monkeypatch.setattr(backend_implementation, "_single_threaded", lambda: True)
    monkeypatch.setattr(
        backend_implementation.native,
        "BlockedChild",
        spawn_support._SuccessfulBlockedChild,
    )

    plan, _ = _plan(
        tmp_path,
        formal_case,
        case_id="B6",
        variant="issuer-reaped-populated",
    )
    descendant = _attach_descendant_plan(tmp_path, formal_case, plan)
    b6_ready = _fifo(tmp_path / "b6-ready.fifo")
    b6_release = _fifo(tmp_path / "b6-release.fifo")
    operation_path = Path(plan["receipt_directory"]) / "b6-operation.json"
    plan["b6"] = {
        **formal_case._B6_ABI["issuer-reaped-populated"],
        "acquisition": {
            "armed_receipt_path": str(
                Path(plan["receipt_directory"]) / "b6-armed.json"
            ),
            "operation_receipt_path": str(operation_path),
            "ready_fifo": b6_ready,
            "release_fifo": b6_release,
        },
    }
    invocation = "b" * 32
    starttime = formal_case._proc_starttime(os.getpid())
    boot_id = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
    lineage_mapping = {
        "BootID": boot_id,
        "ControlGroup": "/fixture.slice/run.service",
        "Id": "run.service",
        "InvocationID": invocation,
        "MainPID": str(os.getpid()),
        "MainStartTime": str(starttime),
        "ServiceDevice": "7",
        "ServiceInode": "8",
        "SupervisorDevice": "7",
        "SupervisorInode": "9",
    }
    config = formal_case._materialized_config(
        plan,
        plan_sha256="c" * 64,
        invocation_lineage=lineage_mapping,
        systemd_armed_receipt_sha256="d" * 64,
    )
    lineage = execution.InvocationLineage.from_properties(
        tuple(lineage_mapping.items())
    )
    monkeypatch.setattr(formal_case, "_current_invocation_id", lambda: invocation)
    monkeypatch.setattr(
        formal_case,
        "_formal_process_identity",
        lambda value, actual_lineage: {
            "boot_id": actual_lineage["BootID"],
            "invocation_id": actual_lineage["InvocationID"],
            "pid": int(actual_lineage["MainPID"]),
            "starttime": int(actual_lineage["MainStartTime"]),
        },
    )
    capture_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    authority = spawn_support._FakeAuthority(capture_fd)
    owner = backend_implementation.SpawnBackend.open(
        spawn_support._FakeServiceCgroup(authority), capture_fd
    )
    assert type(owner) is backend_implementation.SpawnBackend
    child = spawn_support._SuccessfulBlockedChild(
        stdout=b"leader", stderr=b"descendant"
    )
    capture_fds = tuple(child._capture_fds)
    populated = cgroup_v2.CgroupEventsFact.decode(b"populated 1\nfrozen 0\n")
    empty = cgroup_v2.CgroupEventsFact.decode(b"populated 0\nfrozen 0\n")
    expected_job_cgroup = (
        lineage.control_group + "/" + descendant["expected_job_name"]
    )
    fact_read_fd, fact_write_fd = os.pipe2(os.O_CLOEXEC)
    child_pid = os.fork()
    if child_pid == 0:
        os.close(fact_read_fd)
        try:
            os.environ["INVOCATION_ID"] = invocation
            real_read_proc_text = adversary_implementation._read_proc_text

            def mapped_cgroup_read(path: Path, *, label: str) -> str:
                if path.name == "cgroup":
                    return f"0::{expected_job_cgroup}\n"
                return real_read_proc_text(path, label=label)

            adversary_implementation._read_proc_text = mapped_cgroup_read
            real_child_report_and_hold = adversary_implementation._child_report_and_hold

            def child_report_and_hold(*args: object, **kwargs: object) -> object:
                os.close(fact_write_fd)
                return real_child_report_and_hold(*args, **kwargs)

            adversary_implementation._child_report_and_hold = child_report_and_hold
            leader_identity = adversary_implementation._identity(
                unit=descendant["unit"],
                scenario=descendant["scenario"],
                expected_job_name=descendant["expected_job_name"],
                expected_job_cgroup=expected_job_cgroup,
            )
            descendant_identity = adversary_implementation._double_fork_descendant(
                Path(plan["control_fifo"]["path"]),
                (
                    int(plan["control_fifo"]["device"]),
                    int(plan["control_fifo"]["inode"]),
                ),
                scenario=descendant["scenario"],
                unit=descendant["unit"],
                expected_job_name=descendant["expected_job_name"],
                expected_job_cgroup=expected_job_cgroup,
            )
            formal_case._write_all(
                fact_write_fd,
                _canonical(
                    {"leader": leader_identity, "descendant": descendant_identity}
                ),
            )
            os.close(fact_write_fd)
            os._exit(0)
        except BaseException:
            os.close(fact_write_fd)
            os._exit(125)
    os.close(fact_write_fd)
    try:
        real_process_raw = formal_case._read_all(fact_read_fd)
    finally:
        os.close(fact_read_fd)
    waited_pid, waited_status = os.waitpid(child_pid, 0)
    assert waited_pid == child_pid
    assert os.waitstatus_to_exitcode(waited_status) == 0
    real_processes = json.loads(real_process_raw.decode("ascii"))
    leader_identity = real_processes["leader"]
    descendant_identity = real_processes["descendant"]
    assert leader_identity["pid"] == child_pid
    assert descendant_identity["pid"] not in {os.getpid(), child_pid}
    assert leader_identity["starttime"] > 0
    assert descendant_identity["starttime"] > 0
    assert not Path(f"/proc/{child_pid}").exists()
    assert Path(f"/proc/{descendant_identity['pid']}").exists()
    child.pid = child_pid
    child.terminal = (child_pid, *child.terminal[1:])
    original_process_starttime = backend_implementation._process_starttime
    monkeypatch.setattr(
        backend_implementation,
        "_process_starttime",
        lambda pid: (
            leader_identity["starttime"]
            if pid == child_pid
            else original_process_starttime(pid)
        ),
    )
    original_child_cgroup = formal_case._child_cgroup
    monkeypatch.setattr(
        formal_case,
        "_child_cgroup",
        lambda pid: (
            expected_job_cgroup
            if pid == descendant_identity["pid"]
            else original_child_cgroup(pid)
        ),
    )

    published_spec_sha256: list[str] = []

    def publish_descendant_evidence(native_arguments: tuple[object, ...]) -> None:
        executable, argv, environment, cwd = native_arguments[1:]
        exact_spec = execution.GenericProcessSpec.create(
            opaque_job_key="formal-B6-issuer-reaped-populated",
            executable=executable,
            argv=argv,
            environment=environment,
            cwd=cwd,
        )
        assert exact_spec.environment == (
            b"INVOCATION_ID=" + invocation.encode("ascii"),
            b"LC_ALL=C",
        )
        published_spec_sha256.append(exact_spec.spec_sha256)
        request_path = Path(descendant["request_path"])
        receipt_path = Path(descendant["receipt_path"])
        request = {
            "schema": formal_case._DESCENDANT_REQUEST_SCHEMA,
            "scenario": descendant["scenario"],
            "unit": descendant["unit"],
            "expected_invocation_id": invocation,
            "expected_job_name": descendant["expected_job_name"],
            "expected_job_cgroup": expected_job_cgroup,
            "receipt_path": str(receipt_path),
            "hold_release_fifo": plan["control_fifo"],
        }
        request_path.write_bytes(_canonical(request))
        request_sha256 = hashlib.sha256(request_path.read_bytes()).hexdigest()
        program_path = Path(descendant["program_path"])
        program_status = program_path.lstat()
        program_receipt = {
            "path": str(program_path),
            "sha256": descendant["program_sha256"],
            "identity": {
                "device": program_status.st_dev,
                "inode": program_status.st_ino,
                "mode": program_status.st_mode & 0o7777,
            },
        }
        receipt = {
            "schema": formal_case._DESCENDANT_RECEIPT_SCHEMA,
            "scenario": descendant["scenario"],
            "unit": descendant["unit"],
            "actor": leader_identity,
            "expected_invocation_id": invocation,
            "expected_job_name": descendant["expected_job_name"],
            "expected_job_cgroup": expected_job_cgroup,
            "hold_release_fifo": plan["control_fifo"],
            "release_handshake": {
                "device": int(plan["control_fifo"]["device"]),
                "inode": int(plan["control_fifo"]["inode"]),
                "path": plan["control_fifo"]["path"],
                "permit_sha256": hashlib.sha256(
                    formal_case._RELEASE_BYTES
                ).hexdigest(),
            },
            "request_path": str(request_path),
            "request_sha256": request_sha256,
            "descendant": descendant_identity,
            "formal_plan_binding": {
                "schema": formal_case._DESCENDANT_PLAN_SCHEMA,
                "scenario": descendant["scenario"],
                "unit": descendant["unit"],
                "expected_job_name": descendant["expected_job_name"],
                "plan_path": plan["descendant_adversary_plan"]["path"],
                "plan_sha256": plan["descendant_adversary_plan"]["sha256"],
                "program": program_receipt,
                "acquisition": None,
                "hold_release_fifo": plan["control_fifo"],
                "materialized_request_sha256": request_sha256,
            },
        }
        receipt_path.write_bytes(_canonical(receipt))

    def spawn_child(*args: object) -> object:
        job = authority.last_job
        assert job is not None
        job.events = [populated, empty]
        publish_descendant_evidence(args)
        return child

    monkeypatch.setattr(backend_implementation.native, "spawn_blocked", spawn_child)

    class AdaptivePoll:
        def __init__(self, factory: "AdaptivePollFactory") -> None:
            self.factory = factory
            self.registered: dict[int, int] = {}

        def register(self, fd: int, mask: int) -> None:
            self.registered[fd] = mask

        def poll(self) -> list[tuple[int, int]]:
            job = authority.last_job
            assert job is not None
            known = {
                "stdout": capture_fds[0],
                "stderr": capture_fds[1],
                "exec": capture_fds[2],
                "events": job._events_fileno(),
            }
            if not self.factory.pidfd_sent:
                candidates = set(self.registered) - set(known.values())
                assert len(candidates) == 1
                fd = candidates.pop()
                self.factory.pidfd_sent = True
                self.factory.calls.append("pidfd")
                return [(fd, backend_implementation.select.POLLIN)]
            if not self.factory.events_sent and known["events"] in self.registered:
                self.factory.events_sent = True
                self.factory.calls.append("events")
                return [
                    (known["events"], backend_implementation.select.POLLPRI)
                ]
            for kind in ("stdout", "stderr", "exec"):
                fd = known[kind]
                if fd not in self.registered:
                    continue
                count = self.factory.stream_counts[kind]
                self.factory.stream_counts[kind] = count + 1
                self.factory.calls.append(kind)
                return [
                    (
                        fd,
                        backend_implementation.select.POLLIN
                        if count == 0
                        else backend_implementation.select.POLLHUP,
                    )
                ]
            raise AssertionError(
                f"adaptive poll has no deterministic registered target: "
                f"{self.registered!r}"
            )

    class AdaptivePollFactory:
        def __init__(self) -> None:
            self.pidfd_sent = False
            self.events_sent = False
            self.stream_counts = {"stdout": 0, "stderr": 0, "exec": 0}
            self.calls: list[str] = []

        def __call__(self) -> AdaptivePoll:
            return AdaptivePoll(self)

    poll_factory = AdaptivePollFactory()
    monkeypatch.setattr(backend_implementation.select, "poll", poll_factory)

    signal_context = formal_case._B6SignalContext()
    controller = formal_case._B6FaultController(config, {}, signal_context)
    controller.install(backend_implementation)
    controller.bind_backend(owner)
    coordinator_errors: list[BaseException] = []
    cancel_coordinator = threading.Event()

    def coordinate_b6() -> None:
        try:
            signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGUSR1})
            ready_fd = os.open(b6_ready["path"], os.O_RDONLY | os.O_CLOEXEC)
            try:
                ready = formal_case._read_all(ready_fd)
            finally:
                os.close(ready_fd)
            if cancel_coordinator.is_set():
                return
            assert ready == formal_case._READY_BYTES
            os.kill(os.getpid(), signal.SIGUSR1)
            release_fd = os.open(
                b6_release["path"], os.O_WRONLY | os.O_CLOEXEC
            )
            try:
                formal_case._write_all(release_fd, formal_case._RELEASE_BYTES)
            finally:
                os.close(release_fd)
        except BaseException as exc:
            coordinator_errors.append(exc)

    coordinator = threading.Thread(target=coordinate_b6)
    coordinator.start()
    try:
        result = formal_case._case_b6(
            execution, config, owner, controller, lineage
        )
        coordinator.join()
        assert coordinator_errors == []
        assert poll_factory.calls[0] == "pidfd"
        assert set(poll_factory.calls) == {
            "pidfd",
            "stdout",
            "stderr",
            "exec",
        }
        assert result["outcome"] == "PASS"
        assert type(result["failure"]) is execution.ContainedSpawnFailure
        assert result["failure"].reason is execution.ContainedSpawnReason.ISSUER_INTERRUPTED
        assert result["failure"].phase is execution.ContainedSpawnPhase.LEADER_REAPED_DRAINING
        assert controller.descendant_binding is not None
        assert controller.descendant_binding["validated"] is True
        assert controller.descendant_binding["evidence"]["cgroup_events"] == populated
        assert authority.last_job is not None
        assert authority.last_job.read_events_calls >= 2
        evidence = controller.descendant_binding["evidence"]
        assert evidence["expected_job_cgroup"] == expected_job_cgroup
        assert evidence["actor"]["pid"] == child_pid
        assert evidence["actor"]["starttime"] == leader_identity["starttime"]
        assert evidence["descendant"]["pid"] == descendant_identity["pid"]
        assert evidence["descendant"]["starttime"] == descendant_identity["starttime"]
        assert evidence["descendant"]["session_id"] == os.getsid(
            descendant_identity["pid"]
        )
        assert evidence["process_spec"]["environment"] == (
            b"INVOCATION_ID=" + invocation.encode("ascii"),
            b"LC_ALL=C",
        )
        assert published_spec_sha256 == [evidence["process_spec_sha256"]]
        assert evidence["receipt_sha256"] == hashlib.sha256(
            Path(descendant["receipt_path"]).read_bytes()
        ).hexdigest()
        operation = json.loads(operation_path.read_text(encoding="ascii"))
        (
            _call_chain,
            operation_state,
            effect_state,
            return_type,
            exception_type,
            error_number,
            postcondition,
        ) = _INSTALLABLE_B6_OPERATION_CONTRACTS["issuer-reaped-populated"]
        assert operation["declared_phase"] == "reaped-but-populated"
        assert operation["planned_ordinal"] == operation["observed_ordinal"] == 1
        assert operation["operation_state"] == operation_state
        assert operation["effect_state"] == effect_state
        assert operation["return_type"] == return_type
        assert operation["exception_type"] == exception_type
        assert operation["errno"] == error_number
        assert operation["postcondition"] == postcondition
        assert operation["injection_count"] == 1
        with pytest.raises(formal_case.RequirementMissing) as second:
            controller._arm_and_wait()
        assert second.value.code == "B6_EXTRA_INJECTION"
    finally:
        if coordinator.is_alive():
            cancel_coordinator.set()
            for fifo in (b6_ready, b6_release):
                unblock_fd = os.open(
                    fifo["path"],
                    os.O_RDWR | os.O_NONBLOCK | os.O_CLOEXEC,
                )
                os.close(unblock_fd)
        coordinator.join()
        assert not coordinator.is_alive()
        controller.uninstall()
        if not signal_context.restored:
            signal_context.restore()
        descendant_release_fd = os.open(
            plan["control_fifo"]["path"], os.O_WRONLY | os.O_CLOEXEC
        )
        try:
            formal_case._write_all(
                descendant_release_fd, formal_case._RELEASE_BYTES
            )
        finally:
            os.close(descendant_release_fd)
        os.close(capture_fd)

    assert vars(formal_case._B6FaultController).get("_arm_and_wait") is not None
    assert vars(formal_case._B6FaultController).get("_prove_reaped_populated") is not None


@pytest.mark.parametrize("variant", sorted((
    "tmpfile-unsupported",
    "tmpfile-allocation",
    "tmpfile-open",
)))
def test_b7_internal_faults_use_real_public_start_with_zero_native_and_restore(
    variant: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    formal_case: ModuleType,
    spawn_support: ModuleType,
) -> None:
    import scion.runtime.execution as execution

    backend_implementation = spawn_support.spawn_backend
    monkeypatch.setattr(
        backend_implementation, "ServiceCgroup", spawn_support._FakeServiceCgroup
    )
    monkeypatch.setattr(backend_implementation, "_single_threaded", lambda: True)
    capture_fd = os.open(
        tmp_path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
    )
    authority = spawn_support._FakeAuthority(capture_fd)
    owner = backend_implementation.SpawnBackend.open(
        spawn_support._FakeServiceCgroup(authority), capture_fd
    )
    assert type(owner) is backend_implementation.SpawnBackend
    original_os = backend_implementation.os
    original_native = backend_implementation.native.spawn_blocked
    try:
        result = formal_case._case_b7(
            execution,
            {
                "case_id": "B7",
                "variant": variant,
                "scratch_directory": str(tmp_path),
                "case_script": str(_FIXTURE),
                "invocation_nonce": "a" * 64,
                "ordinal": 7,
            },
            owner,
            {},
        )
    finally:
        os.close(capture_fd)
    assert result["outcome"] == "PASS"
    assert result["action_owner"] == "formal-case"
    assert result["control_fifo"] is None
    assert result["native_spawn_call_count"] == 0
    assert backend_implementation.os is original_os
    assert backend_implementation.native.spawn_blocked is original_native


@pytest.mark.parametrize("variant", sorted((
    "cgroup-inode-drift",
    "unexpected-sibling",
    "unexpected-nested",
    "supervisor-extra-task",
)))
def test_b7_external_topology_action_rejects_any_ordinary_return_with_exact_id(
    variant: str,
    monkeypatch: pytest.MonkeyPatch,
    formal_case: ModuleType,
) -> None:
    execution = ModuleType("execution")

    class BlockedSpawn:
        pass

    execution.BlockedSpawn = BlockedSpawn
    blocked = BlockedSpawn()
    control_events: list[str] = []
    armed_actions: list[tuple[str, bytes]] = []

    class Control:
        def __init__(self, config: object) -> None:
            del config

        def read_expected(self, expected: bytes) -> bytes:
            assert expected == b"DRIFT_APPLIED\n"
            control_events.append("permit")
            return expected

        def close(self) -> None:
            control_events.append("closed")

    backend = SimpleNamespace(release_and_collect=lambda value: object())
    monkeypatch.setattr(formal_case, "_ControlFifoPin", Control)
    monkeypatch.setattr(formal_case, "_helper_argv", lambda *args: (b"/bin/true",))
    monkeypatch.setattr(formal_case, "_new_spec", lambda *args, **kwargs: object())
    monkeypatch.setattr(formal_case, "_start", lambda *args, **kwargs: blocked)
    monkeypatch.setattr(
        formal_case,
        "_write_armed",
        lambda *args, **kwargs: armed_actions.append(
            (kwargs["action_id"], kwargs["expected_permit"])
        )
        or "a" * 64,
    )
    with pytest.raises(formal_case.FixtureError, match="ordinary control"):
        formal_case._case_b7(
            execution,
            {"variant": variant},
            backend,
            {},
        )
    assert armed_actions == [(f"b7-{variant}", b"DRIFT_APPLIED\n")]
    assert control_events == ["permit", "closed"]


def test_reaped_populated_seam_rejects_nonreaped_leader(
    formal_case: ModuleType,
) -> None:
    controller = formal_case._B6FaultController(
        {
            "b6": {
                **formal_case._B6_ABI["issuer-reaped-populated"],
                "acquisition": {},
            }
        },
        {},
        None,
    )
    controller.blocked = SimpleNamespace(_child=SimpleNamespace(state="RELEASED"))
    controller.blocked_fact = {"process_identity": {"pid": os.getpid()}}
    controller.control_pin = SimpleNamespace(revalidate=lambda: None)
    with pytest.raises(formal_case.RequirementMissing) as error:
        controller._prove_reaped_populated()
    assert error.value.code == "B6_LEADER_REAPED"


def test_final_inventory_directly_proves_fd_task_and_cgroup_closure(
    formal_case: ModuleType,
) -> None:
    execution = ModuleType("inventory_execution")

    class ContainedSpawnFailure:
        def __init__(self, identity: object) -> None:
            self.cgroup_identity = identity

    class Events:
        @staticmethod
        def decode(raw: bytes) -> object:
            assert raw == b"populated 0\nfrozen 0\n"
            return SimpleNamespace(populated=0, frozen=0)

    execution.ContainedSpawnFailure = ContainedSpawnFailure
    execution.CgroupEventsFact = Events
    root = {
        "relative": ".",
        "device": 7,
        "inode": 8,
        "children": ["supervisor"],
        "cgroup.procs": b"",
        "cgroup.events": b"populated 1\nfrozen 0\n",
        "cgroup.controllers": b"pids\n",
    }
    baseline = {
        "fds": [{"fd": 0, "inode": 1}],
        "tasks": [{"tid": 11, "starttime": 22}],
        "current_unified_cgroup": "/fixture/run.service/supervisor",
        "cgroups": {
            "control_group": "/fixture/run.service",
            "directories": [root],
        },
    }
    assert formal_case._require_final_inventory(
        execution, baseline, dict(baseline), {"outcome": "PASS"}
    ) == {
        "fd_returned_to_baseline": True,
        "task_returned_to_baseline": True,
        "cgroup_proof": {"kind": "RETURNED_TO_BASELINE"},
    }

    identity = SimpleNamespace(job_name="job-7-a", job_device=7, job_inode=9)
    final = {
        **baseline,
        "cgroups": {
            "control_group": "/fixture/run.service",
            "directories": [
                {**root, "children": ["job-7-a", "supervisor"]},
                {
                    "relative": "/job-7-a",
                    "device": 7,
                    "inode": 9,
                    "children": [],
                    "cgroup.procs": b"",
                    "cgroup.events": b"populated 0\nfrozen 0\n",
                    "cgroup.controllers": b"pids\n",
                },
            ],
        },
    }
    proof = formal_case._require_final_inventory(
        execution,
        baseline,
        final,
        {"failure": ContainedSpawnFailure(identity)},
    )
    assert proof["fd_returned_to_baseline"] is True
    assert proof["task_returned_to_baseline"] is True
    assert proof["cgroup_proof"]["kind"] == "EXACT_RETAINED_FAILED_JOB"
    assert proof["cgroup_proof"]["identity"] is identity


@pytest.mark.parametrize("drift", ("fds", "tasks", "cgroups"))
def test_final_inventory_directly_rejects_each_unclosed_inventory_dimension(
    drift: str,
    formal_case: ModuleType,
) -> None:
    execution = SimpleNamespace(ContainedSpawnFailure=type("Failure", (), {}))
    baseline = {
        "fds": [{"fd": 0}],
        "tasks": [{"tid": 1}],
        "cgroups": {"control_group": "/run", "directories": []},
    }
    final = {
        "fds": list(baseline["fds"]),
        "tasks": list(baseline["tasks"]),
        "cgroups": dict(baseline["cgroups"]),
    }
    if drift == "fds":
        final["fds"].append({"fd": 9})
    elif drift == "tasks":
        final["tasks"].append({"tid": 2})
    else:
        final["cgroups"] = {"control_group": "/run", "directories": [{}]}
    with pytest.raises(formal_case.FixtureError, match="inventory|cgroup"):
        formal_case._require_final_inventory(
            execution, baseline, final, {"outcome": "PASS"}
        )


def test_fixture_ast_has_no_forbidden_runtime_or_bounded_output_policy() -> None:
    assert _forbidden_fixture_ast_evidence(
        _FIXTURE.read_text(encoding="utf-8")
    ) == frozenset()
    assert hashlib.sha256(_SPAWN_BACKEND.read_bytes()).hexdigest() == (
        "9c25defcf383046b39e0638f6f3841fca9c47572506a5cd4c3a9fb9c3232f938"
    )


@pytest.mark.parametrize(
    ("mutation", "expected"),
    (
        ("cap(payload, 1024)", "call:cap"),
        ("truncate(payload)", "call:truncate"),
        ("truncation = True", "assignment:truncation"),
        ("automatic_cleanup()", "call:automatic_cleanup"),
        ("automatic_restart = True", "assignment:automatic_restart"),
        (
            "def bounded(payload):\n    return payload[:1024]",
            "slice:fixed-output-upper-bound",
        ),
    ),
)
def test_fixture_ast_policy_gate_rejects_targeted_mutations(
    mutation: str,
    expected: str,
) -> None:
    source = _FIXTURE.read_text(encoding="utf-8") + "\n" + mutation + "\n"
    assert expected in _forbidden_fixture_ast_evidence(source)


def test_fixture_ast_policy_gate_ignores_protocol_state_strings() -> None:
    source = """
PROTOCOL_STATES = (
    "cap",
    "truncate",
    "truncation",
    "automatic cleanup",
    "automatic restart",
)

def decode_protocol_state(value):
    return {"state": value[:-1], "version": sys.version_info[:2]}
"""
    assert _forbidden_fixture_ast_evidence(source) == frozenset()
