from __future__ import annotations

import fnmatch
import hashlib
import shutil
from pathlib import Path
from typing import Any

from scion.cli.commands import init_run as init_run_cmd
from scion.config.problem import (
    ProblemSpec,
    ProtocolConfig,
    SearchSpace,
    SeedLedgerConfig,
    SplitManifest,
)
from scion.core.campaign import CampaignManager
import scion.core.campaign_composition as campaign_composition
from scion.core.models import ChampionState, PatchProposal
from scion.external_ingest.ingest import ExternalProposalIngestor
import scion.external_ingest.ingest as ingest_module
from scion.proposal.mock_client import MockLLMClient
import scion.runtime.workspace as workspace_module


SOLVER_DESIGN_PATTERNS = (
    "policies/baseline_algorithm.py",
    "policies/baseline_modules/*.py",
)


def _solver_design_spec(root_dir: Path) -> ProblemSpec:
    return ProblemSpec(
        name="solver-design-test",
        root_dir=str(root_dir),
        operator_categories=["solver_design"],
        search_space=SearchSpace(
            editable=list(SOLVER_DESIGN_PATTERNS),
            frozen=["solver.py"],
            import_whitelist=[],
        ),
    )


def _write_solver_design_workspace(root: Path) -> None:
    (root / "operators").mkdir(parents=True)
    (root / "policies" / "baseline_modules").mkdir(parents=True)
    (root / "policies" / "baseline_algorithm.py").write_text(
        "def solve(instance, rng, time_limit_sec, context):\n"
        "    return None\n",
        encoding="utf-8",
    )
    (root / "policies" / "baseline_modules" / "acceptance.py").write_text(
        "def accept(candidate):\n"
        "    return True\n",
        encoding="utf-8",
    )
    (root / "policies" / "search_policy.py").write_text(
        "def choose():\n"
        "    return 'legacy'\n",
        encoding="utf-8",
    )
    (root / "operators" / "legacy.py").write_text(
        "class Legacy:\n"
        "    pass\n",
        encoding="utf-8",
    )


def test_campaign_composition_passes_cvrp_solver_design_editable_patterns(
    monkeypatch,
    tmp_path: Path,
) -> None:
    instances: list[Any] = []

    class FakeMaterializer:
        def __init__(
            self,
            campaign_dir: str,
            *,
            frozen_patterns: frozenset[str] | None = None,
            editable_patterns: tuple[str, ...] = (),
        ) -> None:
            self.campaign_dir = campaign_dir
            self.frozen_patterns = frozen_patterns
            self.editable_patterns = editable_patterns
            self._champions_dir = Path(campaign_dir) / "champions"
            self._champions_dir.mkdir(parents=True, exist_ok=True)
            instances.append(self)

        def create_champion_snapshot(
            self,
            champion: ChampionState,
            target_dir: str,
        ) -> str:
            snapshot = Path(target_dir) / f"champion_v{champion.version}"
            snapshot.mkdir(parents=True, exist_ok=True)
            return str(snapshot)

        def compute_snapshot_hash(self, workspace: str) -> str:
            return "hash-for-" + str(self.editable_patterns)

        def editable_identity_manifest(self, workspace: str) -> dict[str, object]:
            return {
                "schema_version": "scion.editable_identity_manifest.v1",
                "files": [],
                "code_hash": "0" * 64,
            }

        def archive_workspace(self, workspace: str, branch_id: str) -> None:
            return None

        def cleanup(self, workspace: str) -> None:
            return None

    monkeypatch.setattr(campaign_composition, "WorkspaceMaterializer", FakeMaterializer)

    cvrp_spec = ProblemSpec.from_yaml(
        str(Path("scion/scion/problems/cvrp/problem.yaml").resolve())
    )
    champion_root = tmp_path / "champion"
    champion_root.mkdir()

    manager = CampaignManager(
        problem_spec=cvrp_spec,
        protocol_config=ProtocolConfig(),
        split_manifest=SplitManifest(),
        seed_ledger=SeedLedgerConfig(),
        llm_client=MockLLMClient(),
        champion=ChampionState(
            version=1,
            operator_pool={},
            solver_config_hash="initial",
            code_snapshot_path=str(champion_root),
            code_snapshot_hash="initial",
        ),
        campaign_dir=str(tmp_path / "campaign"),
    )

    assert manager._materializer is instances[0]
    assert instances[0].editable_patterns == SOLVER_DESIGN_PATTERNS
    assert "operators/*.py" not in instances[0].editable_patterns
    assert "policies/*.py" not in instances[0].editable_patterns


