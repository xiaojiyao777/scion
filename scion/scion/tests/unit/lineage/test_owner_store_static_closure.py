from __future__ import annotations

import ast
from pathlib import Path

from scion.core import campaign_owner_registry
from scion.lineage import branch_owner_store
from scion.lineage import champion_store
from scion.lineage import hypothesis_owner_store
from scion.lineage import owner_transaction
from scion.lineage import proposal_attempt_owner
from scion.proposal import hypothesis_code_source_owner

_BRANCH_PRIVATE = frozenset(
    {
        "_issue_branch_store_authority",
        "_require_branch_store_ledger",
        "_execute_branch_owner_update",
        "_execute_branch_owner_insert",
        "_issue_branch_mutation_receipt",
        "_issue_branch_creation_receipt",
    }
)
_HYPOTHESIS_PRIVATE = frozenset(
    {
        "_issue_hypothesis_store_authority",
        "_require_hypothesis_store_ledger",
        "_execute_hypothesis_owner_update",
        "_execute_hypothesis_owner_insert",
        "_issue_hypothesis_mutation_receipt",
        "_issue_hypothesis_creation_receipt",
    }
)
_MUTATION_REGISTRY_PRIVATE = frozenset(
    {
        "_attach_owner_receipt_ledger",
        "_consume_branch_mutation_receipt",
        "_consume_hypothesis_mutation_receipt",
        "_seal_owner_receipt_ledger",
        "_close_owner_receipt_ledger",
    }
)
_CREATION_REGISTRY_PRIVATE = frozenset(
    {
        "_consume_branch_creation_receipt",
        "_consume_hypothesis_creation_receipt",
    }
)
_CHAMPION_CREATION_PRIVATE = frozenset(
    {
        "_issue_branch_creation_authorizer_authority",
        "_register_branch_creation_authorization",
        "_issue_branch_semantic_creation_outcome_witness",
        "_complete_branch_creation_authorization",
    }
)
_REGISTRY_PRIVATE = _MUTATION_REGISTRY_PRIVATE | _CREATION_REGISTRY_PRIVATE
_SQLITE_BRIDGE_PRIVATE = frozenset(
    {
        "_install_transaction_authorizer_for_transaction",
        "_require_transaction_authorizer_for_transaction",
    }
)
_REGISTRY_SQLITE_PRIVATE = frozenset(
    {
        "_open_coordinated_transaction_session",
        "_coordinated_transaction",
        "_commit_coordinated_transaction",
        "_deactivate_coordinated_transaction",
        "_close_coordinated_transaction",
        "_settle_deactivated_original_connection",
        "_independent_authority_read_snapshot",
    }
)
_REGISTRY_SQLITE_STATE_PRIVATE = frozenset(
    {
        "_thread_session_owner",
        "_lookup_session_state",
        "_session_deactivation_complete",
    }
)
_SHARED_SQLITE_AUTHORITY_PRIVATE = frozenset({"_lookup_authority_state"})
_CHAMPION_DORMANT_SURFACE = frozenset(
    {
        "ConnectionScopedChampionStore",
        "_authorize_branch_creation_in",
        "_complete_branch_creation_in",
        "_require_branch_creation_outcome",
        "_settle_branch_creation_outcome",
        "_discard_branch_creation_outcome",
    }
)


def _production_trees() -> dict[Path, ast.Module]:
    package_root = Path(__file__).resolve().parents[3]
    result: dict[Path, ast.Module] = {}
    for path in package_root.rglob("*.py"):
        if "tests" in path.relative_to(package_root).parts:
            continue
        result[path] = ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
        )
    return result


def _attribute_callers(
    trees: dict[Path, ast.Module],
    names: frozenset[str],
) -> dict[str, set[Path]]:
    callers = {name: set() for name in names}
    for path, tree in trees.items():
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in names:
                callers[node.attr].add(path)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name in names:
                        callers[alias.name].add(path)
    return callers


def _owner_internal_private_names() -> frozenset[str]:
    owner_path = Path(owner_transaction.__file__).resolve()
    tree = ast.parse(
        owner_path.read_text(encoding="utf-8"),
        filename=str(owner_path),
    )
    private_definitions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("_")
    }
    approved_cross_module = (
        _BRANCH_PRIVATE
        | _HYPOTHESIS_PRIVATE
        | _REGISTRY_PRIVATE
        | _CHAMPION_CREATION_PRIVATE
    )
    return frozenset(private_definitions - approved_cross_module)


