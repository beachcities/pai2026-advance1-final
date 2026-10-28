#!/usr/bin/env python3
"""lerobot-record の出力を読み、エピソードごとに「場所 N の M 回目 どうぞ」を大きく表示する。

使い方: lerobot-record ... 2>&1 | python3 scripts/record_guide.py --places 5 --log outputs/record_places.csv
- lerobot の出力はそのまま流す。"Recording episode K"（K は 0 始まりの通し番号）と
  "Reset the environment" の行を見つけたら案内を出す。
- 場所は 1→2→…→places→1 と回す（途中で止めても場所ごとの本数が偏らない）。
- 何本目がどの場所だったかを CSV に追記する（失敗した回を後で外すため）。
"""
import argparse
import datetime
import re
import subprocess
import sys
from pathlib import Path

SOUND = "/usr/share/sounds/freedesktop/stereo/complete.oga"


def place_of(k: int, places: int) -> tuple[int, int]:
    return k % places + 1, k // places + 1


def banner(lines: list[str]) -> None:
    bar = "=" * 60
    print(f"\n{bar}", flush=True)
    for line in lines:
        print(f"  {line}", flush=True)
    print(f"{bar}\n", flush=True)


def chime() -> None:
    if Path(SOUND).exists():
        subprocess.Popen(["paplay", SOUND], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--places", type=int, default=5)
    ap.add_argument("--total", type=int, default=0, help="目標の本数（表示用）")
    ap.add_argument("--episode-s", default="30")
    ap.add_argument("--reset-s", default="30")
    ap.add_argument("--log", default="outputs/record_places.csv")
    args = ap.parse_args()

    log = Path(args.log)
    log.parent.mkdir(parents=True, exist_ok=True)
    if not log.exists():
        log.write_text("episode_index,place,round,started_at\n")
    rec = re.compile(r"Recording episode (\d+)")
    current = None
    for line in sys.stdin:
        sys.stdout.write(line)
        sys.stdout.flush()
        m = rec.search(line)
        if m:
            current = int(m.group(1))
            place, rnd = place_of(current, args.places)
            total = f"（通し {current + 1}" + (f" / {args.total}）" if args.total else "）")
            banner([f"▶ 録画中 {args.episode_s} 秒：場所 {place} の {rnd} 回目 どうぞ {total}",
                    "  つまむ → テープの中心へ入れる → 開始姿勢に戻って待つ"])
            chime()
            with log.open("a") as f:
                f.write(f"{current},{place},{rnd},{datetime.datetime.now().isoformat(timespec='seconds')}\n")
        elif "Reset the environment" in line and current is not None:
            place, rnd = place_of(current + 1, args.places)
            banner([f"■ 置き直し {args.reset_s} 秒（この間は保存されません）",
                    f"  次は 場所 {place} の {rnd} 回目：耳栓を 場所 {place} に置き、腕を開始姿勢へ"])
            chime()
        elif "Stop recording" in line:
            banner(["● 録画を終えました（保存中。ターミナルが戻るまで待ってください）"])


if __name__ == "__main__":
    main()
