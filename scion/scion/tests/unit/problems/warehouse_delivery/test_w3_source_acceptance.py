from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path

import pytest

import scion.problems.warehouse_delivery.w3_source_acceptance as source_acceptance
from scion.problems.warehouse_delivery.w3_source_acceptance import (
    FixedSourceReviewClosure,
    RootFixedSourceAcceptanceReceipt,
    RootOwnedGitSourceVerifier,
    W3_SOURCE_ACCEPTANCE_LOGICAL_PATH,
    WarehouseW3SourceAcceptanceError,
)
from scion.tests.unit.problems.warehouse_delivery.test_w3_installation import (
    _canonical,
    _prepared_inputs,
)

_ROOT_COMMIT = hashlib.sha1(b"root fixed source commit").hexdigest()
_ROOT_TREE = hashlib.sha1(b"root fixed source tree").hexdigest()


def _accepted(tmp_path, monkeypatch):
    _intent, source, objects, *_rest = _prepared_inputs(tmp_path, monkeypatch)
    sealed = next(
        item
        for item in objects
        if item.adapter.logical_path == W3_SOURCE_ACCEPTANCE_LOGICAL_PATH
    )
    return source, RootFixedSourceAcceptanceReceipt.from_bytes(sealed.raw)


def test_fixed_source_acceptance_round_trip_closes_two_independent_reviews(
    tmp_path,
    monkeypatch,
) -> None:
    source, accepted = _accepted(tmp_path, monkeypatch)

    assert RootFixedSourceAcceptanceReceipt.from_bytes(accepted.raw) == accepted
    assert accepted.source_receipt == source.receipt
    assert tuple(item.review_scope for item in accepted.reviews) == (
        "launch_readiness",
        "root_installation",
    )
    assert (
        len({(item.reviewer_identity, item.task_identity) for item in accepted.reviews})
        == 2
    )


def test_fixed_source_review_refuses_nonzero_p0_or_p1(
    tmp_path,
    monkeypatch,
) -> None:
    _source, accepted = _accepted(tmp_path, monkeypatch)
    value = json.loads(accepted.reviews[0].raw)
    value["p1_open"] = 1

    with pytest.raises(
        WarehouseW3SourceAcceptanceError,
        match="zero-P0/zero-P1",
    ):
        FixedSourceReviewClosure.from_bytes(_canonical(value))


@pytest.mark.parametrize("duplicate_field", ["reviewer_identity", "task_identity"])
def test_fixed_source_acceptance_requires_independent_reviewer_and_task_identities(
    tmp_path,
    monkeypatch,
    duplicate_field,
) -> None:
    source, accepted = _accepted(tmp_path, monkeypatch)
    first, second = accepted.reviews
    identity = {
        "reviewer_identity": first.reviewer_identity,
        "task_identity": first.task_identity,
    }
    identity[duplicate_field] = getattr(second, duplicate_field)
    duplicate_identity = FixedSourceReviewClosure.create(
        review_scope=first.review_scope,
        reviewer_identity=identity["reviewer_identity"],
        task_identity=identity["task_identity"],
        source_commit=first.source_commit,
        source_tree=first.source_tree,
        source_inventory_sha256=first.source_inventory_sha256,
        report_sha256=first.report_sha256,
        p0_open=0,
        p1_open=0,
        completed_at_utc=first.completed_at_utc,
    )

    with pytest.raises(
        WarehouseW3SourceAcceptanceError,
        match="dependency binding differs",
    ):
        RootFixedSourceAcceptanceReceipt.create(
            source=source,
            root_git_verification=accepted.root_git_verification,
            reviews=(duplicate_identity, second),
            accepted_at_utc=accepted.accepted_at_utc,
        )


def test_repository_content_walk_rejects_alternates_and_symlinks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "trusted.git"
    (repository / "objects" / "info").mkdir(parents=True)
    (repository / "refs").mkdir()
    (repository / "HEAD").write_bytes(b"ref: refs/heads/main\n")
    (repository / "config").write_bytes(b"[core]\n\tbare = true\n")
    monkeypatch.setattr(
        source_acceptance,
        "_open_root_owned_directory",
        lambda path, *, expected_uid: os.open(
            path,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
        ),
    )

    aggregate, identity = source_acceptance._root_owned_repository_content(
        repository,
        expected_uid=os.getuid(),
        expected_gid=os.getgid(),
    )
    assert len(aggregate) == 64
    assert identity.st_ino == repository.stat().st_ino

    alternates = repository / "objects" / "info" / "alternates"
    alternates.write_bytes(b"/tmp/untrusted-objects\n")
    with pytest.raises(
        WarehouseW3SourceAcceptanceError,
        match="external object authority",
    ):
        source_acceptance._root_owned_repository_content(
            repository,
            expected_uid=os.getuid(),
            expected_gid=os.getgid(),
        )
    alternates.unlink()
    (repository / "unsafe").symlink_to("/tmp")
    with pytest.raises(
        WarehouseW3SourceAcceptanceError,
        match="non-regular authority",
    ):
        source_acceptance._root_owned_repository_content(
            repository,
            expected_uid=os.getuid(),
            expected_gid=os.getgid(),
        )


