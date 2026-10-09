# Physical AI 応用編1（2026）最終課題

SO-101 の実機で「録画 → 学習 → 実機推論」を一周させる課題のリポジトリです。

- タスク：蛍光イエローの耳栓をつまみ、青いテープの芯の中へ入れる（データセット名 `so101-pickplace`）
- 方策：ACT と SmolVLA を同じデータから学習し、実機でうまく動いた方を使う
- 学習の場所：Google Colab（A100）

## 構成

### ハードウェア
| 部品 | 内容 |
|---|---|
| アーム | SO-101（リーダー：黒、フォロワー：白） |
| カメラ | Logicool C920n 1 台（正面）。手首のカメラは後の発展で足す |
| 実機の PC | Ubuntu（デュアルブートの片側） |
| 学習 | Google Colab（A100） |

### ソフトウェア
| 部品 | 版 |
|---|---|
| [LeRobot](https://github.com/huggingface/lerobot) | v0.4.4 |
| 方策 | ACT（`lerobot/policies/act`）、SmolVLA（`lerobot/policies/smolvla`、`lerobot/smolvla_base` から微調整） |
| データと重みの置き場所 | Hugging Face Hub（private） |

### データの流れ
```
リーダーで操作 ──▶ lerobot-record ──▶ データセット（Hugging Face Hub）
                                          │
                                          ▼
                              Colab A100：train/colab_train.ipynb
                                          │
                                          ▼
                        学習済みの方策（Hugging Face Hub）
                                          │
                                          ▼
                 lerobot-record（方策で推論）──▶ フォロワーが動く・様子を録画
```

## 実行の手順
手順は [docs/HOWTO_lerobot_v0.4.4.md](docs/HOWTO_lerobot_v0.4.4.md) にまとめています。

| 段階 | 置き場所 |
|---|---|
| 録画 | [record/](record/)、手順書の「1. 録画」 |
| 学習 | [train/](train/)（`colab_train.ipynb`）、手順書の「2. ACT」「3. SmolVLA」 |
| 実機の推論と、その録画 | [infer/](infer/)、手順書の「4. 推論」 |
| レポート | [docs/report/](docs/report/) |

## 課題の要件と、このリポジトリで対応する場所
| 要件 | 対応する場所 |
|---|---|
| 動画（1〜3 分。倍速は 2 倍以内で、倍速なら明記。YouTube の URL を提出） | 撮り方は手順書の「4. 推論」。URL はレポートの「10 リンク」に書く |
| 使用したコード一式（public の GitHub リポジトリ） | このリポジトリ |
| レポート PDF（概要・目的・工夫した点・苦労した点） | [docs/report/report.md](docs/report/report.md) と、PDF にする手順 [docs/report/README.md](docs/report/README.md) |
| AI の使用（推論は必須、学習は加点） | 学習：`train/`、推論：`infer/` と手順書の「4. 推論」 |
| 成果物に氏名・所属・メールアドレスを載せない | CI（[.github/workflows/check.yml](.github/workflows/check.yml)）で、メールアドレス・ホームのパス・画像の位置情報を検査する |
| サンプルの丸写しでないこと、工夫点の明記 | レポートの「8 工夫した点・苦労した点」 |
| 公開リポジトリに LICENSE を置く | [LICENSE](LICENSE) |

日程：提出開始 2026-10-19、締切 2026-11-02 10:00。

## ライセンス
[Apache License 2.0](LICENSE)。LeRobot（Apache-2.0）を使っています。
