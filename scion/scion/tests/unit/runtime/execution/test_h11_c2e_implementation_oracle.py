from __future__ import annotations

import ast
from collections import Counter, deque
from dataclasses import dataclass, replace
from functools import lru_cache
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import threading
from types import SimpleNamespace
from typing import Any, Iterable, Iterator, Literal, Sequence

import pytest


FIXTURES = Path(__file__).parents[3] / "fixtures" / "runtime" / "execution"
INSTALLER_SOURCE = FIXTURES / "generic_backend_root_installer.py"
DESIGN = (
    Path(__file__).parents[5]
    / "docs"
    / "planning"
    / "v0.4"
    / "v0.4-w3-h11-c2e-implementation-oracle-design-20260720.md"
)
DESIGN_SHA256 = "a30f8858873c69d8d2e34b3827325f6c34ae09e1096e43b0048848283f7ffd7b"
M = "generic_backend_root_installer"
ROOT_QNAME = f"{M}.authorize_h11_release"

LEGACY_MODULE_SYMBOLS = (
    "H11RootAuthorizerSession",
    "H11RootAuthorizerReadyClosure",
    "H11RootAuthorizedPermit",
    "RetainedH11RootDirectory",
    "RetainedH11RootFifo",
    "RetainedH11RootJsonSource",
    "RetainedH11RootPresentOutput",
    "RetainedH11RootPublication",
    "H11RootRetainedAuthority",
    "_commit_h11_authorized_permit",
    "_close_h11_ownership",
    "_publish_h11_named_staging",
    "_open_h11_named_staging",
    "_complete_h11_named_staging",
)
LEGACY_CLASS_ATTRIBUTES = (
    ("H11RootValidatedFifo", "from_tree_row"),
)


