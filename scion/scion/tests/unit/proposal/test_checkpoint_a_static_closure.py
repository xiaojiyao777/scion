from __future__ import annotations

import ast
from pathlib import Path

from scion.proposal import hypothesis_generation_authority


_PACKAGE_ROOT = Path(hypothesis_generation_authority.__file__).resolve().parents[1]
_LEAF_PATH = Path(hypothesis_generation_authority.__file__).resolve()
_LEAF_MODULE = "scion.proposal.hypothesis_generation_authority"

_REGISTRY = "core/campaign_owner_registry.py"
_PROPOSAL_OWNER = "lineage/proposal_attempt_owner.py"
_CODE_SOURCE_OWNER = "proposal/hypothesis_code_source_owner.py"
_CONTEXT_MANAGER = "proposal/context_manager/manager.py"
_PROMPT_OWNER = "proposal/prompt_projection_authority.py"
_PROVIDER_OWNER = "proposal/engine/provider_call.py"

_LEAF_IMPORTERS = {
    _REGISTRY,
    _PROPOSAL_OWNER,
    _CODE_SOURCE_OWNER,
    _CONTEXT_MANAGER,
    _PROMPT_OWNER,
    _PROVIDER_OWNER,
}

_LEAF_EXTERNAL_CALLERS = {
    "_install_checkpoint_a_authorities": set(),
    "_require_authority": set(_LEAF_IMPORTERS),
    "_require_same_installation": {_REGISTRY},
    "_issue_generation_view": {_REGISTRY},
    "_inspect_generation_view": set(),
    "_issue_code_source_request": {_REGISTRY},
    "_spend_prestart_generation_view": {_REGISTRY},
    "_abort_prestart_generation_view": {_REGISTRY},
    "_finish_start_without_authority": {_REGISTRY},
    "_hold_generation_view": {_REGISTRY},
    "_claim_code_source_request": {_CODE_SOURCE_OWNER},
    "_finish_code_source_request_failure": {_CODE_SOURCE_OWNER},
    "_issue_code_source": {_CODE_SOURCE_OWNER},
    "_inspect_code_source": {_REGISTRY},
    "_claim_code_source_for_evidence": {_CONTEXT_MANAGER},
    "_finish_problem_evidence_failure": {_CONTEXT_MANAGER},
    "_issue_problem_evidence": {_CONTEXT_MANAGER},
    "_issue_prompt_source": {_REGISTRY},
    "_claim_prompt_source": {_PROMPT_OWNER},
    "_finish_prompt_failure": {_PROMPT_OWNER},
    "_settle_prompt_failure": {_REGISTRY},
    "_issue_bound_prompt": {_PROMPT_OWNER},
    "_inspect_bound_prompt": {_REGISTRY},
    "_begin_started_attempt": {_REGISTRY},
    "_claim_bound_prompt_for_start": {_PROPOSAL_OWNER},
    "_issue_started_attempt": {_PROPOSAL_OWNER},
    "_inspect_started_attempt": {_REGISTRY},
    "_issue_provider_permit": {_REGISTRY},
    "_claim_provider_permit": {_PROVIDER_OWNER},
    "_mark_provider_claim_unknown": {_PROVIDER_OWNER},
    "_settle_provider_claim_unknown": {_REGISTRY},
    "_issue_generated_result": {_PROVIDER_OWNER},
    "_issue_failed_generation": {_PROVIDER_OWNER},
    "_issue_aborted_generation": {_REGISTRY},
    "_inspect_generation_outcome": {_REGISTRY},
    "_begin_terminal_persistence": {_REGISTRY},
    "_claim_terminal_outcome": {_PROPOSAL_OWNER},
    "_issue_terminal_receipt": {_PROPOSAL_OWNER},
    "_resolve_terminal_receipt": {_REGISTRY},
}

_LEAF_INTERNAL_ONLY = {
    "_sealed_subclass",
    "_release_installed_owner_role",
    "_lookup_handle",
    "_new_context_binding",
    "_prove_context",
    "_retire_context",
    "_required_text",
    "_optional_text",
    "_optional_bool",
    "_required_digest",
    "_required_nonnegative_int",
    "_lookup_exact",
    "_handle_state",
    "_same_installation",
    "_normalize_source_entries",
}


def _production_trees() -> dict[str, ast.Module]:
    result: dict[str, ast.Module] = {}
    for path in _PACKAGE_ROOT.rglob("*.py"):
        relative = path.relative_to(_PACKAGE_ROOT)
        if "tests" in relative.parts:
            continue
        result[relative.as_posix()] = ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
        )
    return result


