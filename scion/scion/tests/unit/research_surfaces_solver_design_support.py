from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from scion.contract.gate import ContractGate
from scion.core.models import HypothesisProposal, PatchProposal
from scion.problem.bridge import (
    legacy_problem_spec_from_v1,
    load_problem_spec_v1_from_yaml,
)
from scion.problems.cvrp.adapter import CvrpAdapter
from scion.tests.unit.research_surface_helpers import _CVRP_ROOT


def _gate_with_cvrp_champion(
    tmp_path: Path,
    rel_paths: tuple[str, ...],
) -> tuple[ContractGate, dict[str, str]]:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    champion = tmp_path / "champion"
    codes: dict[str, str] = {}
    for rel_path in rel_paths:
        source = _CVRP_ROOT / rel_path
        code = source.read_text(encoding="utf-8")
        target = champion / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(code, encoding="utf-8")
        codes[rel_path] = code
    gate = ContractGate(
        legacy_problem_spec_from_v1(spec),
        champion_snapshot_path=str(champion),
    )
    return gate, codes


__all__ = [
    name
    for name in globals()
    if not (name.startswith("__") and name.endswith("__"))
]
