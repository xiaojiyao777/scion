"""Focused tests split from test_sprint_e3.py."""

from .sprint_e3_test_support import *  # noqa: F401,F403

class TestT06ObservabilityFields:
    """T06: campaign_summary.json must contain new observability fields."""

    def _build_mock_campaign(self, tmp_path: Path):
        """Build a minimal CampaignManager with mock steps to test summary writing."""
        from scion.config.problem import ProblemSpec, ProtocolConfig, SplitManifest, SeedLedgerConfig, SearchSpace
        from scion.core.campaign import CampaignManager
        from scion.core.models import ChampionState
        from scion.proposal.mock_client import MockLLMClient

        op_dir = tmp_path / "operators"
        op_dir.mkdir()
        (op_dir / "local_search.py").write_text("class LocalSearch: pass\n")

        spec = ProblemSpec(
            name="test",
            root_dir=str(tmp_path),
            operator_categories=["local_search"],
            search_space=SearchSpace(
                editable=["operators/*.py"],
                frozen=["solver.py"],
                import_whitelist=["random"],
            ),
        )
        champion = ChampionState(
            version=1, operator_pool={}, solver_config_hash="abc",
            code_snapshot_path=str(tmp_path), code_snapshot_hash="xyz",
        )
        mgr = CampaignManager(
            problem_spec=spec,
            protocol_config=ProtocolConfig(),
            split_manifest=SplitManifest(screening=[], validation=[], frozen=[]),
            seed_ledger=SeedLedgerConfig(screening=[1], validation=[2], frozen=[3]),
            llm_client=MockLLMClient(mode="success"),
            champion=champion,
            campaign_dir=str(tmp_path),
        )
        return mgr

    def test_summary_contains_observability_fields(self, tmp_path):
        mgr = self._build_mock_campaign(tmp_path)

        # Inject some synthetic step history
        mgr._step_history = [
            _make_step(
                round_num=1,
                failure_stage="verification",
                failure_detail="V8_nondeterminism: uuid used",
                cache_stats={"total": 1000, "cache_read": 300, "cache_create": 700},
                hypothesis_text="subcategory consolidation via merging vehicles",
            ),
            _make_step(
                round_num=2,
                decision=Decision.QUEUE_VALIDATE,
                protocol_result=_make_protocol_result("pass", 0.75),
                cache_stats={"total": 1200, "cache_read": 600, "cache_create": 600},
                hypothesis_text="destroy rebuild approach",
            ),
        ]
        mgr._budget.used = 5
        mgr._budget.total = 20

        mgr._write_campaign_summary()

        summary_path = tmp_path / "campaign_summary.json"
        assert summary_path.exists(), "campaign_summary.json not written"
        summary = json.loads(summary_path.read_text())

        # Top-level observability fields
        assert "cache_stats" in summary, "Missing cache_stats"
        assert "verification_failure_breakdown" in summary, "Missing verification_failure_breakdown"
        assert "action_locus_coverage" in summary, "Missing action_locus_coverage"
        assert "family_coverage" in summary, "Missing family_coverage"
        assert "budget_utilization" in summary, "Missing budget_utilization"
        assert "stagnation_signals" in summary, "Missing stagnation_signals"
        assert "diagnostics" in summary, "Missing diagnostics"

        # Cache stats correctness
        cs = summary["cache_stats"]
        assert cs["total_tokens"] == 2200
        assert cs["cache_read_tokens"] == 900
        assert cs["cache_hit_rate"] == pytest.approx(900 / 2200, abs=1e-4)

        # Budget utilization
        assert summary["budget_utilization"] == pytest.approx(5 / 20, abs=1e-4)

        # Verification failure breakdown has entry
        assert "V8_nondeterminism" in summary["verification_failure_breakdown"]

        # Family coverage (mechanism label from hypothesis text)
        assert len(summary["family_coverage"]) > 0

    def test_failed_code_archived_in_steps(self, tmp_path):
        """Steps with code_archive_ref show public archive refs in summary."""
        mgr = self._build_mock_campaign(tmp_path)
        mgr._step_history = [
            _make_step(
                round_num=1,
                failure_stage="verification",
                failure_detail="V1_syntax: bad syntax",
                code_archive_ref="/tmp/archive/round_1_abc12345",
            ),
        ]
        mgr._write_campaign_summary()
        summary = json.loads((tmp_path / "campaign_summary.json").read_text())
        step = summary["steps"][0]
        assert not step["code_archive_ref"].startswith("/")
        assert "round_1_abc12345" in step["code_archive_ref"]
        assert step["verification_detail"] is None  # no verification_detail was set


class TestT09RicherCaseFeedback:
    """T09: _render_case_feedback must produce richer, directional output."""

    def _make_case_feedback(
        self,
        case_id: str = "scr_l01",
        dominant_result: str = "win",
        dominant_decisive_objective: str = "business_aggregation",
        median_delta_subcategory_splits: Optional[float] = -5.0,
        median_delta_total_cost: Optional[float] = 1000.0,
        case_features: Optional[Dict] = None,
    ) -> CaseAggregateFeedback:
        median_deltas = {}
        if median_delta_subcategory_splits is not None:
            median_deltas["subcategory_splits"] = median_delta_subcategory_splits
        if median_delta_total_cost is not None:
            median_deltas["total_cost"] = median_delta_total_cost
        return CaseAggregateFeedback(
            case_id=case_id,
            n_pairs=6,
            wins=4,
            losses=2,
            ties=0,
            win_rate=0.67,
            dominant_result=dominant_result,
            decisive_metric=dominant_decisive_objective,
            median_deltas=median_deltas,
            seed_consistency=0.67,
            case_features=case_features or {"size_bucket": "large", "n_orders": 150},
            # Deprecated aliases
            dominant_decisive_objective=dominant_decisive_objective,
            median_delta_total_cost=median_delta_total_cost,
            median_delta_subcategory_splits=median_delta_subcategory_splits,
        )

    def test_feedback_includes_decisive_objective(self):
        from scion.proposal.context_manager import _render_case_feedback
        cf = self._make_case_feedback()
        result = _render_case_feedback(cf)
        assert "Decisive:" in result

    def test_feedback_shows_directional_change_win(self):
        from scion.proposal.context_manager import _render_case_feedback
        cf = self._make_case_feedback(
            dominant_result="win",
            dominant_decisive_objective="subcategory_splits",
            median_delta_subcategory_splits=22.0,
        )
        result = _render_case_feedback(cf)
        assert "↓" in result or "22" in result

    def test_feedback_shows_directional_change_loss(self):
        from scion.proposal.context_manager import _render_case_feedback
        # splits_delta negative → candidate worse (more splits) → up arrow
        cf = self._make_case_feedback(
            dominant_result="loss",
            dominant_decisive_objective="business_aggregation",
            median_delta_subcategory_splits=-2.0,  # negative = candidate worse
        )
        result = _render_case_feedback(cf)
        # Should show ↑ (candidate increased splits)
        assert "↑" in result or "2.0" in result

    def test_feedback_shows_champion_baseline(self):
        from scion.proposal.context_manager import _render_case_feedback
        cf = self._make_case_feedback(
            case_features={"size_bucket": "large", "n_orders": 150, "champion_splits": 40}
        )
        result = _render_case_feedback(cf)
        assert "Champion baseline" in result or "40" in result

    def test_feedback_shows_result_label(self):
        from scion.proposal.context_manager import _render_case_feedback
        for result_str in ["win", "loss", "mixed"]:
            cf = self._make_case_feedback(dominant_result=result_str)
            rendered = _render_case_feedback(cf)
            assert result_str.upper() in rendered
