from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scion.problems.warehouse_delivery import w3_installation as installation_module
from scion.problems.warehouse_delivery.w3_composition import (
    EXPECTED_MANIFEST_NAME,
    EXPECTED_MANIFEST_SHA256,
    EXPECTED_NATIVE_ACCEPTANCE_RECORD_SHA256,
)
from scion.problems.warehouse_delivery.w3_candidate_gate import (
    W3_WHEEL_LOGICAL_PATH,
    W3_WHEEL_SEALED_PATH,
)
from scion.problems.warehouse_delivery.w3_installation import (
    ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256,
    AuthorityInputAdapter,
    CandidateReceipt,
    CandidateRootIdentity,
    CandidateSelectionCommit,
    CandidateSelectionIntent,
    CandidateSelectionOwner,
    EnvironmentContentReceipt,
    GitSourceAcquirer,
    SealedStoreObject,
    SealedStoreReceipt,
    W3_CLOSE_TEMPLATE_LOGICAL_PATH,
    W3_COMPOSITION_LOGICAL_PATH,
    W3_NATIVE_RECORD_LOGICAL_PATH,
    W3_RUN_TEMPLATE_LOGICAL_PATH,
    W3_TOOL_LOGICAL_PATH,
    WarehouseW3InstallationError,
    build_warehouse_installation,
    build_warehouse_launch_authority,
    derive_candidate_paths,
    derive_launch_id,
    derive_selection_key,
    prepare_candidate,
    verify_candidate,
)
from scion.problems.warehouse_delivery.w3_source_acceptance import (
    FixedSourceReviewClosure,
    RootFixedSourceAcceptanceReceipt,
    RootGitVerificationReceipt,
    W3_SOURCE_ACCEPTANCE_LOGICAL_PATH,
    W3_SOURCE_ACCEPTANCE_SEALED_PATH,
    source_inventory_sha256,
)

COMMIT = hashlib.sha1(b"w3 launch commit").hexdigest()
TREE = hashlib.sha1(b"w3 launch tree").hexdigest()
NONCE = hashlib.sha256(b"w3 nonce").hexdigest()
REMOTE = "origin"
REMOTE_REF = "refs/heads/v0.4-dev"
REMOTE_URL = "ssh://git.example.test/scion.git"


def _canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _blob_oid(raw: bytes) -> str:
    return hashlib.sha1(f"blob {len(raw)}\0".encode("ascii") + raw).hexdigest()


class _FakeRunner:
    def __init__(
        self,
        root: Path,
        responses: dict[tuple[str, ...], bytes],
    ) -> None:
        self.root = root
        self.responses = responses
        self.calls: list[tuple[str, ...]] = []

    def run(self, argv: tuple[str, ...], *, cwd: Path) -> bytes:
        assert type(argv) is tuple
        assert cwd == self.root
        self.calls.append(argv)
        if argv not in self.responses:
            raise AssertionError(f"unexpected Git argv: {argv!r}")
        return self.responses[argv]


def test_subprocess_git_runner_disables_replace_objects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class _Completed:
        returncode = 0
        stdout = b"exact git output\n"
        stderr = b""

    def run(argv: tuple[str, ...], **kwargs: object) -> _Completed:
        captured["argv"] = argv
        captured.update(kwargs)
        return _Completed()

    monkeypatch.setenv("GIT_OBJECT_DIRECTORY", "/tmp/untrusted-object-directory")
    monkeypatch.setattr(installation_module.subprocess, "run", run)
    output = installation_module.SubprocessGitRunner().run(
        ("git", "rev-parse", "--verify", "HEAD^{commit}"),
        cwd=tmp_path,
    )

    environment = captured["env"]
    assert type(environment) is dict
    assert output == b"exact git output\n"
    assert environment["GIT_NO_REPLACE_OBJECTS"] == "1"
    assert environment["GIT_OPTIONAL_LOCKS"] == "0"
    assert environment["GIT_TERMINAL_PROMPT"] == "0"
    assert "GIT_OBJECT_DIRECTORY" not in environment
    assert captured["shell"] is False


