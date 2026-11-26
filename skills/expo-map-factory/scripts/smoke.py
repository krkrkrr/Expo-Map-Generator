#!/usr/bin/env python3
"""生成したマップ HTML を実ブラウザで開き、仕様が無くても言える最低限の動作を確かめる。

前提: HTML は references/data-contract.md の「テスト用の目印」を満たす
  window.EXPO_MAP_DATA / data-testid = search, exhibitor-item, booth, sheet-tab,
  map-image, detail, fav

使い方:
  python3 smoke.py <map.html> <map-data.json> [--browser /usr/bin/chromium] [--monkey 300] [--seed 1]
最後の行に FACTORY_GATES 形式で結果を出す。ブラウザが起動できなければ MISCONFIGURED。
"""
import argparse
import json
import random
import sys
from pathlib import Path

import _deps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("data")
    ap.add_argument("--browser", help="Chromium 系ブラウザの実行ファイル。省略時は Playwright 同梱、無ければ OS の Chrome/Edge/Chromium を探す（EXPO_MAP_BROWSER でも指定できる）")
    ap.add_argument("--monkey", type=int, default=300, help="ランダム操作の回数")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright が無い（pip install playwright）")
        print("FACTORY_GATES: level=smoke status=MISCONFIGURED passed=0 failed=0 failing= skipped= misconfigured=playwright")
        sys.exit(2)

    D = json.loads(Path(a.data).read_text(encoding="utf-8"))
    EX = D["exhibitors"]
    url = Path(a.html).resolve().as_uri()
    R = {}
    rnd = random.Random(a.seed)

    def rec(name, ok, detail=""):
        R[name] = (bool(ok), detail)

    with sync_playwright() as p:
        exe = a.browser or None
        try:
            b = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        except Exception:  # noqa: BLE001
            alt = _deps.find_system_browser()
            if not alt:
                print("FACTORY_GATES: level=smoke status=MISCONFIGURED passed=0 failed=0 failing= skipped= misconfigured=browser")
                sys.exit(2)
            b = p.chromium.launch(executable_path=alt)

        def open_page(offline=False, mobile=False):
            ctx = b.new_context(viewport={"width": 390, "height": 844} if mobile else {"width": 1366, "height": 860},
                                has_touch=mobile, is_mobile=mobile)
            errs = []
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: errs.append(f"pageerror: {e}"))
            pg.on("console", lambda m: m.type == "error" and errs.append(f"console: {m.text}"))
            if offline:
                pg.route("**/*", lambda r: r.abort() if r.request.url.startswith(("http:", "https:")) else r.continue_())
            pg.goto(url)
            pg.wait_for_timeout(800)
            return ctx, pg, errs

        # S1 読み込み、S2 データ件数、S3 一覧件数
        ctx, pg, errs = open_page()
        n_data = pg.evaluate("() => (window.EXPO_MAP_DATA && window.EXPO_MAP_DATA.exhibitors || []).length")
        rec("S2-data", n_data == len(EX), f"埋め込み {n_data} / map-data.json {len(EX)}")
        n_items = pg.locator('[data-testid="exhibitor-item"]').count()
        rec("S3-list", n_items == len(EX), f"一覧 {n_items} / {len(EX)}")

        # S4 シートごとに画像と区画
        tabs = pg.locator('[data-testid="sheet-tab"]')
        nt = tabs.count()
        pages_with_map = sorted({e["map"]["page"] for e in EX if e.get("map")})
        bad = []
        for i in range(max(nt, 1)):
            if nt:
                tabs.nth(i).click(); pg.wait_for_timeout(300)
            loaded = pg.evaluate("""() => [...document.querySelectorAll('[data-testid="map-image"]')]
                .filter(i => i.offsetParent !== null).every(i => i.complete && i.naturalWidth > 0)""")
            nb = pg.locator('[data-testid="booth"]').count()
            if not loaded or nb == 0:
                bad.append(f"tab{i}: image={loaded} booths={nb}")
        rec("S4-sheets", nt >= 1 and not bad and nt >= len(pages_with_map) > 0,
            f"タブ {nt} / 位置のあるページ {len(pages_with_map)} {bad}")

        # S5 検索 → 選択 → 詳細
        mapped = [e for e in EX if e.get("map")]
        target = rnd.choice(mapped) if mapped else None
        ok5, det5 = False, "位置のある出展者なし"
        if target:
            pg.fill('[data-testid="search"]', target["name"]); pg.wait_for_timeout(300)
            items = pg.locator('[data-testid="exhibitor-item"]')
            hit = pg.locator(f'[data-testid="exhibitor-item"][data-id="{target["id"]}"]')
            cnt = items.count()
            if hit.count():
                hit.first.click(); pg.wait_for_timeout(400)
                dv = pg.locator('[data-testid="detail"]')
                ok5 = 0 < cnt < len(EX) and dv.count() > 0 and dv.first.is_visible() and target["name"] in dv.first.inner_text()
                det5 = f"「{target['name']}」 検索結果 {cnt} 件, 詳細表示={ok5}"
            else:
                det5 = f"「{target['name']}」 が検索で出ない（{cnt} 件）"
        rec("S5-search-detail", ok5, det5)

        # S6 お気に入りが再読み込み後も残る
        ok6, det6 = False, "詳細が開けない"
        if ok5:
            fav = pg.locator('[data-testid="detail"] [data-testid="fav"]').first
            before = fav.get_attribute("aria-pressed")
            fav.click(); pg.wait_for_timeout(300)
            pg.reload(); pg.wait_for_timeout(800)
            pg.fill('[data-testid="search"]', target["name"]); pg.wait_for_timeout(300)
            pg.locator(f'[data-testid="exhibitor-item"][data-id="{target["id"]}"]').first.click(); pg.wait_for_timeout(400)
            after = pg.locator('[data-testid="detail"] [data-testid="fav"]').first.get_attribute("aria-pressed")
            ok6 = before in ("false", None) and after == "true"
            det6 = f"aria-pressed {before} → 再読み込み後 {after}"
        rec("S6-persist", ok6, det6)

        # S9 ランダム操作
        vp = pg.viewport_size
        pg.fill('[data-testid="search"]', "")
        for _ in range(a.monkey):
            r = rnd.random()
            x, y = rnd.randint(0, vp["width"] - 1), rnd.randint(0, vp["height"] - 1)
            try:
                if r < 0.55:
                    pg.mouse.click(x, y)
                elif r < 0.75:
                    pg.mouse.wheel(0, rnd.choice([-300, -120, 120, 300]))
                elif r < 0.9:
                    pg.mouse.move(x, y); pg.mouse.down()
                    pg.mouse.move(x + rnd.randint(-200, 200), y + rnd.randint(-200, 200), steps=4); pg.mouse.up()
                else:
                    pg.keyboard.press(rnd.choice(["Escape", "Tab", "Enter"]))
            except Exception:  # noqa: BLE001  ページ遷移などで操作が失敗しても続ける
                pass
            if pg.url != url:  # 外部リンクに飛んだら戻す
                pg.goto(url); pg.wait_for_timeout(300)
        rec("S1-no-errors", not errs, "; ".join(errs[:5]) or f"エラー 0（ランダム操作 {a.monkey} 回を含む）")
        ctx.close()

        # S7 オフラインでも地図が出る（1 ファイルで完結）
        ctx, pg, errs7 = open_page(offline=True)
        img_ok = pg.evaluate("""() => { const i=[...document.querySelectorAll('[data-testid="map-image"]')]
            .filter(i => i.offsetParent !== null); return i.length>0 && i.every(i => i.complete && i.naturalWidth > 0); }""")
        fatal = [e for e in errs7 if e.startswith("pageerror")]
        rec("S7-offline", img_ok and not fatal, f"画像={img_ok} {fatal[:3]}")
        ctx.close()

        # S8 スマホ幅: 横にはみ出さず、区画をタップすると詳細が出る
        ctx, pg, errs8 = open_page(mobile=True)
        overflow = pg.evaluate("() => document.documentElement.scrollWidth > window.innerWidth + 1")
        tapped = False
        bx = pg.locator('[data-testid="booth"]')
        for i in range(min(bx.count(), 30)):
            el = bx.nth(rnd.randrange(bx.count()))
            box = el.bounding_box()
            if box and 0 < box["x"] + box["width"] / 2 < 390 and 0 < box["y"] + box["height"] / 2 < 844:
                pg.touchscreen.tap(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2); pg.wait_for_timeout(400)
                d = pg.locator('[data-testid="detail"]')
                if d.count() and d.first.is_visible():
                    tapped = True
                    break
        rec("S8-mobile", not overflow and tapped and not errs8, f"横はみ出し={overflow} タップで詳細={tapped} {errs8[:3]}")
        ctx.close()
        b.close()

    for k in sorted(R):
        ok, d = R[k]
        print(f"{'PASS' if ok else 'FAIL'} {k}: {d}")
    failing = [k for k in sorted(R) if not R[k][0]]
    status = "GREEN" if not failing else "RED"
    print(f"FACTORY_GATES: level=smoke status={status} passed={len(R) - len(failing)} failed={len(failing)} "
          f"failing={','.join(failing)} skipped= misconfigured=")
    sys.exit(0 if status == "GREEN" else 1)


if __name__ == "__main__":
    main()
