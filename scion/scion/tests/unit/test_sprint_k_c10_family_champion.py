"""Focused tests split from test_sprint_k.py."""

from .sprint_k_test_support import *  # noqa: F401,F403

class TestK6C10ModifyKey:
    def _make_spec(self) -> MagicMock:
        spec = MagicMock()
        spec.operator_categories = ["vehicle_level"]
        spec.search_space = MagicMock()
        spec.search_space.editable = ["operators/*.py"]
        spec.search_space.frozen = []
        return spec

    def test_modify_different_text_passes_c10(self):
        """Two modify hypotheses on same file with different text are blocked — file-level key (K6-fix)."""
        gate = ContractGate(self._make_spec())
        h1 = HypothesisRecord(
            hypothesis_id="h1", branch_id="b1",
            change_locus="vehicle_level", action="modify",
            status="active", target_file="ops/foo.py",
            hypothesis_text="A" * 60,
        )
        hyp = HypothesisProposal(
            hypothesis_text="B" * 60,  # different text but same file
            change_locus="vehicle_level",
            action="modify",
            target_file="ops/foo.py",
        )
        result = gate._c10_novelty(hyp, [h1], [])
        assert not result.passed, "Same file modify should be blocked (K6-fix: file-level key)"

    def test_modify_same_text_blocked_by_c10(self):
        """Two modify hypotheses with same locus/file/text[:50] should be blocked."""
        gate = ContractGate(self._make_spec())
        shared_text = "Improve the subcategory consolidation logic in foo operator"
        h1 = HypothesisRecord(
            hypothesis_id="h1", branch_id="b1",
            change_locus="vehicle_level", action="modify",
            status="active", target_file="ops/foo.py",
            hypothesis_text=shared_text,
        )
        hyp = HypothesisProposal(
            hypothesis_text=shared_text,
            change_locus="vehicle_level",
            action="modify",
            target_file="ops/foo.py",
        )
        result = gate._c10_novelty(hyp, [h1], [])
        assert not result.passed

    def test_remove_action_uses_original_key_no_text(self):
        """remove action should still use (locus, action, file) without text."""
        gate = ContractGate(self._make_spec())
        h1 = HypothesisRecord(
            hypothesis_id="h1", branch_id="b1",
            change_locus="vehicle_level", action="remove",
            status="active", target_file="ops/foo.py",
            hypothesis_text="any text",
        )
        # Same remove target — should be blocked regardless of text
        hyp = HypothesisProposal(
            hypothesis_text="completely different text here",
            change_locus="vehicle_level",
            action="remove",
            target_file="ops/foo.py",
        )
        result = gate._c10_novelty(hyp, [h1], [])
        assert not result.passed

    def test_create_new_still_uses_text_key(self):
        """create_new should also be keyed with text[:50]."""
        gate = ContractGate(self._make_spec())
        h1 = HypothesisRecord(
            hypothesis_id="h1", branch_id="b1",
            change_locus="vehicle_level", action="create_new",
            status="active", target_file=None,
            hypothesis_text="Create operator A for subcategory handling",
        )
        hyp = HypothesisProposal(
            hypothesis_text="Create operator B for totally different purpose",
            change_locus="vehicle_level",
            action="create_new",
            target_file=None,
        )
        result = gate._c10_novelty(hyp, [h1], [])
        assert result.passed, f"Different create_new text should pass, got: {result.detail}"


