#!/usr/bin/env python3
"""学習した方策を、録画したデータで答え合わせする（アームは動かさない）。

各エピソードの映像と関節の値を、推論のときと同じ順で 1 フレームずつ方策に見せ、
方策が出す動き（action）と、所有者が実際に動かした動き（記録の action）の差を関節ごとに出す。
ACT は 1 回の推論で先の 100 フレーム分をまとめて出し、それを順に使う（推論のときと同じ）。

注意: 答え合わせに使うエピソードは学習にも使っている（学習で見たデータ）。
「習ったことを再現できるか」の確認で、実機で動くかの代わりにはならない。

使い方:
  python scripts/offline_eval.py --policy outputs/train/act_so101_pickplace_v2/checkpoints/last/pretrained_model \
      --dataset beachcities/so101-pickplace-v2 --episodes 0 5 10 15 20 25 30 35 40 45 --plot outputs/offline_eval.png
"""
import argparse
import time

import numpy as np
import torch

from lerobot.datasets.lerobot_dataset import LeRobotDataset
from lerobot.policies.act.modeling_act import ACTPolicy
from lerobot.policies.factory import make_pre_post_processors

JOINTS = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]


def place_of(ep: int, per_place: int = 10, places: int = 5) -> int:
    return min(ep // per_place + 1, places)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", required=True)
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--episodes", type=int, nargs="+", required=True)
    ap.add_argument("--plot", default=None, help="1 本目のエピソードの、方策と記録の動きを重ねた図の保存先")
    args = ap.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    policy = ACTPolicy.from_pretrained(args.policy).to(device).eval()
    pre, post = make_pre_post_processors(
        policy.config, pretrained_path=args.policy, preprocessor_overrides={"device_processor": {"device": device.type}}
    )
    ds = LeRobotDataset(args.dataset)
    eps = ds.meta.episodes
    task = ds.meta.tasks.index[0]

    rows, events, plot_data = [], [], None
    t0 = time.time()
    for ep in args.episodes:
        start, end = int(eps["dataset_from_index"][ep]), int(eps["dataset_to_index"][ep])
        policy.reset()
        pred, true, state = [], [], []
        for i in range(start, end):
            item = ds[i]
            obs = {k: v.unsqueeze(0).to(device) for k, v in item.items()
                   if k.startswith("observation.") and isinstance(v, torch.Tensor)}
            obs["task"] = [task]
            obs["robot_type"] = ds.meta.robot_type
            with torch.inference_mode():
                a = post(policy.select_action(pre(obs)))
            pred.append(a.squeeze(0).cpu().numpy())
            true.append(item["action"].numpy())
            state.append(item["observation.state"].numpy())
        pred, true, state = map(np.stack, (pred, true, state))
        err = np.abs(pred - true).mean(0)
        still = np.abs(state[0] - true).mean(0)  # 比べる目安：「最初の姿勢のまま、まったく動かない」と答えた場合の差
        rows.append((ep, place_of(ep), len(true), err, still))
        events.append((ep, pred, true))
        if plot_data is None:
            plot_data = (ep, pred, true)

    print(f"方策: {args.policy}")
    print(f"答え合わせ {len(rows)} 本 / {sum(r[2] for r in rows)} フレーム / {time.time() - t0:.0f} 秒")
    print("関節ごとの平均の差（度。gripper は 0〜100 の開き具合）。かっこ内は「最初の姿勢のまま動かない」と答えた場合の差")
    print("回目 場所 フレーム  " + "  ".join(f"{j[:11]:>11}" for j in JOINTS))
    for ep, pl, n, err, still in rows:
        print(f"{ep + 1:4d} {pl:4d} {n:7d}  " + "  ".join(f"{e:5.1f}({s:4.1f})" for e, s in zip(err, still)))
    allerr = np.mean([r[3] for r in rows], axis=0)
    allstill = np.mean([r[4] for r in rows], axis=0)
    print("平均            " + "  ".join(f"{e:5.1f}({s:4.1f})" for e, s in zip(allerr, allstill)))
    for pl in sorted({r[1] for r in rows}):
        e = np.mean([r[3] for r in rows if r[1] == pl], axis=0)
        print(f"場所 {pl}：全関節の平均の差 {e.mean():.1f}（gripper {e[5]:.1f}）")

    print("\n大事な場面（方策 / 記録）：グリッパーの最小（閉じた）・最大（開いた）、手首の回転の最小（場所 4 は手先を返して約 0 度）")
    for ep, pred, true in events:
        print(f"{ep + 1:4d}回目 場所{place_of(ep)}  gripper 最小 {pred[:, 5].min():5.1f} / {true[:, 5].min():5.1f}"
              f"  最大 {pred[:, 5].max():5.1f} / {true[:, 5].max():5.1f}"
              f"  wrist_roll 最小 {pred[:, 4].min():6.1f} / {true[:, 4].min():6.1f}")

    if args.plot and plot_data is not None:
        try:
            import matplotlib
        except ImportError:
            print("matplotlib が無いので図は描きません")
            return
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        ep, pred, true = plot_data
        fig, axes = plt.subplots(len(JOINTS), 1, figsize=(8, 10), sharex=True)
        tt = np.arange(len(true)) / ds.fps
        for k, ax in enumerate(axes):
            ax.plot(tt, true[:, k], label="recorded", lw=1.5)
            ax.plot(tt, pred[:, k], label="policy", lw=1.0, ls="--")
            ax.set_ylabel(JOINTS[k], fontsize=8)
        axes[0].legend(loc="upper right", fontsize=8)
        axes[-1].set_xlabel("seconds")
        fig.suptitle(f"episode {ep + 1}: recorded action vs policy action (offline)")
        fig.tight_layout()
        fig.savefig(args.plot, dpi=100)
        print(f"図: {args.plot}")


if __name__ == "__main__":
    main()
