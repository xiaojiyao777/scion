#!/bin/sh
# Tests-only static preflight. It never freezes runtime receipts, opens a
# bus/FIFO/journal, or installs, reloads, starts, stops or resets a unit.

set -eu
umask 077

die() {
    printf '%s\n' "generic-backend-formal-wrapper: $*" >&2
    exit 64
}

usage() {
    printf '%s\n' \
        'usage: generic-backend-formal-wrapper.sh preflight STATIC-INVENTORY.tsv SEAL-RECEIPT.json' >&2
    exit 64
}

require_regular_file() {
    path=$1
    label=$2
    [ -f "$path" ] || die "$label is not a regular file: $path"
    [ ! -L "$path" ] || die "$label must not be a symbolic link: $path"
}

require_nonempty_file() {
    require_regular_file "$1" "$2"
    [ -s "$1" ] || die "$2 is empty: $1"
}

require_single_key() {
    file=$1
    key=$2
    expected=$3
    counts=$(awk -v key="$key" -v expected="$expected" '
        index($0, key "=") == 1 {
            total += 1
            if ($0 == key "=" expected) exact += 1
        }
        END { printf "%d:%d", total + 0, exact + 0 }
    ' "$file")
    [ "$counts" = "1:1" ] || die "$file must contain exactly one $key=$expected"
}

require_absent_key() {
    file=$1
    key=$2
    count=$(awk -v key="$key" 'index($0, key "=") == 1 { n += 1 } END { print n + 0 }' "$file")
    [ "$count" = 0 ] || die "$file must not contain $key"
}

require_description() {
    file=$1
    prefix=$2
    value=$(awk -F= '$1 == "Description" { n += 1; value = substr($0, length($1) + 2) } END { if (n == 1) print value }' "$file")
    case "$value" in "$prefix"*) suffix=${value#"$prefix"} ;; *) die "$file Description prefix is not exact" ;; esac
    [ -n "$suffix" ] || die "$file Description suffix is empty"
    printf '%s\n' "$suffix" | LC_ALL=C grep -Eq '^[A-Za-z0-9_.:/+-]+$' \
        || die "$file Description suffix is not canonical"
}

require_closed_directives() {
    file=$1
    role=$2
    awk -v role="$role" '
        function add(section, key) { allowed[section SUBSEP key] = 1 }
        BEGIN {
            add("Unit", "Description");
            add("Service", "Type"); add("Service", "User");
            add("Service", "Group"); add("Service", "UMask");
            add("Service", "ExecStart"); add("Service", "Restart");
            add("Service", "NoNewPrivileges"); add("Service", "PrivateTmp");
            add("Service", "ProtectSystem"); add("Service", "ProtectHome");
            add("Service", "ReadOnlyPaths"); add("Service", "ReadWritePaths");
            if (role == "run") {
                add("Unit", "OnSuccess"); add("Unit", "OnFailure");
                add("Unit", "CollectMode"); add("Service", "ExecStopPost");
                add("Service", "ExitType"); add("Service", "KillMode");
                add("Service", "SendSIGKILL"); add("Service", "TimeoutStopSec");
                add("Service", "OOMPolicy"); add("Service", "Delegate");
                add("Service", "DelegateSubgroup"); add("Service", "PrivateMounts");
                add("Service", "ProtectControlGroups"); add("Service", "ProtectProc");
                add("Service", "ProcSubset");
            } else if (role == "close") {
                add("Unit", "After"); add("Unit", "CollectMode");
                add("Service", "TimeoutStartSec");
            } else if (role == "gc") {
                add("Unit", "X-Scion-Acceptance-Case");
                add("Unit", "X-Scion-Expected-Result"); add("Unit", "CollectMode");
                add("Service", "KillMode"); add("Service", "SendSIGKILL");
                add("Service", "TimeoutStopSec");
            } else exit 1
        }
        $0 == "" { next }
        /^#/ {
            if (role != "gc" || section != "" || comment_seen++ ||
                $0 != "# H10 NEGATIVE CONTROL ONLY. This unit can never satisfy formal acceptance.") exit 1
            next
        }
        /^\[.*\]$/ {
            name = substr($0, 2, length($0) - 2)
            if ((name != "Unit" && name != "Service") || section_seen[name]++) exit 1
            section_order += 1
            if ((section_order == 1 && name != "Unit") || (section_order == 2 && name != "Service")) exit 1
            section = name
            next
        }
        {
            split_at = index($0, "=")
            if (section == "" || split_at < 2) exit 1
            key = substr($0, 1, split_at - 1)
            value = substr($0, split_at + 1)
            binding = section SUBSEP key
            if (key !~ /^[A-Za-z][A-Za-z0-9-]*$/ || value == "" || !allowed[binding] || seen[binding]++) exit 1
        }
        END {
            if (section_order != 2 || (role == "gc" && comment_seen != 1) || (role != "gc" && comment_seen != 0)) exit 1
            for (binding in allowed) if (seen[binding] != 1) exit 1
        }
    ' "$file" || die "$file section/directive multiset is not the exact closed form"
}

