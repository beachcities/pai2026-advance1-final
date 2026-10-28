#!/usr/bin/env bash
# このマシン（CUDA の GPU）で ACT を学習する。ターミナルを閉じても止まらない（setsid + nohup）。
#   bash train/train_act_local.sh start    新しく始める（ログは outputs/logs/）
#   bash train/train_act_local.sh resume   checkpoints/last から再開する
#   bash train/train_act_local.sh status   動いているか・最新のロス・完了予定
#   bash train/train_act_local.sh stop     止める（チェックポイントは残る。resume で続きから）
# リポジトリの直下で実行します。outputs/ は .gitignore 済みです。
set -euo pipefail
MODE="${1:-}"
case "$MODE" in start|resume|status|stop) ;; *) sed -n '2,7p' "$0"; exit 2;; esac
cd "$(dirname "$0")/.."

HF_USER="${HF_USER:-beachcities}"
DATASET="${DATASET:-$HF_USER/so101-pickplace-v2}"
RUN="${RUN:-act_so101_pickplace_v2}"   # データセット v2 に合わせる
POLICY_REPO="${POLICY_REPO:-$HF_USER/$RUN}"
STEPS="${STEPS:-100000}"; BATCH="${BATCH:-8}"; SAVE_FREQ="${SAVE_FREQ:-5000}"
OUT="outputs/train/$RUN"; LOGDIR="outputs/logs"; PIDFILE="$LOGDIR/$RUN.pid"
mkdir -p "$LOGDIR"

running() { [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; }
latest_log() { ls -t "$LOGDIR/$RUN"_*.log 2>/dev/null | head -1; }

if [ "$MODE" = status ]; then
  if running; then echo "動いています（PID $(cat "$PIDFILE")）"; else echo "動いていません"; fi
  L=$(latest_log); [ -n "$L" ] || { echo "ログがありません"; exit 0; }
  echo "ログ: $L"; tail -n 3 "$L"
  ls -1 "$OUT/checkpoints" 2>/dev/null | tr '\n' ' ' | sed 's/^/チェックポイント: /'; echo
  python3 scripts/train_eta.py "$L" --total-steps "$STEPS" || true
  exit 0
fi
if [ "$MODE" = stop ]; then
  running || { echo "動いていません"; exit 0; }
  kill -INT -- "-$(cat "$PIDFILE")" 2>/dev/null || kill -INT "$(cat "$PIDFILE")"; echo "止める合図を送りました"; exit 0
fi
running && { echo "既に動いています（PID $(cat "$PIDFILE")）。status で確認してください"; exit 1; }

# lerobot の venv
if [ -n "${LEROBOT_VENV:-}" ]; then source "$LEROBOT_VENV/bin/activate"
elif ! command -v lerobot-train >/dev/null; then
  for c in "$HOME/lerobot-venv" "$HOME/lerobot/.venv" "$HOME/.venv"; do
    [ -x "$c/bin/lerobot-train" ] && { source "$c/bin/activate"; break; }
  done
fi
command -v lerobot-train >/dev/null || { echo "lerobot-train が見つかりません。LEROBOT_VENV=<venv> を付けて実行してください"; exit 1; }

# GPU（無ければ Colab に切り替える: train/colab_train.ipynb）
if ! python -c 'import torch,sys; sys.exit(0 if torch.cuda.is_available() else 1)' 2>/dev/null; then
  echo "CUDA の GPU が使えません。train/colab_train.ipynb（Colab A100）で学習してください（DATASET_REPO_ID=\"$DATASET\"）"; exit 1
fi
python -c 'import torch; p=torch.cuda.get_device_properties(0); print(f"GPU: {p.name} / {p.total_memory/2**30:.1f} GiB")'
# 空きディスク（ACT のチェックポイントは 1 個あたり数百 MB の見込み × STEPS/SAVE_FREQ 個）
FREE_GB=$(df -P --block-size=1G . | awk 'NR==2{print $4}')
echo "空きディスク: ${FREE_GB} GB"
[ "$FREE_GB" -ge 20 ] || echo "注意: 空きが 20 GB 未満です（チェックポイント $((STEPS / SAVE_FREQ)) 個ぶん）"

TS=$(date +%Y%m%d_%H%M%S); LOG="$LOGDIR/${RUN}_${MODE}_$TS.log"
if [ "$MODE" = start ]; then
  [ -e "$OUT" ] && { echo "$OUT が既にあります。続きなら resume、やり直すなら $OUT を別名に退けてください"; exit 1; }
  CMD=(lerobot-train --dataset.repo_id="$DATASET" --policy.type=act --policy.device=cuda
       --output_dir="$OUT" --job_name="$RUN" --steps="$STEPS" --batch_size="$BATCH" --save_freq="$SAVE_FREQ"
       --policy.push_to_hub=true --policy.repo_id="$POLICY_REPO" --policy.private=true --wandb.enable=false)
else
  CFG="$OUT/checkpoints/last/pretrained_model/train_config.json"
  [ -f "$CFG" ] || { echo "再開できるチェックポイントがありません: $CFG"; exit 1; }
  CMD=(lerobot-train --config_path="$CFG" --resume=true)
fi
{ echo "開始 $(date -u +%Y-%m-%dT%H:%M:%SZ)"; printf '%q ' "${CMD[@]}"; echo; } | tee "$LOG"
setsid nohup "${CMD[@]}" >> "$LOG" 2>&1 < /dev/null &
echo $! > "$PIDFILE"
echo "起動しました（PID $(cat "$PIDFILE")）。ログ: $LOG"
echo "確認: bash train/train_act_local.sh status"
