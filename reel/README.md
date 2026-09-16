# 体重記録リール

体重計の写真と体重記録グラフから、Instagram リール用の縦動画 (1080x1920 / 30fps / 約16.5秒) を生成します。

## 構成

| 秒 | シーン |
|---|---|
| 0–4 | 体重計の写真に「今朝の体重 71.8 kg」 |
| 4–11.5 | グラフを左から右へスキャン表示。スタート 77.6 kg → 現在 71.8 kg |
| 11.5–16.5 | まとめ: 開始時 / 現在 / 合計 -5.8 kg のカウントアップ |

## 生成方法

```bash
pip install pillow numpy imageio-ffmpeg
python3 make_reel.py            # output/weight_reel.mp4 を書き出し
python3 make_reel.py --preview  # 各シーンの静止画を output/preview/ に書き出し
```

日付・体重の数値は `make_reel.py` 冒頭の `TODAY` / `CURRENT` / `START` で変更できます。
画像を差し替える場合は `assets/scale.jpg` と `assets/graph.jpg` を置き換えてください。