@lru_cache(maxsize=1)
def _load_installer() -> Any:
    name = "_fixture_generic_backend_root_installer_c2e"
    spec = importlib.util.spec_from_file_location(name, INSTALLER_SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def _load_accepted_fixture_tests() -> Any:
    path = Path(__file__).with_name("test_formal_fixture_systemd.py")
    name = "_h11_c2e_accepted_formal_fixture_tests"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


TargetKind = Literal["internal", "sensitive", "pure-value"]


@dataclass(frozen=True, slots=True)
class H11ResolvedCall:
    caller_qname: str
    target_kind: TargetKind
    canonical_target: str
    lexical_target: str
    same_caller_occurrence: int
    rule_id: str


@dataclass(frozen=True, slots=True)
class H11ScanFailure:
    caller_qname: str
    lexical_target: str
    reason: str


@dataclass(frozen=True, slots=True)
class H11ScanResult:
    calls: tuple[H11ResolvedCall, ...]
    unresolved: tuple[H11ScanFailure, ...]
    multi_target: tuple[H11ScanFailure, ...]
    unclassified: tuple[H11ScanFailure, ...]
    reachable_ast_call_count: int

    @property
    def resolved_call_count(self) -> int:
        return len(self.calls)


PURE_VALUE_NAMES = frozenset(
    {
        "builtins.any",
        "builtins.bool",
        "builtins.bytes",
        "builtins.bytes.decode",
        "builtins.bytes.join",
        "builtins.dict",
        "builtins.dict.get",
        "builtins.dict.items",
        "builtins.dict.values",
        "builtins.enumerate",
        "builtins.format",
        "builtins.int",
        "builtins.len",
        "builtins.list",
        "builtins.list.append",
        "builtins.memoryview",
        "builtins.object.__setattr__",
        "builtins.ord",
        "builtins.range",
        "builtins.set",
        "builtins.set.add",
        "builtins.set.issubset",
        "builtins.set.update",
        "builtins.sorted",
        "builtins.str",
        "builtins.str.encode",
        "builtins.str.isalnum",
        "builtins.str.isascii",
        "builtins.str.join",
        "builtins.str.split",
        "builtins.str.startswith",
        "builtins.tuple",
        "builtins.type",
        "builtins.zip",
        "hashlib.sha256",
        "hashlib.sha256.hexdigest",
        "json.dumps",
        "json.loads",
        "os.path.commonpath",
        "os.strerror",
        "pathlib.Path",
        "pathlib.Path.is_absolute",
        "re.fullmatch",
        "stat.S_IFMT",
        "stat.S_IMODE",
        "stat.S_ISDIR",
        "stat.S_ISFIFO",
        "stat.S_ISREG",
        f"{M}.H11RootClosedPartition.__init__",
        f"{M}.H11RootCommitReceipt.__init__",
        f"{M}.H11RootDirectoryReference.__init__",
        f"{M}.H11RootFifoReference.__init__",
        f"{M}.H11RootIndirectAuthoritySpec.__init__",
        f"{M}.H11RootNamedStagingPlan.__init__",
        f"{M}.H11RootObservedPathIdentity.__init__",
        f"{M}.H11RootPrePermitBarrier.__init__",
        f"{M}.H11RootRolePath.__init__",
        f"{M}.H11RootTransactionState.__init__",
        f"{M}.H11RootValidatedFifo.__init__",
        f"{M}.InstallerError",
    }
)


SENSITIVE_NAMES = frozenset(
    {
        "builtins.BaseException.add_note",
        "builtins.bytes.decode",
        "builtins.str.encode",
        "ctypes.CDLL",
        "ctypes.CDLL.renameat2",
        "ctypes.get_errno",
        "ctypes.set_errno",
        "json.dumps",
        "json.loads",
        "os.close",
        "os.fchmod",
        "os.fstat",
        "os.fsync",
        "os.getegid",
        "os.geteuid",
        "os.lseek",
        "os.open",
        "os.read",
        "os.stat",
        "os.write",
        "pathlib.Path.lstat",
        "pathlib.Path.resolve",
    }
)


SCALAR_HELPER_ALLOWED_CALLERS = frozenset(
    {
        f"{M}._prove_h11_direct_authority_bindings",
        f"{M}._build_h11_tree_indirect_specs",
        f"{M}._build_h11_seal_indirect_specs",
        f"{M}._prove_h11_preflight_snapshot_bindings",
        f"{M}._build_h11_install_target_specs",
    }
)
SCALAR_HELPERS = frozenset(
    {
        f"{M}._h11_exact_object_fields",
        f"{M}._h11_object_member",
        f"{M}._h11_text",
        f"{M}._h11_uint",
        f"{M}._h11_path",
        f"{M}._h11_sha256_text",
    }
)


CORRECTION_INTERNAL_EDGES = (
    (f"{M}.H11RootAuthorizationFlow._acquire_authorities", f"{M}._decode_h11_canonical_frozen_object", 9),
    (f"{M}.H11RootAuthorizationFlow._acquire_authorities", f"{M}._prove_h11_execution_authority", 1),
    (f"{M}.H11RootAuthorizationFlow._acquire_authorities", f"{M}._build_h11_indirect_authority_inventory", 1),
    (f"{M}._build_h11_indirect_authority_inventory", f"{M}._prove_h11_direct_authority_bindings", 1),
    (f"{M}._build_h11_indirect_authority_inventory", f"{M}._build_h11_tree_indirect_specs", 1),
    (f"{M}._build_h11_indirect_authority_inventory", f"{M}._build_h11_seal_indirect_specs", 1),
    (f"{M}._build_h11_indirect_authority_inventory", f"{M}._prove_h11_preflight_snapshot_bindings", 1),
    (f"{M}._build_h11_indirect_authority_inventory", f"{M}._build_h11_install_target_specs", 1),
    (f"{M}._build_h11_tree_indirect_specs", f"{M}._make_h11_indirect_authority_spec", 1),
    (f"{M}._build_h11_seal_indirect_specs", f"{M}._make_h11_indirect_authority_spec", 1),
    (f"{M}._build_h11_install_target_specs", f"{M}._make_h11_indirect_authority_spec", 1),
    (f"{M}._build_h11_install_target_specs", f"{M}._systemd_unit_object_path", 1),
    (f"{M}.H11RootAuthorizationFlow._acquire_authorities", f"{M}._observe_h11_indirect_authority", 1),
    (f"{M}.H11RootAuthorizationFlow._acquire_authorities", f"{M}._prove_h11_indirect_observations", 1),
)


FLOW_INTERNAL_EDGES = (
    (f"{M}.authorize_h11_release", f"{M}.H11RootAuthorizationFlow.__init__", 1),
    (f"{M}.authorize_h11_release", f"{M}.H11RootAuthorizationFlow.authorize_once", 1),
    (f"{M}.H11RootAuthorizationFlow.authorize_once", f"{M}.H11RootAuthorizationFlow._acquire_authorities", 1),
    (f"{M}.H11RootAuthorizationFlow.authorize_once", f"{M}.H11RootAuthorizationFlow._consume_ready_commit", 1),
    (f"{M}.H11RootAuthorizationFlow.authorize_once", f"{M}.H11RootAuthorizationFlow._publish_permit", 1),
    (f"{M}.H11RootAuthorizationFlow.authorize_once", f"{M}.H11RootAuthorizationFlow._commit_permit", 1),
    (f"{M}.H11RootAuthorizationFlow.authorize_once", f"{M}.H11RootAuthorizationFlow._fail", 1),
    (f"{M}.H11RootAuthorizationFlow.authorize_once", f"{M}.H11RootAuthorizationFlow._finish", 1),
    (f"{M}.H11RootAuthorizationFlow._consume_ready_commit", f"{M}.H11RootAuthorizationFlow._close_slot_once", 1),
    (f"{M}.H11RootAuthorizationFlow._commit_permit", f"{M}.H11RootAuthorizationFlow._close_slot_once", 1),
    (f"{M}.H11RootAuthorizationFlow._fail", f"{M}.H11RootAuthorizationFlow._sweep_slots", 1),
    (f"{M}.H11RootAuthorizationFlow._finish", f"{M}.H11RootAuthorizationFlow._sweep_slots", 1),
    (f"{M}.H11RootAuthorizationFlow.close", f"{M}.H11RootAuthorizationFlow._sweep_slots", 1),
    (f"{M}.H11RootAuthorizationFlow._sweep_slots", f"{M}.H11RootAuthorizationFlow._close_slot_once", 1),
    (f"{M}.H11RootAuthorizationFlow._commit_permit", f"{M}.H11RootAuthorizationFlow._mark_write_in_flight", 1),
    (f"{M}.H11RootAuthorizationFlow._commit_permit", f"{M}.H11RootAuthorizationFlow._mark_postwrite", 1),
    (f"{M}.H11RootAuthorizationFlow._acquire_authorities", f"{M}.H11RootDirectoryReference.decode", 7),
    (f"{M}.H11RootAuthorizationFlow._acquire_authorities", f"{M}.H11RootFifoReference.decode", 2),
    (f"{M}.H11RootAuthorizationFlow._acquire_authorities", f"{M}.H11RootDirectoryView.revalidate", 21),
    (f"{M}.H11RootAuthorizationFlow._acquire_authorities", f"{M}.H11RootFifoView.revalidate", 6),
    (f"{M}.H11RootAuthorizationFlow._acquire_authorities", f"{M}.H11RootJsonSourceView.revalidate", 18),
    (f"{M}.H11RootDirectoryView.revalidate", f"{M}.H11RootDirectoryReference.prove", 2),
    (f"{M}.H11RootFifoView.revalidate", f"{M}.H11RootFifoReference.prove", 2),
)

CODEC_INTERNAL_EDGES = (
    (f"{M}._decode_h11_canonical_frozen_object", f"{M}._freeze_h11_json_value", 1),
    (f"{M}._freeze_h11_json_value", f"{M}._freeze_h11_json_value", 2),
)

EXPECTED_INTERNAL_QNAMES = frozenset(
    {ROOT_QNAME, *SCALAR_HELPERS}
    | {
        caller
        for caller, _callee, _count in (
            *FLOW_INTERNAL_EDGES,
            *CORRECTION_INTERNAL_EDGES,
            *CODEC_INTERNAL_EDGES,
        )
    }
    | {
        callee
        for _caller, callee, _count in (
            *FLOW_INTERNAL_EDGES,
            *CORRECTION_INTERNAL_EDGES,
            *CODEC_INTERNAL_EDGES,
        )
    }
    | {
        f"{M}.H11OwnedFdSlot._bind",
        f"{M}.H11OwnedFdSlot.open",
        f"{M}.H11OwnedFdSlot.borrow",
        f"{M}.H11OwnedFdSlot.detach",
    }
)

_FROZEN_FIELD_METHODS = {
    ("H11RootDirectoryView", "_slot", "borrow"): f"{M}.H11OwnedFdSlot.borrow",
    ("H11RootDirectoryView", "_parent_slot", "borrow"): f"{M}.H11OwnedFdSlot.borrow",
    ("H11RootDirectoryView", "reference", "prove"): f"{M}.H11RootDirectoryReference.prove",
    ("H11RootFifoView", "_slot", "borrow"): f"{M}.H11OwnedFdSlot.borrow",
    ("H11RootFifoView", "_parent_slot", "borrow"): f"{M}.H11OwnedFdSlot.borrow",
    ("H11RootFifoView", "reference", "prove"): f"{M}.H11RootFifoReference.prove",
    ("H11RootJsonSourceView", "_slot", "borrow"): f"{M}.H11OwnedFdSlot.borrow",
    ("H11RootJsonSourceView", "_parent_slot", "borrow"): f"{M}.H11OwnedFdSlot.borrow",
    ("H11RootPresentOutputView", "_slot", "borrow"): f"{M}.H11OwnedFdSlot.borrow",
    ("H11RootPresentOutputView", "_parent_slot", "borrow"): f"{M}.H11OwnedFdSlot.borrow",
    ("H11RootPublicationView", "_slot", "borrow"): f"{M}.H11OwnedFdSlot.borrow",
    ("H11RootPublicationView", "_parent_slot", "borrow"): f"{M}.H11OwnedFdSlot.borrow",
}

_MONO_PARAM_CLASSES = {
    (f"{M}.H11RootAuthorizationFlow._close_slot_once", "slot"): "H11OwnedFdSlot",
}

C2E_BINDING_FORMS = frozenset(
    {
        "arguments",
        "Assign",
        "AnnAssign",
        "AugAssign",
        "NamedExpr",
        "For.target",
        "AsyncFor.target",
        "comprehension.target",
        "With.optional_vars",
        "AsyncWith.optional_vars",
        "ExceptHandler.name",
        "Import",
        "ImportFrom",
        "destructure",
        "Delete",
        "MatchAs.name",
        "MatchStar.name",
        "MatchMapping.rest",
        "FunctionDef.name",
        "FunctionDef.type_params",
        "AsyncFunctionDef.name",
        "AsyncFunctionDef.type_params",
        "ClassDef.name",
        "ClassDef.type_params",
        "TypeAlias.name",
        "TypeAlias.type_params",
        "Global",
        "Nonlocal",
    }
)

_EXPLICIT_FROZEN_FIELDS = {
    "H11RootDirectoryView": ("_flow", "_slot", "_parent_slot", "reference", "child_name"),
    "H11RootFifoView": ("_flow", "_slot", "_parent_slot", "role", "reference"),
    "H11RootJsonSourceView": ("_flow", "_slot", "_parent_slot", "path", "raw", "source", "label", "child_name"),
    "H11RootPresentOutputView": ("_flow", "_slot", "_parent_slot", "role", "path", "raw", "reference_items"),
    "H11RootPublicationView": ("_flow", "_slot", "_parent_slot", "final_name", "raw", "reference_items"),
    "H11RootAuthorityView": (
        "_flow", "authorization_view", "harness_manifest_view", "install_receipt_view",
        "install_manifest_view", "tree_receipt_view", "seal_receipt_view",
        "preflight_receipt_view", "permit_ready_view", "run_armed_view",
        "formal_root_directory", "authority_root_directory", "harness_root_directory",
        "scenario_root_directory", "input_root_directory", "receipt_root_directory",
        "fifo_root_directory", "ready_commit_fifo", "permit_commit_fifo",
        "authorization_manifest", "harness_manifest", "ready_receipt", "armed_receipt",
        "fixture_uid", "fixture_gid", "validated_fifos",
    ),
    "H11RootAuthorityPhaseData": ("authority",),
    "H11RootReadyPhaseData": (
        "authority_data", "ready_commit", "partition", "present_h0",
        "present_run_main_properties", "transaction_state",
        "present_outputs_sha256", "future_absence_sha256",
    ),
    "H11RootPermitPhaseData": ("ready_data", "barrier", "publication", "transaction_state"),
}

_GENERATED_CLASS_FIELDS = {
    "H11RootDirectoryReference": ("role", "path", "device", "inode", "mode", "uid", "gid"),
    "H11RootFifoReference": ("path", "device", "inode", "mode", "uid", "gid", "accepted_owners"),
    "H11RootCommitReceipt": ("phase", "fifo", "payload_sha256", "byte_count"),
    "H11RootRolePath": ("role", "path"),
    "H11RootClosedPartition": (
        "present_prerequisites",
        "future_absence_inventory",
        "frozen_root",
        "input_future_absence",
        "receipt_future_absence",
    ),
    "H11RootTransactionState": ("role", "path", "state"),
    "H11RootValidatedFifo": ("role", "path", "owner", "uid", "gid", "mode", "device", "inode", "accepted_owners"),
    "H11RootNamedStagingPlan": ("parent", "staging_name", "final_name", "raw", "expected_owner", "require_root", "test_failure"),
    "H11RootPrePermitBarrier": (
        "directory_chain", "present_outputs_sha256", "future_absence_sha256",
        "transaction_state", "future_absence_inventory",
    ),
    "H11RootIndirectAuthoritySpec": (
        "semantic_role", "equivalence_class", "install_ordinal", "path", "kind",
        "device", "inode", "mode", "accepted_owners",
    ),
    "H11RootObservedPathIdentity": (
        "semantic_role", "equivalence_class", "install_ordinal", "path", "kind",
        "device", "inode", "mode", "uid", "gid",
    ),
}

_EXACT_NOMINAL_CLASSES = frozenset(
    {
        "H11OwnedFdSlot",
        "H11RootAuthorizationFlow",
        *_EXPLICIT_FROZEN_FIELDS,
        *_GENERATED_CLASS_FIELDS,
    }
)

_EXACT_CLASS_METHODS = {
    "H11OwnedFdSlot": ("__init__", "role", "open", "_bind", "borrow", "detach"),
    "H11RootAuthorizationFlow": (
        "__init__", "state", "_transition", "_mark_write_in_flight", "_mark_postwrite",
        "_close_slot_once", "_sweep_slots", "_fail", "_finish", "close",
        "_acquire_authorities", "_consume_ready_commit", "_publish_permit",
        "_commit_permit", "authorize_once",
    ),
    "H11RootDirectoryView": ("__init__", "revalidate"),
    "H11RootFifoView": ("__init__", "revalidate"),
    "H11RootJsonSourceView": ("__init__", "revalidate"),
    "H11RootPresentOutputView": ("__init__", "reference", "revalidate"),
    "H11RootPublicationView": ("__init__", "reference", "revalidate"),
    "H11RootAuthorityView": ("__init__",),
    "H11RootAuthorityPhaseData": ("__init__",),
    "H11RootReadyPhaseData": ("__init__",),
    "H11RootPermitPhaseData": ("__init__",),
    "H11RootDirectoryReference": ("decode", "parent_reference", "prove"),
    "H11RootFifoReference": ("decode", "reference", "prove"),
    "H11RootCommitReceipt": ("ready_committed", "permit_committed", "reference"),
    "H11RootRolePath": ("decode", "reference"),
    "H11RootClosedPartition": (),
    "H11RootTransactionState": ("reference",),
    "H11RootValidatedFifo": ("acquisition_reference",),
    "H11RootNamedStagingPlan": (),
    "H11RootPrePermitBarrier": (),
    "H11RootIndirectAuthoritySpec": (),
    "H11RootObservedPathIdentity": (),
}

_FACTORY_RESULTS = {
    f"{M}.H11RootDirectoryReference.decode": "H11RootDirectoryReference",
    f"{M}.H11RootFifoReference.decode": "H11RootFifoReference",
    f"{M}.H11RootCommitReceipt.ready_committed": "H11RootCommitReceipt",
    f"{M}.H11RootCommitReceipt.permit_committed": "H11RootCommitReceipt",
}

_FACTORY_SIGNATURES = {
    f"{M}.H11RootDirectoryReference.decode": (
        ("cls", "value"),
        ("label",),
        {"value": "H11RootFrozenJsonValue", "label": "str"},
        "H11RootDirectoryReference",
    ),
    f"{M}.H11RootFifoReference.decode": (
        ("cls", "value"),
        ("label", "require_root", "process_euid", "process_egid"),
        {
            "value": "H11RootFrozenJsonValue",
            "label": "str",
            "require_root": "bool",
            "process_euid": "int",
            "process_egid": "int",
        },
        "H11RootFifoReference",
    ),
    f"{M}.H11RootCommitReceipt.ready_committed": (
        ("cls", "fifo", "payload"),
        (),
        {"fifo": "H11RootFifoView", "payload": "bytes"},
        "H11RootCommitReceipt",
    ),
    f"{M}.H11RootCommitReceipt.permit_committed": (
        ("cls", "fifo", "payload"),
        (),
        {"fifo": "H11RootFifoView", "payload": "bytes"},
        "H11RootCommitReceipt",
    ),
}

_PHASE_CURSORS = {
    f"{M}.H11RootAuthorizationFlow._consume_ready_commit": (
        "AUTHORITIES_RETAINED",
        "H11RootAuthorityPhaseData",
        "H11 READY consume requires exact retained authority data",
    ),
    f"{M}.H11RootAuthorizationFlow._publish_permit": (
        "READY_CONSUMED",
        "H11RootReadyPhaseData",
        "H11 permit publication requires exact READY data",
    ),
    f"{M}.H11RootAuthorizationFlow._commit_permit": (
        "PERMIT_PUBLISHED",
        "H11RootPermitPhaseData",
        "H11 permit commit requires exact published permit data",
    ),
}

_EXPLICIT_CONSTRUCTOR_CALLERS = {
    "H11RootDirectoryView": f"{M}.H11RootAuthorizationFlow._acquire_authorities",
    "H11RootFifoView": f"{M}.H11RootAuthorizationFlow._acquire_authorities",
    "H11RootJsonSourceView": f"{M}.H11RootAuthorizationFlow._acquire_authorities",
    "H11RootPresentOutputView": f"{M}.H11RootAuthorizationFlow._consume_ready_commit",
    "H11RootPublicationView": f"{M}.H11RootAuthorizationFlow._publish_permit",
    "H11RootAuthorityView": f"{M}.H11RootAuthorizationFlow._acquire_authorities",
    "H11RootAuthorityPhaseData": f"{M}.H11RootAuthorizationFlow._acquire_authorities",
    "H11RootReadyPhaseData": f"{M}.H11RootAuthorizationFlow._consume_ready_commit",
    "H11RootPermitPhaseData": f"{M}.H11RootAuthorizationFlow._publish_permit",
}

_PARENT_SLOT_PAIRS = {
    "H11RootDirectoryView": frozenset(
        {(15, None), (14, 15), (13, 14), (12, 13), (11, 15), (10, 12), (9, 15)}
    ),
    "H11RootFifoView": frozenset({(8, 9), (7, 9)}),
    "H11RootJsonSourceView": frozenset(
        {(22, 12), (6, 12), (5, None), (16, None), (17, None), (18, None),
         (19, None), (20, None), (21, None)}
    ),
    "H11RootPresentOutputView": frozenset({(4, 10), (3, 11)}),
    "H11RootPublicationView": frozenset({(2, 12)}),
}

_FORBIDDEN_CLASS_HOOKS = frozenset(
    {
        "__new__", "__post_init__", "__init_subclass__", "__class_getitem__",
        "__mro_entries__", "__getattribute__", "__getattr__", "__setattr__",
        "__delattr__", "__get__", "__set__", "__delete__", "__set_name__",
    }
)


_BUILTIN_NAMES = frozenset(
    name.split(".", 1)[1]
    for name in PURE_VALUE_NAMES
    if name.startswith("builtins.") and "." not in name.split(".", 1)[1]
)
_BUILTIN_CLASSES = frozenset({"BaseException", "bytes", "dict", "list", "set", "str"})
_GENERATED_CLASSES = frozenset(_GENERATED_CLASS_FIELDS)


@dataclass(frozen=True, slots=True)
class _FunctionInfo:
    qname: str
    node: ast.FunctionDef | ast.AsyncFunctionDef
    class_name: str | None


@dataclass(slots=True)
class _BindingInventory:
    counts: Counter[str]
    simple_values: dict[str, ast.AST]
    deleted: set[str]
    forms: dict[str, Counter[str]]


def _bound_target_names(target: ast.AST) -> tuple[str, ...]:
    if isinstance(target, ast.Name):
        return (target.id,)
    if isinstance(target, (ast.Tuple, ast.List)):
        return tuple(
            name
            for element in target.elts
            for name in _bound_target_names(element)
        )
    if isinstance(target, ast.Starred):
        return _bound_target_names(target.value)
    return ()


class _WholeFunctionBindings(ast.NodeVisitor):
    """Inventory every binder that can invalidate exact local provenance."""

    def __init__(self, info: _FunctionInfo) -> None:
        self.inventory = _BindingInventory(Counter(), {}, set(), {})
        for argument in (
            *info.node.args.posonlyargs,
            *info.node.args.args,
            *info.node.args.kwonlyargs,
        ):
            self._record(argument.arg, "arguments")
        if info.node.args.vararg is not None:
            self._record(info.node.args.vararg.arg, "arguments")
        if info.node.args.kwarg is not None:
            self._record(info.node.args.kwarg.arg, "arguments")
        for parameter in getattr(info.node, "type_params", ()):
            self._record(parameter.name, f"{type(info.node).__name__}.type_params")
        for statement in info.node.body:
            self.visit(statement)

    def _record(
        self,
        name: str,
        form: str,
        *,
        simple_value: ast.AST | None = None,
    ) -> None:
        if form not in C2E_BINDING_FORMS:
            raise AssertionError(f"unknown C2e binding form: {form}")
        self.inventory.counts[name] += 1
        self.inventory.forms.setdefault(name, Counter())[form] += 1
        if simple_value is not None:
            self.inventory.simple_values[name] = simple_value

    def _bind(
        self,
        target: ast.AST,
        *,
        form: str,
        simple_value: ast.AST | None = None,
    ) -> None:
        names = _bound_target_names(target)
        for name in names:
            self._record(
                name,
                form if len(names) == 1 and isinstance(target, ast.Name) else "destructure",
                simple_value=simple_value if isinstance(target, ast.Name) else None,
            )

    def visit_Assign(self, node: ast.Assign) -> None:
        self.visit(node.value)
        for target in node.targets:
            self._bind(
                target,
                form="Assign",
                simple_value=node.value if len(node.targets) == 1 else None,
            )

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self.visit(node.annotation)
        if node.value is not None:
            self.visit(node.value)
        self._bind(
            node.target,
            form="AnnAssign",
            simple_value=node.value,
        )

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self.visit(node.value)
        self._bind(node.target, form="AugAssign")

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self.visit(node.value)
        self._bind(node.target, form="NamedExpr")

    def visit_For(self, node: ast.For) -> None:
        self.visit(node.iter)
        self._bind(node.target, form="For.target")
        for statement in (*node.body, *node.orelse):
            self.visit(statement)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self.visit(node.iter)
        self._bind(node.target, form="AsyncFor.target")
        for statement in (*node.body, *node.orelse):
            self.visit(statement)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        self.visit(node.iter)
        self._bind(node.target, form="comprehension.target")
        for condition in node.ifs:
            self.visit(condition)

    def visit_With(self, node: ast.With) -> None:
        for item in node.items:
            self.visit(item.context_expr)
            if item.optional_vars is not None:
                self._bind(item.optional_vars, form="With.optional_vars")
        for statement in node.body:
            self.visit(statement)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        for item in node.items:
            self.visit(item.context_expr)
            if item.optional_vars is not None:
                self._bind(item.optional_vars, form="AsyncWith.optional_vars")
        for statement in node.body:
            self.visit(statement)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is not None:
            self.visit(node.type)
        if node.name is not None:
            self._record(node.name, "ExceptHandler.name")
        for statement in node.body:
            self.visit(statement)

    def visit_Delete(self, node: ast.Delete) -> None:
        for target in node.targets:
            for name in _bound_target_names(target):
                self._record(name, "Delete")
                self.inventory.deleted.add(name)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._record(alias.asname or alias.name.split(".", 1)[0], "Import")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            self._record(alias.asname or alias.name, "ImportFrom")

    def _visit_nested_definition(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        self._record(node.name, f"{type(node).__name__}.name")
        for parameter in getattr(node, "type_params", ()):
            self._record(parameter.name, f"{type(node).__name__}.type_params")
        for decorator in node.decorator_list:
            self.visit(decorator)
        for default in (*node.args.defaults, *node.args.kw_defaults):
            if default is not None:
                self.visit(default)

    visit_FunctionDef = _visit_nested_definition
    visit_AsyncFunctionDef = _visit_nested_definition

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._record(node.name, "ClassDef.name")
        for parameter in getattr(node, "type_params", ()):
            self._record(parameter.name, "ClassDef.type_params")
        for decorator in node.decorator_list:
            self.visit(decorator)
        for base in node.bases:
            self.visit(base)
        for keyword in node.keywords:
            self.visit(keyword.value)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        # Lambda parameters and body have their own local scope.
        for default in (*node.args.defaults, *node.args.kw_defaults):
            if default is not None:
                self.visit(default)

    def visit_Global(self, node: ast.Global) -> None:
        for name in node.names:
            self._record(name, "Global")

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        for name in node.names:
            self._record(name, "Nonlocal")

    def visit_MatchAs(self, node: ast.MatchAs) -> None:
        if node.pattern is not None:
            self.visit(node.pattern)
        if node.name is not None:
            self._record(node.name, "MatchAs.name")

    def visit_MatchStar(self, node: ast.MatchStar) -> None:
        if node.name is not None:
            self._record(node.name, "MatchStar.name")

    def visit_MatchMapping(self, node: ast.MatchMapping) -> None:
        for pattern in node.patterns:
            self.visit(pattern)
        if node.rest is not None:
            self._record(node.rest, "MatchMapping.rest")

    def visit_TypeAlias(self, node: ast.TypeAlias) -> None:
        if isinstance(node.name, ast.Name):
            self._record(node.name.id, "TypeAlias.name")
        for parameter in node.type_params:
            self._record(parameter.name, "TypeAlias.type_params")
        self.visit(node.value)


class _EvaluationOrderCalls(ast.NodeVisitor):
    """Visit Call nodes in the design's fixed Python evaluation order."""

    def __init__(self) -> None:
        self.calls: list[ast.Call] = []
        self.forbidden_context_calls: set[int] = set()
        self._forbidden_depth = 0

    def _visit_forbidden(self, node: ast.AST) -> None:
        self._forbidden_depth += 1
        self.generic_visit(node)
        self._forbidden_depth -= 1

    def visit_forbidden_context(self, node: ast.AST) -> None:
        self._forbidden_depth += 1
        self.visit(node)
        self._forbidden_depth -= 1

    visit_Lambda = _visit_forbidden
    visit_ListComp = _visit_forbidden
    visit_SetComp = _visit_forbidden
    visit_DictComp = _visit_forbidden
    visit_GeneratorExp = _visit_forbidden
    visit_BoolOp = _visit_forbidden
    visit_IfExp = _visit_forbidden

    def visit_Call(self, node: ast.Call) -> None:
        self.visit(node.func)
        for argument in node.args:
            self.visit(argument)
        for keyword in node.keywords:
            self.visit(keyword.value)
        if self._forbidden_depth:
            self.forbidden_context_calls.add(id(node))
        self.calls.append(node)


def _attribute_parts(node: ast.AST) -> tuple[str, ...] | None:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    parts.append(current.id)
    return tuple(reversed(parts))


class H11ReachableCallScanner:
    """Fail-closed scanner for the C2e production root.

    The scanner owns only resolution/classification.  Protocol meaning and the
    expected topology remain independent constants below.
    """

    def __init__(self, source: str, *, module_name: str = M) -> None:
        self.module_name = module_name
        self.tree = ast.parse(source)
        self.imports: dict[str, str] = {}
        self.functions: dict[str, _FunctionInfo] = {}
        self.classes: dict[str, ast.ClassDef] = {}
        self.module_shadowed: set[str] = set()
        self._binding_cache: dict[str, _BindingInventory] = {}
        module_function = ast.parse("def _c2e_module_scope():\n    pass\n").body[0]
        assert isinstance(module_function, ast.FunctionDef)
        module_function.body = self.tree.body
        self._module_bindings = _WholeFunctionBindings(
            _FunctionInfo(f"{module_name}._c2e_module_scope", module_function, None)
        ).inventory
        self._class_attribute_mutations: set[str] = set()
        self._nominal_cache: dict[str, bool] = {}
        self._frozen_constructor_cache: dict[str, bool] = {}
        self._factory_cache: dict[str, bool] = {}
        self._phase_graph_cache: bool | None = None
        self._phase_cursor_cache: dict[str, bool] = {}
        self._parent_pair_cache: dict[str, bool] = {}
        self._parents = {
            child: parent
            for parent in ast.walk(self.tree)
            for child in ast.iter_child_nodes(parent)
        }
        self._index_module()

    def _index_module(self) -> None:
        for node in self.tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.imports[alias.asname or alias.name] = alias.name
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                for alias in node.names:
                    self.imports[alias.asname or alias.name] = f"{node.module}.{alias.name}"
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qname = f"{self.module_name}.{node.name}"
                self.functions[qname] = _FunctionInfo(qname, node, None)
            elif isinstance(node, ast.ClassDef):
                self.classes[node.name] = node
                for member in node.body:
                    if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        qname = f"{self.module_name}.{node.name}.{member.name}"
                        self.functions[qname] = _FunctionInfo(qname, member, node.name)
            elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                self.module_shadowed.update(
                    target.id for target in targets if isinstance(target, ast.Name)
                )
                for target in targets:
                    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                        self._class_attribute_mutations.add(target.value.id)
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                call = node.value
                if (
                    isinstance(call.func, ast.Name)
                    and call.func.id == "setattr"
                    and call.args
                    and isinstance(call.args[0], ast.Name)
                ):
                    self._class_attribute_mutations.add(call.args[0].id)
        for name in self.module_shadowed:
            self.imports.pop(name, None)

    def scan(self, root_qname: str) -> H11ScanResult:
        pending = deque([root_qname])
        close_qname = f"{self.module_name}.H11RootAuthorizationFlow.close"
        if (
            root_qname == ROOT_QNAME
            and self.module_name == M
            and close_qname in self.functions
        ):
            # The accepted lifecycle topology includes the explicit close entrypoint
            # even though the one-shot wrapper does not invoke it on its success path.
            pending.append(close_qname)
        visited: set[str] = set()
        calls: list[H11ResolvedCall] = []
        unresolved: list[H11ScanFailure] = []
        multi_target: list[H11ScanFailure] = []
        unclassified: list[H11ScanFailure] = []
        call_count = 0
        occurrence: Counter[tuple[str, str, str]] = Counter()

        while pending:
            caller = pending.popleft()
            if caller in visited:
                continue
            visited.add(caller)
            info = self.functions.get(caller)
            if info is None:
                unresolved.append(H11ScanFailure(caller, "<root>", "missing internal body"))
                continue
            bindings = self._function_bindings(info)
            local_types = self._local_value_types(info, bindings)
            local_bound = set(bindings.counts)
            visitor = _EvaluationOrderCalls()
            for decorator in info.node.decorator_list:
                visitor.visit_forbidden_context(decorator)
            for statement in info.node.body:
                visitor.visit(statement)
            call_count += len(visitor.calls)
            for call in visitor.calls:
                lexical = ast.unparse(call.func)
                resolved = self._resolve_call(
                    call,
                    info=info,
                    local_types=local_types,
                    local_bound=local_bound,
                )
                if resolved is None:
                    unresolved.append(H11ScanFailure(caller, lexical, "no permitted provenance rule"))
                    continue
                canonical, rule = resolved
                kind = self._classify(canonical)
                if kind is None:
                    unclassified.append(H11ScanFailure(caller, lexical, canonical))
                    continue
                if kind == "sensitive" and id(call) in visitor.forbidden_context_calls:
                    unresolved.append(
                        H11ScanFailure(
                            caller,
                            lexical,
                            "sensitive call in forbidden conditional/callback context",
                        )
                    )
                    continue
                key = (caller, canonical, lexical)
                same = occurrence[key]
                occurrence[key] += 1
                calls.append(H11ResolvedCall(caller, kind, canonical, lexical, same, rule))
                if kind == "internal" and canonical in self.functions:
                    pending.append(canonical)

        return H11ScanResult(
            calls=tuple(calls),
            unresolved=tuple(unresolved),
            multi_target=tuple(multi_target),
            unclassified=tuple(unclassified),
            reachable_ast_call_count=call_count,
        )

    def _function_bindings(self, info: _FunctionInfo) -> _BindingInventory:
        cached = self._binding_cache.get(info.qname)
        if cached is None:
            cached = _WholeFunctionBindings(info).inventory
            self._binding_cache[info.qname] = cached
        return cached

    def _local_value_types(
        self,
        info: _FunctionInfo,
        bindings: _BindingInventory | None = None,
    ) -> dict[str, str]:
        inventory = bindings or self._function_bindings(info)
        result: dict[str, str] = {}
        phase_specification = _PHASE_CURSORS.get(info.qname)
        if phase_specification is not None and self._prove_phase_cursor(info):
            result["phase_data"] = phase_specification[1]
        for name, value in inventory.simple_values.items():
            if not self._simple_value_binding_is_live(
                info=info,
                inventory=inventory,
                name=name,
                value=value,
            ):
                continue
            if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
                if self._prove_exact_nominal_class(value.func.id):
                    result[name] = value.func.id
                elif value.func.id in {"dict", "list", "set", "tuple"}:
                    result[name] = f"builtins.{value.func.id}"
                elif self.imports.get(value.func.id) == "pathlib.Path":
                    result[name] = "pathlib.Path"
            elif isinstance(value, ast.Call):
                parts = _attribute_parts(value.func)
                if parts is not None and len(parts) == 2:
                    qname = f"{self.module_name}.{parts[0]}.{parts[1]}"
                    if self._prove_factory(qname):
                        result[name] = _FACTORY_RESULTS[qname]
            elif isinstance(value, ast.List):
                result[name] = "builtins.list"
            elif isinstance(value, ast.Dict):
                result[name] = "builtins.dict"
            elif isinstance(value, ast.Set):
                result[name] = "builtins.set"
            elif isinstance(value, ast.Tuple):
                result[name] = "builtins.tuple"
        changed = True
        while changed:
            changed = False
            for name, value in inventory.simple_values.items():
                if name in result or inventory.counts[name] != 1 or name in inventory.deleted:
                    continue
                nominal = self._expression_nominal(
                    value,
                    info=info,
                    local_types=result,
                    require_field_proof=True,
                )
                if nominal is not None:
                    result[name] = nominal
                    changed = True
                elif (
                    isinstance(value, ast.Subscript)
                    and isinstance(value.value, ast.Name)
                    and self._tuple_generator_element_type(
                        inventory.simple_values.get(value.value.id)
                    )
                    == "builtins.dict"
                ):
                    result[name] = "builtins.dict"
                    changed = True
        return result

    def _node_is_in_comprehension_target(
        self,
        node: ast.AST,
        *,
        boundary: ast.AST,
    ) -> bool:
        current = node
        while current is not boundary and current in self._parents:
            parent = self._parents[current]
            if isinstance(parent, ast.comprehension):
                return node is parent.target or node in set(ast.walk(parent.target))
            current = parent
        return False

    def _simple_value_binding_is_live(
        self,
        *,
        info: _FunctionInfo,
        inventory: _BindingInventory,
        name: str,
        value: ast.AST,
    ) -> bool:
        if inventory.counts[name] == 1 and name not in inventory.deleted:
            return True
        name_nodes = [
            node
            for node in ast.walk(info.node)
            if isinstance(node, ast.Name)
            and node.id == name
            and isinstance(node.ctx, (ast.Store, ast.Del))
        ]
        stores = [node for node in name_nodes if isinstance(node.ctx, ast.Store)]
        deletes = [node for node in name_nodes if isinstance(node.ctx, ast.Del)]
        forms = inventory.forms.get(name, Counter())
        initial_forms = forms["Assign"] + forms["AnnAssign"]
        if initial_forms != 1 or any(
            forms[form]
            for form in forms
            if form not in {"Assign", "AnnAssign", "destructure", "comprehension.target", "Delete"}
        ):
            return False
        same_scope_stores = [
            node
            for node in stores
            if not self._node_is_in_comprehension_target(node, boundary=info.node)
        ]
        if (
            info.qname
            == f"{self.module_name}.H11RootAuthorizationFlow._consume_ready_commit"
            and name == "path"
            and isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and self.imports.get(value.func.id) == "pathlib.Path"
            and not deletes
            and len(same_scope_stores) == 2
        ):
            receiver_lines = [
                candidate.lineno
                for candidate in ast.walk(info.node)
                if isinstance(candidate, ast.Call)
                and isinstance(candidate.func, ast.Attribute)
                and isinstance(candidate.func.value, ast.Name)
                and candidate.func.value.id == name
            ]
            if (
                receiver_lines
                and same_scope_stores[0].lineno < min(receiver_lines)
                and max(receiver_lines) < same_scope_stores[1].lineno
            ):
                return True
        if len(same_scope_stores) != 1:
            return False
        if not deletes:
            return all(
                node in same_scope_stores
                or self._node_is_in_comprehension_target(node, boundary=info.node)
                for node in stores
            )
        literal_container = isinstance(value, (ast.List, ast.Dict, ast.Set, ast.Tuple)) or (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and value.func.id in {"dict", "list", "set", "tuple"}
        )
        if not literal_container or len(deletes) != 1:
            return False
        receiver_lines = [
            candidate.lineno
            for candidate in ast.walk(info.node)
            if isinstance(candidate, ast.Call)
            and isinstance(candidate.func, ast.Attribute)
            and isinstance(candidate.func.value, ast.Name)
            and candidate.func.value.id == name
        ]
        return bool(receiver_lines) and max(receiver_lines) < deletes[0].lineno

    @staticmethod
    def _tuple_generator_element_type(value: ast.AST | None) -> str | None:
        if (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and value.func.id == "tuple"
            and len(value.args) == 1
            and not value.keywords
            and isinstance(value.args[0], ast.GeneratorExp)
        ):
            element = value.args[0].elt
            if (
                isinstance(element, ast.Call)
                and isinstance(element.func, ast.Name)
                and element.func.id == "dict"
            ):
                return "builtins.dict"
        return None

    def _field_annotation_nominal(self, class_name: str, field_name: str) -> str | None:
        node = self.classes.get(class_name)
        if node is None:
            return None
        matches = [
            member.annotation
            for member in node.body
            if isinstance(member, ast.AnnAssign)
            and isinstance(member.target, ast.Name)
            and member.target.id == field_name
        ]
        if len(matches) != 1:
            return None
        nominals = self._annotation_nominals(matches[0]) - {"None"}
        internal = nominals & _EXACT_NOMINAL_CLASSES
        return next(iter(internal)) if len(internal) == 1 else None

    def _expression_nominal(
        self,
        expression: ast.AST,
        *,
        info: _FunctionInfo,
        local_types: dict[str, str],
        require_field_proof: bool,
    ) -> str | None:
        if isinstance(expression, ast.Name):
            return local_types.get(expression.id)
        if not isinstance(expression, ast.Attribute):
            return None
        owner = self._expression_nominal(
            expression.value,
            info=info,
            local_types=local_types,
            require_field_proof=require_field_proof,
        )
        if owner is None:
            return None
        nominal = self._field_annotation_nominal(owner, expression.attr)
        if nominal is None:
            return None
        if require_field_proof and owner in _EXPLICIT_FROZEN_FIELDS:
            target = f"{self.module_name}.{nominal}.__init__"
            if not self._prove_frozen_field(
                info=self.functions.get(f"{self.module_name}.{owner}.__init__")
                or info,
                field_name=expression.attr,
                target=target,
            ):
                return None
        return nominal

    @staticmethod
    def _decorator_leaf_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
        result: set[str] = set()
        for decorator in node.decorator_list:
            target = decorator.func if isinstance(decorator, ast.Call) else decorator
            parts = _attribute_parts(target)
            if parts is not None:
                result.add(parts[-1])
        return result

    def _is_explicit_instance_method(self, info: _FunctionInfo) -> bool:
        if info.class_name is None:
            return False
        positional = (*info.node.args.posonlyargs, *info.node.args.args)
        if not positional or positional[0].arg != "self":
            return False
        if self._decorator_leaf_names(info.node) & {"staticmethod", "classmethod"}:
            return False
        bindings = self._function_bindings(info)
        return bindings.counts["self"] == 1 and "self" not in bindings.deleted

    @staticmethod
    def _annotation_nominals(annotation: ast.AST | None) -> frozenset[str]:
        if annotation is None:
            return frozenset()
        if isinstance(annotation, ast.Constant):
            if annotation.value is None:
                return frozenset({"None"})
            if isinstance(annotation.value, str):
                try:
                    return H11ReachableCallScanner._annotation_nominals(
                        ast.parse(annotation.value, mode="eval").body
                    )
                except SyntaxError:
                    return frozenset()
        if isinstance(annotation, ast.Name):
            return frozenset({annotation.id})
        if isinstance(annotation, ast.Attribute):
            parts = _attribute_parts(annotation)
            return frozenset({parts[-1]}) if parts is not None else frozenset()
        if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
            return (
                H11ReachableCallScanner._annotation_nominals(annotation.left)
                | H11ReachableCallScanner._annotation_nominals(annotation.right)
            )
        if isinstance(annotation, ast.Subscript):
            base = _attribute_parts(annotation.value)
            if base is not None and base[-1] in {"Optional", "Union"}:
                values = (
                    annotation.slice.elts
                    if isinstance(annotation.slice, ast.Tuple)
                    else (annotation.slice,)
                )
                result = frozenset().union(
                    *(H11ReachableCallScanner._annotation_nominals(value) for value in values)
                )
                return result | ({"None"} if base[-1] == "Optional" else set())
        return frozenset()

    @staticmethod
    def _annotation_is_none(annotation: ast.AST | None) -> bool:
        return isinstance(annotation, ast.Constant) and annotation.value is None

    @staticmethod
    def _type_params_are_empty(node: ast.AST) -> bool:
        return not getattr(node, "type_params", ())

    def _direct_decorator(
        self,
        decorator: ast.AST,
        *,
        imported_name: str,
    ) -> ast.Call | None:
        if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Name):
            return None
        if (
            decorator.func.id != imported_name
            or self.imports.get(imported_name) != f"dataclasses.{imported_name}"
            or self._module_bindings.counts[imported_name] != 1
        ):
            return None
        return decorator

    def _dataclass_configuration(
        self,
        class_name: str,
    ) -> tuple[bool, bool, bool] | None:
        node = self.classes.get(class_name)
        if node is None or len(node.decorator_list) != 1:
            return None
        decorator = self._direct_decorator(
            node.decorator_list[0],
            imported_name="dataclass",
        )
        if decorator is None or decorator.args or any(keyword.arg is None for keyword in decorator.keywords):
            return None
        keywords = {keyword.arg: keyword.value for keyword in decorator.keywords}
        if len(keywords) != len(decorator.keywords):
            return None
        allowed = {"frozen", "slots"}
        if class_name in _EXPLICIT_FROZEN_FIELDS:
            allowed.add("init")
        elif class_name in _GENERATED_CLASS_FIELDS and "init" in keywords:
            allowed.add("init")
        if set(keywords) != allowed:
            return None
        if any(
            not isinstance(value, ast.Constant) or type(value.value) is not bool
            for value in keywords.values()
        ):
            return None
        frozen = keywords["frozen"].value
        slots = keywords["slots"].value
        init = keywords.get("init", ast.Constant(value=True)).value
        return frozen, slots, init

    @staticmethod
    def _method_decorator_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[str, ...] | None:
        names: list[str] = []
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Name):
                return None
            names.append(decorator.id)
        return tuple(names)

    def _prove_exact_nominal_class(self, class_name: str) -> bool:
        cached = self._nominal_cache.get(class_name)
        if cached is not None:
            return cached
        self._nominal_cache[class_name] = False
        node = self.classes.get(class_name)
        if (
            class_name not in _EXACT_NOMINAL_CLASSES
            or node is None
            or node.bases
            or node.keywords
            or not self._type_params_are_empty(node)
            or self._module_bindings.counts[class_name] != 1
            or class_name in self._class_attribute_mutations
        ):
            return False

        if class_name in {"H11OwnedFdSlot", "H11RootAuthorizationFlow"}:
            if node.decorator_list:
                return False
        else:
            configuration = self._dataclass_configuration(class_name)
            expected_init = class_name not in _EXPLICIT_FROZEN_FIELDS
            if configuration != (True, True, expected_init):
                return False

        fields: list[str] = []
        methods: list[str] = []
        slot_assignments: list[ast.Assign] = []
        docstrings = 0
        for ordinal, member in enumerate(node.body):
            if isinstance(member, ast.AnnAssign) and isinstance(member.target, ast.Name):
                if member.value is not None:
                    return False
                fields.append(member.target.id)
            elif isinstance(member, ast.Assign):
                slot_assignments.append(member)
            elif isinstance(member, ast.FunctionDef):
                if not self._type_params_are_empty(member) or member.name in _FORBIDDEN_CLASS_HOOKS:
                    return False
                methods.append(member.name)
            elif isinstance(member, ast.AsyncFunctionDef):
                return False
            elif (
                isinstance(member, ast.Expr)
                and isinstance(member.value, ast.Constant)
                and isinstance(member.value.value, str)
                and ordinal == 0
            ):
                docstrings += 1
            else:
                return False
        if docstrings > 1 or tuple(methods) != _EXACT_CLASS_METHODS[class_name]:
            return False
        expected_fields = (
            _EXPLICIT_FROZEN_FIELDS.get(class_name)
            or _GENERATED_CLASS_FIELDS.get(class_name)
            or ()
        )
        if tuple(fields) != expected_fields:
            return False
        if class_name == "H11OwnedFdSlot":
            if len(slot_assignments) != 1:
                return False
            assignment = slot_assignments[0]
            if (
                len(assignment.targets) != 1
                or not isinstance(assignment.targets[0], ast.Name)
                or assignment.targets[0].id != "__slots__"
                or not isinstance(assignment.value, ast.Tuple)
                or tuple(
                    item.value if isinstance(item, ast.Constant) else None
                    for item in assignment.value.elts
                )
                != ("_role", "_descriptor", "_open_started")
            ):
                return False
        elif slot_assignments:
            return False

        for method_name in methods:
            method = self.functions.get(f"{self.module_name}.{class_name}.{method_name}")
            if method is None:
                return False
            decorators = self._method_decorator_names(method.node)
            if decorators is None:
                return False
            if method_name in {
                "role", "state", "parent_reference", "reference", "acquisition_reference"
            }:
                if decorators != ("property",):
                    return False
            elif method_name in {"decode", "ready_committed", "permit_committed"}:
                if decorators != ("classmethod",):
                    return False
            elif decorators:
                return False

        if class_name in _EXPLICIT_FROZEN_FIELDS and not self._prove_frozen_constructor(class_name):
            return False
        if class_name in _GENERATED_CLASS_FIELDS and any(
            method.name in {"__init__", "__post_init__"}
            for method in node.body
            if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
        ):
            return False
        self._nominal_cache[class_name] = True
        return True

    @staticmethod
    def _object_setattr_call(statement: ast.stmt) -> ast.Call | None:
        if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
            return None
        call = statement.value
        return call if _attribute_parts(call.func) == ("object", "__setattr__") else None

    def _prove_frozen_constructor(self, class_name: str) -> bool:
        cached = self._frozen_constructor_cache.get(class_name)
        if cached is not None:
            return cached
        self._frozen_constructor_cache[class_name] = False
        fields = _EXPLICIT_FROZEN_FIELDS.get(class_name)
        constructor = self.functions.get(f"{self.module_name}.{class_name}.__init__")
        if fields is None or constructor is None or not isinstance(constructor.node, ast.FunctionDef):
            return False
        node = constructor.node
        if (
            not self._type_params_are_empty(node)
            or node.args.posonlyargs
            or tuple(argument.arg for argument in node.args.args) != ("self",)
            or node.args.vararg is not None
            or node.args.kwarg is not None
            or node.args.defaults
            or any(default is not None for default in node.args.kw_defaults)
            or tuple(argument.arg for argument in node.args.kwonlyargs)
            != tuple(field.removeprefix("_") for field in fields)
            or not self._annotation_is_none(node.returns)
        ):
            return False
        bindings = self._function_bindings(constructor)
        protected = ("self", *(field.removeprefix("_") for field in fields))
        if (
            self._module_bindings.counts["object"]
            or bindings.counts["object"]
            or any(bindings.counts[name] != 1 or name in bindings.deleted for name in protected)
        ):
            return False
        calls = [self._object_setattr_call(statement) for statement in node.body]
        store_indexes = [index for index, call in enumerate(calls) if call is not None]
        if not store_indexes or store_indexes != list(range(store_indexes[0], len(node.body))):
            return False
        stores = [call for call in calls[store_indexes[0] :] if call is not None]
        if len(stores) != len(fields):
            return False
        for field, call in zip(fields, stores):
            parameter = field.removeprefix("_")
            if (
                call is None
                or len(call.args) != 3
                or call.keywords
                or not isinstance(call.args[0], ast.Name)
                or call.args[0].id != "self"
                or not isinstance(call.args[1], ast.Constant)
                or call.args[1].value != field
                or not isinstance(call.args[2], ast.Name)
                or call.args[2].id != parameter
            ):
                return False
        for member in self.classes[class_name].body:
            if not isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for candidate in ast.walk(member):
                if (
                    isinstance(candidate, ast.Attribute)
                    and isinstance(candidate.value, ast.Name)
                    and candidate.value.id == "self"
                    and candidate.attr in fields
                    and isinstance(candidate.ctx, (ast.Store, ast.Del))
                ):
                    return False
                if isinstance(candidate, ast.Call) and _attribute_parts(candidate.func) in {
                    ("setattr",),
                    ("object", "__setattr__"),
                }:
                    if member.name != "__init__" or candidate not in stores:
                        return False
        self._frozen_constructor_cache[class_name] = True
        return True

    def _prove_factory(self, qname: str) -> bool:
        cached = self._factory_cache.get(qname)
        if cached is not None:
            return cached
        self._factory_cache[qname] = False
        specification = _FACTORY_SIGNATURES.get(qname)
        info = self.functions.get(qname)
        if specification is None or info is None or not isinstance(info.node, ast.FunctionDef):
            return False
        positional, keyword_only, annotations, result_class = specification
        node = info.node
        if (
            not self._type_params_are_empty(node)
            or self._method_decorator_names(node) != ("classmethod",)
            or node.args.posonlyargs
            or tuple(argument.arg for argument in node.args.args) != positional
            or tuple(argument.arg for argument in node.args.kwonlyargs) != keyword_only
            or node.args.vararg is not None
            or node.args.kwarg is not None
            or node.args.defaults
            or any(default is not None for default in node.args.kw_defaults)
            or self._annotation_nominals(node.returns) != frozenset({result_class})
            or not self._prove_exact_nominal_class(result_class)
        ):
            return False
        parameters = {
            argument.arg: argument
            for argument in (*node.args.args, *node.args.kwonlyargs)
        }
        if any(
            self._annotation_nominals(parameters[name].annotation) != frozenset({nominal})
            for name, nominal in annotations.items()
        ):
            return False
        returns = [candidate for candidate in ast.walk(node) if isinstance(candidate, ast.Return)]
        if (
            len(returns) != 1
            or not node.body
            or node.body[-1] is not returns[0]
            or not isinstance(returns[0].value, ast.Call)
            or not isinstance(returns[0].value.func, ast.Name)
            or returns[0].value.func.id != result_class
            or any(isinstance(candidate, (ast.Yield, ast.YieldFrom)) for candidate in ast.walk(node))
        ):
            return False
        for candidate in ast.walk(node):
            if (
                isinstance(candidate, ast.Call)
                and isinstance(candidate.func, ast.Name)
                and candidate.func.id == "cls"
            ):
                return False
        bindings = self._function_bindings(info)
        if any(
            bindings.counts[name] != 1 or name in bindings.deleted
            for name in (*positional, *keyword_only)
        ):
            return False
        self._factory_cache[qname] = True
        return True

    @staticmethod
    def _phase_assignment(statement: ast.stmt, *, value_class: str | None) -> bool:
        target: ast.AST | None = None
        value: ast.AST | None = None
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            target, value = statement.targets[0], statement.value
        elif isinstance(statement, ast.AnnAssign):
            target, value = statement.target, statement.value
        if (
            not isinstance(target, ast.Attribute)
            or not isinstance(target.value, ast.Name)
            or target.value.id != "self"
            or target.attr != "_phase_data"
            or value is None
        ):
            return False
        if value_class is None:
            return isinstance(value, ast.Constant) and value.value is None
        return (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and value.func.id == value_class
        )

    @staticmethod
    def _transition_statement(
        statement: ast.stmt,
        *,
        expected: str,
        target: str,
    ) -> bool:
        if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
            return False
        call = statement.value
        if _attribute_parts(call.func) != ("self", "_transition") or call.args:
            return False
        values = {keyword.arg: _attribute_parts(keyword.value) for keyword in call.keywords}
        return values == {
            "expected": ("H11RootAuthorizationState", expected),
            "target": ("H11RootAuthorizationState", target),
        }

    def _prove_phase_graph(self) -> bool:
        if self._phase_graph_cache is not None:
            return self._phase_graph_cache
        self._phase_graph_cache = False
        flow = self.classes.get("H11RootAuthorizationFlow")
        if flow is None or not self._prove_exact_nominal_class("H11RootAuthorizationFlow"):
            return False
        expected_writers = {
            "__init__": (None, None, None),
            "_acquire_authorities": (
                "H11RootAuthorityPhaseData", "NEW", "AUTHORITIES_RETAINED"
            ),
            "_consume_ready_commit": (
                "H11RootReadyPhaseData", "AUTHORITIES_RETAINED", "READY_CONSUMED"
            ),
            "_publish_permit": (
                "H11RootPermitPhaseData", "READY_CONSUMED", "PERMIT_PUBLISHED"
            ),
        }
        seen: set[str] = set()
        for member in flow.body:
            if not isinstance(member, ast.FunctionDef):
                continue
            stores = [
                statement
                for statement in member.body
                if self._phase_assignment(statement, value_class=None)
                or any(
                    self._phase_assignment(statement, value_class=nominal)
                    for nominal in (
                        "H11RootAuthorityPhaseData",
                        "H11RootReadyPhaseData",
                        "H11RootPermitPhaseData",
                    )
                )
            ]
            attribute_mutations = [
                candidate
                for candidate in ast.walk(member)
                if isinstance(candidate, ast.Attribute)
                and isinstance(candidate.value, ast.Name)
                and candidate.value.id == "self"
                and candidate.attr == "_phase_data"
                and isinstance(candidate.ctx, (ast.Store, ast.Del))
            ]
            if member.name not in expected_writers:
                if attribute_mutations:
                    return False
                continue
            nominal, expected_state, target_state = expected_writers[member.name]
            if len(stores) != 1 or len(attribute_mutations) != 1:
                return False
            statement = stores[0]
            if not self._phase_assignment(statement, value_class=nominal):
                return False
            seen.add(member.name)
            if member.name == "__init__":
                continue
            index = member.body.index(statement)
            if index + 1 >= len(member.body) or not self._transition_statement(
                member.body[index + 1], expected=expected_state, target=target_state
            ):
                return False
            call = statement.value
            assert isinstance(call, ast.Call)
            if member.name == "_consume_ready_commit":
                predecessor = self._constructor_argument(
                    call,
                    self.functions[f"{self.module_name}.H11RootReadyPhaseData.__init__"],
                    "authority_data",
                )
                if not isinstance(predecessor, ast.Name) or predecessor.id != "phase_data":
                    return False
            if member.name == "_publish_permit":
                predecessor = self._constructor_argument(
                    call,
                    self.functions[f"{self.module_name}.H11RootPermitPhaseData.__init__"],
                    "ready_data",
                )
                if not isinstance(predecessor, ast.Name) or predecessor.id != "phase_data":
                    return False
        if seen != set(expected_writers):
            return False
        expected_caller = f"{self.module_name}.H11RootAuthorizationFlow.authorize_once"
        for method_name in ("_consume_ready_commit", "_publish_permit", "_commit_permit"):
            callers = []
            for caller in self.functions.values():
                callers.extend(
                    caller.qname
                    for candidate in ast.walk(caller.node)
                    if isinstance(candidate, ast.Call)
                    and _attribute_parts(candidate.func) == ("self", method_name)
                )
            if callers != [expected_caller]:
                return False
        self._phase_graph_cache = True
        return True

    @staticmethod
    def _phase_gate(statement: ast.stmt, *, state: str, nominal: str, message: str) -> bool:
        if (
            not isinstance(statement, ast.If)
            or statement.orelse
            or len(statement.body) != 1
            or not isinstance(statement.test, ast.BoolOp)
            or not isinstance(statement.test.op, ast.Or)
            or len(statement.test.values) != 2
        ):
            return False
        state_gate, type_gate = statement.test.values
        expected_state_gate = (
            isinstance(state_gate, ast.Compare)
            and len(state_gate.ops) == 1
            and isinstance(state_gate.ops[0], ast.IsNot)
            and len(state_gate.comparators) == 1
            and _attribute_parts(state_gate.left) == ("self", "_state")
            and _attribute_parts(state_gate.comparators[0])
            == ("H11RootAuthorizationState", state)
        )
        expected_type_gate = (
            isinstance(type_gate, ast.Compare)
            and len(type_gate.ops) == 1
            and isinstance(type_gate.ops[0], ast.IsNot)
            and len(type_gate.comparators) == 1
            and isinstance(type_gate.left, ast.Call)
            and _attribute_parts(type_gate.left.func) == ("type",)
            and len(type_gate.left.args) == 1
            and not type_gate.left.keywords
            and isinstance(type_gate.left.args[0], ast.Name)
            and type_gate.left.args[0].id == "phase_data"
            and _attribute_parts(type_gate.comparators[0]) == (nominal,)
        )
        branch = statement.body[0]
        expected_failure = (
            isinstance(branch, ast.Expr)
            and isinstance(branch.value, ast.Call)
            and _attribute_parts(branch.value.func) == ("_fail",)
            and len(branch.value.args) == 1
            and not branch.value.keywords
            and isinstance(branch.value.args[0], ast.Constant)
            and branch.value.args[0].value == message
        )
        return expected_state_gate and expected_type_gate and expected_failure

    def _prove_phase_cursor(self, info: _FunctionInfo) -> bool:
        cached = self._phase_cursor_cache.get(info.qname)
        if cached is not None:
            return cached
        self._phase_cursor_cache[info.qname] = False
        specification = _PHASE_CURSORS.get(info.qname)
        if (
            specification is None
            or not isinstance(info.node, ast.FunctionDef)
            or len(info.node.body) < 2
            or not self._prove_phase_graph()
        ):
            return False
        assignment, gate = info.node.body[:2]
        if (
            not isinstance(assignment, ast.Assign)
            or len(assignment.targets) != 1
            or not isinstance(assignment.targets[0], ast.Name)
            or assignment.targets[0].id != "phase_data"
            or _attribute_parts(assignment.value) != ("self", "_phase_data")
            or not self._phase_gate(
                gate,
                state=specification[0],
                nominal=specification[1],
                message=specification[2],
            )
        ):
            return False
        bindings = self._function_bindings(info)
        if any(
            bindings.counts[name] != 1 or name in bindings.deleted
            for name in ("self", "phase_data")
        ):
            return False
        self._phase_cursor_cache[info.qname] = True
        return True

    def _is_frozen_init_false_class(self, class_name: str) -> bool:
        node = self.classes.get(class_name)
        if node is None:
            return False
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            parts = _attribute_parts(decorator.func)
            if parts is None or parts[-1] != "dataclass":
                continue
            keywords = {
                keyword.arg: keyword.value
                for keyword in decorator.keywords
                if keyword.arg is not None
            }
            return all(
                isinstance(keywords.get(name), ast.Constant)
                and keywords[name].value is expected
                for name, expected in (("frozen", True), ("slots", True), ("init", False))
            )
        return False

    def _constructor_argument(
        self,
        call: ast.Call,
        constructor: _FunctionInfo,
        parameter_name: str,
    ) -> ast.AST | None:
        if any(isinstance(argument, ast.Starred) for argument in call.args):
            return None
        if any(keyword.arg is None for keyword in call.keywords):
            return None
        matching = [
            keyword.value for keyword in call.keywords if keyword.arg == parameter_name
        ]
        if len(matching) > 1:
            return None
        if matching:
            return matching[0]
        positional = (*constructor.node.args.posonlyargs, *constructor.node.args.args)
        positional = positional[1:] if positional and positional[0].arg == "self" else positional
        names = tuple(argument.arg for argument in positional)
        if parameter_name not in names:
            return None
        index = names.index(parameter_name)
        return call.args[index] if index < len(call.args) else None

    def _expression_has_nominal_provenance(
        self,
        expression: ast.AST,
        *,
        caller: _FunctionInfo,
        nominal: str,
        allow_none: bool,
    ) -> bool:
        if isinstance(expression, ast.Constant) and expression.value is None:
            return allow_none
        if (
            isinstance(expression, ast.Name)
            and expression.id == "self"
            and nominal == "H11RootAuthorizationFlow"
            and caller.class_name == nominal
            and self._is_explicit_instance_method(caller)
        ):
            return self._prove_exact_nominal_class(nominal)
        if isinstance(expression, ast.Call) and isinstance(expression.func, ast.Name):
            return expression.func.id == nominal and self._prove_exact_nominal_class(nominal)
        if (
            nominal == "H11OwnedFdSlot"
            and isinstance(expression, ast.Subscript)
            and isinstance(expression.value, ast.Attribute)
            and isinstance(expression.value.value, ast.Name)
            and expression.value.value.id == "self"
            and expression.value.attr == "_slots"
            and isinstance(expression.slice, ast.Constant)
            and type(expression.slice.value) is int
            and 0 <= expression.slice.value <= 22
            and caller.class_name == "H11RootAuthorizationFlow"
            and self._is_explicit_instance_method(caller)
        ):
            return True
        if not isinstance(expression, ast.Name):
            return False
        bindings = self._function_bindings(caller)
        if bindings.counts[expression.id] != 1 or expression.id in bindings.deleted:
            return False
        value = bindings.simple_values.get(expression.id)
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
            return value.func.id == nominal and self._prove_exact_nominal_class(nominal)
        if isinstance(value, ast.Call):
            parts = _attribute_parts(value.func)
            if parts is None or len(parts) != 2:
                return False
            qname = f"{self.module_name}.{parts[0]}.{parts[1]}"
            return _FACTORY_RESULTS.get(qname) == nominal and self._prove_factory(qname)
        if (
            isinstance(value, ast.Attribute)
            and _attribute_parts(value) == ("self", "_phase_data")
            and _PHASE_CURSORS.get(caller.qname, (None, None, None))[1] == nominal
        ):
            return self._prove_phase_cursor(caller)
        return False

    def _prove_frozen_field(
        self,
        *,
        info: _FunctionInfo,
        field_name: str,
        target: str,
    ) -> bool:
        class_name = info.class_name
        if (
            class_name is None
            or class_name not in _EXPLICIT_FROZEN_FIELDS
            or not self._prove_exact_nominal_class(class_name)
        ):
            return False
        constructor = self.functions.get(f"{self.module_name}.{class_name}.__init__")
        if constructor is None or not self._is_explicit_instance_method(constructor):
            return False
        nominal = target.removeprefix(f"{self.module_name}.").rsplit(".", 1)[0]
        class_node = self.classes[class_name]
        field_annotations = [
            member.annotation
            for member in class_node.body
            if isinstance(member, ast.AnnAssign)
            and isinstance(member.target, ast.Name)
            and member.target.id == field_name
        ]
        if len(field_annotations) != 1:
            return False
        field_nominals = self._annotation_nominals(field_annotations[0])
        if nominal not in field_nominals:
            return False
        parameter_name = field_name.removeprefix("_")
        parameters = {
            argument.arg: argument
            for argument in (
                *constructor.node.args.posonlyargs,
                *constructor.node.args.args,
                *constructor.node.args.kwonlyargs,
            )
        }
        parameter = parameters.get(parameter_name)
        if parameter is None:
            return False
        parameter_nominals = self._annotation_nominals(parameter.annotation)
        if nominal not in parameter_nominals:
            return False

        writes: list[tuple[str, ast.AST]] = []
        for member in class_node.body:
            if not isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            member_qname = f"{self.module_name}.{class_name}.{member.name}"
            for node in ast.walk(member):
                if (
                    isinstance(node, ast.Attribute)
                    and isinstance(node.value, ast.Name)
                    and node.value.id == "self"
                    and node.attr == field_name
                    and isinstance(node.ctx, (ast.Store, ast.Del))
                ):
                    return False
                if not isinstance(node, ast.Call):
                    continue
                parts = _attribute_parts(node.func)
                is_object_setattr = parts == ("object", "__setattr__")
                is_builtin_setattr = parts == ("setattr",)
                if not (is_object_setattr or is_builtin_setattr):
                    continue
                if not node.args or not isinstance(node.args[0], ast.Name) or node.args[0].id != "self":
                    continue
                if len(node.args) < 2 or not isinstance(node.args[1], ast.Constant):
                    return False
                if node.args[1].value != field_name:
                    continue
                if not is_object_setattr or len(node.args) != 3 or node.keywords:
                    return False
                writes.append((member_qname, node.args[2]))
        if len(writes) != 1 or writes[0][0] != constructor.qname:
            return False
        stored_value = writes[0][1]
        if not isinstance(stored_value, ast.Name) or stored_value.id != parameter_name:
            return False
        constructor_bindings = self._function_bindings(constructor)
        if (
            constructor_bindings.counts[parameter_name] != 1
            or parameter_name in constructor_bindings.deleted
        ):
            return False

        callers: list[tuple[_FunctionInfo, ast.Call]] = []
        for caller in self.functions.values():
            for node in ast.walk(caller.node):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == class_name
                ):
                    callers.append((caller, node))
        if not callers:
            return False
        expected_caller = _EXPLICIT_CONSTRUCTOR_CALLERS[class_name]
        if {caller.qname for caller, _call in callers} != {expected_caller}:
            return False
        allow_none = "None" in parameter_nominals
        for caller, call in callers:
            argument = self._constructor_argument(call, constructor, parameter_name)
            if argument is None or not self._expression_has_nominal_provenance(
                argument,
                caller=caller,
                nominal=nominal,
                allow_none=allow_none,
            ):
                return False
        if field_name in {"_slot", "_parent_slot"} and class_name in _PARENT_SLOT_PAIRS:
            if not self._prove_parent_pairs(class_name):
                return False
        return True

    @staticmethod
    def _literal_flow_slot(expression: ast.AST) -> int | None:
        if (
            isinstance(expression, ast.Subscript)
            and _attribute_parts(expression.value) == ("self", "_slots")
            and isinstance(expression.slice, ast.Constant)
            and type(expression.slice.value) is int
            and 0 <= expression.slice.value <= 22
        ):
            return expression.slice.value
        return None

    def _prove_parent_pairs(self, class_name: str) -> bool:
        cached = self._parent_pair_cache.get(class_name)
        if cached is not None:
            return cached
        self._parent_pair_cache[class_name] = False
        constructor = self.functions.get(f"{self.module_name}.{class_name}.__init__")
        expected = _PARENT_SLOT_PAIRS.get(class_name)
        if constructor is None or expected is None:
            return False
        pairs: list[tuple[int, int | None]] = []
        expected_caller = _EXPLICIT_CONSTRUCTOR_CALLERS[class_name]
        for caller in self.functions.values():
            for candidate in ast.walk(caller.node):
                if (
                    not isinstance(candidate, ast.Call)
                    or not isinstance(candidate.func, ast.Name)
                    or candidate.func.id != class_name
                ):
                    continue
                if caller.qname != expected_caller:
                    return False
                slot = self._constructor_argument(candidate, constructor, "slot")
                parent = self._constructor_argument(candidate, constructor, "parent_slot")
                slot_index = self._literal_flow_slot(slot) if slot is not None else None
                parent_index = self._literal_flow_slot(parent) if parent is not None else None
                if slot_index is None or (
                    parent_index is None
                    and not (isinstance(parent, ast.Constant) and parent.value is None)
                ):
                    return False
                pairs.append((slot_index, parent_index))
        if len(pairs) != len(expected) or frozenset(pairs) != expected:
            return False
        self._parent_pair_cache[class_name] = True
        return True

    def _optional_parent_dominates(self, call: ast.Call, *, class_name: str) -> bool:
        if class_name not in {"H11RootDirectoryView", "H11RootJsonSourceView"}:
            return False
        current: ast.AST = call
        while current in self._parents:
            parent = self._parents[current]
            if isinstance(parent, (ast.Lambda, ast.comprehension)):
                return False
            if isinstance(parent, ast.If):
                test = parent.test
                direct_none = (
                    isinstance(test, ast.Compare)
                    and len(test.ops) == 1
                    and isinstance(test.ops[0], ast.Is)
                    and len(test.comparators) == 1
                    and _attribute_parts(test.left) == ("self", "_parent_slot")
                    and isinstance(test.comparators[0], ast.Constant)
                    and test.comparators[0].value is None
                )
                if direct_none:
                    return any(
                        current is node or current in set(ast.walk(node))
                        for node in parent.orelse
                    )
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                break
            current = parent
        return False

    def _literal_receiver_nominal(
        self,
        expression: ast.AST,
        *,
        local_bound: set[str],
    ) -> str | None:
        if isinstance(expression, ast.Dict):
            return "builtins.dict"
        if isinstance(expression, ast.List):
            return "builtins.list"
        if isinstance(expression, ast.Set):
            return "builtins.set"
        if isinstance(expression, ast.Tuple):
            return "builtins.tuple"
        if isinstance(expression, ast.Constant):
            if type(expression.value) is str:
                return "builtins.str"
            if type(expression.value) is bytes:
                return "builtins.bytes"
        if (
            isinstance(expression, ast.Call)
            and isinstance(expression.func, ast.Name)
            and expression.func.id in {"dict", "list", "set", "tuple"}
            and expression.func.id not in local_bound
            and not any(isinstance(argument, ast.Starred) for argument in expression.args)
            and not any(keyword.arg is None for keyword in expression.keywords)
        ):
            return f"builtins.{expression.func.id}"
        return None

    def _prove_parameter_nominal(
        self,
        info: _FunctionInfo,
        parameter_name: str,
        nominal: str,
        *,
        seen: frozenset[tuple[str, str]] = frozenset(),
    ) -> bool:
        key = (info.qname, parameter_name)
        if key in seen:
            return False
        parameters = {
            argument.arg: argument
            for argument in (
                *info.node.args.posonlyargs,
                *info.node.args.args,
                *info.node.args.kwonlyargs,
            )
        }
        parameter = parameters.get(parameter_name)
        bindings = self._function_bindings(info)
        if (
            parameter is None
            or nominal not in self._annotation_nominals(parameter.annotation)
            or bindings.counts[parameter_name] != 1
            or parameter_name in bindings.deleted
        ):
            return False
        callers: list[tuple[_FunctionInfo, ast.Call]] = []
        leaf = info.qname.rsplit(".", 1)[1]
        for caller in self.functions.values():
            for candidate in ast.walk(caller.node):
                if (
                    isinstance(candidate, ast.Call)
                    and isinstance(candidate.func, ast.Name)
                    and candidate.func.id == leaf
                ):
                    callers.append((caller, candidate))
        if not callers:
            return False
        for caller, call in callers:
            argument = self._constructor_argument(call, info, parameter_name)
            if argument is None:
                return False
            if self._expression_has_nominal_provenance(
                argument,
                caller=caller,
                nominal=nominal,
                allow_none=False,
            ):
                continue
            if (
                not isinstance(argument, ast.Name)
                or not self._prove_parameter_nominal(
                    caller,
                    argument.id,
                    nominal,
                    seen=seen | {key},
                )
            ):
                return False
        return True

    def _prove_reference_property_dict(
        self,
        expression: ast.AST,
        *,
        info: _FunctionInfo,
    ) -> bool:
        if (
            info.qname != f"{self.module_name}._prove_h11_direct_authority_bindings"
            or not isinstance(expression, ast.Attribute)
            or expression.attr != "reference"
            or not isinstance(expression.value, ast.Name)
            or expression.value.id not in {
                "ready_commit_fifo_reference", "permit_commit_fifo_reference"
            }
            or not self._prove_parameter_nominal(
                info,
                expression.value.id,
                "H11RootFifoReference",
            )
            or not self._prove_exact_nominal_class("H11RootFifoReference")
        ):
            return False
        property_info = self.functions.get(
            f"{self.module_name}.H11RootFifoReference.reference"
        )
        if property_info is None or self._method_decorator_names(property_info.node) != ("property",):
            return False
        returns = [node for node in ast.walk(property_info.node) if isinstance(node, ast.Return)]
        return (
            len(returns) == 1
            and property_info.node.body[-1] is returns[0]
            and isinstance(returns[0].value, ast.Dict)
        )

    def _prove_systemd_character_call(self, call: ast.Call, *, info: _FunctionInfo) -> bool:
        if (
            info.qname != f"{self.module_name}._systemd_unit_object_path"
            or not isinstance(call.func, ast.Attribute)
            or call.func.attr not in {"isascii", "isalnum"}
            or not isinstance(call.func.value, ast.Name)
            or call.func.value.id != "character"
            or tuple(argument.arg for argument in info.node.args.args) != ("unit",)
            or self._annotation_nominals(info.node.args.args[0].annotation)
            != frozenset({"str"})
        ):
            return False
        current: ast.AST = call
        while current in self._parents:
            current = self._parents[current]
            if isinstance(current, ast.GeneratorExp):
                if len(current.generators) != 1:
                    return False
                generator = current.generators[0]
                return (
                    isinstance(generator.target, ast.Name)
                    and generator.target.id == "character"
                    and isinstance(generator.iter, ast.Name)
                    and generator.iter.id == "unit"
                )
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                break
        return False

    def _prove_systemd_regex_call(self, call: ast.Call, *, info: _FunctionInfo) -> bool:
        if (
            info.qname != f"{self.module_name}._systemd_unit_object_path"
            or _attribute_parts(call.func) != ("_UNIT_RE", "fullmatch")
            or self._module_bindings.counts["_UNIT_RE"] != 1
            or self.imports.get("re") != "re"
        ):
            return False
        assignments = [
            node
            for node in self.tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "_UNIT_RE" for target in node.targets)
        ]
        if len(assignments) != 1:
            return False
        value = assignments[0].value
        return (
            isinstance(value, ast.Call)
            and _attribute_parts(value.func) == ("re", "compile")
            and len(value.args) == 1
            and not value.keywords
            and isinstance(value.args[0], ast.Constant)
            and type(value.args[0].value) is str
        )

    def _resolve_call(
        self,
        call: ast.Call,
        *,
        info: _FunctionInfo,
        local_types: dict[str, str],
        local_bound: set[str],
    ) -> tuple[str, str] | None:
        func = call.func
        if _attribute_parts(func) == ("object", "__setattr__"):
            class_name = info.class_name
            if (
                class_name in _EXPLICIT_FROZEN_FIELDS
                and info.node.name == "__init__"
                and self._prove_frozen_constructor(class_name)
                and any(
                    self._object_setattr_call(statement) is call
                    for statement in info.node.body
                )
            ):
                return "builtins.object.__setattr__", "FROZEN_CONSTRUCTOR_STORE"
            return None
        if isinstance(func, ast.Name):
            if func.id in self.classes:
                if func.id == "InstallerError":
                    return f"{self.module_name}.InstallerError", "DIRECT_CLASS"
                if not self._prove_exact_nominal_class(func.id):
                    return None
                target = f"{self.module_name}.{func.id}.__init__"
                return target, "DIRECT_CLASS"
            local = f"{self.module_name}.{func.id}"
            if local in self.functions:
                return local, "IMPORT"
            if func.id in self.imports and func.id not in local_bound:
                return self._canonical_external(self.imports[func.id]), "IMPORT"
            if func.id in _BUILTIN_NAMES or func.id in {"format", "type"}:
                return f"builtins.{func.id}", "IMPORT"
            return None

        if isinstance(func, ast.Attribute):
            literal_nominal = self._literal_receiver_nominal(
                func.value,
                local_bound=local_bound,
            )
            if literal_nominal is not None:
                target = f"{literal_nominal}.{func.attr}"
                return (target, "LITERAL_CONTAINER") if target in PURE_VALUE_NAMES else None
            if (
                func.attr == "items"
                and self._prove_reference_property_dict(func.value, info=info)
            ):
                return "builtins.dict.items", "FROZEN_FIELD"
            if self._prove_systemd_character_call(call, info=info):
                return f"builtins.str.{func.attr}", "LITERAL_CONTAINER"
            if self._prove_systemd_regex_call(call, info=info):
                return "re.fullmatch", "IMPORT"

        parts = _attribute_parts(func)
        if parts is not None:
            head, *tail = parts
            if head == "self" and info.class_name is not None and len(tail) == 1:
                target = f"{self.module_name}.{info.class_name}.{tail[0]}"
                return (
                    (target, "SELF_RECEIVER")
                    if self._is_explicit_instance_method(info)
                    and target in self.functions
                    and (
                        target in EXPECTED_INTERNAL_QNAMES
                        or self._prove_exact_nominal_class(info.class_name)
                    )
                    else None
                )
            if head == "self" and info.class_name is not None and len(tail) == 2:
                target = _FROZEN_FIELD_METHODS.get((info.class_name, tail[0], tail[1]))
                optional_parent = tail[0] == "_parent_slot" and info.class_name in {
                    "H11RootDirectoryView", "H11RootJsonSourceView"
                }
                return (
                    (
                        target,
                        "FROZEN_OPTIONAL_PARENT" if optional_parent else "FROZEN_FIELD",
                    )
                    if target is not None
                    and self._is_explicit_instance_method(info)
                    and self._prove_frozen_field(
                        info=info,
                        field_name=tail[0],
                        target=target,
                    )
                    and (not optional_parent or self._optional_parent_dominates(call, class_name=info.class_name))
                    else None
                )
            if head in self.classes and len(tail) == 1:
                target = f"{self.module_name}.{head}.{tail[0]}"
                if not self._prove_exact_nominal_class(head):
                    return None
                if target in _FACTORY_RESULTS and not self._prove_factory(target):
                    return None
                return (target, "DIRECT_CLASS") if target in self.functions or target in EXPECTED_INTERNAL_QNAMES else None
            if len(tail) >= 1:
                receiver = func.value if isinstance(func, ast.Attribute) else None
                nominal = (
                    self._expression_nominal(
                        receiver,
                        info=info,
                        local_types=local_types,
                        require_field_proof=True,
                    )
                    if receiver is not None
                    else None
                )
            else:
                nominal = None
            if nominal is not None:
                if nominal.startswith("builtins.") or nominal == "pathlib.Path":
                    target = f"{nominal}.{parts[-1]}"
                    return (target, "LITERAL_CONTAINER") if target in PURE_VALUE_NAMES else None
                if not self._prove_exact_nominal_class(nominal):
                    return None
                target = f"{self.module_name}.{nominal}.{parts[-1]}"
                rule = (
                    "PHASE_CURSOR"
                    if head == "phase_data"
                    else "FROZEN_FIELD"
                    if len(parts) > 2
                    else "ONE_ASSIGN"
                )
                return (target, rule) if target in self.functions else None
            mono_class = _MONO_PARAM_CLASSES.get((info.qname, head))
            if mono_class is not None and len(tail) == 1:
                target = f"{self.module_name}.{mono_class}.{tail[0]}"
                return (target, "MONO_PARAM") if target in EXPECTED_INTERNAL_QNAMES else None
            if head in self.imports and head not in local_bound:
                origin = self.imports[head]
                return self._canonical_external(".".join((origin, *tail))), "IMPORT"
            if head in _BUILTIN_CLASSES and len(tail) == 1:
                return f"builtins.{head}.{tail[0]}", "DIRECT_CLASS"
            if head == "libc" and tail == ["renameat2"]:
                return "ctypes.CDLL.renameat2", "NATIVE_SYMBOL"

        # The only accepted dynamic subscript receiver is the literal flow slot.
        if isinstance(func, ast.Attribute) and func.attr in {"open", "borrow", "detach"}:
            receiver = func.value
            if (
                isinstance(receiver, ast.Subscript)
                and isinstance(receiver.value, ast.Attribute)
                and isinstance(receiver.value.value, ast.Name)
                and receiver.value.value.id == "self"
                and receiver.value.attr == "_slots"
                and isinstance(receiver.slice, ast.Constant)
                and type(receiver.slice.value) is int
                and 0 <= receiver.slice.value <= 22
                and info.class_name == "H11RootAuthorizationFlow"
                and self._is_explicit_instance_method(info)
            ):
                return f"{self.module_name}.H11OwnedFdSlot.{func.attr}", "LITERAL_SLOT"

        if (
            isinstance(func, ast.Attribute)
            and func.attr == "hexdigest"
            and isinstance(func.value, ast.Call)
            and _attribute_parts(func.value.func) == ("hashlib", "sha256")
        ):
            return "hashlib.sha256.hexdigest", "HASH_RESULT"
        return None

    @staticmethod
    def _canonical_external(name: str) -> str:
        if name == "pathlib.Path":
            return name
        return name

    def _classify(self, canonical: str) -> TargetKind | None:
        if canonical.startswith(f"{self.module_name}.") and canonical.endswith(".__init__"):
            class_name = canonical.removeprefix(f"{self.module_name}.").removesuffix(".__init__")
            if class_name in _GENERATED_CLASSES:
                return "pure-value" if self._prove_exact_nominal_class(class_name) else None
            if f"{self.module_name}.{class_name}.__init__" in self.functions:
                return "internal" if self._prove_exact_nominal_class(class_name) else None
        if canonical in self.functions or canonical in EXPECTED_INTERNAL_QNAMES:
            return "internal"
        if canonical in SENSITIVE_NAMES:
            return "sensitive"
        if canonical in PURE_VALUE_NAMES:
            return "pure-value"
        return None

    def _is_generated_dataclass(self, class_name: str) -> bool:
        node = self.classes.get(class_name)
        if node is None:
            return False
        if any(
            isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
            and member.name == "__init__"
            for member in node.body
        ):
            return False
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            if not isinstance(decorator.func, ast.Name) or decorator.func.id != "dataclass":
                continue
            keywords = {
                keyword.arg: keyword.value
                for keyword in decorator.keywords
                if keyword.arg is not None
            }
            return (
                isinstance(keywords.get("frozen"), ast.Constant)
                and keywords["frozen"].value is True
                and isinstance(keywords.get("slots"), ast.Constant)
                and keywords["slots"].value is True
            )
        return False


