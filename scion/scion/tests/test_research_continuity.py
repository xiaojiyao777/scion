"""P4: material bytes survive attempts; source/state authority does not move."""
import base64
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from scion.core.code_research_limits import CodeResearchLimits
from scion.core.execution_outcome import ExecutionOutcome
from scion.observation.config import PublicResearchConfig, PublicResearchStop
from scion.observation.controller import compose_public_research
from scion.observation.source import ObservationError, SourceCopier
from scion.problem.loader import load_problem_adapter
from scion.runtime.workspace import WorkspaceMaterializer
from scion.tests.test_public_research_sessions import hypothesis, opened, note, observe
from scion.tests.test_observation_execution import CVRP, WAREHOUSE, budget
from scion.tests.test_cvrp_direct_outer_smoke import _problem_v1


def make_controller(tmp_path, *, observation=True, materials=True, imports=(), warehouse=False, limits=None):
    from scion.tests.test_warehouse_direct_outer_smoke import _problem_v1 as warehouse_spec
    adapter = load_problem_adapter(warehouse_spec() if warehouse else _problem_v1())
    source = tmp_path / "source"
    source.mkdir(parents=True)
    provider = adapter.public_observation_provider()
    spec = provider.describe()
    copier = SourceCopier(forbidden_files=(), max_bytes=10**7, max_files=1000)
    root = WAREHOUSE if warehouse else CVRP
    for name in spec.subject_workspace_paths:
        copier.copy(root, name, source)
    for name in spec.subject_optional_workspace_paths:
        copier.copy(root, name, source, optional=True)
    (source / "operator-only.txt").write_text("not in public source projection")
    cfg = PublicResearchConfig(observation, materials,
        (limits or budget(max_read_bytes=65536)) if observation or materials else None)
    return compose_public_research(configuration=cfg, adapter=adapter, problem_spec=adapter.spec,
        split_manifest=SimpleNamespace(), source_root=source, initial_source_root=source,
        output_root=tmp_path / "research", code_research_limits=CodeResearchLimits(),
        materializer=WorkspaceMaterializer(str(tmp_path / "workspaces")), research_material_imports=imports)


def read(session, ref, length=65536):
    result = session.execute({"action": "read_research", "ref": ref, "offset": 0, "length": length})
    assert result["ok"], result
    return base64.b64decode(result["data"])


@pytest.mark.parametrize("observation,materials", [(False, False), (True, False), (False, True), (True, True)])
def test_switches_are_independent(tmp_path, observation, materials):
    ctrl = make_controller(tmp_path, observation=observation, materials=materials)
    if not (observation or materials):
        assert ctrl is None
        return
    first = opened(ctrl)
    result = note(first, "negative evidence")
    if not observation:
        assert first.execute(observe(first))["reason_code"] == "REQUEST_INVALID"
        assert ctrl.service.usage["started_subjects"] == 0
    first.close()
    second = opened(ctrl)
    visible = [e for e in second.entries if e.get("origin_ref") == result["ref"]]
    assert bool(visible) == materials
    if visible:
        assert read(second, visible[0]["ref"]) == b"negative evidence"


def test_old_h_and_c_materials_are_h_only_and_revisions_keep_bytes(tmp_path):
    ctrl = make_controller(tmp_path)
    h = opened(ctrl)
    old = note(h, "first explanation")
    handoff = h.freeze_handoff(hypothesis(), [])
    h.close()
    c = opened(ctrl, "code", handoff=handoff)
    assert c.execute({"action": "read_research", "ref": old["ref"], "offset": 0, "length": 64})["reason_code"] == "REF_NOT_VISIBLE"
    negative = note(c, "draft has a counterexample")
    c.close()
    fresh = opened(ctrl)
    originals = {e.get("origin_ref"): e for e in fresh.entries}
    assert read(fresh, originals[negative["ref"]]["ref"]) == b"draft has a counterexample"
    original = originals[old["ref"]]
    revised = note(fresh, "revised explanation", supersedes_ref=original["ref"])
    assert read(fresh, original["ref"]) == b"first explanation"
    with pytest.raises(ObservationError, match="REF_NOT_VISIBLE"):
        fresh.freeze_handoff(hypothesis(), [original["ref"]])
    fresh.close()
    again = opened(ctrl)
    new_entry = next(e for e in again.entries if e.get("origin_ref") == revised["ref"])
    assert read(again, new_entry["ref"]) == b"revised explanation"
    assert new_entry["supersedes_ref"] in again.visible


