"""Focused tests split from test_sprint_e3.py."""

from .sprint_e3_test_support import *  # noqa: F401,F403

class TestT25StagnationDetector:
    """T25: StagnationDetector detects collapse, oscillation, plateau, timeout."""

    def test_no_signal_when_healthy(self):
        detector = StagnationDetector(window_size=5)
        # Use different mechanisms and varying win rates to avoid plateau/oscillation
        texts = [
            "subcategory consolidation via merging vehicles",
            "destroy rebuild approach completely",
            "order swap between vehicles",
            "cost reduction by downsizing vehicle type",
            "rebalance loads across vehicles",
        ]
        steps = [
            _make_step(round_num=i, decision=Decision.QUEUE_VALIDATE,
                       protocol_result=_make_protocol_result("pass", 0.5 + i * 0.1),
                       hypothesis_text=texts[i])
            for i in range(5)
        ]
        signals = detector.check(steps)
        assert signals == []

    def test_detects_collapse(self):
        detector = StagnationDetector()
        steps = [
            _make_step(round_num=i, failure_stage="verification", failure_detail="V1_syntax: err")
            for i in range(4)
        ]
        signals = detector.check(steps)
        kinds = {s.kind for s in signals}
        assert "collapse" in kinds

    def test_collapse_severity_critical_at_5(self):
        detector = StagnationDetector()
        steps = [
            _make_step(round_num=i, failure_stage="verification", failure_detail="V1_syntax: err")
            for i in range(6)
        ]
        signals = detector.check(steps)
        collapse_signals = [s for s in signals if s.kind == "collapse"]
        assert any(s.severity == "critical" for s in collapse_signals)

    def test_detects_oscillation(self):
        detector = StagnationDetector(window_size=6)
        # Alternating pass/fail pattern
        steps = []
        for i in range(6):
            if i % 2 == 0:
                steps.append(_make_step(round_num=i, decision=Decision.QUEUE_VALIDATE,
                                        protocol_result=_make_protocol_result("pass", 0.7)))
            else:
                steps.append(_make_step(round_num=i, decision=Decision.ABANDON,
                                        protocol_result=_make_protocol_result("fail", 0.3)))
        signals = detector.check(steps)
        kinds = {s.kind for s in signals}
        assert "oscillation" in kinds

    def test_no_oscillation_with_few_steps(self):
        detector = StagnationDetector()
        steps = [_make_step(round_num=1)]
        signals = detector.check(steps)
        assert not any(s.kind == "oscillation" for s in signals)

    def test_detects_timeout_cascade(self):
        detector = StagnationDetector()
        steps = [
            _make_step(round_num=i, failure_stage="screening", failure_detail="timeout: process killed")
            for i in range(3)
        ]
        signals = detector.check(steps)
        kinds = {s.kind for s in signals}
        assert "timeout_cascade" in kinds

    def test_empty_history(self):
        detector = StagnationDetector()
        assert detector.check([]) == []

    def test_signals_have_required_fields(self):
        detector = StagnationDetector()
        steps = [
            _make_step(round_num=i, failure_stage="verification", failure_detail="V1_syntax: x")
            for i in range(4)
        ]
        signals = detector.check(steps)
        for sig in signals:
            assert sig.kind in ("oscillation", "plateau", "collapse", "timeout_cascade")
            assert sig.severity in ("warning", "critical")
            assert isinstance(sig.detail, str)
            assert isinstance(sig.suggested_action, str)


class TestT23CampaignDiagnosis:
    """T23: diagnose() returns CampaignDiagnosis on critical stagnation."""

    def test_diagnosis_generated_on_stagnation(self):
        detector = StagnationDetector()
        steps = [
            _make_step(
                round_num=i,
                failure_stage="verification",
                failure_detail="V8_nondeterminism: uuid",
                hypothesis_text="subcategory consolidation merging",
            )
            for i in range(6)
        ]
        diag = detector.diagnose(round_num=6, step_history=steps)
        assert diag is not None
        assert isinstance(diag, CampaignDiagnosis)

    def test_diagnosis_format(self):
        detector = StagnationDetector()
        steps = [
            _make_step(
                round_num=i,
                failure_stage="verification",
                failure_detail="V6_feasibility: assignment mismatch",
                hypothesis_text="destroy rebuild approach",
            )
            for i in range(5)
        ]
        diag = detector.diagnose(round_num=5, step_history=steps)
        assert diag is not None
        assert diag.round_num == 5
        assert isinstance(diag.signals, list)
        assert isinstance(diag.family_distribution, dict)
        assert isinstance(diag.failure_pattern, dict)
        assert diag.recommendation in (
            "diversify_locus", "switch_action", "check_environment", "increase_screening_n"
        )

    def test_no_diagnosis_when_healthy(self):
        detector = StagnationDetector()
        steps = [
            _make_step(round_num=i, decision=Decision.QUEUE_VALIDATE,
                       protocol_result=_make_protocol_result("pass", 0.75))
            for i in range(3)
        ]
        diag = detector.diagnose(round_num=3, step_history=steps)
        assert diag is None

    def test_signals_in_summary(self, tmp_path):
        """Stagnation signals appear in campaign_summary.json."""
        from scion.config.problem import ProblemSpec, ProtocolConfig, SplitManifest, SeedLedgerConfig, SearchSpace
        from scion.core.campaign import CampaignManager
        from scion.core.models import ChampionState
        from scion.proposal.mock_client import MockLLMClient

        op_dir = tmp_path / "operators"
        op_dir.mkdir()
        (op_dir / "local_search.py").write_text("class LocalSearch: pass\n")

        spec = ProblemSpec(
            name="test", root_dir=str(tmp_path),
            operator_categories=["ls"],
            search_space=SearchSpace(editable=["operators/*.py"], frozen=[], import_whitelist=[]),
        )
        champion = ChampionState(
            version=1, operator_pool={}, solver_config_hash="abc",
            code_snapshot_path=str(tmp_path), code_snapshot_hash="xyz",
        )
        mgr = CampaignManager(
            problem_spec=spec, protocol_config=ProtocolConfig(),
            split_manifest=SplitManifest(screening=[], validation=[], frozen=[]),
            seed_ledger=SeedLedgerConfig(screening=[1], validation=[2], frozen=[3]),
            llm_client=MockLLMClient(mode="success"),
            champion=champion,
            campaign_dir=str(tmp_path),
        )
        # Inject collapse-inducing steps and manually trigger stagnation check
        mgr._step_history = [
            _make_step(round_num=i, failure_stage="verification", failure_detail="V1_syntax: err")
            for i in range(5)
        ]
        mgr._run_stagnation_check()
        mgr._write_campaign_summary()

        summary = json.loads((tmp_path / "campaign_summary.json").read_text())
        assert "stagnation_signals" in summary
        assert len(summary["stagnation_signals"]) > 0
        assert any(s["kind"] == "collapse" for s in summary["stagnation_signals"])


