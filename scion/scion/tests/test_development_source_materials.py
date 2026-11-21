"""P5c B: actual execution inputs survive cleanup without becoming authority."""
from dataclasses import replace
import json
from pathlib import Path

import pytest

from scion.core.code_development import CodeDevelopmentEvaluator
from scion.core.code_research_limits import CodeResearchLimits
from scion.observation.config import PublicResearchStop
from scion.runtime.workspace import WorkspaceMaterializer
from scion.verification.development import BubblewrapDevelopmentSandbox, DevelopmentSuiteManifest
from scion.tests.test_development_test_materials import (
    ABANDON, REVISE, body, old, session,
)
from scion.tests.test_public_research_sessions import opened
from scion.tests.test_research_continuity import make_controller, read
from scion.tests.unit.test_code_development import _spec


PROBE = "from operators.main import improve\ndef test_reference():\n    assert improve(2) == 3\n"


def evaluator(tmp_path, *, sandbox=None):
    root = tmp_path / "problem"
    (root / "tests").mkdir(parents=True)
    (root / "tests/test_public.py").write_text("# HOST_SUITE_PRIVATE\ndef test_host(): assert True\n")
    (root / "support.py").write_bytes(b"# public dependency\r\nVALUE = 7\r\n")
    (root / "models.py").write_bytes(b"# public problem model\nVALUE = 9\n")
    return CodeDevelopmentEvaluator(
        materializer=WorkspaceMaterializer(str(tmp_path / "work"), editable_patterns=("operators/*.py",)),
        problem_spec=_spec(root), suites=(DevelopmentSuiteManifest(
            check_name="D3_unit_tests", source_root=str(root), test_path="tests/test_public.py"),),
        workspace_paths=("support.py",), problem_package_paths=("models.py",),
        limits=CodeResearchLimits(), **({"sandbox": sandbox} if sandbox else {}))


def callback(e, c):
    def run(patch, timeout, corpus, script):
        return e.evaluate(patch=patch, source_corpus=corpus, selected_surface=None,
            total_timeout_sec=timeout, falsifier_source=script,
            capture_source=c.capture_development_source).provider_projection()
    return run


def run_test(c, e, script=PROBE):
    runner, creative = session(c, [REVISE, {"action": "test_patch", "falsifier_source": script}, ABANDON],
                               callback=callback(e, c))
    runner.run(old._snapshot())
    return runner, creative


def tree_bytes(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts}


def test_q08_actual_stage_bytes_survive_cleanup_and_private_paths_are_not_visible(tmp_path):
    c = opened(make_controller(tmp_path / "materials"), "code")
    snapshots, workspaces = {}, []
    class RecordingSandbox(BubblewrapDevelopmentSandbox):
        def check(self, kwargs, stage):
            root = Path(kwargs["workspace"])
            workspaces.append(root)
            snapshots[stage] = tree_bytes(root)
            directory = Path(c.development_tests.pending["request_ref"]).parent
            saved = c.service.materials.root / ("private-" + str(directory)) / stage / "tree"
            assert tree_bytes(saved) == snapshots[stage]
        def run_probe(self, **kwargs):
            self.check(kwargs, "probe")
            return super().run_probe(**kwargs)
        def run_pytest(self, **kwargs):
            self.check(kwargs, "host_checks")
            return super().run_pytest(**kwargs)
    e = evaluator(tmp_path, sandbox=RecordingSandbox())
    run_test(c, e)
    result = body(c)
    assert result["feedback"]["outcome"] == result["feedback"]["falsifier_outcome"] == "passed"
    assert all(not p.exists() for p in workspaces)
    directory = Path(result["request_ref"]).parent
    for stage, actual in snapshots.items():
        saved = c.service.materials.root / ("private-" + str(directory)) / stage / "tree"
        assert tree_bytes(saved) == actual
    assert len(result["tested_source_refs"]) == 2
    for ref in result["tested_source_refs"]:
        source = json.loads(read(c, ref))
        assert source["capture_state"] == "captured_before_execution"
        assert source["source_kind"] == "development_draft"
        for f in source["files"]:
            path = f["path"] if f["location"] == "workspace" else ".scion-development-problems/generic_subject/" + f["path"]
            assert read(c, f["ref"]) == snapshots[source["stage"]][path]
            assert f["path"] != "tests/test_public.py"
        assert str(tmp_path) not in read(c, ref).decode()
    private = next(c.service.materials.root.glob("private-development-tests/**/*.json"))
    denied = c.execute({"action": "read_research", "ref": str(private.relative_to(c.service.materials.root)), "offset": 0, "length": 100})
    assert denied["reason_code"] == "REF_NOT_VISIBLE"
    assert not any("HOST_SUITE_PRIVATE" in read(c, ref).decode() for ref in c.visible)
    assert c.service.usage["started_subjects"] == c.service.usage["started_checkers"] == 0


