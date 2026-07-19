#!/usr/bin/env python3
"""Root-owned tests-only system-manager evidence harness.

This file is the sole formal launch owner.  It uses one system-bus connection,
installs signal handlers before subscribing, lifetime-pins positive units,
performs exactly one ``StartUnit(..., "fail")`` transaction, and freezes typed
raw evidence before releasing any acquisition barrier.  It has no external
manager client, PID-directed signal path or built-in observation clock.
"""

from __future__ import annotations

import base64
import ctypes
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import select
import socket
import stat
import struct
import sys
import signal as signal_module
from typing import Any, Callable, NoReturn, Protocol


MANIFEST_SCHEMA = "scion.generic_backend.systemd_harness_manifest.v1"
TREE_RECEIPT_SCHEMA = "scion.generic_backend.root_tree_receipt.v1"
SEAL_RECEIPT_SCHEMA = "scion.generic_backend.root_seal_receipt.v1"
PREFLIGHT_RECEIPT_SCHEMA = "scion.generic_backend.static_preflight_receipt.v1"
INSTALL_RECEIPT_SCHEMA = "scion.generic_backend.root_install_receipt.v1"
INSTALL_MANIFEST_SCHEMA = "scion.generic_backend.root_install.v1"
PREFLIGHT_MANIFEST_SCHEMA = "scion.generic_backend.static_preflight.v1"
DESCRIPTOR_SCHEMA = "scion.generic_backend.systemd_start_descriptor.v1"
SOURCE_SELECTOR_SCHEMA = "scion.generic_backend.systemd_source_selector.v1"
RAW_QUERY_SCHEMA = "scion.generic_backend.systemd_raw_query.v1"
SIGNAL_RECEIPT_SCHEMA = "scion.generic_backend.systemd_signal_receipt.v1"
JOURNAL_RECEIPT_SCHEMA = "scion.generic_backend.systemd_journal_receipt.v1"
HARNESS_RECEIPT_SCHEMA = "scion.generic_backend.systemd_harness_receipt.v1"
FORMAL_ARMED_SCHEMA = "scion.generic_backend.formal_run_armed.v1"
MANAGER_EVENT_SCHEMA = "scion.generic_backend.systemd_manager_events.v1"
FORMAL_ACTION_ARMED_SCHEMA = "scion.generic_backend.formal_action_armed.v1"
B6_ARMED_SCHEMA = "scion.generic_backend.b6_armed.v1"
B6_OPERATION_SCHEMA = "scion.generic-backend.b6-operation.v1"
FORMAL_RECEIPT_SCHEMA = "scion.generic-backend-formal-receipt.v1"

READY_BYTES = b"SCION_GENERIC_BACKEND_READY_V1\n"
RELEASE_BYTES = b"SCION_GENERIC_BACKEND_RELEASE_V1\n"
SYSTEMD_DESTINATION = "org.freedesktop.systemd1"
MANAGER_PATH = "/org/freedesktop/systemd1"
MANAGER_INTERFACE = "org.freedesktop.systemd1.Manager"
PROPERTIES_INTERFACE = "org.freedesktop.DBus.Properties"
UNIT_INTERFACE = "org.freedesktop.systemd1.Unit"
SERVICE_INTERFACE = "org.freedesktop.systemd1.Service"
JOURNAL_SOCKET = "/run/systemd/journal/io.systemd.journal"

