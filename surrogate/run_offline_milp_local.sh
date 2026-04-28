#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Offline MILP local launcher

Usage:
  ./surrogate/run_offline_milp_local.sh --family synthetic
  ./surrogate/run_offline_milp_local.sh --family production
  ./surrogate/run_offline_milp_local.sh --family production --limit 2
  ./surrogate/run_offline_milp_local.sh --manifest /abs/path/to/manifest.yaml --family production --out-dir /tmp/milp-prod
  ./surrogate/run_offline_milp_local.sh --family production --python /path/to/python
  ./surrogate/run_offline_milp_local.sh --family production --data-root /path/to/scion-data

Options:
  --family synthetic|production   Required unless --manifest is paired with --family
  --manifest PATH                 Override manifest path
  --out-dir PATH                  Override output directory
  --python PATH                   Python executable to use
  --data-root PATH                Local scion-data root for production manifests with absolute server paths
  --limit N                       Only run first N instances after manifest de-dup
  --tag NAME                      Optional suffix for output directory name
  -h, --help                      Show help

Notes:
  - Run this from the repo root, or let the script auto-detect the repo root.
  - Default manifests:
      synthetic  -> scion/problems/warehouse_delivery/split_manifest.yaml
      production -> scion/problems/warehouse_delivery/split_manifest_prod.yaml
  - Default output root:
      ./offline-milp-benchmark/<timestamp>[-tag]/<family>
  - For production, this script can rewrite server-side absolute paths such as
      /home/clawd/research/scion-data/...
    to your local data root automatically.
EOF
}

FAMILY=""
MANIFEST=""
OUT_DIR=""
PYTHON_BIN="${PYTHON_BIN:-python}"
DATA_ROOT=""
LIMIT=0
TAG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --family)
      FAMILY="$2"
      shift 2
      ;;
    --manifest)
      MANIFEST="$2"
      shift 2
      ;;
    --out-dir)
      OUT_DIR="$2"
      shift 2
      ;;
    --python)
      PYTHON_BIN="$2"
      shift 2
      ;;
    --data-root)
      DATA_ROOT="$2"
      shift 2
      ;;
    --limit)
      LIMIT="$2"
      shift 2
      ;;
    --tag)
      TAG="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$FAMILY" ]]; then
  echo "ERROR: --family is required" >&2
  usage >&2
  exit 2
fi
if [[ "$FAMILY" != "synthetic" && "$FAMILY" != "production" ]]; then
  echo "ERROR: --family must be synthetic or production" >&2
  exit 2
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

if [[ -z "$MANIFEST" ]]; then
  if [[ "$FAMILY" == "synthetic" ]]; then
    MANIFEST="$REPO_ROOT/scion/problems/warehouse_delivery/split_manifest.yaml"
  else
    MANIFEST="$REPO_ROOT/scion/problems/warehouse_delivery/split_manifest_prod.yaml"
  fi
fi

if [[ ! -f "$MANIFEST" ]]; then
  echo "ERROR: manifest not found: $MANIFEST" >&2
  exit 2
fi

if [[ -z "$OUT_DIR" ]]; then
  TS="$(date +%Y%m%d-%H%M%S)"
  SUFFIX=""
  if [[ -n "$TAG" ]]; then
    SUFFIX="-$TAG"
  fi
  OUT_DIR="$REPO_ROOT/offline-milp-benchmark/${TS}${SUFFIX}/$FAMILY"
fi
mkdir -p "$OUT_DIR"

RESOLVED_MANIFEST="$MANIFEST"
if [[ "$FAMILY" == "production" ]]; then
  if [[ -z "$DATA_ROOT" ]]; then
    if [[ -d "$REPO_ROOT/../scion-data" ]]; then
      DATA_ROOT="$(cd "$REPO_ROOT/../scion-data" && pwd)"
    elif [[ -d "$HOME/research-local/scion-data" ]]; then
      DATA_ROOT="$(cd "$HOME/research-local/scion-data" && pwd)"
    fi
  fi

  if [[ -n "$DATA_ROOT" ]]; then
    if [[ ! -d "$DATA_ROOT" ]]; then
      echo "ERROR: --data-root does not exist: $DATA_ROOT" >&2
      exit 2
    fi
    RESOLVED_MANIFEST="$OUT_DIR/manifest.local.yaml"
    python3 - <<'PY' "$MANIFEST" "$RESOLVED_MANIFEST" "$DATA_ROOT"
import sys
from pathlib import Path
import yaml
src = Path(sys.argv[1])
out = Path(sys.argv[2])
data_root = Path(sys.argv[3]).resolve()
raw = yaml.safe_load(src.read_text(encoding='utf-8'))
server_prefix = '/home/clawd/research/scion-data/'

def remap(value):
    s = str(value)
    if s.startswith(server_prefix):
        rel = s[len(server_prefix):]
        return str((data_root / rel).resolve())
    return s

for split in ['canary', 'screening', 'validation', 'frozen']:
    raw[split] = [remap(v) for v in raw.get(split, []) or []]
out.write_text(yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding='utf-8')
print(out)
PY
  fi
fi

cat <<EOF
[offline-milp-local]
repo_root=$REPO_ROOT
family=$FAMILY
manifest=$MANIFEST
resolved_manifest=$RESOLVED_MANIFEST
out_dir=$OUT_DIR
python=$PYTHON_BIN
data_root=${DATA_ROOT:-}
limit=$LIMIT
start_time=$(date '+%Y-%m-%d %H:%M:%S %z')
EOF

RUNNER="$REPO_ROOT/surrogate/run_offline_milp_batch.py"
CMD=(
  "$PYTHON_BIN"
  "$RUNNER"
  --manifest "$RESOLVED_MANIFEST"
  --family "$FAMILY"
  --out-dir "$OUT_DIR"
)
if [[ "$LIMIT" != "0" ]]; then
  CMD+=(--limit "$LIMIT")
fi

printf '\n[offline-milp-local] command:\n'
printf ' %q' "${CMD[@]}"
printf '\n\n'

exec "${CMD[@]}"
