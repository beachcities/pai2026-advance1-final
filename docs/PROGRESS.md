# 進捗（2026-10-28 時点）

## 終わったこと
- 録画：`beachcities/so101-pickplace-v2`（50 本 = 置き場所 5 か所 × 10、20839 フレーム、Hub に private）
- 学習：ACT 100K step（約 4 時間、ロス 0.038）→ 方策 `beachcities/act_so101_pickplace_v2`（Hub に private）
- 録画のデータでの答え合わせ（`scripts/offline_eval.py`）：方策と記録の差は関節ごとの平均で 0.8〜2.4°
- 実機推論：8/15（53%）。場所 1・2 は 3/3、場所 3 は 0/3、場所 4・5 は 1/3
- レポートの原稿：`docs/report/report.md`（1〜10 章、YouTube のリンクまで）
- 動画：https://youtu.be/9_KTuG4R2Bg（等速、1 分 47 秒）

## 残り（Windows で行う）
1. ~~1 章に omnicampus のアカウント名を書く~~（済：Beachcities）
2. 見直す：人や部屋の写った画像、氏名・所属・メールアドレス、W&B のリンクが入っていないこと
3. PDF にする（手順は `docs/report/README.md`）。ファイル名は `説明資料_PAI最終課題_<omnicampusアカウント名>.pdf`
4. omnicampus で提出する

## メモ
- 録画のログ・場所の CSV・動画のファイルは Ubuntu の PC の `outputs/` にあり、git には入れていない
