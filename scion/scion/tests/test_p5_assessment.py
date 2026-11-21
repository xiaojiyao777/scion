"""P5 offline engineering checks; these are not real-agent E2 evidence."""
from copy import deepcopy
import importlib.util
import json
import math
from pathlib import Path

import pytest

from scion.core.code_research_limits import load_code_research_limits
from scion.core.research_input import normalize_research_input
from scion.core.resource_envelope import normalize_resource_envelope
from scion.observation.config import load_public_research
from scion.observation.sandbox import ObservationSandbox, RunLimits
from scion.observation.service import ObservationService
from scion.observation.source import SourceBinding, SourceCopier, prepare_source
from scion.problems.cvrp.public_observation import CvrpPublicObservationProvider
from scion.problems.warehouse_delivery.public_observation import WarehousePublicObservationProvider

REPO = Path(__file__).resolve().parents[3]
FRAMEWORK = REPO / "scion/scion"
spec = importlib.util.spec_from_file_location("p5_assessment", REPO / "scion/tools/p5_assessment.py")
p5 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p5)


def problem_parts(problem):
    if problem == "cvrp":
        return CvrpPublicObservationProvider(), FRAMEWORK / "problems/cvrp", {}
    root = REPO / "surrogate"
    return WarehousePublicObservationProvider(), root, {
        "operator_selection": "registry" if (root / "registry.yaml").exists() else "defaults"}


CASES = [(problem, n, side) for problem in ("cvrp", "warehouse") for n in range(3) for side in range(2)]


@pytest.mark.parametrize("problem,n,side", CASES)
def test_reference_answers_in_real_isolated_checker(tmp_path, problem, n, side):
    provider, root, config = problem_parts(problem)
    task = p5.load(p5.DATA / problem / "public/tasks.json")[n]
    answer = p5.load(p5.DATA / problem / "evaluator/answers.json")[n]
    assert task["task_id"] == answer["task_id"]
    example = task["research_input"]["observations"][0]
    provider.validate_input(example["instance"])
    # Only frozen checker and exact public closure; never import candidate on host.
    prepared = tmp_path / "prepared"
    prepare_source(binding=SourceBinding(root, "current", "initial", config),
        problem_root=root, framework_root=FRAMEWORK, spec=provider.describe(),
        destination=prepared, copier=SourceCopier(forbidden_files=(), max_files=4000, max_bytes=64*1024**2))
    assert not any("evaluator" in str(p) or "p5_assessment" in str(p) for p in prepared.rglob("*"))
    inputs, empty = tmp_path / "inputs", tmp_path / "empty"
    inputs.mkdir(); empty.mkdir()
    (inputs / "request.json").write_text(json.dumps({"instance":example["instance"],
        "solution":example["sample_solutions"][side]}))
    result = ObservationSandbox().run(subject=empty, runtime=prepared / "checker", inputs=inputs,
        module=provider.describe().checker_module, mode="subject",
        limits=RunLimits(3, 2, 256*1024**2, 65536, 1024**2),
        dependencies=provider.describe().checker_dependencies)
    assert result.reason_code == "COMPLETED", result.stderr
    checked = json.loads(result.result)
    assert {key: checked[key] for key in answer["checks"][side]} == answer["checks"][side]
    assert result.started and result.cpu_seconds > 0


@pytest.mark.parametrize("problem", ["cvrp", "warehouse"])
def test_public_diagnostic_runs_complete_solver(tmp_path, problem):
    provider, root, config = problem_parts(problem)
    budget = load_public_research(p5.DATA / "config/diagnostic-public-research.json").budget
    svc = ObservationService(provider=provider, problem_root=root, framework_root=FRAMEWORK,
        output_root=tmp_path / "records", forbidden_files=(), budget=budget)
    example = p5.load(p5.DATA / problem / "public/tasks.json")[0]["research_input"]["observations"][0]
    args = {"time_limit_sec":0.05}
    if problem == "warehouse":
        args["max_iterations"] = 1
    result = svc.observe(binding=SourceBinding(root, "current", "initial", config),
        raw_input=json.dumps(example["instance"]).encode(), public_args=args, seed=17,
        limits=budget.per_action)
    assert result["data"] == "valid", result
    assert result["check"]["feasibility"] == "pass"
    assert svc.usage["started_subjects"] == svc.usage["started_checkers"] == 1