def _source_fixture(
    tmp_path: Path,
    blobs: dict[str, bytes],
    *,
    status: bytes = b"",
    tracking_commit: str = COMMIT,
    remote_commit: str = COMMIT,
    corrupt_blob_path: str | None = None,
) -> tuple[GitSourceAcquirer, _FakeRunner]:
    responses: dict[tuple[str, ...], bytes] = {
        ("git", "rev-parse", "--verify", "HEAD^{commit}"): (
            f"{COMMIT}\n".encode("ascii")
        ),
        ("git", "rev-parse", "--verify", f"{COMMIT}^{{commit}}"): (
            f"{COMMIT}\n".encode("ascii")
        ),
        ("git", "rev-parse", "--verify", f"{COMMIT}^{{tree}}"): (
            f"{TREE}\n".encode("ascii")
        ),
        ("git", "status", "--porcelain=v1", "--untracked-files=all"): status,
        ("git", "remote", "get-url", REMOTE): f"{REMOTE_URL}\n".encode(),
        (
            "git",
            "rev-parse",
            "--verify",
            "refs/remotes/origin/v0.4-dev^{commit}",
        ): f"{tracking_commit}\n".encode("ascii"),
        (
            "git",
            "ls-remote",
            "--exit-code",
            REMOTE,
            REMOTE_REF,
        ): f"{remote_commit}\t{REMOTE_REF}\n".encode("ascii"),
    }
    for path, raw in blobs.items():
        oid = _blob_oid(raw)
        git_tree_path = installation_module.w3_project_git_tree_path(path)
        responses[
            (
                "git",
                "ls-tree",
                "-z",
                "--full-tree",
                COMMIT,
                "--",
                installation_module.w3_project_git_pathspec(path),
            )
        ] = (
            f"100644 blob {oid}\t{git_tree_path}".encode() + b"\0"
        )
        responses[("git", "cat-file", "-s", oid)] = f"{len(raw)}\n".encode()
        responses[("git", "cat-file", "blob", oid)] = (
            raw + b"corrupt" if path == corrupt_blob_path else raw
        )
    runner = _FakeRunner(tmp_path, responses)
    return GitSourceAcquirer(tmp_path, runner=runner), runner


def _unit_templates() -> tuple[bytes, bytes]:
    problem_root = (
        Path(__file__).resolve().parents[4]
        / "problems"
        / "warehouse_delivery"
        / "systemd"
    )
    return (
        (problem_root / "scion-w3@.service").read_bytes(),
        (problem_root / "scion-w3-close@.service").read_bytes(),
    )


def _required_blobs() -> dict[str, bytes]:
    run_template, close_template = _unit_templates()
    return {
        W3_COMPOSITION_LOGICAL_PATH: b'"""fixed composition fixture"""\n',
        W3_TOOL_LOGICAL_PATH: b'"""fixed tool fixture"""\n',
        W3_RUN_TEMPLATE_LOGICAL_PATH: run_template,
        W3_CLOSE_TEMPLATE_LOGICAL_PATH: close_template,
    }


def _source(tmp_path: Path):
    blobs = _required_blobs()
    acquirer, runner = _source_fixture(tmp_path, blobs)
    source = acquirer.acquire(
        launch_commit=COMMIT,
        remote_name=REMOTE,
        remote_ref=REMOTE_REF,
        logical_paths=tuple(reversed(tuple(blobs))),
    )
    return source, runner