def _dynamic_private_references(
    trees: dict[Path, ast.Module],
    protected: frozenset[str],
) -> list[tuple[Path, int, str]]:
    violations: list[tuple[Path, int, str]] = []
    for path, tree in trees.items():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            function_name = (
                node.func.id
                if isinstance(node.func, ast.Name)
                else node.func.attr if isinstance(node.func, ast.Attribute) else None
            )
            if function_name not in {"getattr", "__import__", "import_module"}:
                continue
            for argument in node.args:
                if (
                    isinstance(argument, ast.Constant)
                    and isinstance(argument.value, str)
                    and argument.value in protected
                ):
                    violations.append((path, node.lineno, argument.value))
    return violations


def test_owner_private_importers_are_an_exact_dormant_allowlist() -> None:
    trees = _production_trees()
    branch_path = Path(branch_owner_store.__file__).resolve()
    hypothesis_path = Path(hypothesis_owner_store.__file__).resolve()
    owner_path = Path(owner_transaction.__file__).resolve()
    champion_path = Path(champion_store.__file__).resolve()
    proposal_attempt_path = Path(proposal_attempt_owner.__file__).resolve()
    registry_path = Path(campaign_owner_registry.__file__).resolve()

    assert all(
        callers == {branch_path}
        for callers in _attribute_callers(trees, _BRANCH_PRIVATE).values()
    )
    assert all(
        callers == {hypothesis_path}
        for callers in _attribute_callers(trees, _HYPOTHESIS_PRIVATE).values()
    )
    assert all(
        callers == {champion_path}
        for callers in _attribute_callers(
            trees,
            _CHAMPION_CREATION_PRIVATE,
        ).values()
    )
    assert all(
        callers == {registry_path}
        for callers in _attribute_callers(
            trees,
            _MUTATION_REGISTRY_PRIVATE,
        ).values()
    )
    assert all(
        callers == {registry_path}
        for callers in _attribute_callers(
            trees,
            _REGISTRY_SQLITE_STATE_PRIVATE,
        ).values()
    )
    assert _attribute_callers(
        trees,
        _SHARED_SQLITE_AUTHORITY_PRIVATE,
    ) == {
        "_lookup_authority_state": {
            owner_path,
            registry_path,
            champion_path,
            proposal_attempt_path,
        }
    }
    assert all(
        not callers
        for callers in _attribute_callers(
            trees,
            _CREATION_REGISTRY_PRIVATE,
        ).values()
    )
    assert all(
        callers == {owner_path}
        for callers in _attribute_callers(trees, _SQLITE_BRIDGE_PRIVATE).values()
    )
    assert all(
        callers == {registry_path}
        for callers in _attribute_callers(
            trees,
            _REGISTRY_SQLITE_PRIVATE,
        ).values()
    )
    assert all(
        not callers
        for callers in _attribute_callers(
            trees,
            _owner_internal_private_names(),
        ).values()
    )


def test_focused_owner_stores_have_no_production_importer() -> None:
    trees = _production_trees()
    registry_path = Path(campaign_owner_registry.__file__).resolve()
    focused_modules = {
        "scion.lineage.branch_owner_store",
        "scion.lineage.hypothesis_owner_store",
    }
    focused_names = {"branch_owner_store", "hypothesis_owner_store"}
    importers: set[Path] = set()
    for path, tree in trees.items():
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(
                alias.name in focused_modules for alias in node.names
            ):
                importers.add(path)
            elif isinstance(node, ast.ImportFrom):
                if node.module in focused_modules or (
                    node.module == "scion.lineage"
                    and any(alias.name in focused_names for alias in node.names)
                ):
                    importers.add(path)
    assert importers == {registry_path}


def test_connection_scoped_champion_surface_has_exact_checkpoint_a_reader() -> None:
    trees = _production_trees()
    champion_path = Path(champion_store.__file__).resolve()
    code_source_path = Path(hypothesis_code_source_owner.__file__).resolve()
    callers = _attribute_callers(
        trees,
        _CHAMPION_DORMANT_SURFACE,
    )
    assert callers == {
        "ConnectionScopedChampionStore": {code_source_path},
        "_authorize_branch_creation_in": set(),
        "_complete_branch_creation_in": set(),
        "_require_branch_creation_outcome": {champion_path},
        "_settle_branch_creation_outcome": set(),
        "_discard_branch_creation_outcome": set(),
    }


