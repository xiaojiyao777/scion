from __future__ import annotations

from dataclasses import FrozenInstanceError
import copy
from pathlib import Path

import pytest

from scion.runtime.execution.systemd255 import (
    ConfiguredUnitProperties,
    InvocationLineage,
    StopPostEnvironment,
    StopPostTopology,
    Systemd255ContractError,
    UnitHandoffProperties,
    UnitRole,
    validate_run_close_pair,
    validate_same_invocation,
)


RUN = "research-run@abc.service"
CLOSER = "research-close@abc.service"
INVOCATION = "0123456789abcdef0123456789abcdef"


def run_directives() -> dict[str, str]:
    return {
        "Delegate": "pids",
        "DelegateSubgroup": "supervisor",
        "CollectMode": "inactive",
        "Restart": "no",
        "KillMode": "control-group",
        "TimeoutStopSec": "infinity",
        "OnSuccess": CLOSER,
        "OnFailure": CLOSER,
    }


def run_expanded_properties() -> dict[str, str]:
    return {
        "Id": RUN,
        "Delegate": "yes",
        "DelegateControllers": "pids",
        "DelegateSubgroup": "supervisor",
        "CollectMode": "inactive",
        "Restart": "no",
        "KillMode": "control-group",
        "TimeoutStopUSec": "infinity",
        "OnSuccess": CLOSER,
        "OnFailure": CLOSER,
    }


def closer_directives() -> dict[str, str]:
    return {
        "CollectMode": "inactive",
        "Restart": "no",
        "TimeoutStartSec": "infinity",
        "After": RUN,
    }


def closer_expanded_properties() -> dict[str, str]:
    return {
        "Id": CLOSER,
        "CollectMode": "inactive",
        "Restart": "no",
        "TimeoutStartUSec": "infinity",
        "After": f"basic.target {RUN}",
    }


def lineage_properties() -> dict[str, str]:
    return {
        "BootID": "01234567-89ab-cdef-0123-456789abcdef",
        "Id": RUN,
        "InvocationID": INVOCATION,
        "ControlGroup": "/generated.slice/research-run@abc.service",
        "ServiceDevice": "31",
        "ServiceInode": "101",
        "SupervisorDevice": "31",
        "SupervisorInode": "102",
        "MainPID": "5001",
        "MainStartTime": "9000001",
    }


def handoff_properties() -> dict[str, str]:
    return {
        "Id": RUN,
        "InvocationID": INVOCATION,
        "LoadState": "loaded",
        "ActiveState": "inactive",
        "SubState": "dead",
        "Result": "success",
        "ExecMainCode": "1",
        "ExecMainStatus": "0",
        "ExecStopPostCode": "1",
        "ExecStopPostStatus": "0",
    }