class TestK7FamilyKey:
    def test_different_target_files_give_different_keys(self):
        key1 = _make_family_key("generic", "modify", "vehicle_level", "operators/foo.py")
        key2 = _make_family_key("generic", "modify", "vehicle_level", "operators/bar.py")
        assert key1 != key2

    def test_same_target_file_gives_same_key(self):
        key1 = _make_family_key("generic", "modify", "vehicle_level", "operators/foo.py")
        key2 = _make_family_key("generic", "modify", "vehicle_level", "operators/foo.py")
        assert key1 == key2

    def test_no_target_file_backward_compat(self):
        """Without target_file, key should match original 3-component format."""
        key_new = _make_family_key("generic", "modify", "vehicle_level", "")
        key_old = "generic/modify/vehicle_level"
        assert key_new == key_old

    def test_target_file_uses_filename_only(self):
        key = _make_family_key("generic", "modify", "vehicle_level", "some/deep/path/operators/foo.py")
        assert key == "generic/modify/vehicle_level/foo"

    def test_different_file_exhaustion_tracked_separately(self):
        """Two attempts on different files should create separate family entries."""
        from scion.core.models import EvalStats, ExperimentStage, HypothesisProposal, ProtocolResult, StepRecord

        mem = CampaignSearchMemory(family_taxonomy=WAREHOUSE_MECHANISM_TAXONOMY)

        def _make_step(text, file, wr=0.1, bid="b1", rnum=1):
            hyp = HypothesisProposal(
                hypothesis_text=text,
                change_locus="vehicle_level",
                action="modify",
                target_file=file,
            )
            proto = ProtocolResult(
                stage=ExperimentStage.SCREENING,
                stats=EvalStats(n_cases=5, wins=1, losses=4, ties=0,
                               win_rate=wr, median_delta=0.0, ci_low=0.0, ci_high=0.0),
                gate_outcome="fail",
                reason_codes=(),
                exposed_summary="",
                raw_metrics_ref="",
            )
            return StepRecord(
                round_num=rnum, branch_id=bid,
                hypothesis=hyp, patch=None,
                contract_passed=True, verification_passed=True,
                protocol_result=proto,
                decision=None, failure_stage=None, failure_detail=None,
            )

        for i in range(6):
            mem.update(_make_step("swap subcats in foo", "operators/foo.py", wr=0.1, rnum=i))
        for i in range(3):
            mem.update(_make_step("swap subcats in bar", "operators/bar.py", wr=0.1, rnum=i+10))

        foo_key = _make_family_key("order_swap", "modify", "vehicle_level", "operators/foo.py")
        bar_key = _make_family_key("order_swap", "modify", "vehicle_level", "operators/bar.py")
        assert foo_key in mem.families
        assert bar_key in mem.families
        assert mem.families[foo_key].total_attempts == 6
        assert mem.families[bar_key].total_attempts == 3
        # foo is exhausted (6 attempts, wr < 0.35); bar is not (only 3 attempts)
        assert mem.families[foo_key].is_exhausted
        assert not mem.families[bar_key].is_exhausted

    def test_family_entry_key_property_matches_make_family_key(self):
        entry = FamilyEntry(
            label="generic",
            locus="vehicle_level",
            action="modify",
            target_file="operators/baz.py",
        )
        expected = _make_family_key("generic", "modify", "vehicle_level", "operators/baz.py")
        assert entry.family_key == expected

    def test_family_entry_no_file_backward_compat(self):
        entry = FamilyEntry(label="generic", locus="vehicle_level", action="modify")
        assert entry.family_key == "generic/modify/vehicle_level"


class TestK8C10RejectsRejected:
    def _make_spec(self) -> MagicMock:
        spec = MagicMock()
        spec.operator_categories = ["order_level"]
        spec.search_space = MagicMock()
        spec.search_space.editable = ["operators/*.py"]
        spec.search_space.frozen = []
        return spec

    def _make_rejected(
        self,
        locus: str = "order_level",
        action: str = "modify",
        target_file: str = "operators/foo.py",
        text: str = "same text approach",
        hid: str = "h-rej",
    ) -> HypothesisRecord:
        return HypothesisRecord(
            hypothesis_id=hid,
            branch_id="b1",
            change_locus=locus,
            action=action,
            status="rejected",
            target_file=target_file,
            hypothesis_text=text,
        )

    # K8-1: basic — rejected hypothesis with same key blocks new proposal
    def test_rejected_same_text_blocks_c10(self):
        gate = ContractGate(self._make_spec())
        shared_text = "same text approach for foo"
        rejected = self._make_rejected(text=shared_text)
        hyp = HypothesisProposal(
            hypothesis_text=shared_text,
            change_locus="order_level",
            action="modify",
            target_file="operators/foo.py",
        )
        result = gate.validate_hypothesis(hyp, [], [], rejected_hypotheses=[rejected])
        assert not result.passed
        assert "C10_novelty" in (result.failure_reason or "")

    # K8-2: with K6-fix, same modify file is blocked regardless of text when champion version matches
    def test_rejected_different_text_passes_c10(self):
        gate = ContractGate(self._make_spec())
        rejected = self._make_rejected(text="approach A" + "x" * 50, hid="h-rej")
        rejected.base_champion_version = 0
        hyp = HypothesisProposal(
            hypothesis_text="approach B" + "y" * 50,  # different text, same file
            change_locus="order_level",
            action="modify",
            target_file="operators/foo.py",
        )
        # Same champion version (both 0): modify uses file-level key → blocked
        result = gate.validate_hypothesis(hyp, [], [], rejected_hypotheses=[rejected],
                                          current_champion_version=0)
        assert not result.passed, "Same file+champion_version modify should be blocked (K6-fix)"

    # K8-3a: backward compat — not passing rejected_hypotheses defaults to None, same behaviour
    def test_no_rejected_arg_backward_compat(self):
        gate = ContractGate(self._make_spec())
        hyp = HypothesisProposal(
            hypothesis_text="novel idea here",
            change_locus="order_level",
            action="modify",
            target_file="operators/foo.py",
        )
        result = gate.validate_hypothesis(hyp, [], [])
        assert result.passed

    # K8-3b: empty rejected list has no effect
    def test_empty_rejected_list_passes(self):
        gate = ContractGate(self._make_spec())
        hyp = HypothesisProposal(
            hypothesis_text="another novel idea",
            change_locus="order_level",
            action="modify",
            target_file="operators/foo.py",
        )
        result = gate.validate_hypothesis(hyp, [], [], rejected_hypotheses=[])
        assert result.passed

    # K8-4: blacklisted behaviour unchanged (regression)
    def test_blacklisted_still_blocked(self):
        gate = ContractGate(self._make_spec())
        shared_text = "blacklisted approach here"
        blacklisted = HypothesisRecord(
            hypothesis_id="h-bl",
            branch_id="b1",
            change_locus="order_level",
            action="modify",
            status="blacklisted",
            target_file="operators/foo.py",
            hypothesis_text=shared_text,
        )
        hyp = HypothesisProposal(
            hypothesis_text=shared_text,
            change_locus="order_level",
            action="modify",
            target_file="operators/foo.py",
        )
        result = gate.validate_hypothesis(hyp, [], [blacklisted])
        assert not result.passed
        assert "C10_novelty" in (result.failure_reason or "")


