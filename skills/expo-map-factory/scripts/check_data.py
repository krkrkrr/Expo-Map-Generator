#!/usr/bin/env python3
"""マップのデータ（map-data.json）が契約（references/data-contract.md）を満たすかを検査する。

使い方:
  python3 check_data.py <map-data.json> [--layout layout.json] [--min-coverage 0.9]
最後の行に FACTORY_GATES 形式で結果を出す。必須の検査が実行できなければ GREEN にしない。
"""
import argparse
import json
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("--layout", help="layout.json（ページ寸法の照合に使う）")
    ap.add_argument("--min-coverage", type=float, default=0.9,
                    help="位置が付いた出展者の割合の下限（憲章の値を渡す）")
    a = ap.parse_args()

    results = {}  # name -> (ok, detail)
    try:
        D = json.loads(Path(a.data).read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"cannot read data: {e}")
        print("FACTORY_GATES: level=data status=MISCONFIGURED passed=0 failed=0 failing= skipped= misconfigured=read")
        sys.exit(2)

    meta = D.get("meta") or {}
    miss = [k for k in ("event", "map_pdf", "sources", "fetched") if not meta.get(k)]
    results["D1-meta"] = (not miss, f"meta に無い: {miss}" if miss else "ok")

    pages = {p["page"]: p for p in (D.get("pages") or [])}
    if a.layout:
        L = json.loads(Path(a.layout).read_text(encoding="utf-8"))
        bad = [p["page"] for p in L["pages"]
               if p["page"] not in pages or abs(pages[p["page"]]["w"] - p["w"]) > 0.5
               or abs(pages[p["page"]]["h"] - p["h"]) > 0.5]
        results["D2-pages"] = (bool(pages) and not bad, f"layout と寸法が違うページ: {bad}" if bad else "ok")
    else:
        results["D2-pages"] = (bool(pages) and all(p.get("w") and p.get("h") for p in pages.values()),
                               "pages に w/h が必要")

    ex = D.get("exhibitors") or []
    ids = [e.get("id") for e in ex]
    dup = sorted({i for i in ids if ids.count(i) > 1}, key=str)
    nonint = [i for i in ids if not isinstance(i, int)]
    noname = [e.get("id") for e in ex if not str(e.get("name") or "").strip()]
    ok = bool(ex) and not dup and not nonint and not noname
    results["D3-ids"] = (ok, f"重複={dup[:5]} 整数でない={nonint[:5]} 名前なし={noname[:5]} 件数={len(ex)}")

    oob, nosrc, noinf_note = [], [], []
    for e in ex:
        m = e.get("map")
        if not m:
            continue
        pg = pages.get(m.get("page"))
        if (not pg or m["w"] <= 0 or m["h"] <= 0 or m["x"] < -1 or m["y"] < -1
                or m["x"] + m["w"] > pg["w"] + 1 or m["y"] + m["h"] > pg["h"] + 1):
            oob.append(e["id"])
        if not (m.get("match") or {}).get("method"):
            nosrc.append(e["id"])
        if (m.get("inferred") or m.get("extra")) and not e.get("booth_note"):
            noinf_note.append(e["id"])
    results["D4-bounds"] = (not oob, f"ページ外・寸法不正: {oob[:10]}" if oob else "ok")
    results["D5-source"] = (not nosrc and not noinf_note,
                            f"位置の出どころ(map.match.method)なし: {nosrc[:10]} / 推定なのに booth_note なし: {noinf_note[:10]}"
                            if (nosrc or noinf_note) else "ok")

    mapped = [e for e in ex if e.get("map")]
    zone_ids = {i for z in (D.get("zones") or []) for i in z.get("ids", [])}
    covered = len({e["id"] for e in mapped} | zone_ids)
    cov = covered / max(len(ex), 1)
    results["D6-coverage"] = (cov >= a.min_coverage, f"位置あり {covered}/{len(ex)} = {cov:.1%}（下限 {a.min_coverage:.0%}）")

    unexplained = [e["id"] for e in ex if not e.get("map") and e["id"] not in zone_ids and not e.get("map_note")]
    results["D7-unmapped-reason"] = (not unexplained,
                                     f"位置なしで理由(map_note)なし: {unexplained[:10]}" if unexplained else "ok")

    bad_zone = [z.get("name") for z in (D.get("zones") or [])
                if z.get("page") not in pages or not z.get("ids") or any(i not in set(ids) for i in z["ids"])]
    results["D8-zones"] = (not bad_zone, f"不正なゾーン: {bad_zone}" if bad_zone else "ok")

    th = D.get("theme")
    text_only = all((e.get("map_note") or "").find("会場図の表記のみ") >= 0 for e in D.get("exhibitors", [])) \
        if D.get("exhibitors") else False
    if not th and not text_only:
        results["D9-theme"] = (False, "theme がない（ジャンル分けは必須。会場図の表記のみで作ったときだけ省略可）")
    if th:
        gids = {g["id"] for g in th.get("genres", [])}
        badt = [k for k, v in (th.get("items") or {}).items()
                if int(k) not in set(ids) or not set(v.get("g", [])) <= gids or v.get("p") not in ("S", "A", "B", "C")
                or not v.get("evidence")]
        results["D9-theme"] = (bool(gids) and not badt,
                               f"不正・根拠(evidence)なしのテーマ付与: {badt[:10]}" if badt else "ok")

    for k, (ok, d) in results.items():
        print(f"{'PASS' if ok else 'FAIL'} {k}: {d}")
    failing = [k for k, (ok, _) in results.items() if not ok]
    passed = len(results) - len(failing)
    status = "GREEN" if not failing else "RED"
    print(f"FACTORY_GATES: level=data status={status} passed={passed} failed={len(failing)} "
          f"failing={','.join(failing)} skipped= misconfigured=")
    sys.exit(0 if status == "GREEN" else 1)


if __name__ == "__main__":
    main()