def test_selection_receipts_are_canonical_plan_bound_and_cross_bound(
    tmp_path: Path,
) -> None:
    intent = CandidateSelectionIntent.create(
        experiment_parent=tmp_path,
        task_event_identity="task-event:20260723",
        launch_commit=COMMIT,
        launch_tree=TREE,
        source_acceptance_sha256="d" * 64,
    )
    expected_key = derive_selection_key(
        task_event_identity="task-event:20260723",
        launch_commit=COMMIT,
        launch_tree=TREE,
        source_acceptance_sha256="d" * 64,
        dry_root_manifest_sha256=EXPECTED_MANIFEST_SHA256,
        native_record_sha256=EXPECTED_NATIVE_ACCEPTANCE_RECORD_SHA256,
    )
    paths = derive_candidate_paths(tmp_path, expected_key)

    assert intent.selection_key == expected_key
    assert intent.candidate_root == str(paths.candidate_root)
    assert paths.candidate_root.name == f"v04-w3-launch-{expected_key}-claw"
    assert json.loads(intent.raw)["fixed_plan_sha256"] == (
        ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256
    )
    assert CandidateSelectionIntent.from_bytes(intent.raw) == intent
    assert intent.raw == _canonical(json.loads(intent.raw))

    paths.candidate_root.mkdir()
    identity = CandidateRootIdentity.capture(paths.candidate_root)
    authority_sha = hashlib.sha256(b"authority").hexdigest()
    committed = CandidateSelectionCommit.create(
        intent=intent,
        candidate_root_identity=identity,
        nonce=NONCE,
        authority_sha256=authority_sha,
    )
    assert committed.launch_id == derive_launch_id(authority_sha, NONCE)
    assert CandidateSelectionCommit.from_bytes(committed.raw, intent) == committed

    changed = json.loads(committed.raw)
    changed["intent_sha256"] = "0" * 64
    with pytest.raises(
        WarehouseW3InstallationError,
        match="differs from intent",
    ):
        CandidateSelectionCommit.from_bytes(_canonical(changed), intent)


def test_selection_intent_rejects_unknown_duplicate_and_plan_drift(
    tmp_path: Path,
) -> None:
    intent = CandidateSelectionIntent.create(
        experiment_parent=tmp_path,
        task_event_identity="task-event:one",
        launch_commit=COMMIT,
        launch_tree=TREE,
        source_acceptance_sha256="d" * 64,
    )
    value = json.loads(intent.raw)
    value["unknown"] = False
    with pytest.raises(WarehouseW3InstallationError, match="fields differ"):
        CandidateSelectionIntent.from_bytes(_canonical(value))

    duplicate = b'{"schema":"scion.w3-candidate-selection-intent.v1",' + intent.raw[1:]
    with pytest.raises(WarehouseW3InstallationError, match="canonical JSON"):
        CandidateSelectionIntent.from_bytes(duplicate)

    value = json.loads(intent.raw)
    value["fixed_plan_sha256"] = "0" * 64
    with pytest.raises(WarehouseW3InstallationError, match="plan differs"):
        CandidateSelectionIntent.from_bytes(_canonical(value))


def test_selection_owner_publishes_one_fsynced_pair_and_refuses_reuse(
    tmp_path: Path,
) -> None:
    intent = CandidateSelectionIntent.create(
        experiment_parent=tmp_path,
        task_event_identity="task-event:selection-owner",
        launch_commit=COMMIT,
        launch_tree=TREE,
        source_acceptance_sha256="d" * 64,
    )
    paths = derive_candidate_paths(tmp_path, intent.selection_key)
    owner = CandidateSelectionOwner(intent)

    assert owner.publish_intent() == intent
    assert owner.state == "INTENT_PUBLISHED"
    assert paths.intent_path.read_bytes() == intent.raw
    assert paths.intent_path.stat().st_mode & 0o777 == 0o444

    paths.candidate_root.mkdir(mode=0o755)
    paths.candidate_root.chmod(0o555)
    committed = owner.commit(
        nonce=NONCE,
        authority_sha256=hashlib.sha256(b"authority").hexdigest(),
    )

    assert owner.state == "COMMITTED"
    assert paths.committed_path.read_bytes() == committed.raw
    assert paths.committed_path.stat().st_mode & 0o777 == 0o444
    assert paths.selection_directory.stat().st_mode & 0o777 == 0o555
    assert tuple(sorted(path.name for path in paths.selection_directory.iterdir())) == (
        "committed.v1.json",
        "intent.v1.json",
    )

    with pytest.raises(
        WarehouseW3InstallationError,
        match="candidate root already exists|selection key already exists",
    ):
        CandidateSelectionOwner(intent).publish_intent()