class TestT24PostmortemCLI:
    """T24: scion postmortem command generates markdown report."""

    def _make_summary(self, tmp_path: Path) -> Path:
        summary = {
            "campaign_id": "test-campaign-123",
            "total_rounds": 10,
            "champion_version": 2,
            "cache_stats": {
                "total_tokens": 5000,
                "cache_read_tokens": 2000,
                "cache_create_tokens": 3000,
                "cache_hit_rate": 0.4,
            },
            "verification_failure_breakdown": {"V8_nondeterminism": 3, "V6_feasibility": 1},
            "action_locus_coverage": {"modify/vehicle_level": 5, "create_new/order_level": 3},
            "family_coverage": {"subcategory_consolidation": 6, "destroy_rebuild": 2},
            "budget_utilization": 0.25,
            "stagnation_signals": [
                {
                    "kind": "collapse",
                    "severity": "critical",
                    "detail": "5 consecutive hard failures",
                    "suggested_action": "check_environment",
                }
            ],
            "diagnostics": [
                {
                    "round_num": 8,
                    "recommendation": "check_environment",
                    "family_distribution": {"subcategory_consolidation": 4},
                    "failure_pattern": {"verification": 3},
                    "signals": [],
                }
            ],
            "steps": [
                {
                    "round": 1,
                    "branch_id": "abc",
                    "decision": "promote",
                    "contract_passed": True,
                    "verification_passed": True,
                    "failure_stage": None,
                    "failure_detail": None,
                    "hypothesis": {
                        "text": "Merge subcategory vehicles",
                        "action": "modify",
                        "change_locus": "vehicle_level",
                        "target_file": "operators/merge.py",
                    },
                    "protocol_result": {"stage": "screening", "win_rate": 0.83, "gate_outcome": "pass"},
                },
                {
                    "round": 2,
                    "branch_id": "abc",
                    "decision": "abandon",
                    "contract_passed": True,
                    "verification_passed": False,
                    "failure_stage": "verification",
                    "failure_detail": "V8_nondeterminism: uuid",
                    "hypothesis": {
                        "text": "Try destroy-rebuild",
                        "action": "create_new",
                        "change_locus": "order_level",
                        "target_file": None,
                    },
                    "protocol_result": None,
                },
            ],
        }
        summary_file = tmp_path / "campaign_summary.json"
        summary_file.write_text(json.dumps(summary, indent=2))
        return summary_file

    def test_postmortem_cli_runs(self, tmp_path):
        from typer.testing import CliRunner
        from scion.cli.main import app

        self._make_summary(tmp_path)
        runner = CliRunner()
        result = runner.invoke(app, ["postmortem", str(tmp_path)])
        assert result.exit_code == 0, f"CLI failed: {result.output}"
        assert "Postmortem" in result.output or "Campaign Summary" in result.output

    def test_postmortem_output_format(self, tmp_path):
        from typer.testing import CliRunner
        from scion.cli.main import app

        self._make_summary(tmp_path)
        runner = CliRunner()
        result = runner.invoke(app, ["postmortem", str(tmp_path)])
        output = result.output

        # Check required sections
        assert "Campaign Summary" in output
        assert "Family Distribution" in output or "family" in output.lower()
        assert "Failure" in output
        assert "Stagnation" in output or "stagnation" in output.lower()
        assert "Recommendations" in output or "recommendation" in output.lower()

    def test_postmortem_output_file(self, tmp_path):
        from typer.testing import CliRunner
        from scion.cli.main import app

        self._make_summary(tmp_path)
        out_file = tmp_path / "report.md"
        runner = CliRunner()
        result = runner.invoke(app, ["postmortem", str(tmp_path), "--output", str(out_file)])
        assert result.exit_code == 0
        assert out_file.exists()
        content = out_file.read_text()
        assert "Campaign Summary" in content

    def test_postmortem_missing_summary(self, tmp_path):
        from typer.testing import CliRunner
        from scion.cli.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["postmortem", str(tmp_path)])
        assert result.exit_code != 0
        assert "ERROR" in result.output or "not found" in result.output