class TestK6FixChampionVersion:
    def _make_spec(self) -> MagicMock:
        spec = MagicMock()
        spec.operator_categories = ["vehicle_level"]
        spec.search_space = MagicMock()
        spec.search_space.editable = ["operators/*.py"]
        spec.search_space.frozen = []
        return spec

    def _make_gate(self) -> ContractGate:
        return ContractGate(self._make_spec())

    def _make_record(self, status: str, file: str, text: str, champ_ver: int = 0,
                     action: str = "modify", hid: str = "h1") -> HypothesisRecord:
        r = HypothesisRecord(
            hypothesis_id=hid, branch_id="b1",
            change_locus="vehicle_level", action=action,
            status=status, target_file=file,
            hypothesis_text=text,
        )
        r.base_champion_version = champ_ver
        return r

    # K6fix-1: modify same file, different text, same champion → blocked
    def test_modify_same_file_different_text_same_champion_blocked(self):
        gate = self._make_gate()
        existing = self._make_record("active", "operators/foo.py", "Approach A " * 5, champ_ver=0)
        hyp = HypothesisProposal(
            hypothesis_text="Approach B completely different idea",
            change_locus="vehicle_level",
            action="modify",
            target_file="operators/foo.py",
        )
        result = gate._c10_novelty(hyp, [existing], [], current_champion_version=0)
        assert not result.passed, "Same file modify should be blocked regardless of text"

    # K6fix-2: modify same file, different champion version → allowed (retry after promotion)
    def test_modify_same_file_different_champion_allowed(self):
        gate = self._make_gate()
        # Rejected at champion v0
        rejected = self._make_record("rejected", "operators/foo.py", "Approach A " * 5, champ_ver=0)
        hyp = HypothesisProposal(
            hypothesis_text="Approach A " * 5,
            change_locus="vehicle_level",
            action="modify",
            target_file="operators/foo.py",
        )
        # Current champion is v1 → rejected from v0 is skipped
        result = gate._c10_novelty(hyp, [], [rejected], current_champion_version=1)
        assert result.passed, f"Cross-champion modify should be allowed, got: {result.detail}"

    # K6fix-3: create_new text[:50] key still works (K6 preserved)
    def test_create_new_different_text_still_passes(self):
        gate = self._make_gate()
        existing = self._make_record("active", None, "Create operator A for subcats",
                                     action="create_new", hid="h1")
        hyp = HypothesisProposal(
            hypothesis_text="Create operator B for cost reduction totally new",
            change_locus="vehicle_level",
            action="create_new",
            target_file=None,
        )
        result = gate._c10_novelty(hyp, [existing], [], current_champion_version=0)
        assert result.passed, f"Different create_new text should pass: {result.detail}"

    def test_create_new_same_text_blocked(self):
        gate = self._make_gate()
        shared = "Create operator A for subcategory consolidation"
        existing = self._make_record("active", None, shared, action="create_new", hid="h1")
        hyp = HypothesisProposal(
            hypothesis_text=shared,
            change_locus="vehicle_level",
            action="create_new",
            target_file=None,
        )
        result = gate._c10_novelty(hyp, [existing], [], current_champion_version=0)
        assert not result.passed

    # K6fix-4: rejected + same champion_version → blocked
    def test_rejected_same_champion_version_blocked(self):
        gate = self._make_gate()
        rejected = self._make_record("rejected", "operators/foo.py", "text", champ_ver=2)
        hyp = HypothesisProposal(
            hypothesis_text="text",
            change_locus="vehicle_level",
            action="modify",
            target_file="operators/foo.py",
        )
        result = gate.validate_hypothesis(hyp, [], [], rejected_hypotheses=[rejected],
                                          current_champion_version=2)
        assert not result.passed
        assert "C10_novelty" in (result.failure_reason or "")

    # K6fix-5: rejected + different champion_version → allowed
    def test_rejected_different_champion_version_allowed(self):
        gate = self._make_gate()
        rejected = self._make_record("rejected", "operators/foo.py", "text", champ_ver=1)
        hyp = HypothesisProposal(
            hypothesis_text="text",
            change_locus="vehicle_level",
            action="modify",
            target_file="operators/foo.py",
        )
        result = gate.validate_hypothesis(hyp, [], [], rejected_hypotheses=[rejected],
                                          current_champion_version=2)
        assert result.passed, f"Cross-champion rejected should be allowed: {result.failure_reason}"

    # K6fix-6: validate_hypothesis without current_champion_version → no error
    def test_validate_hypothesis_default_champion_version_no_error(self):
        gate = self._make_gate()
        hyp = HypothesisProposal(
            hypothesis_text="A novel idea for vehicle operator",
            change_locus="vehicle_level",
            action="modify",
            target_file="operators/new.py",
        )
        result = gate.validate_hypothesis(hyp, [], [])
        assert result.passed  # no collision, sensible behaviour

    # K6fix-7: HypothesisRecord base_champion_version default is 0
    def test_hypothesis_record_default_base_champion_version(self):
        rec = HypothesisRecord(
            hypothesis_id="x", branch_id="b", change_locus="locus",
            action="modify", status="active",
        )
        assert rec.base_champion_version == 0

    # K6fix-8: HypothesisStore persists and reads back base_champion_version
    def test_hypothesis_store_persists_base_champion_version(self, tmp_path):
        from scion.lineage.registry import LineageRegistry
        from scion.lineage.branch_store import HypothesisStore

        reg = LineageRegistry(str(tmp_path / "test.db"))
        store = HypothesisStore(reg)

        rec = HypothesisRecord(
            hypothesis_id="htest", branch_id="b1",
            change_locus="vehicle_level", action="modify",
            status="active", target_file="operators/foo.py",
            hypothesis_text="some text",
        )
        rec.base_champion_version = 5
        store.save(rec)

        loaded = store.get_by_status("active")
        assert len(loaded) == 1
        assert loaded[0].base_champion_version == 5

    # K6fix-9: DB migration — old schema without base_champion_version gets column added
    def test_db_migration_adds_base_champion_version_column(self, tmp_path):
        import sqlite3 as _sqlite3
        from scion.lineage.registry import LineageRegistry

        db_path = str(tmp_path / "old.db")
        # Create table without base_champion_version (old schema)
        with _sqlite3.connect(db_path) as conn:
            conn.execute("""
                CREATE TABLE hypotheses (
                    hypothesis_id TEXT PRIMARY KEY,
                    branch_id TEXT,
                    change_locus TEXT,
                    action TEXT,
                    status TEXT,
                    target_file TEXT,
                    parent_hypothesis_id TEXT,
                    suggested_weight REAL,
                    hypothesis_text TEXT,
                    created_at TEXT
                )
            """)

        # Running LineageRegistry._init_db should migrate
        reg = LineageRegistry(db_path)

        with _sqlite3.connect(db_path) as conn:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(hypotheses)")}
        assert "base_champion_version" in cols, "Migration should add base_champion_version column"
