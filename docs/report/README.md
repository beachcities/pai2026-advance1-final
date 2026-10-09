# docs/report/

レポートの原稿 [`report.md`](report.md) と、PDF にする手順です。

- 提出のファイル名：`説明資料_PAI最終課題_<omnicampusアカウント名>.pdf`
- PDF はこのリポジトリに入れません（`.gitignore` で `docs/report/*.pdf` を外しています）。提出の直前に手元で作ります。
- 書かないもの：氏名・所属・メールアドレス、人や部屋の写った画像、W&B のリンク。

## PDF にする手順

### A. pandoc ＋ LuaLaTeX（日本語は `ltjsarticle`）
```bash
# 準備（Ubuntu の例）
sudo apt install pandoc texlive-luatex texlive-lang-japanese

# PDF にする（docs/report/ で実行）
pandoc report.md -o "説明資料_PAI最終課題_<アカウント名>.pdf" \
  --pdf-engine=lualatex \
  -V documentclass=ltjsarticle \
  -V geometry:margin=20mm
```

### B. pandoc で HTML にして、ブラウザで PDF に保存（TeX を入れたくないとき）
```bash
pandoc report.md -s -o report.html --metadata title="最終課題レポート"
# report.html をブラウザで開き、印刷 → 「PDF に保存」
```

## 提出の前の確かめ
1. `python scripts/check_privacy.py`（リポジトリの直下で）で、個人情報が入っていないことを確かめる。
2. PDF を開いて、氏名・メールアドレス・人や部屋の写った画像がないことを、目で確かめる。
3. 画像を載せた場合は、元の画像の位置情報（EXIF）も CI で検査されます。