def test_cli_initial_champion_hash_uses_exact_editable_identity(
    monkeypatch,
    tmp_path: Path,
) -> None:
    instances: list[Any] = []

    class HashingMaterializer:
        def __init__(
            self,
            campaign_dir: str,
            *,
            frozen_patterns: frozenset[str] | None = None,
            editable_patterns: tuple[str, ...] = (),
        ) -> None:
            self.campaign_dir = campaign_dir
            self.frozen_patterns = frozen_patterns
            self.editable_patterns = editable_patterns or frozenset()
            instances.append(self)

        def compute_snapshot_hash(self, workspace: str) -> str:
            root = Path(workspace)
            h = hashlib.sha256()
            for path in sorted(root.rglob("*.py")):
                rel = path.relative_to(root).as_posix()
                if any(
                    fnmatch.fnmatchcase(rel, pattern)
                    for pattern in self.editable_patterns
                ):
                    h.update(rel.encode())
                    h.update(path.read_bytes())
            return h.hexdigest()

    monkeypatch.setattr(workspace_module, "WorkspaceMaterializer", HashingMaterializer)

    root = tmp_path / "solver"
    _write_solver_design_workspace(root)
    spec = _solver_design_spec(root)

    initial_hash = init_run_cmd._compute_initial_champion_snapshot_hash(
        tmp_path / "campaign",
        spec,
    )
    (root / "policies" / "search_policy.py").write_text(
        "def choose():\n"
        "    return 'changed-but-not-declared'\n",
        encoding="utf-8",
    )
    after_undeclared_policy_hash = init_run_cmd._compute_initial_champion_snapshot_hash(
        tmp_path / "campaign",
        spec,
    )
    (root / "policies" / "baseline_modules" / "acceptance.py").write_text(
        "def accept(candidate):\n"
        "    return False\n",
        encoding="utf-8",
    )
    after_editable_module_hash = init_run_cmd._compute_initial_champion_snapshot_hash(
        tmp_path / "campaign",
        spec,
    )

    assert instances[0].editable_patterns == SOLVER_DESIGN_PATTERNS
    assert after_undeclared_policy_hash == initial_hash
    assert after_editable_module_hash != initial_hash


def test_external_ingest_materializer_uses_same_editable_identity(
    monkeypatch,
    tmp_path: Path,
) -> None:
    instances: list[Any] = []

    class FakeMaterializer:
        def __init__(
            self,
            campaign_dir: str,
            *,
            frozen_patterns: frozenset[str] | None = None,
            editable_patterns: tuple[str, ...] = (),
        ) -> None:
            self.campaign_dir = Path(campaign_dir)
            self.frozen_patterns = frozen_patterns
            self.editable_patterns = editable_patterns
            instances.append(self)

        def create_branch_workspace(self, branch_id: str, code_base: str) -> str:
            workspace = self.campaign_dir / "workspaces" / branch_id
            if workspace.exists():
                shutil.rmtree(workspace)
            shutil.copytree(code_base, workspace)
            return str(workspace)

        def apply_patch(self, workspace: str, patch: PatchProposal) -> str:
            target = Path(workspace) / patch.file_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(patch.code_content, encoding="utf-8")
            return "patched"

    monkeypatch.setattr(ingest_module, "WorkspaceMaterializer", FakeMaterializer)

    root = tmp_path / "solver"
    _write_solver_design_workspace(root)
    ingestor = ExternalProposalIngestor(
        problem_spec=_solver_design_spec(root),
        output_dir=tmp_path / "out",
    )

    workspace = ingestor._materialize_host_workspace(
        ingest_id="ingest-1",
        base_workspace=root,
        patch=PatchProposal(
            file_path="policies/baseline_modules/acceptance.py",
            action="modify",
            code_content="def accept(candidate):\n    return False\n",
        ),
        ingest_dir=tmp_path / "ingest",
    )

    assert instances[0].editable_patterns == SOLVER_DESIGN_PATTERNS
    assert instances[0].frozen_patterns == frozenset({"solver.py"})
    assert (
        workspace / "policies" / "baseline_modules" / "acceptance.py"
    ).read_text(encoding="utf-8").endswith("return False\n")
    workspace_manifest = (
        workspace / ".scion" / "external_ingest" / "workspace_manifest.json"
    )
    assert workspace_manifest.exists()
