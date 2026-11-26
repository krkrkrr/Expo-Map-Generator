#!/usr/bin/env python3
"""会場図 PDF から、マップ作成に要る素材を機械的に取り出す。

出力（OUTDIR 配下）:
  layout.json   ページ寸法、ブース候補の矩形、文字（語・ラベル）、番号らしき語
  page-<n>.jpg  各ページの画像（背景用）

座標はすべて PDF のポイント（左上原点）。画像はこの座標系に重ねて使う前提で、
image_scale（画像 px / PDF pt）を layout.json に記録する。

使い方:
  python3 extract_pdf.py <pdf のパスか URL> <OUTDIR> [--width 2400] [--quality 80]
依存: pymupdf（pip install pymupdf）。番号が図形で描かれた PDF では tesseract（apt install tesseract-ocr）
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

import pymupdf

import _deps

NUM_RE = re.compile(r"^[A-Za-z]{0,2}-?\d{1,5}[A-Za-z]?$")


def load_pdf(src: str, outdir: Path) -> Path:
    if re.match(r"^https?://", src):
        dst = outdir / "source.pdf"
        req = urllib.request.Request(src, headers={"User-Agent": "expo-map-factory/1.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            dst.write_bytes(r.read())
        return dst
    return Path(src)


def is_whiteish(c):
    return c is None or all(v > 0.97 for v in c)


def booth_rects(page):
    """塗りつぶされた矩形のうち、ブースらしい大きさのものを返す。"""
    W, H = page.rect.width, page.rect.height
    out, seen = [], set()
    for g in page.get_drawings():
        fill = g.get("fill")
        if is_whiteish(fill):
            continue
        for it in g["items"]:
            if it[0] == "re":
                r = it[1]
            elif it[0] == "qu":
                r = it[1].rect
            else:
                continue
            w, h = r.width, r.height
            if w < 4 or h < 4 or w * h > 0.05 * W * H:
                continue
            key = (round(r.x0, 1), round(r.y0, 1), round(w, 1), round(h, 1))
            if key in seen:
                continue
            seen.add(key)
            out.append({"x": key[0], "y": key[1], "w": key[2], "h": key[3],
                        "fill": "#%02x%02x%02x" % tuple(int(v * 255) for v in fill[:3])})
    return out


def smallest_containing(rects, cx, cy):
    best = None
    for i, r in enumerate(rects):
        if r["x"] <= cx <= r["x"] + r["w"] and r["y"] <= cy <= r["y"] + r["h"]:
            if best is None or r["w"] * r["h"] < rects[best]["w"] * rects[best]["h"]:
                best = i
    return best


def overlap_rect(rects, w, min_frac=0.4):
    """語の中心が矩形の外でも、語の面積の min_frac 以上が重なる最小の矩形を返す（はみ出した社名）。"""
    best, area = None, None
    wa = max(w["w"] * w["h"], 1e-6)
    for i, r in enumerate(rects):
        ix = min(w["x"] + w["w"], r["x"] + r["w"]) - max(w["x"], r["x"])
        iy = min(w["y"] + w["h"], r["y"] + r["h"]) - max(w["y"], r["y"])
        if ix > 0 and iy > 0 and ix * iy / wa >= min_frac:
            if best is None or r["w"] * r["h"] < area:
                best, area = i, r["w"] * r["h"]
    return best


def _bbox(ws):
    x0 = min(w["x"] for w in ws); y0 = min(w["y"] for w in ws)
    x1 = max(w["x"] + w["w"] for w in ws); y1 = max(w["y"] + w["h"] for w in ws)
    return x0, y0, x1, y1


def labels(words, rects):
    """語をラベル（社名候補）にまとめる。

    1. 中心が矩形の中にある語、または面積の 4 割以上が矩形に重なる語は、その矩形のラベルにする
    2. それ以外は PDF の行ごとにまとめ、縦に隣接して横位置が重なる行を 1 つのラベルにつなぐ
       （2 行に折り返した社名を 1 つにするため）
    """
    groups, free = {}, {}
    for w in words:
        cx, cy = (w["x"] + w["w"] / 2), (w["y"] + w["h"] / 2)
        ri = smallest_containing(rects, cx, cy)
        if ri is None:
            ri = overlap_rect(rects, w)
        if ri is not None:
            groups.setdefault(("r", ri), []).append(w)
        else:
            free.setdefault((w["block"], w["line"]), []).append(w)
    # 行をつなぐ（union-find）
    lines = list(free.values())
    parent = list(range(len(lines)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    boxes = [_bbox(l) for l in lines]
    for i in range(len(lines)):
        ax0, ay0, ax1, ay1 = boxes[i]
        for j in range(i + 1, len(lines)):
            bx0, by0, bx1, by1 = boxes[j]
            h = min(ay1 - ay0, by1 - by0)
            gap = max(by0 - ay1, ay0 - by1)
            ov = min(ax1, bx1) - max(ax0, bx0)
            if -0.5 * h <= gap <= 0.6 * h and ov > 0.3 * min(ax1 - ax0, bx1 - bx0):
                parent[find(j)] = find(i)
    for i, l in enumerate(lines):
        groups.setdefault(("l", find(i)), []).extend(l)
    out = []
    for key, ws in groups.items():
        ws.sort(key=lambda w: (round(w["y"] / 3), w["x"]))
        x0, y0, x1, y1 = _bbox(ws)
        out.append({"text": " ".join(w["t"] for w in ws), "x": round(x0, 1), "y": round(y0, 1),
                    "w": round(x1 - x0, 1), "h": round(y1 - y0, 1),
                    "rect": key[1] if key[0] == "r" else None})
    return out


def ocr_numbers(page, rects, scale=5.0, min_conf=50):
    """図形（アウトライン化された文字）で描かれたブース番号を OCR で読む。

    文字として取れない番号は多い。tesseract が無ければ空を返す。
    誤読を減らすため、ブースの矩形の中にある番号らしい語だけを残す。
    """
    tes = _deps.find_tesseract()
    if not tes:
        return None
    pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
    with tempfile.TemporaryDirectory() as td:
        img = Path(td) / "p.png"
        pix.save(str(img))
        out = subprocess.run(
            [tes, str(img), "stdout", "--psm", "11", "-c",
             "tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-", "tsv"],
            capture_output=True, text=True).stdout
    res = []
    for line in out.splitlines()[1:]:
        f = line.split("\t")
        if len(f) < 12 or not f[11].strip() or float(f[10]) < min_conf:
            continue
        t = f[11].strip()
        if not (NUM_RE.match(t) and re.search(r"\d{2}", t)):
            continue
        x, y, w, h = (int(v) / scale for v in f[6:10])
        ri = smallest_containing(rects, x + w / 2, y + h / 2)
        if ri is None:
            continue
        res.append({"t": t, "x": round(x, 1), "y": round(y, 1), "w": round(w, 1), "h": round(h, 1),
                    "rect": ri, "ocr": True, "conf": round(float(f[10]))})
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("outdir")
    ap.add_argument("--width", type=int, default=2400, help="ページ画像の横幅 px")
    ap.add_argument("--quality", type=int, default=80)
    ap.add_argument("--ocr", choices=["auto", "on", "off"], default="auto",
                    help="ブース番号の OCR。auto は文字として取れた番号が矩形の 2 割未満のページだけ")
    a = ap.parse_args()
    outdir = Path(a.outdir); outdir.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(load_pdf(a.pdf, outdir))
    pages = []
    for p in doc:
        n = p.number + 1
        W, H = p.rect.width, p.rect.height
        scale = a.width / W
        pix = p.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
        img = f"page-{n}.jpg"
        (outdir / img).write_bytes(pix.tobytes("jpeg", jpg_quality=a.quality))
        words = [{"t": w[4], "x": round(w[0], 1), "y": round(w[1], 1),
                  "w": round(w[2] - w[0], 1), "h": round(w[3] - w[1], 1),
                  "block": w[5], "line": w[6]} for w in p.get_text("words")]
        rects = booth_rects(p)
        nums = [w for w in words if NUM_RE.match(w["t"])]
        for w in nums:
            w["rect"] = smallest_containing(rects, w["x"] + w["w"] / 2, w["y"] + w["h"] / 2)
        ocr_state = "off"
        if a.ocr == "on" or (a.ocr == "auto" and rects and len(nums) < 0.2 * len(rects)):
            got = ocr_numbers(p, rects)
            if got is None:
                ocr_state = "unavailable"
                print(f"WARNING: page {n}: tesseract が無く番号の OCR を飛ばした", file=sys.stderr)
            else:
                have = {(w["t"], w["rect"]) for w in nums}
                nums += [w for w in got if (w["t"], w["rect"]) not in have]
                ocr_state = f"on({len(got)})"
        pages.append({"page": n, "w": round(W, 2), "h": round(H, 2), "image": img,
                      "image_scale": round(scale, 4), "rects": rects,
                      "labels": labels(words, rects), "numbers": nums,
                      "words": [{k: w[k] for k in ("t", "x", "y", "w", "h")} for w in words],
                      "raster_images": len(p.get_images()), "ocr": ocr_state})
    layout = {"source": a.pdf, "page_count": doc.page_count, "pages": pages}
    (outdir / "layout.json").write_text(json.dumps(layout, ensure_ascii=False), encoding="utf-8")
    for pg in pages:
        print(f"page {pg['page']}: {pg['w']}x{pg['h']}pt rects={len(pg['rects'])} "
              f"labels={len(pg['labels'])} numbers={len(pg['numbers'])} words={len(pg['words'])} ocr={pg['ocr']}")
    if all(len(pg["words"]) == 0 for pg in pages):
        print("WARNING: 文字が 1 つも取れない。画像だけの PDF の可能性。画像を読んで手で位置を起こす必要がある",
              file=sys.stderr)


if __name__ == "__main__":
    main()
