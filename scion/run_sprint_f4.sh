#!/usr/bin/env bash
# run_sprint_f4.sh — Sprint F4 正式实验启动脚本（tmux）
#
# 实验矩阵（200r each）：
#   Group A: split_manifest.yaml      — 合成基线 200r 稳定性验证
#   Group B: split_manifest_prod.yaml — 纯生产风格 benchmark
#   Group C: split_manifest_mixed.yaml — 合成 scr/val + 生产 frozen 泛化验证
#
# 用法：
#   ./run_sprint_f4.sh a b c    # 三组并行（推荐）
#   ./run_sprint_f4.sh b c      # 只跑 B+C
#   ./run_sprint_f4.sh a        # 只跑 A

set -euo pipefail

SCION_DIR="/home/clawd/research/or-autoresearch-agent/scion"
PYTHON="/home/clawd/miniconda3/envs/claw/bin/python"
EXPBASE="/home/clawd/research/scion-experiments/sprint-f4"
PROBLEM_DIR="$SCION_DIR/problems/warehouse_delivery"
ROUNDS=200
MODEL="claude-opus-4-6"

# API Key
SCION_API_KEY="$(grep SCION_API_KEY ~/.openclaw/.env | cut -d= -f2)"
if [ -z "${SCION_API_KEY:-}" ]; then
    echo "ERROR: SCION_API_KEY not found in ~/.openclaw/.env" >&2
    exit 1
fi

GROUPS=("$@")
if [ ${#GROUPS[@]} -eq 0 ]; then
    echo "Usage: $0 [a] [b] [c]"
    echo "  a = Group A: synthetic baseline, 200r stability test"
    echo "  b = Group B: pure production-style benchmark"
    echo "  c = Group C: mixed (synthetic scr/val + production frozen)"
    exit 1
fi

mkdir -p "$EXPBASE"

launch_group() {
    local group="$1"
    local manifest="$2"
    local session="scion-f4-${group}"
    local exp_dir="$EXPBASE/group_${group}"
    local log_file="$EXPBASE/group_${group}.log"

    # Kill existing session if any
    tmux kill-session -t "$session" 2>/dev/null || true

    mkdir -p "$exp_dir"

    local cmd="cd $SCION_DIR && \
SCION_API_KEY=$SCION_API_KEY \
SCION_CAMPAIGN_DIR=$exp_dir \
SCION_MODEL=$MODEL \
SCION_SPLIT_MANIFEST=$PROBLEM_DIR/$manifest \
$PYTHON run_v3_campaign.py $ROUNDS \
> $log_file 2>&1 && \
openclaw system event --text '[Sprint F4] Group $group 完成 (${ROUNDS}r)' --mode now; \
echo '[DONE] exit code: '$?"

    tmux new-session -d -s "$session" bash
    tmux send-keys -t "$session" "$cmd" Enter

    echo "  Group $group → tmux: $session | log: $log_file"
}

echo "Starting Sprint F4 (${ROUNDS}r per group)..."
echo ""

for g in "${GROUPS[@]}"; do
    case "$g" in
        a) launch_group "a" "split_manifest.yaml" ;;
        b) launch_group "b" "split_manifest_prod.yaml" ;;
        c) launch_group "c" "split_manifest_mixed.yaml" ;;
        *) echo "Unknown group: $g (valid: a b c)" ;;
    esac
done

echo ""
echo "Monitor:"
for g in "${GROUPS[@]}"; do
    echo "  tmux attach -t scion-f4-${g}     # interactive"
    echo "  tail -f $EXPBASE/group_${g}.log  # log only"
done