def test_selection_owner_rejects_root_and_existing_candidate_before_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    intent = CandidateSelectionIntent.create(
        experiment_parent=tmp_path,
        task_event_identity="task-event:selection-root-refusal",
        launch_commit=COMMIT,
        launch_tree=TREE,
        source_acceptance_sha256="d" * 64,
    )
    paths = derive_candidate_paths(tmp_path, intent.selection_key)

    with monkeypatch.context() as patch:
        patch.setattr(installation_module.os, "geteuid", lambda: 0)
        with pytest.raises(WarehouseW3InstallationError, match="uid zero"):
            CandidateSelectionOwner(intent)
    assert not paths.selection_directory.exists()

    paths.candidate_root.mkdir()
    with pytest.raises(
        WarehouseW3InstallationError, match="candidate root already exists"
    ):
        CandidateSelectionOwner(intent).publish_intent()
    assert not paths.selection_directory.exists()


def test_git_source_acquisition_uses_exact_argv_and_real_blob_identities(
    tmp_path: Path,
) -> None:
    blobs = {
        "scion/z.py": b"z = 1\n",
        "scion/a.py": b"a = 1\n",
    }
    acquirer, runner = _source_fixture(tmp_path, blobs)

    source = acquirer.acquire(
        launch_commit=COMMIT,
        remote_name=REMOTE,
        remote_ref=REMOTE_REF,
        logical_paths=("scion/z.py", "scion/a.py"),
    )

    assert source.receipt.source_commit == COMMIT
    assert source.receipt.source_tree == TREE
    assert source.receipt.remote_url == REMOTE_URL
    assert tuple(item.logical_path for item in source.blobs) == (
        "scion/a.py",
        "scion/z.py",
    )
    for fact in source.blobs:
        assert fact.blob_oid == _blob_oid(fact.raw)
        assert fact.sha256 == hashlib.sha256(fact.raw).hexdigest()
        assert fact.size_bytes == len(fact.raw)
    assert runner.calls[:7] == [
        ("git", "rev-parse", "--verify", "HEAD^{commit}"),
        ("git", "rev-parse", "--verify", f"{COMMIT}^{{commit}}"),
        ("git", "rev-parse", "--verify", f"{COMMIT}^{{tree}}"),
        ("git", "status", "--porcelain=v1", "--untracked-files=all"),
        ("git", "remote", "get-url", REMOTE),
        (
            "git",
            "rev-parse",
            "--verify",
            "refs/remotes/origin/v0.4-dev^{commit}",
        ),
        ("git", "ls-remote", "--exit-code", REMOTE, REMOTE_REF),
    ]


