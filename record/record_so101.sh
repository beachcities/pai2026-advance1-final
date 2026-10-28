#!/usr/bin/env bash
# SO-101 の録画を始める（所有者が自分のターミナルで実行する。矢印キーで操作するため）。
#   bash record/record_so101.sh trial    試し録り：2 本・30 秒。Hub には上げない（名前 …-v1-trial）
#   bash record/record_so101.sh main     本番：50 本。最後に Hub へ private で上げる
#   bash record/record_so101.sh resume   本番の続き：残りの本数を meta/info.json から計算して足す
#   bash record/record_so101.sh eval     推論：学習した方策が白いアームを動かす（既定 15 本＝場所ごとに 3 本。Hub には上げない）
# 実行する lerobot-record のコマンドを全文表示してから始めます。
# 値は環境変数で変えられます（既定値は下）。キーはこのターミナルで Enter 次へ / Backspace 録り直し / Esc やめる（record/lerobot_record_keys.py）。
# 1 本ごとに「場所 N の M 回目 どうぞ」を表示する（scripts/record_guide.py。場所は 1→PLACES と回す）。
set -euo pipefail
MODE="${1:-}"
case "$MODE" in trial|main|resume|eval) ;; *) sed -n '2,9p' "$0"; exit 2;; esac

HF_USER="${HF_USER:-beachcities}"
NAME="${DATASET_NAME:-so101-pickplace-v2}"   # v1 は白アームの台が外れる前の 3 本（使わない）
TASK="${TASK:-Pick up the yellow earplug and put it into the blue tape core.}"
TARGET="${NUM_EPISODES:-50}"
EPISODE_TIME_S="${EPISODE_TIME_S:-30}"
RESET_TIME_S="${RESET_TIME_S:-30}"
FPS="${FPS:-30}"
export PLACES="${PLACES:-5}"                      # 耳栓を置く場所の数（紙の印）
export PER_PLACE="${PER_PLACE:-10}"               # 1 か所あたりの本数（場所 1 を 10 本 → 場所 2 …）
FOLLOWER_PORT="${FOLLOWER_PORT:-/dev/ttyACM1}"   # 白フォロワー（7 月の記録）
LEADER_PORT="${LEADER_PORT:-/dev/ttyACM0}"       # 黒リーダー（7 月の記録）
ROBOT_ID="${ROBOT_ID:-white}"                     # キャリブレーションのファイル名 white.json に合わせる
TELEOP_ID="${TELEOP_ID:-black}"                   # 同 black.json
CAMERA="${CAMERA:-/dev/v4l/by-id/usb-046d_HD_Pro_Webcam_C920-video-index0}"  # C920。/dev/video0 は内蔵カメラ（BisonCam）なので使わない
ROTATION="${ROTATION:-0}"                         # カメラを逆さに付けたなら 180（0 / 90 / 180 / -90）

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
if [ "$MODE" = eval ]; then
  # lerobot は方策を使うときデータセット名が eval_ で始まることを求める
  POLICY_PATH="${POLICY_PATH:-$(cd "$(dirname "$0")/.." && pwd)/outputs/train/act_so101_pickplace_v2/checkpoints/last/pretrained_model}"
  [ -f "$POLICY_PATH/model.safetensors" ] || { echo "方策がありません: $POLICY_PATH"; exit 1; }
  REPO_ID="$HF_USER/eval_${NAME}_act"; N="${NUM_EPISODES:-15}"; TARGET="$N"
  # 冒頭の PER_PLACE（録画の既定 10）を上書きする。推論は場所ごとに EVAL_PER_PLACE 本
  export PER_PLACE="${EVAL_PER_PLACE:-3}"; export EVAL=1
  # 時間切れで勝手に次へ進まないよう長めにする（終わったら Enter）
  EPISODE_TIME_S="${EVAL_EPISODE_TIME_S:-60}"; RESET_TIME_S="${EVAL_RESET_TIME_S:-120}"
  # 方策が大きく跳んだ指令を出したときだけ抑える（1 回の指令で動ける角度の上限）。
  # 録画では指令と実際の位置の差が手首の曲げで上位 1% 38 度あったので、普通の動きを妨げない 40 度にする
  EXTRA+=(--policy.path="$POLICY_PATH" --dataset.push_to_hub=false --robot.max_relative_target="${MAX_RELATIVE_TARGET:-40}")