def test_configured_run_and_closer_are_exact_reciprocal_facts() -> None:
    run = ConfiguredUnitProperties.from_receipts(
        UnitRole.RUN,
        run_directives(),
        run_expanded_properties(),
        expected_unit=RUN,
        expected_peer=CLOSER,
    )
    closer = ConfiguredUnitProperties.from_receipts(
        UnitRole.CLOSER,
        closer_directives(),
        closer_expanded_properties(),
        expected_unit=CLOSER,
        expected_peer=RUN,
    )

    validate_run_close_pair(run, closer)
    assert run.delegate == "pids"
    assert run.delegate_effective == "yes"
    assert run.delegate_controllers == ("pids",)
    assert run.timeout_stop_sec == "infinity"
    assert run.timeout_stop_usec == "infinity"
    assert run.delegate_subgroup == "supervisor"
    assert closer.after == ("basic.target", RUN)


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("Delegate", "yes"),
        ("Delegate", "pids memory"),
        ("DelegateSubgroup", ""),
        ("CollectMode", "inactive-or-failed"),
        ("Restart", "on-failure"),
        ("KillMode", "process"),
        ("TimeoutStopSec", "90s"),
        ("OnSuccess", "other.service"),
        ("OnFailure", "other.service"),
    ],
)
def test_run_rejects_every_relaxed_property(field: str, bad: str) -> None:
    directives = run_directives()
    directives[field] = bad
    with pytest.raises(Systemd255ContractError):
        ConfiguredUnitProperties.from_receipts(
            UnitRole.RUN,
            directives,
            run_expanded_properties(),
            expected_unit=RUN,
            expected_peer=CLOSER,
        )


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("Delegate", "pids"),
        ("Delegate", "no"),
        ("DelegateControllers", "pids memory"),
        ("DelegateSubgroup", ""),
        ("CollectMode", "inactive-or-failed"),
        ("Restart", "on-failure"),
        ("KillMode", "process"),
        ("TimeoutStopUSec", "90000000"),
        ("OnSuccess", "other.service"),
        ("OnFailure", "other.service"),
    ],
)
def test_run_rejects_non_host_shaped_or_relaxed_expanded_property(
    field: str, bad: str
) -> None:
    expanded = run_expanded_properties()
    expanded[field] = bad
    with pytest.raises(Systemd255ContractError):
        ConfiguredUnitProperties.from_receipts(
            UnitRole.RUN,
            run_directives(),
            expanded,
            expected_unit=RUN,
            expected_peer=CLOSER,
        )


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("CollectMode", "inactive-or-failed"),
        ("Restart", "on-failure"),
        ("TimeoutStartSec", "1min"),
        ("After", "basic.target"),
    ],
)
def test_closer_rejects_every_relaxed_property(field: str, bad: str) -> None:
    directives = closer_directives()
    directives[field] = bad
    with pytest.raises(Systemd255ContractError):
        ConfiguredUnitProperties.from_receipts(
            UnitRole.CLOSER,
            directives,
            closer_expanded_properties(),
            expected_unit=CLOSER,
            expected_peer=RUN,
        )


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("CollectMode", "inactive-or-failed"),
        ("Restart", "on-failure"),
        ("TimeoutStartUSec", "90000000"),
        ("After", "basic.target"),
    ],
)
def test_closer_rejects_relaxed_expanded_property(field: str, bad: str) -> None:
    expanded = closer_expanded_properties()
    expanded[field] = bad
    with pytest.raises(Systemd255ContractError):
        ConfiguredUnitProperties.from_receipts(
            UnitRole.CLOSER,
            closer_directives(),
            expanded,
            expected_unit=CLOSER,
            expected_peer=RUN,
        )


def test_configured_properties_reject_schema_duplicates_and_role_coercion() -> None:
    missing = run_directives()
    missing.pop("Restart")
    unknown = run_directives()
    unknown["ResetFailed"] = "no"
    duplicate = list(run_directives().items()) + [("Restart", "no")]
    for directives in (missing, unknown, duplicate):
        with pytest.raises(Systemd255ContractError):
            ConfiguredUnitProperties.from_receipts(
                UnitRole.RUN,
                directives,
                run_expanded_properties(),
                expected_unit=RUN,
                expected_peer=CLOSER,
            )
    with pytest.raises(Systemd255ContractError):
        ConfiguredUnitProperties.from_receipts(  # type: ignore[arg-type]
            "RUN",
            run_directives(),
            run_expanded_properties(),
            expected_unit=RUN,
            expected_peer=CLOSER,
        )


def test_configured_pair_rejects_wrong_order_or_unrelated_peer() -> None:
    run = ConfiguredUnitProperties.from_receipts(
        UnitRole.RUN,
        run_directives(),
        run_expanded_properties(),
        expected_unit=RUN,
        expected_peer=CLOSER,
    )
    closer = ConfiguredUnitProperties.from_receipts(
        UnitRole.CLOSER,
        closer_directives(),
        closer_expanded_properties(),
        expected_unit=CLOSER,
        expected_peer=RUN,
    )
    with pytest.raises(Systemd255ContractError):
        validate_run_close_pair(closer, run)

    other = closer_expanded_properties()
    other["Id"] = "other-close.service"
    mismatched = ConfiguredUnitProperties.from_receipts(
        UnitRole.CLOSER,
        closer_directives(),
        other,
        expected_unit="other-close.service",
        expected_peer=RUN,
    )
    with pytest.raises(Systemd255ContractError):
        validate_run_close_pair(run, mismatched)