@pytest.mark.parametrize("location", ["algorithm", "workspace", "problem"])
def test_q08_absolute_formal_aliases_after_copy_are_rejected_before_execution(tmp_path, location):
    c = opened(make_controller(tmp_path / "materials"), "code")
    e = evaluator(tmp_path)
    root = Path(e.problem_spec.root_dir)
    forbidden = (Path(c.source_root) / "operators/main.py" if location == "algorithm"
                 else root / ("support.py" if location == "workspace" else "models.py"))
    c.controller.configuration_files = (*c.controller.configuration_files, str(forbidden))
    with pytest.raises(PublicResearchStop, match="PUBLIC_CLOSURE_INVALID"):
        run_test(c, e)
    assert not c.development_tests.pending["source_refs"]
    assert not list(c.service.materials.root.glob("development-tests/**/source.json"))


@pytest.mark.parametrize("fault", ["missing", "symlink", "hardlink", "storage", "write", "index"])
def test_q08_capture_fault_stops_execution_without_reconstruction(tmp_path, monkeypatch, fault):
    c = opened(make_controller(tmp_path / "materials"), "code")
    e = evaluator(tmp_path)
    original = c.capture_development_source
    def fail_capture(**kwargs):
        path = Path(kwargs["workspace"]) / "operators/main.py"
        if fault in {"missing", "symlink", "hardlink"}:
            path.unlink()
            if fault == "symlink": path.symlink_to(Path(e.problem_spec.root_dir) / "support.py")
            if fault == "hardlink": path.hardlink_to(Path(e.problem_spec.root_dir) / "support.py")
        elif fault == "storage":
            c.service.budget = replace(c.service.budget, max_storage_bytes=c.service.materials.used_bytes() + 1)
        elif fault == "write":
            real = c.service._bytes
            def broken(path, raw):
                if path.name == "source.json": raise OSError("disk failure")
                return real(path, raw)
            monkeypatch.setattr(c.service, "_bytes", broken)
        elif fault == "index":
            monkeypatch.setattr(c, "persist_index", lambda: (_ for _ in ()).throw(OSError("index failure")))
        return original(**kwargs)
    monkeypatch.setattr(c, "capture_development_source", fail_capture)
    monkeypatch.setattr(e.sandbox, "run_probe", lambda **_: pytest.fail("must not execute after capture failure"))
    with pytest.raises(PublicResearchStop): run_test(c, e)
    assert not c.development_tests.pending["source_refs"]
    assert not any("/source/" in r or r.endswith("/source.json") for r in c.visible)


def test_q08_later_stage_failure_keeps_completed_probe_source(tmp_path, monkeypatch):
    c = opened(make_controller(tmp_path / "materials"), "code")
    e = evaluator(tmp_path)
    original = c.service._bytes
    def fail(path, raw):
        if path.name == "source.json" and "host_checks" in path.parts:
            raise OSError("second stage persistence failure")
        return original(path, raw)
    monkeypatch.setattr(c.service, "_bytes", fail)
    monkeypatch.setattr(e.sandbox, "run_pytest", lambda **_: pytest.fail("host checks must not start"))
    with pytest.raises(PublicResearchStop): run_test(c, e)
    refs = c.development_tests.pending["source_refs"]
    assert len(refs) == 1 and "/probe/" in refs[0]
    assert (c.service.materials.root / refs[0]).is_file()
    assert not any("/host_checks/" in r for r in c.visible)
    c.close()
    assert any(row.get("origin_ref") == refs[0] for row in c.controller.continuity.rows)


