from __future__ import annotations

from scion.core.models import ChampionState, OperatorConfig
from scion.lineage.research_champion_store import ChampionStore


def _champion(version: int, revision: int = 0) -> ChampionState:
    return ChampionState(
        version=version,
        weight_revision=revision,
        operator_pool={
            "pair": OperatorConfig(
                name="pair",
                file_path="operators/pair.py",
                category="local_search",
                weight=0.7,
                class_name="PairMove",
            )
        },
        solver_config_hash="solver-config",
        code_snapshot_path=f"champions/v{version}",
        code_snapshot_hash=f"code-{version}-{revision}",
        promotion_experiment_id="experiment-1",
        promotion_dossier_ref="artifacts/promotion/dossier.json",
    )


def test_plain_append_and_revision_queries(tmp_path) -> None:
    store = ChampionStore(tmp_path / "scion.db", tmp_path / "champions")
    store.promote(_champion(1))
    store.promote(_champion(1, 1))
    store.promote(_champion(2))

    assert store.get_current() == _champion(2)
    assert store.get_by_version(1) == _champion(1, 1)
    assert store.get_by_version_revision(1, 0) == _champion(1)
    assert store.get_history() == [_champion(1), _champion(1, 1), _champion(2)]
    assert store.snapshot_path_for(2) == tmp_path / "champions" / "v2"
    store.close()
