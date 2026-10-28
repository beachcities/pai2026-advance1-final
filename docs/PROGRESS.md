# 進捗（2026-10-28 時点）

## 終わったこと
- 録画：`beachcities/so101-pickplace-v2`（50 本 = 置き場所 5 か所 × 10、20839 フレーム、Hub に private）
- 学習：ACT 100K step（約 4 時間、ロス 0.038）→ 方策 `beachcities/act_so101_pickplace_v2`（Hub に private）
- 録画のデータでの答え合わせ（`scripts/offline_eval.py`）：方策と記録の差は関節ごとの平均で 0.8〜2.4°
- 実機推論：8/15（53%）。場所 1・2 は 3/3、場所 3 は 0/3、場所 4・5 は 1/3
- レポートの原稿：`docs/report/report.md`（1〜10 章、YouTube のリンクまで）
- 動画：https://youtu.be/9_KTuG4R2Bg（等速、1 分 47 秒）

## 残り（Windows で行う）
1. 次のリンクを開き、右上の ⬇ で PDF をダウンロードする
   https://github.com/beachcities/pai2026-advance1-final/blob/main/docs/report/説明資料_PAI最終課題_Beachcities.pdf
2. omnicampus の提出ページで、その PDF を提出する

（アカウント名の記入・見直し・PDF 作成は Ubuntu で済み。個人情報の検査も 0 件）

## メモ
- 録画のログ・場所の CSV・動画のファイルは Ubuntu の PC の `outputs/` にあり、git には入れていない
