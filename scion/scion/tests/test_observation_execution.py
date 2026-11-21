"""P1b/P2 real Linux isolation cases. No candidate imports occur on the host."""
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil

import pytest

from scion.observation.sandbox import ObservationSandbox, RunLimits
from scion.observation.service import ObservationBudget, ObservationService
from scion.observation.source import ObservationError, SourceBinding
from scion.observation.source import SourceCopier, prepare_source
from scion.problems.cvrp.public_observation import CvrpPublicObservationProvider
from scion.problems.warehouse_delivery.public_observation import WarehousePublicObservationProvider

FRAMEWORK = Path(__file__).resolve().parents[1]
REPO = FRAMEWORK.parents[1]
CVRP = FRAMEWORK / "problems/cvrp"
WAREHOUSE = REPO / "surrogate"
RUN = RunLimits(8, 4, 512 * 1024**2, 512 * 1024, 4 * 1024**2)
CHECK = RunLimits(2, 1, 256 * 1024**2, 65536, 1024**2)


def budget(**changes):
    return replace(ObservationBudget(RUN, CHECK, 1, 30, 30, 30, 200, 100, 100 * 1024**2,
        4 * 1024**2, 300, 65536, 30, 20000, 100, 64, 100, 64), **changes)


def service(tmp_path, *, warehouse=False, **kwargs):
    return ObservationService(provider=WarehousePublicObservationProvider() if warehouse else CvrpPublicObservationProvider(),
        problem_root=WAREHOUSE if warehouse else CVRP, framework_root=FRAMEWORK,
        output_root=tmp_path / "records", forbidden_files=(), budget=budget(), **kwargs)


def binding(root=CVRP, config=None):
    return SourceBinding(root, "current", "branch-current", {} if config is None else config)


def observe(svc, *, source=CVRP, value=None, config=None, limits=RUN):
    value = value or json.loads((CVRP / "data/tiny_development.json").read_text())
    return svc.observe(binding=binding(source, config), raw_input=json.dumps(value).encode(),
        public_args={"time_limit_sec": 0.05}, seed=17, limits=limits)


def stderr(svc, response, stage="subject"):
    path = (svc.materials.root / response["ref"]).parent.joinpath(f"{stage}.stderr")
    return path.read_text() if path.exists() else repr(response)


def custom_source(tmp_path, code):
    source = tmp_path / "source"
    (source / "policies").mkdir(parents=True)
    (source / "policies/__init__.py").write_text("")
    (source / "policies/baseline_algorithm.py").write_text(code)
    return source


def simple_cvrp():
    return {"name": "triangle", "capacity": 2, "depot": 0, "allowed_routes": 1,
        "use_integer_cost": True, "nodes": [{"id": 0, "x": 0, "y": 0, "demand": 0},
        {"id": 1, "x": 3, "y": 0, "demand": 1}, {"id": 2, "x": 0, "y": 4, "demand": 1}]}


def test_real_cvrp_subject_and_independent_checker(tmp_path):
    svc = service(tmp_path)
    result = observe(svc)
    assert result["data"] == "valid", stderr(svc, result)
    assert result["check"]["feasibility"] == "pass"
    assert svc.usage["started_subjects"] == svc.usage["started_checkers"] == 1
    assert result["usage"]["subject"]["cpu_seconds"] > 0.01
    assert result["usage"]["checker"]["cpu_seconds"] > 0
    assert result["usage"]["subject"]["peak_memory_bytes"] > 0


@pytest.mark.parametrize("routes,distance,fleet", [("((1,2),)", 12, 0), ("((1,),(2,))", 14, 1)])
def test_reference_distance_and_fleet(tmp_path, routes, distance, fleet):
    source = custom_source(tmp_path, f"from scion.problems.cvrp.models import CvrpSolution\ndef solve(*args): return CvrpSolution({routes})\n")
    result = observe(service(tmp_path), source=source, value=simple_cvrp())
    assert result["check"]["recomputed_objective"] == {"total_distance": distance, "fleet_violation": fleet, "routes": fleet + 1}


