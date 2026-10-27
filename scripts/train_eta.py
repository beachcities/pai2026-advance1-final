#!/usr/bin/env python3
"""lerobot-train のログから、1 step あたりの時間・ロス・完了予定を出す。

使い方: python scripts/train_eta.py <ログ> [--total-steps 100000] [--log-freq 200]
ログの 1 行（lerobot の既定の書式）:
  INFO 2026-10-27 23:13:11 ot_train.py:420 step:200 smpl:2K ep:5 epch:0.13 loss:4.123 ... updt_s:0.110 data_s:0.003
step は 1000 以上で "2K" のように丸められるので、最初の行の step と行の数と log_freq から数える。
"""

import argparse
import re
import sys
from datetime import datetime, timedelta, timezone

LINE = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*?\bstep:(\S+) .*?\bloss:([0-9.]+)(?:.*?\bupdt_s:([0-9.]+))?(?:.*?\bdata_s:([0-9.]+))?")
JST = timezone(timedelta(hours=9))


def parse_step(tok: str) -> float:
    mult = {"K": 1e3, "M": 1e6}.get(tok[-1], 1)
    return float(tok[:-1] if mult != 1 else tok) * mult


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    ap.add_argument("--total-steps", type=int, default=100_000)
    ap.add_argument("--log-freq", type=int, default=200)
    ap.add_argument("--tz-offset-hours", type=float, default=None,
                    help="ログの時刻の UTC からのずれ（既定: このマシンの時間帯）")
    a = ap.parse_args()

    rows = []
    for line in open(a.log, encoding="utf-8", errors="replace"):
        m = LINE.search(line)
        if m:
            rows.append(m.groups())
    if len(rows) < 2:
        print(f"学習の行が {len(rows)} 行しかありません（log_freq={a.log_freq} step ごとに 1 行）。少し待ってから再実行してください")
        return 1

    tz = timezone(timedelta(hours=a.tz_offset_hours)) if a.tz_offset_hours is not None else datetime.now().astimezone().tzinfo
    t = [datetime.strptime(r[0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=tz) for r in rows]
    first_step = parse_step(rows[0][1])
    if first_step >= 1000:  # 再開のときは丸められている
        print(f"注意: 最初の行の step が {rows[0][1]} と丸められているので、step は ±500 程度ずれます")
    steps = [first_step + i * a.log_freq for i in range(len(rows))]
    sec_per_step = (t[-1] - t[0]).total_seconds() / (steps[-1] - steps[0])
    remaining = max(0, a.total_steps - steps[-1])
    eta = t[-1] + timedelta(seconds=remaining * sec_per_step)

    print(f"行数 {len(rows)} / step {int(steps[0])} → {int(steps[-1])}（{t[0]:%H:%M:%S} → {t[-1]:%H:%M:%S}）")
    print("ロス: " + ", ".join(f"{int(s)}:{r[2]}" for s, r in list(zip(steps, rows))[:10]) + (" …" if len(rows) > 10 else ""))
    print(f"最新のロス {rows[-1][2]}（step {int(steps[-1])}）")
    if rows[-1][3]:
        print(f"updt_s（直近の区間の最大）{rows[-1][3]} 秒 / data_s {rows[-1][4]} 秒")
    print(f"1 step あたり {sec_per_step:.3f} 秒（ログの時刻の差から計算。データの読み込みと保存を含む）")
    print(f"残り {int(remaining)} step → 約 {remaining * sec_per_step / 3600:.1f} 時間")
    print(f"完了予定 {eta.astimezone(timezone.utc):%Y-%m-%d %H:%M} UTC ／ {eta.astimezone(JST):%Y-%m-%d %H:%M} JST"
          "（チェックポイントの保存の時間で少し延びます）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
