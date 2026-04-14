from __future__ import annotations
import ast
import os
from typing import Dict, Optional
import yaml

from scion.core.models import OperatorConfig, HypothesisProposal, PatchProposal


class PoolManager:
    def __init__(self, initial_pool: Dict[str, OperatorConfig]) -> None:
        self._pool = dict(initial_pool)

    def build_candidate_pool(
        self,
        champion_pool: Dict[str, OperatorConfig],
        hypothesis: HypothesisProposal,
        patch: PatchProposal,
        workspace: Optional[str] = None,
    ) -> Dict[str, OperatorConfig]:
        """
        Construct a candidate pool from the champion pool by applying the
        hypothesis action (modify / create_new / remove).

        If workspace is provided, scans the patched file's AST to extract
        the actual class name (handles LLM renaming the class on modify/create).
        """
        pool = dict(champion_pool)
        action = hypothesis.action

        if action == "modify":
            # Find operator whose file_path matches the target and update it
            target = hypothesis.target_file
            for name, op in list(pool.items()):
                if op.file_path == target or name == _stem(target or ""):
                    # Scan actual file for real class name if workspace available
                    scanned_class = None
                    if workspace:
                        abs_path = os.path.join(workspace, patch.file_path)
                        scanned_class = _scan_class_name(abs_path)
                    pool[name] = OperatorConfig(
                        name=op.name,
                        file_path=patch.file_path,
                        category=op.category,
                        weight=op.weight,
                        class_name=scanned_class if scanned_class else op.class_name,
                    )
                    break

        elif action == "create_new":
            new_name = _stem(patch.file_path)
            weight = hypothesis.suggested_weight if hypothesis.suggested_weight else 0.1
            # Scan actual file for real class name if workspace available
            scanned_class = None
            if workspace:
                abs_path = os.path.join(workspace, patch.file_path)
                scanned_class = _scan_class_name(abs_path)
            pool[new_name] = OperatorConfig(
                name=new_name,
                file_path=patch.file_path,
                category=hypothesis.change_locus,
                weight=weight,
                class_name=scanned_class if scanned_class else _guess_class_name(new_name),
            )
            pool = _normalize_weights(pool)

        elif action == "remove":
            target = hypothesis.target_file
            to_remove = None
            for name, op in pool.items():
                if op.file_path == target or name == _stem(target or ""):
                    to_remove = name
                    break
            if to_remove:
                del pool[to_remove]
                if pool:
                    pool = _normalize_weights(pool)

        return pool

    def export_registry(
        self, pool: Dict[str, OperatorConfig], target_dir: str
    ) -> str:
        """Export pool to registry.yaml in target_dir. Returns the file path."""
        os.makedirs(target_dir, exist_ok=True)
        registry_path = os.path.join(target_dir, "registry.yaml")
        operators_list = [
            {
                "name": op.name,
                "file_path": op.file_path,
                "category": op.category,
                "weight": round(op.weight, 6),
                "class_name": op.class_name,
            }
            for op in pool.values()
        ]
        with open(registry_path, "w") as f:
            yaml.dump({"operators": operators_list}, f, default_flow_style=False)
        return registry_path


# --- helpers ---

def _normalize_weights(pool: Dict[str, OperatorConfig]) -> Dict[str, OperatorConfig]:
    if not pool:
        return pool
    total = sum(op.weight for op in pool.values())
    if total <= 0:
        equal = 1.0 / len(pool)
        return {
            name: OperatorConfig(
                name=op.name, file_path=op.file_path,
                category=op.category, weight=equal, class_name=op.class_name,
            )
            for name, op in pool.items()
        }
    return {
        name: OperatorConfig(
            name=op.name, file_path=op.file_path,
            category=op.category, weight=op.weight / total, class_name=op.class_name,
        )
        for name, op in pool.items()
    }


def _stem(file_path: str) -> str:
    return os.path.splitext(os.path.basename(file_path))[0]


def _guess_class_name(stem: str) -> str:
    return "".join(word.capitalize() for word in stem.split("_"))


def _scan_class_name(abs_path: str) -> Optional[str]:
    """Parse a Python file's AST and return the first class definition name.

    Prefers a class that inherits from 'Operator' if present; otherwise
    returns the first class found. Returns None if the file doesn't exist
    or cannot be parsed.
    """
    try:
        with open(abs_path, encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
    except (OSError, SyntaxError):
        return None

    classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    if not classes:
        return None

    # Prefer class inheriting from Operator
    for cls in classes:
        for base in cls.bases:
            base_name = None
            if isinstance(base, ast.Name):
                base_name = base.id
            elif isinstance(base, ast.Attribute):
                base_name = base.attr
            if base_name == "Operator":
                return cls.name

    return classes[0].name


# ─────────────────────────────────────────────────────────────────────────────
# Module-level registry IO
# ─────────────────────────────────────────────────────────────────────────────

def read_registry(registry_path: str) -> Dict[str, OperatorConfig]:
    """Read operator pool from registry.yaml. Returns {name: OperatorConfig}."""
    with open(registry_path, 'r') as f:
        data = yaml.safe_load(f)
    pool = {}
    for op in data.get('operators', []):
        name = op['name']
        pool[name] = OperatorConfig(
            name=name,
            file_path=op['file_path'],
            category=op.get('category', ''),
            weight=op.get('weight', 1.0),
            class_name=op.get('class_name', _guess_class_name(name)),
        )
    return pool


def read_weights(registry_path: str) -> Dict[str, float]:
    """Read only the weight values from registry.yaml. Returns {operator_name: weight}."""
    pool = read_registry(registry_path)
    return {name: op.weight for name, op in pool.items()}


def update_weights(registry_path: str, weights: Dict[str, float]) -> None:
    """Update only the weight field in registry.yaml. Preserves all other fields.

    Raises:
        KeyError: if weights keys don't exactly match registry operator names.
    """
    with open(registry_path, 'r') as f:
        data = yaml.safe_load(f)

    operators = data.get('operators', [])
    registry_names = {op['name'] for op in operators}
    weight_names = set(weights.keys())

    if registry_names != weight_names:
        missing_in_weights = registry_names - weight_names
        extra_in_weights = weight_names - registry_names
        raise KeyError(
            f"Weight map mismatch. Missing: {missing_in_weights}, Extra: {extra_in_weights}"
        )

    for op in operators:
        op['weight'] = round(weights[op['name']], 6)

    with open(registry_path, 'w') as f:
        yaml.dump(data, f, default_flow_style=False)