fi
DIR="$LR/$REPO_ID"
if [ "$MODE" = resume ]; then
  [ -f "$DIR/meta/info.json" ] || { echo "続きを録るデータセットがありません: $REPO_ID"; exit 1; }
  DONE=$(python -c 'import json,sys; print(json.load(open(sys.argv[1]))["total_episodes"])' "$DIR/meta/info.json")
  N=$(( TARGET - DONE ))
  [ "$N" -gt 0 ] || { echo "既に $DONE 本あります（目標 $TARGET 本）。録る必要はありません"; exit 0; }
  echo "既に $DONE 本。残り $N 本を足します"
  EXTRA+=(--resume=true)
elif [ -e "$DIR" ]; then
  if [ "$MODE" = trial ] || [ "$MODE" = eval ]; then
    BAK="$DIR.bak-$(date +%Y%m%d_%H%M%S)"
    if [ "${DRY_RUN:-0}" = 1 ]; then echo "（表示だけ）前の分を ${BAK#$LR/} に退けます"
    else mv "$DIR" "$BAK"; echo "前の分を ${BAK#$LR/} に退けました"; fi
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
# カメラの自動調整を固定した値に戻す（scripts/camera_lock.sh lock で保存した値。無ければ自動のまま）
if [ -f "$(dirname "$0")/../outputs/camera_c920.env" ]; then CAMERA="$CAMERA" bash "$(dirname "$0")/../scripts/camera_lock.sh" apply
else echo "注意: outputs/camera_c920.env が無いので、カメラは自動調整のまま録ります（bash scripts/camera_lock.sh lock）"; fi
SHOW="${DISPLAY_DATA:-true}"   # rerun の窓を出さないなら DISPLAY_DATA=false
if [ "$SHOW" = true ] && ! python -c 'import rerun' 2>/dev/null; then SHOW=false; echo "rerun が無いので --display_data=false にします"; fi

CMD=(python "$(cd "$(dirname "$0")" && pwd)/lerobot_record_keys.py"   # lerobot-record と同じ。Enter で次へ
  --robot.type=so101_follower --robot.port="$FOLLOWER_PORT" --robot.id="$ROBOT_ID"
  --robot.cameras="{front: {type: opencv, index_or_path: $CAMERA, width: 640, height: 480, fps: $FPS, rotation: $ROTATION}}"
  --teleop.type=so101_leader --teleop.port="$LEADER_PORT" --teleop.id="$TELEOP_ID"
  --dataset.repo_id="$REPO_ID" --dataset.single_task="$TASK"
  --dataset.num_episodes="$N" --dataset.episode_time_s="$EPISODE_TIME_S" --dataset.reset_time_s="$RESET_TIME_S"
  --dataset.fps="$FPS" --dataset.private=true --display_data="$SHOW" --play_sounds=false --dataset.streaming_encoding=true --dataset.encoder_threads=2 "${EXTRA[@]}")
echo "lerobot $LEROBOT_VERSION / 開始 $(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '%q ' "${CMD[@]}"; echo
[ "${DRY_RUN:-0}" = 1 ] && exit 0
HERE="$(cd "$(dirname "$0")/.." && pwd)"
NEXT=0; [ "$MODE" = resume ] && NEXT="$DONE"
FIRST_PLACE=$(( NEXT / PER_PLACE + 1 > PLACES ? PLACES : NEXT / PER_PLACE + 1 ))
echo "■ 接続中です。まだ Enter は押さないでください（押しても無視されます）"
echo "  この間に、耳栓を 場所 $FIRST_PLACE に置き、腕を開始姿勢にしてください（$(( NEXT + 1 )) 回目）"
STAMP=$(date +%Y%m%d_%H%M%S); export KEY_LOG="$HERE/outputs/keys_$STAMP.log"   # 押されたキーと区間の始まり（原因調べ用）
PYTHONUNBUFFERED=1 "${CMD[@]}" 2>&1 | tee "$HERE/outputs/record_$STAMP.log" | python3 "$HERE/scripts/record_guide.py" --places "$PLACES" --per-place "$PER_PLACE" \
  --total "$([ "$MODE" = trial ] && echo "$N" || echo "$TARGET")" --episode-s "$EPISODE_TIME_S" --reset-s "$RESET_TIME_S" --log "$HERE/outputs/places_${REPO_ID##*/}.csv"
echo "終了 $(date -u +%Y-%m-%dT%H:%M:%SZ)"
