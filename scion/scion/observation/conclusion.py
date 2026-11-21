"""H-only conclusion material; the campaign loop owns stopping."""
from copy import deepcopy
import json

from scion.core.research_lifecycle import ResearchConclusion
from scion.observation.config import PublicResearchStop, TERMINAL_REASONS
from scion.observation.source import ObservationError


def conclude_research(session, raw):
    if session.closed or session.conclusion is not None:
        raise PublicResearchStop("INTERNAL_ERROR", phase=session.phase)
    try:
        if session.phase != "hypothesis" or not session.investigation:
            raise ObservationError("REQUEST_INVALID")
        if (type(raw) is not dict or set(raw) not in ({"action", "reason"}, {"action", "reason", "note_refs"})
                or raw.get("action") != "conclude_research"
                or type(raw.get("reason")) is not str or not raw["reason"].strip()
                or raw["reason"] != raw["reason"].strip() or len(raw["reason"]) > 2000):
            raise ObservationError("REQUEST_INVALID")
        refs, svc = raw.get("note_refs", []), session.service
        if type(refs) is not list or len(refs) > svc.budget.max_collection_items:
            raise ObservationError("REQUEST_INVALID")
        if any(type(ref) is not str or ref not in session.own_refs for ref in refs) or len(set(refs)) != len(refs):
            raise ObservationError("REF_NOT_VISIBLE")
        if any(session._entry(ref)["kind"] != "note" for ref in refs):
            raise ObservationError("REF_NOT_VISIBLE")
        with svc.account_host_work():
            if svc.stopped or session.controller.failure_reason:
                raise PublicResearchStop(session.controller.failure_reason or "GLOBAL_RESEARCH_LIMIT", phase="hypothesis")
            # Read selected bytes through the existing safe material boundary;
            # notes are append-only and never rewritten by the provider.
            size = sum(len(session._bytes(ref, "note")) for ref in refs)
            body = {"schema_version": 1, "operation": "research_conclusion",
                "reason": raw["reason"], "note_refs": list(refs),
                "source_condition": deepcopy(session.source_condition)}
            content = json.dumps(body, ensure_ascii=True, allow_nan=False).encode()
            if size + len(content) > svc.budget.max_input_bytes:
                raise ObservationError("INPUT_INVALID")
            ref = svc.materials.append("note", content)
            # Keep the saved original address even if indexing/publishing fails.
            # Only the pipeline's post-close checks can accept normal completion.
            session.conclusion = ResearchConclusion(ref)
            session._add(ref, "note")
            session.entries[-1]["dependencies"] = list(refs)
            session.persist_index()
        if svc.stopped:
            raise PublicResearchStop("GLOBAL_RESEARCH_LIMIT", phase="hypothesis")
        return session.conclusion
    except ObservationError as error:
        if error.reason_code not in TERMINAL_REASONS:
            return {"action": "conclude_research", "ok": False, "reason_code": error.reason_code}
        session.controller.record_material_failure(error)
        raise PublicResearchStop(session.controller.failure_reason, phase="hypothesis") from None
    except (OSError, KeyboardInterrupt) as error:
        session.controller.record_material_failure(error)
        raise PublicResearchStop(session.controller.failure_reason, phase="hypothesis") from None
