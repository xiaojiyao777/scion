"""Host-only observation orchestration; H/C exposure is a separate P3 boundary."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from contextlib import contextmanager
import json
from pathlib import Path
import tempfile
import time

from scion.observation.materials import ResearchMaterials
from scion.observation.sandbox import ObservationSandbox, RunLimits
from scion.observation.source import ObservationError, SourceBinding, SourceCopier, prepare_source
from scion.problem.public_input import PublicInputError, decode_public_json


@dataclass(frozen=True)
class ObservationBudget:
    per_action: RunLimits
    checker: RunLimits
    preparation_wall_seconds: float
    max_subject_runs: int
    max_analysis_runs: int
    max_checker_runs: int
    total_wall_seconds: float
    total_cpu_seconds: float
    max_storage_bytes: int
    max_source_bytes: int
    max_files_per_action: int
    max_input_bytes: int
    max_json_depth: int
    max_collection_items: int
    max_actions_per_session: int
    max_read_bytes: int
    max_search_matches: int
    max_search_scan_bytes: int

    def __post_init__(self):
        import math
        for name, value in vars(self).items():
            if name in {"per_action", "checker"}:
                if type(value) is not RunLimits:
                    raise ValueError("explicit run limits required")
            elif name in {"preparation_wall_seconds", "total_wall_seconds", "total_cpu_seconds"}:
                if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                    raise ValueError("positive finite budget required")
            elif type(value) is not int or value <= 0:
                raise ValueError("positive integer budget required")


class ObservationService:
    def __init__(self, *, provider, problem_root: Path, framework_root: Path,
                 output_root: Path, forbidden_files: tuple[Path, ...], budget: ObservationBudget,
                 sandbox: ObservationSandbox | None = None):
        self.provider, self.spec = provider, provider.describe()
        self.problem_root, self.framework_root = problem_root, framework_root
        self.forbidden_files, self.budget = forbidden_files, budget
        self.sandbox = sandbox or ObservationSandbox()
        self.materials = ResearchMaterials(output_root, max_storage_bytes=budget.max_storage_bytes,
            max_read_bytes=budget.max_read_bytes, max_search_matches=budget.max_search_matches,
            max_search_scan_bytes=budget.max_search_scan_bytes)
        self.usage = {"started_subjects": 0, "started_analyses": 0, "started_checkers": 0,
                      "wall_seconds": 0.0, "cpu_seconds": 0.0}
        self.session_actions = 0
        self.stopped = False
        self._action_active = False
        self._timing_active = False
        self._action_started = None

    @contextmanager
    def account_host_work(self):
        if self._timing_active:
            yield
            return
        start, cpu = time.monotonic(), time.process_time()
        self._timing_active = True
        try:
            yield
        finally:
            self._timing_active = False
            self.usage["wall_seconds"] += time.monotonic() - start
            self.usage["cpu_seconds"] += time.process_time() - cpu
            if (self.usage["wall_seconds"] >= self.budget.total_wall_seconds
                    or self.usage["cpu_seconds"] >= self.budget.total_cpu_seconds):
                self.stopped = True

    @contextmanager
    def action_scope(self):
        """Charge once, including rejected session permissions and host setup."""
        self._action()
        with self.account_host_work():
            self._action_active = True
            self._action_started = time.monotonic()
            try:
                yield
            finally:
                self._action_active = False
                self._action_started = None

    def begin_session(self):
        """Host transition only. Shared campaign counters are deliberately retained."""
        self.session_actions = 0

    def _action(self):
        if self._action_active:
            return
        if self.stopped:
            raise ObservationError("GLOBAL_RESEARCH_LIMIT")
        self.session_actions += 1
        if self.session_actions > self.budget.max_actions_per_session:
            raise ObservationError("PROPOSAL_LOCAL_LIMIT")

    def write_material(self, kind: str, content: str):
        self._action()
        if type(content) is not str:
            raise ObservationError("REQUEST_INVALID")
        try:
            raw = content.encode("utf-8")
        except UnicodeError:
            raise ObservationError("REQUEST_INVALID") from None
        if len(raw) > self.budget.max_input_bytes:
            raise ObservationError("INPUT_INVALID")
        if kind == "input":
            try:
                self._decode(raw)
            except PublicInputError:
                raise ObservationError("INPUT_INVALID") from None
        try:
            return self.materials.append(kind, raw)
        except ObservationError as error:
            if error.reason_code in {"PERSISTENCE_ERROR", "GLOBAL_RESEARCH_LIMIT"}:
                self.stopped = True
            raise

    def read_material(self, *args, **kwargs):
        self._action()
        return self.materials.read(*args, **kwargs)

    def search_materials(self, *args, **kwargs):
        self._action()
        return self.materials.search(*args, **kwargs)

    def _decode(self, raw, max_bytes=None):
        return decode_public_json(raw, max_bytes=max_bytes or self.budget.max_input_bytes,
            max_depth=self.budget.max_json_depth, max_collection_items=self.budget.max_collection_items)

    def _reserve(self, mode, limits):
        cap = self.budget.per_action
        if limits.wall_seconds <= self.budget.preparation_wall_seconds:
            raise ObservationError("LIMIT_NOT_AVAILABLE")
        if any(getattr(limits, key) > getattr(cap, key) for key in vars(cap)):
            raise ObservationError("LIMIT_NOT_AVAILABLE")
        required = [("started_analyses", self.budget.max_analysis_runs)] if mode == "analysis" else [
            ("started_subjects", self.budget.max_subject_runs), ("started_checkers", self.budget.max_checker_runs)]
        if (any(self.usage[key] >= cap for key, cap in required)
                or self.usage["wall_seconds"] >= self.budget.total_wall_seconds
                or self.usage["cpu_seconds"] >= self.budget.total_cpu_seconds
                or self.materials.used_bytes() >= self.budget.max_storage_bytes):
            self.stopped = True
            raise ObservationError("GLOBAL_RESEARCH_LIMIT")
        if (self.usage["wall_seconds"] + limits.wall_seconds > self.budget.total_wall_seconds
                or self.usage["cpu_seconds"] + limits.cpu_seconds > self.budget.total_cpu_seconds):
            raise ObservationError("LIMIT_NOT_AVAILABLE")
        if mode == "subject_run":
            check = self.budget.checker
            if (limits.wall_seconds <= check.wall_seconds + self.budget.preparation_wall_seconds
                    or limits.cpu_seconds <= check.cpu_seconds or limits.output_bytes <= check.output_bytes
                    or limits.memory_bytes < check.memory_bytes or limits.scratch_bytes < check.scratch_bytes):
                raise ObservationError("LIMIT_NOT_AVAILABLE")

    def observe(self, *, binding: SourceBinding, raw_input: bytes, public_args: dict,
                seed: int, limits: RunLimits):
        return self._observe(binding=binding, raw_input=raw_input, public_args=public_args,
                             seed=seed, limits=limits, analysis=None)

    def analyze(self, *, binding: SourceBinding, script: str, inputs: dict, limits: RunLimits):
        # P3 resolves allowed refs into detached values before this host-only call.
        return self._observe(binding=binding, raw_input=json.dumps(inputs, allow_nan=False).encode(),
                             public_args={}, seed=0, limits=limits, analysis=script)

    def _observe(self, **kwargs):
        with self.account_host_work():
            return self._execute_observation(start=self._action_started or time.monotonic(), **kwargs)

    def _execute_observation(self, *, start, binding, raw_input, public_args, seed, limits, analysis):
        self._action()
        mode = "analysis" if analysis is not None else "subject_run"
        self._reserve(mode, limits)
        if type(seed) is not int or not 0 <= seed <= 2**63 - 1:
            raise ObservationError("REQUEST_INVALID")
        if len(binding.source_ref.encode("utf-8")) > self.budget.max_input_bytes:
            raise ObservationError("REQUEST_INVALID")
        try:
            instance = self._decode(raw_input)
            args = {} if analysis is not None else self.provider.validate_args(public_args)
            if analysis is None:
                instance = self.provider.validate_input(instance)
            elif type(analysis) is not str or len(analysis.encode()) > self.budget.max_input_bytes:
                raise PublicInputError("INPUT_SIZE_LIMIT")
        except (PublicInputError, UnicodeError):
            raise ObservationError("INPUT_INVALID") from None
        try:
            staging = Path(tempfile.mkdtemp(prefix=".pending-", dir=self.materials.root))
        except OSError:
            self.stopped = True
            raise ObservationError("PERSISTENCE_ERROR") from None
        runs = {}
        response = {"schema_version": 1, "mode": mode, "execution": "not_started",
                    "capture": "none", "data": "not_checked", "reason_code": "COMPLETED",
                    "requested_limits": asdict(limits),
                    "source_condition": {"role": binding.role, "source_ref": binding.source_ref}}
        payload = check = None
        try:
            free = self.budget.max_storage_bytes - self.materials.used_bytes()
            # Reserve output plus bounded host metadata; source copy has its own cap.
            source_cap = min(self.budget.max_source_bytes, free - 2 * limits.output_bytes - 3 * len(raw_input) - 32768)
            if source_cap <= 0:
                raise ObservationError("LIMIT_NOT_AVAILABLE")
            if self.budget.max_files_per_action <= 16:
                raise ObservationError("LIMIT_NOT_AVAILABLE")
            copier = SourceCopier(forbidden_files=self.forbidden_files,
                max_files=self.budget.max_files_per_action - 16, max_bytes=source_cap)
            available = prepare_source(binding=binding, problem_root=self.problem_root,
                framework_root=self.framework_root, spec=self.spec, destination=staging, copier=copier)
            if sum(p.is_file() for p in staging.rglob("*")) + 16 > self.budget.max_files_per_action:
                raise ObservationError("LIMIT_NOT_AVAILABLE")
            try:
                config = self.provider.validate_source_config(binding.config, available)
            except PublicInputError:
                raise ObservationError("SOURCE_UNAVAILABLE") from None
            request = {"schema_version": 1, "instance": instance, "seed": seed,
                       "public_args": args, "source_config": config}
            input_dir = staging / "input"
            input_dir.mkdir()
            self._json(input_dir / "request.json", request)
            self._json(input_dir / "instance.json", instance)
            self._json(staging / "source_files.json", list(available))
            (staging / "empty").mkdir()
            if analysis is not None:
                self._bytes(input_dir / "analysis.py", analysis.encode("utf-8"))
            setup_elapsed = time.monotonic() - start
            if setup_elapsed > self.budget.preparation_wall_seconds:
                raise ObservationError("WALL_LIMIT")
            check_limits = self.budget.checker
            active = replace(limits, wall_seconds=limits.wall_seconds - self.budget.preparation_wall_seconds)
            if analysis is None:
                active = replace(active, wall_seconds=active.wall_seconds - check_limits.wall_seconds,
                    cpu_seconds=active.cpu_seconds - check_limits.cpu_seconds,
                    output_bytes=active.output_bytes - check_limits.output_bytes)
            self._run("analysis" if analysis is not None else "subject", runs, staging,
                      inputs=input_dir, limits=active, analysis=analysis is not None)
            subject = next(iter(runs.values()))
            if subject.reason_code != "COMPLETED":
                response["reason_code"] = (("ANALYSIS_ERROR" if analysis is not None else "SUBJECT_ERROR")
                    if subject.reason_code == "PROCESS_ERROR" else subject.reason_code)
            elif analysis is None:
                try:
                    payload = self._decode(subject.result, active.output_bytes)
                    if (set(payload) != {"schema_version", "outcome", "solution", "reported_objective", "diagnostics"}
                            or type(payload["schema_version"]) is not int or payload["schema_version"] != 1
                            or payload["outcome"] not in {"returned", "algorithm_error", "invalid_solution"}
                            or type(payload["reported_objective"]) is not dict or type(payload["diagnostics"]) is not dict):
                        raise PublicInputError("DATA_INVALID")
                    if payload["outcome"] != "returned":
                        response["reason_code"] = "SUBJECT_ERROR"
                    elif type(payload["solution"]) is not dict:
                        raise PublicInputError("DATA_INVALID")
                    else:
                        checker_input = staging / "checker_input"
                        checker_input.mkdir()
                        self._json(checker_input / "request.json", {"instance": instance, "solution": payload["solution"]})
                        remaining_wall = limits.wall_seconds - (time.monotonic() - start)
                        if remaining_wall < check_limits.wall_seconds:
                            raise ObservationError("WALL_LIMIT")
                        self._run("checker", runs, staging, inputs=checker_input, limits=check_limits)
                        if runs["checker"].reason_code != "COMPLETED":
                            response["reason_code"] = "CHECKER_ERROR"
                        else:
                            check = self._decode(runs["checker"].result, check_limits.output_bytes)
                            if (set(check) != {"schema_version", "consistency", "feasibility", "recomputed_objective", "reason_codes"}
                                    or type(check["schema_version"]) is not int or check["schema_version"] != 1
                                    or check["consistency"] not in {"pass", "fail", "not_evaluated"}
                                    or check["feasibility"] not in {"pass", "fail", "not_evaluated"}
                                    or (check["recomputed_objective"] is not None and type(check["recomputed_objective"]) is not dict)
                                    or type(check["reason_codes"]) is not list
                                    or any(type(code) is not str for code in check["reason_codes"])):
                                raise PublicInputError("DATA_INVALID")
                            response["data"] = "valid"
                except (PublicInputError, TypeError):
                    response["reason_code"], response["data"] = "DATA_INVALID", "invalid"
        except ObservationError as error:
            response["reason_code"] = error.reason_code
        except OSError:
            self.stopped = True
            raise ObservationError("PERSISTENCE_ERROR") from None
        except KeyboardInterrupt:
            response["reason_code"] = "USER_INTERRUPTED"
            self.stopped = True
        except Exception:
            response["reason_code"] = "INTERNAL_ERROR"
            self.stopped = True
        if runs:
            response["execution"] = "completed" if all(r.reason_code == "COMPLETED" for r in runs.values()) else "error"
            response["capture"] = "complete" if any(r.started or r.captured_bytes for r in runs.values()) else "none"
            if not any(r.started for r in runs.values()):
                response["execution"] = "not_started"
            if any(r.reason_code in {"OUTPUT_LIMIT", "WALL_LIMIT", "CPU_LIMIT"} for r in runs.values()):
                response["execution"], response["capture"] = "limited", "partial"
            elif any(r.reason_code == "PROCESS_KILLED" for r in runs.values()):
                response["execution"], response["capture"] = "error", "partial"
        if response["reason_code"] in {"ISOLATION_UNAVAILABLE", "PUBLIC_CLOSURE_INVALID", "PERSISTENCE_ERROR", "INTERNAL_ERROR", "USER_INTERRUPTED"}:
            self.stopped = True
        if response["reason_code"] == "USER_INTERRUPTED":
            response["execution"], response["capture"] = "interrupted", "partial"
        response["usage"] = {key: {k: v for k, v in asdict(run).items() if k not in {"stdout", "stderr", "result"}} for key, run in runs.items()}
        response["usage"]["total_wall_seconds"] = time.monotonic() - start
        try:
            for name, run in runs.items():
                for stream in ("stdout", "stderr", "result"):
                    self._bytes(staging / f"{name}.{stream}", getattr(run, stream))
            self._json(staging / "record.json", response)
            if self.materials.used_bytes() > self.budget.max_storage_bytes:
                self.stopped = True
                raise ObservationError("GLOBAL_RESEARCH_LIMIT")
            ordinal = len(tuple(self.materials.root.glob("observation-*"))) + 1
            destination = self.materials.root / f"observation-{ordinal:06d}"
            staging.rename(destination)
        except OSError:
            self.stopped = True
            raise ObservationError("PERSISTENCE_ERROR") from None
        response["ref"] = f"{destination.name}/record.json"
        response["output_refs"] = [f"{destination.name}/{name}.{stream}" for name in runs for stream in ("stdout", "stderr", "result")]
        response["payload"], response["check"] = payload, check
        return response

    def _run(self, stage, runs, staging, *, inputs, limits, analysis=False):
        checker = stage == "checker"
        result = self.sandbox.run(
            subject=staging / ("empty" if checker else "subject"),
            runtime=staging / ("checker" if checker else "runner"), inputs=inputs,
            module=self.spec.checker_module if checker else self.spec.runner_module,
            mode="analysis" if analysis else stage, limits=limits,
            dependencies=self.spec.checker_dependencies if checker else self.spec.subject_dependencies,
        )
        runs[stage] = result
        if result.cpu_seconds is not None:
            self.usage["cpu_seconds"] += result.cpu_seconds
        if result.started:
            counter = {"subject": "started_subjects", "analysis": "started_analyses", "checker": "started_checkers"}[stage]
            self.usage[counter] += 1

    def _json(self, path, value):
        raw = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
        self._bytes(path, raw)

    def _bytes(self, path, raw):
        if self.materials.used_bytes() + len(raw) > self.budget.max_storage_bytes:
            self.stopped = True
            raise ObservationError("GLOBAL_RESEARCH_LIMIT")
        path.write_bytes(raw)
