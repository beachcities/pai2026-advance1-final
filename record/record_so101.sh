#!/usr/bin/env bash
# SO-101 の録画を始める（所有者が自分のターミナルで実行する。矢印キーで操作するため）。
#   bash record/record_so101.sh trial    試し録り：2 本・30 秒。Hub には上げない（名前 …-v1-trial）
#   bash record/record_so101.sh main     本番：50 本。最後に Hub へ private で上げる
#   bash record/record_so101.sh resume   本番の続き：残りの本数を meta/info.json から計算して足す
# 実行する lerobot-record のコマンドを全文表示してから始めます。
# 値は環境変数で変えられます（既定値は下）。キー: → 次へ / ← 録り直し / Esc 止める（それまでの分は保存）。
set -euo pipefail
MODE="${1:-}"
case "$MODE" in trial|main|resume) ;; *) sed -n '2,8p' "$0"; exit 2;; esac

HF_USER="${HF_USER:-beachcities}"
NAME="${DATASET_NAME:-so101-pickplace-v1}"
TASK="${TASK:-Pick up the yellow earplug and put it into the blue tape core.}"
TARGET="${NUM_EPISODES:-50}"
EPISODE_TIME_S="${EPISODE_TIME_S:-30}"
RESET_TIME_S="${RESET_TIME_S:-15}"
FPS="${FPS:-30}"
FOLLOWER_PORT="${FOLLOWER_PORT:-/dev/ttyACM1}"   # 白フォロワー（7 月の記録）
LEADER_PORT="${LEADER_PORT:-/dev/ttyACM0}"       # 黒リーダー（7 月の記録）
ROBOT_ID="${ROBOT_ID:-white}"                     # キャリブレーションのファイル名 white.json に合わせる
TELEOP_ID="${TELEOP_ID:-black}"                   # 同 black.json
CAMERA="${CAMERA:-0}"                             # /dev/video0（C920）。/dev/v4l/by-id/… のパスでも可

# lerobot の venv
if [ -n "${LEROBOT_VENV:-}" ]; then source "$LEROBOT_VENV/bin/activate"
elif ! command -v lerobot-record >/dev/null; then
  for c in "$HOME/lerobot-venv" "$HOME/lerobot/.venv" "$HOME/.venv"; do
    [ -x "$c/bin/lerobot-record" ] && { source "$c/bin/activate"; break; }
  done
fi
command -v lerobot-record >/dev/null || { echo "lerobot-record が見つかりません。LEROBOT_VENV=<venv> を付けて実行してください"; exit 1; }
LEROBOT_VERSION=$(python -c 'import importlib.metadata as m; print(m.version("lerobot"))' 2>/dev/null || echo 不明)

# ポートとキャリブレーションの確認（アームは動かさない）
for p in "$FOLLOWER_PORT" "$LEADER_PORT"; do [ -e "$p" ] || { echo "ポート $p がありません（USB を確認）"; exit 1; }; done
[ "$(readlink -f "$FOLLOWER_PORT")" != "$(readlink -f "$LEADER_PORT")" ] || { echo "フォロワーとリーダーのポートが同じです"; exit 1; }
LR="${HF_LEROBOT_HOME:-${HF_HOME:-$HOME/.cache/huggingface}/lerobot}"
for f in "$LR/calibration/robots/so_follower/$ROBOT_ID.json" "$LR/calibration/teleoperators/so_leader/$TELEOP_ID.json"; do
  if [ ! -f "$f" ]; then
    echo "キャリブレーションのファイルがありません: ${f#$LR/}"
    echo "7 月の退避分を戻すなら: hf download beachcities/so101-migration-backup --repo-type dataset --include 'calibration/*' --local-dir \"$LR\""
    exit 1
  fi
done

REPO_ID="$HF_USER/$NAME"; EXTRA=(); N="$TARGET"
[ "$MODE" = trial ] && { REPO_ID="$REPO_ID-trial"; N="${NUM_EPISODES:-2}"; EXTRA+=(--dataset.push_to_hub=false); }
DIR="$LR/$REPO_ID"
if [ "$MODE" = resume ]; then
  [ -f "$DIR/meta/info.json" ] || { echo "続きを録るデータセットがありません: $REPO_ID"; exit 1; }
  DONE=$(python -c 'import json,sys; print(json.load(open(sys.argv[1]))["total_episodes"])' "$DIR/meta/info.json")
  N=$(( TARGET - DONE ))
  [ "$N" -gt 0 ] || { echo "既に $DONE 本あります（目標 $TARGET 本）。録る必要はありません"; exit 0; }
  echo "既に $DONE 本。残り $N 本を足します"
  EXTRA+=(--resume=true)
elif [ -e "$DIR" ]; then
  if [ "$MODE" = trial ]; then
    BAK="$DIR.bak-$(date +%Y%m%d_%H%M%S)"; mv "$DIR" "$BAK"; echo "前の試し録りを ${BAK#$LR/} に退けました"
  else
    echo "$REPO_ID は既に手元にあります。続きを録るなら: bash record/record_so101.sh resume"; exit 1
  fi
fi
# lerobot 0.6 以降は、指定しないとデータセット名の末尾に日時を付ける（configs/dataset.py の stamp_repo_id）
HAS_NO_STAMP=$(python - <<'PY2' 2>/dev/null || true
try:
    from lerobot.configs.dataset import DatasetRecordConfig          # 0.6 以降
except ImportError:
    from lerobot.scripts.lerobot_record import DatasetRecordConfig   # 0.4.x
print("no_stamp" in DatasetRecordConfig.__dataclass_fields__)
PY2
)
[ -n "$HAS_NO_STAMP" ] || { lerobot-record --help 2>/dev/null | grep -q 'no_stamp' && HAS_NO_STAMP=True; }
[ "$HAS_NO_STAMP" = True ] && EXTRA+=(--dataset.no_stamp=true)
SHOW=true; python -c 'import rerun' 2>/dev/null || { SHOW=false; echo "rerun が無いので --display_data=false にします"; }

CMD=(lerobot-record
  --robot.type=so101_follower --robot.port="$FOLLOWER_PORT" --robot.id="$ROBOT_ID"
  --robot.cameras="{front: {type: opencv, index_or_path: $CAMERA, width: 640, height: 480, fps: $FPS}}"
  --teleop.type=so101_leader --teleop.port="$LEADER_PORT" --teleop.id="$TELEOP_ID"
  --dataset.repo_id="$REPO_ID" --dataset.single_task="$TASK"
  --dataset.num_episodes="$N" --dataset.episode_time_s="$EPISODE_TIME_S" --dataset.reset_time_s="$RESET_TIME_S"
  --dataset.fps="$FPS" --dataset.private=true --display_data="$SHOW" "${EXTRA[@]}")
echo "lerobot $LEROBOT_VERSION / 開始 $(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '%q ' "${CMD[@]}"; echo
[ "${DRY_RUN:-0}" = 1 ] && exit 0
"${CMD[@]}"
echo "終了 $(date -u +%Y-%m-%dT%H:%M:%SZ)"
