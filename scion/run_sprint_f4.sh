#!/usr/bin/env bash
# run_sprint_f4.sh — Sprint F4 正式实验启动脚本
#
# 实验矩阵：
#   Group A (baseline): split_manifest.yaml       — 已在 F3 完成，不重跑
#   Group B (prod):     split_manifest_prod.yaml  — 纯生产风格 benchmark
#   Group C (mixed):    split_manifest_mixed.yaml — 合成 scr/val + 生产 frozen
#
# 用法：
#   ./run_sprint_f4.sh b        # 只跑 Group B
#   ./run_sprint_f4.sh c        # 只跑 Group C
#   ./run_sprint_f4.sh b c      # 并行跑 B + C

set -euo pipefail

SCION_DIR="/home/clawd/research/or-autoresearch-agent/scion"
PYTHON="/home/clawd/miniconda3/envs/claw/bin/python"
EXPBASE="/home/clawd/research/scion-experiments/sprint-f4"
PROBLEM_DIR="$SCION_DIR/problems/warehouse_delivery"
ROUNDS=200

# API Key
source ~/.openclaw/.env 2>/dev/null || true
if [ -z "${SCION_API_KEY:-}" ]; then
    echo "ERROR: SCION_API_KEY not set" >&2
    exit 1
fi

mkdir -p "$EXPBASE"

run_group() {
    local group="$1"          # b or c
    local manifest="$2"       # split_manifest_prod.yaml or split_manifest_mixed.yaml
    local label="group_${group}"
    local exp_dir="$EXPBASE/$label"
    local log_file="$EXPBASE/${label}.log"

    mkdir -p "$exp_dir"
    echo "[$(date '+%H:%M:%S')] Starting Group $group → $exp_dir"

    nohup bash -c "
        cd $SCION_DIR
        SCION_CAMPAIGN_DIR=$exp_dir \
        SCION_MODEL=claude-opus-4-6 \
        SCION_API_KEY=$SCION_API_KEY \
        SCION_SPLIT_MANIFEST=$PROBLEM_DIR/$manifest \
        $PYTHON run_v3_campaign.py $ROUNDS \
        > $log_file 2>&1
        echo 'EXIT_CODE='$? >> $log_file
        touch $EXPBASE/${label}_done
        openclaw system event --text '[Sprint F4] Group $group 完成 (${ROUNDS}r)' --mode now
    " &>/dev/null &

    echo "  PID=$! log=$log_file"
}

GROUPS=("$@")
if [ ${#GROUPS[@]} -eq 0 ]; then
    echo "Usage: $0 [a] [b] [c]"
    echo "  a = Group A (synthetic baseline, 200r stability test)"
    echo "  b = Group B (pure production-style)"
    echo "  c = Group C (mixed: synthetic scr/val + production frozen)"
    exit 1
fi

for g in "${GROUPS[@]}"; do
    case "$g" in
        a) run_group "a" "split_manifest.yaml" ;;
        b) run_group "b" "split_manifest_prod.yaml" ;;
        c) run_group "c" "split_manifest_mixed.yaml" ;;
        *) echo "Unknown group: $g (valid: a b c)" ;;
    esac
done

echo ""
echo "Started. Monitor with:"
for g in "${GROUPS[@]}"; do
    echo "  tail -f $EXPBASE/group_${g}.log"
done