def test_focused_store_registry_surface_has_exact_production_callers() -> None:
    trees = _production_trees()
    registry_path = Path(campaign_owner_registry.__file__).resolve()
    mutation_callers = _attribute_callers(
        trees,
        frozenset({"compare_and_swap_in"}),
    )
    creation_callers = _attribute_callers(
        trees,
        frozenset({"insert_once_in"}),
    )
    snapshot_callers = _attribute_callers(
        trees,
        frozenset(
            {
                "_load_revisioned_branch_from_snapshot",
                "_load_all_revisioned_branches_from_snapshot",
                "_load_revisioned_hypothesis_from_snapshot",
                "_load_all_revisioned_hypotheses_from_snapshot",
                "_load_branch_hypotheses_from_snapshot",
            }
        ),
    )
    assert mutation_callers == {"compare_and_swap_in": {registry_path}}
    assert creation_callers == {"insert_once_in": set()}
    assert all(callers == {registry_path} for callers in snapshot_callers.values())


def test_campaign_owner_registry_has_no_production_composition_importer() -> None:
    trees = _production_trees()
    registry_path = Path(campaign_owner_registry.__file__).resolve()
    importers: set[Path] = set()
    for path, tree in trees.items():
        if path == registry_path:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(
                alias.name == "scion.core.campaign_owner_registry"
                for alias in node.names
            ):
                importers.add(path)
            elif isinstance(node, ast.ImportFrom) and (
                node.module == "scion.core.campaign_owner_registry"
                or (
                    node.module == "scion.core"
                    and any(
                        alias.name == "campaign_owner_registry" for alias in node.names
                    )
                )
            ):
                importers.add(path)
    assert importers == set()


def test_private_owner_symbols_are_not_reached_dynamically() -> None:
    protected = (
        _BRANCH_PRIVATE
        | _HYPOTHESIS_PRIVATE
        | _REGISTRY_PRIVATE
        | _SQLITE_BRIDGE_PRIVATE
        | _REGISTRY_SQLITE_PRIVATE
        | _REGISTRY_SQLITE_STATE_PRIVATE
        | _SHARED_SQLITE_AUTHORITY_PRIVATE
        | _CHAMPION_DORMANT_SURFACE
        | _owner_internal_private_names()
    )
    assert _dynamic_private_references(_production_trees(), protected) == []


def test_static_closure_detects_alias_direct_and_dynamic_private_access() -> None:
    alias_path = Path("alias_caller.py")
    direct_path = Path("direct_caller.py")
    dynamic_path = Path("dynamic_caller.py")
    trees = {
        alias_path: ast.parse(
            "import scion.lineage.owner_transaction as owner\n"
            "owner._execute_owner_statement()\n"
        ),
        direct_path: ast.parse(
            "from scion.lineage.owner_transaction import _issue_receipt\n"
        ),
        dynamic_path: ast.parse("getattr(owner, '_require_store_ledger')\n"),
    }
    callers = _attribute_callers(
        trees,
        frozenset({"_execute_owner_statement", "_issue_receipt"}),
    )
    assert callers == {
        "_execute_owner_statement": {alias_path},
        "_issue_receipt": {direct_path},
    }
    assert _dynamic_private_references(
        trees,
        frozenset({"_require_store_ledger"}),
    ) == [(dynamic_path, 1, "_require_store_ledger")]


def test_owner_public_exports_are_receipts_and_typed_errors_only() -> None:
    assert owner_transaction.__all__ == (
        "InvalidOwnerReceiptError",
        "InactiveOwnerTransactionError",
        "OwnerCreationReceipt",
        "OwnerMutationReceipt",
        "OwnerReceiptClosureError",
        "OwnerTransactionError",
        "OwnerWriteProtocolError",
        "SemanticCreationOutcomeWitness",
    )
    assert branch_owner_store.__all__ == ("BranchStore",)
    assert hypothesis_owner_store.__all__ == ("HypothesisStore",)