def test_invocation_lineage_decodes_exact_copied_identity() -> None:
    lineage = InvocationLineage.from_properties(lineage_properties())
    assert lineage.main_pid == 5001
    assert lineage.control_group.endswith(RUN)


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("BootID", "0123456789abcdef0123456789abcdef"),
        ("InvocationID", ""),
        ("InvocationID", INVOCATION.upper()),
        ("ControlGroup", "generated.slice/run.service"),
        ("ControlGroup", "/generated.slice/../run.service"),
        ("ControlGroup", "/generated.slice/run.service/supervisor"),
        ("ServiceDevice", "01"),
        ("ServiceInode", "-1"),
        ("SupervisorInode", "0"),
        ("MainPID", "0"),
        ("MainStartTime", "1.0"),
    ],
)
def test_invocation_lineage_rejects_noncanonical_fields(field: str, bad: str) -> None:
    properties = lineage_properties()
    properties[field] = bad
    with pytest.raises(Systemd255ContractError):
        InvocationLineage.from_properties(properties)


def test_invocation_lineage_rejects_same_service_and_supervisor_inode() -> None:
    properties = lineage_properties()
    properties["SupervisorInode"] = properties["ServiceInode"]
    with pytest.raises(Systemd255ContractError):
        InvocationLineage.from_properties(properties)


def test_stop_post_environment_retains_literal_selector_values() -> None:
    environment = StopPostEnvironment.from_environment(
        {
            "INVOCATION_ID": INVOCATION,
            "SERVICE_RESULT": "exit-code",
            "EXIT_CODE": "exited",
            "EXIT_STATUS": "23",
        }
    )
    assert environment.service_result == "exit-code"
    assert environment.exit_status == "23"


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("INVOCATION_ID", ""),
        ("SERVICE_RESULT", ""),
        ("EXIT_CODE", "exited killed"),
        ("EXIT_STATUS", "TERM\nforged"),
    ],
)
def test_stop_post_environment_rejects_empty_or_nonliteral_values(
    field: str, bad: str
) -> None:
    properties = {
        "INVOCATION_ID": INVOCATION,
        "SERVICE_RESULT": "success",
        "EXIT_CODE": "exited",
        "EXIT_STATUS": "0",
    }
    properties[field] = bad
    with pytest.raises(Systemd255ContractError):
        StopPostEnvironment.from_environment(properties)


def test_stop_post_topology_requires_only_sealer_and_empty_process_sets() -> None:
    topology = StopPostTopology.from_mapping(
        {
            "ServiceControlGroup": "/generated.slice/research-run@abc.service",
            "ControlGroup": "/generated.slice/research-run@abc.service/.control",
            "SealerPID": "6001",
            "SealerStartTime": "9001000",
            "ControlPIDs": "6001",
            "SupervisorPIDs": "",
            "JobCgroups": "job-0-0123456789abcdef job-1-0123456789abcdef",
            "JobPIDs": "",
        }
    )
    assert topology.control_pids == (6001,)
    assert topology.job_cgroups == (
        "job-0-0123456789abcdef",
        "job-1-0123456789abcdef",
    )


