"""Preserve the actual development scratch before each execution stage.

Private scratch copies are never material entries or executable source bindings.
Only the existing C source inventory and declared public dependencies are indexed.
"""
from copy import deepcopy
from pathlib import Path

from scion.observation.development_materials import _bytes
from scion.observation.source import ObservationError, SourceCopier


def capture_source(materials, *, stage, workspace, problem_runtime_root, problem_root,
                   algorithm_paths, workspace_paths, problem_package_paths):
    pending = materials.pending
    if (pending is None or stage not in {"probe", "host_checks"}
            or stage in pending["stages"] or "host_checks" in pending["stages"]):
        raise ObservationError("INTERNAL_ERROR")
    session = materials.session
    svc, budget = session.service, session.service.budget
    root, runtime, original = map(Path, (workspace, problem_runtime_root, problem_root))
    directory = str(Path(pending["request_ref"]).parent)
    private = svc.materials.root / ("private-" + directory) / stage
    tree = private / "tree"
    tree.mkdir(parents=True, exist_ok=False)
    free = budget.max_storage_bytes - svc.materials.used_bytes() - pending["result_cap"]
    if free <= 0:
        raise ObservationError("GLOBAL_RESEARCH_LIMIT")
    copier = SourceCopier(forbidden_files=(), max_files=budget.max_files_per_action,
                          max_bytes=min(budget.max_source_bytes, free))
    # Include ordinary non-Python files and empty directories in the private
    # prepared tree. No glob reconstruction and no follow-links traversal.
    remaining, visited = [root], 0
    while remaining:
        current = remaining.pop()
        for path in current.iterdir():
            visited += 1
            if visited > budget.max_files_per_action:
                raise ObservationError("LIMIT_NOT_AVAILABLE")
            if path.is_symlink():
                raise ObservationError("PUBLIC_CLOSURE_INVALID")
            if path.name == "__pycache__" and path.is_dir():
                continue
            relative = str(path.relative_to(root))
            if path.is_dir():
                (tree / relative).mkdir(parents=True, exist_ok=True)
                remaining.append(path)
            else:
                copier.copy(root, relative, tree)

    forbidden = set(session.controller.exclusions(root))
    forbidden.update(session.controller.exclusions(runtime))
    # A frozen formal file copied into scratch has a new inode. Carry the
    # original path exclusions into both execution locations before projecting.
    for origin, destination in ((Path(session.source_root), root),
                                (original, root), (original, runtime)):
        for path in tuple(forbidden):
            try:
                relative = path.relative_to(origin.absolute())
            except ValueError:
                continue
            forbidden.add(destination / relative)
    public = SourceCopier(forbidden_files=tuple(forbidden),
        max_files=budget.max_files_per_action - copier.files,
        max_bytes=min(budget.max_source_bytes, free) - copier.bytes)
    condition = deepcopy(pending["result_entry"]["source_condition"])
    record_ref = f"{directory}/{stage}/source.json"
    files, entries = [], []
    for location, source, paths in (
        ("workspace", root, (*algorithm_paths, *workspace_paths)),
        ("problem", runtime, problem_package_paths),
    ):
        prefix = f"{directory}/{stage}/source/{location}"
        for path in paths:
            copied = public.copy(source, path, svc.materials.root / prefix)
            for relative in copied:
                ref = f"{prefix}/{relative}"
                files.append({"location": location, "path": relative, "ref": ref})
                entries.append({"ref": ref, "kind": "source",
                    "bytes": (svc.materials.root / ref).stat().st_size,
                    "phase": "code", "source_condition": deepcopy(condition),
                    "source_path": relative, "source_availability": "projection_only"})
    # Runtime layout, suite source and host paths belong only to operator audit.
    svc._json(private / "audit.json", {"stage": stage, "workspace": str(root),
        "problem_runtime_root": str(runtime), "problem_root": str(original),
        "capture_state": "captured_before_execution", "request_ref": pending["request_ref"]})
    request = next(e for e in session.entries if e["ref"] == pending["request_ref"])
    dependencies = [pending["request_ref"], *request.get("dependencies", []),
                    *(file["ref"] for file in files)]
    record = {"schema_version": 1, "source_kind": "development_draft",
        "capture_scope": "public_test_source", "stage": stage,
        "capture_state": "captured_before_execution", "source_condition": condition,
        "request_ref": pending["request_ref"], "files": files,
        "execution_dependencies": "partial_public_projection"}
    raw = _bytes(record)
    entries.append({"ref": record_ref, "kind": "source", "bytes": len(raw),
        "phase": "code", "source_condition": condition,
        "source_availability": "projection_only", "dependencies": dependencies})
    future_result = deepcopy(pending["result_entry"])
    future_result["dependencies"].extend([*pending["source_refs"], record_ref])
    index_cap = len(_bytes({"phase": "code", "entries": [*session.entries, *entries, future_result],
                           "usage": svc.usage})) + 512
    if svc.materials.used_bytes() + len(raw) + pending["result_cap"] + 2 * index_cap > budget.max_storage_bytes:
        raise ObservationError("GLOBAL_RESEARCH_LIMIT")
    svc._bytes(svc.materials.root / record_ref, raw)
    # Publish only the complete stage. Partial private/public files remain
    # unindexed on failure; the shared fault stops the next research dispatch.
    previous = len(session.entries)
    session.entries.extend(entries)
    try:
        session.persist_index()
    except BaseException:
        del session.entries[previous:]
        raise
    session.own_refs.update(entry["ref"] for entry in entries)
    pending["source_refs"].append(record_ref)
    pending["stages"].append(stage)
    return record_ref