class _RootGitRunner:
    def __init__(self, root: Path, responses: dict[tuple[str, ...], bytes]) -> None:
        self.root = root
        self.responses = responses

    def run(self, argv: tuple[str, ...], *, git_root: Path) -> bytes:
        assert git_root == self.root
        try:
            return self.responses[argv]
        except KeyError as exc:
            raise AssertionError(f"unexpected root Git argv: {argv!r}") from exc


def _root_git_verifier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    bare: bytes = b"true\n",
    config: bytes | None = None,
    replace_refs: bytes = b"",
) -> RootOwnedGitSourceVerifier:
    commit = _ROOT_COMMIT
    tree = _ROOT_TREE
    pyproject = b"[build-system]\nrequires=[]\n"
    tool = b"def main():\n    return 0\n"
    pyproject_oid = hashlib.sha1(
        f"blob {len(pyproject)}\0".encode("ascii") + pyproject
    ).hexdigest()
    tool_oid = hashlib.sha1(f"blob {len(tool)}\0".encode("ascii") + tool).hexdigest()
    root = tmp_path / "trusted.git"
    root.mkdir()
    prefix = (source_acceptance.FIXED_GIT, f"--git-dir={root}")
    responses = {
        (*prefix, "rev-parse", "--is-bare-repository"): bare,
        (*prefix, "rev-parse", "--is-shallow-repository"): b"false\n",
        (*prefix, "config", "--local", "--null", "--list"): (
            config
            if config is not None
            else b"core.bare\ntrue\0remote.origin.url\nfile:///trusted\0"
        ),
        (
            *prefix,
            "for-each-ref",
            "--format=%(refname)",
            "refs/replace",
        ): replace_refs,
        (*prefix, "rev-parse", "--verify", "refs/heads/main^{commit}"): (
            f"{commit}\n".encode("ascii")
        ),
        (*prefix, "rev-parse", "--verify", f"{commit}^{{commit}}"): (
            f"{commit}\n".encode("ascii")
        ),
        (*prefix, "rev-parse", "--verify", f"{commit}^{{tree}}"): (
            f"{tree}\n".encode("ascii")
        ),
        (
            *prefix,
            "ls-tree",
            "-rz",
            "--full-tree",
            f"{commit}:scion",
            "--",
            "pyproject.toml",
            "scion",
        ): (
            f"100644 blob {pyproject_oid}\tpyproject.toml".encode("ascii")
            + b"\0"
            + f"100644 blob {tool_oid}\tscion/tools/scion_w3_install.py".encode("ascii")
            + b"\0"
        ),
        (*prefix, "cat-file", "blob", pyproject_oid): pyproject,
        (*prefix, "cat-file", "blob", tool_oid): tool,
        (*prefix, "config", "--get", "remote.origin.url"): b"file:///trusted\n",
    }
    identity = root.stat()
    monkeypatch.setattr(
        source_acceptance,
        "_root_owned_repository_content",
        lambda path, *, expected_uid: ("c" * 64, identity),
    )
    monkeypatch.setattr(
        source_acceptance,
        "_validate_root_owned_directory",
        lambda path, *, expected_uid: identity,
    )
    monkeypatch.setattr(
        source_acceptance,
        "_hash_stable_regular",
        lambda path, *, expected_uid: ("d" * 64, identity),
    )
    return RootOwnedGitSourceVerifier(
        runner=_RootGitRunner(root, responses),
        expected_uid=os.getuid(),
    )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"bare": b"false\n"}, "complete bare mirror"),
        (
            {"config": (b"core.bare\ntrue\0" b"remote.origin.promisor\ntrue\0")},
            "delegates external authority",
        ),
        ({"replace_refs": b"refs/replace/main\n"}, "replacement refs"),
    ],
)
def test_root_git_verifier_rejects_nonbare_or_external_object_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kwargs: dict[str, bytes],
    message: str,
) -> None:
    verifier = _root_git_verifier(tmp_path, monkeypatch, **kwargs)

    with pytest.raises(WarehouseW3SourceAcceptanceError, match=message):
        verifier.verify(
            tmp_path / "trusted.git",
            source_commit=_ROOT_COMMIT,
            remote_name="origin",
            remote_ref="refs/heads/main",
        )


def test_root_git_verifier_binds_complete_bare_repository_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verifier = _root_git_verifier(tmp_path, monkeypatch)

    source, receipt = verifier.verify(
        tmp_path / "trusted.git",
        source_commit=_ROOT_COMMIT,
        remote_name="origin",
        remote_ref="refs/heads/main",
    )

    assert source.receipt.source_commit == _ROOT_COMMIT
    assert receipt.trusted_git_content_sha256 == "c" * 64