require_exact_argv() {
    file=$1
    key=$2
    line=$(awk -v key="$key" 'index($0, key "=") == 1 { n += 1; value = substr($0, length(key) + 2) } END { if (n == 1) print value }' "$file")
    [ -n "$line" ] || die "$file must contain exactly one $key"
    printf '%s\n' "$line" | LC_ALL=C grep -Eq '^/usr/bin/python3\.12 -I -B /[A-Za-z0-9_./:+-]+ --plan /[A-Za-z0-9_./:+-]+$' \
        || die "$file $key is not exact /usr/bin/python3.12 -I -B PROGRAM --plan PLAN argv"
}

require_concrete() {
    file=$1
    LC_ALL=C grep -Eq '@|%' "$file" && die "$file contains an unresolved placeholder/specifier"
    return 0
}

validate_run_fragment() {
    file=$1
    close_unit=$2
    root=$3
    require_regular_file "$file" RUN_FRAGMENT
    require_concrete "$file"
    require_closed_directives "$file" run
    require_description "$file" 'Scion generic SpawnBackend formal run '
    require_single_key "$file" Type exec
    require_single_key "$file" UMask 0077
    require_single_key "$file" Restart no
    require_single_key "$file" KillMode control-group
    require_single_key "$file" TimeoutStopSec infinity
    require_single_key "$file" Delegate pids
    require_single_key "$file" DelegateSubgroup supervisor
    require_single_key "$file" CollectMode inactive
    require_single_key "$file" OnSuccess "$close_unit"
    require_single_key "$file" OnFailure "$close_unit"
    require_single_key "$file" ExitType main
    require_single_key "$file" SendSIGKILL yes
    require_single_key "$file" OOMPolicy stop
    require_single_key "$file" NoNewPrivileges yes
    require_single_key "$file" PrivateTmp yes
    require_single_key "$file" PrivateMounts yes
    require_single_key "$file" ProtectSystem strict
    require_single_key "$file" ProtectHome read-only
    require_single_key "$file" ProtectControlGroups no
    require_single_key "$file" ProtectProc invisible
    require_single_key "$file" ProcSubset all
    require_single_key "$file" ReadOnlyPaths "$root/sealed $root/input"
    require_single_key "$file" ReadWritePaths "$root/work $root/fifo"
    require_exact_argv "$file" ExecStart
    require_exact_argv "$file" ExecStopPost
}

validate_close_fragment() {
    file=$1
    run_unit=$2
    root=$3
    require_regular_file "$file" CLOSE_FRAGMENT
    require_concrete "$file"
    require_closed_directives "$file" close
    require_description "$file" 'Scion generic SpawnBackend formal closer '
    require_single_key "$file" Type oneshot
    require_single_key "$file" UMask 0077
    require_single_key "$file" After "$run_unit"
    require_single_key "$file" Restart no
    require_single_key "$file" TimeoutStartSec infinity
    require_single_key "$file" CollectMode inactive
    require_single_key "$file" NoNewPrivileges yes
    require_single_key "$file" PrivateTmp yes
    require_single_key "$file" ProtectSystem strict
    require_single_key "$file" ProtectHome read-only
    require_single_key "$file" ReadOnlyPaths "$root/sealed $root/input"
    require_single_key "$file" ReadWritePaths "$root/work $root/fifo"
    require_exact_argv "$file" ExecStart
    require_absent_key "$file" ExecStopPost
}