def _imports_leaf(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(
            alias.name == _LEAF_MODULE for alias in node.names
        ):
            return True
        if isinstance(node, ast.ImportFrom) and (
            node.module == _LEAF_MODULE
            or (
                node.module == "scion.proposal"
                and any(
                    alias.name == "hypothesis_generation_authority"
                    for alias in node.names
                )
            )
        ):
            return True
    return False


def _leaf_callers(
    trees: dict[str, ast.Module],
) -> dict[str, set[str]]:
    callers = {name: set() for name in _LEAF_EXTERNAL_CALLERS}
    for path, tree in trees.items():
        if (_PACKAGE_ROOT / path).resolve() == _LEAF_PATH:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in callers:
                callers[node.attr].add(path)
            elif isinstance(node, ast.ImportFrom) and node.module == _LEAF_MODULE:
                for alias in node.names:
                    if alias.name in callers:
                        callers[alias.name].add(path)
    return callers


def test_checkpoint_a_leaf_has_exact_importers_and_transition_callers() -> None:
    trees = _production_trees()
    importers = {path for path, tree in trees.items() if _imports_leaf(tree)}

    assert importers == _LEAF_IMPORTERS
    assert _leaf_callers(trees) == _LEAF_EXTERNAL_CALLERS


def test_checkpoint_a_leaf_function_surface_is_frozen() -> None:
    tree = ast.parse(_LEAF_PATH.read_text(encoding="utf-8"))
    functions = {
        node.name for node in tree.body if isinstance(node, ast.FunctionDef)
    }

    assert functions == set(_LEAF_EXTERNAL_CALLERS) | _LEAF_INTERNAL_ONLY


def test_checkpoint_a_has_no_dynamic_leaf_access_or_composition_caller() -> None:
    trees = _production_trees()
    dynamic_access: list[tuple[str, int]] = []
    component_install_callers: dict[str, set[str]] = {
        "_install_hypothesis_generation_authority": set(),
        "_install_hypothesis_generation_components": set(),
    }
    for path, tree in trees.items():
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in {"getattr", "setattr", "delattr", "hasattr"}
                and len(node.args) >= 2
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id in {"_generation", "generation"}
                and isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)
                and node.args[1].value.startswith("_")
            ):
                dynamic_access.append((path, node.lineno))
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "vars"
                and node.args
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id in {"_generation", "generation"}
            ):
                dynamic_access.append((path, node.lineno))
            if (
                isinstance(node, ast.Attribute)
                and node.attr == "__dict__"
                and isinstance(node.value, ast.Name)
                and node.value.id in {"_generation", "generation"}
            ):
                dynamic_access.append((path, node.lineno))
            if (
                isinstance(node, ast.Attribute)
                and node.attr in component_install_callers
            ):
                component_install_callers[node.attr].add(path)

    assert dynamic_access == []
    assert component_install_callers == {
        "_install_hypothesis_generation_authority": set(),
        "_install_hypothesis_generation_components": set(),
    }


def test_checkpoint_a_leaf_and_prompt_provider_dependencies_are_acyclic() -> None:
    leaf_tree = ast.parse(_LEAF_PATH.read_text(encoding="utf-8"))
    leaf_import_roots: set[str] = set()
    for node in ast.walk(leaf_tree):
        if isinstance(node, ast.Import):
            leaf_import_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            leaf_import_roots.add(node.module.split(".", 1)[0])
    assert leaf_import_roots <= {
        "__future__",
        "contextvars",
        "dataclasses",
        "enum",
        "hashlib",
        "threading",
        "typing",
        "weakref",
    }

    prompt_path = _PACKAGE_ROOT / _PROMPT_OWNER
    prompt_tree = ast.parse(prompt_path.read_text(encoding="utf-8"))
    prompt_imports = {
        alias.name
        for node in ast.walk(prompt_tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module
        for node in ast.walk(prompt_tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert "scion.proposal.engine.provider_call" not in prompt_imports


def test_checkpoint_a_transaction_bundle_reader_has_one_registry_caller() -> None:
    trees = _production_trees()
    callers = {
        path
        for path, tree in trees.items()
        if any(
            isinstance(node, ast.Attribute)
            and node.attr == "_load_branch_hypotheses_in"
            for node in ast.walk(tree)
        )
    }

    assert callers == {_REGISTRY}