@pytest.mark.parametrize("body", ["raise ValueError('failed active')", "return None"])
def test_active_failure_never_falls_back(tmp_path, body):
    source = custom_source(tmp_path, f"def solve(*args): {body}\n")
    result = observe(service(tmp_path), source=source)
    assert result["payload"]["outcome"] == "algorithm_error"
    assert result["check"] is None and result["reason_code"] == "SUBJECT_ERROR"


def test_checker_ignores_subject_memory_pollution(tmp_path):
    source = custom_source(tmp_path, '''from scion.problems.cvrp.models import CvrpSolution, CvrpInstance
def solve(*args):
    CvrpInstance.route_distance = lambda *args: 99999
    return CvrpSolution(((1,2),))
''')
    result = observe(service(tmp_path), source=source, value=simple_cvrp())
    assert result["check"]["recomputed_objective"]["total_distance"] == 12


def test_warehouse_real_config_and_frozen_price(tmp_path):
    svc = service(tmp_path, warehouse=True)
    source = tmp_path / "initial-default-source"
    shutil.copytree(WAREHOUSE, source, ignore=shutil.ignore_patterns("__pycache__", "tests", "data", "registry.yaml"))
    value = json.loads((WAREHOUSE / "data/instance_development.json").read_text())
    value["orders"] = value["orders"][:1]
    result = svc.observe(binding=binding(source, {"operator_selection": "defaults"}),
        raw_input=json.dumps(value).encode(), public_args={"time_limit_sec": 0.05, "max_iterations": 1}, seed=17, limits=RUN)
    assert result["data"] == "valid", stderr(svc, result)
    assert result["check"]["recomputed_objective"] == {"subcategory_splits": 0, "total_cost": 800}


def test_warehouse_selected_registry_and_missing_registry(tmp_path):
    source = tmp_path / "warehouse"
    shutil.copytree(WAREHOUSE, source, ignore=shutil.ignore_patterns("__pycache__", "tests", "data"))
    (source / "operators/marker.py").write_text('''from operators.base import Operator
class Marker(Operator):
    def __init__(self, instance, phase): pass
    def execute(self, solution, rng):
        print("selected-registry-operator")
        return solution
''')
    (source / "registry.yaml").write_text("operators:\n  - name: marker\n    file_path: operators/marker.py\n    class_name: Marker\n    weight: 1\n")
    config_path = source / "config.py"
    config_path.write_text(config_path.read_text().replace("pool_size: int = 40", "pool_size: int = 2"))
    svc = service(tmp_path, warehouse=True)
    kwargs = dict(binding=binding(source, {"operator_selection": "registry"}),
        raw_input=(WAREHOUSE / "data/instance_development.json").read_bytes(),
        public_args={"time_limit_sec": 0.1, "max_iterations": 1}, seed=17, limits=RUN)
    result = svc.observe(**kwargs)
    assert result["data"] == "valid", stderr(svc, result)
    assert result["payload"]["diagnostics"]["runtime"]["operator_registry"] == ["marker"]
    assert result["payload"]["diagnostics"]["config"]["pool_size"] == 2
    (source / "registry.yaml").unlink()
    result = svc.observe(**kwargs)
    assert result["reason_code"] == "SOURCE_UNAVAILABLE" and result["execution"] == "not_started"
    assert svc.usage["started_subjects"] == 1


def test_prepared_source_does_not_reread_host(tmp_path):
    source = custom_source(tmp_path, "from scion.problems.cvrp.models import CvrpSolution\ndef solve(*args): return CvrpSolution(((1,2),))\n")
    class ChangingSandbox(ObservationSandbox):
        def run(self, **kwargs):
            (source / "policies/baseline_algorithm.py").write_text("raise Exception('host changed')")
            return super().run(**kwargs)
    result = observe(service(tmp_path, sandbox=ChangingSandbox()), source=source, value=simple_cvrp())
    assert result["check"]["recomputed_objective"]["total_distance"] == 12