@pytest.mark.parametrize("task", [f"{p}-{n:02}" for p in ("cvrp", "warehouse") for n in range(1,4)])
def test_export_only_public_research_input(task, monkeypatch):
    original = p5.load
    def public_only(path):
        assert "/public/" in str(path)
        return original(path)
    monkeypatch.setattr(p5, "load", public_only)
    value = p5.export_task(task)
    assert normalize_research_input(value) == value
    assert value["observations"] == []
    assert "sample_solutions" in value["current_question"]
    assert "recomputed_objective" not in value["current_question"]


def test_export_unknown_and_no_overwrite(tmp_path):
    with pytest.raises(ValueError):
        p5.export_task("../evaluator/answers.json")
    path = tmp_path / "task.json"
    p5.write_new(path, p5.export_task("cvrp-01"))
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        p5.write_new(path, {})
    assert path.read_bytes() == original


def test_resource_configs_and_plan():
    runs = p5.plan()
    assert len(runs) == 8 and len({r["run_id"] for r in runs}) == 8
    totals = [0,0,0,0]
    for run in runs:
        kind = run["kind"]
        config = load_public_research(p5.DATA / f"config/{kind}-public-research.json")
        execution = p5.load(p5.DATA / f"config/{kind}-run.json")
        envelope = normalize_resource_envelope(execution["resource_envelope"])
        assert config.public_observation_enabled and config.research_materials_enabled
        assert envelope.provider_transient_retries == 0
        assert execution["external_confirmation_looks"] == 0
        totals = [a+b for a,b in zip(totals, [envelope.provider_call_cap,
            envelope.outer_hardwall_sec, config.budget.total_cpu_seconds, config.budget.max_storage_bytes])]
    assert totals == [672,25200,3480,7*1024**3]
    limits = load_code_research_limits(p5.DATA / "config/code-research-limits.json")
    assert limits.max_transcript_chars is None and limits.max_turns == 24


def test_reference_geometry_and_vehicle_arithmetic_independent_of_checker():
    # Independent arithmetic catches a shared mistaken expected value/checker.
    assert math.hypot(3, 4) == 5
    cvrp = p5.load(p5.DATA / "cvrp/evaluator/answers.json")
    assert [c["recomputed_objective"]["total_distance"] for c in cvrp[0]["checks"]] == [2*3+2*4, 3+5+4]
    warehouse = p5.load(p5.DATA / "warehouse/evaluator/answers.json")
    assert [c["recomputed_objective"]["total_cost"] for c in warehouse[0]["checks"]] == [2*800, 800]
    assert 2+2 > 3  # public T3 capacity, versus two separate two-pallet loads
    for problem, expected in [("cvrp", (120,130)), ("warehouse", (100,110))]:
        model = p5.load(p5.DATA / problem / "public/tasks.json")[1]["research_input"]["observations"][0]["work_model"]
        answer = p5.load(p5.DATA / problem / "evaluator/answers.json")[1]["work_model_reference"]
        assert (sum(model["baseline_components"].values()), sum(model["candidate_components"].values())) == expected
        assert (answer["baseline_total"], answer["candidate_total"]) == expected


@pytest.mark.parametrize("task", ["open-cvrp", "open-warehouse"])
def test_open_task_exports_no_diagnosis_answers(task):
    value = p5.export_task(task)
    assert normalize_research_input(value) == value
    assert value["observations"] == [] and "sample_solutions" not in value["current_question"]


@pytest.fixture
def reviewed(tmp_path):
    # Deliberately synthetic evidence, not a real research trace.
    raw = "构造证据：尚不足以证明算法更优。\n"
    (tmp_path / "trace.txt").write_text(raw)
    citation = {"path":"trace.txt", "start":0, "end":len(raw.encode()), "quote":raw}
    sheet = p5.template()
    row = sheet["runs"][0]
    row.update(status="completed", note="Synthetic test only", terminal_ref=citation)
    assessment = {"reviewer":"one", "blinding":"Synthetic fixture; no model labels",
        "dimensions":{dim:{"rating":"insufficient", "reason":"No real trace", "evidence":[]}
                      for dim in p5.DIMENSIONS}}
    assessment["dimensions"]["conclusion"] = {"rating":"supported", "reason":"Scoped negative", "evidence":[citation]}
    second = deepcopy(assessment); second["reviewer"] = "two"
    second["dimensions"]["conclusion"]["rating"] = "contradicted"
    row["reviews"] = [assessment, second]
    return sheet


def test_report_keeps_disagreement_missing_and_unrun(reviewed, tmp_path):
    result = p5.review(reviewed, tmp_path)
    assert len(result["runs"]) == 8
    assert result["runs"][0]["disagreements"] == ["conclusion"]
    assert result["runs"][0]["costs"]["physical_calls"] is None
    assert len(result["pending_double_review"]) == 7
    assert "decision" not in result and "score" not in result
    assert result["runs"][0]["reviews"] == reviewed["runs"][0]["reviews"]


