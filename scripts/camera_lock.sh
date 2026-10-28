#!/usr/bin/env bash
# C920 の自動調整（ピント・露出・ホワイトバランス）を固定する（アームは動かさない）。
#   bash scripts/camera_lock.sh lock    いまの自動調整が落ち着いた値で固定し、値を outputs/camera_c920.env に保存
#   bash scripts/camera_lock.sh apply   保存した値を設定し直す（抜き差しや再起動の後。record_so101.sh も最初に呼ぶ）
#   bash scripts/camera_lock.sh show    いまの値を表示
#   bash scripts/camera_lock.sh auto    自動調整に戻す
set -euo pipefail
DEV="${CAMERA:-/dev/v4l/by-id/usb-046d_HD_Pro_Webcam_C920-video-index0}"
ENV_FILE="$(cd "$(dirname "$0")/.." && pwd)/outputs/camera_c920.env"
KEYS="focus_absolute exposure_time_absolute gain white_balance_temperature brightness zoom_absolute"
get() { v4l2-ctl -d "$DEV" -C "$1" | awk '{print $2}'; }
show() { for k in focus_automatic_continuous auto_exposure white_balance_automatic exposure_dynamic_framerate power_line_frequency $KEYS; do printf '%s=%s\n' "$k" "$(get "$k")"; done; }

case "${1:-}" in
  lock)
    # 自動調整を有効にしたまま映像を流して落ち着かせ、そのあと自動を切る（切った時点の値が残る）
    v4l2-ctl -d "$DEV" -c focus_automatic_continuous=1 -c auto_exposure=3 -c white_balance_automatic=1 -c exposure_dynamic_framerate=0
    v4l2-ctl -d "$DEV" --stream-mmap --stream-count=90 --stream-to=/dev/null
    v4l2-ctl -d "$DEV" -c focus_automatic_continuous=0 -c auto_exposure=1 -c white_balance_automatic=0
    mkdir -p "$(dirname "$ENV_FILE")"
    for k in $KEYS; do printf '%s=%s\n' "$k" "$(get "$k")"; done > "$ENV_FILE"
    echo "固定して保存しました: outputs/camera_c920.env"; cat "$ENV_FILE";;
  apply)
    [ -f "$ENV_FILE" ] || { echo "outputs/camera_c920.env がありません。先に lock を実行してください"; exit 1; }
    v4l2-ctl -d "$DEV" -c focus_automatic_continuous=0 -c auto_exposure=1 -c white_balance_automatic=0 -c exposure_dynamic_framerate=0
    args=(); while IFS='=' read -r k v; do [ -n "$k" ] && args+=(-c "$k=$v"); done < "$ENV_FILE"
    v4l2-ctl -d "$DEV" "${args[@]}"
    echo "outputs/camera_c920.env の値を設定しました";;
  show) show;;
  auto) v4l2-ctl -d "$DEV" -c focus_automatic_continuous=1 -c auto_exposure=3 -c white_balance_automatic=1; echo "自動調整に戻しました";;
  *) sed -n '2,6p' "$0"; exit 2;;
esac
