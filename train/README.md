# train/

学習の置き場所です。`colab_train.ipynb`（Google Colab の A100 で、ACT と SmolVLA を学習する）を置きます。手順書の「2. ACT」「3. SmolVLA」「5. チェックポイント」も参照してください。

チェックポイントや学習の出力は、このリポジトリには入れません（`.gitignore`）。

## このマシンの GPU で ACT を学習する（2026-10-28 追記。実機ではまだ実行していません）
`train/train_act_local.sh` は、ターミナルを閉じても止まらない形（`setsid` ＋ `nohup`）で `lerobot-train` を起動し、ログを `outputs/logs/` に残します。

| コマンド | 何をするか |
|---|---|
| `bash train/train_act_local.sh start` | 新しく始める（`beachcities/so101-pickplace-v1`、100,000 step、バッチ 8、5,000 step ごとに保存、最後に `beachcities/act_so101_pickplace_v1` へ private で上げる、W&B なし） |
| `bash train/train_act_local.sh status` | 動いているか・最新のロス・1 step あたりの時間・完了予定（`scripts/train_eta.py`） |
| `bash train/train_act_local.sh resume` | `outputs/train/act_so101_pickplace_v1/checkpoints/last` から再開 |
| `bash train/train_act_local.sh stop` | 止める（チェックポイントは残る） |

- CUDA の GPU が使えないときは、何もせずに止まり、`colab_train.ipynb` を使うように表示します。
- ACT のチェックポイントは 1 個あたり数百 MB の見込みで、20 個できます。空きが 20 GB 未満なら注意を出します。