def _scan_snippet(body: str, *, prelude: str = "") -> H11ScanResult:
    source = f"{prelude}\ndef authorize_h11_release():\n"
    source += "\n".join(f"    {line}" for line in body.splitlines()) + "\n"
    return H11ReachableCallScanner(source).scan(ROOT_QNAME)


def _failure_reasons(result: H11ScanResult) -> tuple[str, ...]:
    return tuple(item.reason for item in (*result.unresolved, *result.multi_target, *result.unclassified))


def _c2e_new_flow_fifo_peer(
    paths: dict[str, Path],
    production: Any,
    frames: list[bytes],
    errors: list[BaseException],
) -> None:
    root = paths["authorization"].parents[3]
    ready_path = root / "fifo" / "h11-ready-committed.fifo"
    permit_path = root / "fifo" / "h11-permit-committed.fifo"
    descriptor = -1
    try:
        descriptor = os.open(ready_path, os.O_WRONLY | os.O_CLOEXEC)
        written = os.write(descriptor, production.H11_READY_COMMITTED_BYTES)
        if written != len(production.H11_READY_COMMITTED_BYTES):
            raise AssertionError("C2e READY peer write was incomplete")
        os.close(descriptor)
        descriptor = -1
        descriptor = os.open(permit_path, os.O_RDONLY | os.O_CLOEXEC)
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 4096)
            if not chunk:
                break
            chunks.append(chunk)
        frames.append(b"".join(chunks))
    except BaseException as exc:
        errors.append(exc)
    finally:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass


@dataclass(frozen=True, slots=True)
class H11SiteIdentity:
    static_site_rule: str
    caller_qname: str
    boundary_kind: Literal["open", "fstat", "prove", "decode", "revalidate", "observe"]
    callee_qname: str
    literal_slot_or_receiver: int | str | None
    occurrence_label: str
    semantic_role_or_none: str | None = None
    equivalence_class_or_none: str | None = None
    install_ordinal_or_none: int | None = None
    semantic_ordinal_or_none: int | None = None


@dataclass(frozen=True, slots=True)
class BoundaryExecution:
    site_identity: H11SiteIdentity
    execution_ordinal: int


@dataclass(frozen=True, slots=True)
class H11TraceEvent:
    event_kind: Literal["enter", "complete", "fail", "unwind"]
    execution: BoundaryExecution


FixtureClass = tuple[str, str, int | None]


CANONICAL_INDIRECT_CLASSES: tuple[FixtureClass, ...] = (
    ("tree/directory/formal-root", "formal-root", None),
    ("tree/directory/sealed-root", "sealed-root", None),
    ("tree/directory/input-root", "input-root", None),
    ("tree/directory/work-root", "work-root", None),
    ("tree/directory/fifo-root", "fifo-root", None),
    ("tree/directory/authority-root", "authority-root", None),
    ("tree/fifo/closer-ready", "closer-ready", None),
    ("tree/fifo/closer-release", "closer-release", None),
    ("tree/fifo/exec-stop-post-ready", "exec-stop-post-ready", None),
    ("tree/fifo/exec-stop-post-release", "exec-stop-post-release", None),
    ("tree/fifo/h11-permit-commit", "h11-permit-commit", None),
    ("tree/fifo/h11-ready-commit", "h11-ready-commit", None),
    ("tree/fifo/run-main-ready", "run-main-ready", None),
    ("tree/fifo/run-main-release", "run-main-release", None),
    ("tree/prepare-manifest", "prepare-manifest", None),
    ("seal/manifest", "seal-manifest", None),
    ("preflight/inventory", "preflight-manifest", None),
    ("seal/file/close-fragment", "close-fragment", None),
    ("seal/file/close-plan", "close-plan", None),
    ("seal/file/close-program", "close-program", None),
    ("seal/file/gc-fragment", "gc-fragment", None),
    ("seal/file/harness-program", "harness-program", None),
    ("seal/file/installer-program", "installer-program", None),
    ("seal/file/run-fragment", "run-fragment", None),
    ("seal/file/run-plan", "run-plan", None),
    ("seal/file/run-program", "run-program", None),
    ("seal/file/start-descriptor", "start-descriptor", None),
    ("seal/file/stop-plan", "stop-plan", None),
    ("seal/file/stop-program", "stop-program", None),
    ("install/target/run-fragment", "run-fragment", 0),
    ("install/target/close-fragment", "close-fragment", 1),
    ("install/target/gc-fragment", "gc-fragment", 2),
)

EXPANDED_ASSET_LITERALS = (
    ("aaa-expanded-asset", b"scion-expanded-a\n", "aaa-expanded-asset"),
    ("zzz-expanded-asset", b"scion-expanded-z\n", "zzz-expanded-asset"),
)
EXPANDED_CLASS_LITERALS: tuple[FixtureClass, ...] = (
    ("seal/file/aaa-expanded-asset", "aaa-expanded-asset", None),
    ("seal/file/zzz-expanded-asset", "zzz-expanded-asset", None),
)
EXPANDED_INDIRECT_CLASSES = (
    CANONICAL_INDIRECT_CLASSES[:17]
    + EXPANDED_CLASS_LITERALS[:1]
    + CANONICAL_INDIRECT_CLASSES[17:29]
    + EXPANDED_CLASS_LITERALS[1:]
    + CANONICAL_INDIRECT_CLASSES[29:]
)
REORDERED_INDIRECT_CLASSES = CANONICAL_INDIRECT_CLASSES
REORDERED_RAW_SEAL_ROLES = (
    "stop-program",
    "stop-plan",
    "start-descriptor",
    "run-program",
    "run-plan",
    "run-fragment",
    "installer-program",
    "harness-program",
    "gc-fragment",
    "close-program",
    "close-plan",
    "close-fragment",
    "preflight-manifest",
)


