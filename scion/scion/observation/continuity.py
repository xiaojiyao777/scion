"""Ordinary public corpus and separate complete source copies; no runtime restore."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile

from scion.observation.source import ObservationError, SourceCopier
from scion.problem.public_input import decode_public_json

KINDS = {"note", "script", "input", "output", "request", "observation", "source"}
REQUIRED = {"ref", "kind", "bytes", "phase", "source_condition"}
OPTIONAL = {"origin_ref", "origin_scope", "branch", "session", "supersedes_ref",
            "dependencies", "availability", "source_path", "missing_dependencies", "source_availability", "reference_origins"}


def relative(value):
    return (type(value) is str and bool(value) and len(value) <= 4096
            and "\\" not in value and "\x00" not in value
            and all(p not in {"", ".", ".."} for p in value.split("/")))


def validate_entry(entry):
    if (type(entry) is not dict or not REQUIRED <= set(entry) or set(entry) - REQUIRED - OPTIONAL
            or not relative(entry["ref"]) or entry["kind"] not in KINDS
            or type(entry["bytes"]) is not int or entry["bytes"] < 0
            or entry["phase"] not in {"hypothesis", "code", "public"}
            or entry.get("availability", "available") not in {"available", "unavailable"}):
        raise ValueError("invalid material entry")
    if entry.get("source_availability", "projection_only") not in {"retained", "projection_only", "unavailable"}:
        raise ValueError("invalid source availability")
    for key in ("origin_ref", "origin_scope", "supersedes_ref", "source_path"):
        if key in entry and not relative(entry[key]):
            raise ValueError("invalid material location")
    if "branch" in entry and (type(entry["branch"]) is not str or not relative(entry["branch"])):
        raise ValueError("invalid material branch")
    if "session" in entry and (type(entry["session"]) is not int or entry["session"] < 0):
        raise ValueError("invalid material session")
    for key in ("dependencies", "missing_dependencies"):
        if key in entry and (type(entry[key]) is not list or any(not relative(r) for r in entry[key])):
            raise ValueError("invalid material dependencies")
    origins = entry.get("reference_origins", [])
    if type(origins) is not list or any(type(o) is not dict or set(o) != {"scope", "ref"}
            or not relative(o["scope"]) or not relative(o["ref"]) for o in origins):
        raise ValueError("invalid material reference origins")
    condition = entry["source_condition"]
    if condition is not None:
        if (type(condition) is not dict or not {"role", "source_ref"} <= set(condition)
                or set(condition) - {"role", "source_ref", "draft_revision"}
                or condition["role"] not in {"current", "base", "draft"}
                or not relative(condition["source_ref"])
                or ("draft_revision" in condition and (type(condition["draft_revision"]) is not int
                    or condition["draft_revision"] < 0))):
            raise ValueError("invalid source condition")


class ResearchContinuity:
    def __init__(self, controller):
        self.controller, self.service = controller, controller.service
        self.root = self.service.materials.root / "continuity"
        self.root.mkdir()
        (self.root / "files").mkdir()
        self.rows = []
        self.local_refs = {}
        self.sources = {}
        self.source_count = 0
        self.import_count = 0
        self._save([])

    def _save(self, rows):
        """Publish the entire index atomically; never select a recent subset."""
        target = self.root / ".index.pending"
        self.service._json(target, {"schema_version": 1, "entries": rows})
        target.replace(self.root / "index.json")

    def _copier(self, root, *, full=False):
        b = self.service.budget
        remaining = b.max_storage_bytes - self.service.materials.used_bytes()
        if remaining <= 0:
            raise ObservationError("GLOBAL_RESEARCH_LIMIT")
        return SourceCopier(forbidden_files=() if full else self.controller.exclusions(root),
            max_files=b.max_files_per_action, max_bytes=min(b.max_source_bytes, remaining))

    def _copy_file(self, root, ref, target):
        copier = self._copier(root)
        copier.copy(root, ref, target)
        return target / ref

    def _publish(self, entries, root, *, scope, imported=False):
        """Copy one closed set, then publish all rows; failed copies stay unindexed."""
        staging = Path(tempfile.mkdtemp(prefix=".materials-", dir=self.root))
        name = f"set-{len(tuple((self.root / 'files').iterdir())) + 1:06d}"
        mapping = {e["ref"]: f"files/{name}/{i:06d}.bin" for i, e in enumerate(entries)}
        rows = []
        existing = {row["ref"] for row in self.rows}
        def mapped(ref):
            if not imported and ref.startswith("continuity/") and ref[len("continuity/"):] in existing:
                return ref[len("continuity/"):]
            return mapping.get(ref, self.local_refs.get(ref, f"missing/{scope}/{ref}") if not imported else f"missing/{scope}/{ref}")
        for i, entry in enumerate(entries):
            validate_entry(entry)
            original = entry["ref"]
            row = deepcopy(entry)
            row.update(ref=mapping[original], origin_ref=entry.get("origin_ref", original),
                       origin_scope=(scope + "/" + entry.get("origin_scope", "local")) if imported else scope)
            row["reference_origins"] = [
                {"scope": scope + "/" + old["scope"], "ref": old["ref"]}
                for old in entry.get("reference_origins", [])
            ] + [{"scope": scope, "ref": original}]
            if imported and row["source_condition"] is not None:
                row["source_condition"]["source_ref"] = scope + "/" + row["source_condition"]["source_ref"]
            row["availability"] = entry.get("availability", "available")
            if imported:
                row["source_availability"] = "projection_only"
            # Even a declared unavailable file cannot smuggle a symlink into imports.
            probe = root
            for part in original.split("/"):
                probe /= part
                if probe.is_symlink():
                    raise ObservationError("PUBLIC_CLOSURE_INVALID")
            if row["availability"] == "available":
                if not probe.exists():
                    row["availability"] = "unavailable"
                else:
                    copied = self._copy_file(root, original, staging / f"copy-{i}")
                    if copied.stat().st_size != row["bytes"]:
                        raise ObservationError("MATERIAL_IMPORT_INVALID" if imported else "PERSISTENCE_ERROR")
                    copied.rename(staging / f"{i:06d}.bin")
            dependencies = entry.get("dependencies", [])
            row["dependencies"] = [mapped(ref) for ref in dependencies]
            if "supersedes_ref" in row:
                old = row["supersedes_ref"]
                row["supersedes_ref"] = mapped(old)
            rows.append(row)
        # Only copied bytes are published; temporary nested directories may be empty.
        staging.rename(self.root / "files" / name)
        proposed = [*deepcopy(self.rows), *rows]
        present = {row["ref"] for row in proposed if row.get("availability") == "available"}
        for row in proposed:
            row["missing_dependencies"] = [ref for ref in row.get("dependencies", []) if ref not in present]
        self._save(proposed)
        self.rows = proposed
        if not imported:
            self.local_refs.update(mapping)

    def import_directory(self, directory):
        root = Path(directory).absolute()
        if root == self.root or self.service.materials.root in root.parents:
            raise ObservationError("MATERIAL_IMPORT_INVALID")
        b = self.service.budget
        staging = Path(tempfile.mkdtemp(prefix=".import-index-", dir=self.service.materials.root))
        try:
            self._copy_file(root, "index.json", staging)
        except ObservationError as error:
            if error.reason_code in {"PUBLIC_DEPENDENCY_UNAVAILABLE", "SOURCE_UNAVAILABLE"}:
                raise ObservationError("MATERIAL_IMPORT_INVALID") from None
            raise
        try:
            value = decode_public_json((staging / "index.json").read_bytes(),
                max_bytes=b.max_source_bytes, max_depth=b.max_json_depth,
                max_collection_items=b.max_collection_items)
            if (type(value) is not dict or set(value) != {"schema_version", "entries"}
                    or type(value["schema_version"]) is not int or value["schema_version"] != 1
                    or type(value["entries"]) is not list):
                raise ValueError()
            entries = value["entries"]
            for entry in entries:
                validate_entry(entry)
            if len({e["ref"] for e in entries}) != len(entries):
                raise ValueError()
        except (ValueError, TypeError, KeyError):
            raise ObservationError("MATERIAL_IMPORT_INVALID") from None
        self.import_count += 1
        self._publish(entries, root, scope=f"import-{self.import_count:06d}", imported=True)

    def visible_entries(self):
        rows = deepcopy(self.rows)
        for row in rows:
            condition = row["source_condition"]
            source_ref = condition["source_ref"] if condition else ""
            if source_ref.startswith("retained-") and "/" not in source_ref:
                tree = self.service.materials.root / "retained_sources" / source_ref / "tree"
                row["source_availability"] = "retained" if tree.is_dir() else "unavailable"
            else:
                row["source_availability"] = "projection_only"
            path = self.root / row["ref"]
            if not path.is_file():
                row["availability"] = "unavailable"
        present = {row["ref"] for row in rows if row.get("availability") == "available"}
        for row in rows:
            row["missing_dependencies"] = [ref for ref in row.get("dependencies", []) if ref not in present]
            for key in ("ref", "supersedes_ref"):
                if key in row:
                    row[key] = "continuity/" + row[key]
            for key in ("dependencies", "missing_dependencies"):
                row[key] = ["continuity/" + ref for ref in row.get(key, [])]
        return rows

    def publish_session(self, session):
        entries = [deepcopy(e) for e in session.entries if e["ref"] in session.own_refs
                   or (e["phase"] == "public" and e["ref"] not in self.local_refs)]
        for entry in entries:
            entry.update(branch=session.branch, session=session.ordinal)
        if entries:
            self._publish(entries, self.service.materials.root, scope=f"session-{session.ordinal:06d}")

    def retain_source(self, root, *, branch="campaign", kind="current"):
        """Save actual complete bytes privately; expose only declared workspace files."""
        root = Path(root).absolute()
        if not root.is_dir():
            raise ObservationError("SOURCE_UNAVAILABLE")
        key = str(root)
        if key in self.sources:
            saved = self.service.materials.root / "retained_sources" / self.sources[key]["source_ref"] / "tree"
            if not saved.is_dir():
                raise ObservationError("SOURCE_UNAVAILABLE")
            return deepcopy(self.sources[key])
        self.source_count += 1
        label = f"retained-{self.source_count:06d}"
        directory = self.service.materials.root / "retained_sources"
        directory.mkdir(exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".source-", dir=directory))
        tree = staging / "tree"
        tree.mkdir()
        copier = self._copier(root, full=True)
        pending = [root]
        count = 0
        while pending:
            current = pending.pop()
            for path in sorted(current.iterdir()):
                count += 1
                if count > self.service.budget.max_files_per_action:
                    raise ObservationError("LIMIT_NOT_AVAILABLE")
                if path.is_symlink():
                    raise ObservationError("PUBLIC_CLOSURE_INVALID")
                if path.name == "__pycache__" and path.is_dir():
                    continue
                relative_path = str(path.relative_to(root))
                if path.is_dir():
                    (tree / relative_path).mkdir(parents=True, exist_ok=True)
                    pending.append(path)
                else:
                    copier.copy(root, relative_path, tree)
        projection = staging / "projection"
        public = self._copier(root)
        paths = []
        for path in self.service.spec.subject_workspace_paths:
            paths += public.copy(root, path, projection)
        for path in self.service.spec.subject_optional_workspace_paths:
            paths += public.copy(root, path, projection, optional=True)
        condition = {"role": "current", "source_ref": label}
        entries = [{"ref": path, "kind": "source", "bytes": (projection / path).stat().st_size,
            "phase": "hypothesis", "source_condition": condition, "source_path": path,
            "branch": branch, "session": 0} for path in paths]
        # Record real paths only on the operator side; never put this record in the corpus.
        self.service._json(staging / "source.json", {"original_path": str(root), "kind": kind,
            "branch": branch, "public_paths": paths})
        destination = directory / label
        staging.rename(destination)
        self._publish(entries, destination / "projection", scope=label)
        self.sources[key] = condition
        return deepcopy(condition)