def test_q08_capture_time_consumes_existing_test_deadline(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from scion.core import code_development
    c = opened(make_controller(tmp_path / "materials"), "code")
    e = evaluator(tmp_path)
    now = [100.0]
    monkeypatch.setattr(code_development, "time", SimpleNamespace(monotonic=lambda: now[0]))
    original = c.capture_development_source
    def slow(**kwargs):
        ref = original(**kwargs)
        now[0] += 1000
        return ref
    monkeypatch.setattr(c, "capture_development_source", slow)
    monkeypatch.setattr(e.sandbox, "run_probe", lambda **_: pytest.fail("deadline is exhausted"))
    run_test(c, e)
    result = body(c)
    assert result["feedback"]["outcome"] == "timeout"
    assert len(result["tested_source_refs"]) == 1
    assert json.loads(read(c, result["tested_source_refs"][0]))["capture_state"] == "captured_before_execution"


def test_q08_preflight_rejection_retains_request_without_fabricating_source(tmp_path, monkeypatch):
    from scion.core import code_development
    from scion.verification.development import DevelopmentCheckObservation
    c = opened(make_controller(tmp_path / "materials"), "code")
    e = evaluator(tmp_path)
    monkeypatch.setattr(code_development, "development_safety_preflight_failure", lambda **_:
        DevelopmentCheckObservation(name="D0_preflight", outcome="preflight_rejected", reason_code="source_frozen"))
    monkeypatch.setattr(c, "capture_development_source", lambda **_: pytest.fail("preflight rejected"))
    run_test(c, e)
    result = body(c)
    assert result["feedback"]["outcome"] == "preflight_rejected"
    assert result["capture_scope"] == "request_only" and result["tested_source_refs"] == []
    assert not (c.service.materials.root / "private-development-tests").exists()


@pytest.mark.parametrize("kind,script", [
    ("wrong_reference", PROBE.replace("== 3", "== 4")),
    ("algorithm_bug", PROBE.replace("== 3", "== 2")),
    ("scope_mismatch", "from operators.main import improve\ndef test_scope():\n"
     "    calls = []\n    def observed(x):\n        calls.append(x)\n        return improve(x)\n"
     "    improve(2)\n    assert len(calls) == 1\n"),
])
def test_q09_real_failures_explanation_and_weaker_pass_do_not_clear_veto(tmp_path, kind, script):
    c = opened(make_controller(tmp_path / "materials"), "code")
    e = evaluator(tmp_path)
    def review(_):
        assert body(c)["feedback"]["falsifier_outcome"] == "failed"
        ref = body(c, "request.json")["script_ref"]
        return {"action": "read_research", "ref": ref, "offset": 0, "length": 65536}
    runner, creative = session(c, [REVISE, {"action": "test_patch", "falsifier_source": script}, review,
        {"action": "write_research", "kind": "note", "content": "Revised explanation: " + kind},
        {"action": "test_patch", "falsifier_source": PROBE}, {"action": "ready"}, ABANDON],
        callback=callback(e, c))
    runner.run(old._snapshot())
    assert body(c, number=2)["feedback"]["falsifier_outcome"] == "passed"
    assert "latest_draft_falsifier_failed" in json.dumps(creative.snapshots[-1].structured_context)
    assert "frozen_ready_patch" not in creative.snapshots[-1].structured_context["code_research"]
    assert read(c, body(c, "request.json")["script_ref"]) == script.encode()
    assert len(body(c)["tested_source_refs"]) == 2


def test_q10_closed_attempt_and_fresh_import_retain_exact_source_and_missing_dependencies(tmp_path):
    ctrl = make_controller(tmp_path / "first")
    c = opened(ctrl, "code")
    run_test(c, evaluator(tmp_path), PROBE.replace("== 3", "== 4"))
    result, request = body(c), body(c, "request.json")
    result_ref = next(ref for ref in c.visible if ref.endswith("/result.json"))
    result_raw = read(c, result_ref)
    source_ref = result["tested_source_refs"][0]
    source_raw = read(c, source_ref)
    file_ref = json.loads(source_raw)["files"][0]["ref"]
    file_raw = read(c, file_ref)
    c.close()
    h = opened(ctrl)
    def imported_ref(s, ref):
        return next(e["ref"] for e in s.entries if e.get("origin_ref") == ref or
                    any(o["ref"] == ref for o in e.get("reference_origins", [])))
    assert read(h, imported_ref(h, source_ref)) == source_raw
    assert read(h, imported_ref(h, file_ref)) == file_raw
    assert read(h, imported_ref(h, result_ref)) == result_raw
    assert read(h, imported_ref(h, request["script_ref"])) == PROBE.replace("== 3", "== 4").encode()
    # Deleting an exported dependency must not cause reconstruction from patch
    # or from the fresh campaign's entirely independent executable source root.
    export = ctrl.continuity.root
    rows = json.loads((export / "index.json").read_bytes())["entries"]
    missing = next(row for row in rows if row.get("origin_ref") == file_ref)
    (export / missing["ref"]).unlink()
    fresh = make_controller(tmp_path / "fresh", imports=(str(export),))
    current_before = tree_bytes(Path(fresh.source_roots[-1]))
    f = opened(fresh)
    assert read(f, imported_ref(f, source_ref)) == source_raw
    assert read(f, imported_ref(f, result_ref)) == result_raw
    assert read(f, imported_ref(f, request["script_ref"])) == PROBE.replace("== 3", "== 4").encode()
    assert json.loads(source_raw)["source_condition"] == request["source_condition"]
    assert json.loads(read(f, imported_ref(f, result["request_ref"])))["capture_scope"] == "request_only"
    record = next(row for row in f.entries if row["ref"] == imported_ref(f, source_ref))
    assert record["source_availability"] == "projection_only" and record["missing_dependencies"]
    missing_read = f.execute({"action": "read_research", "ref": imported_ref(f, file_ref), "offset": 0, "length": 100})
    assert missing_read["reason_code"] == "MATERIAL_UNAVAILABLE"
    assert tree_bytes(Path(fresh.source_roots[-1])) == current_before
    assert fresh.service.usage["started_subjects"] == 0
    assert not (fresh.service.materials.root / "private-development-tests").exists()
