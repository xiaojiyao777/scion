"""Readback of C's own development requests and already-bounded feedback.

No test execution, readiness, or source reconstruction lives here. The callback
has a separate budget; only file/index work is charged to the material service.
"""
from contextlib import contextmanager
from copy import deepcopy
import json
import math

from scion.observation.config import PublicResearchStop
from scion.observation.source import ObservationError


def _bytes(value):
    return json.dumps(value, ensure_ascii=True, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


class DevelopmentTestMaterials:
    def __init__(self, session):
        self.session = session
        self.ordinal = 0
        self.pending = None

    @contextmanager
    def _host_work(self):
        session = self.session
        try:
            if session.closed or session.phase != "code":
                raise ObservationError("INTERNAL_ERROR")
            if session.controller.failure_reason:
                raise ObservationError(session.controller.failure_reason)
            if session.service.stopped:
                raise ObservationError("GLOBAL_RESEARCH_LIMIT")
            with session.service.account_host_work():
                yield
            if session.service.stopped:
                raise ObservationError("GLOBAL_RESEARCH_LIMIT")
        except (Exception, KeyboardInterrupt) as error:
            with session.service.account_host_work():
                session.controller.record_material_failure(error)
            raise PublicResearchStop(session.controller.failure_reason, phase="code") from None

    def begin(self, *, draft_revision, public_draft_files, falsifier_source,
              max_result_chars):
        with self._host_work():
            if self.pending is not None:
                raise ObservationError("INTERNAL_ERROR")
            session, svc = self.session, self.session.service
            self.ordinal += 1
            directory = f"development-tests/session-{session.ordinal:06d}/{self.ordinal:06d}"
            request_ref = f"{directory}/request.json"
            result_ref = f"{directory}/result.json"
            condition = {"role": "draft", "source_ref": request_ref,
                         "draft_revision": draft_revision}
            base = deepcopy(session.source_condition) or {
                "role": "base", "source_ref": f"session-{session.ordinal:06d}/base"}
            base["role"] = "base"
            files, entries, drafts = {}, [], []

            def add(ref, kind, content, **metadata):
                files[ref] = content
                entries.append({"ref": ref, "kind": kind, "bytes": len(content),
                    "phase": "code", "source_condition": deepcopy(condition),
                    "source_availability": "projection_only", **metadata})

            script_ref = None
            if falsifier_source is not None:
                script_ref = f"{directory}/falsifier.py"
                add(script_ref, "script", falsifier_source.encode("utf-8"))
            for index, change in enumerate(public_draft_files):
                ref = f"{directory}/draft-{index:06d}.txt"
                # The filename is metadata, never a destination chosen by C.
                add(ref, "source", change["code_content"].encode("utf-8"),
                    source_path=change["file_path"])
                drafts.append({"file_path": change["file_path"],
                               "action": change["action"], "ref": ref})
            request = {"schema_version": 1, "operation": "development_test",
                "ordinal": self.ordinal, "draft_revision": draft_revision,
                "script_ref": script_ref, "draft_files": drafts,
                "source_condition": condition, "base_source_condition": base,
                "capture_scope": "request_only"}
            dependencies = [*([script_ref] if script_ref else []), *(d["ref"] for d in drafts)]
            add(request_ref, "request", _bytes(request), dependencies=dependencies)
            # Bounded feedback is ASCII JSON. The extra 2 KiB bounds the fixed
            # result envelope (refs, enums, two finite usage scalars and nulls).
            result_cap = max_result_chars + 2048
            result_entry = {"ref": result_ref, "kind": "output", "bytes": result_cap,
                "phase": "code", "source_condition": condition,
                "source_availability": "projection_only", "dependencies": [request_ref]}
            future = [*session.entries, *entries]
            # Sequential execution: no other material action can spend this
            # space while the test callback runs. Include BOTH index writes;
            # the existing service conservatively charges replacements in full.
            index_cap = len(_bytes({"phase": "code", "entries": [*future, result_entry],
                                   "usage": svc.usage})) + 512
            required = sum(map(len, files.values())) + result_cap + 2 * index_cap
            if (len(files) + 2 > svc.budget.max_files_per_action
                    or sum(map(len, files.values())) > svc.budget.max_source_bytes
                    or svc.materials.used_bytes() + required > svc.budget.max_storage_bytes):
                raise ObservationError("GLOBAL_RESEARCH_LIMIT")
            destination = svc.materials.root / directory
            destination.mkdir(parents=True, exist_ok=False)
            for ref, content in files.items():
                svc._bytes(svc.materials.root / ref, content)
            session.entries.extend(entries)
            session.own_refs.update(files)
            session.persist_index()
            self.pending = {"request_ref": request_ref, "result_ref": result_ref,
                            "result_entry": result_entry, "result_cap": result_cap,
                            "source_refs": [], "stages": []}
            return request_ref

    def capture_source(self, **kwargs):
        from scion.observation.development_sources import capture_source
        with self._host_work():
            return capture_source(self, **kwargs)

    def finish(self, *, request_ref, bounded_result, execution_state, callback_wall_seconds):
        with self._host_work():
            pending = self.pending
            if (pending is None or request_ref != pending["request_ref"]
                    or execution_state not in {"not_started", "returned", "interrupted", "unknown"}
                    or not math.isfinite(callback_wall_seconds) or callback_wall_seconds < 0):
                raise ObservationError("INTERNAL_ERROR")
            result = {"schema_version": 1, "operation": "development_test",
                "request_ref": request_ref, "feedback": deepcopy(bounded_result),
                "execution_state": execution_state,
                "capture_scope": "public_test_source" if pending["source_refs"] else "request_only",
                "tested_source_refs": list(pending["source_refs"]),
                "usage": {"callback_wall_seconds": callback_wall_seconds,
                          "child_cpu_seconds": None, "child_cpu_unavailable_reason": "not_measured"}}
            raw = _bytes(result)
            if len(raw) > pending["result_cap"]:
                raise ObservationError("INTERNAL_ERROR")
            svc, session = self.session.service, self.session
            svc._bytes(svc.materials.root / pending["result_ref"], raw)
            entry = deepcopy(pending["result_entry"])
            entry["dependencies"].extend(pending["source_refs"])
            entry["bytes"] = len(raw)
            session.entries.append(entry)
            session.own_refs.add(entry["ref"])
            session.persist_index()
            self.pending = None
            return entry["ref"]