def test_analysis_cannot_read_host_or_spawn_or_mutate_source(tmp_path, monkeypatch):
    secret = tmp_path / "private"
    secret.write_text("must-not-leak")
    monkeypatch.setenv("OBS_PRIVATE_SENTINEL", "must-not-leak")
    svc = service(tmp_path)
    script = f'''import os, socket, importlib, sys
from scion.observation.wire import emit
assert os.getenv("OBS_PRIVATE_SENTINEL") is None
blocked=[]
for name, operation in [
    ("private", lambda: open({str(secret)!r}).read()),
    ("source_write", lambda: open("/subject/policies/baseline_algorithm.py", "w")),
    ("root_write", lambda: open("/escape", "w")),
    ("site_write", lambda: open(f"/python/lib/python{{sys.version_info.major}}.{{sys.version_info.minor}}/site-packages/escape", "w")),
    ("network", lambda: socket.socket()),
    ("fork", lambda: os.fork()),
    ("exec", lambda: os.execv("/python/bin/python", ["python", "-c", "pass"])),
    ("framework", lambda: importlib.import_module("scion.core.decision")),
]:
    try: operation()
    except (OSError, ImportError): blocked.append(name)
emit({{"blocked":blocked}})
'''
    result = svc.analyze(binding=binding(), script=script, inputs={"public": 1}, limits=RUN)
    assert result["reason_code"] == "COMPLETED"
    data = json.loads((svc.materials.root / result["output_refs"][2]).read_bytes())
    assert len(data["blocked"]) == 8


@pytest.mark.parametrize("script,limits,expected", [
    ("while True: pass", replace(RUN, wall_seconds=1.2), "WALL_LIMIT"),
    ("while True: pass", replace(RUN, cpu_seconds=1), "CPU_LIMIT"),
    ("import os\nwhile True: os.write(1,b'x'*4096)", replace(RUN, output_bytes=1000), "OUTPUT_LIMIT"),
])
def test_execution_limits_are_real_and_charged(tmp_path, script, limits, expected):
    svc = service(tmp_path)
    result = svc.analyze(binding=binding(), script=script, inputs={}, limits=limits)
    if expected == "CPU_LIMIT":
        assert result["reason_code"] in {"CPU_LIMIT", "PROCESS_KILLED"}, result
        assert result["execution"] in {"limited", "error"}
    else:
        assert result["reason_code"] == expected, result
        assert result["execution"] == "limited"
    assert result["capture"] == "partial"
    assert svc.usage["started_analyses"] == 1
    assert svc.usage["cpu_seconds"] > 0
    if expected == "CPU_LIMIT":
        assert .9 <= result["usage"]["analysis"]["cpu_seconds"] < 1.5
        assert result["usage"]["analysis"]["returncode"] in {-9, 137, -24, 152}
    if expected == "OUTPUT_LIMIT":
        assert sum((svc.materials.root / ref).stat().st_size for ref in result["output_refs"]) == limits.output_bytes


def test_memory_pressure_is_bounded_without_claiming_known_oom(tmp_path):
    svc = service(tmp_path)
    result = svc.analyze(binding=binding(), script="x=bytearray(1024**3)", inputs={},
                         limits=replace(RUN, memory_bytes=128*1024**2))
    assert result["reason_code"] == "ANALYSIS_ERROR" and result["execution"] == "error"
    assert "MemoryError" in stderr(svc, result, "analysis")
    assert result["usage"]["analysis"]["peak_memory_bytes"] > 0


def test_failure_and_new_session_do_not_reset_shared_cap(tmp_path):
    svc = service(tmp_path)
    svc.budget = budget(max_analysis_runs=1)
    svc.analyze(binding=binding(), script="raise ValueError()", inputs={}, limits=RUN)
    svc.begin_session()
    with pytest.raises(ObservationError, match="GLOBAL_RESEARCH_LIMIT"):
        svc.analyze(binding=binding(), script="pass", inputs={}, limits=RUN)


