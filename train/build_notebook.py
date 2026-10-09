"""Builds train/colab_train.ipynb (run: python train/build_notebook.py). Edit this file, not the notebook."""

import json
from pathlib import Path

MD_TOP = """# SO-101 の方策を Google Colab（A100）で学習する（LeRobot v0.4.4）

Physical AI 応用編1（2026）最終課題の学習ノートブックです。

- 方策は **ACT** と **SmolVLA**（`lerobot/smolvla_base` から微調整）から、変数 `POLICY` で選びます。
- チェックポイントを一定の間隔で保存し、**Google Drive へ定期的に写し**、**途中から再開**できます（Colab が切れても、もう一度「すべて実行」すれば続きから学習します）。
- W&B は既定で使いません（使う場合も `offline`）。
- Hugging Face のトークンは、Colab の「シークレット」の `HF_TOKEN` から読みます。**このノートブックにトークンの値を書かないでください。**
- 学習済みの方策は、変数 `PUSH_TO_HUB` で、Hugging Face の **private** の model リポジトリへ上げられます。
- 引数の根拠は [docs/HOWTO_lerobot_v0.4.4.md](../docs/HOWTO_lerobot_v0.4.4.md) にあります。

## 最初に：スモークテスト（動作確認）
1. ランタイムを GPU（A100）にします。
2. 下の「設定」で `SMOKE_TEST = True` のまま「すべて実行」します。
   - 公開の SO-101 データセット [`lerobot/svla_so101_pickplace`](https://huggingface.co/datasets/lerobot/svla_so101_pickplace)（v3.0 形式、50 エピソード、カメラ 2 台。2026-10-09 に Hub で存在を確認）で、ACT を `SMOKE_STEPS`（既定 20）step だけ学習します。
   - Drive への退避と Hub への push はしません。
3. 最後のセルで、`checkpoints/` に step のディレクトリができていれば成功です。
4. 本番は `SMOKE_TEST = False` にし、`DATASET_REPO_ID`・`POLICY` などを設定して「すべて実行」します。
"""

SETTINGS = '''# === 設定 ===
import os

SMOKE_TEST = True                     # True: 公開データで ACT を数十 step だけ回す動作確認
SMOKE_STEPS = int(os.environ.get("SMOKE_STEPS", "20"))

POLICY = "act"                         # "act" または "smolvla"
DATASET_REPO_ID = "YOUR_HF_USER/so101-pickplace"   # private でも可（HF_TOKEN が要る）
# SmolVLA のときだけ使う：データのカメラ名を smolvla_base の名前（camera1〜3）に合わせる（手順書の 3）
SMOLVLA_RENAME_MAP = {"observation.images.front": "observation.images.camera1"}

STEPS = {"act": 100_000, "smolvla": 20_000}[POLICY]
BATCH_SIZE = {"act": 8, "smolvla": 64}[POLICY]
SAVE_FREQ = {"act": 5_000, "smolvla": 2_000}[POLICY]     # チェックポイントの保存間隔（step）
RUN_NAME = f"{POLICY}_so101_pickplace"

USE_DRIVE = True                       # チェックポイントを Google Drive へ写す・Drive から再開する
DRIVE_DIR = "/content/drive/MyDrive/pai2026-final/runs"
SYNC_MINUTES = 10                      # Drive へ写す間隔（分）
DRIVE_KEEP_LAST = 3                    # Drive に残すチェックポイントの数（古いものから消す）

PUSH_TO_HUB = False                    # True: 学習の最後に private の model リポジトリへ上げる
MODEL_REPO_ID = f"YOUR_HF_USER/{POLICY}_so101_pickplace"

WANDB = "disabled"                     # "disabled" または "offline"（online は使わない）

if SMOKE_TEST:
    POLICY, DATASET_REPO_ID = "act", "lerobot/svla_so101_pickplace"
    STEPS, BATCH_SIZE, SAVE_FREQ = SMOKE_STEPS, 2, max(1, SMOKE_STEPS // 2)
    RUN_NAME, USE_DRIVE, PUSH_TO_HUB, WANDB = "smoke_act", False, False, "disabled"

assert POLICY in ("act", "smolvla"), POLICY
assert WANDB in ("disabled", "offline"), "W&B は disabled か offline だけにする"
print(dict(POLICY=POLICY, DATASET_REPO_ID=DATASET_REPO_ID, STEPS=STEPS, BATCH_SIZE=BATCH_SIZE,
           SAVE_FREQ=SAVE_FREQ, RUN_NAME=RUN_NAME, USE_DRIVE=USE_DRIVE, PUSH_TO_HUB=PUSH_TO_HUB, WANDB=WANDB))
'''

