from __future__ import annotations

import ast
from pathlib import Path

import scion.runtime.execution as execution


def test_public_surface_is_explicit_typed_exports_only() -> None:
    expected = {
        "BackendOpenFailure",
        "BackendOpenPhase",
        "BackendOpenReason",
        "BackendStateError",
        "BlockedSpawn",
        "CapturedStream",
        "CgroupEventsFact",
        "CgroupIdentity",
        "CgroupIntegrityError",
        "CgroupStateError",
        "CgroupValidationError",
        "ChildCreation",
        "ClosedSpawnObservation",
        "ConfiguredUnitProperties",
        "ContainedSpawnFailure",
        "ContainedSpawnPhase",
        "ContainedSpawnReason",
        "FilesystemIdentity",
        "GenericProcessSpec",
        "InvocationLineage",
        "JobCgroupKey",
        "LeaderOutcome",
        "ModelValidationError",
        "PreHandleFailure",
        "PreHandlePhase",
        "PreHandleReason",
        "ProcessIdentity",
        "ServiceCgroup",
        "ServiceCgroupLineage",
        "SettledJob",
        "SpawnBackend",
        "StopPostEnvironment",
        "StopPostTopology",
        "StreamAvailability",
        "Systemd255ContractError",
        "UnitHandoffProperties",
        "UnitRole",
        "WaitFact",
        "validate_run_close_pair",
        "validate_same_invocation",
    }
    assert set(execution.__all__) == expected
    assert all(getattr(execution, name) is not None for name in expected)
    assert not hasattr(execution, "_SettledJobCleanupPermit")
    assert not hasattr(execution, "_issue_cleanup_permit_for_tests")


def test_public_surface_contains_imports_and_all_only() -> None:
    source_path = Path(execution.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    assert all(
        isinstance(node, (ast.Expr, ast.ImportFrom, ast.Assign))
        for node in tree.body
    )
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    assert calls == []