def test_stop_post_topology_rejects_job_ordinal_beyond_uint64() -> None:
    with pytest.raises(Systemd255ContractError):
        StopPostTopology.from_mapping(
            {
                "ServiceControlGroup": "/generated.slice/research-run@abc.service",
                "ControlGroup": "/generated.slice/research-run@abc.service/.control",
                "SealerPID": "6001",
                "SealerStartTime": "9001000",
                "ControlPIDs": "6001",
                "SupervisorPIDs": "",
                "JobCgroups": "job-18446744073709551616-0123456789abcdef",
                "JobPIDs": "",
            }
        )


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("ControlGroup", "/generated.slice/research-run@abc.service/supervisor"),
        ("ControlPIDs", "6001 6002"),
        ("SupervisorPIDs", "5001"),
        ("JobPIDs", "7001"),
        ("JobCgroups", "job-01-0123456789abcdef"),
        ("JobCgroups", "job-1-0123456789abcdef job-0-0123456789abcdef"),
    ],
)
def test_stop_post_topology_rejects_extra_or_ambiguous_authority(
    field: str, bad: str
) -> None:
    properties = {
        "ServiceControlGroup": "/generated.slice/research-run@abc.service",
        "ControlGroup": "/generated.slice/research-run@abc.service/.control",
        "SealerPID": "6001",
        "SealerStartTime": "9001000",
        "ControlPIDs": "6001",
        "SupervisorPIDs": "",
        "JobCgroups": "",
        "JobPIDs": "",
    }
    properties[field] = bad
    with pytest.raises(Systemd255ContractError):
        StopPostTopology.from_mapping(properties)


def test_unit_handoff_accepts_executed_final_source() -> None:
    handoff = UnitHandoffProperties.from_properties(
        handoff_properties(), expected_unit=RUN
    )
    assert handoff.exec_main_status == 0
    assert handoff.result == "success"


def test_unit_handoff_accepts_retained_failed_source_with_exact_status() -> None:
    properties = handoff_properties()
    properties.update(
        {
            "ActiveState": "failed",
            "SubState": "failed",
            "Result": "exit-code",
            "ExecStopPostStatus": "1",
        }
    )
    handoff = UnitHandoffProperties.from_properties(properties, expected_unit=RUN)
    assert handoff.active_state == "failed"
    assert handoff.exec_stop_post_status == 1


def test_unit_handoff_accepts_signal_fact_without_inventing_result_mapping() -> None:
    properties = handoff_properties()
    properties.update(
        {
            "ActiveState": "failed",
            "SubState": "failed",
            "Result": "watchdog",
            "ExecMainCode": "2",
            "ExecMainStatus": "9",
        }
    )
    handoff = UnitHandoffProperties.from_properties(properties, expected_unit=RUN)
    assert handoff.exec_main_code == 2
    assert handoff.result == "watchdog"


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("InvocationID", ""),
        ("LoadState", "not-found"),
        ("ActiveState", "active"),
        ("SubState", "running"),
        ("Result", ""),
        ("ExecMainCode", "0"),
        ("ExecMainStatus", "-1"),
        ("ExecStopPostCode", "0"),
        ("ExecStopPostStatus", "01"),
        ("ExecMainCode", "4"),
        ("ExecMainCode", "5"),
        ("ExecStopPostCode", "4"),
        ("ExecStopPostCode", "6"),
    ],
)
def test_unit_handoff_rejects_gc_defaults_and_nonfinal_facts(
    field: str, bad: str
) -> None:
    properties = handoff_properties()
    properties[field] = bad
    with pytest.raises(Systemd255ContractError):
        UnitHandoffProperties.from_properties(properties, expected_unit=RUN)


@pytest.mark.parametrize(
    "changes",
    [
        {"ExecMainCode": "2", "ExecMainStatus": "15"},
        {"ExecStopPostStatus": "1"},
        {"ActiveState": "failed", "SubState": "failed"},
    ],
)
def test_success_handoff_rejects_signal_failure_or_failed_state(
    changes: dict[str, str]
) -> None:
    properties = handoff_properties()
    properties.update(changes)
    with pytest.raises(Systemd255ContractError):
        UnitHandoffProperties.from_properties(properties, expected_unit=RUN)


@pytest.mark.parametrize(
    ("active_state", "sub_state"),
    [("inactive", "failed"), ("failed", "dead")],
)
def test_failed_handoff_rejects_mixed_final_states(
    active_state: str, sub_state: str
) -> None:
    properties = handoff_properties()
    properties.update(
        {
            "ActiveState": active_state,
            "SubState": sub_state,
            "Result": "exit-code",
            "ExecStopPostStatus": "1",
        }
    )
    with pytest.raises(Systemd255ContractError):
        UnitHandoffProperties.from_properties(properties, expected_unit=RUN)


