#!/usr/bin/env python3
"""体重記録リール生成スクリプト (1080x1920, 30fps, 約16秒)

使い方:
    pip install pillow numpy imageio-ffmpeg
    python3 make_reel.py

assets/scale.jpg  … 体重計の写真
assets/graph.jpg  … 体重記録グラフ (1080x1920)
output/weight_reel.mp4 に書き出します。
"""
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
OUT = os.path.join(HERE, "output", "weight_reel.mp4")

W, H, FPS = 1080, 1920, 30
BG = (11, 15, 26)
BLUE = (66, 165, 245)
GREEN = (102, 209, 140)
ORANGE = (255, 182, 72)
PINK = (255, 92, 138)
WHITE = (255, 255, 255)
GRAY = (160, 168, 184)

JP = "/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf"
NUM = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# 今日の数値
TODAY = "2026.09.16"
CURRENT = 71.8
START = 77.6
DIFF = CURRENT - START  # -5.8

# ---------- helpers ----------
_fonts = {}


def font(path, size):
    key = (path, size)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(path, size)
    return _fonts[key]


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_in_out(t):
    t = clamp(t)
    return 0.5 - 0.5 * math.cos(math.pi * t)


def prog(t, start, dur):
    """t秒時点での [start, start+dur] 区間の進捗 0..1"""
    if dur <= 0:
        return 1.0
    return clamp((t - start) / dur)


def cover(im, w, h, zoom=1.0, cx=0.5, cy=0.5):
    """画像を w x h にカバーフィット。zoom>1 で拡大、(cx,cy) を中心に切り出す"""
    iw, ih = im.size
    s = max(w / iw, h / ih) * zoom
    nw, nh = int(iw * s) + 1, int(ih * s) + 1
    r = im.resize((nw, nh), Image.LANCZOS)
    x0 = int((nw - w) * cx)
    y0 = int((nh - h) * cy)
    return r.crop((x0, y0, x0 + w, y0 + h))


def text_size(draw, s, f):
    l, t, r, b = draw.textbbox((0, 0), s, font=f)
    return r - l, b - t


def draw_text(base, xy, s, f, fill, anchor="la", alpha=1.0, shadow=True):
    """アルファ付きテキスト描画 (影あり)"""
    if alpha <= 0:
        return
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    a = int(255 * clamp(alpha))
    if shadow:
        d.text((xy[0] + 3, xy[1] + 4), s, font=f, fill=(0, 0, 0, int(a * 0.6)), anchor=anchor)
    d.text(xy, s, font=f, fill=fill + (a,), anchor=anchor)
    base.alpha_composite(layer)


def vgradient(w, h, top, bottom):
    """上→下のグラデーション RGBA"""
    a = np.linspace(top[3], bottom[3], h, dtype=np.float32)
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    for i in range(3):
        arr[..., i] = np.linspace(top[i], bottom[i], h, dtype=np.float32)[:, None]
    arr[..., 3] = a[:, None]
    return Image.fromarray(arr, "RGBA")


def blend(a, b, t):
    """2枚の RGB 画像をクロスフェード"""
    if t <= 0:
        return a
    if t >= 1:
        return b
    return Image.blend(a, b, t)


# ---------- assets ----------
scale_src = Image.open(os.path.join(ASSETS, "scale.jpg")).convert("RGB")
graph_src = Image.open(os.path.join(ASSETS, "graph.jpg")).convert("RGB").resize((W, H), Image.LANCZOS)

# グラフのプロット領域 (graph.jpg 上の座標)
PLOT_L, PLOT_R, PLOT_T, PLOT_B = 96, 1046, 172, 1738

# ---------- timeline (秒) ----------
S1_START, S1_DUR = 0.0, 4.0     # 体重計
XF1 = 0.6                        # クロスフェード
S2_START, S2_DUR = 4.0, 7.5     # グラフ
XF2 = 0.6
S3_START, S3_DUR = 11.5, 5.0    # まとめ
TOTAL = S3_START + S3_DUR       # 16.5 秒
FADE_IN, FADE_OUT = 0.5, 0.6