@pytest.mark.parametrize("status", sorted(p5.STATUSES - {"not_run"}))
def test_all_terminal_categories_remain_reported(reviewed, tmp_path, status):
    reviewed["runs"][0]["status"] = status
    assert p5.review(reviewed, tmp_path)["runs"][0]["status"] == status


def test_no_review_and_scientific_intervention_cannot_disappear(reviewed, tmp_path):
    row = reviewed["runs"][0]
    row["reviews"] = []
    row["interventions"] = [{"kind":"scientific", "note":"Human supplied answer",
                             "evidence":row["terminal_ref"]}]
    result = p5.review(reviewed, tmp_path)
    assert row["run_id"] in result["pending_double_review"]
    assert result["runs"][0]["interventions"] == row["interventions"]


def test_continuity_required_for_transfer_task(reviewed, tmp_path):
    first = reviewed["runs"][0]
    later = reviewed["runs"][4]
    later.update({key:deepcopy(value) for key,value in first.items() if key != "run_id"})
    later["reviews"][0]["dimensions"]["continuity"]["rating"] = "not_applicable"
    with pytest.raises(ValueError, match="required dimension"):
        p5.review(reviewed, tmp_path)


@pytest.mark.parametrize("change", ["missing", "duplicate", "extra", "unreviewed", "fake_quote",
    "negative_cost", "bool_cost", "nan_cost", "float_count", "unknown_cost_reason", "missing_reason",
    "repeat_reviewer", "unsupported_rating", "no_citation", "required_na", "terminal_missing"])
def test_incomplete_or_misleading_review_rejected(reviewed, tmp_path, change):
    row = reviewed["runs"][0]
    if change == "missing": reviewed["runs"].pop()
    elif change == "duplicate": reviewed["runs"].append(deepcopy(row))
    elif change == "extra": row["run_id"] = "extra"
    elif change == "unreviewed": row["status"] = "not_run"
    elif change == "fake_quote": row["terminal_ref"]["quote"] = "x"
    elif change in ("negative_cost", "bool_cost", "nan_cost", "float_count"):
        row["costs"]["physical_calls"] = {"negative_cost":-1,"bool_cost":True,"nan_cost":float("nan"),"float_count":1.5}[change]
        del row["missing_costs"]["physical_calls"]
    elif change == "unknown_cost_reason": row["missing_costs"]["unexpected"] = "missing"
    elif change == "missing_reason": del row["missing_costs"]["physical_calls"]
    elif change == "repeat_reviewer": row["reviews"][1]["reviewer"] = "one"
    elif change == "unsupported_rating": row["reviews"][0]["dimensions"]["conclusion"]["rating"] = "pass"
    elif change == "no_citation": row["reviews"][0]["dimensions"]["conclusion"]["evidence"] = []
    elif change == "required_na": row["reviews"][0]["dimensions"]["revision"]["rating"] = "not_applicable"
    elif change == "terminal_missing": row["terminal_ref"] = None
    with pytest.raises(ValueError):
        p5.review(reviewed, tmp_path)


@pytest.mark.parametrize("path", ["../trace.txt", "/trace.txt", "./trace.txt", "a//b", "a\\b", "missing", "."])
def test_unsafe_or_missing_evidence_rejected(tmp_path, path):
    with pytest.raises(ValueError):
        p5.check_citation({"path":path,"start":0,"end":1,"quote":"x"}, tmp_path)


def test_symlink_and_byte_range_rejected(tmp_path):
    (tmp_path / "real").write_bytes(b"value")
    (tmp_path / "link").symlink_to(tmp_path / "real")
    for path, start, end in [("link",0,1), ("real",-1,1), ("real",0,6), ("real",True,2)]:
        with pytest.raises(ValueError):
            p5.check_citation({"path":path,"start":start,"end":end,"quote":"v"}, tmp_path)


@pytest.mark.parametrize("raw", ['{"x":1,"x":2}', '{"x":NaN}'])
def test_ambiguous_json_rejected(tmp_path, raw):
    path = tmp_path / "sheet.json"; path.write_text(raw)
    with pytest.raises(ValueError): p5.load(path)


def test_production_does_not_import_assessment():
    for path in FRAMEWORK.rglob("*.py"):
        if "tests" not in path.parts:
            assert "p5_assessment" not in path.read_text()