INSTALL = '''# === LeRobot v0.4.4 を入れる（SmolVLA は追加の依存 lerobot[smolvla]） ===
import subprocess, sys

if not os.environ.get("SKIP_INSTALL"):
    extra = "[smolvla]" if POLICY == "smolvla" else ""
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", f"lerobot{extra}==0.4.4"], check=True)
print(subprocess.run(["lerobot-train", "--help"], capture_output=True, text=True).returncode == 0
      and "lerobot-train: ok" or "lerobot-train が見つかりません")
'''

SECRETS = '''# === Hugging Face のトークン（Colab のシークレット HF_TOKEN から。値は表示しない） ===
token = None
try:
    from google.colab import userdata
    token = userdata.get("HF_TOKEN")
except Exception:
    token = os.environ.get("HF_TOKEN")
if token:
    os.environ["HF_TOKEN"] = token     # huggingface_hub と lerobot-train の子プロセスが読む
print("HF_TOKEN:", "設定済み" if token else "未設定（公開のデータセットだけ使えます）")
del token
'''

PATHS = '''# === 置き場所と、Drive からの再開 ===
import shutil
from pathlib import Path

WORK = Path("/content/outputs/train") if Path("/content").exists() else Path("outputs/train")
WORK = WORK / RUN_NAME
CKPT = WORK / "checkpoints"
DRUN = Path(DRIVE_DIR) / RUN_NAME

if USE_DRIVE:
    from google.colab import drive
    drive.mount("/content/drive")
    (DRUN / "checkpoints").mkdir(parents=True, exist_ok=True)


def step_dirs(root):
    """Finished step directories (names are digits; `last` is a symlink and is skipped)."""
    d = Path(root) / "checkpoints"
    if not d.is_dir():
        return []
    return sorted((p for p in d.iterdir() if p.is_dir() and not p.is_symlink() and p.name.isdigit()),
                  key=lambda p: int(p.name))


def point_last(step_dir):
    """checkpoints/last is a symlink in LeRobot (utils/train_utils.py:57-62); recreate it locally."""
    last = step_dir.parent / "last"
    if last.is_symlink() or last.exists():
        last.unlink()
    last.symlink_to(step_dir.name)


# Drive に保存があり、手元に無ければ、いちばん新しい step を手元へ戻して再開する
if USE_DRIVE and not step_dirs(WORK) and step_dirs(DRUN):
    newest = [p for p in step_dirs(DRUN) if (p / ".complete").exists()]
    if newest:
        src = newest[-1]
        dst = CKPT / src.name
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".complete"))
        point_last(dst)
        print("Drive から戻しました:", src)

RESUME = (CKPT / "last" / "pretrained_model" / "train_config.json").exists()
print("WORK:", WORK, "| 再開:", RESUME, "| 手元の step:", [p.name for p in step_dirs(WORK)])
'''

SYNC = '''# === Drive へ定期的に写す（学習と並行して動く） ===
import threading, time


def sync_to_drive():
    """Copy every finished step dir to Drive (Drive keeps no symlinks, so `last` is not copied)."""
    if not USE_DRIVE:
        return []
    last = CKPT / "last"
    if not last.is_symlink():
        return []
    done = int(os.readlink(last).rstrip("/").split("/")[-1])   # last は書き終えた step を指す
    copied = []
    for src in step_dirs(WORK):
        if int(src.name) > done:
            continue
        dst = DRUN / "checkpoints" / src.name
        if (dst / ".complete").exists():
            continue
        tmp = dst.with_name(dst.name + ".partial")
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.copytree(src, tmp)
        shutil.rmtree(dst, ignore_errors=True)
        tmp.rename(dst)
        (dst / ".complete").write_text(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        copied.append(src.name)
    olds = [p for p in step_dirs(DRUN) if (p / ".complete").exists()][:-DRIVE_KEEP_LAST]
    for p in olds:
        shutil.rmtree(p, ignore_errors=True)
    return copied


_stop = threading.Event()


def _loop():
    while not _stop.wait(SYNC_MINUTES * 60):
        try:
            got = sync_to_drive()
            if got:
                print("Drive へ写しました:", got, flush=True)
        except Exception as e:                       # 写せなくても学習は止めない
            print("Drive への写しで失敗:", type(e).__name__, e, flush=True)


if USE_DRIVE:
    threading.Thread(target=_loop, daemon=True).start()
    print(f"Drive へ {SYNC_MINUTES} 分ごとに写します:", DRUN)
'''