def test_git_source_rejects_placeholder_commit_before_runner(
    tmp_path: Path,
) -> None:
    acquirer, runner = _source_fixture(tmp_path, {"scion/a.py": b"a = 1\n"})

    with pytest.raises(WarehouseW3InstallationError, match="real 40-hex"):
        acquirer.acquire(
            launch_commit="1" * 40,
            remote_name=REMOTE,
            remote_ref=REMOTE_REF,
            logical_paths=("scion/a.py",),
        )

    assert runner.calls == []


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("dirty", "not clean"),
        ("tracking", "remote-tracking commit differs"),
        ("remote", "ls-remote observation differs"),
        ("blob", "blob bytes differ"),
    ),
)
def test_git_source_rejects_dirty_unpushed_or_non_object_bytes(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    blobs = {"scion/a.py": b"a = 1\n"}
    other = hashlib.sha1(b"other commit").hexdigest()
    acquirer, _runner = _source_fixture(
        tmp_path,
        blobs,
        status=b" M scion/a.py\n" if mutation == "dirty" else b"",
        tracking_commit=other if mutation == "tracking" else COMMIT,
        remote_commit=other if mutation == "remote" else COMMIT,
        corrupt_blob_path="scion/a.py" if mutation == "blob" else None,
    )
    with pytest.raises(WarehouseW3InstallationError, match=message):
        acquirer.acquire(
            launch_commit=COMMIT,
            remote_name=REMOTE,
            remote_ref=REMOTE_REF,
            logical_paths=("scion/a.py",),
        )


def test_authority_and_installation_adapters_are_exact_and_do_not_touch_run_root(
    tmp_path: Path,
) -> None:
    source, _runner = _source(tmp_path)
    manifest_input = AuthorityInputAdapter.external_evidence(
        logical_path=EXPECTED_MANIFEST_NAME,
        sealed_path=f"sealed/{EXPECTED_MANIFEST_NAME}",
        sha256=EXPECTED_MANIFEST_SHA256,
        size_bytes=1234,
        source_path=tmp_path / "accepted" / EXPECTED_MANIFEST_NAME,
        device=10,
        inode=20,
    )
    native_input = AuthorityInputAdapter.external_evidence(
        logical_path=W3_NATIVE_RECORD_LOGICAL_PATH,
        sealed_path=f"sealed/{W3_NATIVE_RECORD_LOGICAL_PATH}",
        sha256=EXPECTED_NATIVE_ACCEPTANCE_RECORD_SHA256,
        size_bytes=456,
        source_path=tmp_path / "accepted" / "native-record.v1.json",
        device=11,
        inode=21,
    )
    generated_raw = b"generated launch receipt\n"
    generated_input = AuthorityInputAdapter.generated(
        logical_path="receipts/generated.v1.json",
        sealed_path="sealed/receipts/generated.v1.json",
        raw=generated_raw,
        generator_sha256=hashlib.sha256(b"generator").hexdigest(),
        input_sha256=(
            hashlib.sha256(b"input-b").hexdigest(),
            hashlib.sha256(b"input-a").hexdigest(),
        ),
        rule_sha256=hashlib.sha256(b"rule").hexdigest(),
    )
    authority = build_warehouse_launch_authority(
        source,
        manifest_input=manifest_input,
        native_record_input=native_input,
        root_basename="accepted-w3-root",
        nonce=NONCE,
        sealed_store_aggregate_sha256=hashlib.sha256(b"sealed").hexdigest(),
        environment_receipt_sha256=hashlib.sha256(b"environment").hexdigest(),
        extra_inputs=(generated_input,),
    )
    run_template, close_template = _unit_templates()
    run_root = tmp_path / "accepted-w3-root"
    assert not run_root.exists()

    installation = build_warehouse_installation(
        authority,
        run_root=run_root,
        run_template_raw=run_template,
        close_template_raw=close_template,
    )

    assert not run_root.exists()
    assert installation.launch_id == derive_launch_id(
        authority.authority_sha256,
        NONCE,
    )
    assert installation.authority_path == (
        f"/var/lib/scion/authorities/w3/{authority.authority_sha256}.json"
    )
    assert installation.environment_root == (
        "/var/lib/scion/environments/w3/" f"{authority.environment_receipt_sha256}"
    )
    assert installation.configured_pair.configured_pair_sha256 == (
        installation.configured_pair_sha256
    )
    provenance = {
        item.logical_path: item.to_mapping()["provenance"] for item in authority.inputs
    }
    assert provenance[W3_COMPOSITION_LOGICAL_PATH] == {
        "kind": "git_blob",
        "commit": COMMIT,
        "path": W3_COMPOSITION_LOGICAL_PATH,
        "blob_oid": _blob_oid(_required_blobs()[W3_COMPOSITION_LOGICAL_PATH]),
    }
    assert provenance["receipts/generated.v1.json"] == {
        "generator_sha256": hashlib.sha256(b"generator").hexdigest(),
        "input_sha256": sorted(
            [
                hashlib.sha256(b"input-b").hexdigest(),
                hashlib.sha256(b"input-a").hexdigest(),
            ]
        ),
        "kind": "generated",
        "rule_sha256": hashlib.sha256(b"rule").hexdigest(),
    }


def test_module_has_no_privileged_or_start_capability() -> None:
    source = (
        Path(__file__).resolve().parents[4]
        / "problems"
        / "warehouse_delivery"
        / "w3_installation.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "StartUnit",
        "NonceClaimOwner",
        "external_installation",
        "import dbus",
        "os.mount",
        "sudo",
    ):
        assert forbidden not in source


def test_sealed_store_receipt_is_complete_canonical_and_provenance_bound(
    tmp_path: Path,
) -> None:
    source, _runner = _source(tmp_path)
    external_path = tmp_path / "external-record.json"
    external_raw = b'{"accepted":true}\n'
    external_path.write_bytes(external_raw)
    external_path.chmod(0o444)
    external = SealedStoreObject.external_evidence(
        logical_path="external/record.json",
        sealed_path="sealed/external/record.json",
        source_path=external_path,
    )
    generated = SealedStoreObject.generated(
        logical_path="bin/scion-w3-tool",
        sealed_path="sealed/bin/scion-w3-tool",
        raw=b"#!/usr/bin/python3\n",
        generator_sha256=hashlib.sha256(b"generator").hexdigest(),
        input_sha256=(source.blobs[0].sha256,),
        rule_sha256=hashlib.sha256(b"copy-rule").hexdigest(),
        executable=True,
    )
    objects = tuple(
        [
            *(SealedStoreObject.from_git_blob(item) for item in source.blobs),
            external,
            generated,
        ]
    )

    receipt = SealedStoreReceipt.create(objects)
    assert SealedStoreReceipt.from_bytes(receipt.raw) == receipt
    assert receipt.raw == _canonical(json.loads(receipt.raw))
    by_path = {item.path: item for item in receipt.inventory}
    assert by_path["."].kind == "directory"
    assert (
        by_path["sealed/external/record.json"].sha256
        == hashlib.sha256(external_raw).hexdigest()
    )
    assert by_path["sealed/bin/scion-w3-tool"].mode == 0o555
    assert dict(by_path["sealed/external/record.json"].provenance or ()) == {
        "device": external_path.stat().st_dev,
        "inode": external_path.stat().st_ino,
        "kind": "external_evidence",
        "source_path": str(external_path),
    }

    changed = json.loads(receipt.raw)
    changed["inventory"][0]["mode"] = 0o755
    with pytest.raises(
        WarehouseW3InstallationError,
        match="directory facts differ",
    ):
        SealedStoreReceipt.from_bytes(_canonical(changed))


def _prepared_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    manifest_raw = b'{"manifest":"test-only"}\n'
    native_raw = b'{"native":"test-only"}\n'
    manifest_sha = hashlib.sha256(manifest_raw).hexdigest()
    native_sha = hashlib.sha256(native_raw).hexdigest()
    monkeypatch.setattr(
        installation_module,
        "EXPECTED_MANIFEST_SHA256",
        manifest_sha,
    )
    monkeypatch.setattr(
        installation_module,
        "EXPECTED_NATIVE_ACCEPTANCE_RECORD_SHA256",
        native_sha,
    )
    source, _runner = _source(tmp_path)
    source_inventory = source_inventory_sha256(source.receipt)
    root_git = RootGitVerificationReceipt.create(
        trusted_git_root=Path("/srv/scion/trusted-w3.git"),
        trusted_git_device=1,
        trusted_git_inode=2,
        trusted_git_content_sha256="b" * 64,
        git_binary_sha256="a" * 64,
        remote_name=REMOTE,
        remote_ref=REMOTE_REF,
        source=source,
    )
    reviews = tuple(
        FixedSourceReviewClosure.create(
            review_scope=scope,
            reviewer_identity=f"reviewer-{index}",
            task_identity=f"task-{index}",
            source_commit=source.receipt.source_commit,
            source_tree=source.receipt.source_tree,
            source_inventory_sha256=source_inventory,
            report_sha256=str(index) * 64,
            p0_open=0,
            p1_open=0,
            completed_at_utc=f"2026-07-2{index}T00:00:00Z",
        )
        for index, scope in enumerate(
            ("root_installation", "launch_readiness"),
            start=1,
        )
    )
    source_acceptance = RootFixedSourceAcceptanceReceipt.create(
        source=source,
        root_git_verification=root_git,
        reviews=reviews,
        accepted_at_utc="2026-07-23T00:00:00Z",
    )
    intent = CandidateSelectionIntent.create(
        experiment_parent=tmp_path,
        task_event_identity="task-event:candidate-facade",
        launch_commit=COMMIT,
        launch_tree=TREE,
        source_acceptance_sha256=source_acceptance.raw_sha256,
        dry_root_manifest_sha256=manifest_sha,
        native_record_sha256=native_sha,
    )

    evidence = tmp_path / "accepted-evidence"
    evidence.mkdir()
    manifest_path = evidence / EXPECTED_MANIFEST_NAME
    native_path = evidence / "native-record.v1.json"
    manifest_path.write_bytes(manifest_raw)
    native_path.write_bytes(native_raw)
    manifest_path.chmod(0o444)
    native_path.chmod(0o444)
    objects = tuple(
        [
            *(SealedStoreObject.from_git_blob(item) for item in source.blobs),
            SealedStoreObject.external_evidence(
                logical_path=EXPECTED_MANIFEST_NAME,
                sealed_path=f"sealed/{EXPECTED_MANIFEST_NAME}",
                source_path=manifest_path,
            ),
            SealedStoreObject.external_evidence(
                logical_path=W3_NATIVE_RECORD_LOGICAL_PATH,
                sealed_path=f"sealed/{W3_NATIVE_RECORD_LOGICAL_PATH}",
                source_path=native_path,
            ),
            SealedStoreObject.generated(
                logical_path=W3_SOURCE_ACCEPTANCE_LOGICAL_PATH,
                sealed_path=W3_SOURCE_ACCEPTANCE_SEALED_PATH,
                raw=source_acceptance.raw,
                generator_sha256=root_git.raw_sha256,
                input_sha256=(source.receipt.raw_sha256,),
                rule_sha256=ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256,
            ),
            SealedStoreObject.generated(
                logical_path=W3_WHEEL_LOGICAL_PATH,
                sealed_path=W3_WHEEL_SEALED_PATH,
                raw=b"exact wheel bytes",
                generator_sha256="b" * 64,
                input_sha256=(source.receipt.raw_sha256,),
                rule_sha256=ACCEPTED_ROOT_INSTALLATION_PLAN_SHA256,
            ),
        ]
    )

    environment_root = tmp_path / "built-environment"
    environment_root.mkdir()
    (environment_root / "bin").mkdir()
    python_entry = environment_root / "bin" / "python3"
    python_entry.write_bytes(b"test-only-python-entry\n")
    python_entry.chmod(0o555)
    (environment_root / "bin").chmod(0o555)
    environment_root.chmod(0o555)
    runtime_path = tmp_path / "external-runtime.so"
    runtime_path.write_bytes(b"test-only-external-runtime\n")
    runtime_path.chmod(0o444)
    paths = derive_candidate_paths(tmp_path, intent.selection_key)
    environment_receipt = EnvironmentContentReceipt.create(
        environment_root,
        external_runtime_paths=(runtime_path,),
        candidate_root=paths.candidate_root,
        selection_root=paths.selection_directory,
    )
    return (
        intent,
        source,
        objects,
        environment_root,
        environment_receipt,
        (runtime_path,),
        tmp_path / "accepted-w3-root",
    )


def test_prepare_and_verify_candidate_freeze_one_acyclic_exact_inventory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        intent,
        source,
        objects,
        environment_root,
        environment_receipt,
        runtime_paths,
        run_root,
    ) = _prepared_inputs(tmp_path, monkeypatch)

    prepared = prepare_candidate(
        intent,
        source=source,
        sealed_objects=objects,
        environment_root=environment_root,
        environment_receipt=environment_receipt,
        external_runtime_paths=runtime_paths,
        run_root=run_root,
        nonce=NONCE,
    )
    reopened = verify_candidate(
        prepared.candidate_root,
        external_runtime_paths=runtime_paths,
    )

    assert reopened == prepared
    assert prepared.candidate_root.stat().st_mode & 0o777 == 0o555
    assert prepared.candidate_receipt.tail_paths == (
        "candidate.v1.json",
        "receipts/candidate-verification.v1.json",
    )
    assert not {
        item.path for item in prepared.candidate_receipt.content_inventory
    }.intersection(prepared.candidate_receipt.tail_paths)
    assert prepared.verification_receipt.candidate_receipt_sha256 == (
        prepared.candidate_receipt.raw_sha256
    )
    assert prepared.candidate_receipt.selection_commit_sha256 == (
        prepared.selection_commit.raw_sha256
    )
    assert tuple(
        sorted(
            str(path.relative_to(prepared.candidate_root))
            for path in prepared.candidate_root.rglob("*")
            if path.is_file()
            and len(path.relative_to(prepared.candidate_root).parts) <= 2
        )
    ) == tuple(
        sorted(
            item
            for item in prepared.candidate_receipt.inventory
            if item not in {"sealed-store", "environment"}
        )
    )
    assert (
        CandidateReceipt.from_bytes(
            (prepared.candidate_root / "candidate.v1.json").read_bytes()
        )
        == prepared.candidate_receipt
    )

    sealed_file = (
        prepared.candidate_root
        / "sealed-store"
        / "sealed"
        / W3_COMPOSITION_LOGICAL_PATH
    )
    original = sealed_file.read_bytes()
    sealed_file.chmod(0o644)
    sealed_file.write_bytes(b"X" + original[1:])
    sealed_file.chmod(0o444)
    with pytest.raises(
        WarehouseW3InstallationError,
        match="sealed-store live inventory differs",
    ):
        verify_candidate(
            prepared.candidate_root,
            external_runtime_paths=runtime_paths,
        )


def test_prepare_candidate_rejects_drifted_built_environment_before_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        intent,
        source,
        objects,
        environment_root,
        environment_receipt,
        runtime_paths,
        run_root,
    ) = _prepared_inputs(tmp_path, monkeypatch)
    entry = environment_root / "bin" / "python3"
    entry.chmod(0o644)
    entry.write_bytes(b"drifted-python-entry\n")
    entry.chmod(0o555)

    with pytest.raises(
        WarehouseW3InstallationError,
        match="built environment differs",
    ):
        prepare_candidate(
            intent,
            source=source,
            sealed_objects=objects,
            environment_root=environment_root,
            environment_receipt=environment_receipt,
            external_runtime_paths=runtime_paths,
            run_root=run_root,
            nonce=NONCE,
        )
    paths = derive_candidate_paths(tmp_path, intent.selection_key)
    assert not paths.selection_directory.exists()
    assert not paths.candidate_root.exists()