class H11ScheduleOracle:
    def __init__(self) -> None:
        self.events: list[H11TraceEvent] = []
        self._next_ordinal = 0

    def call(self, site: H11SiteIdentity, children: Sequence[Any] = ()) -> BoundaryExecution:
        execution = BoundaryExecution(site, self._next_ordinal)
        self._next_ordinal += 1
        self.events.append(H11TraceEvent("enter", execution))
        for child in children:
            child()
        self.events.append(H11TraceEvent("complete", execution))
        return execution

    @staticmethod
    def _site(
        rule: str,
        caller: str,
        kind: Literal["open", "fstat", "prove", "decode", "revalidate", "observe"],
        callee: str,
        receiver: int | str | None,
        label: str,
        *,
        role: str | None = None,
        equivalence_class: str | None = None,
        install_ordinal: int | None = None,
        semantic_ordinal: int | None = None,
    ) -> H11SiteIdentity:
        return H11SiteIdentity(
            rule,
            caller,
            kind,
            callee,
            receiver,
            label,
            role,
            equivalence_class,
            install_ordinal,
            semantic_ordinal,
        )

    def open(self, slot: int, role: str, parent: int | None) -> None:
        self.call(
            self._site(
                f"ACQUIRE_OPEN_SLOT_{slot}",
                f"{M}.H11RootAuthorizationFlow._acquire_authorities",
                "open",
                f"{M}.H11OwnedFdSlot.open",
                slot,
                f"open:{role}:parent={parent}",
                role=role,
            )
        )

    def fstat(self, slot: int, label: str, *, caller: str) -> None:
        self.call(self._site(f"FSTAT_SLOT_{slot}_{label}", caller, "fstat", "os.fstat", slot, label))

    def pin_json(self, slot: int, role: str, parent: int | None) -> None:
        caller = f"{M}.H11RootAuthorizationFlow._acquire_authorities"
        self.open(slot, role, parent)
        self.fstat(slot, "pin-pre", caller=caller)
        self.fstat(slot, "pin-post", caller=caller)
        self.call(
            self._site(
                f"DECODE_JSON_SLOT_{slot}",
                caller,
                "decode",
                f"{M}._decode_h11_canonical_frozen_object",
                slot,
                "initial",
                role=role,
            )
        )

    def revalidate_json(self, slot: int, wave: str) -> None:
        caller = f"{M}.H11RootAuthorizationFlow._acquire_authorities"
        view = f"{M}.H11RootJsonSourceView.revalidate"
        self.call(
            self._site(f"REVALIDATE_JSON_SLOT_{slot}", caller, "revalidate", view, slot, wave),
            (lambda: self.fstat(slot, f"revalidate:{wave}", caller=view),),
        )

    def decode_directory(self, slot: int) -> None:
        self.call(
            self._site(
                f"DECODE_DIRECTORY_SLOT_{slot}",
                f"{M}.H11RootAuthorizationFlow._acquire_authorities",
                "decode",
                f"{M}.H11RootDirectoryReference.decode",
                slot,
                "initial",
            )
        )

    def prove_directory(self, slot: int, label: str) -> None:
        self.call(
            self._site(
                f"PROVE_DIRECTORY_SLOT_{slot}_{label}",
                f"{M}.H11RootDirectoryView.revalidate" if label != "pre-open" else f"{M}.H11RootAuthorizationFlow._acquire_authorities",
                "prove",
                f"{M}.H11RootDirectoryReference.prove",
                slot,
                label,
            )
        )

    def revalidate_directory(self, slot: int, wave: str) -> None:
        caller = f"{M}.H11RootAuthorizationFlow._acquire_authorities"
        view = f"{M}.H11RootDirectoryView.revalidate"
        self.call(
            self._site(f"REVALIDATE_DIRECTORY_SLOT_{slot}", caller, "revalidate", view, slot, wave),
            (
                lambda: self.fstat(slot, f"revalidate:{wave}", caller=view),
                lambda: self.prove_directory(slot, f"opened:{wave}"),
                lambda: self.prove_directory(slot, f"current:{wave}"),
            ),
        )

    def pin_directory(self, slot: int, role: str, parent: int | None) -> None:
        self.open(slot, role, parent)
        self.prove_directory(slot, "pre-open")
        self.revalidate_directory(slot, "initial")

    def decode_fifo(self, slot: int) -> None:
        self.call(
            self._site(
                f"DECODE_FIFO_SLOT_{slot}",
                f"{M}.H11RootAuthorizationFlow._acquire_authorities",
                "decode",
                f"{M}.H11RootFifoReference.decode",
                slot,
                "initial",
            )
        )

    def prove_fifo(self, slot: int, label: str) -> None:
        self.call(
            self._site(
                f"PROVE_FIFO_SLOT_{slot}_{label}",
                f"{M}.H11RootFifoView.revalidate",
                "prove",
                f"{M}.H11RootFifoReference.prove",
                slot,
                label,
            )
        )

    def revalidate_fifo(self, slot: int, wave: str) -> None:
        caller = f"{M}.H11RootAuthorizationFlow._acquire_authorities"
        view = f"{M}.H11RootFifoView.revalidate"
        self.call(
            self._site(f"REVALIDATE_FIFO_SLOT_{slot}", caller, "revalidate", view, slot, wave),
            (
                lambda: self.fstat(slot, f"revalidate:{wave}", caller=view),
                lambda: self.prove_fifo(slot, f"opened:{wave}"),
                lambda: self.prove_fifo(slot, f"current:{wave}"),
            ),
        )

    def pin_fifo(self, slot: int, role: str) -> None:
        self.open(slot, role, 9)
        self.revalidate_fifo(slot, "initial")

    def inventory(self) -> None:
        caller = f"{M}._build_h11_indirect_authority_inventory"
        children = tuple(
            lambda callee=callee, label=label: self.call(
                self._site(
                    f"INVENTORY_{label}",
                    caller,
                    "prove",
                    f"{M}.{callee}",
                    label,
                    label,
                )
            )
            for callee, label in (
                ("_prove_h11_direct_authority_bindings", "direct"),
                ("_build_h11_tree_indirect_specs", "tree"),
                ("_build_h11_seal_indirect_specs", "seal"),
                ("_prove_h11_preflight_snapshot_bindings", "preflight"),
                ("_build_h11_install_target_specs", "install"),
            )
        )
        self.call(
            self._site(
                "BUILD_INDIRECT_INVENTORY",
                f"{M}.H11RootAuthorizationFlow._acquire_authorities",
                "prove",
                caller,
                "inventory",
                "inventory",
            ),
            children,
        )

    def observe(self, fixture_class: FixtureClass, semantic_ordinal: int) -> None:
        equivalence_class, role, install_ordinal = fixture_class
        self.call(
            self._site(
                "OBSERVE_INDIRECT_AUTHORITY",
                f"{M}.H11RootAuthorizationFlow._acquire_authorities",
                "observe",
                f"{M}._observe_h11_indirect_authority",
                "spec",
                "inventory-observe",
                role=role,
                equivalence_class=equivalence_class,
                install_ordinal=install_ordinal,
                semantic_ordinal=semantic_ordinal,
            )
        )


_JSON_SLOTS = (
    (22, "authorization-source", 12),
    (21, "harness-source", None),
    (20, "install-receipt-source", None),
    (19, "install-manifest-source", None),
    (18, "tree-receipt-source", None),
    (17, "seal-receipt-source", None),
    (16, "preflight-receipt-source", None),
)
_DIRECTORY_SLOTS = (
    (15, "formal-root", None),
    (14, "authority-root", 15),
    (13, "harness-root", 14),
    (12, "scenario-root", 13),
    (11, "input-root", 15),
    (10, "receipt-root", 12),
    (9, "fifo-root", 15),
)
_FIFO_SLOTS = ((8, "h11-ready-commit"), (7, "h11-permit-commit"))


def build_c2e_golden_trace(classes: tuple[FixtureClass, ...]) -> tuple[H11TraceEvent, ...]:
    oracle = H11ScheduleOracle()
    oracle.call(
        oracle._site(
            "PROVE_EXECUTION_AUTHORITY",
            f"{M}.H11RootAuthorizationFlow._acquire_authorities",
            "prove",
            f"{M}._prove_h11_execution_authority",
            "process",
            "execution-authority",
        )
    )
    for slot, role, parent in _JSON_SLOTS:
        oracle.pin_json(slot, role, parent)
    for slot, _role, _parent in _DIRECTORY_SLOTS:
        oracle.decode_directory(slot)
    for slot, role, parent in _DIRECTORY_SLOTS:
        oracle.pin_directory(slot, role, parent)
    for slot, _role in _FIFO_SLOTS:
        oracle.decode_fifo(slot)
    for slot, role in _FIFO_SLOTS:
        oracle.pin_fifo(slot, role)
    for wave in ("authority-postbuild",):
        for slot, _role, _parent in _DIRECTORY_SLOTS:
            oracle.revalidate_directory(slot, wave)
        for slot, _role in _FIFO_SLOTS:
            oracle.revalidate_fifo(slot, wave)
    oracle.pin_json(6, "permit-ready-source", 12)
    oracle.pin_json(5, "run-armed-source", None)
    for wave in ("session-postbuild",):
        for slot, _role, _parent in _DIRECTORY_SLOTS:
            oracle.revalidate_directory(slot, wave)
        for slot, _role in _FIFO_SLOTS:
            oracle.revalidate_fifo(slot, wave)
    oracle.inventory()
    for slot in (22, 21, 20, 19, 18, 17, 16, 6, 5):
        oracle.revalidate_json(slot, "pre-observation")
    for semantic_ordinal, fixture_class in enumerate(classes):
        oracle.observe(fixture_class, semantic_ordinal)
    for slot in (22, 21, 20, 19, 18, 17, 16, 6, 5):
        oracle.revalidate_json(slot, "post-observation")
    oracle.call(
        oracle._site(
            "PROVE_INDIRECT_OBSERVATIONS",
            f"{M}.H11RootAuthorizationFlow._acquire_authorities",
            "prove",
            f"{M}._prove_h11_indirect_observations",
            "observations",
            "final",
        )
    )
    return tuple(oracle.events)


def _entered_executions(trace: Iterable[H11TraceEvent]) -> tuple[BoundaryExecution, ...]:
    return tuple(event.execution for event in trace if event.event_kind == "enter")


def _completed_observe_classes(trace: Iterable[H11TraceEvent]) -> tuple[FixtureClass, ...]:
    return tuple(
        (
            event.execution.site_identity.equivalence_class_or_none,
            event.execution.site_identity.semantic_role_or_none,
            event.execution.site_identity.install_ordinal_or_none,
        )
        for event in trace
        if event.event_kind == "complete"
        and event.execution.site_identity.boundary_kind == "observe"
    )  # type: ignore[return-value]


def _cross_fixture_site_projection(site: H11SiteIdentity) -> H11SiteIdentity:
    return replace(site, semantic_ordinal_or_none=None)


def _canonical_json(value: Any) -> bytes:
    return str.encode(
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n",
        "ascii",
    )


def _frozen_json(value: Any) -> Any:
    if value is None or type(value) in {bool, int, str}:
        return value
    if type(value) is list:
        return tuple(_frozen_json(item) for item in value)
    if type(value) is dict:
        return tuple((key, _frozen_json(value[key])) for key in sorted(value))
    raise TypeError(type(value).__name__)


def _contains_mutable_json(value: Any) -> bool:
    if isinstance(value, (dict, list, set)):
        return True
    if type(value) is tuple:
        return any(_contains_mutable_json(item) for item in value)
    return False


def _asset_reference(path: Path) -> dict[str, str]:
    raw = path.read_bytes()
    info = path.lstat()
    return {
        "path": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "device": str(info.st_dev),
        "inode": str(info.st_ino),
        "mode": format(stat.S_IMODE(info.st_mode), "04o"),
        "uid": str(info.st_uid),
        "gid": str(info.st_gid),
    }


def _build_expanded_asset_rows(tmp_path: Path) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    sealed = tmp_path / "sealed"
    sealed.mkdir(mode=0o755)
    inventory_rows: list[dict[str, Any]] = []
    seal_rows: list[dict[str, Any]] = []
    for role, raw, leaf in EXPANDED_ASSET_LITERALS:
        path = sealed / leaf
        path.write_bytes(raw)
        path.chmod(0o444)
        reference = _asset_reference(path)
        inventory_rows.append(
            {
                "tag": "asset",
                "kind": "static-input",
                "role": role,
                "path": str(path),
                "reference": reference,
            }
        )
        seal_rows.append({"role": role, **reference})
    return tuple(inventory_rows), tuple(seal_rows)


@dataclass(frozen=True, slots=True)
class SensitiveSiteKey:
    caller_qname: str
    canonical_target: str
    lexical_target: str
    same_caller_occurrence: int


FaultOwner = Literal["boundary", "base-focused-syscall", "close-primitive"]


# This is an independently transcribed owner ledger for every supplemental
# §6.3 site.  Base §4.4/§7 sites remain owned by their accepted focused tests.
SUPPLEMENTAL_SENSITIVE_FAULT_OWNER: tuple[tuple[SensitiveSiteKey, FaultOwner], ...] = (
    (SensitiveSiteKey(f"{M}.H11RootAuthorizationFlow._acquire_authorities", "pathlib.Path.lstat", "Path.lstat", 0), "base-focused-syscall"),
    (SensitiveSiteKey(f"{M}.H11RootAuthorizationFlow._acquire_authorities", "pathlib.Path.lstat", "Path.lstat", 1), "base-focused-syscall"),
    (SensitiveSiteKey(f"{M}.H11RootAuthorizationFlow._acquire_authorities", "pathlib.Path.lstat", "Path.lstat", 2), "base-focused-syscall"),
    (SensitiveSiteKey(f"{M}.H11RootAuthorizationFlow._acquire_authorities", "pathlib.Path.lstat", "Path.lstat", 3), "base-focused-syscall"),
    (SensitiveSiteKey(f"{M}.H11RootAuthorizationFlow._acquire_authorities", "pathlib.Path.lstat", "Path.lstat", 4), "base-focused-syscall"),
    (SensitiveSiteKey(f"{M}.H11RootAuthorizationFlow._acquire_authorities", "pathlib.Path.lstat", "Path.lstat", 5), "base-focused-syscall"),
    (SensitiveSiteKey(f"{M}.H11RootAuthorizationFlow._acquire_authorities", "pathlib.Path.lstat", "Path.lstat", 6), "base-focused-syscall"),
    (SensitiveSiteKey(f"{M}.H11RootAuthorizationFlow._acquire_authorities", "pathlib.Path.lstat", "Path.lstat", 7), "base-focused-syscall"),
    (SensitiveSiteKey(f"{M}.H11RootAuthorizationFlow._acquire_authorities", "pathlib.Path.lstat", "Path.lstat", 8), "base-focused-syscall"),
    (SensitiveSiteKey(f"{M}.H11RootAuthorizationFlow._acquire_authorities", "pathlib.Path.lstat", "Path.lstat", 9), "base-focused-syscall"),
    (SensitiveSiteKey(f"{M}.H11RootAuthorizationFlow._acquire_authorities", "pathlib.Path.lstat", "Path.lstat", 10), "base-focused-syscall"),
    (SensitiveSiteKey(f"{M}.H11RootAuthorizationFlow._acquire_authorities", "pathlib.Path.lstat", "Path.lstat", 11), "base-focused-syscall"),
    (SensitiveSiteKey(f"{M}.H11RootAuthorizationFlow._acquire_authorities", "pathlib.Path.lstat", "Path.lstat", 12), "base-focused-syscall"),
    (SensitiveSiteKey(f"{M}.H11RootAuthorizationFlow._acquire_authorities", "pathlib.Path.lstat", "Path.lstat", 13), "base-focused-syscall"),
    (SensitiveSiteKey(f"{M}.H11RootAuthorizationFlow._acquire_authorities", "pathlib.Path.lstat", "Path.lstat", 14), "base-focused-syscall"),
    (SensitiveSiteKey(f"{M}.H11RootAuthorizationFlow._acquire_authorities", "pathlib.Path.lstat", "Path.lstat", 15), "base-focused-syscall"),
    (SensitiveSiteKey(f"{M}.H11RootAuthorizationFlow._acquire_authorities", "pathlib.Path.lstat", "Path.lstat", 16), "base-focused-syscall"),
    (SensitiveSiteKey(f"{M}._prove_h11_execution_authority", "pathlib.Path.resolve", "Path.resolve", 0), "boundary"),
    (SensitiveSiteKey(f"{M}.H11RootDirectoryView.revalidate", "pathlib.Path.lstat", "Path.lstat", 0), "base-focused-syscall"),
    (SensitiveSiteKey(f"{M}.H11RootJsonSourceView.revalidate", "pathlib.Path.lstat", "Path.lstat", 0), "base-focused-syscall"),
    (SensitiveSiteKey(f"{M}._observe_h11_indirect_authority", "pathlib.Path.lstat", "Path.lstat", 0), "boundary"),
    (SensitiveSiteKey(f"{M}.H11RootAuthorizationFlow._acquire_authorities", "os.geteuid", "os.geteuid", 0), "base-focused-syscall"),
    (SensitiveSiteKey(f"{M}.H11RootAuthorizationFlow._acquire_authorities", "os.getegid", "os.getegid", 0), "base-focused-syscall"),
    (SensitiveSiteKey(f"{M}.H11RootAuthorizationFlow._close_slot_once", "builtins.BaseException.add_note", "BaseException.add_note", 0), "close-primitive"),
    (SensitiveSiteKey(f"{M}.H11RootAuthorizationFlow._publish_permit", "ctypes.CDLL", "ctypes.CDLL", 0), "base-focused-syscall"),
    (SensitiveSiteKey(f"{M}.H11RootAuthorizationFlow._publish_permit", "ctypes.set_errno", "ctypes.set_errno", 0), "base-focused-syscall"),
    (SensitiveSiteKey(f"{M}.H11RootAuthorizationFlow._publish_permit", "ctypes.CDLL.renameat2", "libc.renameat2", 0), "base-focused-syscall"),
    (SensitiveSiteKey(f"{M}.H11RootAuthorizationFlow._publish_permit", "ctypes.get_errno", "ctypes.get_errno", 0), "base-focused-syscall"),
    (SensitiveSiteKey(f"{M}._decode_h11_canonical_frozen_object", "builtins.bytes.decode", "bytes.decode", 0), "boundary"),
    (SensitiveSiteKey(f"{M}._decode_h11_canonical_frozen_object", "json.loads", "json.loads", 0), "boundary"),
    (SensitiveSiteKey(f"{M}._decode_h11_canonical_frozen_object", "json.dumps", "json.dumps", 0), "boundary"),
    (SensitiveSiteKey(f"{M}._decode_h11_canonical_frozen_object", "builtins.str.encode", "str.encode", 0), "boundary"),
)


SWEEP_ORDER = tuple(range(23))
PrimaryAbi = Literal["identity-preserved", "installer-error-caused-by-oserror"]


@dataclass(frozen=True, slots=True)
class PrimaryState:
    execution: BoundaryExecution
    bound_slot_bitmap: tuple[bool, ...]
    flow_state: str
    commit_boundary: str
    exact_phase_data_type: str
    primary_abi: PrimaryAbi

    @property
    def cleanup_composition_key(self) -> tuple[Any, ...]:
        return (
            self.bound_slot_bitmap,
            self.flow_state,
            self.commit_boundary,
            self.exact_phase_data_type,
            self.primary_abi,
        )


def _primary_abi(site: H11SiteIdentity) -> PrimaryAbi:
    if site.boundary_kind == "prove":
        return "identity-preserved"
    return "installer-error-caused-by-oserror"


def primary_states_for_trace(trace: tuple[H11TraceEvent, ...]) -> tuple[PrimaryState, ...]:
    bound: set[int] = set()
    result: list[PrimaryState] = []
    for event in trace:
        if event.event_kind == "enter":
            result.append(
                PrimaryState(
                    event.execution,
                    tuple(index in bound for index in SWEEP_ORDER),
                    "NEW",
                    "PREWRITE",
                    "None",
                    _primary_abi(event.execution.site_identity),
                )
            )
        elif (
            event.event_kind == "complete"
            and event.execution.site_identity.boundary_kind == "open"
            and type(event.execution.site_identity.literal_slot_or_receiver) is int
        ):
            bound.add(event.execution.site_identity.literal_slot_or_receiver)
    return tuple(result)