@pytest.mark.parametrize("warehouse", [False, True])
def test_real_observation_dependencies_survive_close_and_import(tmp_path, warehouse):
    ctrl = make_controller(tmp_path / "old", warehouse=warehouse)
    h = opened(ctrl)
    request = observe(h)
    if warehouse:
        request["public_args"]["max_iterations"] = 2
    result = h.execute(request)
    assert result["data"] == "valid"
    h.close()
    new = make_controller(tmp_path / "new", imports=[ctrl.continuity.root], warehouse=warehouse)
    fresh = opened(new)
    entry = next(e for e in fresh.entries if e["kind"] == "observation")
    body = json.loads(read(fresh, entry["ref"]))
    assert body["source_condition"] == result["source_condition"]
    assert entry["dependencies"] and not entry["missing_dependencies"]
    assert all(dep in fresh.visible for dep in entry["dependencies"])
    assert new.service.usage["started_subjects"] == 0
    assert entry["source_condition"]["source_ref"].startswith("import-000001/")
    source_entries = [e for e in fresh.entries if e["kind"] == "source"]
    assert source_entries and all("operator-only.txt" not in e.get("source_path", "") for e in source_entries)


def bundle(path, *, content=b"promotion is merely a claim", ref="files/same.note", dependencies=None):
    (path / "files").mkdir(parents=True)
    (path / ref).write_bytes(content)
    entry = {"ref": ref, "kind": "note", "bytes": len(content), "phase": "hypothesis",
             "source_condition": {"role": "current", "source_ref": "old-base"},
             "dependencies": dependencies or []}
    value = {"schema_version": 1, "entries": [entry]}
    (path / "index.json").write_text(json.dumps(value))
    return value


