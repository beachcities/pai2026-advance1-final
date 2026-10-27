#!/usr/bin/env bash
# 録画・学習の前の確認（アームは動かさない。トークンの値は表示しない）。
# 使い方: bash scripts/preflight.sh            （lerobot の venv を自動で探す）
#         LEROBOT_VENV=<venv のパス> bash scripts/preflight.sh
# カメラの検出（lerobot-find-cameras）はカメラを開くだけで、アームは動かしません。
# 検出で撮った画像は outputs/ に保存されます（.gitignore 済み。commit しない）。
set -u
T="~"
say() { printf '\n== %s ==\n' "$1"; }

say "時刻"
date -u '+%Y-%m-%dT%H:%M:%SZ'; TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M:%S JST'

say "OS"
. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME"; uname -r

say "GPU"
if command -v nvidia-smi >/dev/null; then
  nvidia-smi --query-gpu=name,memory.total,memory.used,driver_version --format=csv,noheader
else
  echo "nvidia-smi が見つかりません（GPU なし、またはドライバ未導入）"
fi

say "空きディスク（ホームとこのリポジトリ）"
df -h "$HOME" . | awk 'NR==1 || !seen[$0]++'

say "lerobot の venv"
cands=()
[ -n "${LEROBOT_VENV:-}" ] && cands+=("$LEROBOT_VENV")
cands+=("$HOME/lerobot-venv" "$HOME/lerobot/.venv" "$HOME/.venv" "$HOME/venvs/lerobot" \
        "$HOME/miniforge3/envs/lerobot" "$HOME/miniconda3/envs/lerobot" "$HOME/anaconda3/envs/lerobot")
VENV=""
for c in "${cands[@]}"; do
  if [ -x "$c/bin/lerobot-record" ]; then
    echo "あり: ${c/#$HOME/$T}"; [ -z "$VENV" ] && VENV="$c"
  fi
done
if [ -z "$VENV" ]; then
  found=$(find "$HOME" -maxdepth 5 -path '*/bin/lerobot-record' 2>/dev/null | head -3)
  [ -n "$found" ] && echo "${found//$HOME/$T}" && VENV=$(dirname "$(dirname "$(echo "$found" | head -1)")")
fi
if [ -z "$VENV" ]; then echo "lerobot-record が見つかりません"; else
  echo "使う venv: ${VENV/#$HOME/$T}"
  "$VENV/bin/python" - <<'PY'
import importlib.metadata as m
for p in ("lerobot", "torch", "huggingface_hub", "feetech-servo-sdk", "rerun-sdk", "pynput", "datasets"):
    try: print(f"{p}: {m.version(p)}")
    except m.PackageNotFoundError: print(f"{p}: (未導入)")
try:
    import torch
    ok = torch.cuda.is_available()
    print("torch.cuda.is_available:", ok, "/", torch.cuda.get_device_name(0) if ok else "-")
except Exception as e:
    print("torch の確認に失敗:", type(e).__name__)
PY
fi

say "Hugging Face のログイン（ユーザー名だけ）"
if [ -n "$VENV" ] && [ -x "$VENV/bin/hf" ]; then "$VENV/bin/hf" auth whoami 2>&1 | head -2
elif [ -n "$VENV" ] && [ -x "$VENV/bin/huggingface-cli" ]; then "$VENV/bin/huggingface-cli" whoami 2>&1 | head -2
else echo "hf / huggingface-cli が見つかりません"; fi

say "シリアルポート（モーター）"
ls -l /dev/serial/by-id/ 2>/dev/null | sed 1d | awk '{print $9, $10, $11}' || true
ls /dev/ttyACM* 2>/dev/null || echo "/dev/ttyACM* なし（アームの USB が挿さっていない？）"
id -nG | tr ' ' '\n' | grep -xE 'dialout|video' | sed 's/^/グループ: /'

say "カメラ"
ls /dev/v4l/by-id/ 2>/dev/null || echo "/dev/v4l/by-id なし"
ls /dev/video* 2>/dev/null || echo "/dev/video* なし"

LR="${HF_LEROBOT_HOME:-${HF_HOME:-$HOME/.cache/huggingface}/lerobot}"
say "キャリブレーション（${LR/#$HOME/$T}/calibration）"
find "$LR/calibration" -name '*.json' 2>/dev/null | sed "s#$LR/calibration/##" || true
[ -d "$LR/calibration" ] || echo "キャリブレーションのフォルダがありません"

say "手元のデータセット（${LR/#$HOME/$T}）"
for info in "$LR"/*/*/meta/info.json; do
  [ -f "$info" ] || continue
  d=$(dirname "$(dirname "$info")")
  python3 - "$d" <<'PY'
import json, sys, pathlib
d = pathlib.Path(sys.argv[1]); i = json.loads((d / "meta/info.json").read_text())
cams = [k for k, v in i.get("features", {}).items() if v.get("dtype") in ("video", "image")]
tasks = []
tj = d / "meta/tasks.jsonl"
if tj.exists():
    tasks = [json.loads(l).get("task") for l in tj.read_text().splitlines() if l.strip()]
else:
    try:
        import pyarrow.parquet as pq
        t = pq.read_table(d / "meta/tasks.parquet").to_pandas()
        tasks = list(t.index) if "task" not in t.columns else list(t["task"])
    except Exception:
        tasks = ["(tasks.parquet を読めず)"]
print(f"{d.parent.name}/{d.name}: 本数 {i.get('total_episodes')} / フレーム {i.get('total_frames')} / "
      f"fps {i.get('fps')} / 形式 {i.get('codebase_version')} / カメラ {cams} / タスク {tasks}")
PY
done

if [ -n "$VENV" ] && [ "${SKIP_CAMERAS:-0}" != 1 ]; then
  say "lerobot-find-cameras opencv（カメラを開くだけ）"
  timeout 60 "$VENV/bin/lerobot-find-cameras" opencv 2>&1 | grep -vE '^\s*$' | tail -40
fi