validate_negative_fragment() {
    file=$1
    root=$2
    require_regular_file "$file" GC_FRAGMENT
    require_concrete "$file"
    require_closed_directives "$file" gc
    require_description "$file" 'Scion H10 GC negative control (rejected) '
    require_single_key "$file" Type exec
    require_single_key "$file" UMask 0077
    require_single_key "$file" X-Scion-Acceptance-Case H10-negative-control-only
    require_single_key "$file" X-Scion-Expected-Result rejected-failed-identity-loss
    require_single_key "$file" CollectMode inactive-or-failed
    require_single_key "$file" Restart no
    require_single_key "$file" KillMode control-group
    require_single_key "$file" SendSIGKILL yes
    require_single_key "$file" TimeoutStopSec infinity
    require_single_key "$file" NoNewPrivileges yes
    require_single_key "$file" PrivateTmp yes
    require_single_key "$file" ProtectSystem strict
    require_single_key "$file" ProtectHome read-only
    require_single_key "$file" ReadOnlyPaths "$root/sealed $root/input"
    require_single_key "$file" ReadWritePaths "$root/work $root/fifo"
    require_absent_key "$file" OnSuccess
    require_absent_key "$file" OnFailure
    require_exact_argv "$file" ExecStart
}

validate_identity_directives() {
    run=$1
    close=$2
    negative=$3
    user=$(awk -F= '$1 == "User" { n += 1; value = $2 } END { if (n == 1) print value }' "$run")
    group=$(awk -F= '$1 == "Group" { n += 1; value = $2 } END { if (n == 1) print value }' "$run")
    [ -n "$user" ] && [ -n "$group" ] || die 'run fragment lacks exact User/Group'
    printf '%s\n%s\n' "$user" "$group" | LC_ALL=C grep -Eq '^[A-Za-z_][A-Za-z0-9_.-]*$' \
        || die 'run fragment User/Group is not canonical'
    for file in "$close" "$negative"; do
        require_single_key "$file" User "$user"
        require_single_key "$file" Group "$group"
    done
}

validate_start_descriptor() {
    descriptor=$1
    run_unit=$2
    require_nonempty_file "$descriptor" START_DESCRIPTOR
    printf '%s\n' "{\"bus\":\"system\",\"destination\":\"org.freedesktop.systemd1\",\"interface\":\"org.freedesktop.systemd1.Manager\",\"method\":\"StartUnit\",\"mode\":\"fail\",\"object\":\"/org/freedesktop/systemd1\",\"owner\":\"generic_backend_systemd_harness.py\",\"schema\":\"scion.generic_backend.systemd_start_descriptor.v1\",\"signature\":\"ss\",\"unit\":\"$run_unit\"}" \
        | cmp -s - "$descriptor" \
        || die 'START_DESCRIPTOR is not exact canonical system-bus data'
}

validate_tree() {
    root=$1
    for directory in "$root" "$root/sealed" "$root/input" "$root/work" "$root/fifo" "$root/authority"; do
        [ -d "$directory" ] && [ ! -L "$directory" ] \
            || die "formal tree directory must be an exact non-symlink directory: $directory"
    done
    [ "$(stat -c '%u:%g:%a' -- "$root")" = '0:0:711' ] || die 'TEST_ROOT must be root:root 0711'
    [ "$(stat -c '%u:%g:%a' -- "$root/sealed")" = '0:0:555' ] || die 'sealed root must be root:root 0555'
    [ "$(stat -c '%u:%g:%a' -- "$root/input")" = '0:0:555' ] || die 'input root must be root:root 0555'
    [ "$(stat -c '%a' -- "$root/work")" = '700' ] || die 'work root must be 0700'
    [ "$(stat -c '%u:%g:%a' -- "$root/fifo")" = '0:0:711' ] || die 'FIFO root must be root:root 0711'
    [ "$(stat -c '%u:%g:%a' -- "$root/authority")" = '0:0:700' ] || die 'authority root must be root:root 0700'
}