def test_insufficient_request_and_checker_reservation_do_not_launch(tmp_path):
    svc = service(tmp_path)
    with pytest.raises(ObservationError, match="LIMIT_NOT_AVAILABLE"):
        observe(svc, limits=replace(RUN, cpu_seconds=1))
    assert svc.usage["started_subjects"] == 0
    svc.budget = budget(total_cpu_seconds=3)
    with pytest.raises(ObservationError, match="LIMIT_NOT_AVAILABLE"):
        observe(svc)
    assert not svc.stopped


def test_missing_isolation_does_not_execute(tmp_path):
    svc = service(tmp_path, sandbox=ObservationSandbox(bwrap="/missing-bwrap"))
    result = observe(svc)
    assert result["reason_code"] == "ISOLATION_UNAVAILABLE" and svc.stopped
    assert svc.usage["started_subjects"] == 0


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "formal", "fifo"])
def test_source_aliases_rejected_before_execution(tmp_path, kind):
    source = custom_source(tmp_path, "def solve(*args): return None")
    target = source / "policies/baseline_algorithm.py"
    private = tmp_path / "formal.py"
    private.write_text("raise Exception('private')")
    if kind != "formal":
        target.unlink()
    if kind == "symlink":
        target.symlink_to(private)
    elif kind == "hardlink":
        os.link(private, target)
    elif kind == "fifo":
        os.mkfifo(target)
    svc = service(tmp_path)
    if kind == "formal":
        svc.forbidden_files = (target,)
    result = observe(svc, source=source)
    assert result["reason_code"] == "PUBLIC_CLOSURE_INVALID"
    assert svc.usage["started_subjects"] == 0


def frozen_check(tmp_path, value, solution, *, warehouse=False):
    provider = WarehousePublicObservationProvider() if warehouse else CvrpPublicObservationProvider()
    root = WAREHOUSE if warehouse else CVRP
    spec = provider.describe()
    prepared = tmp_path / "prepared"
    prepare_source(binding=binding(root), problem_root=root, framework_root=FRAMEWORK,
        spec=spec, destination=prepared,
        copier=SourceCopier(forbidden_files=(), max_files=300, max_bytes=4*1024**2))
    (prepared / "empty").mkdir()
    (prepared / "input").mkdir()
    (prepared / "input/request.json").write_text(json.dumps({"instance": value, "solution": solution,
        "reported_objective": {"total_distance": -1000, "total_cost": 0}, "feasible": True}))
    result = ObservationSandbox().run(subject=prepared / "empty", runtime=prepared / "checker",
        inputs=prepared / "input", module=spec.checker_module, mode="checker", limits=CHECK)
    assert result.reason_code == "COMPLETED", result.stderr
    return json.loads(result.result)


@pytest.mark.parametrize("routes", [[[1, 1, 2]], [[1]], [[True, 2]], [[0, 1, 2]], [[99]]])
def test_frozen_cvrp_checker_rejects_bad_routes_without_fake_objective(tmp_path, routes):
    checked = frozen_check(tmp_path, simple_cvrp(), {"routes": routes})
    assert checked["consistency"] == "fail" and checked["recomputed_objective"] is None


def test_capacity_counterexample_is_valid_measurement(tmp_path):
    value = simple_cvrp()
    value["capacity"] = 1
    checked = frozen_check(tmp_path, value, {"routes": [[1, 2]]})
    assert checked["consistency"] == "pass" and checked["feasibility"] == "fail"
    assert checked["recomputed_objective"]["total_distance"] == 12