TRAIN = '''# === 学習（lerobot-train。途中で止まったら、このノートブックをもう一度「すべて実行」すると続きから） ===
import json, subprocess

try:
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
except ImportError:
    device = "cpu"

if RESUME:
    args = ["lerobot-train",
            f"--config_path={CKPT / 'last' / 'pretrained_model' / 'train_config.json'}",
            "--resume=true"]                  # 再開は手元のパスが必須（configs/train.py:89-106）
else:
    args = ["lerobot-train",
            f"--dataset.repo_id={DATASET_REPO_ID}",
            f"--output_dir={WORK}",
            f"--job_name={RUN_NAME}",
            f"--steps={STEPS}",
            f"--batch_size={BATCH_SIZE}",
            f"--save_freq={SAVE_FREQ}",
            f"--policy.device={device}",
            f"--policy.push_to_hub={str(PUSH_TO_HUB).lower()}",
            f"--wandb.enable={str(WANDB != 'disabled').lower()}"]
    if WANDB == "offline":
        args.append("--wandb.mode=offline")
    if PUSH_TO_HUB:
        args += [f"--policy.repo_id={MODEL_REPO_ID}", "--policy.private=true"]
    if POLICY == "act":
        args.append("--policy.type=act")
    else:
        args += ["--policy.path=lerobot/smolvla_base", "--rename_map=" + json.dumps(SMOLVLA_RENAME_MAP)]
    if SMOKE_TEST:
        args += ["--num_workers=0", "--log_freq=1"]

print("$", " ".join(args), flush=True)
t0 = time.time()
rc = subprocess.run(args).returncode
print(f"lerobot-train の終了コード {rc}、{time.time() - t0:.0f} 秒")
'''

FINISH = '''# === 終わったら：最後の写しと、確かめ ===
_stop.set()
if USE_DRIVE:
    print("最後の写し:", sync_to_drive())
print("手元の checkpoints:", [p.name for p in step_dirs(WORK)])
if USE_DRIVE:
    print("Drive の checkpoints:", [p.name for p in step_dirs(DRUN) if (p / ".complete").exists()])
last_model = CKPT / "last" / "pretrained_model"
print("最新の方策:", last_model, "| ある:", last_model.exists())
assert rc == 0, "lerobot-train が失敗しました。上のログを見てください"
'''

PUSH_LATER = '''# === （任意）学習の後から private の model リポジトリへ上げる ===
# PUSH_TO_HUB=False で学習した方策を、あとから上げたいときに使います。
PUSH_LATER = False
if PUSH_LATER:
    from huggingface_hub import HfApi
    api = HfApi()
    api.create_repo(MODEL_REPO_ID, repo_type="model", private=True, exist_ok=True)
    api.upload_folder(folder_path=str(CKPT / "last" / "pretrained_model"), repo_id=MODEL_REPO_ID, repo_type="model")
    print("上げました:", MODEL_REPO_ID, "(private)")
'''


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text.splitlines(keepends=True)}


def code(text):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
            "source": text.splitlines(keepends=True)}


CODE_CELLS = [SETTINGS, INSTALL, SECRETS, PATHS, SYNC, TRAIN, FINISH, PUSH_LATER]

nb = {
    "nbformat": 4,
    "nbformat_minor": 5,
    "metadata": {
        "accelerator": "GPU",
        "colab": {"gpuType": "A100", "provenance": []},
        "kernelspec": {"display_name": "Python 3", "name": "python3"},
        "language_info": {"name": "python"},
    },
    "cells": [md(MD_TOP)] + [code(c) for c in CODE_CELLS],
}
for i, c in enumerate(nb["cells"]):
    c["id"] = f"cell-{i}"
out = Path(__file__).with_name("colab_train.ipynb")
out.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("wrote", out)