validate_tree_fifos() {
    tree_receipt=$1
    root=$2
    /usr/bin/python3.12 -I -B - "$tree_receipt" "$root" <<'PY'
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys


def fail(message):
    raise SystemExit(f"generic-backend-formal-wrapper: {message}")


def object_no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            fail(f"duplicate JSON key {key!r} in TREE_RECEIPT")
        result[key] = value
    return result


def reject_constant(value):
    fail(f"forbidden JSON constant {value!r} in TREE_RECEIPT")


tree_path = Path(sys.argv[1])
root = Path(sys.argv[2])
raw = tree_path.read_bytes()
try:
    tree = json.loads(
        raw.decode("utf-8", "strict"),
        object_pairs_hook=object_no_duplicates,
        parse_constant=reject_constant,
    )
except (UnicodeError, json.JSONDecodeError) as exc:
    fail(f"TREE_RECEIPT is not strict JSON: {exc}")
canonical = (
    json.dumps(
        tree,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    + "\n"
).encode("ascii")
if type(tree) is not dict or raw != canonical:
    fail("TREE_RECEIPT is not one canonical JSON object")
expected_tree_keys = {
    "schema", "formal_root", "sealed_root", "input_root", "work_root",
    "fifo_root", "authority_root", "fixture_user", "fixture_group",
    "fixture_uid", "fixture_gid", "fifos", "prepare_manifest", "phase",
}
if set(tree) != expected_tree_keys:
    fail("TREE_RECEIPT keys are not exact")
if (
    tree["schema"] != "scion.generic_backend.root_tree_receipt.v1"
    or tree["phase"] != "tree-prepared"
    or type(tree["formal_root"]) is not dict
    or tree["formal_root"].get("path") != str(root)
):
    fail("TREE_RECEIPT schema/root/phase drifted")
prepare_reference = tree["prepare_manifest"]
if type(prepare_reference) is not dict or set(prepare_reference) != {
    "path", "sha256", "device", "inode"
}:
    fail("TREE_RECEIPT prepare_manifest reference is not exact")
prepare_path = Path(prepare_reference["path"])
try:
    prepare_info = os.lstat(prepare_path)
    prepare_raw = prepare_path.read_bytes()
except OSError as exc:
    fail(f"cannot read TREE_RECEIPT prepare_manifest: {exc}")
if (
    not stat.S_ISREG(prepare_info.st_mode)
    or str(prepare_info.st_dev) != prepare_reference["device"]
    or str(prepare_info.st_ino) != prepare_reference["inode"]
    or hashlib.sha256(prepare_raw).hexdigest() != prepare_reference["sha256"]
):
    fail("TREE_RECEIPT prepare_manifest full reference drifted")
try:
    prepare = json.loads(
        prepare_raw.decode("utf-8", "strict"),
        object_pairs_hook=object_no_duplicates,
        parse_constant=reject_constant,
    )
except (UnicodeError, json.JSONDecodeError) as exc:
    fail(f"TREE_RECEIPT prepare_manifest is not strict JSON: {exc}")
prepare_canonical = (
    json.dumps(
        prepare,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    + "\n"
).encode("ascii")
if type(prepare) is not dict or prepare_raw != prepare_canonical or set(prepare) != {
    "schema", "formal_root", "fixture_user", "fixture_group", "fifos",
    "receipt_path",
}:
    fail("TREE_RECEIPT prepare_manifest object is not exact canonical authority")
if (
    prepare["schema"] != "scion.generic_backend.root_prepare.v1"
    or prepare["formal_root"] != str(root)
    or prepare["fixture_user"] != tree["fixture_user"]
    or prepare["fixture_group"] != tree["fixture_group"]
    or prepare["receipt_path"] != str(tree_path)
):
    fail("TREE_RECEIPT differs from its prepare_manifest authority")
decimal = re.compile(r"0|[1-9][0-9]*\Z")
role_pattern = re.compile(r"[a-z][a-z0-9]*(?:[-_.][a-z0-9]+)*\Z")
fixture_uid = tree["fixture_uid"]
fixture_gid = tree["fixture_gid"]
if (
    type(fixture_uid) is not str
    or type(fixture_gid) is not str
    or decimal.fullmatch(fixture_uid) is None
    or decimal.fullmatch(fixture_gid) is None
    or fixture_uid == "0"
):
    fail("TREE_RECEIPT fixture UID/GID tuple is not canonical non-root authority")
fixture_identity = (fixture_uid, fixture_gid)
work_path = root / "work"
try:
    work_info = os.lstat(work_path)
except OSError as exc:
    fail(f"cannot lstat TREE_RECEIPT work root: {exc}")
if (
    not stat.S_ISDIR(work_info.st_mode)
    or stat.S_IMODE(work_info.st_mode) != 0o700
    or (str(work_info.st_uid), str(work_info.st_gid)) != fixture_identity
):
    fail("TREE_RECEIPT work root is not the exact fixture-owned 0700 directory")
reserved = {
    "h11-permit-commit": root / "fifo" / "h11-permit-committed.fifo",
    "h11-ready-commit": root / "fifo" / "h11-ready-committed.fifo",
}
rows = tree["fifos"]
if type(rows) is not list or not rows:
    fail("TREE_RECEIPT FIFO authority is empty")
seen_roles = set()
seen_paths = set()
seen_identities = set()
for ordinal, row in enumerate(rows):
    if type(row) is not dict or set(row) != {
        "role", "path", "owner", "uid", "gid", "mode", "device", "inode"
    }:
        fail(f"TREE_RECEIPT fifos[{ordinal}] keys are not exact")
    role = row["role"]
    owner = row["owner"]
    raw_path = row["path"]
    if (
        type(role) is not str
        or role_pattern.fullmatch(role) is None
        or type(owner) is not str
        or owner not in {"fixture", "root"}
        or type(raw_path) is not str
    ):
        fail("TREE_RECEIPT FIFO role/path/owner is not canonical")
    path = Path(raw_path)
    expected_owner = "root" if role in reserved else "fixture"
    expected_uid_gid = ("0", "0") if expected_owner == "root" else fixture_identity
    if (
        not path.is_absolute()
        or str(path) != raw_path
        or path.parent != root / "fifo"
        or role in seen_roles
        or raw_path in seen_paths
        or owner != expected_owner
        or (row["uid"], row["gid"]) != expected_uid_gid
        or row["mode"] != "0600"
        or type(row["device"]) is not str
        or type(row["inode"]) is not str
        or decimal.fullmatch(row["device"]) is None
        or decimal.fullmatch(row["inode"]) is None
    ):
        fail("TREE_RECEIPT FIFO authority metadata drifted")
    if role in reserved and path != reserved[role]:
        fail("TREE_RECEIPT H11 commit FIFO path drifted")
    try:
        info = os.lstat(path)
    except OSError as exc:
        fail(f"cannot stat TREE_RECEIPT FIFO {path}: {exc}")
    identity = (str(info.st_dev), str(info.st_ino))
    if (
        not stat.S_ISFIFO(info.st_mode)
        or stat.S_IMODE(info.st_mode) != 0o600
        or identity != (row["device"], row["inode"])
        or (str(info.st_uid), str(info.st_gid)) != expected_uid_gid
        or identity in seen_identities
    ):
        fail("TREE_RECEIPT FIFO filesystem authority drifted")
    seen_roles.add(role)
    seen_paths.add(raw_path)
    seen_identities.add(identity)
if [row["role"] for row in rows] != sorted(seen_roles):
    fail("TREE_RECEIPT FIFO authority is not sorted by role")
if not set(reserved).issubset(seen_roles):
    fail("TREE_RECEIPT lacks the exact H11 commit FIFO pair")
prepare_fifo_rows = prepare["fifos"]
if prepare_fifo_rows != [
    {"role": row["role"], "path": row["path"], "owner": row["owner"]}
    for row in rows
]:
    fail("TREE_RECEIPT FIFO authority differs from its prepare_manifest")
sys.stdout.write(
    json.dumps(
        rows,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
)
PY
}

safe_absolute() {
    printf '%s\n' "$1" | LC_ALL=C grep -Eq '^/[A-Za-z0-9_./:+-]+$' \
        || die "$2 is not one safe absolute path"
    case "$1" in /|*//*|*/./*|*/../*|*/.|*/..) die "$2 is not normalized" ;; esac
}

header_value() {
    manifest=$1
    ordinal=$2
    key=$3
    value=$(awk -F '\t' -v ordinal="$ordinal" -v key="$key" '
        NR == ordinal && NF == 2 && $1 == key { print $2; ok = 1 }
        END { if (!ok) exit 1 }
    ' "$manifest") || die "static inventory header $key is missing or reordered"
    [ -n "$value" ] || die "static inventory header $key is empty"
    printf '%s\n' "$value"
}

reference_line() {
    manifest=$1
    ordinal=$2
    key=$3
    awk -F '\t' -v ordinal="$ordinal" -v key="$key" '
        NR == ordinal && NF == 6 && $1 == key { print $2, $3, $4, $5, $6; ok = 1 }
        END { if (!ok) exit 1 }
    ' "$manifest" || die "static inventory reference $key is missing or reordered"
}

validate_bound_file() {
    path=$1
    expected_sha=$2
    expected_device=$3
    expected_inode=$4
    expected_mode=$5
    label=$6
    safe_absolute "$path" "$label path"
    require_nonempty_file "$path" "$label"
    printf '%s\n' "$expected_sha" | LC_ALL=C grep -Eq '^[0-9a-f]{64}$' \
        || die "$label SHA-256 is not canonical"
    printf '%s:%s\n' "$expected_device" "$expected_inode" | LC_ALL=C grep -Eq '^(0|[1-9][0-9]*):(0|[1-9][0-9]*)$' \
        || die "$label device/inode is not canonical"
    [ "$expected_mode" = 0444 ] || die "$label mode must be exact 0444"
    actual=$(stat -Lc '%d:%i:%a' -- "$path")
    [ "$actual" = "$expected_device:$expected_inode:444" ] \
        || die "$label identity/mode differs from the sealed inventory"
    [ "$(stat -Lc '%u:%g' -- "$path")" = '0:0' ] \
        || die "$label must be root:root"
    [ "$(sha256sum -- "$path" | awk '{print $1}')" = "$expected_sha" ] \
        || die "$label SHA-256 differs from the sealed inventory"
}

asset_path() {
    manifest=$1
    role=$2
    path=$(awk -F '\t' -v role="$role" '
        $1 == "asset" && $2 == role { n += 1; if (NF == 8) value = $4 }
        END { if (n == 1 && value != "") print value; else exit 1 }
    ' "$manifest") || die "static inventory must contain exactly one $role asset"
    printf '%s\n' "$path"
}

require_inventory_kind() {
    manifest=$1
    path=$2
    kind=$3
    count=$(awk -F '\t' -v path="$path" -v kind="$kind" '
        $1 == "asset" && $3 == kind && $4 == path { n += 1 }
        END { print n + 0 }
    ' "$manifest")
    [ "$count" = 1 ] || die "$path is absent from the exact $kind inventory"
}

validate_argv_inventory() {
    manifest=$1
    fragment=$2
    key=$3
    required=$4
    line=$(awk -v key="$key" '
        index($0, key "=") == 1 { n += 1; value = substr($0, length(key) + 2) }
        END { if (n == 1) print value }
    ' "$fragment")
    if [ -z "$line" ]; then
        [ "$required" = no ] && return 0
        die "$fragment lacks exactly one $key"
    fi
    program=$(printf '%s\n' "$line" | awk '{ if (NF == 6) print $4 }')
    plan=$(printf '%s\n' "$line" | awk '{ if (NF == 6) print $6 }')
    [ -n "$program" ] && [ -n "$plan" ] || die "$fragment $key argv is malformed"
    require_inventory_kind "$manifest" "$program" python-program
    require_inventory_kind "$manifest" "$plan" json-plan
}

preflight() {
    [ "$#" -eq 2 ] || usage
    manifest=$1
    seal_path=$2
    safe_absolute "$manifest" STATIC_INVENTORY
    require_nonempty_file "$manifest" STATIC_INVENTORY
    [ "$(stat -Lc '%u:%g:%a' -- "$manifest")" = '0:0:444' ] \
        || die 'STATIC_INVENTORY must be root:root 0444'
    [ "$(tail -c 1 -- "$manifest" | od -An -tuC | tr -d ' ')" = 10 ] \
        || die 'STATIC_INVENTORY must end with one newline'
    LC_ALL=C grep -q "$(printf '\r')" "$manifest" && die 'STATIC_INVENTORY contains CR'

    schema=$(header_value "$manifest" 1 schema)
    [ "$schema" = scion.generic_backend.static_preflight.v1 ] \
        || die 'STATIC_INVENTORY schema is unsupported'
    test_root=$(header_value "$manifest" 2 formal_root)
    run_unit=$(header_value "$manifest" 3 run_unit)
    close_unit=$(header_value "$manifest" 4 close_unit)
    destination=$(header_value "$manifest" 5 destination_path)
    safe_absolute "$test_root" TEST_ROOT
    safe_absolute "$destination" destination_path
    [ "$destination" != / ] && [ "$(dirname -- "$destination")" = "$test_root/authority" ] \
        || die 'preflight destination must be an authority-root child'
    printf '%s\n' "$run_unit" | LC_ALL=C grep -Eq '^scion-w3-[A-Za-z0-9][A-Za-z0-9_.:-]*\.service$' \
        || die 'RUN_UNIT is not one concrete formal service'
    printf '%s\n' "$close_unit" | LC_ALL=C grep -Eq '^scion-w3-[A-Za-z0-9][A-Za-z0-9_.:-]*\.service$' \
        || die 'CLOSE_UNIT is not one concrete formal service'
    [ "$run_unit" != "$close_unit" ] || die 'RUN_UNIT and CLOSE_UNIT alias'
    validate_tree "$test_root"
    case "$manifest" in "$test_root/sealed/"*) ;; *) die 'STATIC_INVENTORY is not root-sealed' ;; esac

    set -- $(reference_line "$manifest" 6 tree_receipt)
    [ "$#" -eq 5 ] || die 'tree receipt reference is malformed'
    tree_path=$1; tree_sha=$2; tree_device=$3; tree_inode=$4; tree_mode=$5
    validate_bound_file "$tree_path" "$tree_sha" "$tree_device" "$tree_inode" "$tree_mode" TREE_RECEIPT
    fifo_inventory=$(validate_tree_fifos "$tree_path" "$test_root") \
        || die 'TREE_RECEIPT FIFO authority is invalid'
    safe_absolute "$seal_path" SEAL_RECEIPT
    [ "$(dirname -- "$seal_path")" = "$test_root/authority" ] \
        || die 'SEAL_RECEIPT must be an authority-root child'
    require_nonempty_file "$seal_path" SEAL_RECEIPT
    set -- $(stat -Lc '%d %i %a' -- "$seal_path")
    seal_device=$1; seal_inode=$2; seal_mode=0$3
    seal_sha=$(sha256sum -- "$seal_path" | awk '{print $1}')
    validate_bound_file "$seal_path" "$seal_sha" "$seal_device" "$seal_inode" "$seal_mode" SEAL_RECEIPT

    inventory_sha=$(sha256sum -- "$manifest" | awk '{print $1}')
    set -- $(stat -Lc '%d %i %a' -- "$manifest")
    inventory_device=$1; inventory_inode=$2; inventory_mode=0$3
    seal_inventory_binding="{\"device\":\"$inventory_device\",\"inode\":\"$inventory_inode\",\"mode\":\"$inventory_mode\",\"path\":\"$manifest\",\"role\":\"preflight-manifest\",\"sha256\":\"$inventory_sha\"}"
    [ "$(grep -Fo -- "$seal_inventory_binding" "$seal_path" | wc -l)" -eq 1 ] \
        || die 'SEAL_RECEIPT does not bind this exact static inventory manifest'
    seal_tree_binding="{\"device\":\"$tree_device\",\"inode\":\"$tree_inode\",\"path\":\"$tree_path\",\"sha256\":\"$tree_sha\"}"
    [ "$(grep -Fo -- "$seal_tree_binding" "$seal_path" | wc -l)" -eq 1 ] \
        || die 'SEAL_RECEIPT does not bind the exact TREE_RECEIPT'
    seal_schema_binding='"schema":"scion.generic_backend.root_seal_receipt.v1"'
    [ "$(grep -Fo -- "$seal_schema_binding" "$seal_path" | wc -l)" -eq 1 ] \
        || die 'SEAL_RECEIPT schema is not exact'

    asset_count=$(awk -F '\t' '
        NR >= 7 {
            if (NF != 8 || $1 != "asset") exit 1
            roles[$2] += 1; paths[$4] += 1; ids[$6 ":" $7] += 1; n += 1
        }
        END {
            if (n == 0) exit 1
            for (key in roles) if (roles[key] != 1) exit 1
            for (key in paths) if (paths[key] != 1) exit 1
            for (key in ids) if (ids[key] != 1) exit 1
            print n
        }
    ' "$manifest") || die 'static asset inventory is empty, aliased or malformed'

    tab=$(printf '\t')
    tail -n +7 -- "$manifest" | while IFS="$tab" read -r record role kind path sha device inode mode extra; do
        [ "$record" = asset ] && [ -n "$role" ] && [ -n "$kind" ] && [ -z "${extra:-}" ] \
            || die 'static asset inventory record is malformed'
        printf '%s\n' "$role" | LC_ALL=C grep -Eq '^[a-z][a-z0-9]*([-_.][a-z0-9]+)*$' \
            || die "invalid static asset role: $role"
        case "$kind" in
            unit-fragment|python-program|json-plan|start-descriptor|installer-program|harness-program|static-input) ;;
            *) die "invalid static asset kind: $kind" ;;
        esac
        case "$path" in "$test_root/sealed/"*|"$test_root/input/"*) ;; *) die "$role asset is outside sealed/input" ;; esac
        validate_bound_file "$path" "$sha" "$device" "$inode" "$mode" "$role"
    done

    run_fragment=$(asset_path "$manifest" run-fragment)
    close_fragment=$(asset_path "$manifest" close-fragment)
    negative_fragment=$(asset_path "$manifest" gc-fragment)
    start_descriptor=$(asset_path "$manifest" start-descriptor)
    installer_program=$(asset_path "$manifest" installer-program)
    harness_program=$(asset_path "$manifest" harness-program)
    require_inventory_kind "$manifest" "$run_fragment" unit-fragment
    require_inventory_kind "$manifest" "$close_fragment" unit-fragment
    require_inventory_kind "$manifest" "$negative_fragment" unit-fragment
    require_inventory_kind "$manifest" "$start_descriptor" start-descriptor
    require_inventory_kind "$manifest" "$installer_program" installer-program
    require_inventory_kind "$manifest" "$harness_program" harness-program
    [ "$(basename -- "$run_fragment")" = "$run_unit" ] || die 'run fragment basename differs from RUN_UNIT'
    [ "$(basename -- "$close_fragment")" = "$close_unit" ] || die 'close fragment basename differs from CLOSE_UNIT'
    validate_run_fragment "$run_fragment" "$close_unit" "$test_root"
    validate_close_fragment "$close_fragment" "$run_unit" "$test_root"
    validate_negative_fragment "$negative_fragment" "$test_root"
    validate_identity_directives "$run_fragment" "$close_fragment" "$negative_fragment"
    validate_start_descriptor "$start_descriptor" "$run_unit"
    validate_argv_inventory "$manifest" "$run_fragment" ExecStart yes
    validate_argv_inventory "$manifest" "$run_fragment" ExecStopPost yes
    validate_argv_inventory "$manifest" "$close_fragment" ExecStart yes
    validate_argv_inventory "$manifest" "$negative_fragment" ExecStart yes

    [ ! -e "$destination" ] && [ ! -L "$destination" ] \
        || die 'preflight destination already exists; replacement is forbidden'
    mkdir -m 0700 -- "$destination"
    sync -f "$destination"
    sync -f "$test_root/authority"
    output="$destination/PREFLIGHT.json"
    [ ! -e "$output" ] && [ ! -L "$output" ] || die 'PREFLIGHT receipt already exists'
    printf '%s\n' \
        "{\"asset_count\":\"$asset_count\",\"close_unit\":\"$close_unit\",\"fifos\":$fifo_inventory,\"formal_root\":\"$test_root\",\"inventory_manifest\":{\"device\":\"$inventory_device\",\"inode\":\"$inventory_inode\",\"mode\":\"$inventory_mode\",\"path\":\"$manifest\",\"sha256\":\"$inventory_sha\"},\"phase\":\"static-preflight-complete\",\"run_unit\":\"$run_unit\",\"schema\":\"scion.generic_backend.static_preflight_receipt.v1\",\"seal_receipt\":{\"device\":\"$seal_device\",\"inode\":\"$seal_inode\",\"mode\":\"$seal_mode\",\"path\":\"$seal_path\",\"sha256\":\"$seal_sha\"},\"tree_receipt\":{\"device\":\"$tree_device\",\"inode\":\"$tree_inode\",\"mode\":\"$tree_mode\",\"path\":\"$tree_path\",\"sha256\":\"$tree_sha\"}}" \
        >"$output"
    chmod 0444 -- "$output"
    sync -f "$output"
    sync -f "$destination"
    chmod 0500 -- "$destination"
    sync -f "$destination"
    sync -f "$test_root/authority"
    sync -f "$test_root"
    sync -f "$(dirname -- "$test_root")"
}

[ "$#" -ge 1 ] || usage
command_name=$1
shift
case "$command_name" in
    preflight) preflight "$@" ;;
    *) usage ;;
esac