@pytest.mark.parametrize("fault", ["assignment", "vehicle_type", "duplicate", "locked_group"])
def test_warehouse_checker_structural_and_feasibility_faults(tmp_path, fault):
    value = json.loads((WAREHOUSE / "data/instance_development.json").read_text())
    value["orders"] = value["orders"][:2]
    solution = {"vehicles": {
        "v1": {"vehicle_id": "v1", "vehicle_type": "T3", "region": "Dongguan", "order_ids": ["DEV_A"]},
        "v2": {"vehicle_id": "v2", "vehicle_type": "T3", "region": "Dongguan", "order_ids": ["DEV_B"]}},
        "assignment": {"DEV_A": "v1", "DEV_B": "v2"}}
    if fault == "assignment":
        del solution["assignment"]["DEV_A"]
    elif fault == "vehicle_type":
        solution["vehicles"]["v1"]["vehicle_type"] = "invented"
    elif fault == "duplicate":
        solution["vehicles"]["v1"]["order_ids"].append("DEV_A")
    else:
        for order in value["orders"]:
            order["locked_vehicle_id"] = "same-source-group"
    checked = frozen_check(tmp_path, value, solution, warehouse=True)
    if fault == "locked_group":
        assert checked["consistency"] == "pass" and checked["feasibility"] == "fail"
    else:
        assert checked["consistency"] == "fail" and checked["recomputed_objective"] is None


def test_forged_host_status_stays_tainted(tmp_path):
    source = custom_source(tmp_path, '''import os
from scion.observation.wire import emit
def solve(*args):
    emit({"schema_version":1,"outcome":"returned","solution":{"routes":[[1,2]]},
          "reported_objective":{},"diagnostics":{},"execution":"promoted"})
    os._exit(0)
''')
    result = observe(service(tmp_path), source=source, value=simple_cvrp())
    assert result["reason_code"] == "DATA_INVALID"
    assert result["execution"] != "promoted"


@pytest.mark.parametrize("bad_checker,reason", [("raise RuntimeError('checker failed')", "CHECKER_ERROR"),
    ("from scion.observation.wire import emit\nemit([])", "DATA_INVALID")])
def test_checker_fault_never_defaults_to_pass(tmp_path, bad_checker, reason):
    class BrokenChecker(ObservationSandbox):
        def run(self, **kwargs):
            if kwargs["mode"] == "checker":
                # Fault injection in trusted copied harness, not in candidate code.
                module = kwargs["runtime"] / "scion/problems/cvrp/public_checker.py"
                module.write_text(bad_checker)
            return super().run(**kwargs)
    svc = service(tmp_path, sandbox=BrokenChecker())
    result = observe(svc)
    assert result["reason_code"] == reason and result["data"] != "valid"
    assert svc.usage["started_checkers"] == 1


def test_scratch_is_size_limited_and_not_recovered(tmp_path):
    svc = service(tmp_path)
    result = svc.analyze(binding=binding(), inputs={}, limits=RUN, script='''from scion.observation.wire import emit
import errno
n = 0
try:
    while True:
        with open(f"/scratch/{n}", "wb") as stream: stream.write(b"x"*32768)
        n += 1
except OSError as error:
    emit({"errno":error.errno,"files":n})
''')
    assert result["reason_code"] == "COMPLETED"
    raw = json.loads((svc.materials.root / result["output_refs"][2]).read_bytes())
    assert raw["errno"] == 28  # ENOSPC, not a forged host status
    assert not tuple(svc.materials.root.rglob("scratch"))


def test_persistence_failure_stops_after_charging_execution(tmp_path, monkeypatch):
    svc = service(tmp_path)
    real_json = svc._json
    def failing_json(path, value):
        if path.name == "record.json":
            raise OSError("disk failure")
        return real_json(path, value)
    monkeypatch.setattr(svc, "_json", failing_json)
    with pytest.raises(ObservationError, match="PERSISTENCE_ERROR"):
        observe(svc)
    assert svc.stopped and svc.usage["started_subjects"] == 1 and svc.usage["started_checkers"] == 1
    assert svc.usage["cpu_seconds"] > 0
    assert not tuple(svc.materials.root.glob("observation-*"))


