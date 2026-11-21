"""Bounded ordinary source copies; no candidate imports or source reconstruction."""
from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scion.problem.public_observation import PublicObservationSpec


class ObservationError(ValueError):
    def __init__(self, reason_code: str):
        self.reason_code = reason_code
        super().__init__(reason_code)


@dataclass(frozen=True)
class SourceBinding:
    root: Path
    role: str
    source_ref: str
    config: dict[str, Any]

    def __post_init__(self):
        if (self.role not in {"current", "base", "draft"} or type(self.source_ref) is not str
                or not self.source_ref or any(p in {"", ".", ".."} for p in self.source_ref.split("/"))
                or "\\" in self.source_ref):
            raise ObservationError("SOURCE_UNAVAILABLE")


class SourceCopier:
    def __init__(self, *, forbidden_files: tuple[Path, ...], max_files: int, max_bytes: int):
        self.forbidden = {p.resolve() for p in forbidden_files}
        self.forbidden_inodes = set()
        for p in forbidden_files:
            if p.exists():
                info = p.stat()
                self.forbidden_inodes.add((info.st_dev, info.st_ino))
        self.max_files, self.max_bytes = max_files, max_bytes
        self.files = self.bytes = 0
        self.entries = 0

    def copy(self, root: Path, relative: str, destination: Path, *, optional=False):
        parts = relative.split("/")
        if not relative or any(p in {"", ".", ".."} for p in parts) or "\\" in relative:
            raise ObservationError("PUBLIC_CLOSURE_INVALID")
        root = Path(root).absolute()
        if ".." in root.parts:
            raise ObservationError("PUBLIC_CLOSURE_INVALID")
        current = root
        # Check ancestors too: resolving first would hide a source-root symlink.
        for part in root.parents:
            if part.is_symlink():
                raise ObservationError("PUBLIC_CLOSURE_INVALID")
        if root.is_symlink():
            raise ObservationError("PUBLIC_CLOSURE_INVALID")
        for part in parts:
            current = current / part
            if current.is_symlink():
                raise ObservationError("PUBLIC_CLOSURE_INVALID")
        if not current.exists():
            if optional:
                return []
            raise ObservationError("PUBLIC_DEPENDENCY_UNAVAILABLE")
        if current.is_dir():
            found = []
            entries = []
            for entry in current.iterdir():
                self.entries += 1
                if self.entries > self.max_files:
                    raise ObservationError("LIMIT_NOT_AVAILABLE")
                entries.append(entry)
            for entry in sorted(entries):
                if entry.is_symlink():
                    raise ObservationError("PUBLIC_CLOSURE_INVALID")
                if entry.name == "__pycache__":
                    continue  # generated caches are not the algorithm's source
                child = relative + "/" + entry.name
                if entry.is_dir() or entry.suffix == ".py":
                    found.extend(self.copy(root, child, destination))
                else:
                    raise ObservationError("PUBLIC_CLOSURE_INVALID")
            return found
        try:
            # O_NOFOLLOW must apply to every component, not just the leaf.
            parent_fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
            try:
                for part in (*root.parts[1:], *parts[:-1]):
                    next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
                    os.close(parent_fd)
                    parent_fd = next_fd
                fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent_fd)
            finally:
                os.close(parent_fd)
        except FileNotFoundError:
            raise ObservationError("SOURCE_UNAVAILABLE") from None
        except OSError:
            raise ObservationError("PUBLIC_CLOSURE_INVALID") from None
        try:
            before = os.fstat(fd)
            if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                    or current.resolve() in self.forbidden
                    or (before.st_dev, before.st_ino) in self.forbidden_inodes):
                raise ObservationError("PUBLIC_CLOSURE_INVALID")
            if self.files + 1 > self.max_files or self.bytes + before.st_size > self.max_bytes:
                raise ObservationError("LIMIT_NOT_AVAILABLE")
            with os.fdopen(fd, "rb", closefd=False) as stream:
                data = stream.read(self.max_bytes - self.bytes + 1)
            after = os.fstat(fd)
            if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise ObservationError("SOURCE_UNAVAILABLE")
            if len(data) != before.st_size:
                raise ObservationError("SOURCE_UNAVAILABLE")
        finally:
            os.close(fd)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise ObservationError("PUBLIC_CLOSURE_INVALID")
        target.write_bytes(data)
        self.files += 1
        self.bytes += len(data)
        return [relative]


def namespace(root: Path):
    """Empty namespace initializers, never installed framework __init__ code."""
    for directory in [root, *sorted(p for p in root.rglob("*") if p.is_dir())]:
        if directory != root and not (directory / "__init__.py").exists():
            (directory / "__init__.py").write_text("")


def prepare_source(*, binding: SourceBinding, problem_root: Path,
                   framework_root: Path, spec: PublicObservationSpec, destination: Path,
                   copier: SourceCopier):
    if not binding.root.is_dir():
        raise ObservationError("SOURCE_UNAVAILABLE")
    subject = destination / "subject"
    subject.mkdir(parents=True)
    public = destination / "public"
    public.mkdir()
    for path in spec.fixture_paths:
        copier.copy(problem_root, path, public)
    available = []
    for path in spec.subject_workspace_paths:
        available += copier.copy(binding.root, path, subject)
    for path in spec.subject_optional_workspace_paths:
        available += copier.copy(binding.root, path, subject, optional=True)
    for stage, module, package_paths, neutral_paths in (
        ("runner", spec.runner_module, spec.subject_package_paths, spec.neutral_support_paths),
        ("checker", spec.checker_module, spec.checker_package_paths, spec.checker_neutral_support_paths),
    ):
        pieces = module.split(".")
        if len(pieces) != 4 or pieces[:2] != ["scion", "problems"] or pieces[-1] != "public_" + stage:
            raise ObservationError("PUBLIC_CLOSURE_INVALID")
        runtime = destination / stage
        runtime.mkdir()
        package = runtime.joinpath(*pieces[:-1])
        package.mkdir(parents=True)
        for path in package_paths:
            copier.copy(problem_root, path, package)
        for path in neutral_paths:
            copier.copy(framework_root, path, runtime / "scion")
        copier.copy(framework_root, "/".join(pieces[1:]) + ".py", runtime / "scion")
        copier.copy(framework_root, "observation/wire.py", runtime / "scion")
        copier.copy(framework_root / "observation", "bootstrap.py", runtime)
        namespace(runtime)
    return tuple(available)
