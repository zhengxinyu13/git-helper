#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 app.ico —— 蓝紫渐变圆角方块 + 白色 Git 分支图形。

只在需要重新设计图标时才跑一次（用打包用的那个 venv 里的 python，因为需要 Pillow）。
"""
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "app.ico")
SIZE = 512
SIZES = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def gradient(size, c1, c2):
    """对角线渐变"""
    img = Image.new("RGB", (size, size))
    d = ImageDraw.Draw(img)
    for y in range(size):
        for_x = y / max(size - 1, 1)
        col = lerp(c1, c2, for_x * 0.75)
        d.line([(0, y), (size, y)], fill=col)
    # 再叠一层横向变化，让渐变不那么平
    overlay = Image.new("RGB", (size, size))
    od = ImageDraw.Draw(overlay)
    for x in range(size):
        t = x / max(size - 1, 1)
        od.line([(x, 0), (x, size)], fill=lerp(c2, c1, t * 0.35))
    return Image.blend(img, overlay, 0.45)


def rounded_mask(size, radius_ratio=0.24):
    m = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([0, 0, size - 1, size - 1],
                        radius=int(size * radius_ratio), fill=255)
    return m


def draw_git_glyph(d, size, color):
    """三个节点 + 两条连线的分支图"""
    u = size / 512.0
    lw = max(2, int(22 * u))
    r = int(46 * u)

    def node(cx, cy):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)

    # 主干：左下 → 中
    d.line([(150 * u, 372 * u), (300 * u, 200 * u)], fill=color, width=lw)
    # 分支：中 → 右上
    d.line([(300 * u, 200 * u), (392 * u, 130 * u)], fill=color, width=lw)
    # 分支连线到右下节点
    d.line([(300 * u, 200 * u), (352 * u, 320 * u)], fill=color, width=lw)

    node(int(150 * u), int(372 * u))     # 起点
    node(int(392 * u), int(130 * u))     # 分支头
    node(int(352 * u), int(320 * u))     # 另一分支头
    node(int(300 * u), int(200 * u))     # 汇合点（画在最上层稍小）
    r2 = int(34 * u)
    d.ellipse([300 * u - r2, 200 * u - r2, 300 * u + r2, 200 * u + r2], fill=color)


def build(size):
    img = gradient(size, (59, 111, 212), (140, 96, 224))
    d = ImageDraw.Draw(img)
    draw_git_glyph(d, size, (255, 255, 255))
    img.putalpha(rounded_mask(size))
    return img


def main():
    base = build(SIZE)
    # Pillow 会按 sizes 自动缩放并写入多尺寸帧
    base.save(OUT, format="ICO", sizes=SIZES)
    print("已生成图标：%s（%d 字节）" % (OUT, os.path.getsize(OUT)))


if __name__ == "__main__":
    main()