def test_same_names_are_separate_copies_and_missing_dependencies_remain(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    bundle(a, content=b"first", dependencies=["files/missing.py"])
    bundle(b, content=b"second")
    ctrl = make_controller(tmp_path / "new", imports=[a, b])
    shutil.rmtree(a); shutil.rmtree(b)
    h = opened(ctrl)
    notes = [e for e in h.entries if e["kind"] == "note"]
    assert len(notes) == 2 and notes[0]["ref"] != notes[1]["ref"]
    assert [read(h, e["ref"]) for e in notes] == [b"first", b"second"]
    assert notes[0]["missing_dependencies"] and not notes[1]["missing_dependencies"]
    assert notes[0]["origin_scope"] != notes[1]["origin_scope"]


def test_missing_material_is_indexed_without_current_source_substitution(tmp_path):
    directory = tmp_path / "bundle"; bundle(directory)
    (directory / "files/same.note").unlink()
    ctrl = make_controller(tmp_path / "new", imports=[directory])
    h = opened(ctrl)
    entry = next(e for e in h.entries if e["kind"] == "note")
    assert entry["availability"] == "unavailable"
    assert h.execute({"action": "read_research", "ref": entry["ref"], "offset": 0, "length": 32})["reason_code"] == "MATERIAL_UNAVAILABLE"


@pytest.mark.parametrize("mutation", ["traversal", "duplicate", "private_metadata", "unknown_version", "size", "symlink", "hardlink"])
def test_invalid_import_fails_before_dispatch(tmp_path, mutation):
    directory = tmp_path / "bundle"; value = bundle(directory)
    entry = value["entries"][0]
    if mutation == "traversal": entry["ref"] = "../private"
    elif mutation == "duplicate": value["entries"].append(deepcopy(entry))
    elif mutation == "private_metadata": entry["source_condition"]["validation"] = "secret"
    elif mutation == "unknown_version": value["schema_version"] = 2
    elif mutation == "size": entry["bytes"] += 1
    else:
        target = directory / "files/same.note"
        sibling = directory / "original"; target.rename(sibling)
        if mutation == "symlink": target.symlink_to(sibling)
        else: target.hardlink_to(sibling)
    (directory / "index.json").write_text(json.dumps(value))
    with pytest.raises(PublicResearchStop) as error:
        make_controller(tmp_path / "new", imports=[directory])
    assert error.value.record.reason_code in {"MATERIAL_IMPORT_INVALID", "PUBLIC_CLOSURE_INVALID"}


def test_import_requires_m_and_does_not_implicitly_enable_it(tmp_path):
    with pytest.raises(PublicResearchStop, match="OBS_CONFIG_INVALID"):
        make_controller(tmp_path, materials=False, imports=["not-read"])


def test_complete_source_saved_separately_and_old_conditions_do_not_change(tmp_path):
    ctrl = make_controller(tmp_path)
    original_root = ctrl.source_roots[-1]
    h = opened(ctrl); old = note(h); h.close()
    next_root = tmp_path / "changed"; shutil.copytree(original_root, next_root)
    path = next_root / "policies/baseline_algorithm.py"
    old_bytes = path.read_bytes(); path.write_bytes(old_bytes + b"\n# changed complete source\n")
    fresh = ctrl.open_session(phase="hypothesis", source_root=next_root, branch="sibling")
    entry = next(e for e in fresh.entries if e.get("origin_ref") == old["ref"])
    assert entry["source_condition"] != fresh.source_condition
    saved = ctrl.service.materials.root / "retained_sources" / entry["source_condition"]["source_ref"] / "tree"
    assert (saved / "operator-only.txt").read_text() == "not in public source projection"
    assert (saved / "policies/baseline_algorithm.py").read_bytes() == old_bytes
    assert all(e.get("source_path") != "operator-only.txt" for e in fresh.entries)
    assert original_root != next_root and original_root.exists()


def test_close_persistence_failure_preserves_bytes_and_blocks_next_dispatch(tmp_path, monkeypatch):
    ctrl = make_controller(tmp_path); h = opened(ctrl); saved = note(h)
    monkeypatch.setattr(ctrl.continuity, "_save", lambda rows: (_ for _ in ()).throw(OSError("disk")))
    h.close()
    assert h.closed and (ctrl.service.materials.root / saved["ref"]).is_file()
    with pytest.raises(PublicResearchStop) as error: opened(ctrl)
    assert error.value.record.outcome is ExecutionOutcome.BLOCKED_INFRA


def test_retention_failure_is_non_reversing_and_typed(tmp_path, monkeypatch):
    ctrl = make_controller(tmp_path)
    def fail(*args, **kwargs): raise OSError("disk")
    monkeypatch.setattr(ctrl.continuity, "retain_source", fail)
    assert not ctrl.retain_before_cleanup(ctrl.source_roots[-1], "branch", "previous_head")
    assert ctrl.source_roots[-1].exists()
    assert ctrl.failure_reason == "PERSISTENCE_ERROR"
    with pytest.raises(PublicResearchStop): opened(ctrl)


@pytest.mark.parametrize("failure,abandon", [(False, False), (True, False), (True, True)])
def test_decision_keeps_its_result_and_retains_before_cleanup(tmp_path, monkeypatch, failure, abandon):
    from scion.tests.unit.core.test_decision_finalizer_lifecycle import _fixture, _screening_protocol
    from scion.core.models import Decision, CanaryResult, ContractResult, VerificationResult, ChampionState, BranchState
    from scion.core.workspace_service import WorkspaceService, CandidateWorkspace
    import threading
    ctrl = make_controller(tmp_path)
    fixture = _fixture()
    finalizer, branches, branch, h = fixture[:4]
    parent = ctrl.materializer.create_candidate_workspace(str(ctrl.source_roots[-1]))
    candidate = ctrl.materializer.create_candidate_workspace(parent)
    target = Path(candidate) / "policies/baseline_algorithm.py"
    target.write_bytes(target.read_bytes() + b"\n# next exact algorithm\n")
    workspaces = {branch.branch_id: parent}
    workspace = WorkspaceService(ctrl.materializer, branches, workspaces, threading.Lock(),
        lambda: ChampionState(version=1, operator_pool={}, code_snapshot_path=str(ctrl.source_roots[-1])),
        retain_source=ctrl.retain_before_cleanup)
    finalizer.accept_candidate = workspace.accept_candidate
    finalizer.reject_candidate = workspace.reject_candidate
    finalizer.discard_branch_workspace = workspace.discard_branch_workspace
    if failure:
        def fail(*args, **kwargs): raise OSError("disk unavailable")
        monkeypatch.setattr(ctrl.continuity, "retain_source", fail)
    decision = Decision.ABANDON if abandon else Decision.CONTINUE_EXPLORE
    result = finalizer.apply(branch=branch, decision=decision, hypothesis=h,
        protocol_result=_screening_protocol("fail"), canary_result=CanaryResult(passed=True),
        contract_result=ContractResult(passed=True, checks=()), verification_result=VerificationResult(passed=True, checks=()),
        action_label="explore", patch=fixture[7],
        candidate=CandidateWorkspace(workspace=candidate, source_digest="candidate"))
    assert result.decision is decision
    assert branch.state is (BranchState.ABANDONED if abandon else BranchState.EXPLORE)
    if not abandon:
        assert workspaces[branch.branch_id] == candidate and branch.current_code_hash == "candidate"
    if failure:
        assert Path(parent).exists() and ctrl.failure_reason == "PERSISTENCE_ERROR"
        assert result.failure_stage is None
    else:
        assert not Path(parent).exists()
        condition = ctrl.continuity.sources[str(Path(parent).absolute())]
        saved = ctrl.service.materials.root / "retained_sources" / condition["source_ref"] / "tree"
        assert (saved / "operator-only.txt").is_file()
        assert b"next exact algorithm" not in (saved / "policies/baseline_algorithm.py").read_bytes()


def test_real_bounded_h_abstains_then_next_h_reads_prior_material(tmp_path):
    from scion.tests.unit.core.proposal_pipeline_test_support import _pipeline
    from scion.tests.unit.proposal.test_hypothesis_research_session import _context
    from scion.core.models import ChampionState
    class Script:
        def __init__(self): self.calls = 0; self.seen = []
        def call_hypothesis_research_turn(self, snapshot):
            self.seen.append(snapshot.structured_context)
            self.calls += 1
            if self.calls == 1:
                return {"action": "write_research", "kind": "note", "content": "counterexample requires a different explanation"}
            if self.calls == 3:
                prior = next(e for e in snapshot.structured_context["research_material_index"] if e["kind"] == "note")
                return {"action": "read_research", "ref": prior["ref"], "offset": 0, "length": 65536}
            return {"action": "abstain", "reason": "continue investigation in a fresh attempt"}
    creative = Script(); pipeline, branch, runtime, _ = _pipeline(creative=creative)
    ctrl = make_controller(tmp_path)
    pipeline.public_research = ctrl
    pipeline.branch_workspaces.clear()
    pipeline.code_research_limits = CodeResearchLimits()
    pipeline.get_champion = lambda: ChampionState(version=1, operator_pool={}, code_snapshot_path=str(ctrl.source_roots[-1]))
    runtime.build_hypothesis_context = lambda **kw: _context(include_history=False)
    runtime.hypothesis_research_public_sources = lambda: ()
    runtime.hypothesis_research_source_prefixes = lambda: ()
    for _ in range(2):
        result = pipeline.generate_hypothesis(branch)
        assert result.execution_outcome.outcome is ExecutionOutcome.RESEARCH_REJECTED
    assert creative.calls == 4
    data = creative.seen[-1]["public_observation"]["tool_results"][0]
    assert base64.b64decode(data["data"]) == b"counterexample requires a different explanation"


@pytest.mark.parametrize("error,reason,outcome", [
    (OSError("disk"), "PERSISTENCE_ERROR", ExecutionOutcome.BLOCKED_INFRA),
    (KeyboardInterrupt(), "USER_INTERRUPTED", ExecutionOutcome.INTERRUPTED),
    (RuntimeError("bug"), "INTERNAL_ERROR", ExecutionOutcome.NOT_EVALUATED),
    (ObservationError("LIMIT_NOT_AVAILABLE"), "GLOBAL_RESEARCH_LIMIT", ExecutionOutcome.RESOURCE_EXHAUSTED),
])
def test_retention_failure_lanes_are_preserved(tmp_path, monkeypatch, error, reason, outcome):
    ctrl = make_controller(tmp_path)
    def fail(*args, **kwargs): raise error
    monkeypatch.setattr(ctrl.continuity, "retain_source", fail)
    assert not ctrl.retain_before_cleanup(ctrl.source_roots[-1], "branch", "previous")
    with pytest.raises(PublicResearchStop) as stopped: opened(ctrl)
    assert stopped.value.record.reason_code == reason and stopped.value.record.outcome is outcome


def test_export_import_twice_keeps_original_reference_context(tmp_path):
    old = make_controller(tmp_path / "old")
    h = opened(old); made = note(h); h.close()
    middle = make_controller(tmp_path / "middle", imports=[old.continuity.root])
    final = make_controller(tmp_path / "final", imports=[middle.continuity.root])
    entry = next(e for e in opened(final).entries if e["kind"] == "note")
    assert entry["origin_ref"] == made["ref"]
    assert entry["origin_scope"].endswith("session-000001")
    assert entry["source_condition"]["source_ref"].count("import-") == 2


def test_deleted_complete_tree_is_unavailable_without_reconstructing_it(tmp_path):
    ctrl = make_controller(tmp_path)
    h = opened(ctrl); made = note(h); h.close()
    label = h.source_condition["source_ref"]
    saved = ctrl.service.materials.root / "retained_sources" / label / "tree"
    shutil.rmtree(saved)
    entries = ctrl.continuity.visible_entries()
    entry = next(e for e in entries if e.get("origin_ref") == made["ref"])
    assert entry["source_availability"] == "unavailable"
    assert (ctrl.service.materials.root / entry["ref"]).read_bytes() == b"A measured question"
    with pytest.raises(PublicResearchStop, match="SOURCE_UNAVAILABLE"): opened(ctrl)
    assert not saved.exists()


def test_imported_source_is_only_a_public_projection(tmp_path):
    old = make_controller(tmp_path / "old"); h = opened(old); note(h); h.close()
    new = make_controller(tmp_path / "new", imports=[old.continuity.root])
    fresh = opened(new)
    imported = [e for e in fresh.entries if e.get("origin_scope", "").startswith("import-")]
    assert imported and all(e["source_availability"] == "projection_only" for e in imported)
    assert fresh.source_condition["source_ref"] == "retained-000001"


def test_m_only_schema_and_detached_projection(tmp_path):
    from scion.tests.unit.proposal.test_hypothesis_research_session import _snapshot
    ctrl = make_controller(tmp_path, observation=False); h = opened(ctrl)
    from scion.proposal.hypothesis_research_session import bind_hypothesis_research_turn_tool
    base = _snapshot(include_history=False)
    snapshot = h.augment(replace(base, provider_tool=bind_hypothesis_research_turn_tool(base.provider_tool)))
    actions = [s["properties"]["action"]["enum"][0] for s in snapshot.provider_tool["input_schema"]["oneOf"]]
    assert "observe" not in actions and "write_research" in actions
    original = deepcopy(snapshot.structured_context)
    note(h); h.close(); opened(ctrl)
    assert snapshot.structured_context == original
    assert snapshot.structured_context["public_observation"]["materials_enabled"] is True


def test_storage_and_source_limits_stop_without_deleting_materials(tmp_path):
    ctrl = make_controller(tmp_path)
    h = opened(ctrl); saved = note(h)
    ctrl.service.materials.max_storage_bytes = ctrl.service.materials.used_bytes()
    with pytest.raises(PublicResearchStop) as error:
        note(h, "cannot fit")
    assert error.value.record.outcome is ExecutionOutcome.RESOURCE_EXHAUSTED
    assert (ctrl.service.materials.root / saved["ref"]).read_bytes() == b"A measured question"
    with pytest.raises(PublicResearchStop) as error:
        make_controller(tmp_path / "bounded", limits=budget(max_source_bytes=1))
    assert error.value.record.outcome is ExecutionOutcome.RESOURCE_EXHAUSTED


def test_imported_non_utf8_script_is_action_feedback_not_terminal(tmp_path):
    from dataclasses import asdict
    from scion.tests.test_observation_execution import RUN
    directory = tmp_path / "bundle"
    value = bundle(directory, content=b"\xff\xfe")
    value["entries"][0]["kind"] = "script"
    (directory / "index.json").write_text(json.dumps(value))
    ctrl = make_controller(tmp_path / "new", imports=[directory])
    h = opened(ctrl)
    script = next(e for e in h.entries if e["kind"] == "script")
    limits = asdict(RUN); limits.pop("scratch_bytes")
    result = h.execute({"action": "observe", "mode": "analysis", "script_ref": script["ref"],
        "input_refs": [], "limits": limits})
    assert result["reason_code"] == "INPUT_INVALID" and not result["ok"]
    assert ctrl.service.usage["started_analyses"] == 0
    assert note(h, "revise the invalid script")["ok"]
    assert read(h, script["ref"]) == b"\xff\xfe"
