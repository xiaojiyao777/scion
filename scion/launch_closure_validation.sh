#!/usr/bin/env bash
# launch_closure_validation.sh
#
# Thin wrapper that starts run_closure_validation.py under nohup+setsid so
# the launcher (and all its campaign subprocesses) survive terminal disconnect.
# Per scion/CLAUDE.md rule: "never bare tmux" for long-running experiments.
#
# Usage:
#   ./launch_closure_validation.sh                 # defaults (v03-closure-validation)
#   ./launch_closure_validation.sh my-runs 2 100 production
#                                                # base_dir concurrent rounds variant
#
# To check status after launch:
#   cat ~/research/scion-experiments/<base_dir>/status.json
#   tail -f ~/research/scion-experiments/<base_dir>/launcher.log
#
# To stop early:
#   kill -TERM <launcher_pid>    (graceful: sends SIGTERM to campaign PGs)

set -euo pipefail

BASE_DIR="${1:-v03-closure-validation}"
MAX_CONCURRENT="${2:-2}"
MAX_ROUNDS="${3:-100}"
VARIANT="${4:-synthetic}"

SCION_DIR="$(cd "$(dirname "$0")" && pwd)"
OUT_DIR="$HOME/research/scion-experiments/$BASE_DIR"
mkdir -p "$OUT_DIR"

LAUNCHER_LOG="$OUT_DIR/launcher.log"
PID_FILE="$OUT_DIR/launcher.pid"

# Refuse if an old launcher is still alive
if [[ -f "$PID_FILE" ]]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "ERROR: launcher already running: pid=$OLD_PID" >&2
        echo "       stop with: kill -TERM $OLD_PID" >&2
        exit 1
    fi
    rm -f "$PID_FILE"
fi

PY="/home/clawd/miniconda3/envs/claw/bin/python"

echo "Starting v0.3 closure validation launcher"
echo "  base_dir       : $BASE_DIR"
echo "  max_concurrent : $MAX_CONCURRENT"
echo "  max_rounds     : $MAX_ROUNDS"
echo "  variant        : $VARIANT"
echo "  output         : $OUT_DIR"
echo "  launcher log   : $LAUNCHER_LOG"
echo ""

# nohup + setsid: launcher runs in a new session, detached from this TTY.
# Redirect all output to the launcher log (the Python script also writes to it).
nohup setsid "$PY" "$SCION_DIR/run_closure_validation.py" \
    --base-dir "$BASE_DIR" \
    --max-concurrent "$MAX_CONCURRENT" \
    --max-rounds "$MAX_ROUNDS" \
    --variant "$VARIANT" \
    >> "$LAUNCHER_LOG" 2>&1 &
LAUNCHER_PID=$!

echo "$LAUNCHER_PID" > "$PID_FILE"

echo "Launcher PID : $LAUNCHER_PID"
echo "PID file     : $PID_FILE"
echo ""
echo "Monitor:"
echo "  tail -f $LAUNCHER_LOG"
echo "  watch -n 10 cat $OUT_DIR/status.json"
echo ""
echo "Stop:"
echo "  kill -TERM \$(cat $PID_FILE)"
