# LeRobot v0.4.4 の手順書（SO-101・カメラ 1 台）

- 対象：[huggingface/lerobot](https://github.com/huggingface/lerobot) のタグ `v0.4.4`（commit `8fff0fde7c79f23a93d845d1a50e985de01f8b8a`）
- 引数の根拠は「ファイル:行」で示します。パスは、リポジトリの `src/lerobot/` からの相対です（`pyproject.toml` と `docs/` はリポジトリの直下から）。
- **この手順書のコマンドは、どれもまだ実機で実行していません**（書いた作業用 PC には SO-101 がつながっていません）。コードを読んで書いたもので、実機で確かめたら、この注記を直します。
- `${HF_USER}` は Hugging Face のユーザー名、ポートやカメラの番号は、実機で調べた値に置き換えます。
- **2026-10-28 追記（実機では未実行。7 月の記録と lerobot のソースを読んで直した点）**
  - キャリブレーションの id は `white`（フォロワー）・`black`（リーダー）にしました。7 月に退避したキャリブレーションのファイルが `so_follower/white.json`・`so_leader/black.json` で、id はファイル名と一致させる必要があるためです（lerobot は `<id>.json` を読む）。
  - 7 月に実機の PC へ入れた lerobot は **0.6.1** の記録です（0.4.4 ではない）。0.6.x で変わる点は「7. lerobot 0.6.x との違い」にまとめました。
  - データセットと方策の名前を、今回の本番の名前（`so101-pickplace-v1`、`act_so101_pickplace_v1`）にしました。
  - 録画と学習は、版の違いを吸収するスクリプト `record/record_so101.sh`・`train/train_act_local.sh` から始められます。事前の確認は `scripts/preflight.sh`、録画の検査は `scripts/inspect_dataset.py`、学習の完了予定は `scripts/train_eta.py` です。どれも実機ではまだ実行しておらず、偽のコマンドと作ったデータでだけ動作を確かめています。

## 0. 準備（ポート・カメラ・キャリブレーション）
| コマンド | 用途 | 根拠 |
|---|---|---|
| `lerobot-find-port` | リーダーとフォロワーのシリアルポートを調べる | `pyproject.toml:201` |
| `lerobot-find-cameras opencv` | カメラの番号を調べる | `pyproject.toml:200` |
| `lerobot-calibrate --robot.type=so101_follower --robot.port=... --robot.id=white` | フォロワーのキャリブレーション | `pyproject.toml:199`、`robots/so_follower/config_so_follower.py:46`（`so101_follower`） |
| `lerobot-calibrate --teleop.type=so101_leader --teleop.port=... --teleop.id=black` | リーダーのキャリブレーション | `teleoperators/so_leader/config_so_leader.py:34`（`so101_leader`） |

- `--robot.id`・`--teleop.id` は、キャリブレーションのファイルを見分ける名前です（`robots/config.py:25`、`teleoperators/config.py:25`）。**録画と推論でも同じ id を使います。** 実機の PC には、7 月に作った `white.json`・`black.json` があります（退避先は private の Hub データセット）。保存先は `~/.cache/huggingface/lerobot/calibration/robots/so_follower/` と `…/teleoperators/so_leader/` です。

## 1. 録画（リーダーで操作し、言語のタスク文字列つきでエピソードを録る）
```bash
lerobot-record \
  --robot.type=so101_follower \
  --robot.port=/dev/ttyACM1 \
  --robot.id=white \
  --robot.cameras="{front: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30}}" \
  --teleop.type=so101_leader \
  --teleop.port=/dev/ttyACM0 \
  --teleop.id=black \
  --dataset.repo_id=${HF_USER}/so101-pickplace-v1 \
  --dataset.single_task="Pick up the yellow earplug and put it into the blue tape core." \
  --dataset.num_episodes=50 \
  --dataset.episode_time_s=30 \
  --dataset.reset_time_s=15 \
  --dataset.fps=30 \
  --dataset.private=true \
  --display_data=true
```
| 引数 | 意味 | 既定値 | 根拠 |
|---|---|---|---|
| `--robot.type=so101_follower` | フォロワー（白） | — | `robots/so_follower/config_so_follower.py:46` |
| `--robot.port` | フォロワーのポート | 必須 | `robots/so_follower/config_so_follower.py:30` |
| `--robot.cameras` | カメラの辞書（名前 → 設定） | 空 | `robots/so_follower/config_so_follower.py:40`。`type: opencv` は `cameras/opencv/configuration_opencv.py:23`、`index_or_path` は同 `:61`、`fps`・`width`・`height` は `cameras/configs.py:61-63` |
| `--teleop.type=so101_leader` | リーダー（黒） | — | `teleoperators/so_leader/config_so_leader.py:34`、ポートは同 `:28` |
| `--dataset.repo_id` | データセットの名前（`ユーザー名/名前`） | 必須 | `scripts/lerobot_record.py:155` |
| `--dataset.single_task` | **言語のタスク文字列**。全エピソードに付く | 必須（無いとエラー） | `scripts/lerobot_record.py:157`、エラーは同 `:204-206` |
| `--dataset.num_episodes` | 録る本数 | 50 | `scripts/lerobot_record.py:167` |
| `--dataset.episode_time_s` | 1 エピソードの長さ（秒） | 60 | `scripts/lerobot_record.py:163` |
| `--dataset.reset_time_s` | エピソードの間のリセットの時間（秒） | 60 | `scripts/lerobot_record.py:165` |
| `--dataset.fps` | 記録の fps | 30 | `scripts/lerobot_record.py:161` |
| `--dataset.push_to_hub` | 録画の後に Hub へ上げる | true | `scripts/lerobot_record.py:171` |
| `--dataset.private` | Hub で private にする | false | `scripts/lerobot_record.py:173` |
| `--dataset.root` | 手元の保存先。未指定なら `$HF_LEROBOT_HOME/repo_id` | None | `scripts/lerobot_record.py:159`、`utils/constants.py:67` |
| `--display_data` | 画面にカメラと値を表示する | false | `scripts/lerobot_record.py:218` |
| `--resume` | 途中まで録ったデータセットに足して録る。**このときの `--dataset.num_episodes` は「足す本数」**で、合計の本数ではない（23 本で止まったら 27 を指定） | false | `scripts/lerobot_record.py:228`、本数の数え方は同 `:531-532` |

**早期終了のキー操作**（`utils/control_utils.py:149-161`）
| キー | 動作 |
|---|---|
| →（右矢印） | 今のエピソード（またはリセットの時間）を早めに終えて次へ |
| ←（左矢印） | 今のエピソードを捨てて録り直す |
| Esc | 録画を止める（それまでの分は保存） |

- 画面のない環境ではキー操作が使えません（`utils/control_utils.py:139-144`）。
- 時間と本数の値（30 秒・15 秒・50 本）は、この手順書の初期案です。タスクの長さを実測して決め直します。

## 2. ACT の学習
```bash
lerobot-train \
  --dataset.repo_id=${HF_USER}/so101-pickplace-v1 \
  --policy.type=act \
  --policy.device=cuda \
  --output_dir=outputs/train/act_so101_pickplace_v1 \
  --job_name=act_so101_pickplace_v1 \
  --steps=100000 \
  --batch_size=8 \
  --save_freq=5000 \
  --policy.push_to_hub=true \
  --policy.repo_id=${HF_USER}/act_so101_pickplace_v1 \
  --policy.private=true \
  --wandb.enable=false
```
| 引数 | 意味 | 既定値 | 根拠 |
|---|---|---|---|
| `--policy.type=act` | ACT。カメラ・状態・行動の数はデータセットから自動で決まる | — | `policies/factory.py:457-471`、公式の説明 `docs/source/il_robots.mdx:467` |
| `--policy.device` | `cuda`・`cpu`・`mps` | None | `configs/policies.py:62` |
| `--output_dir` | 出力先。**既にあると、`--resume=true` でない限りエラー** | `outputs/train/日付/時刻_job名` | `configs/train.py:43`、エラーは同 `:119-123`、既定は同 `:123-126` |
| `--steps` | 学習の step 数 | 100,000 | `configs/train.py:56` |
| `--batch_size` | バッチの大きさ | 8 | `configs/train.py:55` |
| `--policy.push_to_hub` | 学習の最後に Hub へ上げる | **true** | `configs/policies.py:70`。true なのに `--policy.repo_id` が無いとエラー（`configs/train.py:138-141`） |
| `--policy.repo_id` | 上げる先の model リポジトリ | None | `configs/policies.py:71` |
| `--policy.private` | private にする | None | `configs/policies.py:74` |
| `--wandb.enable` | W&B を使う | **false** | `configs/default.py:42`。使う場合も `--wandb.mode=offline` にする（同 `:49`） |

- ACT の主な既定値：`chunk_size=100`、`n_action_steps=100`、`vision_backbone=resnet18`、`optimizer_lr=1e-5`（`policies/act/configuration_act.py:86-87, 99, 127`）。
- Hub へ上げるのは学習の最後だけです（`scripts/lerobot_train.py:531-538`）。途中の分は、下の 5 のチェックポイントで守ります。

## 3. SmolVLA の学習（`lerobot/smolvla_base` からの微調整）
**追加の依存**：`pip install "lerobot[smolvla]==0.4.4"`。中身は `transformers`（`lerobot[transformers-dep]`）・`num2words>=0.5.14,<0.6.0`・`accelerate>=1.7.0,<2.0.0`・`safetensors>=0.4.3,<1.0.0` です（`pyproject.toml:139`）。

```bash
lerobot-train \
  --policy.path=lerobot/smolvla_base \
  --dataset.repo_id=${HF_USER}/so101-pickplace-v1 \
  --rename_map='{"observation.images.front": "observation.images.camera1"}' \
  --policy.device=cuda \
  --output_dir=outputs/train/smolvla_so101_pickplace_v1 \
  --job_name=smolvla_so101_pickplace_v1 \
  --steps=20000 \
  --batch_size=64 \
  --save_freq=2000 \
  --policy.push_to_hub=true \
  --policy.repo_id=${HF_USER}/smolvla_so101_pickplace_v1 \
  --policy.private=true \
  --wandb.enable=false
```
| 引数 | 意味 | 根拠 |
|---|---|---|
| `--policy.path=lerobot/smolvla_base` | 学習済みの SmolVLA から始める | `configs/train.py:82-86`、公式の例 `docs/source/smolvla.mdx:57-65`（steps 20000、batch 64） |
| `--rename_map` | **データのカメラ名を、smolvla_base の名前に合わせる** | `configs/train.py:78`、`scripts/lerobot_train.py:236-240` |

**`--rename_map` が要る理由**（コードを読んでの推測。実行はしていません）
- `lerobot/smolvla_base` の `config.json` の `input_features` は、`observation.state` と `observation.images.camera1`〜`camera3` です（Hub の `config.json` を 2026-10-09 に取得）。
- `--policy.path` から作ると、config の `input_features` は空でないので、データのカメラ名（ここでは `front`）には置き換わりません（`policies/factory.py:469-471`）。
- SmolVLA は、`image_features` のうち 1 つもバッチに無いとエラーで止まります（`policies/smolvla/modeling_smolvla.py:409-415`）。足りないカメラ（camera2・camera3）は、あるものだけで動きます（同 `:409-410`）。
- そのため、`front` を `camera1` に名前を付け替えます。

- SmolVLA の主な既定値：`chunk_size=50`・`n_action_steps=50`（`policies/smolvla/configuration_smolvla.py:32-33`）、`optimizer_lr=1e-4`（同 `:77`）、視覚のエンコーダーを固定し、行動の部分だけを学習（同 `:72-73`）。

## 4. 学習済みの方策で実機を動かす（推論）と、その録画
推論も `lerobot-record` で行います。`--policy.path` を付けると、リーダーの代わりに方策がフォロワーを動かします（`scripts/lerobot_record.py:216, 232-238, 356-369`）。

```bash
lerobot-record \
  --robot.type=so101_follower \
  --robot.port=/dev/ttyACM1 \
  --robot.id=white \
  --robot.cameras="{front: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30}}" \
  --dataset.repo_id=${HF_USER}/eval_so101-pickplace-v1_act \
  --dataset.single_task="Pick up the yellow earplug and put it into the blue tape core." \
  --dataset.num_episodes=10 \
  --dataset.episode_time_s=30 \
  --dataset.reset_time_s=15 \
  --dataset.private=true \
  --policy.path=${HF_USER}/act_so101_pickplace_v1
```
- **データセット名は `eval_` で始める**：方策を付けたのに `eval_` で始まらないと、エラーになります（逆も同じ。`utils/control_utils.py:189-200`）。
- **タスク文字列は、学習のときと同じにします**（SmolVLA は言語の条件で動くため）。
- **SmolVLA のとき**は、`--policy.path=${HF_USER}/smolvla_so101_pickplace_v1` にし、`--dataset.rename_map='{"observation.images.front": "observation.images.camera1"}'` を足します（`scripts/lerobot_record.py:202, 512-515`）。
- **安全のため**、最初は `--robot.max_relative_target` で 1 回の動きの大きさを制限することを検討します（`robots/so_follower/config_so_follower.py:34-37`。値は実機で決めます）。
- リーダーを一緒に付けると（`--teleop.*`）、エピソードの間のリセットを手で行えます（`scripts/lerobot_record.py:34-37` のコメント）。

**様子の録画（提出用の動画）**
- `lerobot-record` は、カメラの映像を評価のデータセット（`eval_…`）の動画として保存します（`--dataset.video` 既定 true、`scripts/lerobot_record.py:169`）。保存先は `$HF_LEROBOT_HOME/${HF_USER}/eval_…/videos/`（`utils/constants.py:67`）。
- 提出の動画（1〜3 分、倍速は 2 倍以内で、倍速なら明記）は、ロボット全体が見えるように、別のカメラ（スマートフォンなど）でも撮ることを勧めます。人や部屋が映らないように撮ります。

## 5. チェックポイントの保存間隔と再開
- **保存間隔**：`--save_freq`（既定 20,000 step）。`--save_checkpoint`（既定 true）（`configs/train.py:60-62`）。`step % save_freq == 0` と最後の step で保存します（`scripts/lerobot_train.py:431, 453-467`）。
- **保存先の形**：`<output_dir>/checkpoints/<step>/pretrained_model/` と `.../training_state/`。最新の分を指す **`checkpoints/last` はシンボリックリンク**です（`utils/constants.py:46-49`、`utils/train_utils.py:40-44, 57-62`）。
  - Google Drive はシンボリックリンクを保存できない見込みです（推測）。Colab では、`/content` で学習し、Drive へは実体の step ディレクトリだけを写します（`train/colab_train.ipynb` で対応）。
- **再開**：
  ```bash
  lerobot-train \
    --config_path=outputs/train/act_so101_pickplace_v1/checkpoints/last/pretrained_model/train_config.json \
    --resume=true
  ```
  - `--resume=true` のときは `--config_path` が必須で、手元のパスでなければなりません（Hub からの再開はできません。`configs/train.py:89-106`）。公式の例は `docs/source/il_robots.mdx:476-478`。
  - optimizer と scheduler と step 数は、`training_state` から戻ります（`scripts/lerobot_train.py:318-319`）。

## 6. カメラを 2 台（正面＋手首）に増やすとき（後の発展用。いまは書くだけ）
- **録画**：`--robot.cameras` に 2 つ目を足します。例：`"{front: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30}, wrist: {type: opencv, index_or_path: 2, width: 640, height: 480, fps: 30}}"`（`robots/so_follower/config_so_follower.py:40`）。
- **データセット**：カメラの数が変わると、データセットの項目（features）が変わります。1 台で録ったデータセットに、2 台の録画を足すことはできない見込みです（推測）。**新しいデータセット名で録り直します**。
- **ACT**：カメラの数は、データセットから自動で決まります（`policies/factory.py:457-471`）。
- **SmolVLA**：`--rename_map` に 2 つ目を足します。例：`'{"observation.images.front": "observation.images.camera1", "observation.images.wrist": "observation.images.camera2"}'`。推論の `--dataset.rename_map` も同じにします。
- **推論**：`--robot.cameras` の名前と台数を、学習のデータと同じにします。
- **USB の帯域**：2 台を同じ USB のハブにつなぐと、fps が落ちることがあります（推測）。`lerobot-find-cameras` と録画の画面で fps を確かめます。

## 7. lerobot 0.6.x との違い（実機の PC が 0.6.x のとき。ソースを読んだだけで、実行はしていません）
- 対象：タグ `v0.6.1`（commit `7e241bd630a3719a56157a497ce5d08f244784f1`）。パスは `src/lerobot/` からの相対です。
- 版の確かめ方：`python -c 'import importlib.metadata as m; print(m.version("lerobot"))'`（`scripts/preflight.sh` も表示します）。

| 点 | 0.4.4 | 0.6.x | 根拠（0.6.1） |
|---|---|---|---|
| データセット名 | `--dataset.repo_id` のまま | **末尾に日時（`_20261027_213000` など）が付く**。付けないなら `--dataset.no_stamp=true` | `configs/dataset.py:76-89`、`scripts/lerobot_record.py:438` |
| `--dataset.no_stamp` | **無い**（付けるとエラーの見込み） | ある | 同上 |
| `--resume` の本数 | 足す本数 | 足す本数（同じ） | `scripts/lerobot_record.py:470-471` |
| 推論（方策で動かす） | `lerobot-record --policy.path=…`、名前は `eval_` で始める | `lerobot-record` は `eval_` の名前を拒み、**`lerobot-rollout` を使う**（引数は未確認） | `scripts/lerobot_record.py:431-437`、`pyproject.toml:359` |
| 学習の再開 | `--config_path` は手元のパスだけ | 手元のパスか、Hub の model リポジトリ | `configs/train.py:88-90` |
| 途中のチェックポイントを Hub へ | 無い | `--save_checkpoint_to_hub=true`（`--policy.repo_id` が要る） | `configs/train.py:136, 291-292` |
| 録画に要る追加の依存 | — | `pip install 'lerobot[feetech,core_scripts]'`（7 月の実測で、`feetech` だけだと `lerobot-record` が `datasets` 不足で落ちた） | `pyproject.toml:132, 170` |
| データセットの形式 | v3.0 | v3.0（同じ） | `datasets/dataset_metadata.py:60`（0.4.4 は `datasets/lerobot_dataset.py:83`） |

- 形式の版が同じなので、0.6.x で録ったデータセットを Colab の 0.4.4（`train/colab_train.ipynb`）で学習できる見込みです（推測。未確認）。
- `record/record_so101.sh` は、`DatasetRecordConfig` に `no_stamp` があるときだけ `--dataset.no_stamp=true` を付けます。