def expected_secondary_indices(bitmap: tuple[bool, ...]) -> tuple[int, ...]:
    bound_slots = tuple(slot for slot in SWEEP_ORDER if bitmap[slot])
    if not bound_slots:
        return ()
    return tuple(
        dict.fromkeys(
            (
                bound_slots[0],
                bound_slots[(len(bound_slots) - 1) // 2],
                bound_slots[-1],
            )
        )
    )


DOMAIN_NEGATIVE_AXES = {
    "_prove_h11_direct_authority_bindings": (
        "source-class",
        "source-path",
        "source-hash",
        "source-identity",
        "authorization-projection",
        "ready-projection",
        "armed-projection",
        "harness-projection",
        "directory-chain",
        "slot19-slot20-binding",
        "missing",
        "extra",
        "duplicate",
        "foreign-flow",
    ),
    "_build_h11_tree_indirect_specs": (
        "schema",
        "phase",
        "directory-role",
        "directory-path",
        "directory-identity",
        "directory-mode",
        "directory-owner",
        "fifo-role",
        "fifo-path",
        "fifo-identity",
        "fifo-mode",
        "fifo-owner",
        "harness-acquisition",
        "armed-ready-release",
        "preflight-fifo",
        "prepare-manifest",
        "fixture-uid-gid",
        "commit-owner-translation",
        "commit-accepted-owner-identity",
        "duplicate",
        "alias",
        "order",
    ),
    "_build_h11_seal_indirect_specs": (
        "schema",
        "phase",
        "seal-manifest",
        "static-role-closure",
        "armed-plan-program",
        "install-source",
        "installer",
        "preflight-class",
        "extra-valid-row",
        "duplicate-role",
        "duplicate-path",
        "duplicate-identity",
    ),
    "_prove_h11_preflight_snapshot_bindings": (
        "schema",
        "path",
        "unit",
        "manifest-source-binding",
        "formal-root-binding",
        "harness-unit-binding",
        "tree-projection",
        "seal-projection",
        "fifo-equality",
        "inventory-reference",
        "asset-count",
    ),
    "_build_h11_install_target_specs": (
        "receipt",
        "manifest",
        "unit-role-ordinal",
        "manager-ledger",
        "source-path",
        "source-hash",
        "source-identity",
        "source-mode",
        "source-owner",
        "target-path",
        "target-hash",
        "target-identity",
        "target-mode",
        "target-owner",
        "source-member-merge",
        "target-alias",
    ),
}


@dataclass(slots=True)
class C2EInventoryFixture:
    production: Any
    arguments: dict[str, Any]
    documents: dict[str, dict[str, Any]]

    def with_document_delta(self, document: str, field: str, value: Any) -> dict[str, Any]:
        changed = json.loads(json.dumps(self.documents[document]))
        changed[field] = value
        arguments = dict(self.arguments)
        arguments[document] = self.production._decode_h11_canonical_frozen_object(
            _canonical_json(changed),
            label=f"C2e {document} single delta",
        )
        return arguments


def _build_c2e_inventory_fixture(
    tmp_path: Path,
    *,
    variant: Literal["canonical", "expanded", "reordered"] = "canonical",
) -> C2EInventoryFixture:
    production = _load_installer()
    accepted_fixtures = _load_accepted_fixture_tests()

    original_seal_tree = accepted_fixtures.installer.seal_tree

    def seal_tree_with_fixture_literal(manifest_path: Path, *, require_root: bool = True) -> Any:
        manifest = json.loads(manifest_path.read_text(encoding="ascii"))
        if variant == "expanded":
            inventory_path = next(
                Path(item["path"])
                for item in manifest["files"]
                if item["role"] == "preflight-manifest"
            )
            inventory_lines = inventory_path.read_text(encoding="ascii").splitlines(keepends=True)
            expanded_files: list[dict[str, str]] = []
            for role, raw, leaf in EXPANDED_ASSET_LITERALS:
                path = Path(manifest["formal_root"]) / "sealed" / leaf
                path.write_bytes(raw)
                path.chmod(0o444)
                info = path.lstat()
                inventory_lines.append(
                    "\t".join(
                        (
                            "asset",
                            role,
                            "static-input",
                            str(path),
                            hashlib.sha256(raw).hexdigest(),
                            str(info.st_dev),
                            str(info.st_ino),
                            "0444",
                        )
                    )
                    + "\n"
                )
                expanded_files.append(
                    {"role": role, "path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}
                )
            inventory_path.write_text("".join(inventory_lines), encoding="ascii")
            preflight_row = next(item for item in manifest["files"] if item["role"] == "preflight-manifest")
            preflight_row["sha256"] = hashlib.sha256(inventory_path.read_bytes()).hexdigest()
            manifest["files"].extend(expanded_files)
        if variant == "reordered":
            by_role = {item["role"]: item for item in manifest["files"]}
            manifest["files"] = [by_role[role] for role in REORDERED_RAW_SEAL_ROLES]
        manifest_path.write_bytes(_canonical_json(manifest))
        return original_seal_tree(manifest_path, require_root=require_root)

    if variant != "canonical":
        accepted_fixtures.installer.seal_tree = seal_tree_with_fixture_literal
    try:
        paths = accepted_fixtures._root_c2a_session_model(tmp_path)
    finally:
        accepted_fixtures.installer.seal_tree = original_seal_tree
    documents: dict[str, dict[str, Any]] = {
        "authorization_manifest": json.loads(paths["authorization"].read_text(encoding="ascii")),
        "harness_manifest": json.loads(paths["manifest"].read_text(encoding="ascii")),
        "permit_ready": json.loads(paths["ready"].read_text(encoding="ascii")),
        "run_armed": json.loads(paths["armed"].read_text(encoding="ascii")),
    }
    install_receipt_path = Path(documents["harness_manifest"]["installer_receipt"]["path"])
    documents["install_receipt"] = json.loads(install_receipt_path.read_text(encoding="ascii"))
    install_manifest_path = Path(documents["install_receipt"]["install_manifest"]["path"])
    tree_receipt_path = Path(documents["install_receipt"]["tree_receipt"]["path"])
    seal_receipt_path = Path(documents["install_receipt"]["seal_receipt"]["path"])
    preflight_receipt_path = Path(documents["install_receipt"]["preflight_receipt"]["path"])
    source_paths = {
        "authorization": paths["authorization"],
        "harness": paths["manifest"],
        "install_receipt": install_receipt_path,
        "install_manifest": install_manifest_path,
        "tree_receipt": tree_receipt_path,
        "seal_receipt": seal_receipt_path,
        "preflight_receipt": preflight_receipt_path,
        "permit_ready": paths["ready"],
        "run_armed": paths["armed"],
    }
    documents.update(
        {
            "install_manifest": json.loads(install_manifest_path.read_text(encoding="ascii")),
            "tree_receipt": json.loads(tree_receipt_path.read_text(encoding="ascii")),
            "seal_receipt": json.loads(seal_receipt_path.read_text(encoding="ascii")),
            "preflight_receipt": json.loads(preflight_receipt_path.read_text(encoding="ascii")),
        }
    )
    decoder = production._decode_h11_canonical_frozen_object
    arguments: dict[str, Any] = {
        name: decoder(_canonical_json(value), label=f"C2e canonical {name}")
        for name, value in documents.items()
    }
    arguments.update(
        {
            f"{name}_source_reference": _frozen_json(_asset_reference(path))
            for name, path in source_paths.items()
        }
    )
    directory_rows = {
        row["role"]: row
        for row in documents["harness_manifest"]["permit_authority"]["directory_chain"]
    }
    for argument_name, role in (
        ("formal_root_directory_reference", "formal-root"),
        ("authority_root_directory_reference", "authority-root"),
        ("harness_root_directory_reference", "harness-root"),
        ("scenario_root_directory_reference", "scenario-root"),
        ("input_root_directory_reference", "input-root"),
        ("receipt_root_directory_reference", "receipt-root"),
        ("fifo_root_directory_reference", "fifo-root"),
    ):
        arguments[argument_name] = production.H11RootDirectoryReference.decode(
            _frozen_json(directory_rows[role]),
            label=f"C2e canonical {role}",
        )
    process_euid = os.geteuid()
    process_egid = os.getegid()
    for argument_name, key in (
        ("ready_commit_fifo_reference", "ready_commit_fifo"),
        ("permit_commit_fifo_reference", "permit_commit_fifo"),
    ):
        arguments[argument_name] = production.H11RootFifoReference.decode(
            _frozen_json(documents["harness_manifest"]["permit_authority"][key]),
            label=f"C2e canonical {key}",
            require_root=False,
            process_euid=process_euid,
            process_egid=process_egid,
        )
    arguments.update(
        {
            "formal_root": Path(documents["authorization_manifest"]["formal_root"]),
            "require_root": False,
            "process_euid": process_euid,
            "process_egid": process_egid,
        }
    )
    assert set(arguments) == {
        "authorization_manifest",
        "harness_manifest",
        "install_receipt",
        "install_manifest",
        "tree_receipt",
        "seal_receipt",
        "preflight_receipt",
        "permit_ready",
        "run_armed",
        "authorization_source_reference",
        "harness_source_reference",
        "install_receipt_source_reference",
        "install_manifest_source_reference",
        "tree_receipt_source_reference",
        "seal_receipt_source_reference",
        "preflight_receipt_source_reference",
        "permit_ready_source_reference",
        "run_armed_source_reference",
        "formal_root_directory_reference",
        "authority_root_directory_reference",
        "harness_root_directory_reference",
        "scenario_root_directory_reference",
        "input_root_directory_reference",
        "receipt_root_directory_reference",
        "fifo_root_directory_reference",
        "ready_commit_fifo_reference",
        "permit_commit_fifo_reference",
        "formal_root",
        "require_root",
        "process_euid",
        "process_egid",
    }
    return C2EInventoryFixture(production, arguments, documents)


def test_c2e_oracle_is_bound_to_the_reviewed_design() -> None:
    assert hashlib.sha256(DESIGN.read_bytes()).hexdigest() == DESIGN_SHA256
    assert INSTALLER_SOURCE.is_file()


def test_c2e_legacy_module_symbol_and_factory_matrix_is_removed() -> None:
    tree = ast.parse(INSTALLER_SOURCE.read_text(encoding="utf-8"))
    module_definitions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert module_definitions.isdisjoint(LEGACY_MODULE_SYMBOLS)
    production = _load_installer()
    assert all(not hasattr(production, name) for name in LEGACY_MODULE_SYMBOLS)
    assert all(
        not hasattr(getattr(production, class_name), attribute_name)
        for class_name, attribute_name in LEGACY_CLASS_ATTRIBUTES
    )


def test_c2e_new_flow_e2e_commits_one_exact_frame_and_receipt(tmp_path: Path) -> None:
    production = _load_installer()
    paths = _load_accepted_fixture_tests()._root_c2a_session_model(tmp_path)
    harness = json.loads(paths["manifest"].read_text(encoding="ascii"))
    permit_fifo_reference = harness["permit_authority"]["permit_commit_fifo"]
    frames: list[bytes] = []
    peer_errors: list[BaseException] = []
    peer = threading.Thread(
        target=_c2e_new_flow_fifo_peer,
        args=(paths, production, frames, peer_errors),
        name="c2e-new-flow-fifo-peer",
    )
    peer.start()
    try:
        receipt = production.authorize_h11_release(
            paths["authorization"],
            require_root=False,
        )
    except BaseException:
        root = paths["authorization"].parents[3]
        ready_release = os.open(
            root / "fifo" / "h11-ready-committed.fifo",
            os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC,
        )
        try:
            permit_release = os.open(
                root / "fifo" / "h11-permit-committed.fifo",
                os.O_WRONLY | os.O_CLOEXEC,
            )
            os.close(permit_release)
        finally:
            os.close(ready_release)
        peer.join()
        raise
    peer.join()
    assert not peer.is_alive()
    assert peer_errors == []
    assert frames == [production.H11_PERMIT_COMMITTED_BYTES]
    assert receipt == {
        "schema": production.H11_COMMIT_FIFO_RECEIPT_SCHEMA,
        "phase": "permit-committed",
        "fifo": permit_fifo_reference,
        "payload_sha256": hashlib.sha256(
            production.H11_PERMIT_COMMITTED_BYTES
        ).hexdigest(),
        "byte_count": str(len(production.H11_PERMIT_COMMITTED_BYTES)),
    }


def test_c2e_scanner_accepts_only_resolved_classified_calls() -> None:
    result = _scan_snippet(
        """process_euid = os.geteuid()
encoded = str.encode(\"ok\", \"ascii\")
return len(encoded) + process_euid""",
        prelude="import os",
    )
    assert result.unresolved == ()
    assert result.multi_target == ()
    assert result.unclassified == ()
    assert result.resolved_call_count == result.reachable_ast_call_count == 3
    assert tuple((call.canonical_target, call.target_kind) for call in result.calls) == (
        ("os.geteuid", "sensitive"),
        ("builtins.str.encode", "sensitive"),
        ("builtins.len", "pure-value"),
    )


def test_c2e_scanner_forbidden_context_is_sensitive_only_after_classification() -> None:
    result = H11ReachableCallScanner(
        """def _conditional_internal():
    return len(())
def authorize_h11_release():
    return _conditional_internal() if flag else bool(0)
"""
    ).scan(ROOT_QNAME)
    assert result.unresolved == result.multi_target == result.unclassified == ()
    assert result.resolved_call_count == result.reachable_ast_call_count == 3
    assert tuple((call.canonical_target, call.target_kind) for call in result.calls) == (
        (f"{M}._conditional_internal", "internal"),
        ("builtins.bool", "pure-value"),
        ("builtins.len", "pure-value"),
    )


def test_c2e_scanner_scans_decorators_and_rejects_only_sensitive_calls_there() -> None:
    pure = H11ReachableCallScanner(
        """@len(())
def authorize_h11_release():
    return bool(0)
"""
    ).scan(ROOT_QNAME)
    assert pure.unresolved == pure.multi_target == pure.unclassified == ()
    assert tuple(call.canonical_target for call in pure.calls) == (
        "builtins.len",
        "builtins.bool",
    )

    sensitive = H11ReachableCallScanner(
        """import os
@os.open('/tmp/c2e', 0)
def authorize_h11_release():
    return bool(0)
"""
    ).scan(ROOT_QNAME)
    assert tuple(item.lexical_target for item in sensitive.unresolved) == ("os.open",)
    assert _failure_reasons(sensitive) == (
        "sensitive call in forbidden conditional/callback context",
    )
    assert tuple(call.canonical_target for call in sensitive.calls) == ("builtins.bool",)


@pytest.mark.parametrize(
    ("body", "prelude"),
    (
        ("owner.close()", ""),
        ("spec.path.lstat()", ""),
        ("cls()", ""),
        ("callback()", ""),
        ("self._slots[index].borrow()", ""),
        ("getattr(os, 'open')('/tmp/x', 0)", "import os"),
        ("selected = (os.open,)[0]\nselected('/tmp/x', 0)", "import os"),
        ("selected = os.open if flag else os.stat\nselected('/tmp/x', 0)", "import os"),
        ("hash_obj = hashlib.sha256(b'x')\nhash_obj.hexdigest()", "import hashlib"),
        ("_HEX_RE.fullmatch('0' * 64)", "import re\n_HEX_RE = re.compile(r'[0-9a-f]{64}')"),
        ("renameat2 = libc.renameat2\nrenameat2()", "import ctypes\nlibc = ctypes.CDLL(None, use_errno=True)"),
        ("reversed(())", ""),
        ("fn = lambda: os.open('/tmp/x', 0)", "import os"),
    ),
    ids=(
        "owner-close",
        "bound-path-lstat",
        "cls-constructor",
        "callback",
        "dynamic-slot",
        "getattr",
        "container-callable",
        "branch-callable",
        "escaped-hash-result",
        "bound-regex",
        "native-alias",
        "reversed",
        "conditional-context",
    ),
)
def test_c2e_scanner_adversarial_dynamic_calls_fail_closed(body: str, prelude: str) -> None:
    result = _scan_snippet(body, prelude=prelude)
    assert result.resolved_call_count < result.reachable_ast_call_count
    assert _failure_reasons(result)


def test_c2e_scanner_rejects_import_and_annotation_forgery() -> None:
    shadowed = H11ReachableCallScanner(
        """import os
os = object()
def authorize_h11_release():
    return os.geteuid()
"""
    ).scan(ROOT_QNAME)
    assert shadowed.unresolved

    annotation = H11ReachableCallScanner(
        """class Reference:
    def prove(self):
        return None
def authorize_h11_release():
    value: Reference
    return value.prove()
"""
    ).scan(ROOT_QNAME)
    assert annotation.unresolved


@pytest.mark.parametrize(
    "class_body",
    (
        "@dataclass(slots=True)\nclass H11RootValidatedFifo:\n    value: int",
        "@dataclass(frozen=True, slots=True)\nclass H11RootValidatedFifo:\n    value: int\n    def __init__(self, value):\n        self.value = value",
    ),
    ids=("not-frozen", "explicit-init"),
)
def test_c2e_scanner_rejects_non_generated_constructor_leaf(class_body: str) -> None:
    result = H11ReachableCallScanner(
        f"from dataclasses import dataclass\n{class_body}\n"
        "def authorize_h11_release():\n"
        "    return H11RootValidatedFifo(1)\n"
    ).scan(ROOT_QNAME)
    assert result.unresolved


def test_c2e_scanner_accepts_exact_generated_constructor_leaf() -> None:
    result = H11ReachableCallScanner(
        """from dataclasses import dataclass
@dataclass(frozen=True, slots=True)
class H11RootValidatedFifo:
    role: str
    path: str
    owner: str
    uid: int
    gid: int
    mode: int
    device: int
    inode: int
    accepted_owners: tuple
    @property
    def acquisition_reference(self):
        return {}
def authorize_h11_release():
    return H11RootValidatedFifo('r', 'p', 'o', 1, 2, 3, 4, 5, ())
"""
    ).scan(ROOT_QNAME)
    assert result.unresolved == result.multi_target == result.unclassified == ()
    assert result.calls[0].canonical_target == f"{M}.H11RootValidatedFifo.__init__"


def test_c2e_scanner_rejects_type_wide_frozen_field_without_exact_constructor() -> None:
    missing_constructor = H11ReachableCallScanner(
        """class H11RootDirectoryView:
    def revalidate(self):
        return self._slot.borrow()
"""
    ).scan(f"{M}.H11RootDirectoryView.revalidate")
    assert tuple(item.lexical_target for item in missing_constructor.unresolved) == (
        "self._slot.borrow",
    )


def test_c2e_scanner_proves_complete_frozen_field_constructor_and_callers() -> None:
    frozen = H11ReachableCallScanner(INSTALLER_SOURCE.read_text()).scan(
        f"{M}.H11RootDirectoryView.revalidate"
    )
    assert frozen.unresolved == frozen.multi_target == frozen.unclassified == ()
    borrow = next(call for call in frozen.calls if call.lexical_target == "self._slot.borrow")
    assert borrow.canonical_target == f"{M}.H11OwnedFdSlot.borrow"
    assert borrow.rule_id == "FROZEN_FIELD"


@pytest.mark.parametrize(
    "mutation",
    (
        "object.__setattr__(self, '_slot', replacement)",
        "self._slot = replacement",
        "setattr(self, '_slot', replacement)",
        "object.__setattr__(self, field_name, replacement)",
    ),
    ids=("second-object-store", "attribute-store", "builtin-setattr", "dynamic-field-store"),
)
def test_c2e_scanner_rejects_frozen_field_replacement(mutation: str) -> None:
    source = f"""from dataclasses import dataclass
class H11OwnedFdSlot:
    def borrow(self):
        return 1
@dataclass(frozen=True, slots=True, init=False)
class H11RootDirectoryView:
    _slot: H11OwnedFdSlot
    def __init__(self, *, slot: H11OwnedFdSlot):
        object.__setattr__(self, '_slot', slot)
    def replace(self, replacement, field_name='_slot'):
        {mutation}
    def revalidate(self):
        return self._slot.borrow()
def make_view():
    slot = H11OwnedFdSlot()
    return H11RootDirectoryView(slot=slot)
"""
    result = H11ReachableCallScanner(source).scan(
        f"{M}.H11RootDirectoryView.revalidate"
    )
    assert tuple(item.lexical_target for item in result.unresolved) == (
        "self._slot.borrow",
    )


def test_c2e_scanner_self_receiver_requires_exact_explicit_instance_method() -> None:
    positive = H11ReachableCallScanner(
        """class H11RootAuthorizationFlow:
    def authorize_once(self):
        return self._finish()
    def _finish(self):
        return None
"""
    ).scan(f"{M}.H11RootAuthorizationFlow.authorize_once")
    assert positive.unresolved == positive.multi_target == positive.unclassified == ()
    assert positive.calls[0].rule_id == "SELF_RECEIVER"


@pytest.mark.parametrize(
    "class_body",
    (
        "def authorize_once(receiver):\n        return receiver._finish()\n    def _finish(self):\n        return None",
        "@staticmethod\n    def authorize_once(self):\n        return self._finish()\n    def _finish(self):\n        return None",
        "@classmethod\n    def authorize_once(self):\n        return self._finish()\n    def _finish(self):\n        return None",
        "def authorize_once(self):\n        self = replacement\n        return self._finish()\n    def _finish(self):\n        return None",
        "def authorize_once(self):\n        del self\n        return self._finish()\n    def _finish(self):\n        return None",
        "def authorize_once(self):\n        return self._finish()",
    ),
    ids=("wrong-first-name", "staticmethod", "classmethod", "rebound", "deleted", "missing-target"),
)
def test_c2e_scanner_rejects_forged_self_receivers(class_body: str) -> None:
    result = H11ReachableCallScanner(
        f"class H11RootAuthorizationFlow:\n    {class_body}\n"
    ).scan(f"{M}.H11RootAuthorizationFlow.authorize_once")
    assert result.unresolved


def test_c2e_scanner_resolves_mono_params_and_literal_containers() -> None:

    mono = H11ReachableCallScanner(
        """class H11RootAuthorizationFlow:
    def _close_slot_once(self, slot):
        return slot.detach()
"""
    ).scan(f"{M}.H11RootAuthorizationFlow._close_slot_once")
    assert mono.unresolved == mono.unclassified == ()
    assert mono.calls[0].canonical_target == f"{M}.H11OwnedFdSlot.detach"
    assert mono.calls[0].rule_id == "MONO_PARAM"

    literal = _scan_snippet("items = []\nitems.append(1)\nreturn tuple(items)")
    assert literal.unresolved == literal.unclassified == ()
    assert tuple(call.canonical_target for call in literal.calls) == (
        "builtins.list.append",
        "builtins.tuple",
    )


def _scan_one_assign_case(extra: str, *, parameters: str = "") -> H11ScanResult:
    source = INSTALLER_SOURCE.read_text() + f"""
def c2e_one_assign_test({parameters}):
    slot = H11OwnedFdSlot(role="test")
{extra}
    return slot.borrow()
"""
    return H11ReachableCallScanner(source).scan(f"{M}.c2e_one_assign_test")


def test_c2e_scanner_one_assign_accepts_only_one_simple_constructor_binding() -> None:
    result = _scan_one_assign_case("    pass")
    assert result.unresolved == result.multi_target == result.unclassified == ()
    assert tuple(call.rule_id for call in result.calls if call.lexical_target == "slot.borrow") == (
        "ONE_ASSIGN",
    )


@pytest.mark.parametrize(
    ("extra", "parameters"),
    (
        ("    slot += replacement", ""),
        ("    (slot := replacement)", ""),
        ("    for slot in items:\n        pass", ""),
        ("    with manager as slot:\n        pass", ""),
        ("    try:\n        pass\n    except Exception as slot:\n        pass", ""),
        ("    slot, other = pair", ""),
        ("    pass", "slot"),
        ("    import os as slot", ""),
        ("    del slot", ""),
        ("    slot = replacement", ""),
        ("    slot = alias = H11OwnedFdSlot()", ""),
    ),
    ids=(
        "augassign",
        "namedexpr",
        "for",
        "with",
        "except",
        "destructure",
        "parameter",
        "import",
        "delete",
        "reassign",
        "chained",
    ),
)
def test_c2e_scanner_one_assign_rejects_every_other_binder(
    extra: str,
    parameters: str,
) -> None:
    result = _scan_one_assign_case(extra, parameters=parameters)
    assert any(item.lexical_target == "slot.borrow" for item in result.unresolved)


def _production_scanner(source: str | None = None) -> H11ReachableCallScanner:
    return H11ReachableCallScanner(source or INSTALLER_SOURCE.read_text())


def _phase_cursor_source() -> str:
    return INSTALLER_SOURCE.read_text()


def test_c2e_binding_forms_constant_and_inventory_are_exact() -> None:
    assert C2E_BINDING_FORMS == frozenset(
        {
            "arguments", "Assign", "AnnAssign", "AugAssign", "NamedExpr",
            "For.target", "AsyncFor.target", "comprehension.target",
            "With.optional_vars", "AsyncWith.optional_vars", "ExceptHandler.name",
            "Import", "ImportFrom", "destructure", "Delete", "MatchAs.name",
            "MatchStar.name", "MatchMapping.rest", "FunctionDef.name",
            "FunctionDef.type_params", "AsyncFunctionDef.name",
            "AsyncFunctionDef.type_params", "ClassDef.name", "ClassDef.type_params",
            "TypeAlias.name", "TypeAlias.type_params", "Global", "Nonlocal",
        }
    )
    source = """
async def inventory(slot):
    slot: int
    async for slot in values:
        pass
    async with manager as slot:
        pass
    values = [item for slot in values]
    match value:
        case [slot]:
            pass
        case [*slot]:
            pass
        case {"key": item, **slot}:
            pass
    def slot():
        pass
    async def other[slot]():
        pass
    class third[slot]:
        pass
    type fourth[slot] = int
    global global_name
    nonlocal nonlocal_name
"""
    node = ast.parse(source).body[0]
    assert isinstance(node, ast.AsyncFunctionDef)
    inventory = _WholeFunctionBindings(
        _FunctionInfo(f"{M}.inventory", node, None)
    ).inventory
    assert inventory.counts["slot"] > 1
    assert {
        "arguments", "AnnAssign", "AsyncFor.target", "AsyncWith.optional_vars",
        "comprehension.target", "MatchAs.name", "MatchStar.name",
        "MatchMapping.rest", "FunctionDef.name", "AsyncFunctionDef.type_params",
        "ClassDef.type_params", "TypeAlias.type_params",
    } <= set(inventory.forms["slot"])
    assert inventory.forms["global_name"] == Counter({"Global": 1})
    assert inventory.forms["nonlocal_name"] == Counter({"Nonlocal": 1})


def test_c2e_exact_nominal_and_frozen_store_closure_accepts_only_70() -> None:
    scanner = _production_scanner()
    assert set(scanner.classes) >= _EXACT_NOMINAL_CLASSES
    assert all(scanner._prove_exact_nominal_class(name) for name in _EXACT_NOMINAL_CLASSES)
    assert sum(map(len, _EXPLICIT_FROZEN_FIELDS.values())) == 70
    assert all(scanner._prove_frozen_constructor(name) for name in _EXPLICIT_FROZEN_FIELDS)
    result = scanner.scan(ROOT_QNAME)
    stores = [call for call in result.calls if call.rule_id == "FROZEN_CONSTRUCTOR_STORE"]
    assert len(stores) == 70
    assert {call.canonical_target for call in stores} == {"builtins.object.__setattr__"}
    assert result.resolved_call_count + len(result.unresolved) == result.reachable_ast_call_count


@pytest.mark.parametrize("class_name", tuple(_EXPLICIT_FROZEN_FIELDS))
@pytest.mark.parametrize(
    "mutation",
    ("missing", "extra", "reordered", "duplicate", "dynamic-field", "wrong-value"),
)
def test_c2e_frozen_constructor_store_shape_fails_closed(
    class_name: str,
    mutation: str,
) -> None:
    tree = ast.parse(INSTALLER_SOURCE.read_text())
    class_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    constructor = next(
        node
        for node in class_node.body
        if isinstance(node, ast.FunctionDef) and node.name == "__init__"
    )
    indexes = [
        index
        for index, statement in enumerate(constructor.body)
        if H11ReachableCallScanner._object_setattr_call(statement) is not None
    ]
    assert indexes
    first_index = indexes[0]
    first_statement = constructor.body[first_index]
    first = H11ReachableCallScanner._object_setattr_call(first_statement)
    assert first is not None
    if mutation == "missing":
        del constructor.body[first_index]
    elif mutation == "extra":
        constructor.body.insert(
            first_index,
            ast.parse(ast.unparse(first_statement)).body[0],
        )
    elif mutation == "reordered":
        if len(indexes) == 1:
            constructor.body.insert(0, constructor.body.pop(first_index))
        else:
            constructor.body[indexes[0]], constructor.body[indexes[1]] = (
                constructor.body[indexes[1]], constructor.body[indexes[0]]
            )
    elif mutation == "duplicate":
        constructor.body.insert(
            first_index,
            ast.parse(ast.unparse(first_statement)).body[0],
        )
    elif mutation == "dynamic-field":
        first.args[1] = ast.Name(id="field_name", ctx=ast.Load())
    else:
        first.args[2] = ast.Name(id="foreign", ctx=ast.Load())
    ast.fix_missing_locations(tree)
    source = ast.unparse(tree)
    assert not _production_scanner(source)._prove_frozen_constructor(class_name)


@pytest.mark.parametrize(
    "replacement",
    (
        "object.__setattr__(self, '_flow', flow)\n        _fail('between stores')",
        "if True:\n            object.__setattr__(self, '_flow', flow)",
        "for _ in (0,):\n            object.__setattr__(self, '_flow', flow)",
        "try:\n            object.__setattr__(self, '_flow', flow)\n        finally:\n            pass",
        "setattr(self, '_flow', flow)",
    ),
    ids=("call-between", "conditional", "loop", "try", "builtin-setattr"),
)
def test_c2e_frozen_constructor_store_control_flow_fails_closed(replacement: str) -> None:
    source = INSTALLER_SOURCE.read_text().replace(
        "object.__setattr__(self, \"_flow\", flow)", replacement, 1
    )
    assert not _production_scanner(source)._prove_frozen_constructor("H11RootDirectoryView")


def test_c2e_generated_dataclass_normalization_and_adversaries() -> None:
    source = INSTALLER_SOURCE.read_text()
    marker = "@dataclass(frozen=True, slots=True)\nclass H11RootClosedPartition:"
    assert _production_scanner(source)._prove_exact_nominal_class("H11RootClosedPartition")
    explicit_true = source.replace(
        marker,
        "@dataclass(frozen=True, slots=True, init=True)\nclass H11RootClosedPartition:",
        1,
    )
    assert _production_scanner(explicit_true)._prove_exact_nominal_class("H11RootClosedPartition")
    mutations = (
        "@dataclass(frozen=True, slots=True, init=False)\nclass H11RootClosedPartition:",
        "@dataclass(frozen=True, slots=True, init=FLAG)\nclass H11RootClosedPartition:",
        "@dataclass(frozen=True, slots=True, unsafe_hash=True)\nclass H11RootClosedPartition:",
        "@dc(frozen=True, slots=True)\nclass H11RootClosedPartition:",
        "@dataclass(frozen=True, slots=True)\nclass H11RootClosedPartition(object):",
        "@dataclass(frozen=True, slots=True)\nclass H11RootClosedPartition(metaclass=type):",
        "@dataclass(frozen=True, slots=True)\nclass H11RootClosedPartition[T]:",
    )
    for mutated_marker in mutations:
        assert not _production_scanner(source.replace(marker, mutated_marker, 1))._prove_exact_nominal_class(
            "H11RootClosedPartition"
        )
    post_init = source.replace(
        "    receipt_future_absence: tuple[H11RootRolePath, ...]\n\n\n@dataclass",
        "    receipt_future_absence: tuple[H11RootRolePath, ...]\n\n"
        "    def __post_init__(self) -> None:\n        return None\n\n\n@dataclass",
        1,
    )
    assert not _production_scanner(post_init)._prove_exact_nominal_class("H11RootClosedPartition")


def test_c2e_closed_factories_have_exact_result_identity() -> None:
    scanner = _production_scanner()
    assert set(_FACTORY_RESULTS) == set(_FACTORY_SIGNATURES)
    assert all(scanner._prove_factory(qname) for qname in _FACTORY_RESULTS)

    source = INSTALLER_SOURCE.read_text()
    mutations = (
        source.replace("return H11RootDirectoryReference(", "return cls(", 1),
        source.replace("    def decode(\n        cls,", "    async def decode(\n        cls,", 1),
        source.replace("        label: str,", "        label: object,", 1),
        source.replace(
            "        return H11RootDirectoryReference(",
            "        if False:\n            return None\n        return H11RootDirectoryReference(",
            1,
        ),
        source.replace("    @classmethod\n    def decode(", "    @staticmethod\n    def decode(", 1),
    )
    qname = f"{M}.H11RootDirectoryReference.decode"
    assert all(not _production_scanner(mutated)._prove_factory(qname) for mutated in mutations)


def test_c2e_phase_cursor_accepts_only_fixed_first_assignment_and_gate() -> None:
    accepted = _production_scanner(_phase_cursor_source())
    assert accepted._prove_phase_graph()
    assert all(
        accepted._prove_phase_cursor(accepted.functions[qname])
        for qname in _PHASE_CURSORS
    )
    current = _production_scanner()
    assert all(
        current._prove_phase_cursor(current.functions[qname])
        for qname in _PHASE_CURSORS
    )
    source = _phase_cursor_source()
    adversaries = (
        source.replace("phase_data = self._phase_data", "cursor = self._phase_data", 1),
        source.replace("type(phase_data) is not H11RootAuthorityPhaseData", "type(phase_data) is not H11RootReadyPhaseData", 1),
        source.replace(
            "self._state is not H11RootAuthorizationState.AUTHORITIES_RETAINED\n"
            "            or type(phase_data) is not H11RootAuthorityPhaseData",
            "type(phase_data) is not H11RootAuthorityPhaseData\n"
            "            or self._state is not H11RootAuthorizationState.AUTHORITIES_RETAINED",
            1,
        ),
    )
    qname = f"{M}.H11RootAuthorizationFlow._consume_ready_commit"
    assert all(
        not _production_scanner(mutated)._prove_phase_cursor(
            _production_scanner(mutated).functions[qname]
        )
        for mutated in adversaries
    )


def test_c2e_optional_parent_requires_exact_pairs_and_else_dominance() -> None:
    scanner = _production_scanner()
    assert all(scanner._prove_parent_pairs(name) for name in _PARENT_SLOT_PAIRS)
    result = scanner.scan(f"{M}.H11RootDirectoryView.revalidate")
    optional = [call for call in result.calls if call.rule_id == "FROZEN_OPTIONAL_PARENT"]
    assert len(optional) == 1
    assert optional[0].lexical_target == "self._parent_slot.borrow"

    wrong_branch = INSTALLER_SOURCE.read_text().replace(
        "if self._parent_slot is None:\n                current = Path.lstat(self.reference.path)\n            else:",
        "if dynamic_parent_test:\n                current = Path.lstat(self.reference.path)\n            else:",
        1,
    )
    rejected = _production_scanner(wrong_branch).scan(
        f"{M}.H11RootDirectoryView.revalidate"
    )
    assert any(
        failure.lexical_target == "self._parent_slot.borrow"
        for failure in rejected.unresolved
    )
    foreign_pair = INSTALLER_SOURCE.read_text().replace(
        "parent_slot=self._slots[15],\n            reference=authority_reference,",
        "parent_slot=None,\n            reference=authority_reference,",
        1,
    )
    assert not _production_scanner(foreign_pair)._prove_parent_pairs("H11RootDirectoryView")


@pytest.mark.parametrize(
    ("classes", "expected_count"),
    (
        (CANONICAL_INDIRECT_CLASSES, 32),
        (EXPANDED_INDIRECT_CLASSES, 34),
        (REORDERED_INDIRECT_CLASSES, 32),
    ),
    ids=("canonical", "expanded", "reordered"),
)
def test_c2e_fixture_owned_class_literals_are_complete(
    classes: tuple[FixtureClass, ...], expected_count: int
) -> None:
    assert len(classes) == expected_count
    assert len({equivalence_class for equivalence_class, _role, _ordinal in classes}) == expected_count
    assert tuple(item for item in classes if item[2] is not None) == (
        ("install/target/run-fragment", "run-fragment", 0),
        ("install/target/close-fragment", "close-fragment", 1),
        ("install/target/gc-fragment", "gc-fragment", 2),
    )


def test_c2e_expanded_and_reordered_fixture_literals_are_independent() -> None:
    assert EXPANDED_INDIRECT_CLASSES != CANONICAL_INDIRECT_CLASSES
    assert EXPANDED_INDIRECT_CLASSES[17] == EXPANDED_CLASS_LITERALS[0]
    assert EXPANDED_INDIRECT_CLASSES[-4] == EXPANDED_CLASS_LITERALS[1]
    assert tuple(item for item in EXPANDED_INDIRECT_CLASSES if item not in CANONICAL_INDIRECT_CLASSES) == EXPANDED_CLASS_LITERALS
    assert REORDERED_RAW_SEAL_ROLES[:-1] == tuple(
        reversed(tuple(item[1] for item in CANONICAL_INDIRECT_CLASSES[17:29]))
    )
    assert REORDERED_RAW_SEAL_ROLES[-1] == "preflight-manifest"
    assert REORDERED_INDIRECT_CLASSES == CANONICAL_INDIRECT_CLASSES


def test_c2e_expanded_fixture_builds_real_canonical_assets(tmp_path: Path) -> None:
    inventory_rows, seal_rows = _build_expanded_asset_rows(tmp_path)
    assert tuple(row["role"] for row in inventory_rows) == ("aaa-expanded-asset", "zzz-expanded-asset")
    assert tuple(row["tag"] for row in inventory_rows) == ("asset", "asset")
    assert tuple(row["kind"] for row in inventory_rows) == ("static-input", "static-input")
    for (role, raw, leaf), inventory_row, seal_row in zip(
        EXPANDED_ASSET_LITERALS, inventory_rows, seal_rows, strict=True
    ):
        path = tmp_path / "sealed" / leaf
        assert path.read_bytes() == raw
        assert stat.S_IMODE(path.lstat().st_mode) == 0o444
        assert inventory_row["path"] == str(path)
        assert inventory_row["reference"] == {key: value for key, value in seal_row.items() if key != "role"}
        assert seal_row["role"] == role
        if os.geteuid() == 0:
            assert (path.lstat().st_uid, path.lstat().st_gid) == (0, 0)


@pytest.mark.parametrize(
    ("classes", "expected_enters"),
    (
        (CANONICAL_INDIRECT_CLASSES, 245),
        (EXPANDED_INDIRECT_CLASSES, 247),
        (REORDERED_INDIRECT_CLASSES, 245),
    ),
    ids=("canonical", "expanded", "reordered"),
)
def test_c2e_schedule_expands_every_boundary_in_exact_order(
    classes: tuple[FixtureClass, ...], expected_enters: int
) -> None:
    trace = build_c2e_golden_trace(classes)
    entered = _entered_executions(trace)
    assert len(entered) == expected_enters
    assert tuple(item.execution_ordinal for item in entered) == tuple(range(expected_enters))
    assert len(trace) == expected_enters * 2
    assert _completed_observe_classes(trace) == classes
    assert Counter(item.site_identity.boundary_kind for item in entered) == Counter(
        {
            "open": 18,
            "fstat": 63,
            "prove": 69,
            "decode": 18,
            "revalidate": 45,
            "observe": len(classes),
        }
    )

    stack: list[BoundaryExecution] = []
    for event in trace:
        if event.event_kind == "enter":
            stack.append(event.execution)
        else:
            assert event.event_kind == "complete"
            assert stack.pop() == event.execution
    assert stack == []


def test_c2e_cross_fixture_fault_projection_only_adds_two_expanded_observes() -> None:
    canonical = _entered_executions(build_c2e_golden_trace(CANONICAL_INDIRECT_CLASSES))
    expanded = _entered_executions(build_c2e_golden_trace(EXPANDED_INDIRECT_CLASSES))
    reordered = _entered_executions(build_c2e_golden_trace(REORDERED_INDIRECT_CLASSES))
    canonical_keys = {_cross_fixture_site_projection(item.site_identity) for item in canonical}
    expanded_keys = {_cross_fixture_site_projection(item.site_identity) for item in expanded}
    reordered_keys = {_cross_fixture_site_projection(item.site_identity) for item in reordered}
    assert reordered_keys == canonical_keys
    assert expanded_keys - canonical_keys == {
        _cross_fixture_site_projection(item.site_identity)
        for item in expanded
        if item.site_identity.equivalence_class_or_none
        in {"seal/file/aaa-expanded-asset", "seal/file/zzz-expanded-asset"}
    }


def test_c2e_supplemental_sensitive_fault_owner_is_total_and_unique() -> None:
    keys = tuple(key for key, _owner in SUPPLEMENTAL_SENSITIVE_FAULT_OWNER)
    assert len(keys) == len(set(keys)) == 32
    assert Counter(owner for _key, owner in SUPPLEMENTAL_SENSITIVE_FAULT_OWNER) == Counter(
        {"base-focused-syscall": 25, "boundary": 6, "close-primitive": 1}
    )
    process_sites = tuple(
        key
        for key, owner in SUPPLEMENTAL_SENSITIVE_FAULT_OWNER
        if key.canonical_target in {"os.geteuid", "os.getegid"}
        and owner == "base-focused-syscall"
    )
    assert len(process_sites) == 2


def test_c2e_cleanup_composition_is_derived_without_representative_selection() -> None:
    fixtures = (
        (0, CANONICAL_INDIRECT_CLASSES),
        (1, EXPANDED_INDIRECT_CLASSES),
        (2, REORDERED_INDIRECT_CLASSES),
    )
    grouped: dict[tuple[Any, ...], list[tuple[int, PrimaryState]]] = {}
    for fixture_rank, classes in fixtures:
        for primary in primary_states_for_trace(build_c2e_golden_trace(classes)):
            grouped.setdefault(primary.cleanup_composition_key, []).append((fixture_rank, primary))
    assert grouped
    selected = {
        key: min(values, key=lambda item: (item[0], item[1].execution.execution_ordinal))
        for key, values in grouped.items()
    }
    assert len(selected) == len(grouped)
    assert all(item in grouped[key] for key, item in selected.items())
    assert any(not any(primary.bound_slot_bitmap) for _rank, primary in selected.values())
    for _rank, primary in selected.values():
        secondary = expected_secondary_indices(primary.bound_slot_bitmap)
        bound = tuple(index for index, is_bound in enumerate(primary.bound_slot_bitmap) if is_bound)
        if not bound:
            assert secondary == ()
        else:
            assert secondary == tuple(dict.fromkeys((bound[0], bound[(len(bound) - 1) // 2], bound[-1])))


def test_c2e_close_matrix_exhausts_all_23_physical_slots() -> None:
    assert SWEEP_ORDER == tuple(range(23))
    close_failure_indices = tuple(index for index in SWEEP_ORDER)
    assert close_failure_indices == tuple(range(23))
    all_bound = tuple(True for _index in SWEEP_ORDER)
    assert expected_secondary_indices(all_bound) == (0, 11, 22)
    single_bound = tuple(index == 7 for index in SWEEP_ORDER)
    assert expected_secondary_indices(single_bound) == (7,)
    none_bound = tuple(False for _index in SWEEP_ORDER)
    assert expected_secondary_indices(none_bound) == ()


def _c2e_actual_close_flow(
    production: Any,
    *,
    state: Any,
    boundary: Any,
    bind_all_slots: bool,
) -> tuple[Any, tuple[int, ...]]:
    flow = production.H11RootAuthorizationFlow(
        Path("/c2e-close-matrix-unused"),
        require_root=False,
    )
    # The close primitive is isolated with a legal state/boundary pair; no phase
    # method is invoked and close never observes phase data.
    flow._state = state
    flow._commit_boundary = boundary
    descriptors: list[int] = []
    if bind_all_slots:
        for slot in flow._slots:
            descriptor = os.open(os.devnull, os.O_RDONLY | os.O_CLOEXEC)
            slot._bind(descriptor)
            descriptors.append(descriptor)
    assert len(flow._slots) == len(SWEEP_ORDER)
    assert len(descriptors) in (0, len(SWEEP_ORDER))
    assert len(descriptors) == len(set(descriptors))
    return flow, tuple(descriptors)


def _c2e_instrument_actual_close(
    monkeypatch: pytest.MonkeyPatch,
    production: Any,
    flow: Any,
    descriptors: tuple[int, ...],
    failure_indices: tuple[int, ...],
    failure_objects: dict[int, OSError] | None = None,
) -> tuple[
    list[tuple[int, Any, BaseException | None]],
    list[int],
    dict[int, OSError],
    Any,
]:
    original_close_slot_once = production.H11RootAuthorizationFlow._close_slot_once
    real_close = os.close
    descriptor_indices = {
        descriptor: index for index, descriptor in enumerate(descriptors)
    }
    visits: list[tuple[int, Any, BaseException | None]] = []
    close_counts = [0 for _index in SWEEP_ORDER]
    failures = (
        {
            index: OSError(f"C2E close matrix failure at slot {index}")
            for index in failure_indices
        }
        if failure_objects is None
        else dict(failure_objects)
    )
    assert tuple(failures) == failure_indices

    def record_close_slot_once(
        self: Any,
        slot: Any,
        *,
        active_error: BaseException | None = None,
    ) -> BaseException | None:
        assert self is flow
        index = next(
            index
            for index, candidate in enumerate(self._slots)
            if candidate is slot
        )
        visits.append((index, self.state, active_error))
        return original_close_slot_once(
            self,
            slot,
            active_error=active_error,
        )

    def faulting_close(descriptor: int) -> None:
        index = descriptor_indices[descriptor]
        close_counts[index] += 1
        real_close(descriptor)
        if index in failures:
            raise failures[index]

    monkeypatch.setattr(
        production.H11RootAuthorizationFlow,
        "_close_slot_once",
        record_close_slot_once,
    )
    monkeypatch.setattr(os, "close", faulting_close)
    return visits, close_counts, failures, real_close


def _c2e_cleanup_actual_close_flow(flow: Any, real_close: Any) -> None:
    for slot in flow._slots:
        descriptor = slot.detach()
        if descriptor >= 0:
            try:
                real_close(descriptor)
            except OSError:
                pass


def test_c2e_actual_flow_close_new_empty_sweep_and_repeat_noop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    production = _load_installer()
    flow, _descriptors = _c2e_actual_close_flow(
        production,
        state=production.H11RootAuthorizationState.NEW,
        boundary=production.H11RootCommitBoundary.PREWRITE,
        bind_all_slots=False,
    )
    original_close_slot_once = production.H11RootAuthorizationFlow._close_slot_once
    visits: list[tuple[int, BaseException | None]] = []

    def record_close_slot_once(
        self: Any,
        slot: Any,
        *,
        active_error: BaseException | None = None,
    ) -> BaseException | None:
        index = next(
            index
            for index, candidate in enumerate(self._slots)
            if candidate is slot
        )
        visits.append((index, active_error))
        return original_close_slot_once(
            self,
            slot,
            active_error=active_error,
        )

    monkeypatch.setattr(
        production.H11RootAuthorizationFlow,
        "_close_slot_once",
        record_close_slot_once,
    )
    flow.close()
    assert flow.state is production.H11RootAuthorizationState.CLOSED
    assert tuple(index for index, _active_error in visits) == SWEEP_ORDER
    assert all(active_error is None for _index, active_error in visits)

    visits.clear()
    flow.close()
    assert visits == []
    assert flow.state is production.H11RootAuthorizationState.CLOSED


@pytest.mark.parametrize(
    ("state_name", "boundary_name", "bind_all_slots"),
    (
        ("COMPLETE", "POSTWRITE", True),
        ("FAILED_PREWRITE", "PREWRITE", False),
        ("FAILED_WRITE_AMBIGUOUS", "WRITE_IN_FLIGHT", False),
        ("FAILED_POSTWRITE", "POSTWRITE", False),
        ("CLOSED", "PREWRITE", False),
    ),
)
def test_c2e_actual_flow_close_terminal_state_is_zero_slot_noop(
    monkeypatch: pytest.MonkeyPatch,
    state_name: str,
    boundary_name: str,
    bind_all_slots: bool,
) -> None:
    production = _load_installer()
    state = getattr(production.H11RootAuthorizationState, state_name)
    flow, descriptors = _c2e_actual_close_flow(
        production,
        state=state,
        boundary=getattr(production.H11RootCommitBoundary, boundary_name),
        bind_all_slots=bind_all_slots,
    )
    real_close = os.close
    visits: list[Any] = []
    sweep_visits: list[Any] = []

    def record_unexpected_slot_access(*args: Any, **kwargs: Any) -> None:
        visits.append((args, kwargs))

    def record_unexpected_sweep(*args: Any, **kwargs: Any) -> None:
        sweep_visits.append((args, kwargs))

    monkeypatch.setattr(
        production.H11RootAuthorizationFlow,
        "_close_slot_once",
        record_unexpected_slot_access,
    )
    monkeypatch.setattr(
        production.H11RootAuthorizationFlow,
        "_sweep_slots",
        record_unexpected_sweep,
    )
    try:
        flow.close()
        flow.close()
        assert visits == []
        assert sweep_visits == []
        assert flow.state is state
        if bind_all_slots:
            assert tuple(slot._descriptor for slot in flow._slots) == descriptors
            assert len(tuple(os.fstat(descriptor) for descriptor in descriptors)) == len(
                SWEEP_ORDER
            )
    finally:
        _c2e_cleanup_actual_close_flow(flow, real_close)


@pytest.mark.parametrize(
    "failure_indices",
    (
        (),
        *((index,) for index in SWEEP_ORDER),
        (0, 11, 22),
    ),
    ids=(
        "success",
        *(f"slot-{index}" for index in SWEEP_ORDER),
        "multiple",
    ),
)
def test_c2e_actual_flow_close_prewrite_sweeps_all_slots_once(
    monkeypatch: pytest.MonkeyPatch,
    failure_indices: tuple[int, ...],
) -> None:
    production = _load_installer()
    initial_state = production.H11RootAuthorizationState.AUTHORITIES_RETAINED
    flow, descriptors = _c2e_actual_close_flow(
        production,
        state=initial_state,
        boundary=production.H11RootCommitBoundary.PREWRITE,
        bind_all_slots=True,
    )
    visits, close_counts, failures, real_close = _c2e_instrument_actual_close(
        monkeypatch,
        production,
        flow,
        descriptors,
        failure_indices,
    )
    try:
        if failure_indices:
            with pytest.raises(OSError) as caught:
                flow.close()
            assert caught.value is failures[failure_indices[0]]
            assert flow.state is production.H11RootAuthorizationState.FAILED_PREWRITE
        else:
            flow.close()
            assert flow.state is production.H11RootAuthorizationState.CLOSED

        assert tuple(index for index, _state, _active_error in visits) == SWEEP_ORDER
        assert all(state is initial_state for _index, state, _error in visits)
        assert all(error is None for _index, _state, error in visits)
        assert close_counts == [1 for _index in SWEEP_ORDER]
        assert all(slot._descriptor == -1 for slot in flow._slots)
        assert all(
            getattr(close_error, "__notes__", []) == []
            for close_error in failures.values()
        )

        visits.clear()
        before_repeat = tuple(close_counts)
        flow.close()
        assert visits == []
        assert tuple(close_counts) == before_repeat
    finally:
        _c2e_cleanup_actual_close_flow(flow, real_close)


@pytest.mark.parametrize(
    "failure_index",
    SWEEP_ORDER,
    ids=tuple(f"slot-{index}" for index in SWEEP_ORDER),
)
def test_c2e_actual_sweep_fixed_primary_exhausts_every_failure_index(
    monkeypatch: pytest.MonkeyPatch,
    failure_index: int,
) -> None:
    production = _load_installer()
    flow, descriptors = _c2e_actual_close_flow(
        production,
        state=production.H11RootAuthorizationState.AUTHORITIES_RETAINED,
        boundary=production.H11RootCommitBoundary.PREWRITE,
        bind_all_slots=True,
    )
    visits, close_counts, failures, real_close = _c2e_instrument_actual_close(
        monkeypatch,
        production,
        flow,
        descriptors,
        (failure_index,),
    )
    primary = production.InstallerError("H11 C2e fixed teardown primary")
    try:
        with pytest.raises(production.InstallerError) as caught:
            flow._fail(primary)
        assert caught.value is primary
        assert str(primary) == "H11 C2e fixed teardown primary"
        assert flow.state is production.H11RootAuthorizationState.FAILED_PREWRITE
        assert tuple(index for index, _state, _error in visits) == SWEEP_ORDER
        assert all(
            state is production.H11RootAuthorizationState.FAILED_PREWRITE
            for _index, state, _error in visits
        )
        assert tuple(error is primary for _index, _state, error in visits) == tuple(
            index <= failure_index for index in SWEEP_ORDER
        )
        assert getattr(primary, "__notes__", []) == [
            "H11 ownership teardown secondary close failure"
        ]
        assert getattr(failures[failure_index], "__notes__", []) == []
        assert close_counts == [1 for _index in SWEEP_ORDER]
        assert all(slot._descriptor == -1 for slot in flow._slots)

        visits.clear()
        before_repeat = tuple(close_counts)
        flow.close()
        assert visits == []
        assert tuple(close_counts) == before_repeat
    finally:
        _c2e_cleanup_actual_close_flow(flow, real_close)


@pytest.mark.parametrize(
    (
        "state_name",
        "boundary_name",
        "terminal_state_name",
        "primary_message",
    ),
    (
        (
            "PERMIT_WRITER_OPEN",
            "WRITE_IN_FLIGHT",
            "FAILED_WRITE_AMBIGUOUS",
            "H11 authorization flow closed while permit write outcome is ambiguous",
        ),
        (
            "PERMIT_FRAME_WRITTEN",
            "POSTWRITE",
            "FAILED_POSTWRITE",
            "H11 authorization flow closed after permit frame write",
        ),
    ),
)
@pytest.mark.parametrize(
    "failure_indices",
    ((), (0,), (11,), (22,), (0, 11, 22)),
    ids=("no-secondary", "first", "middle", "last", "multiple"),
)
def test_c2e_actual_flow_close_commit_boundary_primary_and_secondary_matrix(
    monkeypatch: pytest.MonkeyPatch,
    state_name: str,
    boundary_name: str,
    terminal_state_name: str,
    primary_message: str,
    failure_indices: tuple[int, ...],
) -> None:
    production = _load_installer()
    boundary = getattr(production.H11RootCommitBoundary, boundary_name)
    terminal_state = getattr(production.H11RootAuthorizationState, terminal_state_name)
    flow, descriptors = _c2e_actual_close_flow(
        production,
        state=getattr(production.H11RootAuthorizationState, state_name),
        boundary=boundary,
        bind_all_slots=True,
    )
    visits, close_counts, failures, real_close = _c2e_instrument_actual_close(
        monkeypatch,
        production,
        flow,
        descriptors,
        failure_indices,
    )
    try:
        with pytest.raises(production.InstallerError) as caught:
            flow.close()
        primary = caught.value
        assert type(primary) is production.InstallerError
        assert str(primary) == primary_message
        assert flow.state is terminal_state
        assert flow._commit_boundary is boundary

        assert tuple(index for index, _state, _active_error in visits) == SWEEP_ORDER
        assert all(state is terminal_state for _index, state, _error in visits)
        if failure_indices:
            first_failure = failure_indices[0]
            assert tuple(error is primary for _index, _state, error in visits) == tuple(
                index <= first_failure for index in SWEEP_ORDER
            )
        else:
            assert all(error is primary for _index, _state, error in visits)
        assert close_counts == [1 for _index in SWEEP_ORDER]
        assert all(slot._descriptor == -1 for slot in flow._slots)
        expected_notes = (
            ["H11 ownership teardown secondary close failure"]
            if failure_indices
            else []
        )
        assert getattr(primary, "__notes__", []) == expected_notes
        assert all(
            getattr(close_error, "__notes__", []) == []
            for close_error in failures.values()
        )

        visits.clear()
        before_repeat = tuple(close_counts)
        flow.close()
        assert visits == []
        assert tuple(close_counts) == before_repeat
    finally:
        _c2e_cleanup_actual_close_flow(flow, real_close)


def test_c2e_actual_sweep_uses_base_note_channel_against_hostile_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    production = _load_installer()
    flow, descriptors = _c2e_actual_close_flow(
        production,
        state=production.H11RootAuthorizationState.AUTHORITIES_RETAINED,
        boundary=production.H11RootCommitBoundary.PREWRITE,
        bind_all_slots=True,
    )
    failure_indices = (0, 11, 22)
    visits, close_counts, failures, real_close = _c2e_instrument_actual_close(
        monkeypatch,
        production,
        flow,
        descriptors,
        failure_indices,
    )
    hostile_override_calls: list[str] = []

    class HostileNotePrimary(BaseException):
        def add_note(self, note: str) -> None:
            hostile_override_calls.append(note)
            raise AssertionError("hostile instance add_note override was invoked")

    primary = HostileNotePrimary("C2E hostile note-channel primary")
    try:
        with pytest.raises(HostileNotePrimary) as caught:
            flow._fail(primary)
        assert caught.value is primary
        assert flow.state is production.H11RootAuthorizationState.FAILED_PREWRITE
        assert tuple(index for index, _state, _error in visits) == SWEEP_ORDER
        assert tuple(error is primary for _index, _state, error in visits) == (
            True,
            *(False for _index in SWEEP_ORDER[1:]),
        )
        assert close_counts == [1 for _index in SWEEP_ORDER]
        assert all(slot._descriptor == -1 for slot in flow._slots)
        assert hostile_override_calls == []
        assert getattr(primary, "__notes__", []) == [
            "H11 ownership teardown secondary close failure"
        ]
        assert all(
            getattr(close_error, "__notes__", []) == []
            for close_error in failures.values()
        )
    finally:
        _c2e_cleanup_actual_close_flow(flow, real_close)


def test_c2e_actual_sweep_survives_hostile_secondary_and_poisoned_notes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    production = _load_installer()
    flow, descriptors = _c2e_actual_close_flow(
        production,
        state=production.H11RootAuthorizationState.AUTHORITIES_RETAINED,
        boundary=production.H11RootCommitBoundary.PREWRITE,
        bind_all_slots=True,
    )
    hostile_channel_calls: list[str] = []

    class HostileSecondary(OSError):
        def __str__(self) -> str:
            hostile_channel_calls.append("__str__")
            raise AssertionError("secondary __str__ was invoked")

        def __repr__(self) -> str:
            hostile_channel_calls.append("__repr__")
            raise AssertionError("secondary __repr__ was invoked")

    failure_indices = (0, 11, 22)
    failure_objects = {
        index: HostileSecondary(index) for index in failure_indices
    }
    visits, close_counts, failures, real_close = _c2e_instrument_actual_close(
        monkeypatch,
        production,
        flow,
        descriptors,
        failure_indices,
        failure_objects,
    )
    primary = production.InstallerError("H11 C2e poisoned note-channel primary")
    poisoned_notes = ("C2E poisoned notes",)
    primary.__notes__ = poisoned_notes
    try:
        with pytest.raises(production.InstallerError) as caught:
            flow._fail(primary)
        assert caught.value is primary
        assert flow.state is production.H11RootAuthorizationState.FAILED_PREWRITE
        assert tuple(index for index, _state, _error in visits) == SWEEP_ORDER
        assert tuple(error is primary for _index, _state, error in visits) == (
            True,
            *(False for _index in SWEEP_ORDER[1:]),
        )
        assert close_counts == [1 for _index in SWEEP_ORDER]
        assert all(slot._descriptor == -1 for slot in flow._slots)
        assert hostile_channel_calls == []
        assert primary.__notes__ is poisoned_notes
        assert tuple(failures) == failure_indices
    finally:
        _c2e_cleanup_actual_close_flow(flow, real_close)


def test_c2e_actual_partial_bitmap_excludes_early_detached_holes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    production = _load_installer()
    flow, descriptors = _c2e_actual_close_flow(
        production,
        state=production.H11RootAuthorizationState.AUTHORITIES_RETAINED,
        boundary=production.H11RootCommitBoundary.PREWRITE,
        bind_all_slots=True,
    )
    bound_indices = (2, 4, 7, 11, 16, 20, 22)
    bound_bitmap = tuple(index in bound_indices for index in SWEEP_ORDER)
    failure_indices = expected_secondary_indices(bound_bitmap)
    assert failure_indices == (2, 11, 22)
    real_close = os.close
    hole_indices = tuple(index for index in SWEEP_ORDER if index not in bound_indices)
    assert 0 in hole_indices
    for index in hole_indices:
        early_descriptor = flow._slots[index].detach()
        assert early_descriptor == descriptors[index]
        real_close(early_descriptor)

    visits, close_counts, failures, instrumented_close = (
        _c2e_instrument_actual_close(
            monkeypatch,
            production,
            flow,
            descriptors,
            failure_indices,
        )
    )
    primary = production.InstallerError("H11 C2e fixed teardown primary")
    try:
        with pytest.raises(production.InstallerError) as caught:
            flow._fail(primary)
        assert caught.value is primary
        assert tuple(index for index, _state, _error in visits) == SWEEP_ORDER
        assert tuple(close_counts) == tuple(
            1 if index in bound_indices else 0 for index in SWEEP_ORDER
        )
        assert close_counts[0] == 0
        assert all(flow._slots[index]._descriptor == -1 for index in SWEEP_ORDER)
        assert tuple(failures) == failure_indices
        assert all(
            getattr(close_error, "__notes__", []) == []
            for close_error in failures.values()
        )
        assert getattr(primary, "__notes__", []) == [
            "H11 ownership teardown secondary close failure"
        ]
    finally:
        _c2e_cleanup_actual_close_flow(flow, instrumented_close)


def test_c2e_domain_single_delta_matrix_is_closed_and_nonduplicated() -> None:
    assert tuple(DOMAIN_NEGATIVE_AXES) == (
        "_prove_h11_direct_authority_bindings",
        "_build_h11_tree_indirect_specs",
        "_build_h11_seal_indirect_specs",
        "_prove_h11_preflight_snapshot_bindings",
        "_build_h11_install_target_specs",
    )
    assert all(axes and len(axes) == len(set(axes)) for axes in DOMAIN_NEGATIVE_AXES.values())
    registered = {
        f"{helper}:{axis}"
        for helper, axes in DOMAIN_NEGATIVE_AXES.items()
        for axis in axes
    }
    assert len(registered) == sum(len(axes) for axes in DOMAIN_NEGATIVE_AXES.values()) == 75


@pytest.mark.parametrize(
    ("variant", "expected_classes"),
    (
        ("canonical", CANONICAL_INDIRECT_CLASSES),
        ("expanded", EXPANDED_INDIRECT_CLASSES),
        ("reordered", REORDERED_INDIRECT_CLASSES),
    ),
)
def test_c2e_producer_valid_fixture_builds_exact_inventory_and_owner_identity(
    tmp_path: Path,
    variant: Literal["canonical", "expanded", "reordered"],
    expected_classes: tuple[FixtureClass, ...],
) -> None:
    fixture = _build_c2e_inventory_fixture(tmp_path, variant=variant)
    fixture_uid, fixture_gid, validated_fifos, indirect_specs = (
        fixture.production._build_h11_indirect_authority_inventory(**fixture.arguments)
    )
    assert (fixture_uid, fixture_gid) == (os.geteuid(), os.getegid())
    assert tuple(
        (spec.equivalence_class, spec.semantic_role, spec.install_ordinal)
        for spec in indirect_specs
    ) == expected_classes
    assert len(validated_fifos) == 8
    ordinary = tuple(
        row
        for row in validated_fifos
        if row.role not in {"h11-ready-commit", "h11-permit-commit"}
    )
    assert len(ordinary) == 6
    assert all(row.accepted_owners == ((fixture_uid, fixture_gid),) for row in ordinary)
    for role, reference_name in (
        ("h11-ready-commit", "ready_commit_fifo_reference"),
        ("h11-permit-commit", "permit_commit_fifo_reference"),
    ):
        row = next(item for item in validated_fifos if item.role == role)
        reference = fixture.arguments[reference_name]
        spec = next(item for item in indirect_specs if item.semantic_role == role)
        assert row.accepted_owners is reference.accepted_owners
        assert spec.accepted_owners is reference.accepted_owners


def test_c2e_expanded_full_producer_freezes_inventory_rows_and_asset_count(tmp_path: Path) -> None:
    fixture = _build_c2e_inventory_fixture(tmp_path, variant="expanded")
    seal_roles = tuple(item["role"] for item in fixture.documents["seal_receipt"]["files"])
    assert {"aaa-expanded-asset", "zzz-expanded-asset"}.issubset(seal_roles)
    assert fixture.documents["preflight_receipt"]["asset_count"] == "14"
    inventory = Path(fixture.documents["preflight_receipt"]["inventory_manifest"]["path"])
    asset_rows = tuple(
        line.split("\t")
        for line in inventory.read_text(encoding="ascii").splitlines()
        if line.startswith("asset\t")
    )
    expanded = tuple(row for row in asset_rows if row[1] in {"aaa-expanded-asset", "zzz-expanded-asset"})
    assert tuple((row[0], row[1], row[2]) for row in expanded) == (
        ("asset", "aaa-expanded-asset", "static-input"),
        ("asset", "zzz-expanded-asset", "static-input"),
    )


def test_c2e_reordered_full_producer_is_nonidentity_but_consumer_expected_is_canonical(
    tmp_path: Path,
) -> None:
    fixture = _build_c2e_inventory_fixture(tmp_path, variant="reordered")
    raw_roles = tuple(item["role"] for item in fixture.documents["seal_receipt"]["files"])
    assert raw_roles == REORDERED_RAW_SEAL_ROLES
    assert raw_roles != tuple(reversed(raw_roles))
    assert REORDERED_INDIRECT_CLASSES == CANONICAL_INDIRECT_CLASSES


@pytest.mark.parametrize(
    ("document", "helper_name"),
    (
        ("authorization_manifest", "_prove_h11_direct_authority_bindings"),
        ("tree_receipt", "_build_h11_tree_indirect_specs"),
        ("seal_receipt", "_build_h11_seal_indirect_specs"),
        ("preflight_receipt", "_prove_h11_preflight_snapshot_bindings"),
        ("install_receipt", "_build_h11_install_target_specs"),
    ),
    ids=("direct", "tree", "seal", "preflight", "install"),
)
def test_c2e_each_domain_owns_an_independent_schema_delta(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    document: str,
    helper_name: str,
) -> None:
    fixture = _build_c2e_inventory_fixture(tmp_path)
    original = getattr(fixture.production, helper_name)
    calls: list[str] = []

    def recording_helper(**kwargs: Any) -> Any:
        calls.append(helper_name)
        return original(**kwargs)

    monkeypatch.setattr(fixture.production, helper_name, recording_helper)
    arguments = fixture.with_document_delta(document, "schema", "scion.invalid.single_delta.v1")
    with pytest.raises(fixture.production.InstallerError):
        fixture.production._build_h11_indirect_authority_inventory(**arguments)
    assert calls == [helper_name]


def test_c2e_canonical_codec_accepts_only_frozen_canonical_objects() -> None:
    production = _load_installer()
    assert hasattr(production, "_decode_h11_canonical_frozen_object"), (
        "C2e production decoder is not implemented"
    )
    decoder = production._decode_h11_canonical_frozen_object
    value = {"a": [1, True, None, {"z": "text"}], "b": "value"}
    raw = _canonical_json(value)
    decoded = decoder(raw, label="C2e codec positive")
    assert decoded == _frozen_json(value)
    assert not _contains_mutable_json(decoded)

    invalid = (
        b'{"a":1,"a":1}\n',
        b'{"a":NaN}\n',
        b'{"a":Infinity}\n',
        b'{"a":1.0}\n',
        b'[]\n',
        b'{ "a":1}\n',
        b'{"b":1,"a":2}\n',
        '{"a":"é"}\n'.encode(),
        b'{"a":"\\u00E9"}\n',
        b'{"a":1}\ntrailing',
    )
    for index, payload in enumerate(invalid):
        with pytest.raises(production.InstallerError):
            decoder(payload, label=f"C2e codec negative {index}")


def test_c2e_scalar_helpers_reject_mutable_bool_and_noncanonical_values() -> None:
    production = _load_installer()
    required = tuple(name.removeprefix(f"{M}.") for name in SCALAR_HELPERS)
    assert all(hasattr(production, name) for name in required)
    frozen = _frozen_json({"count": "7", "path": "/tmp/c2e", "sha": "a" * 64})
    assert production._h11_exact_object_fields(
        frozen,
        ("count", "path", "sha"),
        label="C2e scalar object",
    ) is frozen
    assert production._h11_object_member(frozen, "count", label="C2e count") == "7"
    assert production._h11_text("value", label="C2e text") == "value"
    assert production._h11_uint("7", label="C2e uint") == 7
    assert production._h11_path("/tmp/c2e", label="C2e path") == Path("/tmp/c2e")
    assert production._h11_sha256_text("a" * 64, label="C2e SHA") == "a" * 64
    invalid_calls = (
        ("mutable-object", lambda: production._h11_exact_object_fields({}, (), label="mutable object")),
        ("mutable-list", lambda: production._h11_exact_object_fields([], (), label="mutable list")),
        ("bool-uint", lambda: production._h11_uint(True, label="bool uint")),
        ("leading-zero-uint", lambda: production._h11_uint("07", label="leading zero uint")),
        ("oversized-uint", lambda: production._h11_uint(str(1 << 64), label="oversized uint")),
        ("relative-path", lambda: production._h11_path("relative/path", label="relative path")),
        ("noncanonical-path", lambda: production._h11_path("/tmp/../tmp/c2e", label="noncanonical path")),
        ("uppercase-sha", lambda: production._h11_sha256_text("A" * 64, label="uppercase SHA")),
    )
    unexpectedly_accepted: list[str] = []
    for case_name, invalid_call in invalid_calls:
        try:
            invalid_call()
        except production.InstallerError:
            continue
        unexpectedly_accepted.append(case_name)
    assert unexpectedly_accepted == []


def test_c2e_validated_fifo_schema_and_wire_projection_are_closed() -> None:
    production = _load_installer()
    assert hasattr(production, "H11RootValidatedFifo"), "C2e validated FIFO is not implemented"
    fifo_type = production.H11RootValidatedFifo
    assert tuple(fifo_type.__dataclass_fields__) == (
        "role",
        "path",
        "owner",
        "uid",
        "gid",
        "mode",
        "device",
        "inode",
        "accepted_owners",
    )
    assert "__dict__" not in fifo_type.__dict__
    assert "from_tree_row" not in fifo_type.__dict__
    fifo = fifo_type(
        "run-main-ready",
        Path("/tmp/run-main-ready"),
        "fixture",
        1000,
        1000,
        0o600,
        1,
        2,
        ((1000, 1000),),
    )
    assert fifo.accepted_owners == ((1000, 1000),)
    for property_name in ("reference", "acquisition_reference"):
        if hasattr(fifo_type, property_name):
            assert "accepted_owners" not in getattr(fifo, property_name)


def test_c2e_direct_fifo_owner_policy_and_spec_identity_are_preserved(monkeypatch: pytest.MonkeyPatch) -> None:
    production = _load_installer()
    required = (
        "H11RootFifoReference",
        "H11RootValidatedFifo",
        "_make_h11_indirect_authority_spec",
    )
    assert all(hasattr(production, name) for name in required), "C2e FIFO policy is not implemented"
    wire = _frozen_json(
        {
            "path": "/tmp/h11-ready-commit",
            "device": "1",
            "inode": "2",
            "mode": "0600",
            "uid": "0",
            "gid": "0",
        }
    )
    reference = production.H11RootFifoReference.decode(
        wire,
        label="C2e direct FIFO",
        require_root=False,
        process_euid=1000,
        process_egid=1001,
    )
    assert reference.accepted_owners == ((0, 0), (1000, 1001))
    deduplicated = production.H11RootFifoReference.decode(
        wire,
        label="C2e direct FIFO root process",
        require_root=False,
        process_euid=0,
        process_egid=0,
    )
    assert deduplicated.accepted_owners == ((0, 0),)

    row = production.H11RootValidatedFifo(
        role="h11-ready-commit",
        path=Path("/tmp/h11-ready-commit"),
        owner="root",
        uid=0,
        gid=0,
        mode=0o600,
        device=1,
        inode=2,
        accepted_owners=reference.accepted_owners,
    )
    spec = production._make_h11_indirect_authority_spec(
        semantic_role="h11-ready-commit",
        equivalence_class="tree/fifo/h11-ready-commit",
        install_ordinal=None,
        path=row.path,
        kind="fifo",
        device=row.device,
        inode=row.inode,
        mode=row.mode,
        accepted_owners=row.accepted_owners,
    )
    assert row.accepted_owners is reference.accepted_owners
    assert spec.accepted_owners is reference.accepted_owners

    monkeypatch.setattr(os, "geteuid", lambda: pytest.fail("prove reread euid"))
    monkeypatch.setattr(os, "getegid", lambda: pytest.fail("prove reread egid"))
    accepted_info = SimpleNamespace(
        st_mode=stat.S_IFIFO | 0o600,
        st_dev=1,
        st_ino=2,
        st_uid=1000,
        st_gid=1001,
    )
    reference.prove(accepted_info, label="C2e accepted process owner")
    with pytest.raises(production.InstallerError):
        reference.prove(
            SimpleNamespace(**{**vars(accepted_info), "st_uid": 2000}),
            label="C2e foreign owner",
        )


def test_c2e_production_reachable_call_graph_matches_fixed_topology() -> None:
    result = H11ReachableCallScanner(INSTALLER_SOURCE.read_text(encoding="utf-8")).scan(ROOT_QNAME)
    assert result.unresolved == ()
    assert result.multi_target == ()
    assert result.unclassified == ()
    assert result.resolved_call_count == result.reachable_ast_call_count
    actual_edges = Counter(
        (call.caller_qname, call.canonical_target)
        for call in result.calls
        if call.target_kind == "internal"
    )
    for caller, callee, count in (
        *FLOW_INTERNAL_EDGES,
        *CORRECTION_INTERNAL_EDGES,
        *CODEC_INTERNAL_EDGES,
    ):
        assert actual_edges[(caller, callee)] == count, (
            caller,
            callee,
            actual_edges[(caller, callee)],
            count,
        )
    for helper in SCALAR_HELPERS:
        actual_callers = {
            call.caller_qname for call in result.calls if call.canonical_target == helper
        }
        assert actual_callers.issubset(SCALAR_HELPER_ALLOWED_CALLERS)
    actual_sensitive = {
        SensitiveSiteKey(
            call.caller_qname,
            call.canonical_target,
            call.lexical_target,
            call.same_caller_occurrence,
        )
        for call in result.calls
        if call.target_kind == "sensitive"
    }
    assert {
        key for key, _owner in SUPPLEMENTAL_SENSITIVE_FAULT_OWNER
    }.issubset(actual_sensitive)
