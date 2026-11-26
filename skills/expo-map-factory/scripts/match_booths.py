#!/usr/bin/env python3
"""出展者リストと会場図（layout.json）を突き合わせ、各出展者のマップ上の位置を決める。

入力:
  --layout     extract_pdf.py の layout.json
  --exhibitors 出展者リスト JSON（配列）。各要素は少なくとも
               {"id": int, "name": str, "booth": str|null, "aliases": [str]?}
  --overrides  任意。{"<id>": {"page":n,"x":..,"y":..,"w":..,"h":..,"note":"理由"} | null}
               null は「マップに載せない（位置なし）」と人が判断したもの。
出力:
  --out        出展者リストに map を付けた JSON
  --report     照合の結果（未照合、低スコア、宙に浮いたラベル）の Markdown

照合の順序（強い順）:
  1. override（人の判断）
  2. ブース番号の文字が PDF にあり、出展者の booth と一致
  3. 社名の照合（法人格などを除いて正規化し、包含・類似度で採点）
1 つのラベル片は 1 社にしか割り当てない。スコアが --min 未満は割り当てない。
"""
import argparse
import difflib
import json
import re
import unicodedata
from pathlib import Path

CORP = [
    "株式会社", "有限会社", "合同会社", "合資会社", "一般社団法人", "一般財団法人",
    "公益社団法人", "公益財団法人", "国立研究開発法人", "独立行政法人", "学校法人",
    "(株)", "(有)", "(同)", "(一社)", "(一財)", "(公社)", "(公財)", "㈱", "㈲",
    "co.,ltd.", "co., ltd.", "co.,ltd", "co. ltd", "co.ltd", "corporation", "corp.", "corp",
    "inc.", "inc", "ltd.", "ltd", "llc", "gmbh", "pte", "limited", "s.a.", "s.r.l.", "k.k.", "co.",
]
PUNCT = re.compile(r"[\s・･·\.\,\-‐‑–—/／\(\)（）\[\]【】「」『』\"'’“”!！?？&＆+＋:：;；]")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").lower()
    for c in CORP:
        s = s.replace(c, " ")
    return PUNCT.sub("", s)