def test_failed_handoff_requires_nonzero_exit_or_signal_fact() -> None:
    properties = handoff_properties()
    properties.update(
        {"ActiveState": "failed", "SubState": "failed", "Result": "exit-code"}
    )
    with pytest.raises(Systemd255ContractError):
        UnitHandoffProperties.from_properties(properties, expected_unit=RUN)


@pytest.mark.parametrize("signal_status", ["0", "65", "255"])
@pytest.mark.parametrize("code_field", ["ExecMainCode", "ExecStopPostCode"])
def test_signal_wait_code_requires_valid_signal_status(
    code_field: str, signal_status: str
) -> None:
    properties = handoff_properties()
    status_field = code_field.removesuffix("Code") + "Status"
    properties.update(
        {
            "ActiveState": "failed",
            "SubState": "failed",
            "Result": "signal",
            code_field: "2",
            status_field: signal_status,
        }
    )
    with pytest.raises(Systemd255ContractError):
        UnitHandoffProperties.from_properties(properties, expected_unit=RUN)


def test_same_invocation_requires_exact_source_and_identity() -> None:
    lineage = InvocationLineage.from_properties(lineage_properties())
    stop_post = StopPostEnvironment.from_environment(
        {
            "INVOCATION_ID": INVOCATION,
            "SERVICE_RESULT": "success",
            "EXIT_CODE": "exited",
            "EXIT_STATUS": "0",
        }
    )
    handoff = UnitHandoffProperties.from_properties(
        handoff_properties(), expected_unit=RUN
    )
    validate_same_invocation(lineage, stop_post, handoff)

    mismatched_environment = StopPostEnvironment.from_environment(
        {
            "INVOCATION_ID": "fedcba9876543210fedcba9876543210",
            "SERVICE_RESULT": "success",
            "EXIT_CODE": "exited",
            "EXIT_STATUS": "0",
        }
    )
    with pytest.raises(Systemd255ContractError):
        validate_same_invocation(lineage, mismatched_environment, handoff)

    other_handoff = handoff_properties()
    other_handoff["Id"] = "other-run.service"
    with pytest.raises(Systemd255ContractError):
        validate_same_invocation(
            lineage,
            stop_post,
            UnitHandoffProperties.from_properties(
                other_handoff, expected_unit="other-run.service"
            ),
        )


def test_facts_are_frozen_slot_backed_and_final() -> None:
    fact = InvocationLineage.from_properties(lineage_properties())
    assert not hasattr(fact, "__dict__")
    assert copy.copy(fact) == fact
    with pytest.raises(FrozenInstanceError):
        fact.main_pid = 1  # type: ignore[misc]
    with pytest.raises(TypeError):

        class Forbidden(InvocationLineage):
            pass


def test_invalid_utf8_surrogate_and_non_string_values_are_rejected() -> None:
    invalid_text = run_expanded_properties()
    invalid_text["Id"] = "bad\ud800.service"
    with pytest.raises(Systemd255ContractError):
        ConfiguredUnitProperties.from_receipts(
            UnitRole.RUN,
            run_directives(),
            invalid_text,
            expected_unit=RUN,
            expected_peer=CLOSER,
        )

    invalid_type: dict[str, object] = run_directives()
    invalid_type["Restart"] = True
    with pytest.raises(Systemd255ContractError):
        ConfiguredUnitProperties.from_receipts(  # type: ignore[arg-type]
            UnitRole.RUN,
            invalid_type,
            run_expanded_properties(),
            expected_unit=RUN,
            expected_peer=CLOSER,
        )


def test_module_is_pure_and_has_no_systemd_or_process_invocation_surface() -> None:
    source = Path(__file__).parents[4] / "runtime" / "execution" / "systemd255.py"
    text = source.read_text(encoding="utf-8")
    for forbidden in (
        "import subprocess",
        "systemctl",
        "systemd-run",
        "StartUnit",
        "Popen",
        "reset-failed",
        "publish",
    ):
        assert forbidden not in text
