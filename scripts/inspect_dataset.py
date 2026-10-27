#!/usr/bin/env python3
"""録画したデータセット（LeRobot v3.0 形式）を検査する。アームは動かさない。

使い方:
  python scripts/inspect_dataset.py <repo_id またはデータセットのフォルダ> [--expect-episodes N] [--expect-task "..."]

調べること:
  1. meta/info.json の本数・フレーム数・fps・カメラ名
  2. タスク文字列（meta/tasks.parquet か meta/tasks.jsonl）
  3. エピソードごとの長さ（meta/episodes/*.parquet。pyarrow があるとき）
  4. 動画（videos/**.mp4）が最後まで復号できるか、カメラごとのフレーム数の合計が total_frames と合うか
問題があれば終了コード 1。
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def lerobot_home() -> Path:
    if os.environ.get("HF_LEROBOT_HOME"):
        return Path(os.environ["HF_LEROBOT_HOME"])
    hf_home = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface"))
    return hf_home / "lerobot"


def resolve(arg: str) -> Path:
    p = Path(arg).expanduser()
    if (p / "meta" / "info.json").exists():
        return p
    q = lerobot_home() / arg
    if (q / "meta" / "info.json").exists():
        return q
    sys.exit(f"データセットが見つかりません: {arg}（{q} にも meta/info.json がありません）")


def read_tasks(d: Path) -> list[str]:
    tj = d / "meta" / "tasks.jsonl"
    if tj.exists():
        return [json.loads(line)["task"] for line in tj.read_text().splitlines() if line.strip()]
    tp = d / "meta" / "tasks.parquet"
    if tp.exists():
        import pyarrow.parquet as pq

        t = pq.read_table(tp)
        if "task" in t.column_names:
            return [str(x) for x in t.column("task").to_pylist()]
        # v3.0 はタスク文字列を index（__index_level_0__ など）に持つ
        for name in t.column_names:
            if name.startswith("__index_level") or name == "index":
                return [str(x) for x in t.column(name).to_pylist()]
        return [str(t.schema)]
    return []


def episode_lengths(d: Path) -> list[int]:
    files = sorted((d / "meta" / "episodes").rglob("*.parquet"))
    if not files:
        return []
    import pyarrow.parquet as pq

    lengths = []
    for f in files:
        t = pq.read_table(f, columns=["length"])
        lengths += [int(x) for x in t.column("length").to_pylist()]
    return lengths


def video_frames(path: Path) -> tuple[int | None, float | None, str]:
    """(フレーム数, 長さ秒, エラー文)。ffprobe があれば全フレームを数え、無ければ PyAV で復号する。"""
    if shutil.which("ffprobe"):
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
             "-show_entries", "stream=nb_read_frames:format=duration", "-of", "json", str(path)],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            return None, None, r.stderr.strip()[:200]
        j = json.loads(r.stdout)
        n = j.get("streams", [{}])[0].get("nb_read_frames")
        dur = j.get("format", {}).get("duration")
        return (int(n) if n else None), (float(dur) if dur else None), ""
    try:
        import av

        with av.open(str(path)) as c:
            n = sum(1 for _ in c.decode(video=0))
            dur = float(c.duration / 1e6) if c.duration else None
        return n, dur, ""
    except Exception as e:  # 開けない動画はそのまま報告する
        return None, None, f"{type(e).__name__}: {e}"[:200]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--expect-episodes", type=int)
    ap.add_argument("--expect-task")
    a = ap.parse_args()

    d = resolve(a.dataset)
    info = json.loads((d / "meta" / "info.json").read_text())
    problems = []
    fps = info.get("fps")
    total_eps, total_frames = info.get("total_episodes"), info.get("total_frames")
    cams = [k for k, v in info.get("features", {}).items() if v.get("dtype") == "video"]
    print(f"データセット: {d.parent.name}/{d.name}  形式 {info.get('codebase_version')}  robot {info.get('robot_type')}")
    print(f"本数 {total_eps} / フレーム {total_frames} / fps {fps} / カメラ {cams}")

    tasks = read_tasks(d)
    print(f"タスク文字列: {tasks}")
    if a.expect_task is not None and tasks != [a.expect_task]:
        problems.append(f"タスク文字列が期待と違う: {tasks}")
    if a.expect_episodes is not None and total_eps != a.expect_episodes:
        problems.append(f"本数が期待（{a.expect_episodes}）と違う: {total_eps}")

    try:
        lengths = episode_lengths(d)
    except ImportError:
        lengths = []
        print("（pyarrow が無いので、エピソードごとの長さは省略）")
    if lengths:
        secs = [n / fps for n in lengths] if fps else []
        print(f"エピソードの長さ（フレーム）: {lengths}")
        if secs:
            print(f"  秒: 最短 {min(secs):.1f} / 平均 {sum(secs) / len(secs):.1f} / 最長 {max(secs):.1f}")
        if sum(lengths) != total_frames:
            problems.append(f"エピソードの長さの合計 {sum(lengths)} が total_frames {total_frames} と違う")

    for cam in cams:
        files = sorted((d / "videos").glob(f"{cam}/**/*.mp4")) or sorted((d / "videos").rglob(f"*{cam}*/*.mp4"))
        if not files:
            problems.append(f"{cam}: 動画がありません")
            continue
        n_sum = 0
        for f in files:
            n, dur, err = video_frames(f)
            rel = f.relative_to(d)
            if err or n is None:
                problems.append(f"{rel}: 開けません（{err}）")
                continue
            n_sum += n
            print(f"  {rel}: {n} フレーム / {dur:.1f} 秒" if dur else f"  {rel}: {n} フレーム")
        if total_frames is not None and n_sum != total_frames:
            problems.append(f"{cam}: 動画のフレーム数の合計 {n_sum} が total_frames {total_frames} と違う")
        else:
            print(f"{cam}: 動画のフレーム数の合計 {n_sum}（total_frames と一致）")

    if problems:
        print("\n問題:")
        for p in problems:
            print(" -", p)
        return 1
    print("\n問題なし")
    return 0


if __name__ == "__main__":
    sys.exit(main())