def test_interruption_kills_target_and_keeps_cost(tmp_path, monkeypatch):
    import selectors
    base = selectors.DefaultSelector
    class InterruptingSelector(base):
        calls = 0
        def select(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 20:
                raise KeyboardInterrupt()
            return super().select(*args, **kwargs)
    monkeypatch.setattr(selectors, "DefaultSelector", InterruptingSelector)
    svc = service(tmp_path)
    result = svc.analyze(binding=binding(), script="while True: pass", inputs={}, limits=RUN)
    assert result["reason_code"] == "USER_INTERRUPTED" and result["execution"] == "interrupted"
    assert svc.stopped and svc.usage["started_analyses"] == 1
    assert result["usage"]["analysis"]["cpu_seconds"] > 0


def test_analysis_memory_changes_do_not_contaminate_repeated_subjects(tmp_path):
    source = custom_source(tmp_path, "from scion.problems.cvrp.models import CvrpSolution\ndef solve(*args): return CvrpSolution(((1,2),))\n")
    svc = service(tmp_path)
    first = observe(svc, source=source, value=simple_cvrp())
    analysis = svc.analyze(binding=binding(source), inputs={"public_probe": 17}, limits=RUN,
        script='''from scion.problems.cvrp.models import CvrpInstance
CvrpInstance.route_distance = lambda *args: -1
print(open("/input/request.json").read())
''')
    second = observe(svc, source=source, value=simple_cvrp())
    assert first["check"] == second["check"]
    assert analysis["mode"] == "analysis" and analysis["data"] == "not_checked"
    assert svc.usage["started_subjects"] == svc.usage["started_checkers"] == 2
    assert svc.usage["started_analyses"] == 1


def test_failed_launcher_is_not_mistaken_for_algorithm_failure(tmp_path):
    svc = service(tmp_path, sandbox=ObservationSandbox(bwrap="/usr/bin/false"))
    result = observe(svc)
    assert result["reason_code"] == "ISOLATION_UNAVAILABLE"
    assert result["execution"] == "not_started" and svc.usage["started_subjects"] == 0


def test_cvrp_context_instance_path_is_a_real_instance_not_transport_envelope(tmp_path):
    source = custom_source(tmp_path, '''from scion.problems.cvrp.models import CvrpInstance, CvrpSolution
def solve(instance, rng, time_limit_sec, context):
    assert CvrpInstance.from_json(context.instance_path) == instance
    return CvrpSolution(((1,2),))
''')
    result = observe(service(tmp_path), source=source, value=simple_cvrp())
    assert result["data"] == "valid" and result["check"]["recomputed_objective"]["total_distance"] == 12


def test_rejected_validation_still_charges_host_research_cost(tmp_path, monkeypatch):
    import time
    from scion.problem.public_input import PublicInputError
    svc = service(tmp_path)
    def reject(value):
        start = time.process_time()
        while time.process_time() - start < .02:
            pass
        raise PublicInputError("INPUT_INVALID")
    monkeypatch.setattr(svc.provider, "validate_input", reject)
    with pytest.raises(ObservationError, match="INPUT_INVALID"):
        observe(svc)
    assert svc.usage["cpu_seconds"] >= .02 and svc.usage["wall_seconds"] >= .02
    assert svc.usage["started_subjects"] == 0 and svc.session_actions == 1


def test_storage_preparation_failure_is_infrastructure_not_research(tmp_path, monkeypatch):
    import tempfile
    svc = service(tmp_path)
    def fail(**kwargs):
        raise OSError("storage unavailable")
    monkeypatch.setattr(tempfile, "mkdtemp", fail)
    with pytest.raises(ObservationError, match="PERSISTENCE_ERROR"):
        observe(svc)
    assert svc.stopped and svc.usage["started_subjects"] == 0


def test_exit_137_does_not_establish_cpu_or_oom_cause(tmp_path):
    svc = service(tmp_path)
    result = svc.analyze(binding=binding(), script="import os\nos._exit(137)", inputs={}, limits=RUN)
    assert result["reason_code"] == "PROCESS_KILLED"
    assert result["execution"] == "error" and result["capture"] == "partial"
    assert result["usage"]["analysis"]["cpu_seconds"] < .9
    assert svc.usage["started_analyses"] == 1