# ---------- scene 1: scale ----------
def scene_scale(t):
    p = prog(t, S1_START, S1_DUR)
    zoom = 1.0 + 0.10 * ease_in_out(p)
    base = cover(scale_src, W, H, zoom=zoom, cx=0.5, cy=0.42).convert("RGBA")
    # 下部を暗くして文字を読みやすく
    base.alpha_composite(vgradient(W, H, (0, 0, 0, 0), (0, 0, 0, 215)))
    # 上部も少し
    top = vgradient(W, 520, (0, 0, 0, 150), (0, 0, 0, 0))
    base.alpha_composite(top, (0, 0))

    # 日付 (上)
    a = ease_out(prog(t, 0.3, 0.5))
    draw_text(base, (W // 2, 170 - int(20 * (1 - a))), TODAY, font(NUM, 54), GRAY, "mm", a)
    a = ease_out(prog(t, 0.5, 0.5))
    draw_text(base, (W // 2, 250 - int(20 * (1 - a))), "今朝の体重", font(JP, 64), WHITE, "mm", a)

    # 大きな数字 (下) ポップイン
    a = ease_out(prog(t, 1.0, 0.6))
    s = 0.7 + 0.3 * a
    f = font(NUM, int(240 * s))
    draw_text(base, (W // 2 - 40, 1440), f"{CURRENT:.1f}", f, BLUE, "mm", a)
    draw_text(base, (W // 2 + 330, 1500), "kg", font(NUM, int(90 * s)), BLUE, "mm", a)

    a = ease_out(prog(t, 1.8, 0.6))
    draw_text(base, (W // 2, 1660 + int(20 * (1 - a))), "毎日はかって 21ヶ月", font(JP, 62), WHITE, "mm", a)
    a = ease_out(prog(t, 2.3, 0.6))
    draw_text(base, (W // 2, 1750 + int(20 * (1 - a))), "記録はこうなりました ▼", font(JP, 50), GRAY, "mm", a)
    return base.convert("RGB")


# ---------- scene 2: graph reveal ----------
_dark_overlay = None


def scene_graph(t):
    global _dark_overlay
    base = graph_src.copy().convert("RGBA")
    reveal_dur = 5.0
    p = ease_in_out(prog(t, S2_START + 0.4, reveal_dur))
    x = int(PLOT_L + (PLOT_R - PLOT_L) * p)

    if p < 1.0:
        # 未到達部分を暗く隠す
        if _dark_overlay is None:
            _dark_overlay = Image.new("RGBA", (PLOT_R - PLOT_L, PLOT_B - PLOT_T), (8, 10, 18, 232))
        base.alpha_composite(_dark_overlay.crop((x - PLOT_L, 0, PLOT_R - PLOT_L, PLOT_B - PLOT_T)), (x, PLOT_T))
        # スキャンライン (発光)
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        gd.rectangle((x - 6, PLOT_T, x + 6, PLOT_B), fill=BLUE + (120,))
        glow = glow.filter(ImageFilter.GaussianBlur(10))
        base.alpha_composite(glow)
        ld = ImageDraw.Draw(base)
        ld.rectangle((x - 2, PLOT_T, x + 2, PLOT_B), fill=WHITE + (255,))

    # 開始点 / 現在点のコールアウト
    a = ease_out(prog(t, S2_START + 0.6, 0.5))
    draw_text(base, (PLOT_L + 150, 330), "スタート", font(JP, 40), GRAY, "la", a)
    draw_text(base, (PLOT_L + 150, 380), f"{START:.1f} kg", font(NUM, 60), WHITE, "la", a)

    a = ease_out(prog(t, S2_START + 0.4 + reveal_dur, 0.5))
    draw_text(base, (PLOT_R - 30, 1440 + int(30 * (1 - a))), "現在", font(JP, 40), GRAY, "ra", a)
    draw_text(base, (PLOT_R - 30, 1490 + int(30 * (1 - a))), f"{CURRENT:.1f} kg", font(NUM, 60), BLUE, "ra", a)

    # 上部タイトルの上に短い見出し
    a = ease_out(prog(t, S2_START + 0.2, 0.5))
    # タイトルは画像に既にあるので、下部の合計減量を強調する枠だけ
    a2 = ease_out(prog(t, S2_START + 0.4 + reveal_dur + 0.4, 0.5))
    if a2 > 0:
        pulse = 0.5 + 0.5 * math.sin((t - (S2_START + reveal_dur)) * 5.0)
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.rounded_rectangle((820, 1820, 1060, 1905), radius=18, outline=GREEN + (int(255 * a2 * (0.5 + 0.5 * pulse)),), width=5)
        base.alpha_composite(layer)
    return base.convert("RGB")


# ---------- scene 3: summary ----------
def scene_summary(t):
    base = Image.new("RGBA", (W, H), BG + (255,))
    # うっすら背景グラフ
    faint = graph_src.copy()
    faint = Image.blend(Image.new("RGB", (W, H), BG), faint, 0.12)
    base = faint.convert("RGBA")

    a = ease_out(prog(t, S3_START + 0.2, 0.5))
    draw_text(base, (W // 2, 260 - int(20 * (1 - a))), "2024.12 → 2026.9", font(NUM, 56), GRAY, "mm", a)
    a = ease_out(prog(t, S3_START + 0.4, 0.5))
    draw_text(base, (W // 2, 360 - int(20 * (1 - a))), "21ヶ月のまとめ", font(JP, 84), WHITE, "mm", a)

    rows = [
        ("開始時", f"{START:.1f} kg", WHITE, S3_START + 0.9),
        ("現在", f"{CURRENT:.1f} kg", BLUE, S3_START + 1.4),
    ]
    y = 640
    for label, val, col, st in rows:
        a = ease_out(prog(t, st, 0.5))
        dx = int(60 * (1 - a))
        draw_text(base, (120 + dx, y), label, font(JP, 64), GRAY, "lm", a)
        draw_text(base, (W - 120 - dx, y), val, font(NUM, 100), col, "rm", a)
        y += 200

    # 区切り線
    a = ease_out(prog(t, S3_START + 1.9, 0.4))
    if a > 0:
        d = ImageDraw.Draw(base)
        L = int((W - 240) * a)
        d.line((120, 990, 120 + L, 990), fill=GRAY + (int(255 * a),), width=3)

    # 合計 (カウントアップ)
    a = ease_out(prog(t, S3_START + 2.1, 0.8))
    val = DIFF * a
    s = 0.85 + 0.15 * a
    draw_text(base, (W // 2, 1150), "合計", font(JP, 64), GRAY, "mm", a)
    draw_text(base, (W // 2, 1330), f"{val:+.1f} kg".replace("+-", "-"), font(NUM, int(220 * s)), GREEN, "mm", a)

    a = ease_out(prog(t, S3_START + 3.0, 0.6))
    draw_text(base, (W // 2, 1600 + int(20 * (1 - a))), "まだ続けます", font(JP, 72), WHITE, "mm", a)
    a = ease_out(prog(t, S3_START + 3.4, 0.6))
    draw_text(base, (W // 2, 1700 + int(20 * (1 - a))), "#体重記録 #毎日計測 #ダイエット記録", font(JP, 44), GRAY, "mm", a)
    return base.convert("RGB")


# ---------- compositor ----------
def frame_at(t):
    if t < S2_START:
        im = scene_scale(t)
    elif t < S2_START + XF1:
        im = blend(scene_scale(t), scene_graph(t), ease_in_out(prog(t, S2_START, XF1)))
    elif t < S3_START:
        im = scene_graph(t)
    elif t < S3_START + XF2:
        im = blend(scene_graph(t), scene_summary(t), ease_in_out(prog(t, S3_START, XF2)))
    else:
        im = scene_summary(t)

    # 全体フェード
    k = 1.0
    if t < FADE_IN:
        k = t / FADE_IN
    elif t > TOTAL - FADE_OUT:
        k = (TOTAL - t) / FADE_OUT
    if k < 1.0:
        im = Image.blend(Image.new("RGB", (W, H), (0, 0, 0)), im, clamp(k))
    return im


def main():
    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ffmpeg = "ffmpeg"

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    n = int(TOTAL * FPS)
    cmd = [
        ffmpeg, "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", OUT,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(n):
        t = i / FPS
        proc.stdin.write(frame_at(t).tobytes())
        if i % 60 == 0:
            print(f"  {i}/{n} frames ({t:.1f}s)", file=sys.stderr)
    proc.stdin.close()
    proc.wait()
    if proc.returncode != 0:
        sys.exit(f"ffmpeg failed: {proc.returncode}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--preview":
        # 各シーンの静止画を書き出す
        d = os.path.join(HERE, "output", "preview")
        os.makedirs(d, exist_ok=True)
        for name, t in [("s1", 3.0), ("s2a", 6.5), ("s2b", 10.8), ("s3", 15.5)]:
            frame_at(t).save(os.path.join(d, f"{name}.jpg"), quality=88)
        print("previews in", d)
    else:
        main()