def score(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    short, long_ = sorted((a, b), key=len)
    frac = len(short) / len(long_)
    if len(short) >= 2 and short in long_:
        # 先頭一致（「アシダ」⊂「アシダ音響」）は略称として強く、途中や末尾の一致
        # （「Electronics」⊂「Crestron Electronics」）は一般語の可能性があるので弱くする
        if long_.startswith(short) or frac >= 0.6:
            return 0.80 + 0.15 * frac
        return 0.55 + 0.2 * frac
    return difflib.SequenceMatcher(None, a, b).ratio() * 0.9


def split_label(text: str):
    """「東芝/ 東芝ライテック」のような共同出展の表記を社ごとに分ける。"""
    parts = [p.strip() for p in re.split(r"[/／]", text) if p.strip()]
    return parts or [text]


def box_of(page, lab):
    if lab.get("rect") is not None:
        r = page["rects"][lab["rect"]]
        return {"x": r["x"], "y": r["y"], "w": r["w"], "h": r["h"], "kind": "booth"}
    return {"x": lab["x"], "y": lab["y"], "w": lab["w"], "h": lab["h"], "kind": "label"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layout", required=True)
    ap.add_argument("--exhibitors", required=True)
    ap.add_argument("--overrides")
    ap.add_argument("--out", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--min", type=float, default=0.72, help="社名照合で採用する最低スコア")
    ap.add_argument("--review", type=float, default=0.88, help="これ未満は要確認として報告")
    a = ap.parse_args()

    layout = json.loads(Path(a.layout).read_text(encoding="utf-8"))
    exs = json.loads(Path(a.exhibitors).read_text(encoding="utf-8"))
    ovr = json.loads(Path(a.overrides).read_text(encoding="utf-8")) if a.overrides else {}
    pages = {p["page"]: p for p in layout["pages"]}

    # ラベル片の一覧
    pieces = []
    for p in layout["pages"]:
        for li, lab in enumerate(p["labels"]):
            for part in split_label(lab["text"]):
                n = norm(part)
                if len(n) >= 2:
                    pieces.append({"page": p["page"], "label": li, "text": part, "n": n,
                                   "in_rect": lab.get("rect") is not None})
    # 同じ文字列が何度も出る（凡例、一覧表、案内板）ときは、矩形の中にあるものだけを候補に残す
    cnt = {}
    for pc in pieces:
        cnt.setdefault(pc["n"], []).append(pc)
    for n_, lst in cnt.items():
        if len(lst) > 1 and any(x["in_rect"] for x in lst):
            for x in lst:
                if not x["in_rect"]:
                    x["dup_outside"] = True

    done = {}
    # 1. override
    for e in exs:
        k = str(e["id"])
        if k in ovr:
            o = ovr[k]
            done[e["id"]] = None if o is None else {
                "page": o["page"], "x": o["x"], "y": o["y"], "w": o["w"], "h": o["h"],
                "kind": o.get("kind", "booth"), "match": {"method": "override", "note": o.get("note", "")}}

    # 2. ブース番号
    numidx = {}
    for p in layout["pages"]:
        for w in p["numbers"]:
            numidx.setdefault(unicodedata.normalize("NFKC", w["t"]).upper(), []).append((p, w))
    for e in exs:
        if e["id"] in done or not e.get("booth"):
            continue
        hits = numidx.get(unicodedata.normalize("NFKC", str(e["booth"])).upper(), [])
        if len(hits) == 1:
            p, w = hits[0]
            if w.get("rect") is not None:
                r = p["rects"][w["rect"]]
                box = {"x": r["x"], "y": r["y"], "w": r["w"], "h": r["h"], "kind": "booth"}
            else:
                box = {"x": w["x"], "y": w["y"], "w": w["w"], "h": w["h"], "kind": "label"}
            done[e["id"]] = {"page": p["page"], **box,
                             "match": {"method": "booth-number-ocr" if w.get("ocr") else "booth-number",
                                       "score": 1.0}}

    # 3. 社名
    cands = []
    for e in exs:
        if e["id"] in done:
            continue
        names = [e["name"]] + list(e.get("aliases") or [])
        ns = [norm(x) for x in names if norm(x)]
        for pi, pc in enumerate(pieces):
            if pc.get("dup_outside"):
                continue
            s = max(score(n, pc["n"]) for n in ns) if ns else 0
            if pc["in_rect"]:
                s += 0.02  # 同点なら、ブースの矩形に入っている表記を優先する
            if s >= a.min:
                cands.append((s, e["id"], pi))
    cands.sort(key=lambda t: -t[0])
    used = set()
    for s, eid, pi in cands:
        if eid in done or pi in used:
            continue
        pc = pieces[pi]
        p = pages[pc["page"]]
        lab = p["labels"][pc["label"]]
        done[eid] = {"page": pc["page"], **box_of(p, lab),
                     "match": {"method": "name", "score": round(min(s, 1.0), 3), "label": pc["text"]}}
        used.add(pi)

    out, unmatched, review = [], [], []
    for e in exs:
        e = dict(e)
        m = done.get(e["id"])
        if m:
            e["map"] = m
            if m["match"].get("method") == "name" and m["match"]["score"] < a.review or m["kind"] == "label":
                review.append(e)
        else:
            e["map"] = None
            if str(e["id"]) not in ovr:
                unmatched.append(e)
        out.append(e)
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    orphan = [pc for i, pc in enumerate(pieces) if i not in used]
    n = len(exs); m = sum(1 for e in out if e["map"])
    by = {}
    for e in out:
        if e["map"]:
            k = e["map"]["match"]["method"]; by[k] = by.get(k, 0) + 1
    lines = ["# 照合レポート", "",
             f"- 出展者 {n} 件のうち位置あり {m} 件（{m / max(n, 1):.1%}）",
             "- 方法別: " + ", ".join(f"{k}={v}" for k, v in sorted(by.items())),
             f"- 未照合 {len(unmatched)} 件 / 要確認（スコア < {a.review}）{len(review)} 件 / "
             f"誰にも割り当たらなかった PDF 上のラベル片 {len(orphan)} 件", "",
             "## 要確認（名前の照合が弱い、または矩形が無く文字の位置だけ）", ""]
    lines += [f"- id={e['id']} {e['name']} → 「{e['map']['match'].get('label', '')}」 p{e['map']['page']} "
              f"{e['map']['kind']} score={e['map']['match'].get('score')}" for e in review] or ["- なし"]
    lines += ["", "## 未照合の出展者", ""]
    lines += [f"- id={e['id']} {e['name']} booth={e.get('booth')}" for e in unmatched] or ["- なし"]
    lines += ["", "## 割り当たらなかったラベル片（略称違い、共同出展、出展者リスト外の展示の可能性）", ""]
    lines += [f"- p{pc['page']} 「{pc['text']}」" for pc in orphan] or ["- なし"]
    Path(a.report).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"MATCH: total={n} mapped={m} rate={m / max(n, 1):.3f} unmatched={len(unmatched)} "
          f"review={len(review)} orphan_labels={len(orphan)} " + " ".join(f"{k}={v}" for k, v in sorted(by.items())))


if __name__ == "__main__":
    main()
