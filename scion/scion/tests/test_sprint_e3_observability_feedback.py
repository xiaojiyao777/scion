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
        from scion.problem.spec import ObjectiveMetricSpec
        from scion.protocol.experiment import ExperimentProtocol, SeedLedger, SplitManager
        from scion.tests.protocol_adapter_test_support import protocol_test_adapter

        op_dir = tmp_path / "operators"
        op_dir.mkdir()
        (op_dir / "local_search.py").write_text("class LocalSearch: pass\n")

        metric_specs = (
            ObjectiveMetricSpec(name="cost", direction="minimize", priority=1),
        )
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
        adapter = protocol_test_adapter(metric_specs, problem_spec=spec)
        champion = ChampionState(
            version=1, operator_pool={},
            code_snapshot_path=str(tmp_path),
        )
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
            adapter=adapter,
        )
        mgr = CampaignManager(
            protocol_config=ProtocolConfig(),
            split_manifest=split,
            seed_ledger=seeds,
            llm_client=MockLLMClient(mode="success"),
            champion=champion,
            campaign_dir=str(tmp_path / "campaign"),
            experiment_protocol=experiment_protocol,
            adapter=adapter,
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
                hypothesis_text="subcategory consolidation via merging vehicles",
            ),
            _make_step(
                round_num=2,
                decision=Decision.QUEUE_VALIDATE,
                protocol_result=_make_protocol_result("pass", 0.75),
                hypothesis_text="destroy rebuild approach",
            ),
        ]
        mgr._write_campaign_summary()

        summary_path = Path(mgr._campaign_dir) / "campaign_summary.json"
        assert summary_path.exists(), "campaign_summary.json not written"
        summary = json.loads(summary_path.read_text())

        # Top-level observability fields
        assert "cache_stats" not in summary
        assert "verification_failure_breakdown" in summary, "Missing verification_failure_breakdown"
        assert "action_locus_coverage" in summary, "Missing action_locus_coverage"
        assert "family_coverage" in summary, "Missing family_coverage"
        assert "diagnostics" in summary, "Missing diagnostics"

        # Verification failure breakdown has entry
        assert "V8_nondeterminism" in summary["verification_failure_breakdown"]

        # Family coverage (mechanism label from hypothesis text)
        assert len(summary["family_coverage"]) > 0