_OBSERVER_ARMED_KEYS = {
    "schema",
    "mode",
    "unit",
    "process_identity",
    "stop_post_environment",
    "plan_path",
    "plan_sha256",
    "program",
    "request_path",
    "output_path",
    "source_selector_path",
    "raw_authority_paths",
    "ready_fifo",
    "release_fifo",
    "ready_sha256",
    "release_sha256",
}
_ADVERSARY_ARMED_KEYS = {
    "schema",
    "scenario",
    "unit",
    "actor",
    "plan_path",
    "plan_sha256",
    "program",
    "request_path",
    "request_sha256",
    "receipt_path",
    "ready_fifo",
    "release_fifo",
    "ready_sha256",
    "release_sha256",
}
_FORMAL_ARMED_KEYS = {
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
_OBSERVER_IDENTITY_KEYS = {
    "boot_id",
    "invocation_id",
    "pid",
    "proc_cgroup_raw",
    "starttime",
    "unified_cgroup",
}
_ADVERSARY_IDENTITY_KEYS = _OBSERVER_IDENTITY_KEYS | {
    "session_id",
    "stop_selector_environment",
}
_FORMAL_IDENTITY_KEYS = _OBSERVER_IDENTITY_KEYS | {
    "service_control_group",
    "service_device",
    "service_inode",
    "supervisor_device",
    "supervisor_inode",
}
_FORMAL_ACTION_ARMED_KEYS = {
    "schema",
    "action_id",
    "case_id",
    "variant",
    "unit",
    "process_identity",
    "cgroup_identity",
    "control_fifo",
    "systemd_armed_receipt_sha256",
    "plan_sha256",
    "expected_permit_sha256",
}
_B6_ARMED_KEYS = {
    "schema",
    "case_id",
    "variant",
    "unit",
    "fault",
    "declared_phase",
    "hook",
    "target_operation",
    "planned_ordinal",
    "process_identity",
    "plan_sha256",
    "systemd_armed_receipt_sha256",
    "before_fact",
    "ready_fifo",
    "release_fifo",
    "operation_receipt_path",
    "ready_sha256",
    "release_sha256",
    "signal_context",
}
_B6_OPERATION_KEYS = {
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
_FORMAL_PASS_RECEIPT_KEYS = {
    "schema",
    "case_id",
    "variant",
    "fixture_identity",
    "outcome",
    "baseline_inventory",
    "backend_open_inventory",
    "after_inventory",
    "final_inventory_proof",
    "case_result",
}
_FORMAL_REQUIREMENT_RECEIPT_KEYS = {
    "schema",
    "case_id",
    "variant",
    "fixture_identity",
    "outcome",
    "config_sha256",
    "requirement_code",
    "requirement",
}
_FORMAL_FIXTURE_IDENTITY_KEYS = {
    "config_sha256",
    "case_script",
    "case_script_sha256",
    "python_executable",
    "python_version",
    "isolated",
    "dont_write_bytecode",
    "native_extension",
    "native_extension_sha256",
    "spawn_backend",
    "spawn_backend_sha256",
    "accepted_probe",
    "accepted_probe_sha256",
}
_FORMAL_B5_RESULT_KEYS = {
    "failure",
    "descendant_binding",
    "transported_environment",
}
_FORMAL_DESCENDANT_BINDING_KEYS = {
    "plan_path",
    "plan_sha256",
    "request_path",
    "request_sha256",
    "receipt_path",
    "receipt_sha256",
    "actor",
    "descendant",
    "hold_release_fifo",
    "expected_job_name",
    "expected_job_cgroup",
    "process_spec",
    "process_spec_sha256",
}
_FORMAL_DESCENDANT_IDENTITY_KEYS = {
    "boot_id",
    "invocation_id",
    "pid",
    "proc_cgroup_raw",
    "session_id",
    "starttime",
    "stop_selector_environment",
    "unified_cgroup",
}
_FORMAL_B6_RESULT_KEYS = {
    "failure",
    "fault_ledger",
    "observed_pipe_size",
    "emitted_each_stream",
}
_FORMAL_B6_LEDGER_BASE_KEYS = {
    "armed_receipt_sha256",
    "operation_receipt_sha256",
    "injection_count",
    "operation_call_count",
    "operation_ordinal",
    "before",
    "after_release",
}
_FORMAL_FACT_KEYS = {"fact_type", "fields"}
_FORMAL_BINARY_KEYS = {"encoding", "sha256", "byte_length", "data"}
_FORMAL_CONFIG_KEYS = {
    "schema",
    "case_id",
    "variant",
    "receipt_directory",
    "receipt_name",
    "armed_receipt_name",
    "capture_directory",
    "scratch_directory",
    "directory_authorities",
    "control_fifo",
    "run_unit",
    "close_unit",
    "run_configured_directives",
    "run_expanded_properties",
    "invocation_lineage",
    "invocation_nonce",
    "ordinal",
    "case_script",
    "adversary_script",
    "adversary_sha256",
    "accepted_probe",
    "accepted_extension",
    "accepted_probe_sha256",
    "accepted_extension_sha256",
    "accepted_spawn_backend_sha256",
    "systemd_acquisition",
    "systemd_armed_receipt_sha256",
    "descendant_adversary_plan",
    "plan_sha256",
    "b6",
}
_FORMAL_DIRECTORY_AUTHORITY_NAMES = {
    "receipt_directory",
    "capture_directory",
    "scratch_directory",
}
_FORMAL_DIRECTORY_AUTHORITY_KEYS = {"path", "device", "inode", "mode", "uid", "gid"}
_PROGRAM_KEYS = {"path", "sha256", "identity"}
_PROGRAM_IDENTITY_KEYS = {"device", "inode", "mode"}
_DESCENDANT_PLAN_KEYS = {
    "schema",
    "scenario",
    "unit",
    "expected_job_name",
    "program_path",
    "program_sha256",
    "request_path",
    "receipt_path",
    "acquisition",
    "hold_release_fifo",
}
_DESCENDANT_REQUEST_KEYS = {
    "schema",
    "scenario",
    "unit",
    "expected_invocation_id",
    "expected_job_name",
    "expected_job_cgroup",
    "receipt_path",
    "hold_release_fifo",
}
_DESCENDANT_RECEIPT_KEYS = {
    "schema",
    "scenario",
    "unit",
    "actor",
    "expected_invocation_id",
    "expected_job_name",
    "expected_job_cgroup",
    "hold_release_fifo",
    "release_handshake",
    "request_path",
    "request_sha256",
    "descendant",
    "formal_plan_binding",
}
_DESCENDANT_PLAN_BINDING_KEYS = {
    "schema",
    "scenario",
    "unit",
    "expected_job_name",
    "plan_path",
    "plan_sha256",
    "program",
    "acquisition",
    "hold_release_fifo",
    "materialized_request_sha256",
}
_B5_ACTION_KEYS = {
    "schema",
    "action_id",
    "case_id",
    "variant",
    "control_writer_open_count",
    "permit_write_count",
    "ownership",
    "descendant_evidence",
}
_B5_DESCENDANT_EVIDENCE_KEYS = {
    "plan_path",
    "plan_sha256",
    "request_path",
    "request_sha256",
    "receipt_path",
    "receipt_sha256",
    "program",
    "hold_release_fifo",
    "expected_job_name",
    "expected_job_cgroup",
    "actor",
    "descendant",
    "live_descendant",
}
_ADVERSARY_ROLE_SCENARIOS = {
    "run-main": {
        "h2-main-nonzero",
        "h3-main-signal",
        "h7-guardian-hold",
        "h8-extra-topology-hold",
        "h10-gc-negative",
        "h11-unbounded-hold",
    },
    "h4-stop-post": {"h4-stoppost-failure"},
    "failed-closer": {"h9-failed-closer"},
}

_MANAGER_METHOD_SIGNATURES = {
    "Subscribe": "",
    "RefUnit": "s",
    "StartUnit": "ss",
    "StopUnit": "ss",
    "ResetFailedUnit": "s",
    "UnrefUnit": "s",
    "LoadUnit": "s",
    "GetUnit": "s",
}
_SIGNAL_SIGNATURES = {
    "JobNew": "uos",
    "JobRemoved": "uoss",
    "UnitNew": "so",
    "UnitRemoved": "so",
    "PropertiesChanged": "sa{sv}as",
}
_PROPERTY_SIGNATURES = {
    UNIT_INTERFACE: {
        "Id": "s",
        "InvocationID": "ay",
        "LoadState": "s",
        "ActiveState": "s",
        "SubState": "s",
        "After": "as",
        "CollectMode": "s",
        "FragmentPath": "s",
        "NeedDaemonReload": "b",
        "OnSuccess": "as",
        "OnFailure": "as",
    },
    SERVICE_INTERFACE: {
        "ControlGroup": "s",
        "Delegate": "b",
        "DelegateControllers": "as",
        "DelegateSubgroup": "s",
        "ExecMainCode": "i",
        "ExecMainStatus": "i",
        "ExecStopPost": "a(sasbttttuii)",
        "Group": "s",
        "KillMode": "s",
        "MainPID": "u",
        "Restart": "s",
        "Result": "s",
        "TimeoutStartUSec": "t",
        "TimeoutStopUSec": "t",
        "User": "s",
    },
}
_MANIFEST_KEYS = {
    "schema",
    "scenario",
    "descriptor_path",
    "run_unit",
    "closer_unit",
    "boot_id_path",
    "input_root",
    "receipt_root",
    "acquisitions",
    "outputs",
    "scenario_input",
    "formal_actions",
    "preflight_receipt",
    "static_inventory",
    "static_roles",
}
_ACQUISITION_KEYS = {"role", "armed_receipt_path", "ready_fifo", "release_fifo"}
_FIFO_KEYS = {"path", "device", "inode"}
_OUTPUT_KEYS = {"role", "path"}
_FORMAL_ACTION_KEYS = {
    "action_id",
    "armed_receipt_path",
    "operation_receipt_path",
    "action_ledger_path",
    "control_fifo",
}
_STATIC_ROLE_KEYS = {"role", "unit", "owner", "mode", "plan", "program"}
_UNIT_RE = re.compile(r"scion-w3-[A-Za-z0-9_.:-]+\.service\Z")
_ROLE_RE = re.compile(r"[a-z][a-z0-9]*(?:[-_.][a-z0-9]+)*\Z")
_INVOCATION_RE = re.compile(r"[0-9a-f]{32}\Z")
_JOB_NAME_RE = re.compile(r"job-(0|[1-9][0-9]{0,19})-[0-9a-f]{16}\Z")
_BOOT_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z"
)


@dataclass(frozen=True, slots=True)
class RoleOwner:
    schema: str
    mode: str


@dataclass(frozen=True, slots=True)
class TerminalPolicy:
    run: tuple[str, str, str, int, int, int, int]
    stop: tuple[str, str, str]
    closer: tuple[str, str, str, str, int, int]
    accept_stop_topology: bool = True


@dataclass(frozen=True, slots=True)
class ScenarioPolicy:
    scenario_id: str
    run_owner: RoleOwner
    stop_owner: RoleOwner | None
    closer_owner: RoleOwner | None
    acquisition_order: tuple[str, ...]
    required_outputs: frozenset[str]
    allowed_methods: frozenset[str]
    terminal: TerminalPolicy
    final_classification: str
    formal_case: tuple[str, str] | None = None
    formal_actions: tuple[str, ...] = ()
    formal_completion: str | None = None
    formal_expected_fact_type: str | None = None


_OBSERVER_RUN = RoleOwner("observer", "run-main")
_OBSERVER_STOP = RoleOwner("observer", "exec-stop-post")
_OBSERVER_CLOSER = RoleOwner("observer", "closer")
_FORMAL_RUN = RoleOwner("formal", "formal-case")

_BASE_OUTPUTS = frozenset(
    {
        "run-main-properties",
        "exec-stop-post-properties",
        "closer-properties",
        "source-selector",
        "final-run-properties",
        "final-closer-properties",
        "h12-absence",
        "h0",
        "manager-events",
        "signals",
        "journal",
        "final",
    }
)
_BASE_METHODS = frozenset(
    {"Subscribe", "RefUnit", "StartUnit", "ResetFailedUnit", "UnrefUnit", "GetUnit"}
)


def _terminal(
    *,
    result: str = "success",
    active: str = "inactive",
    sub: str = "dead",
    main_code: int = 1,
    main_status: int = 0,
    post_code: int = 1,
    post_status: int = 0,
    service_result: str = "success",
    exit_code: str = "exited",
    exit_status: str = "0",
    closer_result: str = "success",
    closer_active: str = "inactive",
    closer_sub: str = "dead",
    closer_code: int = 1,
    closer_status: int = 0,
    accept_stop_topology: bool = True,
) -> TerminalPolicy:
    return TerminalPolicy(
        (result, active, sub, main_code, main_status, post_code, post_status),
        (service_result, exit_code, exit_status),
        (
            "loaded",
            closer_active,
            closer_sub,
            closer_result,
            closer_code,
            closer_status,
        ),
        accept_stop_topology,
    )


def _policy(
    scenario: str,
    *,
    run: RoleOwner,
    stop: RoleOwner | None = _OBSERVER_STOP,
    closer: RoleOwner | None = _OBSERVER_CLOSER,
    terminal: TerminalPolicy = _terminal(),
    classification: str = "formal-positive-evidence",
    methods: frozenset[str] = _BASE_METHODS,
    outputs: frozenset[str] = _BASE_OUTPUTS,
    formal_case: tuple[str, str] | None = None,
    formal_actions: tuple[str, ...] = (),
    formal_completion: str | None = None,
    formal_expected_fact_type: str | None = None,
) -> ScenarioPolicy:
    effective_outputs = set(outputs)
    if stop is not None and stop.mode == "h4-stoppost-failure":
        effective_outputs.discard("exec-stop-post-properties")
        effective_outputs.add("h4-stop-post-properties")
    if closer is not None and closer.mode == "h9-failed-closer":
        effective_outputs.discard("closer-properties")
        effective_outputs.add("failed-closer-properties")
    if stop is None and closer is None:
        order = ("run-main",)
    else:
        order = (
            "run-main",
            "h4-stop-post" if stop and stop.mode == "h4-stoppost-failure" else "exec-stop-post",
            "failed-closer" if closer and closer.mode == "h9-failed-closer" else "closer",
        )
    return ScenarioPolicy(
        scenario,
        run,
        stop,
        closer,
        order,
        frozenset(effective_outputs),
        methods,
        terminal,
        classification,
        formal_case,
        formal_actions,
        formal_completion,
        formal_expected_fact_type,
    )


_SCENARIO_POLICIES: dict[str, ScenarioPolicy] = {
    "H0": ScenarioPolicy(
        "H0",
        _OBSERVER_RUN,
        None,
        None,
        (),
        frozenset({"h0", "manager-events", "final"}),
        frozenset({"GetUnit"}),
        _terminal(),
        "host-requirements-evidence",
    ),
    "H1": _policy("H1", run=_OBSERVER_RUN),
    "H2": _policy(
        "H2",
        run=RoleOwner("adversary", "h2-main-nonzero"),
        terminal=_terminal(
            result="exit-code", active="failed", sub="failed", main_status=23,
            service_result="exit-code", exit_status="23",
        ),
        classification="expected-main-exit-code-evidence",
    ),
    "H3": _policy(
        "H3",
        run=RoleOwner("adversary", "h3-main-signal"),
        terminal=_terminal(
            result="core-dump", active="failed", sub="failed", main_code=3,
            main_status=6, service_result="core-dump", exit_code="dumped",
            exit_status="6",
        ),
        classification="expected-main-sigabrt-evidence",
    ),
    "H4": _policy(
        "H4",
        run=_OBSERVER_RUN,
        stop=RoleOwner("adversary", "h4-stoppost-failure"),
        terminal=_terminal(
            result="exit-code", active="failed", sub="failed", post_status=47,
        ),
        classification="expected-stop-post-failure-evidence",
    ),
    "H5": _policy(
        "H5", run=_FORMAL_RUN, formal_case=("B1", "clean"),
        outputs=_BASE_OUTPUTS | {"formal-final"},
        classification="accepted-clean-native-evidence",
        formal_completion="typed",
    ),
    "H6": _policy(
        "H6", run=_FORMAL_RUN, formal_case=("B5", "setsid-retain-stdio"),
        formal_actions=("b5-never-release-hold",),
        outputs=_BASE_OUTPUTS | {"formal-final", "formal-action"},
        classification="accepted-containment-failure-evidence",
        formal_completion="typed",
    ),
    "H7": _policy(
        "H7",
        run=RoleOwner("adversary", "h7-guardian-hold"),
        terminal=_terminal(
            result="signal", active="failed", sub="failed", main_code=2,
            main_status=15, service_result="signal", exit_code="killed",
            exit_status="15",
        ),
        methods=_BASE_METHODS | {"StopUnit"},
        classification="expected-systemd-owned-stop-evidence",
    ),
    "H8": _policy(
        "H8",
        run=RoleOwner("adversary", "h8-extra-topology-hold"),
        terminal=_terminal(accept_stop_topology=False),
        classification="formal-negative-evidence/H8_EXTRA_TOPOLOGY",
        outputs=_BASE_OUTPUTS | {"h8-ledger", "h8-inventory"},
    ),
    "H9": _policy(
        "H9",
        run=_OBSERVER_RUN,
        closer=RoleOwner("adversary", "h9-failed-closer"),
        terminal=_terminal(
            closer_result="exit-code", closer_active="failed", closer_sub="failed",
            closer_status=61,
        ),
        classification="rejected-failed-closer",
    ),
    "H10": _policy(
        "H10",
        run=RoleOwner("adversary", "h10-gc-negative"),
        stop=None,
        closer=None,
        terminal=_terminal(result="exit-code", active="failed", sub="failed", main_status=29),
        classification="rejected-failed-identity-loss",
        methods=frozenset({"Subscribe", "StartUnit", "LoadUnit", "GetUnit"}),
        outputs=frozenset(
            {
                "run-main-properties",
                "h10-reloaded-properties",
                "h10-absence",
                "h0",
                "manager-events",
                "signals",
                "journal",
                "final",
            }
        ),
    ),
    "H11": _policy(
        "H11", run=RoleOwner("adversary", "h11-unbounded-hold"),
        classification="accepted-after-explicit-fixture-release",
    ),
    "H12": _policy("H12", run=_OBSERVER_RUN),
}


def _b6_lifecycle_abi() -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    phases = {
        "blocked": ("blocked", "BLOCKED"),
        "just-released": ("just-released", "RELEASED_DRAINING"),
        "leader-terminal": ("leader-terminal", "LEADER_TERMINAL"),
        "reaped-but-populated": ("reaped-populated", "LEADER_REAPED_DRAINING"),
        "empty-before-eof": ("empty-before-eof", "LEADER_REAPED_DRAINING"),
    }
    faults = {
        "issuer": ("issuer-signal", "ISSUER_INTERRUPTED", "ContainedSpawnFailure"),
        "storage": ("capture-storage", "CAPTURE_FAILED", "ContainedSpawnFailure"),
        "close": ("authority-close", "AUTHORITY_CLOSE_UNCERTAIN", "FAILSTOP"),
    }
    installable = {
        ("issuer", "blocked"): (
            "guard-restore",
            "_IssuerSignalGuard.restore",
            "10",
        ),
        ("issuer", "just-released"): (
            "guard-restore",
            "_IssuerSignalGuard.restore",
            "11",
        ),
        ("issuer", "leader-terminal"): (
            "terminal-fact",
            "WaitFact.from_native",
            "1",
        ),
        ("issuer", "reaped-but-populated"): (
            "reaped-pidfd-close",
            "_close_exact(poll_pidfd)",
            "1",
        ),
        ("storage", "just-released"): (
            "capture-write",
            "_write_spool",
            "1",
        ),
    }
    for prefix, (fault, reason, fact_type) in faults.items():
        for phase, (variant_phase, expected_phase) in phases.items():
            hook, operation, ordinal = installable.get(
                (prefix, phase),
                ("unobservable-source-seam", f"{fault}:{phase}", "1"),
            )
            result[f"{prefix}-{variant_phase}"] = {
                "fault": fault,
                "declared_phase": phase,
                "hook": hook,
                "target_operation": operation,
                "planned_ordinal": ordinal,
                "expected_fact_type": fact_type,
                "expected_phase": expected_phase,
                "expected_reason": reason,
            }
    return result


_B6_ABI = {
    "issuer-backend-open": {
        "fault": "issuer-signal",
        "declared_phase": "backend-open",
        "hook": "service-consume",
        "target_operation": "ServiceCgroup._consume",
        "planned_ordinal": "1",
        "expected_fact_type": "BackendOpenFailure",
        "expected_phase": "SERVICE_CONSUME",
        "expected_reason": "ISSUER_INTERRUPTED",
    },
    "issuer-capture-prepare": {
        "fault": "issuer-signal",
        "declared_phase": "capture-prepare",
        "hook": "capture-spool-open",
        "target_operation": "os.open(O_TMPFILE)",
        "planned_ordinal": "1",
        "expected_fact_type": "PreHandleFailure",
        "expected_phase": "CAPTURE_PREPARE",
        "expected_reason": "ISSUER_INTERRUPTED_PRE_HANDLE",
    },
    "issuer-job-created-pre-native": {
        "fault": "issuer-signal",
        "declared_phase": "job-created-pre-native",
        "hook": "pre-native-borrow",
        "target_operation": "_JobCgroup._consume_spawn_dirfd_borrow",
        "planned_ordinal": "1",
        "expected_fact_type": "PreHandleFailure",
        "expected_phase": "PRE_NATIVE_READY",
        "expected_reason": "ISSUER_INTERRUPTED_PRE_HANDLE",
    },
    "issuer-native-no-handle": {
        "fault": "issuer-signal",
        "declared_phase": "native-no-handle",
        "hook": "unobservable-source-seam",
        "target_operation": "native.spawn_blocked",
        "planned_ordinal": "1",
        "expected_fact_type": "PreHandleFailure",
        "expected_phase": "NATIVE_NO_HANDLE",
        "expected_reason": "ISSUER_INTERRUPTED_PRE_HANDLE",
    },
    **_b6_lifecycle_abi(),
}
_B6_INSTALLABLE_HOOKS = {
    "service-consume",
    "capture-spool-open",
    "pre-native-borrow",
    "guard-restore",
    "terminal-fact",
    "reaped-pidfd-close",
    "capture-write",
}
_B6_INSTALLABLE_VARIANTS = frozenset(
    variant for variant, abi in _B6_ABI.items() if abi["hook"] in _B6_INSTALLABLE_HOOKS
)
_B6_REQUIREMENT_VARIANTS = frozenset(_B6_ABI) - _B6_INSTALLABLE_VARIANTS
_B6_DECLARED_FAILSTOP_VARIANTS = frozenset(
    variant
    for variant, abi in _B6_ABI.items()
    if abi["expected_fact_type"] == "FAILSTOP"
)
_B6_OPERATION_SEMANTICS = {
    "service-consume": {
        "operation_state": "RETURNED",
        "effect_state": "AUTHORITY_MOVED",
        "return_type": "scion.runtime.execution.cgroup_v2._ServiceCgroupAuthority",
        "exception_type": None,
        "errno": None,
        "postcondition": "exact target operation completed once",
    },
    "capture-spool-open": {
        "operation_state": "RETURNED",
        "effect_state": "FD_ACQUIRED",
        "return_type": "builtins.int",
        "exception_type": None,
        "errno": None,
        "postcondition": "exact target operation completed once",
    },
    "pre-native-borrow": {
        "operation_state": "RETURNED",
        "effect_state": "PINNED_BORROW_RETURNED",
        "return_type": "builtins.int",
        "exception_type": None,
        "errno": None,
        "postcondition": "exact target operation completed once",
    },
    "guard-restore": {
        "operation_state": "RETURNED",
        "effect_state": "MASK_RESTORED_HANDLER_DELIVERED",
        "return_type": "builtins.bool",
        "exception_type": None,
        "errno": None,
        "postcondition": "fixed handler raised inside production restore and guard recovery returned true",
    },
    "terminal-fact": {
        "operation_state": "RETURNED",
        "effect_state": "WAIT_FACT_RETURNED",
        "return_type": "scion.runtime.execution.model.WaitFact",
        "exception_type": None,
        "errno": None,
        "postcondition": "exact target operation completed once",
    },
    "reaped-pidfd-close": {
        "operation_state": "RETURNED",
        "effect_state": "PIDFD_CLOSED",
        "return_type": "builtins.NoneType",
        "exception_type": None,
        "errno": None,
        "postcondition": "exact target operation completed once",
    },
    "capture-write": {
        "operation_state": "INJECTED_RETURN",
        "effect_state": "ORIGINAL_STORAGE_WRITE_NOT_CALLED",
        "return_type": "builtins.bool",
        "exception_type": None,
        "errno": None,
        "postcondition": "capture storage became unavailable after one injected false",
    },
}


_B_VARIANTS = {
    "B0": ("blocked-sentinel",),
    "B1": ("clean", "nonzero", "signal", "core"),
    "B2": ("wrong-executable", "wrong-cwd"),
    "B3": ("dual-binary",),
    "B4": ("release-after-job-kill",),
    "B5": ("setsid-retain-stdio", "double-fork-close-stdio"),
    "B6": (
        "issuer-blocked", "issuer-just-released", "issuer-leader-terminal",
        "issuer-reaped-populated", "issuer-empty-before-eof", "storage-blocked",
        "storage-just-released", "storage-leader-terminal", "storage-reaped-populated",
        "storage-empty-before-eof", "close-blocked", "close-just-released",
        "close-leader-terminal", "close-reaped-populated", "close-empty-before-eof",
        "issuer-backend-open", "issuer-capture-prepare", "issuer-job-created-pre-native",
        "issuer-native-no-handle",
    ),
    "B7": (
        "tmpfile-unsupported", "tmpfile-allocation", "tmpfile-open",
        "cgroup-inode-drift", "unexpected-sibling", "unexpected-nested",
        "supervisor-extra-task",
    ),
    "B8": ("final-inventory",),
}


def _formal_action_ids(case_id: str, variant: str) -> tuple[str, ...]:
    if case_id == "B4":
        return ("b4-kill-before-release",)
    if case_id == "B5":
        return ("b5-never-release-hold",)
    if case_id == "B6":
        if variant in _B6_REQUIREMENT_VARIANTS:
            return ()
        return ("b6-issuer-send",) if variant.startswith("issuer-") else ("b6-zero-signal-release",)
    if case_id == "B7" and not variant.startswith("tmpfile-"):
        return (f"b7-{variant}",)
    return ()


for _case_id, _variants in _B_VARIANTS.items():
    for _variant in _variants:
        _scenario_id = f"{_case_id}/{_variant}"
        _actions = _formal_action_ids(_case_id, _variant)
        _external_b7 = _case_id == "B7" and not _variant.startswith("tmpfile-")
        _b6_abi = _B6_ABI.get(_variant) if _case_id == "B6" else None
        _completion = (
            "failstop"
            if _external_b7
            else "requirement-missing"
            if _case_id == "B6" and _variant in _B6_REQUIREMENT_VARIANTS
            else "failstop"
            if _b6_abi is not None and _b6_abi["expected_fact_type"] == "FAILSTOP"
            else "typed"
        )
        _failstop = _completion == "failstop"
        _SCENARIO_POLICIES[_scenario_id] = _policy(
            _scenario_id,
            run=_FORMAL_RUN,
            formal_case=(_case_id, _variant),
            formal_actions=_actions,
            outputs=_BASE_OUTPUTS
            | ({"formal-failstop"} if _failstop else {"formal-final"})
            | ({"formal-action"} if _actions else set()),
            terminal=(
                _terminal(
                    result="core-dump",
                    active="failed",
                    sub="failed",
                    main_code=3,
                    main_status=6,
                    service_result="core-dump",
                    exit_code="dumped",
                    exit_status="6",
                )
                if _failstop
                else _terminal(
                    result="exit-code",
                    active="failed",
                    sub="failed",
                    main_status=78,
                    service_result="exit-code",
                    exit_status="78",
                )
                if _completion == "requirement-missing"
                else _terminal()
            ),
            classification=(
                "formal-negative-evidence/B7_EXTERNAL_TOPOLOGY_FAILSTOP"
                if _external_b7
                else "delegated-formal-requirement-missing"
                if _completion == "requirement-missing"
                else "delegated-formal-evidence"
            ),
            formal_completion=_completion,
            formal_expected_fact_type=(
                None if _b6_abi is None else _b6_abi["expected_fact_type"]
            ),
        )


class HarnessError(RuntimeError):
    """Formal system-manager evidence is incomplete or ambiguous."""


def _fail(message: str) -> NoReturn:
    raise HarnessError(message)


def _object_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> NoReturn:
    _fail(f"forbidden JSON constant {value!r}")


def _canonical(value: Any) -> bytes:
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=True,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise HarnessError("value cannot be encoded as canonical JSON") from exc


def _read_all(descriptor: int) -> bytes:
    chunks: list[bytes] = []
    while True:
        chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def _read_regular(path: Path, *, label: str) -> bytes:
    try:
        before = path.lstat()
    except OSError as exc:
        raise HarnessError(f"cannot stat {label}: {path}") from exc
    if not stat.S_ISREG(before.st_mode):
        _fail(f"{label} must be a non-symlink regular file")
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        try:
            opened = os.fstat(descriptor)
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                _fail(f"{label} identity changed while opening")
            raw = _read_all(descriptor)
            after = os.fstat(descriptor)
        finally:
            os.close(descriptor)
    except HarnessError:
        raise
    except OSError as exc:
        raise HarnessError(f"cannot read {label}: {path}") from exc
    if (
        (after.st_dev, after.st_ino) != (before.st_dev, before.st_ino)
        or after.st_size != len(raw)
        or after.st_mtime_ns != before.st_mtime_ns
    ):
        _fail(f"{label} changed while being read")
    return raw


def _decode_canonical_raw(raw: bytes, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            raw.decode("utf-8", "strict"),
            object_pairs_hook=_object_no_duplicates,
            parse_constant=_reject_constant,
        )
    except HarnessError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise HarnessError(f"{label} is not strict UTF-8 JSON") from exc
    if type(value) is not dict or _canonical(value) != raw:
        _fail(f"{label} must be one exact canonical JSON object")
    return value


def _decode_canonical(path: Path, *, label: str) -> dict[str, Any]:
    return _decode_canonical_raw(_read_regular(path, label=label), label=label)


def _exact(value: dict[str, Any], keys: set[str], *, label: str) -> None:
    actual = set(value)
    if actual != keys:
        _fail(
            f"{label} keys mismatch: missing={sorted(keys - actual)!r}, "
            f"unknown={sorted(actual - keys)!r}"
        )


def _text(value: Any, *, label: str) -> str:
    if type(value) is not str or not value:
        _fail(f"{label} must be a nonempty string")
    try:
        encoded = value.encode("utf-8", "strict")
    except UnicodeError as exc:
        raise HarnessError(f"{label} is not strict UTF-8") from exc
    if any(byte < 0x20 or byte == 0x7F for byte in encoded):
        _fail(f"{label} contains a forbidden control byte")
    return value


def _path(value: Any, *, label: str) -> Path:
    raw = _text(value, label=label)
    result = Path(raw)
    if not result.is_absolute() or str(result) != raw or any(
        part in {".", ".."} for part in result.parts
    ):
        _fail(f"{label} must be one normalized absolute path")
    return result


def _decimal(value: Any, *, label: str) -> int:
    if type(value) is not str or re.fullmatch(r"0|[1-9][0-9]*", value) is None:
        _fail(f"{label} must be canonical unsigned decimal text")
    result = int(value, 10)
    if result > (1 << 64) - 1:
        _fail(f"{label} exceeds uint64")
    return result


def _freeze_formal_directory_authorities(
    values: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    authorities: dict[str, dict[str, Any]] = {}
    for name in sorted(_FORMAL_DIRECTORY_AUTHORITY_NAMES):
        path = _path(values[name], label=f"formal {name}")
        try:
            info = path.lstat()
        except OSError as exc:
            raise HarnessError(f"cannot stat formal {name}: {path}") from exc
        if not stat.S_ISDIR(info.st_mode) or path.is_symlink():
            _fail(f"formal {name} is not one non-symlink directory")
        authorities[name] = {
            "path": str(path),
            "device": info.st_dev,
            "inode": info.st_ino,
            "mode": stat.S_IMODE(info.st_mode),
            "uid": info.st_uid,
            "gid": info.st_gid,
        }
    return authorities


def _revalidate_formal_directory_authorities(
    values: dict[str, Any],
    *,
    expected: dict[str, dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    raw = values.get("directory_authorities")
    if type(raw) is not dict:
        _fail("formal directory_authorities is not one exact object")
    _exact(raw, _FORMAL_DIRECTORY_AUTHORITY_NAMES, label="formal directory_authorities")
    declared: dict[str, dict[str, Any]] = {}
    for name in sorted(_FORMAL_DIRECTORY_AUTHORITY_NAMES):
        item = raw[name]
        if type(item) is not dict:
            _fail(f"formal directory_authorities.{name} is not one exact object")
        _exact(
            item,
            _FORMAL_DIRECTORY_AUTHORITY_KEYS,
            label=f"formal directory_authorities.{name}",
        )
        path = _path(item["path"], label=f"formal directory_authorities.{name}.path")
        if path != _path(values[name], label=f"formal {name}"):
            _fail(f"formal {name} path differs from its directory authority")
        for field in ("device", "inode", "mode", "uid", "gid"):
            if type(item[field]) is not int or item[field] < 0:
                _fail(f"formal directory_authorities.{name}.{field} is not nonnegative int")
        declared[name] = dict(item)
    observed = _freeze_formal_directory_authorities(values)
    if declared != observed:
        _fail("formal directory authority identity/mode/ownership drifted")
    if expected is not None and declared != expected:
        _fail("formal directory authorities differ from the pre-StartUnit pins")
    return observed


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(
            path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
        )
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError as exc:
        raise HarnessError(f"cannot fsync receipt directory: {path}") from exc


def _write_no_replace(path: Path, value: Any, *, mode: int = 0o444) -> None:
    raw = _canonical(value)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, mode)
        try:
            view = memoryview(raw)
            while view:
                count = os.write(descriptor, view)
                if count <= 0:
                    _fail("receipt write made no progress")
                view = view[count:]
            os.fsync(descriptor)
            os.fchmod(descriptor, mode)
        finally:
            os.close(descriptor)
        _fsync_directory(path.parent)
    except HarnessError:
        raise
    except OSError as exc:
        raise HarnessError(f"cannot publish no-replace receipt: {path}") from exc


@dataclass(frozen=True)
class SignatureNode:
    code: str
    children: tuple["SignatureNode", ...] = ()


def _parse_one(signature: str, offset: int) -> tuple[SignatureNode, int]:
    if offset >= len(signature):
        _fail("incomplete D-Bus signature")
    code = signature[offset]
    if code in "ybnqiuxtdsohg":
        return SignatureNode(code), offset + 1
    if code == "v":
        return SignatureNode(code), offset + 1
    if code == "a":
        child, next_offset = _parse_one(signature, offset + 1)
        return SignatureNode(code, (child,)), next_offset
    if code == "(":
        children: list[SignatureNode] = []
        cursor = offset + 1
        while cursor < len(signature) and signature[cursor] != ")":
            child, cursor = _parse_one(signature, cursor)
            children.append(child)
        if cursor >= len(signature) or not children:
            _fail("unclosed or empty D-Bus struct signature")
        return SignatureNode(code, tuple(children)), cursor + 1
    if code == "{":
        key, cursor = _parse_one(signature, offset + 1)
        value, cursor = _parse_one(signature, cursor)
        if cursor >= len(signature) or signature[cursor] != "}":
            _fail("unclosed D-Bus dictionary entry")
        return SignatureNode(code, (key, value)), cursor + 1
    _fail(f"unsupported D-Bus signature code {code!r}")


def _parse_signature(signature: str) -> SignatureNode:
    node, cursor = _parse_one(signature, 0)
    if cursor != len(signature):
        _fail("D-Bus signature contains multiple top-level values")
    return node


def _binary(signature: str, raw: bytes) -> dict[str, Any]:
    return {
        "signature": signature,
        "kind": "binary",
        "length": str(len(raw)),
        "base64": base64.b64encode(raw).decode("ascii"),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _encode_node(node: SignatureNode, value: Any) -> dict[str, Any]:
    code = node.code
    if code == "a" and node.children[0].code == "y":
        try:
            raw = bytes(value)
        except (TypeError, ValueError) as exc:
            raise HarnessError("ay value is not lossless bytes") from exc
        return _binary("ay", raw)
    if code in {"s", "o", "g"}:
        if not isinstance(value, str):
            _fail(f"{code} value is not text")
        text = str(value)
        text.encode("utf-8", "strict")
        return {"signature": code, "kind": "text", "value": text}
    if code == "b":
        if not isinstance(value, (bool, int)) or int(value) not in {0, 1}:
            _fail("b value is not an exact boolean")
        return {"signature": code, "kind": "boolean", "value": bool(value)}
    if code in "ynqiuxt":
        if isinstance(value, bool) or not isinstance(value, int):
            _fail(f"{code} value is not an integer")
        return {"signature": code, "kind": "integer", "value": str(int(value))}
    if code == "d":
        _fail("floating-point D-Bus evidence is not accepted")
    if code == "v":
        signature = _runtime_signature(value)
        return {
            "signature": "v",
            "kind": "variant",
            "value": _encode_node(_parse_signature(signature), value),
        }
    if code == "a":
        child = node.children[0]
        if isinstance(value, (str, bytes, bytearray)):
            _fail("array value is not one ordered sequence")
        try:
            items = list(value.items()) if child.code == "{" else list(value)
        except (AttributeError, TypeError) as exc:
            raise HarnessError("array value is not iterable in signature order") from exc
        return {
            "signature": "a" + _signature_text(child),
            "kind": "array",
            "items": [_encode_node(child, item) for item in items],
        }
    if code == "(":
        if isinstance(value, (str, bytes, bytearray)):
            _fail("struct value is not one ordered sequence")
        items = list(value)
        if len(items) != len(node.children):
            _fail("struct arity does not match signature")
        return {
            "signature": _signature_text(node),
            "kind": "struct",
            "items": [
                _encode_node(child, item) for child, item in zip(node.children, items)
            ],
        }
    if code == "{":
        if not isinstance(value, tuple) or len(value) != 2:
            _fail("dictionary entry must preserve one exact pair")
        return {
            "signature": _signature_text(node),
            "kind": "dict-entry",
            "key": _encode_node(node.children[0], value[0]),
            "value": _encode_node(node.children[1], value[1]),
        }
    _fail(f"unsupported D-Bus value signature {code!r}")


def _runtime_signature(value: Any) -> str:
    explicit = getattr(value, "signature", None)
    type_name = type(value).__name__
    if type_name == "Array" and explicit is not None:
        return "a" + str(explicit)
    if type_name == "Dictionary" and explicit is not None:
        return "a" + str(explicit)
    if explicit is not None and str(explicit):
        return str(explicit)
    names = {
        "Byte": "y",
        "Boolean": "b",
        "Int16": "n",
        "UInt16": "q",
        "Int32": "i",
        "UInt32": "u",
        "Int64": "x",
        "UInt64": "t",
        "Double": "d",
        "String": "s",
        "ObjectPath": "o",
        "Signature": "g",
        "ByteArray": "ay",
    }
    if type_name in names:
        return names[type_name]
    if type_name == "Struct":
        return "(" + "".join(_runtime_signature(item) for item in value) + ")"
    _fail(f"variant leaf type {type_name!r} has no exact D-Bus signature")


def _signature_text(node: SignatureNode) -> str:
    if node.code == "a":
        return "a" + _signature_text(node.children[0])
    if node.code == "(":
        return "(" + "".join(_signature_text(child) for child in node.children) + ")"
    if node.code == "{":
        return "{" + "".join(_signature_text(child) for child in node.children) + "}"
    return node.code


def encode_dbus(signature: str, value: Any) -> dict[str, Any]:
    """Encode one exact-signature D-Bus value without textual pretty-printing."""

    return _encode_node(_parse_signature(signature), value)


def encode_journal_value(value: Any) -> dict[str, Any]:
    """Losslessly freeze text, binary and repeated journal fields."""

    if isinstance(value, bytes):
        try:
            text = value.decode("utf-8", "strict")
        except UnicodeError:
            return _binary("ay", value)
        if any(byte < 0x20 and byte not in {0x09} for byte in value):
            return _binary("ay", value)
        return {"kind": "text", "value": text, "length": str(len(value))}
    if isinstance(value, str):
        encoded = value.encode("utf-8", "strict")
        return {"kind": "text", "value": value, "length": str(len(encoded))}
    if isinstance(value, (list, tuple)):
        return {
            "kind": "repeated",
            "items": [encode_journal_value(item) for item in value],
        }
    _fail("journal field has unsupported non-lossless value")


@dataclass(frozen=True)
class StartDescriptor:
    unit: str


def decode_start_descriptor(path: Path, expected_unit: str) -> StartDescriptor:
    return _decode_start_descriptor_raw(
        _read_regular(path, label="StartUnit descriptor"), expected_unit
    )


def _decode_start_descriptor_raw(raw: bytes, expected_unit: str) -> StartDescriptor:
    value = _decode_canonical_raw(raw, label="StartUnit descriptor")
    expected = {
        "schema": DESCRIPTOR_SCHEMA,
        "bus": "system",
        "destination": SYSTEMD_DESTINATION,
        "object": MANAGER_PATH,
        "interface": MANAGER_INTERFACE,
        "method": "StartUnit",
        "signature": "ss",
        "unit": expected_unit,
        "mode": "fail",
        "owner": "generic_backend_systemd_harness.py",
    }
    if value != expected:
        _fail("StartUnit descriptor is not the exact canonical launch authority")
    return StartDescriptor(unit=expected_unit)


@dataclass(frozen=True)
class FifoIdentity:
    path: Path
    device: int
    inode: int

    @classmethod
    def decode(cls, value: Any, *, label: str) -> "FifoIdentity":
        if type(value) is not dict:
            _fail(f"{label} must be one exact FIFO identity")
        _exact(value, _FIFO_KEYS, label=label)
        return cls(
            path=_path(value["path"], label=f"{label}.path"),
            device=_decimal(value["device"], label=f"{label}.device"),
            inode=_decimal(value["inode"], label=f"{label}.inode"),
        )

    def prove(self, descriptor: int, *, label: str) -> None:
        info = os.fstat(descriptor)
        if not stat.S_ISFIFO(info.st_mode) or (info.st_dev, info.st_ino) != (
            self.device,
            self.inode,
        ):
            _fail(f"{label} FIFO identity drifted")


@dataclass(frozen=True)
class Acquisition:
    role: str
    armed_receipt_path: Path
    ready_fifo: FifoIdentity
    release_fifo: FifoIdentity

    @classmethod
    def decode(cls, value: Any, *, label: str) -> "Acquisition":
        if type(value) is not dict:
            _fail(f"{label} must be one acquisition object")
        _exact(value, _ACQUISITION_KEYS, label=label)
        role = _text(value["role"], label=f"{label}.role")
        if _ROLE_RE.fullmatch(role) is None:
            _fail(f"{label}.role is not canonical")
        return cls(
            role=role,
            armed_receipt_path=_path(
                value["armed_receipt_path"], label=f"{label}.armed_receipt_path"
            ),
            ready_fifo=FifoIdentity.decode(value["ready_fifo"], label=f"{label}.ready_fifo"),
            release_fifo=FifoIdentity.decode(
                value["release_fifo"], label=f"{label}.release_fifo"
            ),
        )


@dataclass(frozen=True)
class FormalAction:
    action_id: str
    armed_receipt_path: Path | None
    operation_receipt_path: Path | None
    action_ledger_path: Path
    control_fifo: FifoIdentity | None

    @classmethod
    def decode(cls, value: Any, *, label: str) -> "FormalAction":
        if type(value) is not dict:
            _fail(f"{label} must be one formal action object")
        _exact(value, _FORMAL_ACTION_KEYS, label=label)
        action_id = _text(value["action_id"], label=f"{label}.action_id")
        if _ROLE_RE.fullmatch(action_id) is None:
            _fail(f"{label}.action_id is not canonical")

        def optional_path(raw: Any, name: str) -> Path | None:
            return None if raw is None else _path(raw, label=f"{label}.{name}")

        fifo = value["control_fifo"]
        return cls(
            action_id,
            optional_path(value["armed_receipt_path"], "armed_receipt_path"),
            optional_path(value["operation_receipt_path"], "operation_receipt_path"),
            _path(
                value["action_ledger_path"], label=f"{label}.action_ledger_path"
            ),
            None if fifo is None else FifoIdentity.decode(fifo, label=f"{label}.control_fifo"),
        )


class CreationWatch:
    """One unbounded inotify rendezvous for a predeclared no-replace leaf."""

    _CREATE = 0x00000100
    _MOVED_TO = 0x00000080

    def __init__(self, path: Path) -> None:
        self.path = path
        libc = ctypes.CDLL(None, use_errno=True)
        descriptor = libc.inotify_init1(os.O_CLOEXEC | os.O_NONBLOCK)
        if descriptor < 0:
            error = ctypes.get_errno()
            raise HarnessError("cannot create formal action inotify authority") from OSError(
                error, os.strerror(error)
            )
        self._libc = libc
        self.fd = descriptor
        self._target_event_count = 0
        self._pre_start_boundary = False
        watch = libc.inotify_add_watch(
            descriptor,
            os.fsencode(path.parent),
            self._CREATE | self._MOVED_TO,
        )
        if watch < 0:
            error = ctypes.get_errno()
            os.close(descriptor)
            self.fd = -1
            raise HarnessError("cannot watch formal action receipt parent") from OSError(
                error, os.strerror(error)
            )
        self.watch = watch

    def _drain_target_events(self) -> int:
        observed = 0
        while True:
            try:
                raw = os.read(self.fd, 65536)
            except BlockingIOError:
                break
            if not raw:
                _fail("inotify authority returned an unexpected EOF")
            offset = 0
            while offset < len(raw):
                if len(raw) - offset < 16:
                    _fail("inotify event stream was truncated")
                watch, mask, _cookie, name_length = struct.unpack_from(
                    "iIII", raw, offset
                )
                offset += 16
                if name_length > len(raw) - offset:
                    _fail("inotify event name was truncated")
                name_raw = raw[offset : offset + name_length]
                offset += name_length
                name = os.fsdecode(name_raw.split(b"\0", 1)[0])
                if (
                    watch == self.watch
                    and mask & (self._CREATE | self._MOVED_TO)
                    and name == self.path.name
                ):
                    observed += 1
        self._target_event_count += observed
        return observed

    def close_pre_start_absence_boundary(self) -> None:
        if self._pre_start_boundary:
            _fail("ARMED creation watch pre-Start boundary was repeated")
        self._drain_target_events()
        if (
            self._target_event_count != 0
            or self.path.exists()
            or self.path.is_symlink()
        ):
            _fail("ARMED destination changed before the final StartUnit boundary")
        self._pre_start_boundary = True

    def wait_single_post_start_creation(self) -> None:
        if not self._pre_start_boundary:
            _fail("ARMED creation watch lacks its final pre-Start boundary")
        while self._target_event_count == 0:
            select.select([self.fd], [], [])
            self._drain_target_events()
        if self._target_event_count != 1:
            _fail("ARMED destination did not have exactly one post-Start creation event")
        if not self.path.exists() or self.path.is_symlink():
            _fail("ARMED creation event lacks its exact declared leaf")

    def prove_single_post_start_creation(self) -> None:
        self._drain_target_events()
        if self._target_event_count != 1:
            _fail("ARMED destination did not retain one post-Start creation event")

    def wait_created(self) -> None:
        if self.path.exists():
            return
        while True:
            select.select([self.fd], [], [])
            if self._drain_target_events() and self.path.exists():
                return

    def close(self) -> None:
        if self.fd >= 0:
            self._libc.inotify_rm_watch(self.fd, self.watch)
            os.close(self.fd)
            self.fd = -1

    def __del__(self) -> None:
        try:
            self.close()
        except OSError:
            pass


@dataclass
class PinnedFormalAction:
    action: FormalAction
    control_identity_fd: int | None

    @classmethod
    def open(cls, action: FormalAction) -> "PinnedFormalAction":
        if action.control_fifo is None:
            return cls(action, None)
        try:
            descriptor = os.open(
                action.control_fifo.path,
                os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC,
            )
            action.control_fifo.prove(descriptor, label="formal action control identity")
        except OSError as exc:
            raise HarnessError("cannot pin formal action control FIFO") from exc
        return cls(action, descriptor)

    def close(self) -> None:
        if self.control_identity_fd is not None:
            os.close(self.control_identity_fd)
            self.control_identity_fd = None

    def write_control(self, permit: bytes) -> None:
        descriptor = self.open_control_writer()
        try:
            view = memoryview(permit)
            while view:
                count = os.write(descriptor, view)
                if count <= 0:
                    _fail("formal action control write made no progress")
                view = view[count:]
        finally:
            os.close(descriptor)

    def open_control_writer(self) -> int:
        if self.control_identity_fd is None or self.action.control_fifo is None:
            _fail("formal action lacks its pinned control FIFO")
        try:
            descriptor = os.open(
                f"/proc/self/fd/{self.control_identity_fd}",
                os.O_WRONLY | os.O_CLOEXEC,
            )
            try:
                self.action.control_fifo.prove(
                    descriptor, label="formal action control writer"
                )
            except BaseException:
                os.close(descriptor)
                raise
            return descriptor
        except HarnessError:
            raise
        except OSError as exc:
            raise HarnessError("cannot write formal action control permit") from exc


def _freeze_b5_descendant_authority(
    formal_plan: dict[str, Any],
    *,
    action: FormalAction,
    run_unit: str,
    variant: str,
    assets: dict[str, dict[str, str]],
    retained_assets: dict[str, RetainedStaticAsset],
    require_root: bool,
) -> dict[str, Any]:
    reference = formal_plan.get("descendant_adversary_plan")
    if type(reference) is not dict:
        _fail("B5 formal plan lacks one sealed descendant plan reference")
    _exact(reference, {"path", "sha256"}, label="B5 descendant plan reference")
    plan_path = _path(reference["path"], label="B5 descendant plan path")
    plan_sha256 = _sha256(reference["sha256"], label="B5 descendant plan sha256")
    plan_asset = _inventory_asset(
        assets,
        retained_assets,
        expected_kind="json-plan",
        expected_path=plan_path,
        expected_sha256=plan_sha256,
        label="B5 descendant plan",
        require_root=require_root,
    )
    plan = _decode_canonical_raw(plan_asset.raw, label="B5 descendant plan")
    _exact(plan, _DESCENDANT_PLAN_KEYS, label="B5 descendant plan")
    expected_scenario = {
        "setsid-retain-stdio": "h6-setsid-descendant",
        "double-fork-close-stdio": "b7-double-fork-closed-stdio",
    }.get(variant)
    if expected_scenario is None:
        _fail("B5 descendant authority requested for a non-B5 variant")
    job_name = plan["expected_job_name"]
    if (
        plan["schema"] != "scion.generic_backend.systemd_adversary_plan.v1"
        or plan["scenario"] != expected_scenario
        or plan["unit"] != run_unit
        or type(job_name) is not str
        or _JOB_NAME_RE.fullmatch(job_name) is None
        or plan["acquisition"] is not None
    ):
        _fail("B5 descendant plan schema/scenario/unit/job/acquisition drifted")
    if action.control_fifo is None:
        _fail("B5 descendant action lacks its retained hold FIFO authority")
    expected_fifo = {
        "path": str(action.control_fifo.path),
        "device": str(action.control_fifo.device),
        "inode": str(action.control_fifo.inode),
    }
    if plan["hold_release_fifo"] != expected_fifo:
        _fail("B5 descendant plan hold FIFO differs from the manifest action pin")
    program_path = _path(plan["program_path"], label="B5 descendant program path")
    program_sha256 = _sha256(plan["program_sha256"], label="B5 descendant program sha256")
    program_asset = _inventory_asset(
        assets,
        retained_assets,
        expected_kind="python-program",
        expected_path=program_path,
        expected_sha256=program_sha256,
        label="B5 descendant program",
        require_root=require_root,
    )
    program = {
        "path": str(program_path),
        "sha256": program_sha256,
        "identity": {
            "device": program_asset.device,
            "inode": program_asset.inode,
            "mode": program_asset.mode,
        },
    }
    request_path = _path(plan["request_path"], label="B5 descendant request path")
    receipt_path = _path(plan["receipt_path"], label="B5 descendant receipt path")
    if len({plan_path, program_path, request_path, receipt_path, action.control_fifo.path}) != 5:
        _fail("B5 descendant plan/program/request/receipt/FIFO authorities overlap")
    for path, label in (
        (request_path, "B5 materialized descendant request"),
        (receipt_path, "B5 descendant receipt"),
    ):
        if path.exists() or path.is_symlink():
            _fail(f"{label} exists before StartUnit")
    return {
        "plan": plan,
        "plan_path": plan_path,
        "plan_sha256": plan_sha256,
        "plan_asset": plan_asset,
        "program_asset": program_asset,
        "program": program,
        "request_path": request_path,
        "receipt_path": receipt_path,
        "hold_release_fifo": expected_fifo,
    }


@dataclass
class PinnedAcquisition:
    acquisition: Acquisition
    ready_identity_fd: int
    release_identity_fd: int
    ready_reader_fd: int

    @classmethod
    def open(cls, acquisition: Acquisition) -> "PinnedAcquisition":
        identity_flags = os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC
        try:
            ready_identity = os.open(acquisition.ready_fifo.path, identity_flags)
            try:
                acquisition.ready_fifo.prove(ready_identity, label="ready identity")
                release_identity = os.open(acquisition.release_fifo.path, identity_flags)
                try:
                    acquisition.release_fifo.prove(release_identity, label="release identity")
                    ready_reader = os.open(
                        acquisition.ready_fifo.path,
                        os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC,
                    )
                    acquisition.ready_fifo.prove(ready_reader, label="ready reader")
                except BaseException:
                    os.close(release_identity)
                    raise
            except BaseException:
                os.close(ready_identity)
                raise
        except OSError as exc:
            raise HarnessError("cannot pin acquisition FIFO identities") from exc
        return cls(acquisition, ready_identity, release_identity, ready_reader)

    def close(self) -> None:
        for descriptor in (
            self.ready_reader_fd,
            self.release_identity_fd,
            self.ready_identity_fd,
        ):
            os.close(descriptor)

    def consume_ready(self) -> bytes:
        """Consume after event-loop readability; one writer/EOF transaction."""

        chunks: list[bytes] = []
        while True:
            try:
                chunk = os.read(self.ready_reader_fd, 4096)
            except BlockingIOError as exc:
                raise HarnessError("ready FIFO was consumed without readability") from exc
            if not chunk:
                break
            chunks.append(chunk)
        raw = b"".join(chunks)
        if raw != READY_BYTES:
            _fail("ready FIFO contained early EOF, extra bytes or wrong permit")
        return raw

    def release(self) -> None:
        try:
            descriptor = os.open(
                f"/proc/self/fd/{self.release_identity_fd}",
                os.O_WRONLY | os.O_CLOEXEC,
            )
            try:
                self.acquisition.release_fifo.prove(descriptor, label="release writer")
                count = os.write(descriptor, RELEASE_BYTES)
                if count != len(RELEASE_BYTES):
                    _fail("release FIFO write was not exact")
            finally:
                os.close(descriptor)
        except HarnessError:
            raise
        except OSError as exc:
            raise HarnessError("cannot complete release rendezvous") from exc


@dataclass(frozen=True)
class HashedFile:
    path: Path
    sha256: str

    @classmethod
    def decode_reference(cls, value: Any, *, label: str) -> "HashedFile":
        if type(value) is not dict:
            _fail(f"{label} must be one exact hashed-file identity")
        _exact(value, {"path", "sha256"}, label=label)
        path = _path(value["path"], label=f"{label}.path")
        expected = _text(value["sha256"], label=f"{label}.sha256")
        if re.fullmatch(r"[0-9a-f]{64}", expected) is None:
            _fail(f"{label}.sha256 is not canonical")
        return cls(path, expected)

    @classmethod
    def decode(cls, value: Any, *, label: str) -> "HashedFile":
        result = cls.decode_reference(value, label=label)
        path = result.path
        expected = result.sha256
        if hashlib.sha256(_read_regular(path, label=label)).hexdigest() != expected:
            _fail(f"{label} SHA-256 drifted")
        info = path.lstat()
        if info.st_uid != 0 or info.st_gid != 0 or stat.S_IMODE(info.st_mode) != 0o444:
            _fail(f"{label} must be root:root 0444")
        return result


@dataclass(frozen=True)
class StaticRoleBinding:
    role: str
    unit: str
    owner: str
    mode: str
    plan: HashedFile
    program: HashedFile

    @classmethod
    def decode(cls, value: Any, *, label: str) -> "StaticRoleBinding":
        if type(value) is not dict:
            _fail(f"{label} must be one exact static-role binding")
        _exact(value, _STATIC_ROLE_KEYS, label=label)
        role = _text(value["role"], label=f"{label}.role")
        unit = _text(value["unit"], label=f"{label}.unit")
        owner = _text(value["owner"], label=f"{label}.owner")
        mode = _text(value["mode"], label=f"{label}.mode")
        if _ROLE_RE.fullmatch(role) is None or _UNIT_RE.fullmatch(unit) is None:
            _fail(f"{label} role/unit is not canonical")
        if owner not in {"observer", "adversary", "formal"}:
            _fail(f"{label} owner is outside the closed program set")
        return cls(
            role,
            unit,
            owner,
            mode,
            HashedFile.decode_reference(value["plan"], label=f"{label}.plan"),
            HashedFile.decode_reference(value["program"], label=f"{label}.program"),
        )


@dataclass
class RetainedStaticAsset:
    role: str
    kind: str
    path: Path
    sha256: str
    device: int
    inode: int
    mode: int
    uid: int
    gid: int
    raw: bytes
    descriptor: int

    @property
    def reference(self) -> dict[str, str]:
        return {
            "role": self.role,
            "kind": self.kind,
            "path": str(self.path),
            "sha256": self.sha256,
            "device": str(self.device),
            "inode": str(self.inode),
            "mode": format(self.mode, "04o"),
            "uid": str(self.uid),
            "gid": str(self.gid),
        }

    def revalidate_path_identity(self, *, label: str, require_root: bool) -> None:
        if self.descriptor < 0:
            _fail(f"{label} retained descriptor was closed before last use")
        try:
            retained = os.fstat(self.descriptor)
            current = self.path.lstat()
        except OSError as exc:
            raise HarnessError(f"cannot revalidate retained {label}") from exc
        if (
            not stat.S_ISREG(retained.st_mode)
            or not stat.S_ISREG(current.st_mode)
            or (retained.st_dev, retained.st_ino) != (self.device, self.inode)
            or (current.st_dev, current.st_ino) != (self.device, self.inode)
            or stat.S_IMODE(retained.st_mode) != self.mode
            or stat.S_IMODE(current.st_mode) != self.mode
            or retained.st_uid != self.uid
            or retained.st_gid != self.gid
            or current.st_uid != self.uid
            or current.st_gid != self.gid
            or (require_root and (self.uid != 0 or self.gid != 0))
        ):
            _fail(f"{label} retained path identity/mode/owner drifted")

    def close(self) -> None:
        if self.descriptor >= 0:
            os.close(self.descriptor)
            self.descriptor = -1

    def __del__(self) -> None:
        if getattr(self, "descriptor", -1) >= 0:
            try:
                self.close()
            except OSError:
                pass


def _retain_static_asset(
    value: Any,
    *,
    role: str,
    kind: str,
    label: str,
    require_root: bool,
) -> RetainedStaticAsset:
    if type(value) is not dict:
        _fail(f"{label} must be one exact static file binding")
    _exact(value, {"path", "sha256", "device", "inode", "mode"}, label=label)
    path = _path(value["path"], label=f"{label}.path")
    sha256 = _sha256(value["sha256"], label=f"{label}.sha256")
    device = _decimal(value["device"], label=f"{label}.device")
    inode = _decimal(value["inode"], label=f"{label}.inode")
    mode_text = _text(value["mode"], label=f"{label}.mode")
    if re.fullmatch(r"0[0-7]{3}", mode_text) is None:
        _fail(f"{label}.mode is not canonical")
    mode = int(mode_text, 8)
    descriptor = -1
    try:
        before = path.lstat()
        descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        opened = os.fstat(descriptor)
        raw = _read_all(descriptor)
        after = os.fstat(descriptor)
        current = path.lstat()
        expected_identity = (device, inode)
        observations = (before, opened, after, current)
        if (
            any(not stat.S_ISREG(info.st_mode) for info in observations)
            or any(
                (info.st_dev, info.st_ino) != expected_identity
                for info in observations
            )
            or any(stat.S_IMODE(info.st_mode) != mode for info in observations)
            or any(
                (info.st_uid, info.st_gid) != (opened.st_uid, opened.st_gid)
                for info in observations
            )
            or (require_root and (opened.st_uid != 0 or opened.st_gid != 0))
            or after.st_size != len(raw)
            or after.st_mtime_ns != opened.st_mtime_ns
            or hashlib.sha256(raw).hexdigest() != sha256
        ):
            _fail(f"{label} retained bytes/identity/mode/owner drifted")
        return RetainedStaticAsset(
            role,
            kind,
            path,
            sha256,
            device,
            inode,
            mode,
            opened.st_uid,
            opened.st_gid,
            raw,
            descriptor,
        )
    except BaseException:
        if descriptor >= 0:
            os.close(descriptor)
        raise


def _bound_file_reference(
    value: Any,
    *,
    label: str,
    with_mode: bool = False,
    require_root: bool = False,
) -> tuple[Path, bytes]:
    if type(value) is not dict:
        _fail(f"{label} must be one exact bound-file object")
    keys = {"path", "sha256", "device", "inode"} | ({"mode"} if with_mode else set())
    _exact(value, keys, label=label)
    path = _path(value["path"], label=f"{label}.path")
    expected = _text(value["sha256"], label=f"{label}.sha256")
    if re.fullmatch(r"[0-9a-f]{64}", expected) is None:
        _fail(f"{label}.sha256 is not canonical")
    device = _decimal(value["device"], label=f"{label}.device")
    inode = _decimal(value["inode"], label=f"{label}.inode")
    expected_mode = value.get("mode") if with_mode else None
    if with_mode and (
        type(expected_mode) is not str
        or re.fullmatch(r"0[0-7]{3}", expected_mode) is None
    ):
        _fail(f"{label}.mode is not canonical")
    try:
        before = path.lstat()
        descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        try:
            opened = os.fstat(descriptor)
            raw = _read_all(descriptor)
            after = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        current = path.lstat()
    except OSError as exc:
        raise HarnessError(f"cannot pin and read {label}: {path}") from exc
    expected_identity = (device, inode)
    observations = (before, opened, after, current)
    if (
        any(not stat.S_ISREG(info.st_mode) for info in observations)
        or any((info.st_dev, info.st_ino) != expected_identity for info in observations)
        or after.st_size != len(raw)
        or after.st_mtime_ns != opened.st_mtime_ns
        or hashlib.sha256(raw).hexdigest() != expected
        or (
            expected_mode is not None
            and any(
                format(stat.S_IMODE(info.st_mode), "04o") != expected_mode
                for info in observations
            )
        )
        or (
            require_root
            and any(info.st_uid != 0 or info.st_gid != 0 for info in observations)
        )
    ):
        _fail(f"{label} bytes/identity/mode/owner drifted")
    return path, raw


def _bound_json_reference(
    value: Any,
    *,
    label: str,
    with_mode: bool = False,
    require_root: bool = False,
) -> tuple[Path, dict[str, Any], bytes]:
    path, raw = _bound_file_reference(
        value, label=label, with_mode=with_mode, require_root=require_root
    )
    try:
        decoded = json.loads(
            raw.decode("utf-8", "strict"),
            object_pairs_hook=_object_no_duplicates,
            parse_constant=_reject_constant,
        )
    except HarnessError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise HarnessError(f"{label} is not strict canonical JSON") from exc
    if type(decoded) is not dict or _canonical(decoded) != raw:
        _fail(f"{label} is not one exact canonical JSON object")
    return path, decoded, raw


def _static_inventory_assets(raw: bytes) -> dict[str, dict[str, str]]:
    try:
        text = raw.decode("ascii", "strict")
    except UnicodeError as exc:
        raise HarnessError("static inventory is not ASCII") from exc
    if not text.endswith("\n") or "\r" in text or "\0" in text:
        _fail("static inventory is not canonical line data")
    lines = text[:-1].split("\n")
    if len(lines) < 7:
        _fail("static inventory is incomplete")
    expected_headers = (
        ("schema", PREFLIGHT_MANIFEST_SCHEMA),
        ("formal_root", None),
        ("run_unit", None),
        ("close_unit", None),
        ("destination_path", None),
    )
    for index, (key, fixed) in enumerate(expected_headers):
        fields = lines[index].split("\t")
        if len(fields) != 2 or fields[0] != key or (fixed is not None and fields[1] != fixed):
            _fail(f"static inventory header {key!r} is missing or reordered")
    tree = lines[5].split("\t")
    if len(tree) != 6 or tree[0] != "tree_receipt":
        _fail("static inventory tree receipt is missing or reordered")
    assets: dict[str, dict[str, str]] = {}
    paths: set[str] = set()
    identities: set[tuple[str, str]] = set()
    for index, line in enumerate(lines[6:]):
        fields = line.split("\t")
        if len(fields) != 8 or fields[0] != "asset":
            _fail(f"static inventory asset[{index}] is malformed")
        role, kind, raw_path, sha256, device, inode, mode = fields[1:]
        path = _path(raw_path, label=f"static inventory asset[{index}].path")
        digest = _sha256(
            sha256, label=f"static inventory asset[{index}].sha256"
        )
        asset_device = _decimal(
            device, label=f"static inventory asset[{index}].device"
        )
        asset_inode = _decimal(
            inode, label=f"static inventory asset[{index}].inode"
        )
        if (
            _ROLE_RE.fullmatch(role) is None
            or role in assets
            or kind not in {
                "unit-fragment", "python-program", "json-plan", "start-descriptor",
                "installer-program", "harness-program", "static-input",
            }
            or str(path) in paths
            or (str(asset_device), str(asset_inode)) in identities
            or mode != "0444"
        ):
            _fail("static inventory contains an invalid or aliased asset")
        binding = {
            "role": role,
            "kind": kind,
            "path": str(path),
            "sha256": digest,
            "device": str(asset_device),
            "inode": str(asset_inode),
            "mode": mode,
        }
        assets[role] = binding
        paths.add(str(path))
        identities.add((str(asset_device), str(asset_inode)))
    return assets


def _inventory_asset(
    assets: dict[str, dict[str, str]],
    retained_assets: dict[str, RetainedStaticAsset],
    *,
    expected_kind: str,
    expected_path: Path,
    expected_sha256: str,
    label: str,
    expected_role: str | None = None,
    expected_binding: dict[str, Any] | None = None,
    require_root: bool = False,
) -> RetainedStaticAsset:
    matches = [
        item
        for item in assets.values()
        if item["kind"] == expected_kind
        and item["path"] == str(expected_path)
        and item["sha256"] == expected_sha256
        and (expected_role is None or item["role"] == expected_role)
    ]
    if len(matches) != 1:
        _fail(f"{label} is not one unique exact static inventory asset")
    binding = matches[0]
    full_binding = {
        key: binding[key] for key in ("path", "sha256", "device", "inode", "mode")
    }
    if expected_binding is not None:
        if type(expected_binding) is not dict:
            _fail(f"{label} expected binding is not an object")
        _exact(
            expected_binding,
            {"path", "sha256", "device", "inode", "mode"},
            label=f"{label} expected binding",
        )
        if expected_binding != full_binding:
            _fail(f"{label} differs from its exact static inventory binding")
    retained = retained_assets.get(binding["role"])
    if retained is not None:
        if retained.reference != {
            **binding,
            "uid": str(retained.uid),
            "gid": str(retained.gid),
        }:
            _fail(f"{label} retained asset cache binding drifted")
        retained.revalidate_path_identity(label=label, require_root=require_root)
        return retained
    retained = _retain_static_asset(
        full_binding,
        role=binding["role"],
        kind=binding["kind"],
        label=label,
        require_root=require_root,
    )
    retained_assets[binding["role"]] = retained
    return retained


def _validate_installer_authority(
    receipt_path: Path,
    *,
    preflight_reference: HashedFile,
    inventory_reference: HashedFile,
    descriptor_reference: HashedFile,
    harness_reference: HashedFile,
    run_unit: str,
    require_root: bool,
) -> dict[str, Any]:
    receipt = _decode_canonical(receipt_path, label="root installer receipt")
    _exact(
        receipt,
        {
            "schema", "formal_root", "installer", "install_manifest", "tree_receipt",
            "seal_receipt", "preflight_receipt", "manager_owner", "manager_ledger",
            "fixture_user", "fixture_group", "fixture_uid", "fixture_gid",
            "reload_call_count", "load_call_count", "units", "phase",
        },
        label="root installer receipt",
    )
    if (
        receipt["schema"] != INSTALL_RECEIPT_SCHEMA
        or receipt["phase"] != "installed-before-observation"
        or receipt["reload_call_count"] != "1"
    ):
        _fail("root installer receipt schema/phase/reload count drifted")
    root_identity = receipt["formal_root"]
    if type(root_identity) is not dict:
        _fail("root installer formal_root is not an identity")
    _exact(root_identity, {"path", "device", "inode"}, label="installer formal_root")
    root = _path(root_identity["path"], label="installer formal_root.path")
    root_info = root.lstat()
    if (
        not stat.S_ISDIR(root_info.st_mode)
        or (str(root_info.st_dev), str(root_info.st_ino))
        != (root_identity["device"], root_identity["inode"])
        or stat.S_IMODE(root_info.st_mode) != 0o711
    ):
        _fail("root installer formal_root identity/mode drifted")

    _bound_file_reference(
        receipt["install_manifest"],
        label="installer install_manifest",
        with_mode=True,
        require_root=require_root,
    )
    install_binding = {
        key: receipt["install_manifest"][key]
        for key in ("path", "sha256", "device", "inode")
    }
    _install_path, install_manifest, _ = _bound_json_reference(
        install_binding,
        label="installer install manifest",
        require_root=require_root,
    )
    _exact(
        install_manifest,
        {"schema", "formal_root", "tree_receipt", "seal_receipt", "preflight_receipt", "units", "receipt_path"},
        label="installer install manifest",
    )
    if (
        install_manifest["schema"] != INSTALL_MANIFEST_SCHEMA
        or install_manifest["formal_root"] != str(root)
        or install_manifest["receipt_path"] != str(receipt_path)
        or any(install_manifest[name] != receipt[name] for name in ("tree_receipt", "seal_receipt", "preflight_receipt"))
    ):
        _fail("installer receipt differs from its exact install manifest")

    input_schemas = {
        "tree_receipt": TREE_RECEIPT_SCHEMA,
        "seal_receipt": SEAL_RECEIPT_SCHEMA,
        "preflight_receipt": PREFLIGHT_RECEIPT_SCHEMA,
    }
    inputs: dict[str, dict[str, Any]] = {}
    for name, schema in input_schemas.items():
        _path_value, decoded, _ = _bound_json_reference(
            receipt[name], label=f"installer {name}", require_root=require_root
        )
        if decoded.get("schema") != schema:
            _fail(f"installer {name} schema drifted")
        inputs[name] = decoded
    tree, seal, preflight = (
        inputs["tree_receipt"], inputs["seal_receipt"], inputs["preflight_receipt"]
    )
    if (
        tree.get("formal_root", {}).get("path") != str(root)
        or seal.get("formal_root", {}).get("path") != str(root)
        or seal.get("tree_receipt") != receipt["tree_receipt"]
        or preflight.get("formal_root") != str(root)
        or preflight.get("tree_receipt") != {**receipt["tree_receipt"], "mode": "0444"}
        or preflight.get("seal_receipt") != {**receipt["seal_receipt"], "mode": "0444"}
    ):
        _fail("TREE/SEAL/PREFLIGHT receipt chain is not exact")
    preflight_binding = receipt["preflight_receipt"]
    if (
        str(preflight_reference.path) != preflight_binding["path"]
        or preflight_reference.sha256 != preflight_binding["sha256"]
    ):
        _fail("manifest preflight binding differs from installer authority")
    inventory_binding = preflight.get("inventory_manifest")
    if type(inventory_binding) is not dict:
        _fail("preflight receipt lacks its static inventory binding")
    _exact(
        inventory_binding,
        {"path", "sha256", "device", "inode", "mode"},
        label="preflight inventory binding",
    )
    if (
        str(inventory_reference.path) != inventory_binding["path"]
        or inventory_reference.sha256 != inventory_binding["sha256"]
    ):
        _fail("manifest static inventory differs from preflight authority")
    inventory_asset = _retain_static_asset(
        inventory_binding,
        role="preflight-manifest",
        kind="static-inventory",
        label="preflight-bound static inventory",
        require_root=require_root,
    )
    retained_assets: dict[str, RetainedStaticAsset] = {}
    assets = _static_inventory_assets(inventory_asset.raw)
    sealed_root = root / "sealed"
    sealed_info = sealed_root.lstat()
    if (
        not stat.S_ISDIR(sealed_info.st_mode)
        or stat.S_IMODE(sealed_info.st_mode) != 0o555
        or not inventory_reference.path.is_relative_to(sealed_root)
        or any(
            Path(item["path"]).parent not in {sealed_root, root / "input"}
            for item in assets.values()
        )
    ):
        _fail("static inventory/assets are outside the sealed static authority")
    if preflight.get("asset_count") != str(len(assets)):
        _fail("preflight asset count differs from static inventory")
    seal_files = seal.get("files")
    if type(seal_files) is not list:
        _fail("seal receipt lacks its exact file inventory")
    sealed = {
        item.get("path"): item
        for item in seal_files
        if type(item) is dict and type(item.get("path")) is str
    }
    expected_sealed = {inventory_binding["path"], *(item["path"] for item in assets.values())}
    if set(sealed) != expected_sealed:
        _fail("seal receipt and static inventory file sets differ")
    for binding in (inventory_binding, *assets.values()):
        item = sealed.get(binding["path"])
        if item is None or any(item.get(name) != binding[name] for name in ("path", "sha256", "device", "inode", "mode")):
            _fail("seal receipt file binding differs from static inventory")

    _installer_asset = _inventory_asset(
        assets,
        retained_assets,
        expected_role="installer-program",
        expected_kind="installer-program",
        expected_path=_path(receipt["installer"]["path"], label="installer.path"),
        expected_sha256=_text(
            receipt["installer"]["sha256"], label="installer.sha256"
        ),
        expected_binding=receipt["installer"],
        label="root installer program",
        require_root=require_root,
    )
    descriptor_asset = _inventory_asset(
        assets,
        retained_assets,
        expected_role="start-descriptor",
        expected_kind="start-descriptor",
        expected_path=descriptor_reference.path,
        expected_sha256=descriptor_reference.sha256,
        label="StartUnit descriptor",
        require_root=require_root,
    )
    start_descriptor = _decode_start_descriptor_raw(descriptor_asset.raw, run_unit)
    if harness_reference.path != Path(__file__):
        _fail("manifest harness program is not the current exact program path")
    _harness_asset = _inventory_asset(
        assets,
        retained_assets,
        expected_role="harness-program",
        expected_kind="harness-program",
        expected_path=harness_reference.path,
        expected_sha256=harness_reference.sha256,
        label="current harness program",
        require_root=require_root,
    )

    units = receipt["units"]
    ledger = receipt["manager_ledger"]
    manifest_units = install_manifest["units"]
    if type(units) is not list or not units or type(ledger) is not list or type(manifest_units) is not list:
        _fail("installer units/manager ledger is malformed")
    if (
        len(manifest_units) != len(units)
        or receipt["load_call_count"] != str(len(units))
        or len(ledger) != 1 + 3 * len(units)
    ):
        _fail("installer unit/manager call counts drifted")
    expected_members = ["Reload"] + ["LoadUnit"] * len(units) + [
        member for _ in units for member in ("Get", "Get")
    ]
    for ordinal, (entry, member) in enumerate(zip(ledger, expected_members), start=1):
        if type(entry) is not dict:
            _fail("installer manager ledger entry is not an object")
        _exact(
            entry,
            {"begin_ordinal", "reply_ordinal", "interface", "member", "object_path", "signature", "arguments", "reply"},
            label=f"installer manager ledger[{ordinal - 1}]",
        )
        if (
            entry["begin_ordinal"] != str(2 * ordinal - 1)
            or entry["reply_ordinal"] != str(2 * ordinal)
            or entry["member"] != member
        ):
            _fail("installer manager ledger ordinal/member drifted")
    if ledger[0] != {
        "begin_ordinal": "1", "reply_ordinal": "2",
        "interface": MANAGER_INTERFACE, "member": "Reload",
        "object_path": MANAGER_PATH, "signature": "", "arguments": [], "reply": None,
    }:
        _fail("installer Reload ledger entry is not exact")
    objects: dict[str, str] = {}
    loads = ledger[1 : 1 + len(units)]
    properties = ledger[1 + len(units) :]
    for index, (record, declared, load) in enumerate(zip(units, manifest_units, loads)):
        if type(record) is not dict or type(declared) is not dict:
            _fail("installer unit binding is not an object")
        _exact(
            record,
            {"role", "unit", "source", "target", "object_path", "fragment_path", "need_daemon_reload"},
            label=f"installer units[{index}]",
        )
        unit = _text(record["unit"], label=f"installer units[{index}].unit")
        object_path = _text(record["object_path"], label=f"installer units[{index}].object_path")
        if unit in objects or not object_path.startswith("/org/freedesktop/systemd1/unit/"):
            _fail("installer unit/object mapping is duplicated or invalid")
        source = record["source"]
        target = record["target"]
        _inventory_asset(
            assets,
            retained_assets,
            expected_role=record["role"],
            expected_kind="unit-fragment",
            expected_path=_path(source["path"], label=f"installer source {unit}.path"),
            expected_sha256=_text(
                source["sha256"], label=f"installer source {unit}.sha256"
            ),
            expected_binding=source,
            label=f"installer source {unit}",
            require_root=require_root,
        )
        target_path, target_raw = _bound_file_reference(
            {name: target[name] for name in ("path", "sha256", "device", "inode", "mode")},
            label=f"installer target {unit}", with_mode=True, require_root=require_root,
        )
        target_info = target_path.lstat()
        source_assets = [
            item
            for item in assets.values()
            if item["role"] == record["role"]
            and item["kind"] == "unit-fragment"
            and all(
                item[name] == source[name]
                for name in ("path", "sha256", "device", "inode", "mode")
            )
        ]
        if (
            len(source_assets) != 1
            or declared != {"role": record["role"], "unit": unit, "source": source["path"], "sha256": source["sha256"]}
            or record["fragment_path"] != target["path"]
            or record["need_daemon_reload"] is not False
            or target["mode"] != "0644"
            or str(target_info.st_uid) != target["uid"]
            or str(target_info.st_gid) != target["gid"]
            or hashlib.sha256(target_raw).hexdigest() != source["sha256"]
            or load["arguments"] != [unit]
            or load["reply"] != object_path
            or load["interface"] != MANAGER_INTERFACE
            or load["object_path"] != MANAGER_PATH
            or load["signature"] != "s"
        ):
            _fail("installer unit/source/target/LoadUnit binding drifted")
        fragment_entry, reload_entry = properties[2 * index : 2 * index + 2]
        if (
            fragment_entry["object_path"] != object_path
            or fragment_entry["interface"] != PROPERTIES_INTERFACE
            or fragment_entry["signature"] != "ss"
            or fragment_entry["arguments"] != [UNIT_INTERFACE, "FragmentPath"]
            or fragment_entry["reply"] != target["path"]
            or reload_entry["object_path"] != object_path
            or reload_entry["interface"] != PROPERTIES_INTERFACE
            or reload_entry["signature"] != "ss"
            or reload_entry["arguments"] != [UNIT_INTERFACE, "NeedDaemonReload"]
            or reload_entry["reply"] is not False
        ):
            _fail("installer FragmentPath/NeedDaemonReload ledger drifted")
        objects[unit] = object_path
    return {
        "receipt": receipt,
        "root": root,
        "assets": assets,
        "inventory_asset": inventory_asset,
        "retained_assets": retained_assets,
        "objects": objects,
        "start_descriptor": start_descriptor,
        "fixture_user": _text(receipt["fixture_user"], label="installer fixture_user"),
        "fixture_group": _text(receipt["fixture_group"], label="installer fixture_group"),
        "fixture_uid": _decimal(receipt["fixture_uid"], label="installer fixture_uid"),
        "fixture_gid": _decimal(receipt["fixture_gid"], label="installer fixture_gid"),
    }


@dataclass(frozen=True)
class PinnedFile:
    path: Path
    device: int
    inode: int

    @classmethod
    def decode(cls, value: Any, *, label: str) -> "PinnedFile":
        if type(value) is not dict:
            _fail(f"{label} must be one exact pinned-file identity")
        _exact(value, {"path", "device", "inode"}, label=label)
        result = cls(
            _path(value["path"], label=f"{label}.path"),
            _decimal(value["device"], label=f"{label}.device"),
            _decimal(value["inode"], label=f"{label}.inode"),
        )
        info = result.path.lstat()
        if not stat.S_ISREG(info.st_mode) or (info.st_dev, info.st_ino) != (
            result.device,
            result.inode,
        ):
            _fail(f"{label} identity drifted")
        if info.st_uid != 0 or info.st_gid != 0 or stat.S_IMODE(info.st_mode) != 0o444:
            _fail(f"{label} must be root:root 0444")
        return result


@dataclass(frozen=True)
class OutputPath:
    role: str
    path: Path


@dataclass(frozen=True)
class StaticRoleAuthority:
    role: str
    owner: str
    mode: str
    unit: str
    acquisition: Acquisition
    plan_asset: RetainedStaticAsset
    program_asset: RetainedStaticAsset
    private_paths: tuple[Path, ...]

    @property
    def plan(self) -> dict[str, Any]:
        return _decode_canonical_raw(
            self.plan_asset.raw, label=f"{self.role} retained static plan"
        )

    def revalidate(
        self, *, require_root: bool, require_armed_absent: bool = True
    ) -> None:
        self.plan_asset.revalidate_path_identity(
            label=f"{self.role} static plan", require_root=require_root
        )
        self.program_asset.revalidate_path_identity(
            label=f"{self.role} static program", require_root=require_root
        )
        if require_armed_absent and (
            self.acquisition.armed_receipt_path.exists()
            or self.acquisition.armed_receipt_path.is_symlink()
        ):
            _fail(f"{self.role} ARMED destination exists before StartUnit")
        for name, fifo in (
            ("ready", self.acquisition.ready_fifo),
            ("release", self.acquisition.release_fifo),
        ):
            try:
                info = fifo.path.lstat()
            except OSError as exc:
                raise HarnessError(
                    f"cannot revalidate {self.role} {name} FIFO"
                ) from exc
            if (
                not stat.S_ISFIFO(info.st_mode)
                or (info.st_dev, info.st_ino) != (fifo.device, fifo.inode)
            ):
                _fail(f"{self.role} {name} FIFO identity drifted")


@dataclass
class RetainedManifestDirectory:
    path: Path
    device: int
    inode: int
    mode: int
    uid: int
    gid: int
    descriptor: int

    def close(self) -> None:
        if self.descriptor >= 0:
            os.close(self.descriptor)
            self.descriptor = -1


@dataclass
class ExecutionManifestSource:
    path: Path
    sha256: str
    device: int
    inode: int
    mode: int
    uid: int
    gid: int
    raw: bytes
    descriptor: int
    directories: tuple[RetainedManifestDirectory, ...]

    @property
    def reference(self) -> dict[str, str]:
        return {
            "path": str(self.path),
            "sha256": self.sha256,
            "device": str(self.device),
            "inode": str(self.inode),
            "mode": format(self.mode, "04o"),
            "uid": str(self.uid),
            "gid": str(self.gid),
        }

    @classmethod
    def open_once(
        cls, path: Path, *, require_root: bool
    ) -> tuple["ExecutionManifestSource", bytes]:
        if (
            path.name != "MANIFEST.json"
            or path.parent.parent.name != "harness"
            or path.parent.parent.parent.name != "authority"
        ):
            _fail("execution manifest source is outside its exact parent-chain layout")
        root = path.parents[3]
        scenario_name = path.parent.name
        if (
            not scenario_name
            or path
            != root
            / "authority"
            / "harness"
            / scenario_name
            / "MANIFEST.json"
        ):
            _fail("execution manifest source is outside its exact parent-chain layout")
        opened_directories: list[RetainedManifestDirectory] = []
        descriptor = -1

        def retain_directory(
            directory: Path,
            *,
            expected_mode: int,
            parent_descriptor: int | None = None,
            name: str | None = None,
        ) -> RetainedManifestDirectory:
            current_descriptor = -1
            try:
                before = (
                    directory.lstat()
                    if parent_descriptor is None
                    else os.stat(
                        name,
                        dir_fd=parent_descriptor,
                        follow_symlinks=False,
                    )
                )
                flags = (
                    os.O_RDONLY
                    | os.O_DIRECTORY
                    | os.O_CLOEXEC
                    | os.O_NOFOLLOW
                )
                current_descriptor = (
                    os.open(directory, flags)
                    if parent_descriptor is None
                    else os.open(name, flags, dir_fd=parent_descriptor)
                )
                opened = os.fstat(current_descriptor)
                current = (
                    directory.lstat()
                    if parent_descriptor is None
                    else os.stat(
                        name,
                        dir_fd=parent_descriptor,
                        follow_symlinks=False,
                    )
                )
            except OSError as exc:
                if current_descriptor >= 0:
                    os.close(current_descriptor)
                raise HarnessError(
                    f"cannot retain execution manifest directory: {directory}"
                ) from exc
            observations = (before, opened, current)
            if (
                any(not stat.S_ISDIR(info.st_mode) for info in observations)
                or any(
                    (info.st_dev, info.st_ino)
                    != (opened.st_dev, opened.st_ino)
                    for info in observations
                )
                or any(
                    stat.S_IMODE(info.st_mode) != expected_mode
                    for info in observations
                )
                or any(
                    (info.st_uid, info.st_gid) != (opened.st_uid, opened.st_gid)
                    for info in observations
                )
                or (require_root and (opened.st_uid != 0 or opened.st_gid != 0))
            ):
                os.close(current_descriptor)
                _fail("execution manifest parent-chain identity/mode/owner drifted")
            return RetainedManifestDirectory(
                directory,
                opened.st_dev,
                opened.st_ino,
                stat.S_IMODE(opened.st_mode),
                opened.st_uid,
                opened.st_gid,
                current_descriptor,
            )

        try:
            root_authority = retain_directory(root, expected_mode=0o711)
            opened_directories.append(root_authority)
            authority = retain_directory(
                root / "authority",
                expected_mode=0o700,
                parent_descriptor=root_authority.descriptor,
                name="authority",
            )
            opened_directories.append(authority)
            harness_directory = retain_directory(
                root / "authority" / "harness",
                expected_mode=0o700,
                parent_descriptor=authority.descriptor,
                name="harness",
            )
            opened_directories.append(harness_directory)
            scenario_directory = retain_directory(
                path.parent,
                expected_mode=0o700,
                parent_descriptor=harness_directory.descriptor,
                name=scenario_name,
            )
            opened_directories.append(scenario_directory)
            before = os.stat(
                "MANIFEST.json",
                dir_fd=scenario_directory.descriptor,
                follow_symlinks=False,
            )
            descriptor = os.open(
                "MANIFEST.json",
                os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=scenario_directory.descriptor,
            )
            opened = os.fstat(descriptor)
            raw = _read_all(descriptor)
            after = os.fstat(descriptor)
            current = os.stat(
                "MANIFEST.json",
                dir_fd=scenario_directory.descriptor,
                follow_symlinks=False,
            )
        except OSError as exc:
            raise HarnessError("cannot open execution manifest source") from exc
        except BaseException:
            if descriptor >= 0:
                os.close(descriptor)
            for directory in reversed(opened_directories):
                directory.close()
            raise
        observations = (before, opened, after, current)
        if (
            any(not stat.S_ISREG(info.st_mode) for info in observations)
            or any(
                (info.st_dev, info.st_ino) != (opened.st_dev, opened.st_ino)
                for info in observations
            )
            or any(
                stat.S_IMODE(info.st_mode) != 0o444 for info in observations
            )
            or any(
                (info.st_uid, info.st_gid) != (opened.st_uid, opened.st_gid)
                for info in observations
            )
            or (require_root and (opened.st_uid != 0 or opened.st_gid != 0))
            or after.st_size != len(raw)
            or after.st_mtime_ns != opened.st_mtime_ns
        ):
            os.close(descriptor)
            for directory in reversed(opened_directories):
                directory.close()
            _fail("execution manifest source identity/mode/owner drifted while read")
        source = cls(
            path,
            hashlib.sha256(raw).hexdigest(),
            opened.st_dev,
            opened.st_ino,
            stat.S_IMODE(opened.st_mode),
            opened.st_uid,
            opened.st_gid,
            raw,
            descriptor,
            tuple(opened_directories),
        )
        return source, raw

    def revalidate(self, *, require_root: bool) -> None:
        try:
            if self.descriptor < 0 or len(self.directories) != 4:
                _fail("execution manifest retained authority closed before last use")
            for index, directory in enumerate(self.directories):
                retained = os.fstat(directory.descriptor)
                if index == 0:
                    current = directory.path.lstat()
                else:
                    parent = self.directories[index - 1]
                    current = os.stat(
                        directory.path.name,
                        dir_fd=parent.descriptor,
                        follow_symlinks=False,
                    )
                if (
                    not stat.S_ISDIR(retained.st_mode)
                    or not stat.S_ISDIR(current.st_mode)
                    or (retained.st_dev, retained.st_ino)
                    != (directory.device, directory.inode)
                    or (current.st_dev, current.st_ino)
                    != (directory.device, directory.inode)
                    or stat.S_IMODE(retained.st_mode) != directory.mode
                    or stat.S_IMODE(current.st_mode) != directory.mode
                    or (retained.st_uid, retained.st_gid)
                    != (directory.uid, directory.gid)
                    or (current.st_uid, current.st_gid)
                    != (directory.uid, directory.gid)
                    or (require_root and (directory.uid != 0 or directory.gid != 0))
                ):
                    _fail("execution manifest retained parent-chain directory drifted")
            retained_leaf = os.fstat(self.descriptor)
            current = os.stat(
                "MANIFEST.json",
                dir_fd=self.directories[-1].descriptor,
                follow_symlinks=False,
            )
            os.lseek(self.descriptor, 0, os.SEEK_SET)
            raw = _read_all(self.descriptor)
            os.lseek(self.descriptor, 0, os.SEEK_SET)
        except OSError as exc:
            raise HarnessError("cannot revalidate execution manifest source") from exc
        if (
            raw != self.raw
            or hashlib.sha256(raw).hexdigest() != self.sha256
            or not stat.S_ISREG(retained_leaf.st_mode)
            or not stat.S_ISREG(current.st_mode)
            or (retained_leaf.st_dev, retained_leaf.st_ino)
            != (self.device, self.inode)
            or (current.st_dev, current.st_ino) != (self.device, self.inode)
            or stat.S_IMODE(retained_leaf.st_mode) != self.mode
            or stat.S_IMODE(current.st_mode) != self.mode
            or retained_leaf.st_uid != self.uid
            or retained_leaf.st_gid != self.gid
            or current.st_uid != self.uid
            or current.st_gid != self.gid
            or (require_root and (self.uid != 0 or self.gid != 0))
        ):
            _fail("execution manifest source path identity/mode/owner drifted")

    def close(self) -> None:
        if self.descriptor >= 0:
            os.close(self.descriptor)
            self.descriptor = -1
        for directory in reversed(self.directories):
            directory.close()

    def __del__(self) -> None:
        try:
            self.close()
        except OSError:
            pass


@dataclass(frozen=True)
class HarnessManifest:
    scenario: str
    descriptor: HashedFile
    installer_receipt: HashedFile
    harness_program: HashedFile
    run_unit: str
    closer_unit: str | None
    boot_id_file: PinnedFile
    input_root: Path
    receipt_root: Path
    acquisitions: tuple[Acquisition, ...]
    formal_actions: tuple[FormalAction, ...]
    outputs: tuple[OutputPath, ...]
    scenario_input: dict[str, Any] | None
    preflight_receipt: HashedFile | None = None
    static_inventory: HashedFile | None = None
    static_roles: tuple[StaticRoleBinding, ...] = ()
    source: ExecutionManifestSource | None = None

    def output(self, role: str) -> Path:
        matches = [item.path for item in self.outputs if item.role == role]
        if len(matches) != 1:
            _fail(f"manifest requires exactly one output role {role!r}")
        return matches[0]

    @property
    def policy(self) -> ScenarioPolicy:
        try:
            return _SCENARIO_POLICIES[self.scenario]
        except KeyError as exc:
            raise HarnessError("manifest scenario is outside the closed policy table") from exc

    def _role_owner(self, role: str) -> RoleOwner:
        policy = self.policy
        if role == "run-main":
            return policy.run_owner
        if role in {"exec-stop-post", "h4-stop-post"} and policy.stop_owner is not None:
            return policy.stop_owner
        if role in {"closer", "failed-closer"} and policy.closer_owner is not None:
            return policy.closer_owner
        _fail(f"static role {role!r} has no ScenarioPolicy owner")

    def _validate_static_role(
        self,
        binding: StaticRoleBinding,
        acquisition: Acquisition,
        assets: dict[str, dict[str, str]],
        retained_assets: dict[str, RetainedStaticAsset],
        *,
        require_root: bool,
    ) -> StaticRoleAuthority:
        owner = self._role_owner(binding.role)
        if (
            binding.role != acquisition.role
            or binding.owner != owner.schema
            or binding.mode != owner.mode
            or binding.unit
            != (self.manifest_unit_for_role(binding.role))
        ):
            _fail("static role binding differs from its closed ScenarioPolicy owner")
        plan_asset = _inventory_asset(
            assets,
            retained_assets,
            expected_kind="json-plan",
            expected_path=binding.plan.path,
            expected_sha256=binding.plan.sha256,
            label=f"{binding.role} static plan",
            require_root=require_root,
        )
        program_asset = _inventory_asset(
            assets,
            retained_assets,
            expected_kind="python-program",
            expected_path=binding.program.path,
            expected_sha256=binding.program.sha256,
            label=f"{binding.role} static program",
            require_root=require_root,
        )
        plan = _decode_canonical_raw(
            plan_asset.raw, label=f"{binding.role} static plan"
        )
        expected_acquisition = {
            "armed_receipt_path": str(acquisition.armed_receipt_path),
            "ready_fifo": {
                "path": str(acquisition.ready_fifo.path),
                "device": str(acquisition.ready_fifo.device),
                "inode": str(acquisition.ready_fifo.inode),
            },
            "release_fifo": {
                "path": str(acquisition.release_fifo.path),
                "device": str(acquisition.release_fifo.device),
                "inode": str(acquisition.release_fifo.inode),
            },
        }
        private_paths: list[Path] = [binding.plan.path]
        if binding.owner == "observer":
            if (
                plan.get("schema") != "scion.generic_backend.systemd_observer_plan.v1"
                or plan.get("mode") != binding.mode
                or plan.get("unit") != binding.unit
                or plan.get("program_path") != str(binding.program.path)
                or plan.get("program_sha256") != binding.program.sha256
                or plan.get("acquisition") != expected_acquisition
            ):
                _fail("observer static plan differs from its exact role binding")
            properties = plan.get("property_inputs")
            if type(properties) is not list:
                _fail("observer static plan property_inputs is not an array")
            raw_paths = [
                item.get("raw_authority_path") if type(item) is dict else None
                for item in properties
            ]
            if raw_paths != [str(self.output(f"{binding.role}-properties"))]:
                _fail("observer plan raw authority differs from the manifest output")
            selector = plan.get("source_selector_path")
            if binding.mode == "closer":
                if selector != str(self.output("source-selector")):
                    _fail("closer plan source selector differs from manifest output")
            elif selector is not None:
                _fail("non-closer observer plan unexpectedly binds a source selector")
            for name in ("request_path", "output_path"):
                private_paths.append(_path(plan.get(name), label=f"observer {name}"))
        elif binding.owner == "adversary":
            if (
                plan.get("schema") != "scion.generic_backend.systemd_adversary_plan.v1"
                or plan.get("scenario") != binding.mode
                or plan.get("unit") != binding.unit
                or plan.get("program_path") != str(binding.program.path)
                or plan.get("program_sha256") != binding.program.sha256
                or plan.get("acquisition") != expected_acquisition
            ):
                _fail("adversary static plan differs from its exact role binding")
            for name in ("request_path", "receipt_path"):
                private_paths.append(_path(plan.get(name), label=f"adversary {name}"))
        else:
            formal_program = plan.get("formal_program")
            if (
                plan.get("schema") != "scion.generic-backend.formal-plan.v1"
                or plan.get("run_unit") != binding.unit
                or plan.get("systemd_acquisition") != expected_acquisition
                or type(formal_program) is not dict
                or formal_program.get("path") != str(binding.program.path)
                or formal_program.get("sha256") != binding.program.sha256
                or self.policy.formal_case
                != (plan.get("case_id"), plan.get("variant"))
            ):
                _fail("formal static plan differs from its exact role binding")
            formal_static_kinds = {
                "case_script": "python-program",
                "adversary_script": "python-program",
                "accepted_probe": "static-input",
                "accepted_extension": "static-input",
                "accepted_spawn_backend": "static-input",
            }
            for name, kind in formal_static_kinds.items():
                reference = plan.get(name)
                if type(reference) is not dict:
                    _fail(f"formal static plan lacks one exact {name} reference")
                _exact(reference, {"path", "sha256"}, label=f"formal {name}")
                asset = _inventory_asset(
                    assets,
                    retained_assets,
                    expected_kind=kind,
                    expected_path=_path(
                        reference["path"], label=f"formal {name}.path"
                    ),
                    expected_sha256=_sha256(
                        reference["sha256"], label=f"formal {name}.sha256"
                    ),
                    label=f"formal {name}",
                    require_root=require_root,
                )
                if name == "case_script" and asset is not program_asset:
                    _fail("formal case_script differs from its executing program asset")
            for name in ("final_config_path",):
                private_paths.append(_path(plan.get(name), label=f"formal {name}"))
            receipt_directory = _path(
                plan.get("receipt_directory"), label="formal receipt_directory"
            )
            receipt_name = _text(plan.get("receipt_name"), label="formal receipt_name")
            formal_final = receipt_directory / receipt_name
            if self.policy.formal_completion == "failstop":
                if formal_final in {item.path for item in self.outputs}:
                    _fail("fail-stop formal final path aliases a manifest output")
                private_paths.append(formal_final)
            elif formal_final != self.output("formal-final"):
                _fail("formal plan final receipt differs from manifest formal-final")
        authority = StaticRoleAuthority(
            binding.role,
            binding.owner,
            binding.mode,
            binding.unit,
            acquisition,
            plan_asset,
            program_asset,
            tuple(private_paths),
        )
        authority.revalidate(require_root=require_root)
        return authority

    def manifest_unit_for_role(self, role: str) -> str:
        if role in {"run-main", "exec-stop-post", "h4-stop-post"}:
            return self.run_unit
        if role in {"closer", "failed-closer"} and self.closer_unit is not None:
            return self.closer_unit
        _fail(f"role {role!r} has no concrete manifest unit")

    def prevalidate(self, *, require_root: bool = False) -> dict[str, Any]:
        """Reject the complete manifest before any external observation side effect."""

        policy = self.policy
        roles = tuple(item.role for item in self.acquisitions)
        if roles != policy.acquisition_order:
            _fail(
                "scenario acquisition order mismatch: "
                f"expected={policy.acquisition_order!r}, actual={roles!r}"
            )
        output_roles = frozenset(item.role for item in self.outputs)
        if len(output_roles) != len(self.outputs) or output_roles != policy.required_outputs:
            _fail(
                "scenario output roles mismatch: "
                f"missing={sorted(policy.required_outputs - output_roles)!r}, "
                f"unknown={sorted(output_roles - policy.required_outputs)!r}"
            )
        action_ids = tuple(item.action_id for item in self.formal_actions)
        if action_ids != policy.formal_actions:
            _fail(
                "scenario formal action order mismatch: "
                f"expected={policy.formal_actions!r}, actual={action_ids!r}"
            )
        if self.preflight_receipt is None or self.static_inventory is None:
            _fail("manifest lacks its preflight/static-inventory authority")
        installer_authority = _validate_installer_authority(
            self.installer_receipt.path,
            preflight_reference=self.preflight_receipt,
            inventory_reference=self.static_inventory,
            descriptor_reference=self.descriptor,
            harness_reference=self.harness_program,
            run_unit=self.run_unit,
            require_root=require_root,
        )
        if self.source is None:
            if require_root:
                _fail("privileged harness lacks its execution manifest source")
            execution_manifest_source: dict[str, str] | None = None
            execution_manifest_asset: ExecutionManifestSource | None = None
        else:
            expected_manifest_path = (
                installer_authority["root"]
                / "authority"
                / "harness"
                / self.scenario
                / "MANIFEST.json"
            )
            if self.source.path != expected_manifest_path:
                _fail("execution manifest source is outside its exact root layout")
            self.source.revalidate(require_root=require_root)
            execution_manifest_source = self.source.reference
            execution_manifest_asset = self.source
        if self.manifest_unit_for_role("run-main") not in installer_authority["objects"]:
            _fail("installer authority does not contain the run unit")
        if self.closer_unit is not None and self.closer_unit not in installer_authority["objects"]:
            _fail("installer authority does not contain the closer unit")
        static_role_names = tuple(item.role for item in self.static_roles)
        if static_role_names != roles:
            _fail("static role bindings differ from the exact acquisition order")
        if (self.closer_unit is None) != (policy.closer_owner is None):
            _fail("scenario closer presence differs from the closed policy")
        if self.scenario == "H10" and self.scenario_input is None:
            _fail("H10 requires its exact negative-control input")
        if policy.run_owner.schema == "formal":
            if policy.formal_completion not in {
                "typed",
                "requirement-missing",
                "failstop",
            }:
                _fail("formal scenario lacks one closed completion policy")
            if policy.formal_completion == "requirement-missing" and policy.formal_actions:
                _fail("source-unobservable formal policy cannot own an external action")
            if (policy.formal_completion == "failstop") != (
                "formal-failstop" in policy.required_outputs
            ):
                _fail("formal fail-stop completion/output policy drifted")
            if (policy.formal_completion != "failstop") != (
                "formal-final" in policy.required_outputs
            ):
                _fail("formal-final completion/output policy drifted")
        elif (
            policy.formal_case is not None
            or policy.formal_actions
            or policy.formal_completion is not None
            or policy.formal_expected_fact_type is not None
        ):
            _fail("non-formal scenario carries formal completion authority")

        if len(self.formal_actions) > 1:
            _fail("one formal scenario cannot own multiple external actions")
        for action in self.formal_actions:
            case_id = policy.formal_case[0] if policy.formal_case is not None else None
            needs_armed = case_id in {"B4", "B6", "B7"}
            needs_operation = case_id == "B6"
            needs_control = case_id in {"B4", "B5", "B7"}
            if needs_armed != (action.armed_receipt_path is not None):
                _fail("formal action ARMED receipt presence differs from policy")
            if needs_operation != (action.operation_receipt_path is not None):
                _fail("formal action operation receipt presence differs from policy")
            if needs_control != (action.control_fifo is not None):
                _fail("formal action control FIFO presence differs from policy")
            if action.action_ledger_path != self.output("formal-action"):
                _fail("formal action ledger does not equal its exact manifest output")

        formal_plan: dict[str, Any] | None = None
        formal_directory_authorities: dict[str, dict[str, Any]] | None = None
        b5_descendant_authority: dict[str, Any] | None = None
        validated_static_plans: dict[str, dict[str, Any]] = {}
        static_role_authorities: dict[str, StaticRoleAuthority] = {}
        paths: list[Path] = [
            self.descriptor.path,
            self.installer_receipt.path,
            self.harness_program.path,
            self.boot_id_file.path,
            self.preflight_receipt.path,
            self.static_inventory.path,
            *(item.path for item in self.outputs),
            *((self.source.path,) if self.source is not None else ()),
        ]
        for binding, acquisition in zip(self.static_roles, self.acquisitions):
            static_authority = self._validate_static_role(
                binding,
                acquisition,
                installer_authority["assets"],
                installer_authority["retained_assets"],
                require_root=require_root,
            )
            static_plan = static_authority.plan
            paths.extend(static_authority.private_paths)
            static_role_authorities[binding.role] = static_authority
            validated_static_plans[binding.role] = static_plan
            if binding.owner == "formal":
                if formal_plan is not None:
                    _fail("manifest has more than one formal static plan authority")
                formal_plan = static_plan
                formal_directory_authorities = _freeze_formal_directory_authorities(
                    formal_plan
                )
        if policy.run_owner.schema == "formal":
            if formal_plan is None or formal_directory_authorities is None:
                _fail("formal policy lacks its pre-StartUnit directory authority")
            if policy.formal_case is not None and policy.formal_case[0] == "B5":
                if len(self.formal_actions) != 1:
                    _fail("B5 policy lacks its one pre-StartUnit action authority")
                b5_descendant_authority = _freeze_b5_descendant_authority(
                    formal_plan,
                    action=self.formal_actions[0],
                    run_unit=self.run_unit,
                    variant=policy.formal_case[1],
                    assets=installer_authority["assets"],
                    retained_assets=installer_authority["retained_assets"],
                    require_root=require_root,
                )
                paths.extend(
                    (
                        b5_descendant_authority["request_path"],
                        b5_descendant_authority["receipt_path"],
                    )
                )
        for acquisition in self.acquisitions:
            paths.extend(
                (
                    acquisition.armed_receipt_path,
                    acquisition.ready_fifo.path,
                    acquisition.release_fifo.path,
                )
            )
        for action in self.formal_actions:
            paths.extend(
                item
                for item in (action.armed_receipt_path, action.operation_receipt_path)
                if item is not None
            )
            if action.control_fifo is not None:
                paths.append(action.control_fifo.path)
        if self.scenario == "H8":
            assert self.scenario_input is not None
            if Path(self.scenario_input["ledger_path"]) != self.output("h8-ledger"):
                _fail("H8 ledger input does not equal its exact manifest output")
        elif self.scenario == "H10":
            assert self.scenario_input is not None
            actor_receipt = Path(self.scenario_input["actor_receipt_path"])
            adversary_plans = [
                validated_static_plans[item.role]
                for item in self.static_roles
                if item.owner == "adversary" and item.mode == "h10-gc-negative"
            ]
            if (
                len(adversary_plans) != 1
                or adversary_plans[0].get("receipt_path") != str(actor_receipt)
            ):
                _fail("H10 actor receipt differs from its static adversary output")
        retained_roles = set(installer_authority["retained_assets"])
        inventory_roles = set(installer_authority["assets"])
        if retained_roles != inventory_roles:
            _fail(
                "static inventory has unconsumed or unknown assets: "
                f"unconsumed={sorted(inventory_roles - retained_roles)!r}, "
                f"unknown={sorted(retained_roles - inventory_roles)!r}"
            )
        if len(paths) != len(set(paths)):
            _fail("manifest reuses path authority across outputs/acquisitions/actions")

        for output in self.outputs:
            if output.path.parent not in {self.input_root, self.receipt_root}:
                _fail("manifest output is outside the two sealed output parents")
            if output.path.exists() or output.path.is_symlink():
                _fail("manifest output destination already exists")
            parent = output.path.parent.lstat()
            if not stat.S_ISDIR(parent.st_mode):
                _fail("manifest output parent is not a directory")
        result = dict(installer_authority)
        result["formal_directory_authorities"] = formal_directory_authorities
        result["b5_descendant_authority"] = b5_descendant_authority
        result["static_role_authorities"] = static_role_authorities
        result["execution_manifest_source"] = execution_manifest_source
        result["execution_manifest_asset"] = execution_manifest_asset
        return result


def decode_manifest(path: Path) -> HarnessManifest:
    source, manifest_raw = ExecutionManifestSource.open_once(
        path, require_root=True
    )
    value = _decode_canonical_raw(manifest_raw, label="harness manifest")
    expected_keys = (_MANIFEST_KEYS - {"descriptor_path", "boot_id_path"}) | {
        "descriptor",
        "installer_receipt",
        "harness_program",
        "boot_id_file",
    }
    _exact(value, expected_keys, label="harness manifest")
    if value["schema"] != MANIFEST_SCHEMA:
        _fail("unexpected harness manifest schema")
    scenario = _text(value["scenario"], label="scenario")
    if scenario not in _SCENARIO_POLICIES:
        _fail("scenario is not in the closed system/formal policy table")
    run_unit = _text(value["run_unit"], label="run_unit")
    if _UNIT_RE.fullmatch(run_unit) is None:
        _fail("run_unit is not a concrete Scion formal unit")
    closer_value = value["closer_unit"]
    if closer_value is None:
        closer_unit = None
    else:
        closer_unit = _text(closer_value, label="closer_unit")
        if _UNIT_RE.fullmatch(closer_unit) is None or closer_unit == run_unit:
            _fail("closer_unit is invalid or aliases run_unit")
    input_root = _path(value["input_root"], label="input_root")
    receipt_root = _path(value["receipt_root"], label="receipt_root")
    for root, label in ((input_root, "input_root"), (receipt_root, "receipt_root")):
        info = root.lstat()
        if (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid != 0
            or info.st_gid != 0
            or stat.S_IMODE(info.st_mode) != 0o555
            or root.is_symlink()
        ):
            _fail(f"{label} must be one root:root 0555 non-symlink directory")
    acquisition_values = value["acquisitions"]
    if type(acquisition_values) is not list:
        _fail("acquisitions must be one exact array")
    acquisitions = tuple(
        Acquisition.decode(item, label=f"acquisitions[{index}]")
        for index, item in enumerate(acquisition_values)
    )
    output_values = value["outputs"]
    if type(output_values) is not list or not output_values:
        _fail("outputs must be one nonempty array")
    outputs: list[OutputPath] = []
    roles: set[str] = set()
    all_paths: set[Path] = set()
    for index, item in enumerate(output_values):
        if type(item) is not dict:
            _fail(f"outputs[{index}] must be one object")
        _exact(item, _OUTPUT_KEYS, label=f"outputs[{index}]")
        role = _text(item["role"], label=f"outputs[{index}].role")
        output_path = _path(item["path"], label=f"outputs[{index}].path")
        if _ROLE_RE.fullmatch(role) is None or role in roles:
            _fail("output role is invalid or duplicated")
        roles.add(role)
        if output_path.parent not in {input_root, receipt_root}:
            _fail("output must be an immediate child of input/receipt root")
        outputs.append(OutputPath(role, output_path))
        all_paths.add(output_path)
    acquisition_roles: set[str] = set()
    for acquisition in acquisitions:
        if acquisition.role in acquisition_roles:
            _fail("acquisition role is duplicated")
        acquisition_roles.add(acquisition.role)
        for candidate in (
            acquisition.armed_receipt_path,
            acquisition.ready_fifo.path,
            acquisition.release_fifo.path,
        ):
            if candidate in all_paths:
                _fail("manifest path authority is reused across roles")
            all_paths.add(candidate)
        if acquisition.ready_fifo.path == acquisition.release_fifo.path:
            _fail("ready and release FIFO must be distinct")
    formal_action_values = value["formal_actions"]
    if type(formal_action_values) is not list:
        _fail("formal_actions must be one exact array")
    formal_actions = tuple(
        FormalAction.decode(item, label=f"formal_actions[{index}]")
        for index, item in enumerate(formal_action_values)
    )
    static_role_values = value["static_roles"]
    if type(static_role_values) is not list:
        _fail("static_roles must be one exact ordered array")
    static_roles = tuple(
        StaticRoleBinding.decode(item, label=f"static_roles[{index}]")
        for index, item in enumerate(static_role_values)
    )
    scenario_input = value["scenario_input"]
    if scenario == "H8":
        if type(scenario_input) is not dict:
            _fail("H8 requires one drift input")
        _exact(scenario_input, {"drift_name", "ledger_path"}, label="scenario_input")
        drift_name = _text(scenario_input["drift_name"], label="drift_name")
        if _ROLE_RE.fullmatch(drift_name) is None or "/" in drift_name:
            _fail("H8 drift_name must be one canonical cgroup leaf")
        ledger_path = _path(scenario_input["ledger_path"], label="ledger_path")
        if ledger_path.parent != receipt_root:
            _fail("H8 ledger path must be under receipt_root")
    elif scenario == "H10":
        if type(scenario_input) is not dict:
            _fail("H10 requires one actor receipt input")
        _exact(scenario_input, {"actor_receipt_path"}, label="scenario_input")
        actor_receipt_path = _path(
            scenario_input["actor_receipt_path"], label="actor_receipt_path"
        )
        if actor_receipt_path in all_paths:
            _fail("H10 actor receipt path aliases another authority")
    elif scenario_input is not None:
        _fail("scenario_input is reserved for H8/H10")
    result = HarnessManifest(
        scenario=scenario,
        descriptor=HashedFile.decode_reference(value["descriptor"], label="descriptor"),
        installer_receipt=HashedFile.decode(
            value["installer_receipt"], label="installer_receipt"
        ),
        harness_program=HashedFile.decode_reference(
            value["harness_program"], label="harness_program"
        ),
        run_unit=run_unit,
        closer_unit=closer_unit,
        boot_id_file=PinnedFile.decode(value["boot_id_file"], label="boot_id_file"),
        input_root=input_root,
        receipt_root=receipt_root,
        acquisitions=acquisitions,
        formal_actions=formal_actions,
        outputs=tuple(outputs),
        scenario_input=scenario_input,
        preflight_receipt=HashedFile.decode(
            value["preflight_receipt"], label="preflight_receipt"
        ),
        static_inventory=HashedFile.decode_reference(
            value["static_inventory"], label="static_inventory"
        ),
        static_roles=static_roles,
        source=source,
    )
    if result.harness_program.path.resolve() != Path(__file__).resolve():
        _fail("manifest harness_program does not name this exact program")
    return result


@dataclass(frozen=True)
class ManagerSignal:
    ordinal: int
    member: str
    signature: str
    body: tuple[Any, ...]
    object_path: str
    sender: str


class ManagerTransport(Protocol):
    owner: str

    def install_signal_handlers(self, callback: Callable[[ManagerSignal], None]) -> None: ...

    def subscribe(self) -> None: ...

    def ref_unit(self, unit: str) -> None: ...

    def start_unit(self, unit: str, mode: str) -> str: ...

    def stop_unit(self, unit: str, mode: str) -> str: ...

    def reset_failed_unit(self, unit: str) -> None: ...

    def unref_unit(self, unit: str) -> None: ...

    def load_unit(self, unit: str) -> str: ...

    def get_unit(self, unit: str) -> str: ...

    def property(self, object_path: str, interface: str, name: str) -> Any: ...

    def wait_for(self, predicate: Callable[[], bool]) -> None: ...

    def wait_readable(self, descriptor: int) -> None: ...


class DBusSystemManager:
    """dbus-python/GLib system-manager transport with no command fallback."""

    def __init__(
        self,
        allowed_unit_objects: dict[str, str] | None = None,
    ) -> None:
        try:
            import dbus  # type: ignore[import-not-found]
            import _dbus_bindings  # type: ignore[import-not-found]
            from dbus.mainloop.glib import DBusGMainLoop  # type: ignore[import-not-found]
            from gi.repository import GLib  # type: ignore[import-not-found]
        except ImportError as exc:
            raise HarnessError("dbus-python/GLib binding is unavailable") from exc
        DBusGMainLoop(set_as_default=True)
        self._dbus = dbus
        self._glib = GLib
        self._bus = dbus.SystemBus()
        dbus_obj = self._bus.get_object("org.freedesktop.DBus", "/org/freedesktop/DBus")
        dbus_iface = dbus.Interface(dbus_obj, "org.freedesktop.DBus")
        self.owner = str(dbus_iface.GetNameOwner(SYSTEMD_DESTINATION))
        dbus_paths = [Path(dbus.__file__).resolve(), Path(_dbus_bindings.__file__).resolve()]
        self.binding_receipt = {
            "files": [
                {
                    "path": str(path),
                    "sha256": hashlib.sha256(
                        _read_regular(path, label="dbus-python binding")
                    ).hexdigest(),
                }
                for path in dbus_paths
            ],
            "module_version": str(getattr(dbus, "__version__", "unknown")),
        }
        manager_obj = self._bus.get_object(self.owner, MANAGER_PATH)
        self._manager = dbus.Interface(manager_obj, MANAGER_INTERFACE)
        self._callback: Callable[[ManagerSignal], None] | None = None
        self._allowed_unit_objects = dict(allowed_unit_objects or {})
        self._ordinal = 0
        self._loop: Any = None
        self._predicate: Callable[[], bool] | None = None

    def install_signal_handlers(self, callback: Callable[[ManagerSignal], None]) -> None:
        if self._callback is not None:
            _fail("signal handlers are already installed")
        self._callback = callback
        for member in ("JobNew", "JobRemoved", "UnitNew", "UnitRemoved"):
            def handler(
                *body: Any,
                _member: str = member,
                path: str | None = None,
                sender: str | None = None,
            ) -> None:
                self._emit(_member, tuple(body), path or MANAGER_PATH, sender or "")

            self._bus.add_signal_receiver(
                handler,
                signal_name=member,
                dbus_interface=MANAGER_INTERFACE,
                bus_name=self.owner,
                path=MANAGER_PATH,
                path_keyword="path",
                sender_keyword="sender",
            )

        def properties_handler(
            *body: Any, path: str | None = None, sender: str | None = None
        ) -> None:
            self._emit("PropertiesChanged", tuple(body), path or "", sender or "")

        self._bus.add_signal_receiver(
            properties_handler,
            signal_name="PropertiesChanged",
            dbus_interface=PROPERTIES_INTERFACE,
            bus_name=self.owner,
            path_keyword="path",
            sender_keyword="sender",
        )

    def _emit(self, member: str, body: tuple[Any, ...], path: str, sender: str) -> None:
        if self._callback is None or member not in _SIGNAL_SIGNATURES:
            _fail("unallowlisted manager signal")
        if sender and sender != self.owner:
            _fail("manager signal sender owner drifted")
        unit: str | None = None
        if member in {"JobNew", "JobRemoved"} and len(body) >= 3:
            unit = str(body[2])
        elif member in {"UnitNew", "UnitRemoved"} and body:
            unit = str(body[0])
        if member in {"UnitNew", "UnitRemoved"}:
            if (
                len(body) != 2
                or unit is None
                or self._allowed_unit_objects.get(unit) != str(body[1])
            ):
                _fail("manager unit signal differs from installer unit/object authority")
        if (
            unit is not None
            and self._allowed_unit_objects
            and unit not in self._allowed_unit_objects
        ):
            return
        if (
            member == "PropertiesChanged"
            and self._allowed_unit_objects
            and path not in self._allowed_unit_objects.values()
        ):
            _fail("PropertiesChanged object is outside installer authority")
        self._ordinal += 1
        self._callback(
            ManagerSignal(
                self._ordinal,
                member,
                _SIGNAL_SIGNATURES[member],
                body,
                path,
                sender or self.owner,
            )
        )
        if self._loop is not None and self._predicate is not None and self._predicate():
            self._loop.quit()

    def subscribe(self) -> None:
        self._manager.Subscribe()

    def ref_unit(self, unit: str) -> None:
        self._manager.RefUnit(unit)

    def start_unit(self, unit: str, mode: str) -> str:
        return str(self._manager.StartUnit(unit, mode))

    def stop_unit(self, unit: str, mode: str) -> str:
        return str(self._manager.StopUnit(unit, mode))

    def reset_failed_unit(self, unit: str) -> None:
        self._manager.ResetFailedUnit(unit)

    def unref_unit(self, unit: str) -> None:
        self._manager.UnrefUnit(unit)

    def load_unit(self, unit: str) -> str:
        return str(self._manager.LoadUnit(unit))

    def get_unit(self, unit: str) -> str:
        return str(self._manager.GetUnit(unit))

    def property(self, object_path: str, interface: str, name: str) -> Any:
        obj = self._bus.get_object(self.owner, object_path)
        props = self._dbus.Interface(obj, PROPERTIES_INTERFACE)
        return props.Get(interface, name)

    def wait_for(self, predicate: Callable[[], bool]) -> None:
        if predicate():
            return
        self._predicate = predicate
        self._loop = self._glib.MainLoop()
        self._loop.run()
        self._loop = None
        self._predicate = None

    def wait_readable(self, descriptor: int) -> None:
        loop = self._glib.MainLoop()

        def readable(_descriptor: int, condition: Any) -> bool:
            if condition & (self._glib.IO_ERR | self._glib.IO_NVAL):
                _fail("ready FIFO event source failed")
            loop.quit()
            return False

        self._glib.io_add_watch(
            descriptor,
            self._glib.IO_IN | self._glib.IO_HUP | self._glib.IO_ERR | self._glib.IO_NVAL,
            readable,
        )
        loop.run()


class JournalTransport(Protocol):
    binding_receipt: dict[str, Any]

    def begin(self) -> None: ...

    def add_invocation(self, boot_id: str, invocation_id: str) -> None: ...

    def synchronize(self) -> dict[str, Any]: ...

    def freeze(self) -> dict[str, Any]: ...


def synchronize_journal_varlink(socket_path: Path = Path(JOURNAL_SOCKET)) -> dict[str, Any]:
    """Perform exactly one direct NUL-framed Journal.Synchronize call."""

    before = socket_path.lstat()
    if not stat.S_ISSOCK(before.st_mode):
        _fail("journal Varlink authority is not a Unix socket")
    request = json.dumps(
        {"method": "io.systemd.Journal.Synchronize", "parameters": {}},
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii") + b"\0"
    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM | socket.SOCK_CLOEXEC)
    try:
        connection.connect(str(socket_path))
        peer = os.fstat(connection.fileno())
        if not stat.S_ISSOCK(peer.st_mode):
            _fail("connected journal authority is not a socket")
        connection.sendall(request)
        chunks: list[bytes] = []
        while True:
            chunk = connection.recv(1024 * 1024)
            if not chunk:
                _fail("journal Synchronize returned EOF before one NUL frame")
            chunks.append(chunk)
            joined = b"".join(chunks)
            if b"\0" in joined:
                frame, suffix = joined.split(b"\0", 1)
                if suffix:
                    _fail("journal Synchronize returned more than one frame")
                break
    finally:
        connection.close()
    after = socket_path.lstat()
    if (after.st_dev, after.st_ino) != (before.st_dev, before.st_ino):
        _fail("journal Varlink socket identity drifted")
    try:
        response = json.loads(
            frame.decode("utf-8", "strict"),
            object_pairs_hook=_object_no_duplicates,
            parse_constant=_reject_constant,
        )
    except HarnessError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise HarnessError("journal Synchronize reply is malformed") from exc
    if type(response) is not dict or "error" in response:
        _fail("journal Synchronize returned an error")
    return {
        "request_sha256": hashlib.sha256(request).hexdigest(),
        "reply": response,
        "socket_path": str(socket_path),
        "socket_device": str(before.st_dev),
        "socket_inode": str(before.st_ino),
        "socket_uid": str(before.st_uid),
        "socket_gid": str(before.st_gid),
        "socket_mode": format(stat.S_IMODE(before.st_mode), "04o"),
    }


def _journal_cursor(value: Any, *, label: str) -> str:
    cursor = _text(value, label=label)
    if not cursor.isascii() or any(
        ord(character) <= 0x20 or ord(character) >= 0x7F
        for character in cursor
    ):
        _fail(f"{label} is not one canonical nonempty journal cursor")
    return cursor


class SystemJournal:
    """python-systemd reader with complete fields and a direct sync barrier."""

    def __init__(self) -> None:
        try:
            import systemd  # type: ignore[import-not-found]
            from systemd import _reader  # type: ignore[import-not-found]
            from systemd import journal  # type: ignore[import-not-found]
        except ImportError as exc:
            raise HarnessError("python-systemd journal binding is unavailable") from exc
        self._systemd = systemd
        self._journal_module = journal
        self._reader: Any = None
        self._start_cursor: str | None = None
        self._matches: list[dict[str, str]] = []
        module_paths = [Path(journal.__file__).resolve(), Path(_reader.__file__).resolve()]
        self.binding_receipt = {
            "files": [
                {
                    "path": str(path),
                    "sha256": hashlib.sha256(
                        _read_regular(path, label="python-systemd binding")
                    ).hexdigest(),
                }
                for path in module_paths
            ],
            "module_version": str(getattr(systemd, "__version__", "unknown")),
        }

    def begin(self) -> None:
        if self._reader is not None:
            _fail("journal Reader was already opened")
        reader = self._journal_module.Reader()
        reader.data_threshold = 0
        reader.seek_tail()
        previous = reader.get_previous()
        self._start_cursor = (
            _journal_cursor(reader.get_cursor(), label="journal start cursor")
            if previous
            else None
        )
        self._reader = reader

    def add_invocation(self, boot_id: str, invocation_id: str) -> None:
        if self._reader is None:
            _fail("journal Reader must open before matches")
        if _BOOT_RE.fullmatch(boot_id) is None or _INVOCATION_RE.fullmatch(invocation_id) is None:
            _fail("journal invocation match is noncanonical")
        match = {"_BOOT_ID": boot_id, "_SYSTEMD_INVOCATION_ID": invocation_id}
        if self._matches:
            self._reader.add_disjunction()
        self._reader.add_match(**match)
        self._matches.append(match)

    def synchronize(self) -> dict[str, Any]:
        if self._reader is None:
            _fail("journal Reader did not open before synchronize")
        return synchronize_journal_varlink()

    def freeze(self) -> dict[str, Any]:
        if self._reader is None:
            _fail("journal Reader did not open")
        reader = self._reader
        if self._start_cursor is not None:
            _journal_cursor(self._start_cursor, label="journal retained start cursor")
        reader.seek_tail()
        last = reader.get_previous()
        end_cursor = (
            _journal_cursor(reader.get_cursor(), label="journal end cursor")
            if last
            else None
        )
        if self._start_cursor is None:
            reader.seek_head()
        else:
            reader.seek_cursor(self._start_cursor)
            reader.get_next()
        entries: list[dict[str, Any]] = []
        reached_end = end_cursor is None
        for entry in reader:
            cursor = _journal_cursor(
                reader.get_cursor(), label="journal captured cursor"
            )
            fields = [
                {"name": str(name), "value": encode_journal_value(value)}
                for name, value in entry.items()
            ]
            entries.append({"cursor": cursor, "fields": fields})
            if end_cursor is not None and cursor == end_cursor:
                reached_end = True
                break
        if end_cursor is None:
            if entries:
                _fail("empty journal interval produced entries without an end cursor")
        elif (
            not reached_end
            or not entries
            or entries[-1]["cursor"] != end_cursor
        ):
            _fail("journal iterator ended before the frozen end cursor")
        return {
            "schema": JOURNAL_RECEIPT_SCHEMA,
            "reader_before_start": True,
            "data_threshold": "0",
            "start_cursor": self._start_cursor,
            "end_cursor": end_cursor,
            "matches": self._matches,
            "entries": entries,
            "binding": self.binding_receipt,
        }


def _boot_id(file: PinnedFile) -> str:
    raw = _read_regular(file.path, label="boot ID file")
    try:
        value = raw.decode("ascii", "strict").strip()
    except UnicodeError as exc:
        raise HarnessError("boot ID is not ASCII") from exc
    if _BOOT_RE.fullmatch(value) is None:
        _fail("boot ID is not canonical")
    info = file.path.lstat()
    if (info.st_dev, info.st_ino) != (file.device, file.inode):
        _fail("boot ID file identity drifted")
    return value


def _revalidate_retained_static_authority(
    authority: dict[str, Any], *, require_root: bool
) -> None:
    inventory = authority.get("inventory_asset")
    retained = authority.get("retained_assets")
    roles = authority.get("static_role_authorities")
    manifest_source = authority.get("execution_manifest_asset")
    if not isinstance(inventory, RetainedStaticAsset) or type(retained) is not dict:
        _fail("retained static authority is incomplete")
    inventory.revalidate_path_identity(
        label="preflight-bound static inventory", require_root=require_root
    )
    if manifest_source is not None:
        if not isinstance(manifest_source, ExecutionManifestSource):
            _fail("retained execution manifest authority is malformed")
        manifest_source.revalidate(require_root=require_root)
    for role, asset in retained.items():
        if not isinstance(asset, RetainedStaticAsset):
            _fail("retained static asset cache is malformed")
        asset.revalidate_path_identity(
            label=f"retained static asset {role}", require_root=require_root
        )
    if type(roles) is not dict:
        _fail("retained static role authority is incomplete")
    for role, static_authority in roles.items():
        if not isinstance(static_authority, StaticRoleAuthority):
            _fail(f"retained static role authority is malformed: {role}")
        static_authority.revalidate(require_root=require_root)


def _close_retained_static_authority(authority: dict[str, Any] | None) -> None:
    if type(authority) is not dict:
        return
    retained = authority.get("retained_assets")
    if type(retained) is dict:
        for asset in retained.values():
            if isinstance(asset, RetainedStaticAsset):
                asset.close()
    inventory = authority.get("inventory_asset")
    if isinstance(inventory, RetainedStaticAsset):
        inventory.close()
    manifest_source = authority.get("execution_manifest_asset")
    if isinstance(manifest_source, ExecutionManifestSource):
        manifest_source.close()


def _invocation_from_encoded(value: dict[str, Any], *, allow_empty: bool) -> str:
    if value.get("signature") != "ay" or value.get("kind") != "binary":
        _fail("InvocationID property was not encoded as ay")
    try:
        raw = base64.b64decode(value["base64"], validate=True)
    except (KeyError, TypeError, ValueError) as exc:
        raise HarnessError("InvocationID base64 is invalid") from exc
    if allow_empty and len(raw) == 0 and value.get("length") == "0":
        return ""
    if len(raw) != 16 or value.get("length") != "16":
        _fail("InvocationID property is not exactly 16 bytes")
    return raw.hex()


def query_unit_properties(
    manager: ManagerTransport,
    *,
    unit: str,
    peer_unit: str | None,
    boot_id: str,
    receipt_path: Path,
    allow_empty_invocation: bool = False,
    publish: bool = True,
    object_path: str | None = None,
) -> dict[str, Any]:
    """Freeze every allowlisted systemd-255 property before normalization."""

    if object_path is None:
        object_path = manager.get_unit(unit)
    properties: list[dict[str, Any]] = []
    raw_values: dict[str, Any] = {}
    invocation_id: str | None = None
    for interface, names in _PROPERTY_SIGNATURES.items():
        for name, signature in names.items():
            raw_value = manager.property(object_path, interface, name)
            encoded = encode_dbus(signature, raw_value)
            raw_values[name] = raw_value
            properties.append(
                {
                    "destination_owner": manager.owner,
                    "object_path": object_path,
                    "interface": interface,
                    "property": name,
                    "variant_signature": signature,
                    "value": encoded,
                }
            )
            if interface == UNIT_INTERFACE and name == "InvocationID":
                invocation_id = _invocation_from_encoded(
                    encoded, allow_empty=allow_empty_invocation
                )
    receipt = {
        "schema": RAW_QUERY_SCHEMA,
        "boot_id": boot_id,
        "unit": unit,
        "object_path": object_path,
        "manager_owner": manager.owner,
        "invocation_id": invocation_id,
        "properties": properties,
        "normalization": {
            "configured": _normalize_configured_properties(
                unit=unit,
                peer_unit=peer_unit,
                raw_values=raw_values,
            )
        },
    }
    if publish:
        _write_no_replace(receipt_path, receipt)
    return receipt


def _property_text(name: str, value: Any) -> str:
    if name in {"Delegate"}:
        return "yes" if bool(value) else "no"
    if name in {"TimeoutStartUSec", "TimeoutStopUSec"}:
        number = int(value)
        return "infinity" if number == (1 << 64) - 1 else str(number)
    if name in {"After", "OnSuccess", "OnFailure", "DelegateControllers"}:
        return " ".join(str(item) for item in value)
    return str(value)


def _normalize_configured_properties(
    *, unit: str, peer_unit: str | None, raw_values: dict[str, Any]
) -> dict[str, Any]:
    """Run the production configured-property decoder before release."""

    if peer_unit is None:
        if (
            str(raw_values.get("CollectMode")) != "inactive-or-failed"
            or str(raw_values.get("Restart")) != "no"
        ):
            _fail("negative control properties are not exact inactive-or-failed/Restart=no")
        return {
            "status": "rejected-negative-control",
            "reason": "CollectMode=inactive-or-failed cannot satisfy positive configured decoder",
        }
    try:
        from scion.runtime.execution.systemd255 import (  # type: ignore[import-not-found]
            ConfiguredUnitProperties,
            UnitRole,
        )
    except ImportError as exc:
        raise HarnessError("accepted systemd255 decoder is unavailable") from exc
    role = UnitRole.RUN if raw_values.get("OnSuccess") else UnitRole.CLOSER
    if role is UnitRole.RUN:
        configured = {
            "Delegate": "pids",
            "DelegateSubgroup": "supervisor",
            "CollectMode": "inactive",
            "Restart": "no",
            "KillMode": "control-group",
            "TimeoutStopSec": "infinity",
            "OnSuccess": peer_unit,
            "OnFailure": peer_unit,
        }
        expanded_names = {
            "Id",
            "Delegate",
            "DelegateControllers",
            "DelegateSubgroup",
            "CollectMode",
            "Restart",
            "KillMode",
            "TimeoutStopUSec",
            "OnSuccess",
            "OnFailure",
        }
    else:
        configured = {
            "CollectMode": "inactive",
            "Restart": "no",
            "TimeoutStartSec": "infinity",
            "After": peer_unit,
        }
        expanded_names = {"Id", "CollectMode", "Restart", "TimeoutStartUSec", "After"}
    expanded = {name: _property_text(name, raw_values[name]) for name in expanded_names}
    decoded = ConfiguredUnitProperties.from_receipts(
        role,
        configured,
        expanded,
        expected_unit=unit,
        expected_peer=peer_unit,
    )
    return {"status": "accepted", "role": decoded.role.value}


def seal_source_selector(
    *,
    boot_id: str,
    source_unit: str,
    source_invocation_id: str,
    source_receipt_path: Path,
    selector_path: Path,
) -> dict[str, Any]:
    if _BOOT_RE.fullmatch(boot_id) is None:
        _fail("selector boot_id is not canonical")
    if _UNIT_RE.fullmatch(source_unit) is None:
        _fail("selector source_unit is not canonical")
    if _INVOCATION_RE.fullmatch(source_invocation_id) is None:
        _fail("selector source_invocation_id is not canonical")
    source_raw = _read_regular(source_receipt_path, label="source receipt")
    selector = {
        "schema": SOURCE_SELECTOR_SCHEMA,
        "boot_id": boot_id,
        "source_unit": source_unit,
        "source_invocation_id": source_invocation_id,
        "source_receipt_sha256": hashlib.sha256(source_raw).hexdigest(),
    }
    _write_no_replace(selector_path, selector)
    return selector


def _signal_body(signature: str, body: tuple[Any, ...]) -> list[dict[str, Any]]:
    nodes: list[SignatureNode] = []
    cursor = 0
    while cursor < len(signature):
        node, cursor = _parse_one(signature, cursor)
        nodes.append(node)
    if len(nodes) != len(body):
        _fail("manager signal body arity does not match allowlisted signature")
    return [_encode_node(node, value) for node, value in zip(nodes, body)]


def _encoded_property(receipt: dict[str, Any], interface: str, name: str) -> dict[str, Any]:
    matches = [
        item["value"]
        for item in receipt["properties"]
        if item["interface"] == interface and item["property"] == name
    ]
    if len(matches) != 1:
        _fail(f"raw query does not contain exactly one {interface}.{name}")
    return matches[0]


def _encoded_text(receipt: dict[str, Any], interface: str, name: str) -> str:
    encoded = _encoded_property(receipt, interface, name)
    if encoded.get("kind") != "text" or type(encoded.get("value")) is not str:
        _fail(f"{interface}.{name} is not exact text")
    return encoded["value"]


def _encoded_integer(receipt: dict[str, Any], interface: str, name: str) -> int:
    encoded = _encoded_property(receipt, interface, name)
    value = encoded.get("value")
    if encoded.get("kind") != "integer" or type(value) is not str:
        _fail(f"{interface}.{name} is not one exact integer")
    if re.fullmatch(r"-?(?:0|[1-9][0-9]*)", value) is None:
        _fail(f"{interface}.{name} integer is not canonical")
    return int(value, 10)


def _final_exec_stop_post(receipt: dict[str, Any]) -> tuple[int, int]:
    encoded = _encoded_property(receipt, SERVICE_INTERFACE, "ExecStopPost")
    items = encoded.get("items")
    if encoded.get("signature") != "a(sasbttttuii)" or type(items) is not list:
        _fail("ExecStopPost lost its exact structured signature")
    if len(items) != 1 or items[0].get("kind") != "struct":
        _fail("formal run must have exactly one final ExecStopPost command")
    fields = items[0].get("items")
    if type(fields) is not list or len(fields) != 10:
        _fail("ExecStopPost struct arity drifted")
    code = fields[8]
    status = fields[9]
    if code.get("signature") != "i" or status.get("signature") != "i":
        _fail("ExecStopPost final code/status signatures drifted")
    try:
        return int(code["value"], 10), int(status["value"], 10)
    except (KeyError, TypeError, ValueError) as exc:
        raise HarnessError("ExecStopPost final code/status is not canonical") from exc


@dataclass(frozen=True, slots=True)
class CloserTerminalProperties:
    unit: str
    invocation_id: str
    load_state: str
    active_state: str
    sub_state: str
    result: str
    exec_main_code: int
    exec_main_status: int

    @classmethod
    def from_receipt(
        cls, receipt: dict[str, Any], *, expected_unit: str
    ) -> "CloserTerminalProperties":
        invocation_id = receipt.get("invocation_id")
        if type(invocation_id) is not str or _INVOCATION_RE.fullmatch(invocation_id) is None:
            _fail("closer terminal InvocationID is not exact")
        stop = _encoded_property(receipt, SERVICE_INTERFACE, "ExecStopPost")
        if stop.get("signature") != "a(sasbttttuii)" or stop.get("items") != []:
            _fail("closer terminal must have an exact empty ExecStopPost array")
        value = cls(
            _encoded_text(receipt, UNIT_INTERFACE, "Id"),
            invocation_id,
            _encoded_text(receipt, UNIT_INTERFACE, "LoadState"),
            _encoded_text(receipt, UNIT_INTERFACE, "ActiveState"),
            _encoded_text(receipt, UNIT_INTERFACE, "SubState"),
            _encoded_text(receipt, SERVICE_INTERFACE, "Result"),
            _encoded_integer(receipt, SERVICE_INTERFACE, "ExecMainCode"),
            _encoded_integer(receipt, SERVICE_INTERFACE, "ExecMainStatus"),
        )
        if value.unit != expected_unit:
            _fail("closer terminal unit differs from the concrete closer")
        return value

    def semantic_tuple(self) -> tuple[str, str, str, str, int, int]:
        return (
            self.load_state,
            self.active_state,
            self.sub_state,
            self.result,
            self.exec_main_code,
            self.exec_main_status,
        )


def _closer_terminal_policy(
    receipt: dict[str, Any],
    *,
    expected_unit: str,
    expected: tuple[str, str, str, str, int, int],
) -> CloserTerminalProperties:
    value = CloserTerminalProperties.from_receipt(
        receipt, expected_unit=expected_unit
    )
    if value.semantic_tuple() != expected:
        _fail("closer terminal tuple differs from ScenarioPolicy")
    return value


def _sha256(value: Any, *, label: str) -> str:
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        _fail(f"{label} is not one canonical SHA-256 digest")
    return value


def _prove_armed_program(value: Any) -> dict[str, Any]:
    if type(value) is not dict:
        _fail("ARMED program must be one exact identity object")
    _exact(value, _PROGRAM_KEYS, label="ARMED program")
    path = _path(value["path"], label="ARMED program.path")
    digest = _sha256(value["sha256"], label="ARMED program.sha256")
    identity = value["identity"]
    if type(identity) is not dict:
        _fail("ARMED program.identity must be one exact object")
    _exact(identity, _PROGRAM_IDENTITY_KEYS, label="ARMED program.identity")
    if any(type(identity[name]) is not int or identity[name] < 0 for name in identity):
        _fail("ARMED program identity fields must be nonnegative integers")
    raw = _read_regular(path, label="ARMED program")
    info = path.lstat()
    if hashlib.sha256(raw).hexdigest() != digest:
        _fail("ARMED program hash differs from the executed fixture")
    if identity != {
        "device": info.st_dev,
        "inode": info.st_ino,
        "mode": stat.S_IMODE(info.st_mode),
    }:
        _fail("ARMED program filesystem identity drifted")
    return value


def _prove_armed_file(path_value: Any, sha_value: Any, *, label: str) -> Path:
    path = _path(path_value, label=f"{label}.path")
    digest = _sha256(sha_value, label=f"{label}.sha256")
    if hashlib.sha256(_read_regular(path, label=label)).hexdigest() != digest:
        _fail(f"{label} hash drifted")
    return path


def _armed_identity(
    path: Path,
    acquisition: Acquisition,
    authority: StaticRoleAuthority,
    *,
    run_unit: str,
    closer_unit: str | None,
    policy: ScenarioPolicy,
) -> dict[str, Any]:
    if authority.acquisition != acquisition or authority.role != acquisition.role:
        _fail("ARMED handoff differs from its immutable static role authority")
    authority.revalidate(require_root=False, require_armed_absent=False)
    armed = _decode_canonical(path, label=f"{acquisition.role} ARMED receipt")
    schema = armed.get("schema")
    owner = (
        policy.run_owner
        if acquisition.role == "run-main"
        else policy.stop_owner
        if acquisition.role in {"exec-stop-post", "h4-stop-post"}
        else policy.closer_owner
    )
    if owner is None:
        _fail("ARMED role has no owner in the closed scenario policy")
    if schema == "scion.generic_backend.systemd_observer_armed.v1":
        if owner.schema != "observer":
            _fail("observer ARMED schema differs from the closed role owner")
        _exact(armed, _OBSERVER_ARMED_KEYS, label="observer ARMED receipt")
        if acquisition.role not in {"run-main", "exec-stop-post", "closer"}:
            _fail("observer ARMED role is not observer-owned")
        if armed["mode"] != owner.mode:
            _fail("observer ARMED mode differs from the closed scenario policy")
        identity = armed.get("process_identity")
        identity_keys = _OBSERVER_IDENTITY_KEYS
    elif schema == "scion.generic_backend.systemd_adversary_armed.v1":
        if owner.schema != "adversary":
            _fail("adversary ARMED schema differs from the closed role owner")
        _exact(armed, _ADVERSARY_ARMED_KEYS, label="adversary ARMED receipt")
        if armed["scenario"] != owner.mode:
            _fail("adversary ARMED scenario differs from the closed scenario policy")
        identity = armed.get("actor")
        identity_keys = _ADVERSARY_IDENTITY_KEYS
    elif schema == FORMAL_ARMED_SCHEMA:
        if owner.schema != "formal" or acquisition.role != "run-main":
            _fail("formal ARMED schema differs from the closed role owner")
        _exact(armed, _FORMAL_ARMED_KEYS, label="formal ARMED receipt")
        if policy.formal_case is None or (
            armed["case_id"], armed["variant"]
        ) != policy.formal_case:
            _fail("formal ARMED case/variant differs from ScenarioPolicy")
        identity = armed.get("process_identity")
        identity_keys = _FORMAL_IDENTITY_KEYS
    else:
        _fail("ARMED receipt schema is not observer/adversary/formal v1")
    expected_unit = (
        run_unit
        if acquisition.role in {"run-main", "exec-stop-post", "h4-stop-post"}
        else closer_unit
    )
    if expected_unit is None or armed.get("unit") != expected_unit:
        _fail("ARMED unit differs from the acquisition role's concrete unit")
    if armed.get("ready_fifo") != {
        "path": str(acquisition.ready_fifo.path),
        "device": str(acquisition.ready_fifo.device),
        "inode": str(acquisition.ready_fifo.inode),
    } or armed.get("release_fifo") != {
        "path": str(acquisition.release_fifo.path),
        "device": str(acquisition.release_fifo.device),
        "inode": str(acquisition.release_fifo.inode),
    }:
        _fail("ARMED receipt FIFO authority does not match manifest")
    if type(identity) is not dict:
        _fail("ARMED receipt does not carry one actor identity")
    _exact(identity, identity_keys, label="ARMED actor identity")
    expected_program = {
        "path": str(authority.program_asset.path),
        "sha256": authority.program_asset.sha256,
        "identity": {
            "device": authority.program_asset.device,
            "inode": authority.program_asset.inode,
            "mode": authority.program_asset.mode,
        },
    }
    if (
        armed.get("plan_path") != str(authority.plan_asset.path)
        or armed.get("plan_sha256") != authority.plan_asset.sha256
        or armed.get("program") != expected_program
    ):
        _fail("ARMED receipt differs from its retained static plan/program authority")
    static_plan = authority.plan
    if schema == "scion.generic_backend.systemd_observer_armed.v1":
        request_path = _path(armed["request_path"], label="ARMED request_path")
        output_path = _path(armed["output_path"], label="ARMED output_path")
        selector = armed["source_selector_path"]
        if acquisition.role == "closer":
            _path(selector, label="ARMED source_selector_path")
        elif selector is not None:
            _fail("non-closer observer ARMED receipt names a source selector")
        environment = armed["stop_post_environment"]
        if acquisition.role == "exec-stop-post":
            if type(environment) is not dict or set(environment) != {
                "INVOCATION_ID",
                "SERVICE_RESULT",
                "EXIT_CODE",
                "EXIT_STATUS",
            }:
                _fail("stop-post observer ARMED environment has wrong keys")
        elif environment is not None:
            _fail("non-stop observer ARMED receipt carries stop-post environment")
        raw_authority_paths = armed["raw_authority_paths"]
        if type(raw_authority_paths) is not list or not raw_authority_paths:
            _fail("observer ARMED raw_authority_paths is not one ordered path list")
        authority_paths = tuple(
            _path(item, label="observer ARMED raw_authority_path")
            for item in raw_authority_paths
        )
        if len(authority_paths) != len(set(authority_paths)):
            _fail("observer ARMED raw authority path is duplicated")
        static_properties = static_plan.get("property_inputs")
        expected_authority_paths = (
            tuple(
                _path(
                    item.get("raw_authority_path"),
                    label="static observer raw_authority_path",
                )
                for item in static_properties
            )
            if type(static_properties) is list
            and all(type(item) is dict for item in static_properties)
            else ()
        )
        if (
            request_path != _path(
                static_plan.get("request_path"), label="static observer request_path"
            )
            or output_path != _path(
                static_plan.get("output_path"), label="static observer output_path"
            )
            or selector != static_plan.get("source_selector_path")
            or authority_paths != expected_authority_paths
        ):
            _fail("observer ARMED runtime paths differ from static role authority")
    elif schema == "scion.generic_backend.systemd_adversary_armed.v1":
        request_path = _path(armed["request_path"], label="ARMED request_path")
        _prove_armed_file(
            armed["request_path"], armed["request_sha256"], label="ARMED request"
        )
        receipt_path = _path(armed["receipt_path"], label="ARMED receipt_path")
        if (
            request_path
            != _path(
                static_plan.get("request_path"),
                label="static adversary request_path",
            )
            or receipt_path
            != _path(
                static_plan.get("receipt_path"),
                label="static adversary receipt_path",
            )
        ):
            _fail("adversary ARMED runtime paths differ from static role authority")
    else:
        final_config_path = _path(
            armed["final_config_path"], label="formal final_config_path"
        )
        if final_config_path != _path(
            static_plan.get("final_config_path"),
            label="static formal final_config_path",
        ):
            _fail("formal ARMED final config differs from static role authority")
    if armed["ready_sha256"] != hashlib.sha256(READY_BYTES).hexdigest():
        _fail("ARMED ready permit digest drifted")
    if armed["release_sha256"] != hashlib.sha256(RELEASE_BYTES).hexdigest():
        _fail("ARMED release permit digest drifted")
    invocation_id = identity.get("invocation_id")
    boot_id = identity.get("boot_id")
    unified_cgroup = identity.get("unified_cgroup")
    pid = identity.get("pid")
    starttime = identity.get("starttime")
    unit = armed.get("unit")
    if type(invocation_id) is not str or _INVOCATION_RE.fullmatch(invocation_id) is None:
        _fail("ARMED receipt invocation is not canonical")
    if type(unit) is not str or _UNIT_RE.fullmatch(unit) is None:
        _fail("ARMED receipt unit is not canonical")
    if type(boot_id) is not str or _BOOT_RE.fullmatch(boot_id) is None:
        _fail("ARMED receipt boot ID is not canonical")
    if type(unified_cgroup) is not str:
        _fail("ARMED receipt unified cgroup is not canonical")
    _text(unified_cgroup, label="ARMED unified cgroup")
    if (
        not unified_cgroup.startswith("/")
        or unified_cgroup == "/"
        or "//" in unified_cgroup
        or any(part in {"", ".", ".."} for part in unified_cgroup.split("/")[1:])
    ):
        _fail("ARMED receipt unified cgroup is not canonical")
    if type(pid) is not int or pid <= 0 or type(starttime) is not int or starttime <= 0:
        _fail("ARMED receipt PID/starttime is not positive")
    if identity["proc_cgroup_raw"] != f"0::{unified_cgroup}\n":
        _fail("ARMED raw cgroup entry differs from normalized unified lineage")
    if schema == "scion.generic_backend.systemd_adversary_armed.v1":
        if type(identity["session_id"]) is not int or identity["session_id"] <= 0:
            _fail("ARMED adversary session ID is not positive")
        if type(identity["stop_selector_environment"]) is not dict:
            _fail("ARMED adversary stop-selector environment is not one object")
    if schema == FORMAL_ARMED_SCHEMA:
        if identity["service_control_group"] != identity["unified_cgroup"].removesuffix(
            "/supervisor"
        ):
            _fail("formal ARMED service_control_group differs from actor lineage")
        for name in (
            "service_device",
            "service_inode",
            "supervisor_device",
            "supervisor_inode",
        ):
            value = identity[name]
            if type(value) is int:
                number = value
            elif type(value) is str and re.fullmatch(r"[1-9][0-9]*", value):
                number = int(value, 10)
            else:
                _fail(f"formal ARMED {name} is not a positive integer")
            if number <= 0:
                _fail(f"formal ARMED {name} is not positive")
    return {
        "receipt": armed,
        "schema": schema,
        "identity": identity,
        "boot_id": boot_id,
        "invocation_id": invocation_id,
        "unit": unit,
    }


def _formal_action_armed(
    action: FormalAction,
    policy: ScenarioPolicy,
    outer_armed: dict[str, Any],
) -> dict[str, Any]:
    if action.armed_receipt_path is None or action.control_fifo is None:
        _fail("formal action lacks ARMED/control authority")
    value = _decode_canonical(action.armed_receipt_path, label="formal action ARMED")
    _exact(value, _FORMAL_ACTION_ARMED_KEYS, label="formal action ARMED")
    if value["schema"] != FORMAL_ACTION_ARMED_SCHEMA:
        _fail("formal action ARMED schema drifted")
    if policy.formal_case is None:
        _fail("non-formal policy attempted a formal action")
    case_id, variant = policy.formal_case
    if (
        value["action_id"] != action.action_id
        or (value["case_id"], value["variant"]) != (case_id, variant)
        or value["unit"] != outer_armed["unit"]
    ):
        _fail("formal action ARMED policy binding drifted")
    expected_fifo = {
        "path": str(action.control_fifo.path),
        "device": str(action.control_fifo.device),
        "inode": str(action.control_fifo.inode),
    }
    if value["control_fifo"] != expected_fifo:
        _fail("formal action ARMED control FIFO differs from manifest")
    expected_permit = (
        b"JOB_CGROUP_KILLED\n"
        if case_id == "B4"
        else b"DRIFT_APPLIED\n"
    )
    if value["expected_permit_sha256"] != hashlib.sha256(expected_permit).hexdigest():
        _fail("formal action expected permit hash drifted")
    outer_receipt = outer_armed["receipt"]
    if (
        value["systemd_armed_receipt_sha256"]
        != hashlib.sha256(_canonical(outer_receipt)).hexdigest()
        or value["plan_sha256"] != outer_receipt["plan_sha256"]
    ):
        _fail("formal action ARMED does not bind the outer formal receipt/plan")
    try:
        from scion.runtime.execution.model import CgroupIdentity, ProcessIdentity

        process = ProcessIdentity.from_mapping(value["process_identity"])
        cgroup_mapping = value["cgroup_identity"]
        if type(cgroup_mapping) is not dict:
            _fail("formal action cgroup identity is not one object")
        cgroup_mapping = dict(cgroup_mapping)
        lineage = cgroup_mapping.get("service_relative_lineage")
        if type(lineage) is not list or any(type(item) is not str for item in lineage):
            _fail("formal action cgroup lineage is not one JSON array of strings")
        cgroup_mapping["service_relative_lineage"] = tuple(lineage)
        cgroup = CgroupIdentity.from_mapping(cgroup_mapping)
    except (ImportError, TypeError, ValueError) as exc:
        raise HarnessError("formal action typed identity is unavailable or invalid") from exc
    outer_identity = outer_armed["identity"]
    if (
        process.creator_pid != outer_identity["pid"]
        or process.creator_starttime_ticks != outer_identity["starttime"]
        or cgroup.service_device != int(outer_identity["service_device"])
        or cgroup.service_inode != int(outer_identity["service_inode"])
        or cgroup.supervisor_device != int(outer_identity["supervisor_device"])
        or cgroup.supervisor_inode != int(outer_identity["supervisor_inode"])
        or cgroup.service_name != outer_armed["unit"]
    ):
        _fail("formal action typed identity differs from outer invocation lineage")
    return {"receipt": value, "process": process, "cgroup": cgroup}


def _b6_armed(
    action: FormalAction,
    policy: ScenarioPolicy,
    outer_armed: dict[str, Any],
) -> dict[str, Any]:
    if action.armed_receipt_path is None or action.operation_receipt_path is None:
        _fail("B6 action lacks its two receipt paths")
    value = _decode_canonical(action.armed_receipt_path, label="B6 ARMED")
    _exact(value, _B6_ARMED_KEYS, label="B6 ARMED")
    if value["schema"] != B6_ARMED_SCHEMA or policy.formal_case is None:
        _fail("B6 ARMED schema/policy drifted")
    variant = policy.formal_case[1]
    abi = _B6_ABI.get(variant)
    if abi is None or variant not in _B6_INSTALLABLE_VARIANTS:
        _fail("B6 ARMED exists for a source-unobservable policy")
    semantic_fields = ("fault", "declared_phase", "hook", "target_operation")
    if (
        any(value[name] != abi[name] for name in semantic_fields)
        or value["planned_ordinal"] != int(abi["planned_ordinal"], 10)
        or policy.formal_completion
        != ("failstop" if abi["expected_fact_type"] == "FAILSTOP" else "typed")
        or policy.formal_expected_fact_type != abi["expected_fact_type"]
    ):
        _fail("B6 ARMED differs from the closed source ABI/policy")
    if (
        (value["case_id"], value["variant"]) != policy.formal_case
        or value["unit"] != outer_armed["unit"]
        or value["operation_receipt_path"] != str(action.operation_receipt_path)
        or value["plan_sha256"] != outer_armed["receipt"]["plan_sha256"]
        or value["systemd_armed_receipt_sha256"]
        != hashlib.sha256(_canonical(outer_armed["receipt"])).hexdigest()
    ):
        _fail("B6 ARMED does not cross-bind policy/outer receipt/operation path")
    identity = value["process_identity"]
    if type(identity) is not dict:
        _fail("B6 ARMED process identity is not one object")
    _exact(identity, _FORMAL_IDENTITY_KEYS, label="B6 ARMED process identity")
    if identity != outer_armed["identity"]:
        _fail("B6 ARMED process identity differs from same-PID outer acquisition")
    ready = FifoIdentity.decode(value["ready_fifo"], label="B6 ready FIFO")
    release = FifoIdentity.decode(value["release_fifo"], label="B6 release FIFO")
    if ready.path == release.path or (ready.device, ready.inode) == (
        release.device,
        release.inode,
    ):
        _fail("B6 ready/release FIFO authorities alias")
    if value["ready_sha256"] != hashlib.sha256(READY_BYTES).hexdigest():
        _fail("B6 ready permit digest drifted")
    if value["release_sha256"] != hashlib.sha256(RELEASE_BYTES).hexdigest():
        _fail("B6 release permit digest drifted")
    return {"receipt": value, "ready": ready, "release": release}


def _b6_operation(
    action: FormalAction,
    policy: ScenarioPolicy,
    armed: dict[str, Any],
) -> dict[str, Any]:
    if action.operation_receipt_path is None:
        _fail("B6 operation receipt path is absent")
    value = _decode_canonical(action.operation_receipt_path, label="B6 operation")
    _exact(value, _B6_OPERATION_KEYS, label="B6 operation")
    if value["schema"] != B6_OPERATION_SCHEMA or policy.formal_case is None:
        _fail("B6 operation schema/policy drifted")
    armed_receipt = armed["receipt"]
    variant = policy.formal_case[1]
    abi = _B6_ABI.get(variant)
    if abi is None or abi["hook"] not in _B6_OPERATION_SEMANTICS:
        _fail("B6 operation exists for a source-unobservable policy")
    semantic_fields = (
        "fault",
        "declared_phase",
        "hook",
        "target_operation",
        "planned_ordinal",
    )
    if (
        (value["case_id"], value["variant"]) != policy.formal_case
        or any(value[name] != armed_receipt[name] for name in semantic_fields)
        or value["armed_receipt_sha256"]
        != hashlib.sha256(_canonical(armed_receipt)).hexdigest()
        or value["planned_ordinal"] != value["observed_ordinal"]
        or value["planned_ordinal"] != armed_receipt["planned_ordinal"]
        or value["injection_count"] != 1
        or value["actor_pid"] != armed_receipt["process_identity"]["pid"]
        or value["actor_starttime"]
        != armed_receipt["process_identity"]["starttime"]
        or value["before_fact_sha256"]
        != hashlib.sha256(_canonical(armed_receipt["before_fact"])).hexdigest()
        or value["release_permit_sha256"] != armed_receipt["release_sha256"]
    ):
        _fail("B6 operation receipt does not prove one exact armed operation")
    if value["operation_state"] not in {
        "RETURNED",
        "RAISED",
        "INJECTED_RETURN",
        "POST_COMMIT_UNCERTAINTY",
    }:
        _fail("B6 operation state is outside the closed vocabulary")
    expected_semantics = _B6_OPERATION_SEMANTICS[abi["hook"]]
    if any(value[name] != expected for name, expected in expected_semantics.items()):
        _fail("B6 operation effect/type/exception tuple differs from its hook")
    return value


def _formal_config_binding(
    policy: ScenarioPolicy,
    outer_armed: dict[str, Any],
    *,
    expected_directory_authorities: dict[str, dict[str, Any]] | None = None,
) -> tuple[Path, dict[str, Any], str, Path]:
    if policy.formal_case is None:
        _fail("non-formal policy attempted to decode a formal config")
    outer_receipt = outer_armed["receipt"]
    config_path = _path(
        outer_receipt["final_config_path"], label="formal final config path"
    )
    config_raw = _read_regular(config_path, label="formal final config")
    config = _decode_canonical(config_path, label="formal final config")
    _exact(config, _FORMAL_CONFIG_KEYS, label="formal final config")
    case_id, variant = policy.formal_case
    if (
        config["schema"] != "scion.generic-backend-formal-case.v2"
        or (config["case_id"], config["variant"]) != (case_id, variant)
        or config["run_unit"] != outer_armed["unit"]
        or config["plan_sha256"] != outer_receipt["plan_sha256"]
        or config["systemd_armed_receipt_sha256"]
        != hashlib.sha256(_canonical(outer_receipt)).hexdigest()
    ):
        _fail("formal final config does not bind its policy/outer acquisition")
    _revalidate_formal_directory_authorities(
        config, expected=expected_directory_authorities
    )
    receipt_directory = _path(
        config["receipt_directory"], label="formal receipt directory"
    )
    receipt_name = _text(config["receipt_name"], label="formal receipt name")
    if Path(receipt_name).name != receipt_name or receipt_name in {".", ".."}:
        _fail("formal receipt name is not one leaf")
    return (
        config_path,
        config,
        hashlib.sha256(config_raw).hexdigest(),
        receipt_directory / receipt_name,
    )


def _formal_binary(value: Any, *, label: str) -> bytes:
    if type(value) is not dict:
        _fail(f"{label} is not one encoded byte string")
    _exact(value, _FORMAL_BINARY_KEYS, label=label)
    try:
        raw = base64.b64decode(value["data"], validate=True)
    except (TypeError, ValueError) as exc:
        raise HarnessError(f"{label} base64 is invalid") from exc
    if (
        value["encoding"] != "base64"
        or type(value["byte_length"]) is not int
        or value["byte_length"] != len(raw)
        or value["sha256"] != hashlib.sha256(raw).hexdigest()
    ):
        _fail(f"{label} byte length/hash binding drifted")
    return raw


def _formal_fact(
    value: Any,
    *,
    label: str,
    expected_type: str,
    expected_phase: str | None = None,
    expected_reason: str | None = None,
) -> dict[str, Any]:
    if type(value) is not dict:
        _fail(f"{label} is not one typed fact")
    _exact(value, _FORMAL_FACT_KEYS, label=label)
    fields = value["fields"]
    if value["fact_type"] != expected_type or type(fields) is not dict:
        _fail(f"{label} type/fields drifted")
    if expected_phase is not None and fields.get("phase") != expected_phase:
        _fail(f"{label} phase drifted")
    if expected_reason is not None and fields.get("reason") != expected_reason:
        _fail(f"{label} reason drifted")
    return fields


def _validate_formal_b5_result(
    result: Any,
    *,
    config: dict[str, Any],
    outer_armed: dict[str, Any],
    formal_actions: list[dict[str, Any]],
) -> dict[str, Any]:
    if type(result) is not dict:
        _fail("formal B5 case_result is not one object")
    _exact(result, _FORMAL_B5_RESULT_KEYS, label="formal B5 case_result")
    _formal_fact(
        result["failure"],
        label="formal B5 failure",
        expected_type="ContainedSpawnFailure",
        expected_reason="DESCENDANT_SURVIVED",
    )
    if len(formal_actions) != 1 or formal_actions[0].get("schema") != (
        "scion.generic_backend.b5_action.v1"
    ):
        _fail("formal B5 lacks its external descendant harness ledger")
    action = formal_actions[0]
    _exact(action, _B5_ACTION_KEYS, label="formal B5 action ledger")
    if (
        action["action_id"] != "b5-never-release-hold"
        or action["case_id"] != "B5"
        or action["variant"] != config["variant"]
        or action.get("control_writer_open_count") != "0"
        or action.get("permit_write_count") != "0"
        or action.get("ownership") != "production-kill-and-drain-only"
    ):
        _fail("formal B5 harness action violated hold ownership")
    external = action["descendant_evidence"]
    if type(external) is not dict:
        _fail("formal B5 action lacks one external descendant evidence object")
    _exact(
        external,
        _B5_DESCENDANT_EVIDENCE_KEYS,
        label="formal B5 external descendant evidence",
    )
    binding = result["descendant_binding"]
    if type(binding) is not dict:
        _fail("formal B5 descendant binding is not one object")
    _exact(
        binding,
        _FORMAL_DESCENDANT_BINDING_KEYS,
        label="formal B5 descendant binding",
    )
    plan_reference = config["descendant_adversary_plan"]
    if type(plan_reference) is not dict or set(plan_reference) != {"path", "sha256"}:
        _fail("formal B5 config lacks one sealed descendant plan")
    for name in ("plan", "request", "receipt"):
        path = _path(binding[f"{name}_path"], label=f"formal B5 {name} path")
        if hashlib.sha256(_read_regular(path, label=f"formal B5 {name}")).hexdigest() != (
            binding[f"{name}_sha256"]
        ):
            _fail(f"formal B5 {name} hash drifted")
    if (
        binding["plan_path"] != plan_reference["path"]
        or binding["plan_sha256"] != plan_reference["sha256"]
    ):
        _fail("formal B5 final binding differs from its config plan")
    if len(formal_actions) != 1:
        _fail("formal B5 action cardinality drifted")
    expected_fifo = config["control_fifo"]
    if type(expected_fifo) is not dict or binding["hold_release_fifo"] != expected_fifo:
        _fail("formal B5 final binding differs from its hold FIFO")
    expected_job_name = binding["expected_job_name"]
    expected_job_cgroup = binding["expected_job_cgroup"]
    service_group = outer_armed["identity"]["service_control_group"]
    if (
        type(expected_job_name) is not str
        or expected_job_cgroup != f"{service_group}/{expected_job_name}"
    ):
        _fail("formal B5 final binding differs from the outer service/job lineage")
    actors = []
    for role in ("actor", "descendant"):
        identity = binding[role]
        if type(identity) is not dict:
            _fail(f"formal B5 {role} identity is not one object")
        _exact(
            identity,
            _FORMAL_DESCENDANT_IDENTITY_KEYS,
            label=f"formal B5 {role} identity",
        )
        if (
            identity["boot_id"] != outer_armed["boot_id"]
            or identity["invocation_id"] != outer_armed["invocation_id"]
            or identity["unified_cgroup"] != expected_job_cgroup
            or identity["proc_cgroup_raw"] != f"0::{expected_job_cgroup}\n"
            or identity["stop_selector_environment"] != {}
            or type(identity["pid"]) is not int
            or identity["pid"] <= 0
            or type(identity["starttime"]) is not int
            or identity["starttime"] <= 0
            or type(identity["session_id"]) is not int
            or identity["session_id"] <= 0
        ):
            _fail(f"formal B5 {role} identity/containment drifted")
        actors.append((identity["pid"], identity["starttime"]))
    if actors[0] == actors[1]:
        _fail("formal B5 descendant aliases its native leader")
    live = external["live_descendant"]
    if type(live) is not dict:
        _fail("formal B5 external live descendant proof is not one object")
    _exact(
        live,
        {"pid", "starttime", "session_id", "proc_cgroup_raw", "unified_cgroup"},
        label="formal B5 external live descendant proof",
    )
    external_pairs = {
        "plan_path": binding["plan_path"],
        "plan_sha256": binding["plan_sha256"],
        "request_path": binding["request_path"],
        "request_sha256": binding["request_sha256"],
        "receipt_path": binding["receipt_path"],
        "receipt_sha256": binding["receipt_sha256"],
        "hold_release_fifo": binding["hold_release_fifo"],
        "expected_job_name": binding["expected_job_name"],
        "expected_job_cgroup": binding["expected_job_cgroup"],
        "actor": binding["actor"],
        "descendant": binding["descendant"],
    }
    if any(external[name] != value for name, value in external_pairs.items()):
        _fail("formal B5 final descendant identity differs from the external ledger")
    external_program = external["program"]
    if type(external_program) is not dict:
        _fail("formal B5 external program proof is not one object")
    _exact(external_program, _PROGRAM_KEYS, label="formal B5 external program")
    program_identity = external_program["identity"]
    if type(program_identity) is not dict:
        _fail("formal B5 external program identity is not one object")
    _exact(
        program_identity,
        _PROGRAM_IDENTITY_KEYS,
        label="formal B5 external program identity",
    )
    external_program_path = _path(
        external_program["path"], label="formal B5 external program path"
    )
    program_info = external_program_path.lstat()
    if (
        external_program["path"] != config["adversary_script"]
        or external_program["sha256"] != config["adversary_sha256"]
        or hashlib.sha256(
            _read_regular(external_program_path, label="formal B5 external program")
        ).hexdigest()
        != external_program["sha256"]
        or program_identity
        != {
            "device": program_info.st_dev,
            "inode": program_info.st_ino,
            "mode": stat.S_IMODE(program_info.st_mode),
        }
        or live
        != {
            "pid": binding["descendant"]["pid"],
            "starttime": binding["descendant"]["starttime"],
            "session_id": binding["descendant"]["session_id"],
            "proc_cgroup_raw": binding["descendant"]["proc_cgroup_raw"],
            "unified_cgroup": binding["descendant"]["unified_cgroup"],
        }
    ):
        _fail("formal B5 external live/program proof differs from the final binding")
    environment = result["transported_environment"]
    if type(environment) is not list:
        _fail("formal B5 transported environment is not one ordered array")
    decoded_environment = tuple(
        _formal_binary(item, label=f"formal B5 environment[{index}]")
        for index, item in enumerate(environment)
    )
    expected_environment = tuple(
        sorted(
            (
                b"INVOCATION_ID=" + outer_armed["invocation_id"].encode("ascii"),
                b"LC_ALL=C",
            )
        )
    )
    process_spec = binding["process_spec"]
    if (
        decoded_environment != expected_environment
        or type(process_spec) is not dict
        or process_spec.get("environment") != environment
        or process_spec.get("spec_sha256") != binding["process_spec_sha256"]
    ):
        _fail("formal B5 environment/process-spec cross-binding drifted")
    return {
        "kind": "B5_DESCENDANT_CONTAINMENT",
        "descendant_receipt_sha256": binding["receipt_sha256"],
        "process_spec_sha256": binding["process_spec_sha256"],
        "expected_job_cgroup": expected_job_cgroup,
        "action_ledger_sha256": hashlib.sha256(_canonical(action)).hexdigest(),
        "external_descendant": live,
    }


def _validate_formal_b6_result(
    result: Any,
    *,
    policy: ScenarioPolicy,
    formal_actions: list[dict[str, Any]],
) -> dict[str, Any]:
    if policy.formal_case is None or type(result) is not dict:
        _fail("formal B6 result lacks its policy/object")
    _exact(result, _FORMAL_B6_RESULT_KEYS, label="formal B6 case_result")
    variant = policy.formal_case[1]
    abi = _B6_ABI[variant]
    _formal_fact(
        result["failure"],
        label="formal B6 failure",
        expected_type=abi["expected_fact_type"],
        expected_phase=abi["expected_phase"],
        expected_reason=abi["expected_reason"],
    )
    if len(formal_actions) != 1 or type(formal_actions[0]) is not dict:
        _fail("typed formal B6 lacks one harness action/operation")
    action_evidence = formal_actions[0]
    if set(action_evidence) != {"action", "operation"}:
        _fail("typed formal B6 action evidence fields drifted")
    operation = action_evidence["operation"]
    action = action_evidence["action"]
    if type(operation) is not dict or type(action) is not dict:
        _fail("typed formal B6 action/operation is not one object")
    ledger = result["fault_ledger"]
    if type(ledger) is not dict:
        _fail("formal B6 final lacks one fault ledger")
    expected_ledger_keys = set(_FORMAL_B6_LEDGER_BASE_KEYS)
    if abi["fault"] == "issuer-signal":
        expected_ledger_keys.add("signal_restore")
    _exact(ledger, expected_ledger_keys, label="formal B6 fault ledger")
    operation_sha256 = hashlib.sha256(_canonical(operation)).hexdigest()
    ordinal = int(abi["planned_ordinal"], 10)
    if (
        ledger["operation_receipt_sha256"] != operation_sha256
        or ledger["armed_receipt_sha256"] != operation["armed_receipt_sha256"]
        or ledger["armed_receipt_sha256"] != action.get("armed_receipt_sha256")
        or ledger["injection_count"] != 1
        or ledger["operation_ordinal"] != ordinal
        or type(ledger["operation_call_count"]) is not int
        or ledger["operation_call_count"] < ordinal
        or operation["before_fact_sha256"]
        != hashlib.sha256(_canonical(ledger["before"])).hexdigest()
        or ledger["after_release"].get("release_sha256")
        != operation["release_permit_sha256"]
    ):
        _fail("formal B6 final ledger does not bind its exact action/operation")
    if abi["fault"] == "issuer-signal" and type(ledger["signal_restore"]) is not dict:
        _fail("formal B6 issuer final lacks signal restoration evidence")
    return {
        "kind": "B6_TYPED_OPERATION",
        "expected_fact_type": abi["expected_fact_type"],
        "operation_receipt_sha256": operation_sha256,
        "operation_ordinal": ordinal,
    }


def _formal_final(
    policy: ScenarioPolicy,
    outer_armed: dict[str, Any],
    formal_actions: list[dict[str, Any]],
    *,
    expected_directory_authorities: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    config_path, config, config_sha256, receipt_path = _formal_config_binding(
        policy,
        outer_armed,
        expected_directory_authorities=expected_directory_authorities,
    )
    if policy.formal_completion == "failstop":
        _fail("fail-stop formal policy cannot publish formal-final")
    receipt_raw = _read_regular(receipt_path, label="formal final receipt")
    receipt = _decode_canonical(receipt_path, label="formal final receipt")
    expected_keys = (
        _FORMAL_REQUIREMENT_RECEIPT_KEYS
        if policy.formal_completion == "requirement-missing"
        else _FORMAL_PASS_RECEIPT_KEYS
    )
    _exact(receipt, expected_keys, label="formal final receipt")
    if policy.formal_case is None:
        _fail("formal final lacks one policy case")
    case_id, variant = policy.formal_case
    fixture_identity = receipt["fixture_identity"]
    if type(fixture_identity) is not dict:
        _fail("formal final fixture identity is not one object")
    _exact(
        fixture_identity,
        _FORMAL_FIXTURE_IDENTITY_KEYS,
        label="formal final fixture identity",
    )
    program = outer_armed["receipt"]["program"]
    if (
        receipt["schema"] != FORMAL_RECEIPT_SCHEMA
        or (receipt["case_id"], receipt["variant"]) != (case_id, variant)
        or fixture_identity["config_sha256"] != config_sha256
        or fixture_identity["case_script"] != program["path"]
        or fixture_identity["case_script_sha256"] != program["sha256"]
        or fixture_identity["accepted_probe_sha256"]
        != config["accepted_probe_sha256"]
        or fixture_identity["native_extension_sha256"]
        != config["accepted_extension_sha256"]
        or fixture_identity["spawn_backend_sha256"]
        != config["accepted_spawn_backend_sha256"]
        or fixture_identity["python_version"][:2] != [3, 12]
        or fixture_identity["isolated"] != 1
        or fixture_identity["dont_write_bytecode"] != 1
    ):
        _fail("formal final identity/config/policy binding drifted")
    case_evidence: dict[str, Any]
    if policy.formal_completion == "requirement-missing":
        if (
            receipt["outcome"] != "REQUIREMENT_MISSING"
            or receipt["config_sha256"] != config_sha256
            or case_id != "B6"
            or variant not in _B6_REQUIREMENT_VARIANTS
            or receipt["requirement_code"] != "B6_EXACT_GUARDED_SEAM"
            or type(receipt["requirement"]) is not str
            or not receipt["requirement"]
            or formal_actions
        ):
            _fail("formal requirement receipt differs from its source-unobservable policy")
        case_evidence = {
            "kind": "REQUIREMENT_MISSING",
            "requirement_code": receipt["requirement_code"],
            "declared_expected_fact_type": policy.formal_expected_fact_type,
        }
    else:
        if receipt["outcome"] != "PASS":
            _fail("typed formal policy did not publish PASS")
        if case_id == "B5":
            case_evidence = _validate_formal_b5_result(
                receipt["case_result"],
                config=config,
                outer_armed=outer_armed,
                formal_actions=formal_actions,
            )
        elif case_id == "B6":
            case_evidence = _validate_formal_b6_result(
                receipt["case_result"],
                policy=policy,
                formal_actions=formal_actions,
            )
        else:
            if type(receipt["case_result"]) is not dict:
                _fail("formal typed case_result is not one object")
            case_evidence = {"kind": "TYPED_PASS"}
    return {
        "schema": FORMAL_RECEIPT_SCHEMA,
        "case_id": case_id,
        "variant": variant,
        "outcome": receipt["outcome"],
        "config_path": str(config_path),
        "config_sha256": config_sha256,
        "receipt_path": str(receipt_path),
        "receipt_sha256": hashlib.sha256(receipt_raw).hexdigest(),
        "case_evidence": case_evidence,
    }


def _open_cgroup_from_manager(control_group: str) -> tuple[int, dict[str, str]]:
    if not control_group.startswith("/") or control_group == "/":
        _fail("manager ControlGroup is not one non-root absolute lineage")
    components = control_group.split("/")[1:]
    if any(not component or component in {".", ".."} for component in components):
        _fail("manager ControlGroup is not canonical")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    descriptor = os.open("/sys/fs/cgroup", flags)
    try:
        for component in components:
            child = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        info = os.fstat(descriptor)
        return descriptor, {
            "path": control_group,
            "device": str(info.st_dev),
            "inode": str(info.st_ino),
        }
    except BaseException:
        os.close(descriptor)
        raise


@dataclass
class CgroupPin:
    unit: str
    invocation_id: str
    control_group: str
    service_fd: int
    service_identity: dict[str, str]
    supervisor_fd: int | None = None
    supervisor_identity: dict[str, str] | None = None

    def close(self) -> None:
        if self.supervisor_fd is not None:
            os.close(self.supervisor_fd)
            self.supervisor_fd = None
        os.close(self.service_fd)


def _read_cgroup_procs(directory_fd: int) -> tuple[int, ...]:
    descriptor = os.open(
        "cgroup.procs",
        os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
        dir_fd=directory_fd,
    )
    try:
        raw = _read_all(descriptor)
    finally:
        os.close(descriptor)
    try:
        text = raw.decode("ascii", "strict")
    except UnicodeError as exc:
        raise HarnessError("cgroup.procs is not ASCII") from exc
    values: list[int] = []
    for line in text.splitlines():
        if re.fullmatch(r"[1-9][0-9]*", line) is None:
            _fail("cgroup.procs contains a noncanonical PID")
        values.append(int(line, 10))
    if len(values) != len(set(values)):
        _fail("cgroup.procs contains a duplicate PID")
    return tuple(sorted(values))


def _read_proc_starttime(pid: int) -> int | None:
    """Read one current process identity snapshot without polling or signalling."""

    path = Path(f"/proc/{pid}/stat")
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise HarnessError(f"cannot open process stat for PID {pid}") from exc
    try:
        raw = _read_all(descriptor)
    finally:
        os.close(descriptor)
    try:
        text = raw.decode("ascii", "strict")
    except UnicodeError as exc:
        raise HarnessError(f"process stat for PID {pid} is not ASCII") from exc
    if text.endswith("\n"):
        text = text[:-1]
    if "\n" in text or not text.startswith(f"{pid} ("):
        _fail(f"process stat for PID {pid} is not one exact record")
    close = text.rfind(")")
    if close < len(str(pid)) + 2 or close + 2 >= len(text) or text[close + 1] != " ":
        _fail(f"process stat for PID {pid} has no canonical command boundary")
    fields = text[close + 2 :].split(" ")
    if len(fields) < 20 or any(field == "" for field in fields):
        _fail(f"process stat for PID {pid} lacks its starttime field")
    starttime = _decimal(fields[19], label=f"process {pid} starttime")
    if starttime == 0:
        _fail(f"process stat for PID {pid} has zero starttime")
    return starttime


def _read_proc_cgroup(pid: int) -> tuple[str, str] | None:
    """Read one current unified cgroup record without polling or inference."""

    path = Path(f"/proc/{pid}/cgroup")
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise HarnessError(f"cannot open process cgroup for PID {pid}") from exc
    try:
        raw = _read_all(descriptor)
    finally:
        os.close(descriptor)
    try:
        text = raw.decode("ascii", "strict")
    except UnicodeError as exc:
        raise HarnessError(f"process cgroup for PID {pid} is not ASCII") from exc
    lines = text.splitlines()
    if len(lines) != 1 or not lines[0].startswith("0::"):
        _fail(f"process cgroup for PID {pid} is not one unified record")
    lineage = lines[0][3:]
    if (
        not lineage.startswith("/")
        or "//" in lineage
        or any(part in {"", ".", ".."} for part in lineage.split("/")[1:])
        or text != f"0::{lineage}\n"
    ):
        _fail(f"process cgroup for PID {pid} is not canonical")
    return text, lineage


def _prove_actor_absence(
    frozen_identities: list[dict[str, Any]],
    reader: Callable[[int], int | None],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for frozen in frozen_identities:
        identity = frozen["identity"]
        observed_starttime = reader(identity["pid"])
        if observed_starttime == identity["starttime"]:
            _fail("UnitRemoved left one acquisition actor with the exact PID/starttime alive")
        records.append(
            {
                **frozen,
                "observed_starttime": observed_starttime,
                "absence_proof": (
                    "proc-entry-absent"
                    if observed_starttime is None
                    else "pid-reused-with-different-starttime"
                ),
            }
        )
    return records


def _open_child_cgroup(parent_fd: int, name: str) -> tuple[int, dict[str, str]]:
    descriptor = os.open(
        name,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
        dir_fd=parent_fd,
    )
    info = os.fstat(descriptor)
    return descriptor, {"device": str(info.st_dev), "inode": str(info.st_ino)}


def _recursive_cgroup_inventory(
    directory_fd: int,
    *,
    relative: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    """Freeze every cgroup directory below one retained authority FD."""

    info = os.fstat(directory_fd)

    def optional_file(name: str) -> dict[str, Any] | None:
        try:
            descriptor = os.open(
                name,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=directory_fd,
            )
        except FileNotFoundError:
            return None
        try:
            raw = _read_all(descriptor)
            file_info = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        return {
            "device": str(file_info.st_dev),
            "inode": str(file_info.st_ino),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "text": raw.decode("ascii", "strict"),
        }

    rows = [
        {
            "relative_path": "/".join(relative) if relative else ".",
            "device": str(info.st_dev),
            "inode": str(info.st_ino),
            "events": optional_file("cgroup.events"),
            "procs": optional_file("cgroup.procs"),
        }
    ]
    for name in sorted(os.listdir(directory_fd)):
        child_info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if not stat.S_ISDIR(child_info.st_mode):
            continue
        child_fd = os.open(
            name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=directory_fd,
        )
        try:
            rows.extend(
                _recursive_cgroup_inventory(child_fd, relative=relative + (name,))
            )
        finally:
            os.close(child_fd)
    return rows


@dataclass
class FormalSystemHarness:
    manifest: HarnessManifest
    manager: ManagerTransport
    journal: JournalTransport
    require_root: bool = True
    prevalidated_authority: dict[str, Any] | None = None
    proc_starttime_reader: Callable[[int], int | None] = _read_proc_starttime
    proc_cgroup_reader: Callable[[int], tuple[str, str] | None] = _read_proc_cgroup
    signals: list[ManagerSignal] = field(default_factory=list)
    call_ledger: list[dict[str, Any]] = field(default_factory=list)
    manager_events: list[dict[str, Any]] = field(default_factory=list)
    _start_count: int = 0
    _stop_count: int = 0
    _load_count: int = 0
    _ref_units: set[str] = field(default_factory=set)
    _owned_job_paths: set[str] = field(default_factory=set)
    _cgroup_pins: dict[str, CgroupPin] = field(default_factory=dict)
    _source_binding: dict[str, Any] | None = None
    _h8_applied: bool = False
    _actor_identities: list[dict[str, Any]] = field(default_factory=list)
    _formal_outer_armed: dict[str, Any] | None = None
    _formal_action_evidence: list[dict[str, Any]] = field(default_factory=list)
    _event_ordinal: int = 0
    _state: str = "PREVALIDATED"
    _installer_authority: dict[str, Any] | None = None

    def _installer_identity(self) -> tuple[str, str]:
        authority = self._installer_authority
        if authority is None:
            _fail("installer authority was not validated before H0")
        receipt = authority["receipt"]
        if receipt["manager_owner"] != self.manager.owner:
            _fail("root installer manager owner differs from harness manager owner")
        return authority["fixture_user"], authority["fixture_group"]

    def _record_signal(self, signal: ManagerSignal) -> None:
        if signal.member not in _SIGNAL_SIGNATURES:
            _fail("manager emitted a signal outside the closed allowlist")
        if signal.signature != _SIGNAL_SIGNATURES[signal.member]:
            _fail("manager signal signature drifted")
        if signal.sender != self.manager.owner:
            _fail("manager signal unique owner drifted")
        if signal.ordinal != len(self.signals) + 1:
            _fail("manager transport signal ordinal is not contiguous")
        if signal.member == "PropertiesChanged":
            if (
                self._installer_authority is None
                or signal.object_path
                not in self._installer_authority["objects"].values()
            ):
                _fail("PropertiesChanged did not originate from an installer unit object")
        elif signal.object_path != MANAGER_PATH:
            _fail("manager signal object path drifted")
        decoded_body = _signal_body(signal.signature, signal.body)
        if signal.member in {"UnitNew", "UnitRemoved"}:
            unit_name, unit_object = signal.body
            if (
                self._installer_authority is None
                or type(unit_name) is not str
                or type(unit_object) is not str
                or self._installer_authority["objects"].get(unit_name)
                != unit_object
            ):
                _fail("manager unit signal differs from exact installer object mapping")
        self.signals.append(signal)
        ordinal = self._next_event_ordinal()
        self.manager_events.append(
            {
                "kind": "signal",
                "ordinal": str(ordinal),
                "member": signal.member,
                "signature": signal.signature,
                "body": _signal_body(signal.signature, signal.body),
                "object_path": signal.object_path,
                "sender": signal.sender,
            }
        )

    def _next_event_ordinal(self) -> int:
        self._event_ordinal += 1
        return self._event_ordinal

    def _manager_method(
        self,
        method: str,
        signature: str,
        arguments: list[str],
        invoke: Callable[[], Any],
    ) -> Any:
        if _MANAGER_METHOD_SIGNATURES.get(method) != signature:
            _fail("manager method/signature is outside the exact allowlist")
        if method not in self.manifest.policy.allowed_methods:
            _fail("manager method is forbidden by ScenarioPolicy")
        begin = self._next_event_ordinal()
        event: dict[str, Any] = {
            "kind": "method",
            "method": method,
            "signature": signature,
            "arguments": arguments,
            "destination_owner": self.manager.owner,
            "begin_ordinal": str(begin),
        }
        self.manager_events.append(event)
        try:
            result = invoke()
        except BaseException as exc:
            event["reply_ordinal"] = str(self._next_event_ordinal())
            event["error"] = {
                "type": type(exc).__name__,
                "name": str(getattr(exc, "get_dbus_name", lambda: "")()),
            }
            self.call_ledger.append(dict(event))
            raise
        event["reply_ordinal"] = str(self._next_event_ordinal())
        event["reply"] = None if result is None else str(result)
        self.call_ledger.append(dict(event))
        return result

    def _transition(self, expected: str, target: str) -> None:
        if self._state != expected:
            _fail(f"harness transition {self._state!r} cannot enter {target!r}")
        self._state = target

    def _manager_event_receipt(self) -> dict[str, Any]:
        ordinals: list[int] = []
        for event in self.manager_events:
            if event["kind"] == "signal":
                ordinals.append(int(event["ordinal"]))
            else:
                ordinals.extend(
                    (int(event["begin_ordinal"]), int(event["reply_ordinal"]))
                )
        if sorted(ordinals) != list(range(1, self._event_ordinal + 1)):
            _fail("manager method/signal ordinal space is not exact and contiguous")
        return {
            "schema": MANAGER_EVENT_SCHEMA,
            "manager_owner": self.manager.owner,
            "event_count": str(self._event_ordinal),
            "events": self.manager_events,
        }

    def _final_freeze_policy(self) -> dict[str, Any]:
        roles = tuple(sorted(self.manifest.policy.required_outputs - {"final"}))
        return {
            "policy_id": self.manifest.policy.scenario_id,
            "output_roles": ["install-receipt", *roles, "harness-final"],
        }

    def _installer_unit_objects(self) -> dict[str, str]:
        if self._installer_authority is None:
            _fail("installer unit objects were not prevalidated")
        return dict(self._installer_authority["objects"])

    def _h7_event_evidence(self, stop_job: str) -> dict[str, Any]:
        methods = [
            event
            for event in self.manager_events
            if event["kind"] == "method" and event["method"] == "StopUnit"
        ]
        if len(methods) != 1 or methods[0].get("reply") != stop_job:
            _fail("H7 lacks one exact StopUnit reply job")
        method = methods[0]
        signal_events = [
            (signal, event)
            for signal, event in zip(
                self.signals,
                [item for item in self.manager_events if item["kind"] == "signal"],
            )
        ]
        job_new = [
            (signal, event)
            for signal, event in signal_events
            if signal.member == "JobNew"
            and signal.body[1] == stop_job
            and signal.body[2] == self.manifest.run_unit
        ]
        job_removed = [
            (signal, event)
            for signal, event in signal_events
            if signal.member == "JobRemoved"
            and signal.body[1] == stop_job
            and signal.body[2] == self.manifest.run_unit
        ]
        if len(job_new) != 1 or len(job_removed) != 1:
            _fail("H7 StopUnit job is not bound to exactly one JobNew/JobRemoved")
        new_signal, new_event = job_new[0]
        removed_signal, removed_event = job_removed[0]
        if (
            new_signal.body[0] != removed_signal.body[0]
            or removed_signal.body[3] != "done"
            or not (
                int(method["begin_ordinal"])
                < int(new_event["ordinal"])
                < int(method["reply_ordinal"])
                < int(removed_event["ordinal"])
            )
        ):
            _fail("H7 StopUnit reply/signals lack exact numeric/path/result ordering")
        return {
            "stop_job": stop_job,
            "job_id": str(new_signal.body[0]),
            "method_begin_ordinal": method["begin_ordinal"],
            "job_new_ordinal": new_event["ordinal"],
            "method_reply_ordinal": method["reply_ordinal"],
            "job_removed_ordinal": removed_event["ordinal"],
            "job_removed_result": removed_signal.body[3],
            "run_release_writer_open_count": "0",
        }

    def _preflight(self) -> dict[str, Any]:
        if self.require_root and os.geteuid() != 0:
            _fail("system-manager formal harness requires root; it does not invoke sudo")
        if self.require_root and Path(sys.executable).resolve() != Path("/usr/bin/python3.12"):
            _fail("formal harness must run under frozen /usr/bin/python3.12")
        socket_receipt: dict[str, str] | None
        journal_socket = Path(JOURNAL_SOCKET)
        if self.require_root:
            info = journal_socket.lstat()
            if not stat.S_ISSOCK(info.st_mode):
                _fail("journal Varlink authority is not a socket")
            socket_receipt = {
                "path": JOURNAL_SOCKET,
                "device": str(info.st_dev),
                "inode": str(info.st_ino),
                "uid": str(info.st_uid),
                "gid": str(info.st_gid),
                "mode": format(stat.S_IMODE(info.st_mode), "04o"),
            }
        else:
            socket_receipt = None
        executable = Path(sys.executable).resolve()
        fixture_user, fixture_group = self._installer_identity()
        version = str(
            self.manager.property(MANAGER_PATH, MANAGER_INTERFACE, "Version")
        )
        if re.match(r"255(?:\D|$)", version) is None:
            _fail("system manager is not exact major version 255")

        def host_file(path: Path, label: str) -> tuple[bytes, dict[str, str]]:
            try:
                descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
                before = os.fstat(descriptor)
                raw = _read_all(descriptor)
                after = os.fstat(descriptor)
            except OSError as exc:
                raise HarnessError(f"cannot pin H0 host file {label}") from exc
            finally:
                if "descriptor" in locals():
                    os.close(descriptor)
            if (
                not stat.S_ISREG(before.st_mode)
                or (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino)
            ):
                _fail(f"H0 host file {label} identity drifted while read")
            info = before
            return raw, {
                "path": str(path),
                "device": str(info.st_dev),
                "inode": str(info.st_ino),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }

        mountinfo_raw, mountinfo = host_file(Path("/proc/self/mountinfo"), "mountinfo")
        mount_rows = []
        for raw_line in mountinfo_raw.decode("utf-8", "strict").splitlines():
            left, separator, right = raw_line.partition(" - ")
            if not separator:
                _fail("mountinfo line lacks filesystem separator")
            left_fields = left.split(" ")
            right_fields = right.split(" ")
            if len(left_fields) < 6 or len(right_fields) < 3:
                _fail("mountinfo line has invalid field arity")
            if right_fields[0] == "cgroup2" and left_fields[4] == "/sys/fs/cgroup":
                mount_rows.append(raw_line)
        if len(mount_rows) != 1:
            _fail("host does not expose one cgroup2 mount at /sys/fs/cgroup")
        cgroup_raw, cgroup_file = host_file(Path("/proc/self/cgroup"), "self cgroup")
        unified = cgroup_raw.decode("ascii", "strict").splitlines()
        if len(unified) != 1 or not unified[0].startswith("0::/"):
            _fail("harness process lacks one unified cgroup-v2 entry")
        controllers_raw, controllers = host_file(
            Path("/sys/fs/cgroup/cgroup.controllers"), "cgroup controllers"
        )
        controller_names = controllers_raw.decode("ascii", "strict").split()
        if "pids" not in controller_names:
            _fail("cgroup-v2 hierarchy lacks the pids controller")

        run_object = str(
            self._manager_method(
                "GetUnit",
                "s",
                [self.manifest.run_unit],
                lambda: self.manager.get_unit(self.manifest.run_unit),
            )
        )
        configured_delegate = bool(
            self.manager.property(run_object, SERVICE_INTERFACE, "Delegate")
        )
        configured_subgroup = str(
            self.manager.property(run_object, SERVICE_INTERFACE, "DelegateSubgroup")
        )
        if self.manifest.scenario != "H10" and (
            configured_delegate is not True or configured_subgroup != "supervisor"
        ):
            _fail("pre-start run unit lacks exact pids delegation/subgroup configuration")
        if self.require_root:
            if self._installer_authority is None:
                _fail("H0 lacks its validated installer authority")
            fixture_uid = self._installer_authority["fixture_uid"]
            fixture_gid = self._installer_authority["fixture_gid"]
            for acquisition in self.manifest.acquisitions:
                for fifo in (acquisition.ready_fifo, acquisition.release_fifo):
                    info = fifo.path.lstat()
                    if (
                        not stat.S_ISFIFO(info.st_mode)
                        or info.st_uid != fixture_uid
                        or info.st_gid != fixture_gid
                        or stat.S_IMODE(info.st_mode) != 0o600
                    ):
                        _fail("acquisition FIFO ownership/mode drifted")
        return {
            "schema": "scion.generic_backend.systemd_h0.v1",
            "execution_manifest_source": (
                None
                if self._installer_authority is None
                else self._installer_authority["execution_manifest_source"]
            ),
            "system_manager_owner": self.manager.owner,
            "system_manager_version": version,
            "python_path": str(executable),
            "python_sha256": hashlib.sha256(
                _read_regular(executable, label="host Python")
            ).hexdigest(),
            "harness_program": {
                "path": str(self.manifest.harness_program.path),
                "sha256": self.manifest.harness_program.sha256,
            },
            "installer_receipt": {
                "path": str(self.manifest.installer_receipt.path),
                "sha256": self.manifest.installer_receipt.sha256,
            },
            "fixture_user": fixture_user,
            "fixture_group": fixture_group,
            "dbus_binding": getattr(self.manager, "binding_receipt", None),
            "journal_binding": self.journal.binding_receipt,
            "journal_socket": socket_receipt,
            "host": {
                "mountinfo": mountinfo,
                "cgroup": cgroup_file,
                "controllers": controllers,
                "cgroup2_mount": mount_rows[0],
                "unified_entry": unified[0],
                "controller_names": controller_names,
            },
            "pre_start_run": {
                "object_path": run_object,
                "delegate": configured_delegate,
                "delegate_subgroup": configured_subgroup,
            },
        }

    def _query_for_acquisition(
        self, acquisition: Acquisition, armed: dict[str, Any], boot_id: str
    ) -> dict[str, Any]:
        unit = armed["unit"]
        if unit not in {self.manifest.run_unit, self.manifest.closer_unit}:
            _fail("ARMED receipt unit is outside this concrete pair")
        if unit == self.manifest.run_unit:
            peer = self.manifest.closer_unit
        else:
            peer = self.manifest.run_unit
        authority_output = self.manifest.output(f"{acquisition.role}-properties")
        if armed["schema"] == "scion.generic_backend.systemd_observer_armed.v1":
            if armed["receipt"]["raw_authority_paths"] != [str(authority_output)]:
                _fail(
                    "observer ARMED raw authority does not equal the role's manifest output"
                )
        object_path = str(
            self._manager_method(
                "GetUnit", "s", [unit], lambda: self.manager.get_unit(unit)
            )
        )
        receipt = query_unit_properties(
            self.manager,
            unit=unit,
            peer_unit=peer,
            boot_id=boot_id,
            receipt_path=authority_output,
            publish=False,
            object_path=object_path,
        )
        if armed["boot_id"] != boot_id:
            _fail("ARMED boot ID differs from pinned kernel boot ID")
        if receipt["invocation_id"] != armed["invocation_id"]:
            _fail("D-Bus InvocationID does not match ARMED actor")
        expected_user, expected_group = self._installer_identity()
        if (
            _encoded_text(receipt, SERVICE_INTERFACE, "User") != expected_user
            or _encoded_text(receipt, SERVICE_INTERFACE, "Group") != expected_group
        ):
            _fail("expanded User/Group differs from root installer identity")
        configured_status = receipt["normalization"]["configured"].get("status")
        if self.manifest.scenario.startswith("H10"):
            if configured_status != "rejected-negative-control":
                _fail("H10 was not labelled as exact rejected configured control")
        elif configured_status != "accepted":
            _fail("configured properties did not pass systemd255 normalization")
        receipt["normalization"]["lineage"] = self._pin_and_decode_lineage(
            acquisition, armed, receipt, boot_id
        )
        if acquisition.role in {"exec-stop-post", "h4-stop-post"}:
            receipt["normalization"]["stop_post"] = self._decode_stop_post(
                armed, receipt
            )
        _write_no_replace(
            authority_output, receipt
        )
        return receipt

    def _pin_and_decode_lineage(
        self,
        acquisition: Acquisition,
        armed: dict[str, Any],
        receipt: dict[str, Any],
        boot_id: str,
    ) -> dict[str, Any]:
        unit = armed["unit"]
        invocation_id = armed["invocation_id"]
        control_group = _encoded_text(receipt, SERVICE_INTERFACE, "ControlGroup")
        actor_group = armed["identity"]["unified_cgroup"]
        if not (actor_group == control_group or actor_group.startswith(control_group + "/")):
            _fail("ARMED actor is outside exact manager ControlGroup")
        pin = self._cgroup_pins.get(unit)
        if pin is None:
            service_fd, service_identity = _open_cgroup_from_manager(control_group)
            pin = CgroupPin(
                unit=unit,
                invocation_id=invocation_id,
                control_group=control_group,
                service_fd=service_fd,
                service_identity=service_identity,
            )
            self._cgroup_pins[unit] = pin
        elif pin.invocation_id != invocation_id or pin.control_group != control_group:
            _fail("unit cgroup pin was reused across invocation/lineage drift")
        else:
            info = os.fstat(pin.service_fd)
            if (info.st_dev, info.st_ino) != (
                int(pin.service_identity["device"]),
                int(pin.service_identity["inode"]),
            ):
                _fail("early service cgroup pin identity drifted")

        if acquisition.role != "run-main":
            return {
                "status": "actor-contained-by-early-pin",
                "control_group": control_group,
                "service_device": pin.service_identity["device"],
                "service_inode": pin.service_identity["inode"],
            }
        main_pid = _encoded_integer(receipt, SERVICE_INTERFACE, "MainPID")
        actor_pid = armed["identity"]["pid"]
        if main_pid != actor_pid:
            _fail("raw MainPID differs from run-main ARMED PID")
        if self.manifest.scenario.startswith("H10"):
            if actor_group != control_group:
                _fail("H10 non-delegated actor must equal exact manager ControlGroup")
            return {
                "status": "rejected-negative-control",
                "reason": "H10 has no DelegateSubgroup and cannot claim positive InvocationLineage",
                "unit": unit,
                "invocation_id": invocation_id,
                "control_group": control_group,
                "service_device": pin.service_identity["device"],
                "service_inode": pin.service_identity["inode"],
                "main_pid": str(main_pid),
                "main_starttime": str(armed["identity"]["starttime"]),
            }
        if actor_group != control_group + "/supervisor":
            _fail("run-main actor is not in exact delegated supervisor subgroup")
        if pin.supervisor_fd is None:
            supervisor_fd, supervisor_identity = _open_child_cgroup(
                pin.service_fd, "supervisor"
            )
            pin.supervisor_fd = supervisor_fd
            pin.supervisor_identity = supervisor_identity
        assert pin.supervisor_identity is not None
        if armed["schema"] == FORMAL_ARMED_SCHEMA:
            formal_identity = armed["identity"]
            expected_formal = {
                "service_control_group": control_group,
                "service_device": int(pin.service_identity["device"]),
                "service_inode": int(pin.service_identity["inode"]),
                "supervisor_device": int(pin.supervisor_identity["device"]),
                "supervisor_inode": int(pin.supervisor_identity["inode"]),
            }
            for name, expected in expected_formal.items():
                observed = formal_identity[name]
                if name == "service_control_group":
                    if observed != expected:
                        _fail("formal ARMED service cgroup differs from manager lineage")
                elif int(observed) != expected:
                    _fail(f"formal ARMED {name} differs from pinned manager identity")
        try:
            from scion.runtime.execution.systemd255 import (  # type: ignore[import-not-found]
                InvocationLineage,
            )
        except ImportError as exc:
            raise HarnessError("accepted InvocationLineage decoder is unavailable") from exc
        decoded = InvocationLineage.from_properties(
            {
                "BootID": boot_id,
                "Id": unit,
                "InvocationID": invocation_id,
                "ControlGroup": control_group,
                "ServiceDevice": pin.service_identity["device"],
                "ServiceInode": pin.service_identity["inode"],
                "SupervisorDevice": pin.supervisor_identity["device"],
                "SupervisorInode": pin.supervisor_identity["inode"],
                "MainPID": str(main_pid),
                "MainStartTime": str(armed["identity"]["starttime"]),
            }
        )
        return {
            "status": "accepted",
            "decoder": "InvocationLineage",
            "unit": decoded.unit,
            "invocation_id": decoded.invocation_id,
            "service_device": str(decoded.service_device),
            "service_inode": str(decoded.service_inode),
            "supervisor_device": str(decoded.supervisor_device),
            "supervisor_inode": str(decoded.supervisor_inode),
            "main_pid": str(decoded.main_pid),
            "main_starttime": str(decoded.main_starttime),
        }

    def _decode_stop_post(
        self, armed: dict[str, Any], receipt: dict[str, Any]
    ) -> dict[str, Any]:
        pin = self._cgroup_pins[armed["unit"]]
        actor = armed["identity"]
        control_lineage = pin.control_group + "/.control"
        if actor["unified_cgroup"] != control_lineage:
            _fail("stop-post actor is not in exact .control cgroup")
        environment = actor.get("stop_selector_environment")
        if environment is not None:
            if type(environment) is not dict or set(environment) != {
                "SERVICE_RESULT",
                "EXIT_CODE",
                "EXIT_STATUS",
            }:
                _fail("H4 stop selector environment does not have exact keys")
            environment = {"INVOCATION_ID": armed["invocation_id"], **environment}
        else:
            environment = armed["receipt"].get("stop_post_environment")
        if type(environment) is not dict:
            _fail("stop-post ARMED receipt lacks literal selector environment")
        try:
            from scion.runtime.execution.systemd255 import (  # type: ignore[import-not-found]
                StopPostEnvironment,
            )
        except ImportError as exc:
            raise HarnessError("accepted stop-post environment decoder is unavailable") from exc
        decoded_environment = StopPostEnvironment.from_environment(environment)
        if decoded_environment.invocation_id != armed["invocation_id"]:
            _fail("stop-post environment invocation differs from ARMED invocation")
        observed_stop = (
            decoded_environment.service_result,
            decoded_environment.exit_code,
            decoded_environment.exit_status,
        )
        if observed_stop != self.manifest.policy.terminal.stop:
            _fail("stop-post terminal environment differs from ScenarioPolicy")

        if not self.manifest.policy.terminal.accept_stop_topology:
            if self.manifest.scenario != "H8" or self.manifest.scenario_input is None:
                _fail("negative stop topology is reserved for exact H8")
            ledger = _decode_canonical(
                Path(self.manifest.scenario_input["ledger_path"]), label="H8 drift ledger"
            )
            inventory = _recursive_cgroup_inventory(pin.service_fd)
            drift_name = self.manifest.scenario_input["drift_name"]
            matches = [row for row in inventory if row["relative_path"] == drift_name]
            if len(matches) != 1 or (
                matches[0]["device"], matches[0]["inode"]
            ) != (ledger["child_device"], ledger["child_inode"]):
                _fail("H8 recursive inventory does not contain the exact drift inode")
            os.rmdir(drift_name, dir_fd=pin.service_fd)
            if drift_name in os.listdir(pin.service_fd):
                _fail("H8 fixture-owned drift cgroup leaked after negative freeze")
            negative = {
                "schema": "scion.generic_backend.systemd_h8_inventory.v1",
                "classification": "formal-negative-evidence/H8_EXTRA_TOPOLOGY",
                "service_control_group": pin.control_group,
                "drift_name": drift_name,
                "drift_device": ledger["child_device"],
                "drift_inode": ledger["child_inode"],
                "inventory": inventory,
                "positive_stop_topology_decoder_called": False,
                "fixture_drift_removed": True,
            }
            _write_no_replace(self.manifest.output("h8-inventory"), negative)
            return negative

        try:
            from scion.runtime.execution.systemd255 import (  # type: ignore[import-not-found]
                StopPostTopology,
            )
        except ImportError as exc:
            raise HarnessError("accepted stop-post topology decoder is unavailable") from exc

        control_fd, _ = _open_child_cgroup(pin.service_fd, ".control")
        try:
            control_pids = _read_cgroup_procs(control_fd)
        finally:
            os.close(control_fd)
        if pin.supervisor_fd is None:
            supervisor_fd, supervisor_identity = _open_child_cgroup(
                pin.service_fd, "supervisor"
            )
            pin.supervisor_fd = supervisor_fd
            pin.supervisor_identity = supervisor_identity
        supervisor_pids = _read_cgroup_procs(pin.supervisor_fd)
        job_names: list[str] = []
        job_pids: list[int] = []
        for name in sorted(os.listdir(pin.service_fd)):
            if re.fullmatch(r"job-(?:0|[1-9][0-9]*)-[0-9a-f]{16}", name) is None:
                continue
            job_fd, _ = _open_child_cgroup(pin.service_fd, name)
            try:
                job_names.append(name)
                job_pids.extend(_read_cgroup_procs(job_fd))
            finally:
                os.close(job_fd)
        topology = StopPostTopology.from_mapping(
            {
                "ServiceControlGroup": pin.control_group,
                "ControlGroup": control_lineage,
                "SealerPID": str(actor["pid"]),
                "SealerStartTime": str(actor["starttime"]),
                "ControlPIDs": " ".join(str(pid) for pid in control_pids),
                "SupervisorPIDs": " ".join(str(pid) for pid in supervisor_pids),
                "JobCgroups": " ".join(job_names),
                "JobPIDs": " ".join(str(pid) for pid in sorted(job_pids)),
            }
        )
        return {
            "status": "accepted",
            "environment_decoder": "StopPostEnvironment",
            "topology_decoder": "StopPostTopology",
            "service_control_group": topology.service_control_group,
            "control_group": topology.control_group,
            "sealer_pid": str(topology.sealer_pid),
            "sealer_starttime": str(topology.sealer_starttime),
            "control_pids": [str(pid) for pid in topology.control_pids],
            "supervisor_pids": [str(pid) for pid in topology.supervisor_pids],
            "job_cgroups": list(topology.job_cgroups),
            "job_pids": [str(pid) for pid in topology.job_pids],
        }

    def _h8_drift(self, query: dict[str, Any], armed: dict[str, Any]) -> None:
        scenario_input = self.manifest.scenario_input
        if scenario_input is None:
            _fail("H8 lost its scenario input")
        control_group = _encoded_text(query, SERVICE_INTERFACE, "ControlGroup")
        actor_group = armed["identity"].get("unified_cgroup")
        if type(actor_group) is not str or not (
            actor_group == control_group or actor_group.startswith(control_group + "/")
        ):
            _fail("H8 ARMED actor is outside manager ControlGroup")
        pin = self._cgroup_pins.get(armed["unit"])
        if pin is None or pin.control_group != control_group:
            _fail("H8 lacks the early manager-bound cgroup pin")
        descriptor = pin.service_fd
        parent_identity = pin.service_identity
        drift_name = scenario_input["drift_name"]
        before_names = sorted(os.listdir(descriptor))
        os.mkdir(drift_name, mode=0o755, dir_fd=descriptor)
        child = os.open(
            drift_name,
            os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=descriptor,
        )
        try:
            child_info = os.fstat(child)
        finally:
            os.close(child)
        after_names = sorted(os.listdir(descriptor))
        if drift_name in before_names or drift_name not in after_names:
            _fail("H8 dirfd-relative cgroup drift did not become visible")
        ledger = {
            "schema": "scion.generic_backend.systemd_h8_dirfd_ledger.v1",
            "parent": parent_identity,
            "drift_name": drift_name,
            "before_names": before_names,
            "after_names": after_names,
            "child_device": str(child_info.st_dev),
            "child_inode": str(child_info.st_ino),
            "mkdir_relative_to_pinned_dirfd": True,
            "replacement_cleanup": False,
        }
        _write_no_replace(Path(scenario_input["ledger_path"]), ledger)

    @staticmethod
    def _write_descriptor(descriptor: int, raw: bytes, *, label: str) -> None:
        view = memoryview(raw)
        while view:
            count = os.write(descriptor, view)
            if count <= 0:
                _fail(f"{label} write made no progress")
            view = view[count:]

    def _pin_formal_job(
        self, action_armed: dict[str, Any]
    ) -> tuple[int, dict[str, Any]]:
        cgroup = action_armed["cgroup"]
        service = self._cgroup_pins.get(self.manifest.run_unit)
        if service is None:
            _fail("formal action lacks its outer service cgroup pin")
        job_fd, identity = _open_child_cgroup(service.service_fd, cgroup.job_name)
        if (int(identity["device"]), int(identity["inode"])) != (
            cgroup.job_device,
            cgroup.job_inode,
        ):
            os.close(job_fd)
            _fail("formal action job cgroup differs from BlockedSpawn identity")
        return job_fd, {
            "job_name": cgroup.job_name,
            "device": identity["device"],
            "inode": identity["inode"],
        }

    def _remember_blocked_process(
        self, action_id: str, action_armed: dict[str, Any]
    ) -> None:
        process = action_armed["process"]
        frozen = {
            "role": action_id,
            "unit": self.manifest.run_unit,
            "schema": FORMAL_ACTION_ARMED_SCHEMA,
            "identity": {
                "pid": process.pid,
                "starttime": process.proc_starttime_ticks,
            },
        }
        if any(
            item["identity"] == frozen["identity"]
            and item["role"] == frozen["role"]
            for item in self._actor_identities
        ):
            _fail("formal blocked process identity was frozen twice")
        self._actor_identities.append(frozen)

    def _b5_action(
        self,
        pinned: PinnedFormalAction,
        outer_armed: dict[str, Any],
        receipt_watch: CreationWatch,
        authority: dict[str, Any],
    ) -> dict[str, Any]:
        if pinned.control_identity_fd is None or pinned.action.control_fifo is None:
            _fail("B5 lacks its pre-StartUnit hold FIFO identity pin")
        pinned.action.control_fifo.prove(
            pinned.control_identity_fd, label="B5 retained hold FIFO identity"
        )
        receipt_watch.wait_created()
        plan_asset = authority["plan_asset"]
        program_asset = authority["program_asset"]
        if not isinstance(plan_asset, RetainedStaticAsset) or not isinstance(
            program_asset, RetainedStaticAsset
        ):
            _fail("B5 lacks its retained descendant static assets")
        plan_asset.revalidate_path_identity(
            label="B5 sealed descendant plan", require_root=self.require_root
        )
        program_asset.revalidate_path_identity(
            label="B5 descendant program", require_root=self.require_root
        )
        plan = _decode_canonical_raw(
            plan_asset.raw, label="B5 sealed descendant plan"
        )
        if plan != authority["plan"]:
            _fail("B5 descendant plan semantics changed after StartUnit")
        program = {
            "path": str(program_asset.path),
            "sha256": program_asset.sha256,
            "identity": {
                "device": program_asset.device,
                "inode": program_asset.inode,
                "mode": program_asset.mode,
            },
        }
        if program != authority["program"]:
            _fail("B5 descendant program changed after StartUnit")
        request_path = authority["request_path"]
        request_raw = _read_regular(request_path, label="B5 materialized descendant request")
        request = _decode_canonical(request_path, label="B5 materialized descendant request")
        _exact(request, _DESCENDANT_REQUEST_KEYS, label="B5 descendant request")
        service_group = outer_armed["identity"]["service_control_group"]
        expected_job_name = plan["expected_job_name"]
        expected_job_cgroup = f"{service_group}/{expected_job_name}"
        expected_request = {
            "schema": "scion.generic_backend.systemd_adversary_request.v1",
            "scenario": plan["scenario"],
            "unit": plan["unit"],
            "expected_invocation_id": outer_armed["invocation_id"],
            "expected_job_name": expected_job_name,
            "expected_job_cgroup": expected_job_cgroup,
            "receipt_path": str(authority["receipt_path"]),
            "hold_release_fifo": authority["hold_release_fifo"],
        }
        if request != expected_request:
            _fail("B5 materialized request differs from sealed outer/job/FIFO authority")
        request_sha256 = hashlib.sha256(request_raw).hexdigest()
        receipt_path = authority["receipt_path"]
        receipt_raw = _read_regular(receipt_path, label="B5 descendant receipt")
        receipt = _decode_canonical(receipt_path, label="B5 descendant receipt")
        _exact(receipt, _DESCENDANT_RECEIPT_KEYS, label="B5 descendant receipt")
        binding = receipt["formal_plan_binding"]
        if type(binding) is not dict:
            _fail("B5 descendant receipt lacks one formal plan binding")
        _exact(binding, _DESCENDANT_PLAN_BINDING_KEYS, label="B5 descendant plan binding")
        expected_binding = {
            "schema": plan["schema"],
            "scenario": plan["scenario"],
            "unit": plan["unit"],
            "expected_job_name": expected_job_name,
            "plan_path": str(plan_asset.path),
            "plan_sha256": authority["plan_sha256"],
            "program": program,
            "acquisition": None,
            "hold_release_fifo": authority["hold_release_fifo"],
            "materialized_request_sha256": request_sha256,
        }
        if binding != expected_binding:
            _fail("B5 descendant receipt plan/program/request/FIFO binding drifted")
        expected_receipt_fields = {
            "schema": "scion.generic_backend.systemd_adversary_receipt.v1",
            "scenario": plan["scenario"],
            "unit": plan["unit"],
            "expected_invocation_id": outer_armed["invocation_id"],
            "expected_job_name": expected_job_name,
            "expected_job_cgroup": expected_job_cgroup,
            "hold_release_fifo": authority["hold_release_fifo"],
            "request_path": str(request_path),
            "request_sha256": request_sha256,
        }
        if any(receipt[name] != value for name, value in expected_receipt_fields.items()):
            _fail("B5 descendant receipt differs from request/outer/job authority")
        handshake = receipt["release_handshake"]
        if type(handshake) is not dict:
            _fail("B5 descendant receipt lacks one hold handshake")
        _exact(
            handshake,
            {"device", "inode", "path", "permit_sha256"},
            label="B5 descendant release handshake",
        )
        if handshake != {
            "device": pinned.action.control_fifo.device,
            "inode": pinned.action.control_fifo.inode,
            "path": str(pinned.action.control_fifo.path),
            "permit_sha256": hashlib.sha256(RELEASE_BYTES).hexdigest(),
        }:
            _fail("B5 descendant hold handshake differs from the retained FIFO pin")

        identities: dict[str, dict[str, Any]] = {}
        for role in ("actor", "descendant"):
            identity = receipt[role]
            if type(identity) is not dict:
                _fail(f"B5 {role} identity is not one exact object")
            _exact(identity, _FORMAL_DESCENDANT_IDENTITY_KEYS, label=f"B5 {role} identity")
            for field in ("pid", "starttime", "session_id"):
                if type(identity[field]) is not int or identity[field] <= 0:
                    _fail(f"B5 {role} {field} is not one positive integer")
            if (
                identity["boot_id"] != outer_armed["boot_id"]
                or identity["invocation_id"] != outer_armed["invocation_id"]
                or identity["unified_cgroup"] != expected_job_cgroup
                or identity["proc_cgroup_raw"] != f"0::{expected_job_cgroup}\n"
                or identity["stop_selector_environment"] != {}
            ):
                _fail(f"B5 {role} identity is outside the exact invocation/job cgroup")
            identities[role] = dict(identity)
        if identities["actor"]["pid"] == identities["descendant"]["pid"]:
            _fail("B5 descendant aliases its native leader")
        descendant = identities["descendant"]
        descendant_pid = descendant["pid"]
        live_starttime = self.proc_starttime_reader(descendant_pid)
        live_cgroup = self.proc_cgroup_reader(descendant_pid)
        try:
            live_session = os.getsid(descendant_pid)
        except ProcessLookupError as exc:
            raise HarnessError("B5 descendant disappeared before external proof") from exc
        live_starttime_after = self.proc_starttime_reader(descendant_pid)
        if (
            live_starttime != descendant["starttime"]
            or live_starttime_after != live_starttime
            or live_cgroup
            != (descendant["proc_cgroup_raw"], descendant["unified_cgroup"])
            or live_session != descendant["session_id"]
        ):
            _fail("B5 live descendant PID/starttime/session/cgroup identity drifted")
        evidence = {
            "plan_path": str(plan_asset.path),
            "plan_sha256": authority["plan_sha256"],
            "request_path": str(request_path),
            "request_sha256": request_sha256,
            "receipt_path": str(receipt_path),
            "receipt_sha256": hashlib.sha256(receipt_raw).hexdigest(),
            "program": program,
            "hold_release_fifo": authority["hold_release_fifo"],
            "expected_job_name": expected_job_name,
            "expected_job_cgroup": expected_job_cgroup,
            "actor": identities["actor"],
            "descendant": descendant,
            "live_descendant": {
                "pid": descendant_pid,
                "starttime": live_starttime,
                "session_id": live_session,
                "proc_cgroup_raw": live_cgroup[0],
                "unified_cgroup": live_cgroup[1],
            },
        }
        ledger = {
            "schema": "scion.generic_backend.b5_action.v1",
            "action_id": pinned.action.action_id,
            "case_id": "B5",
            "variant": self.manifest.policy.formal_case[1],
            "control_writer_open_count": "0",
            "permit_write_count": "0",
            "ownership": "production-kill-and-drain-only",
            "descendant_evidence": evidence,
        }
        _write_no_replace(pinned.action.action_ledger_path, ledger)
        return ledger

    def _b4_action(
        self, pinned: PinnedFormalAction, outer_armed: dict[str, Any]
    ) -> dict[str, Any]:
        writer = pinned.open_control_writer()
        job_fd = -1
        try:
            armed = _formal_action_armed(pinned.action, self.manifest.policy, outer_armed)
            self._remember_blocked_process(pinned.action.action_id, armed)
            job_fd, job_identity = self._pin_formal_job(armed)
            kill_fd = os.open(
                "cgroup.kill",
                os.O_WRONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=job_fd,
            )
            try:
                self._write_descriptor(kill_fd, b"1\n", label="B4 cgroup.kill")
                kill_identity = os.fstat(kill_fd)
            finally:
                os.close(kill_fd)
            ledger = {
                "schema": "scion.generic_backend.b4_action.v1",
                "action_id": pinned.action.action_id,
                "case_id": "B4",
                "variant": self.manifest.policy.formal_case[1],
                "job_cgroup": job_identity,
                "kill_file": {
                    "device": str(kill_identity.st_dev),
                    "inode": str(kill_identity.st_ino),
                },
                "write_count": "1",
                "write_bytes_sha256": hashlib.sha256(b"1\n").hexdigest(),
                "armed_receipt_sha256": hashlib.sha256(
                    _canonical(armed["receipt"])
                ).hexdigest(),
                "permit_sha256": hashlib.sha256(b"JOB_CGROUP_KILLED\n").hexdigest(),
            }
            _write_no_replace(pinned.action.action_ledger_path, ledger)
            self._write_descriptor(
                writer, b"JOB_CGROUP_KILLED\n", label="B4 control permit"
            )
            return ledger
        finally:
            if job_fd >= 0:
                os.close(job_fd)
            os.close(writer)

    def _b7_action(
        self, pinned: PinnedFormalAction, outer_armed: dict[str, Any]
    ) -> dict[str, Any]:
        writer = pinned.open_control_writer()
        job_fd = -1
        try:
            armed = _formal_action_armed(pinned.action, self.manifest.policy, outer_armed)
            self._remember_blocked_process(pinned.action.action_id, armed)
            job_fd, job_identity = self._pin_formal_job(armed)
            service = self._cgroup_pins[self.manifest.run_unit]
            assert self.manifest.policy.formal_case is not None
            variant = self.manifest.policy.formal_case[1]
            before = _recursive_cgroup_inventory(service.service_fd)
            mutation: dict[str, Any]
            if variant == "cgroup-inode-drift":
                replacement = f".scion-drift-{job_identity['job_name']}"
                os.rename(
                    job_identity["job_name"],
                    replacement,
                    src_dir_fd=service.service_fd,
                    dst_dir_fd=service.service_fd,
                )
                os.mkdir(job_identity["job_name"], mode=0o755, dir_fd=service.service_fd)
                new_fd, new_identity = _open_child_cgroup(
                    service.service_fd, job_identity["job_name"]
                )
                os.close(new_fd)
                if new_identity == {
                    "device": job_identity["device"],
                    "inode": job_identity["inode"],
                }:
                    _fail("B7 cgroup inode replacement retained the old identity")
                mutation = {
                    "kind": "cgroup-inode-drift",
                    "renamed_leaf": replacement,
                    "replacement_identity": new_identity,
                }
            elif variant == "unexpected-sibling":
                name = ".scion-unexpected-sibling"
                os.mkdir(name, mode=0o755, dir_fd=service.service_fd)
                child, identity = _open_child_cgroup(service.service_fd, name)
                os.close(child)
                mutation = {"kind": variant, "name": name, "identity": identity}
            elif variant == "unexpected-nested":
                name = ".scion-unexpected-nested"
                os.mkdir(name, mode=0o755, dir_fd=job_fd)
                child, identity = _open_child_cgroup(job_fd, name)
                os.close(child)
                mutation = {"kind": variant, "name": name, "identity": identity}
            elif variant == "supervisor-extra-task":
                if service.supervisor_fd is None:
                    _fail("B7 supervisor action lacks the outer supervisor pin")
                child_pid = armed["process"].pid
                child_starttime = armed["process"].proc_starttime_ticks
                if self.proc_starttime_reader(child_pid) != child_starttime:
                    _fail("B7 blocked child identity drifted before supervisor move")
                procs = os.open(
                    "cgroup.procs",
                    os.O_WRONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                    dir_fd=service.supervisor_fd,
                )
                try:
                    self._write_descriptor(
                        procs, f"{child_pid}\n".encode("ascii"), label="B7 supervisor task"
                    )
                finally:
                    os.close(procs)
                if self.proc_starttime_reader(child_pid) != child_starttime:
                    _fail("B7 blocked child identity drifted after supervisor move")
                mutation = {
                    "kind": variant,
                    "pid": str(child_pid),
                    "starttime": str(child_starttime),
                    "source": "identity-pinned-formal-blocked-child",
                }
            else:
                _fail("B7 external action variant is outside the closed source table")
            after = _recursive_cgroup_inventory(service.service_fd)
            ledger = {
                "schema": "scion.generic_backend.b7_action.v1",
                "action_id": pinned.action.action_id,
                "case_id": "B7",
                "variant": variant,
                "job_cgroup": job_identity,
                "mutation": mutation,
                "before": before,
                "after": after,
                "armed_receipt_sha256": hashlib.sha256(
                    _canonical(armed["receipt"])
                ).hexdigest(),
                "permit_sha256": hashlib.sha256(b"DRIFT_APPLIED\n").hexdigest(),
            }
            _write_no_replace(pinned.action.action_ledger_path, ledger)
            self._write_descriptor(writer, b"DRIFT_APPLIED\n", label="B7 control permit")
            return ledger
        finally:
            if job_fd >= 0:
                os.close(job_fd)
            os.close(writer)

    def _b6_action(
        self,
        pinned: PinnedFormalAction,
        outer_armed: dict[str, Any],
        armed_watch: CreationWatch,
        operation_watch: CreationWatch,
    ) -> dict[str, Any]:
        armed_watch.wait_created()
        armed = _b6_armed(pinned.action, self.manifest.policy, outer_armed)
        rendezvous = PinnedAcquisition.open(
            Acquisition(
                "b6-action",
                pinned.action.armed_receipt_path,
                armed["ready"],
                armed["release"],
            )
        )
        pidfd = -1
        try:
            self.manager.wait_readable(rendezvous.ready_reader_fd)
            rendezvous.consume_ready()
            identity = armed["receipt"]["process_identity"]
            pid = identity["pid"]
            starttime = identity["starttime"]
            pidfd = os.pidfd_open(pid, 0)
            pidfd_info = os.fstat(pidfd)
            if self.proc_starttime_reader(pid) != starttime:
                _fail("B6 pidfd target differs from ARMED PID/starttime")
            issuer = pinned.action.action_id == "b6-issuer-send"
            if issuer:
                signal_module.pidfd_send_signal(pidfd, signal_module.SIGUSR1)
            ledger = {
                "schema": "scion.generic_backend.b6_action.v1",
                "action_id": pinned.action.action_id,
                "case_id": "B6",
                "variant": self.manifest.policy.formal_case[1],
                "signal": "SIGUSR1" if issuer else None,
                "signal_send_count": "1" if issuer else "0",
                "pid": str(pid),
                "starttime": str(starttime),
                "pidfd_device": str(pidfd_info.st_dev),
                "pidfd_inode": str(pidfd_info.st_ino),
                "armed_receipt_sha256": hashlib.sha256(
                    _canonical(armed["receipt"])
                ).hexdigest(),
                "release_sha256": hashlib.sha256(RELEASE_BYTES).hexdigest(),
            }
            _write_no_replace(pinned.action.action_ledger_path, ledger)
            rendezvous.release()
            operation_watch.wait_created()
            operation = _b6_operation(
                pinned.action, self.manifest.policy, armed
            )
            return {"action": ledger, "operation": operation}
        finally:
            if pidfd >= 0:
                os.close(pidfd)
            rendezvous.close()

    def _perform_formal_action(
        self,
        pinned: PinnedFormalAction,
        outer_armed: dict[str, Any],
        armed_watch: CreationWatch | None,
        operation_watch: CreationWatch | None,
        b5_receipt_watch: CreationWatch | None,
    ) -> dict[str, Any]:
        case_id = self.manifest.policy.formal_case[0]
        if case_id == "B4":
            return self._b4_action(pinned, outer_armed)
        if case_id == "B5":
            if self._installer_authority is None:
                _fail("B5 lacks its prevalidated root authority")
            authority = self._installer_authority.get("b5_descendant_authority")
            if type(authority) is not dict or b5_receipt_watch is None:
                _fail("B5 lacks its pre-StartUnit descendant receipt watch/authority")
            return self._b5_action(
                pinned, outer_armed, b5_receipt_watch, authority
            )
        if case_id == "B6":
            if armed_watch is None or operation_watch is None:
                _fail("B6 lacks its pre-start creation watches")
            return self._b6_action(
                pinned, outer_armed, armed_watch, operation_watch
            )
        if case_id == "B7":
            return self._b7_action(pinned, outer_armed)
        _fail("formal action exists for a source row without external action")

    def _formal_failstop_evidence(
        self, terminal_receipts: dict[str, dict[str, Any]]
    ) -> dict[str, Any] | None:
        policy = self.manifest.policy
        if "formal-failstop" not in policy.required_outputs:
            return None
        is_external_b7 = (
            policy.formal_case is not None
            and policy.formal_case[0] == "B7"
            and not policy.formal_case[1].startswith("tmpfile-")
        )
        is_b6_failstop = (
            policy.formal_case is not None
            and policy.formal_case[0] == "B6"
            and policy.formal_case[1] in _B6_DECLARED_FAILSTOP_VARIANTS
            and policy.formal_completion == "failstop"
            and policy.formal_expected_fact_type == "FAILSTOP"
        )
        if (
            not (is_external_b7 or is_b6_failstop)
            or self._formal_outer_armed is None
            or len(self.manifest.formal_actions) != 1
        ):
            _fail("formal fail-stop output is outside its closed B7/B6 policy")
        outer = self._formal_outer_armed
        if self._installer_authority is None:
            _fail("formal fail-stop lacks pre-StartUnit directory authority")
        config_path, config, config_sha256, forbidden_final = _formal_config_binding(
            policy,
            outer,
            expected_directory_authorities=self._installer_authority[
                "formal_directory_authorities"
            ],
        )
        case_id, variant = policy.formal_case
        reserved = {item.path for item in self.manifest.outputs}
        if forbidden_final in reserved:
            _fail("external B7 forbidden formal-final aliases a harness output")
        if forbidden_final.exists() or forbidden_final.is_symlink():
            _fail("external B7 fail-stop incorrectly published formal-final")
        action = self.manifest.formal_actions[0]
        action_raw = _read_regular(action.action_ledger_path, label="formal action ledger")
        operation_sha256 = None
        if is_b6_failstop:
            if (
                len(self._formal_action_evidence) != 1
                or type(self._formal_action_evidence[0]) is not dict
                or set(self._formal_action_evidence[0]) != {"action", "operation"}
            ):
                _fail("B6 fail-stop lacks one durable action/operation evidence pair")
            operation = self._formal_action_evidence[0]["operation"]
            if type(operation) is not dict:
                _fail("B6 fail-stop operation evidence is not one object")
            operation_sha256 = hashlib.sha256(_canonical(operation)).hexdigest()
        handoff = terminal_receipts[self.manifest.run_unit]["normalization"]["handoff"]
        evidence = {
            "schema": "scion.generic_backend.formal_failstop.v1",
            "classification": policy.final_classification,
            "case_id": case_id,
            "variant": variant,
            "unit": self.manifest.run_unit,
            "action_id": action.action_id,
            "action_ledger_sha256": hashlib.sha256(action_raw).hexdigest(),
            "final_config_path": str(config_path),
            "final_config_sha256": config_sha256,
            "forbidden_formal_final_path": str(forbidden_final),
            "formal_final_absent": True,
            "run_terminal": {
                name: handoff[name]
                for name in (
                    "result",
                    "active_state",
                    "sub_state",
                    "exec_main_code",
                    "exec_main_status",
                    "exec_stop_post_code",
                    "exec_stop_post_status",
                )
            },
        }
        if is_b6_failstop:
            evidence["operation_receipt_sha256"] = operation_sha256
        _write_no_replace(self.manifest.output("formal-failstop"), evidence)
        return evidence

    def _remember_source_binding(self, armed: dict[str, Any]) -> None:
        if self._source_binding is not None:
            _fail("source stop-post binding was published more than once")
        receipt = armed["receipt"]
        raw_path = receipt.get("output_path")
        if raw_path is None:
            raw_path = receipt.get("receipt_path")
        source_receipt_path = _path(raw_path, label="source terminal receipt path")
        reserved = {item.path for item in self.manifest.outputs}
        for acquisition in self.manifest.acquisitions:
            reserved.update(
                {
                    acquisition.armed_receipt_path,
                    acquisition.ready_fifo.path,
                    acquisition.release_fifo.path,
                }
            )
        if source_receipt_path in reserved:
            _fail("source terminal receipt aliases another manifest authority")
        self._source_binding = {
            "boot_id": armed["boot_id"],
            "unit": armed["unit"],
            "invocation_id": armed["invocation_id"],
            "receipt_path": source_receipt_path,
        }

    def _seal_source_binding_for_closer(self) -> None:
        binding = self._source_binding
        if binding is None:
            _fail("closer armed before exact source stop-post binding")
        source = _decode_canonical(binding["receipt_path"], label="source terminal receipt")
        if source.get("schema") == "scion.generic_backend.systemd_observer_receipt.v1":
            identity = source.get("process_identity")
        elif source.get("schema") == "scion.generic_backend.systemd_adversary_receipt.v1":
            identity = source.get("actor")
        else:
            _fail("source terminal receipt schema is not observer/adversary v1")
        if (
            type(identity) is not dict
            or source.get("unit") != binding["unit"]
            or identity.get("boot_id") != binding["boot_id"]
            or identity.get("invocation_id") != binding["invocation_id"]
        ):
            _fail("source terminal receipt does not cross-bind boot/unit/invocation")
        seal_source_selector(
            boot_id=binding["boot_id"],
            source_unit=binding["unit"],
            source_invocation_id=binding["invocation_id"],
            source_receipt_path=binding["receipt_path"],
            selector_path=self.manifest.output("source-selector"),
        )

    def _h10(
        self,
        boot_id: str,
        start_job: str,
        armed: dict[str, Any],
        original_object: str,
    ) -> dict[str, Any]:
        del start_job
        self.manager.wait_for(
            lambda: any(
                signal.member == "UnitRemoved"
                and len(signal.body) == 2
                and str(signal.body[0]) == self.manifest.run_unit
                for signal in self.signals
            )
        )
        scenario_input = self.manifest.scenario_input
        if type(scenario_input) is not dict:
            _fail("H10 actor receipt input is missing")
        actor_receipt_path = Path(scenario_input["actor_receipt_path"])
        actor_receipt = _decode_canonical(actor_receipt_path, label="H10 actor receipt")
        if (
            actor_receipt.get("schema")
            != "scion.generic_backend.systemd_adversary_receipt.v1"
            or actor_receipt.get("scenario") != "h10-gc-negative"
            or actor_receipt.get("unit") != self.manifest.run_unit
            or actor_receipt.get("actor") != armed["identity"]
        ):
            _fail("H10 terminal actor receipt does not cross-bind ARMED identity")
        if (
            actor_receipt["actor"].get("boot_id") != boot_id
            or actor_receipt["actor"].get("invocation_id") != armed["invocation_id"]
        ):
            _fail("H10 terminal actor boot/invocation differs from ARMED receipt")
        pin = self._cgroup_pins.get(self.manifest.run_unit)
        if pin is None or pin.invocation_id != armed["invocation_id"]:
            _fail("H10 lost its acquisition-time cgroup pin")
        info = os.fstat(pin.service_fd)
        if (info.st_dev, info.st_ino) != (
            int(pin.service_identity["device"]),
            int(pin.service_identity["inode"]),
        ):
            _fail("H10 pinned cgroup identity drifted")
        path_absent: bool | None = None
        if self.require_root:
            try:
                replacement, _ = _open_cgroup_from_manager(pin.control_group)
            except FileNotFoundError:
                path_absent = True
            else:
                os.close(replacement)
                _fail("H10 UnitRemoved left or replaced its exact cgroup path")
        pin.close()
        self._cgroup_pins.pop(self.manifest.run_unit, None)
        self._load_count += 1
        if self._load_count != 1:
            _fail("H10 LoadUnit call count drifted")
        loaded_object = str(
            self._manager_method(
                "LoadUnit",
                "s",
                [self.manifest.run_unit],
                lambda: self.manager.load_unit(self.manifest.run_unit),
            )
        )
        removals = [
            event
            for signal, event in zip(
                self.signals,
                [item for item in self.manager_events if item["kind"] == "signal"],
            )
            if signal.member == "UnitRemoved"
            and signal.body == (self.manifest.run_unit, original_object)
        ]
        load_events = [
            event
            for event in self.manager_events
            if event["kind"] == "method"
            and event["method"] == "LoadUnit"
            and event["arguments"] == [self.manifest.run_unit]
        ]
        if (
            len(removals) != 1
            or len(load_events) != 1
            or int(removals[0]["ordinal"]) >= int(load_events[0]["begin_ordinal"])
            or load_events[0].get("reply") != loaded_object
        ):
            _fail("H10 original object removal is not strictly before one LoadUnit reply")
        receipt = query_unit_properties(
            self.manager,
            unit=self.manifest.run_unit,
            peer_unit=None,
            boot_id=boot_id,
            receipt_path=self.manifest.output("h10-reloaded-properties"),
            allow_empty_invocation=True,
            publish=False,
            object_path=loaded_object,
        )
        if receipt["invocation_id"] != "":
            _fail("H10 reloaded InvocationID is not empty")
        states = tuple(
            _encoded_text(receipt, UNIT_INTERFACE, name)
            for name in ("LoadState", "ActiveState", "SubState")
        )
        if states != ("loaded", "inactive", "dead"):
            _fail("H10 reloaded unit is not loaded/inactive/dead")
        receipt["negative_identity_loss"] = {
            "actor_receipt_path": str(actor_receipt_path),
            "actor_receipt_sha256": hashlib.sha256(
                _read_regular(actor_receipt_path, label="H10 actor receipt")
            ).hexdigest(),
            "source_boot_id": boot_id,
            "source_unit": self.manifest.run_unit,
            "source_invocation_id": armed["invocation_id"],
            "early_cgroup_identity": pin.service_identity,
            "path_absent_after_unit_removed": path_absent,
            "original_object_path": original_object,
            "unit_removed_ordinal": removals[0]["ordinal"],
            "load_begin_ordinal": load_events[0]["begin_ordinal"],
            "load_reply_ordinal": load_events[0]["reply_ordinal"],
            "loaded_object_path": loaded_object,
        }
        _write_no_replace(self.manifest.output("h10-reloaded-properties"), receipt)
        _write_no_replace(
            self.manifest.output("h10-absence"),
            {
                "schema": "scion.generic_backend.systemd_h10_absence.v1",
                "classification": "rejected-failed-identity-loss",
                **receipt["negative_identity_loss"],
            },
        )
        return receipt

    def run(self) -> dict[str, Any]:
        self._installer_authority = (
            self.manifest.prevalidate(require_root=self.require_root)
            if self.prevalidated_authority is None
            else self.prevalidated_authority
        )
        acquisition_watches = {
            item.role: CreationWatch(item.armed_receipt_path)
            for item in self.manifest.acquisitions
        }
        boot_id = _boot_id(self.manifest.boot_id_file)
        descriptor = self._installer_authority["start_descriptor"]
        h0 = self._preflight()
        _write_no_replace(self.manifest.output("h0"), h0)
        self._transition("PREVALIDATED", "H0_FROZEN")
        if self.manifest.scenario == "H0":
            manager_events = self._manager_event_receipt()
            _write_no_replace(self.manifest.output("manager-events"), manager_events)
            final = {
                "schema": HARNESS_RECEIPT_SCHEMA,
                "scenario": "H0",
                "execution_manifest_source": self._installer_authority[
                    "execution_manifest_source"
                ],
                "classification": self.manifest.policy.final_classification,
                "h0_sha256": hashlib.sha256(_canonical(h0)).hexdigest(),
                "start_call_count": "0",
                "state": self._state,
                "final_freeze": self._final_freeze_policy(),
            }
            _write_no_replace(self.manifest.output("final"), final)
            for watch in acquisition_watches.values():
                watch.close()
            _close_retained_static_authority(self._installer_authority)
            return final
        pins = [PinnedAcquisition.open(item) for item in self.manifest.acquisitions]
        action_pins = [PinnedFormalAction.open(item) for item in self.manifest.formal_actions]
        action_watches: dict[str, tuple[CreationWatch | None, CreationWatch | None]] = {}
        b5_receipt_watches: dict[str, CreationWatch | None] = {}
        for action in self.manifest.formal_actions:
            action_watches[action.action_id] = (
                None
                if action.armed_receipt_path is None
                else CreationWatch(action.armed_receipt_path),
                None
                if action.operation_receipt_path is None
                else CreationWatch(action.operation_receipt_path),
            )
            authority = self._installer_authority.get("b5_descendant_authority")
            b5_receipt_watches[action.action_id] = (
                CreationWatch(authority["receipt_path"])
                if type(authority) is dict
                and self.manifest.policy.formal_case is not None
                and self.manifest.policy.formal_case[0] == "B5"
                else None
            )
        try:
            self.journal.begin()
            self.manager.install_signal_handlers(self._record_signal)
            self._manager_method("Subscribe", "", [], self.manager.subscribe)
            if self.manifest.scenario == "H10":
                if self.manifest.closer_unit is not None:
                    _fail("H10 negative control must not name a closer")
            else:
                if self.manifest.closer_unit is None:
                    _fail("positive scenario requires one concrete closer")
                for unit in (self.manifest.run_unit, self.manifest.closer_unit):
                    self._manager_method(
                        "RefUnit", "s", [unit], lambda unit=unit: self.manager.ref_unit(unit)
                    )
                    self._ref_units.add(unit)
            self._transition("H0_FROZEN", "SUBSCRIBED_AND_REFED")
            _revalidate_retained_static_authority(
                self._installer_authority, require_root=self.require_root
            )
            for watch in acquisition_watches.values():
                watch.close_pre_start_absence_boundary()
            self._start_count += 1
            if self._start_count != 1:
                _fail("formal root issued more than one StartUnit")
            start_job = str(
                self._manager_method(
                    "StartUnit",
                    "ss",
                    [descriptor.unit, "fail"],
                    lambda: self.manager.start_unit(descriptor.unit, "fail"),
                )
            )
            self._owned_job_paths.add(start_job)

            query_receipts: list[dict[str, Any]] = []
            seen_invocations: set[str] = set()
            h10_armed: dict[str, Any] | None = None
            h7_stop_job: str | None = None
            for pin in pins:
                self.manager.wait_readable(pin.ready_reader_fd)
                acquisition_watch = acquisition_watches.get(pin.acquisition.role)
                if acquisition_watch is None:
                    _fail("acquisition lacks its retained ARMED creation watch")
                acquisition_watch.wait_single_post_start_creation()
                pin.consume_ready()
                static_authority = self._installer_authority[
                    "static_role_authorities"
                ].get(pin.acquisition.role)
                if not isinstance(static_authority, StaticRoleAuthority):
                    _fail("ready acquisition lacks its retained static role authority")
                armed = _armed_identity(
                    pin.acquisition.armed_receipt_path,
                    pin.acquisition,
                    static_authority,
                    run_unit=self.manifest.run_unit,
                    closer_unit=self.manifest.closer_unit,
                    policy=self.manifest.policy,
                )
                acquisition_watch.prove_single_post_start_creation()
                self._actor_identities.append(
                    {
                        "role": pin.acquisition.role,
                        "unit": armed["unit"],
                        "schema": armed["schema"],
                        "identity": json.loads(json.dumps(armed["identity"])),
                    }
                )
                query = self._query_for_acquisition(pin.acquisition, armed, boot_id)
                query_receipts.append(query)
                if pin.acquisition.role == "run-main":
                    self._transition("SUBSCRIBED_AND_REFED", "RUN_ACQUIRED")
                    if armed["schema"] == FORMAL_ARMED_SCHEMA:
                        self._formal_outer_armed = armed
                invocation = armed["invocation_id"]
                if invocation not in seen_invocations:
                    self.journal.add_invocation(boot_id, invocation)
                    seen_invocations.add(invocation)
                if pin.acquisition.role in {"exec-stop-post", "h4-stop-post"}:
                    self._remember_source_binding(armed)
                if pin.acquisition.role in {"closer", "failed-closer"}:
                    self._seal_source_binding_for_closer()
                if (
                    self.manifest.scenario == "H7"
                    and pin.acquisition.role == "run-main"
                ):
                    if self._stop_count != 0:
                        _fail("H7 attempted more than one StopUnit")
                    stop_job = str(
                        self._manager_method(
                            "StopUnit",
                            "ss",
                            [self.manifest.run_unit, "fail"],
                            lambda: self.manager.stop_unit(self.manifest.run_unit, "fail"),
                        )
                    )
                    self._stop_count += 1
                    if not stop_job:
                        _fail("H7 StopUnit did not return one job object")
                    self._owned_job_paths.add(stop_job)
                    h7_stop_job = stop_job
                    continue
                if (
                    self.manifest.scenario == "H8"
                    and pin.acquisition.role == "run-main"
                ):
                    if self._h8_applied:
                        _fail("H8 attempted more than one dirfd drift")
                    self._h8_drift(query, armed)
                    self._h8_applied = True
                pin.release()
                if pin.acquisition.role == "run-main" and action_pins:
                    if self._formal_outer_armed is None:
                        _fail("formal action policy lacks a formal outer acquisition")
                    for action_pin in action_pins:
                        watches = action_watches[action_pin.action.action_id]
                        self._formal_action_evidence.append(
                            self._perform_formal_action(
                                action_pin,
                                self._formal_outer_armed,
                                watches[0],
                                watches[1],
                                b5_receipt_watches[action_pin.action.action_id],
                            )
                        )
                    self._transition("RUN_ACQUIRED", "FORMAL_ACTION")
                elif pin.acquisition.role in {"exec-stop-post", "h4-stop-post"}:
                    expected = "FORMAL_ACTION" if action_pins else "RUN_ACQUIRED"
                    self._transition(expected, "STOP_ACQUIRED")
                elif pin.acquisition.role in {"closer", "failed-closer"}:
                    self._transition("STOP_ACQUIRED", "CLOSER_ACQUIRED")
                if self.manifest.scenario == "H10":
                    h10_armed = armed

            if self.manifest.scenario == "H10":
                if h10_armed is None or len(query_receipts) != 1:
                    _fail("H10 did not complete exactly one run-main acquisition")
                h10 = self._h10(
                    boot_id,
                    start_job,
                    h10_armed,
                    h0["pre_start_run"]["object_path"],
                )
                self._transition("RUN_ACQUIRED", "H10_RELOADED")
                sync_receipt = self.journal.synchronize()
                journal_receipt = self.journal.freeze()
                _write_no_replace(self.manifest.output("signals"), self._signal_receipt(boot_id))
                _write_no_replace(self.manifest.output("journal"), journal_receipt)
                manager_events = self._manager_event_receipt()
                _write_no_replace(self.manifest.output("manager-events"), manager_events)
                final = {
                    "schema": HARNESS_RECEIPT_SCHEMA,
                    "scenario": self.manifest.scenario,
                    "execution_manifest_source": self._installer_authority[
                        "execution_manifest_source"
                    ],
                    "classification": "rejected-failed-identity-loss",
                    "h10": h10,
                    "journal_synchronize": sync_receipt,
                    "call_ledger": self.call_ledger,
                    "manager_events_sha256": hashlib.sha256(
                        _canonical(manager_events)
                    ).hexdigest(),
                    "state": self._state,
                    "final_freeze": self._final_freeze_policy(),
                }
                _write_no_replace(self.manifest.output("final"), final)
                return final

            if self.manifest.scenario == "H8" and not self._h8_applied:
                _fail("H8 did not execute its one run-main dirfd drift")

            self._wait_for_owned_jobs_and_closer()
            h7_evidence = (
                self._h7_event_evidence(h7_stop_job)
                if self.manifest.scenario == "H7" and h7_stop_job is not None
                else None
            )
            terminal_receipts = self._freeze_terminal_properties(boot_id)
            formal_final = None
            if self.manifest.policy.formal_completion in {
                "typed",
                "requirement-missing",
            }:
                if self._formal_outer_armed is None:
                    _fail("formal-final policy lacks its outer formal acquisition")
                formal_final = _formal_final(
                    self.manifest.policy,
                    self._formal_outer_armed,
                    self._formal_action_evidence,
                    expected_directory_authorities=self._installer_authority[
                        "formal_directory_authorities"
                    ],
                )
            formal_failstop = self._formal_failstop_evidence(terminal_receipts)
            self._transition("CLOSER_ACQUIRED", "TERMINAL_POLICY_FROZEN")
            sync_receipt = self.journal.synchronize()
            journal_receipt = self.journal.freeze()
            h12_absence = self._complete_h12(terminal_receipts)
            self._transition("TERMINAL_POLICY_FROZEN", "H12_COLLECTED")
            _write_no_replace(self.manifest.output("h12-absence"), h12_absence)
            _write_no_replace(self.manifest.output("signals"), self._signal_receipt(boot_id))
            _write_no_replace(self.manifest.output("journal"), journal_receipt)
            manager_events = self._manager_event_receipt()
            _write_no_replace(self.manifest.output("manager-events"), manager_events)
            final = {
                "schema": HARNESS_RECEIPT_SCHEMA,
                "scenario": self.manifest.scenario,
                "execution_manifest_source": self._installer_authority[
                    "execution_manifest_source"
                ],
                "classification": self.manifest.policy.final_classification,
                "start_job": start_job,
                "query_receipt_count": str(len(query_receipts)),
                "journal_synchronize": sync_receipt,
                "call_ledger": self.call_ledger,
                "remaining_refs": sorted(self._ref_units),
                "formal_actions": self._formal_action_evidence,
                "formal_final": formal_final,
                "formal_failstop": formal_failstop,
                "h7": h7_evidence,
                "manager_events_sha256": hashlib.sha256(
                    _canonical(manager_events)
                ).hexdigest(),
                "state": self._state,
                "final_freeze": self._final_freeze_policy(),
            }
            if self._ref_units:
                _fail("H12 leaked a unit reference")
            _write_no_replace(self.manifest.output("final"), final)
            return final
        finally:
            for watch in acquisition_watches.values():
                watch.close()
            for watch_pair in action_watches.values():
                for watch in watch_pair:
                    if watch is not None:
                        watch.close()
            for watch in b5_receipt_watches.values():
                if watch is not None:
                    watch.close()
            for action_pin in action_pins:
                action_pin.close()
            for pin in pins:
                pin.close()
            for cgroup_pin in list(self._cgroup_pins.values()):
                cgroup_pin.close()
            self._cgroup_pins.clear()
            _close_retained_static_authority(self._installer_authority)

    def _job_removed(self, job_path: str) -> bool:
        return any(
            signal.member == "JobRemoved"
            and len(signal.body) == 4
            and str(signal.body[1]) == job_path
            for signal in self.signals
        )

    def _wait_for_owned_jobs_and_closer(self) -> None:
        self.manager.wait_for(
            lambda: all(self._job_removed(path) for path in self._owned_job_paths)
        )
        closer = self.manifest.closer_unit
        if closer is None:
            return
        self.manager.wait_for(
            lambda: any(
                signal.member == "JobNew"
                and len(signal.body) == 3
                and str(signal.body[2]) == closer
                for signal in self.signals
            )
        )
        closer_jobs = {
            str(signal.body[1])
            for signal in self.signals
            if signal.member == "JobNew"
            and len(signal.body) == 3
            and str(signal.body[2]) == closer
        }
        if len(closer_jobs) != 1:
            _fail("closer did not have exactly one manager-owned job")
        self.manager.wait_for(lambda: all(self._job_removed(path) for path in closer_jobs))

    def _freeze_terminal_properties(self, boot_id: str) -> dict[str, dict[str, Any]]:
        closer = self.manifest.closer_unit
        if closer is None:
            _fail("positive terminal evidence lost its closer")
        run_object = str(
            self._manager_method(
                "GetUnit", "s", [self.manifest.run_unit],
                lambda: self.manager.get_unit(self.manifest.run_unit),
            )
        )
        run_receipt = query_unit_properties(
            self.manager,
            unit=self.manifest.run_unit,
            peer_unit=closer,
            boot_id=boot_id,
            receipt_path=self.manifest.output("final-run-properties"),
            publish=False,
            object_path=run_object,
        )
        run_receipt["normalization"]["handoff"] = self._decode_handoff(run_receipt)
        handoff = run_receipt["normalization"]["handoff"]
        observed_run = (
            handoff["result"],
            handoff["active_state"],
            handoff["sub_state"],
            int(handoff["exec_main_code"]),
            int(handoff["exec_main_status"]),
            int(handoff["exec_stop_post_code"]),
            int(handoff["exec_stop_post_status"]),
        )
        if observed_run != self.manifest.policy.terminal.run:
            _fail("run terminal tuple differs from ScenarioPolicy")
        if run_receipt["normalization"]["configured"].get("status") != "accepted":
            _fail("final run configured properties did not normalize")
        _write_no_replace(self.manifest.output("final-run-properties"), run_receipt)
        closer_object = str(
            self._manager_method(
                "GetUnit", "s", [closer], lambda: self.manager.get_unit(closer)
            )
        )
        closer_receipt = query_unit_properties(
            self.manager,
            unit=closer,
            peer_unit=self.manifest.run_unit,
            boot_id=boot_id,
            receipt_path=self.manifest.output("final-closer-properties"),
            publish=False,
            object_path=closer_object,
        )
        if closer_receipt["normalization"]["configured"].get("status") != "accepted":
            _fail("final closer configured properties did not normalize")
        closer_terminal = _closer_terminal_policy(
            closer_receipt,
            expected_unit=closer,
            expected=self.manifest.policy.terminal.closer,
        )
        closer_receipt["normalization"]["terminal"] = {
            "status": "accepted",
            "decoder": "CloserTerminalProperties",
            "unit": closer_terminal.unit,
            "invocation_id": closer_terminal.invocation_id,
            "load_state": closer_terminal.load_state,
            "active_state": closer_terminal.active_state,
            "sub_state": closer_terminal.sub_state,
            "result": closer_terminal.result,
            "exec_main_code": str(closer_terminal.exec_main_code),
            "exec_main_status": str(closer_terminal.exec_main_status),
        }
        _write_no_replace(self.manifest.output("final-closer-properties"), closer_receipt)
        return {self.manifest.run_unit: run_receipt, closer: closer_receipt}

    def _decode_handoff(self, receipt: dict[str, Any]) -> dict[str, Any]:
        code, status = _final_exec_stop_post(receipt)
        try:
            from scion.runtime.execution.systemd255 import (  # type: ignore[import-not-found]
                UnitHandoffProperties,
            )
        except ImportError as exc:
            raise HarnessError("accepted UnitHandoffProperties decoder is unavailable") from exc
        invocation_id = receipt["invocation_id"]
        if type(invocation_id) is not str or _INVOCATION_RE.fullmatch(invocation_id) is None:
            _fail("final run InvocationID is not a live invocation selector")
        pin = self._cgroup_pins.get(self.manifest.run_unit)
        if pin is None or pin.invocation_id != invocation_id:
            _fail("final handoff invocation differs from early cgroup pin")
        decoded = UnitHandoffProperties.from_properties(
            {
                "Id": _encoded_text(receipt, UNIT_INTERFACE, "Id"),
                "InvocationID": invocation_id,
                "LoadState": _encoded_text(receipt, UNIT_INTERFACE, "LoadState"),
                "ActiveState": _encoded_text(receipt, UNIT_INTERFACE, "ActiveState"),
                "SubState": _encoded_text(receipt, UNIT_INTERFACE, "SubState"),
                "Result": _encoded_text(receipt, SERVICE_INTERFACE, "Result"),
                "ExecMainCode": str(
                    _encoded_integer(receipt, SERVICE_INTERFACE, "ExecMainCode")
                ),
                "ExecMainStatus": str(
                    _encoded_integer(receipt, SERVICE_INTERFACE, "ExecMainStatus")
                ),
                "ExecStopPostCode": str(code),
                "ExecStopPostStatus": str(status),
            },
            expected_unit=self.manifest.run_unit,
        )
        return {
            "status": "accepted",
            "decoder": "UnitHandoffProperties",
            "unit": decoded.unit,
            "invocation_id": decoded.invocation_id,
            "load_state": decoded.load_state,
            "active_state": decoded.active_state,
            "sub_state": decoded.sub_state,
            "result": decoded.result,
            "exec_main_code": str(decoded.exec_main_code),
            "exec_main_status": str(decoded.exec_main_status),
            "exec_stop_post_code": str(decoded.exec_stop_post_code),
            "exec_stop_post_status": str(decoded.exec_stop_post_status),
        }

    def _complete_h12(
        self, terminal_receipts: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        units = [self.manifest.run_unit]
        if self.manifest.closer_unit is not None:
            units.append(self.manifest.closer_unit)
        cgroup_pins: list[tuple[CgroupPin, dict[str, str]]] = []
        if self.require_root:
            for unit in units:
                pin = self._cgroup_pins.get(unit)
                if pin is None:
                    _fail("H12 lacks an early acquisition-time cgroup pin")
                if pin.control_group != _encoded_text(
                    terminal_receipts[unit], SERVICE_INTERFACE, "ControlGroup"
                ):
                    _fail("terminal ControlGroup differs from early cgroup pin")
                try:
                    events_fd = os.open(
                        "cgroup.events",
                        os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                        dir_fd=pin.service_fd,
                    )
                    try:
                        events_raw = _read_all(events_fd)
                    finally:
                        os.close(events_fd)
                except BaseException:
                    raise
                try:
                    events_text = events_raw.decode("ascii", "strict")
                except UnicodeError as exc:
                    raise HarnessError("cgroup.events is not ASCII") from exc
                event_pairs: dict[str, str] = {}
                for line in events_text.splitlines():
                    parts = line.split(" ")
                    if len(parts) != 2 or parts[0] in event_pairs:
                        _fail("cgroup.events is not one canonical key/value receipt")
                    event_pairs[parts[0]] = parts[1]
                if event_pairs.get("populated") != "0":
                    _fail("terminal cgroup tree is still populated")
                cgroup_pins.append((pin, event_pairs))
        for unit in units:
            state = _encoded_text(
                terminal_receipts[unit], UNIT_INTERFACE, "ActiveState"
            )
            if state == "failed":
                self._manager_method(
                    "ResetFailedUnit", "s", [unit],
                    lambda unit=unit: self.manager.reset_failed_unit(unit),
                )
        for unit in units:
            self._manager_method(
                "UnrefUnit", "s", [unit], lambda unit=unit: self.manager.unref_unit(unit)
            )
            self._ref_units.remove(unit)
        self.manager.wait_for(
            lambda: all(
                any(
                    signal.member == "UnitRemoved"
                    and len(signal.body) == 2
                    and str(signal.body[0]) == unit
                    for signal in self.signals
                )
                for unit in units
            )
        )
        installed_objects = self._installer_unit_objects()
        removal_evidence: list[dict[str, Any]] = []
        signal_events = [
            (signal, event)
            for signal, event in zip(
                self.signals,
                [item for item in self.manager_events if item["kind"] == "signal"],
            )
        ]
        for unit in units:
            object_path = terminal_receipts[unit]["object_path"]
            if installed_objects and installed_objects.get(unit) != object_path:
                _fail("terminal unit object differs from installer authority")
            removals = [
                (signal, event)
                for signal, event in signal_events
                if signal.member == "UnitRemoved"
                and signal.body == (unit, object_path)
            ]
            unrefs = [
                event
                for event in self.manager_events
                if event["kind"] == "method"
                and event["method"] == "UnrefUnit"
                and event["arguments"] == [unit]
            ]
            if len(removals) != 1 or len(unrefs) != 1 or int(
                removals[0][1]["ordinal"]
            ) <= int(unrefs[0]["reply_ordinal"]):
                _fail("H12 UnitRemoved is not unique and later than Unref reply")
            try:
                self._manager_method(
                    "GetUnit", "s", [unit], lambda unit=unit: self.manager.get_unit(unit)
                )
            except BaseException as exc:
                name_getter = getattr(exc, "get_dbus_name", None)
                name = name_getter() if callable(name_getter) else getattr(exc, "name", "")
                if name != "org.freedesktop.systemd1.NoSuchUnit":
                    raise
            else:
                _fail("H12 post-removal GetUnit did not return exact NoSuchUnit")
            removal_evidence.append(
                {
                    "unit": unit,
                    "object_path": object_path,
                    "unref_reply_ordinal": unrefs[0]["reply_ordinal"],
                    "unit_removed_ordinal": removals[0][1]["ordinal"],
                    "post_removal_get_unit": "org.freedesktop.systemd1.NoSuchUnit",
                }
            )
        actor_records = _prove_actor_absence(
            self._actor_identities, self.proc_starttime_reader
        )
        records: list[dict[str, Any]] = []
        try:
            for pin, event_pairs in cgroup_pins:
                info = os.fstat(pin.service_fd)
                if (info.st_dev, info.st_ino) != (
                    int(pin.service_identity["device"]),
                    int(pin.service_identity["inode"]),
                ):
                    _fail("pinned terminal cgroup identity drifted")
                try:
                    replacement, _ = _open_cgroup_from_manager(pin.control_group)
                except FileNotFoundError:
                    replacement = -1
                if replacement >= 0:
                    os.close(replacement)
                    _fail("UnitRemoved did not remove the exact cgroup path")
                records.append(
                    {
                        "unit": pin.unit,
                        "identity": pin.service_identity,
                        "terminal_events": event_pairs,
                        "path_absent_after_unit_removed": True,
                    }
                )
        finally:
            for pin, _ in cgroup_pins:
                pin.close()
                self._cgroup_pins.pop(pin.unit, None)
        return {
            "schema": "scion.generic_backend.systemd_h12_absence.v1",
            "classification": (
                "system-manager-authority" if self.require_root else "pure-fake-only"
            ),
            "units": records,
            "removals": removal_evidence,
            "actors": actor_records,
            "actor_count": str(len(actor_records)),
            "unit_removed_count": str(
                len([signal for signal in self.signals if signal.member == "UnitRemoved"])
            ),
            "remaining_refs": sorted(self._ref_units),
        }

    def _signal_receipt(self, boot_id: str) -> dict[str, Any]:
        return {
            "schema": SIGNAL_RECEIPT_SCHEMA,
            "boot_id": boot_id,
            "manager_owner": self.manager.owner,
            "signals": [
                {
                    "ordinal": str(signal.ordinal),
                    "member": signal.member,
                    "signature": signal.signature,
                    "body": _signal_body(signal.signature, signal.body),
                    "object_path": signal.object_path,
                    "sender": signal.sender,
                }
                for signal in self.signals
            ],
        }


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] != "--manifest":
        raise HarnessError("usage: generic_backend_systemd_harness.py --manifest MANIFEST.json")
    manifest = decode_manifest(Path(argv[2]))
    authority = manifest.prevalidate(require_root=True)
    object_paths = dict(authority["objects"])
    harness = FormalSystemHarness(
        manifest,
        DBusSystemManager(allowed_unit_objects=object_paths),
        SystemJournal(),
        prevalidated_authority=authority,
    )
    harness.run()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except HarnessError as exc:
        print(f"generic-backend-systemd-harness: {exc}", file=sys.stderr)
        raise SystemExit(64) from exc
