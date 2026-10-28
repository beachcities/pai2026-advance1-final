# record/

録画（データ集め）の置き場所です。手順は [docs/HOWTO_lerobot_v0.4.4.md](../docs/HOWTO_lerobot_v0.4.4.md) の「1. 録画」にあります。

録画したデータセットそのものは Hugging Face Hub（private）に置き、このリポジトリには入れません（`.gitignore`）。

## 録画の始め方（2026-10-28 追記。実機ではまだ実行していません）
所有者が自分のターミナルで、リポジトリの直下から実行します（アームを動かすため）。どれも、実行する `lerobot-record` の全文を表示してから始めます。

| コマンド | 何をするか |
|---|---|
| `bash scripts/preflight.sh` | 事前の確認（OS・GPU・ディスク・venv と lerobot の版・HF のログイン・ポート・カメラ・キャリブレーション・手元のデータセット）。アームは動かさない |
| `bash record/record_so101.sh trial` | 試し録り：2 本・30 秒。名前は `…/so101-pickplace-v1-trial`、Hub には上げない |
| `python scripts/inspect_dataset.py beachcities/so101-pickplace-v1-trial --expect-episodes 2` | 試し録りの検査（本数・フレーム数・タスク文字列・動画が最後まで開けるか） |
| `bash record/record_so101.sh main` | 本番：50 本。最後に Hub へ private で上げる |
| `bash record/record_so101.sh resume` | 本番の続き。残りの本数を `meta/info.json` から計算して足す |
| `bash record/record_so101.sh eval` | 推論：学習した方策（既定 `outputs/train/act_so101_pickplace_v2/checkpoints/last/pretrained_model`、`POLICY_PATH` で変更）が白いアームを動かす。既定 15 本（場所ごとに 3 本）。置き直しの間は黒いアームで白いアームを開始姿勢に戻せる。`--robot.max_relative_target=40`。Hub には上げない |

- 既定値：フォロワー（白）`/dev/ttyACM1`、リーダー（黒）`/dev/ttyACM0`、id `white`・`black`、カメラ C920（`/dev/v4l/by-id/usb-046d_HD_Pro_Webcam_C920-video-index0`、640×480、30 fps。`/dev/video0` は内蔵カメラ）、エピソード 30 秒・リセット 30 秒。
- 録画の前に `bash scripts/camera_lock.sh lock` でカメラのピント・露出・ホワイトバランスを固定しておくと、録画のたびに同じ値を設定し直します。
- Wayland の画面では lerobot のキー操作（→ ← Esc）が効きません（2026-10-28 に確認）。時間で自動に進みます。1 本ごとに「場所 N の M 回目 どうぞ」を表示し（`scripts/record_guide.py`、場所は 1→`PLACES` と回す）、何本目がどの場所かを `outputs/places_<名前>.csv` に残します。途中で止めるときは、別の窓から `pkill -INT -f lerobot-record`（それまでの分は保存）。
- `DISPLAY_DATA=false` で rerun の窓を出しません。
- 環境変数で変えられます。例：`EPISODE_TIME_S=25 RESET_TIME_S=10 bash record/record_so101.sh main`、`FOLLOWER_PORT=/dev/serial/by-id/… LEADER_PORT=/dev/serial/by-id/…`、`LEROBOT_VENV=<venv>`。
- lerobot 0.6.x では、データセット名に日時が付かないように `--dataset.no_stamp=true` を自動で付けます（手順書の 7）。
- `DRY_RUN=1` を付けると、コマンドを表示するだけで録画しません。
