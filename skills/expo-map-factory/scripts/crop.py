#!/usr/bin/env python3
"""会場図の一部を PNG に切り出す。照合の要確認・未照合を、目で（画像を読んで）確かめるために使う。

使い方:
  python3 crop.py <pdf> <page> <x> <y> <w> <h> <out.png> [--pad 40] [--dpi 200] [--mark]
  --mark を付けると、指定の矩形を赤枠で描く（照合結果が正しい区画を指しているかの確認用）
"""
import argparse

import pymupdf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf"); ap.add_argument("page", type=int)
    ap.add_argument("x", type=float); ap.add_argument("y", type=float)
    ap.add_argument("w", type=float); ap.add_argument("h", type=float)
    ap.add_argument("out")
    ap.add_argument("--pad", type=float, default=40)
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--mark", action="store_true")
    a = ap.parse_args()
    doc = pymupdf.open(a.pdf)
    p = doc[a.page - 1]
    r = pymupdf.Rect(a.x, a.y, a.x + a.w, a.y + a.h)
    if a.mark:
        p.draw_rect(r, color=(1, 0, 0), width=1.2)
    clip = pymupdf.Rect(r.x0 - a.pad, r.y0 - a.pad, r.x1 + a.pad, r.y1 + a.pad) & p.rect
    p.get_pixmap(clip=clip, dpi=a.dpi).save(a.out)
    print(a.out)


if __name__ == "__main__":
    main()
