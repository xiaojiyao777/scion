from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from scion.config.problem import (
    ProblemSpec,
    ProtocolConfig,
    SearchSpace,
    SeedLedgerConfig,
    SplitManifest,
)
from scion.core.campaign import CampaignManager
import scion.core.campaign_composition as campaign_composition
from scion.core.models import ChampionState
from scion.proposal.mock_client import MockLLMClient
from scion.problem.spec import ObjectiveMetricSpec
from scion.protocol.experiment import ExperimentProtocol, SeedLedger, SplitManager


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

        def archive_workspace(self, workspace: str, branch_id: str) -> None:
            return None

        def cleanup(self, workspace: str) -> None:
            return None

    monkeypatch.setattr(campaign_composition, "WorkspaceMaterializer", FakeMaterializer)

    cvrp_spec = ProblemSpec.from_yaml(
        str(Path(__file__).resolve().parents[2] / "problems" / "cvrp" / "problem.yaml")
    )
    champion_root = tmp_path / "champion"
    champion_root.mkdir()
    split = SplitManifest(
        screening=["screening-case"],
        validation=["validation-case"],
        frozen=["frozen-case"],
        canary=["canary-case"],
    )
    seeds = SeedLedgerConfig(
        screening=[1], validation=[2], frozen=[3], canary=[4]
    )
    experiment_protocol = ExperimentProtocol(
        ProtocolConfig(),
        SplitManager(split),
        SeedLedger(seeds),
        runner=object(),
        metrics_dir=str(tmp_path / "protocol-metrics"),
        metric_specs=(
            ObjectiveMetricSpec(
                name="total_distance", direction="minimize", priority=1
            ),
        ),
        problem_spec=cvrp_spec,
    )

    manager = CampaignManager(
        problem_spec=cvrp_spec,
        protocol_config=ProtocolConfig(),
        split_manifest=split,
        seed_ledger=seeds,
        llm_client=MockLLMClient(),
        champion=ChampionState(
            version=1,
            operator_pool={},
            code_snapshot_path=str(champion_root),
        ),
        campaign_dir=str(tmp_path / "campaign"),
        experiment_protocol=experiment_protocol,
        adapter=SimpleNamespace(spec=cvrp_spec),
    )

    assert manager._materializer is instances[0]
    assert instances[0].editable_patterns == SOLVER_DESIGN_PATTERNS
    assert "operators/*.py" not in instances[0].editable_patterns
    assert "policies/*.py" not in instances[0].editable_patterns
