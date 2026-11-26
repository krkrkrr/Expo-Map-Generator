#!/usr/bin/env python3
"""expo-map-factory の依存を調べ、--install なら入れられるものを入れる。

調べるもの:
  python    3.10 以上
  pymupdf   会場図の読み取り（必須）
  playwright と ブラウザ   smoke.py（必須）
  tesseract ブース番号の OCR（番号が図形で描かれた会場図で必須。無ければ社名だけで照合する）
  node/npm  アプリのビルドとテスト（初回のアプリ作成で必須）

--install で自動で入れるのは、Python のパッケージと Playwright のブラウザだけ。
OS のパッケージ（tesseract、node）は管理者権限が要ることがあるので、コマンドを出すだけにする。

最後の行に SETUP: status=READY|MISSING missing=<名前> の形で結果を出す。
"""
import argparse
import importlib.util
import subprocess
import sys

import _deps


def has_module(name):
    return importlib.util.find_spec(name) is not None


def pip_install(pkgs):
    cmd = [sys.executable, "-m", "pip", "install", *pkgs]
    r = subprocess.run(cmd)
    if r.returncode != 0:
        # PEP 668（OS 管理の Python）では --user でも断られることがある
        r = subprocess.run(cmd + ["--user"])
    return r.returncode == 0


def playwright_browser_ok():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None, "playwright が無い"
    with sync_playwright() as p:
        try:
            p.chromium.launch().close()
            return "playwright 同梱の Chromium", None
        except Exception:  # noqa: BLE001
            pass
        alt = _deps.find_system_browser()
        if alt:
            try:
                p.chromium.launch(executable_path=alt).close()
                return alt, None
            except Exception as e:  # noqa: BLE001
                return None, f"{alt} が起動しない: {str(e).splitlines()[0]}"
    return None, "起動できるブラウザが無い"


def run_version(cmd):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return (out.stdout or out.stderr).strip().splitlines()[0]
    except Exception:  # noqa: BLE001
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--install", action="store_true", help="入れられる依存を入れる")
    ap.add_argument("--no-app", action="store_true", help="node を調べない（既存の app/ を使わず、データだけ作る場合）")
    a = ap.parse_args()

    missing, rows = [], []

    ok = sys.version_info >= (3, 10)
    rows.append(("python", ok, sys.version.split()[0] + f" ({sys.executable})"))
    if not ok:
        missing.append("python")

    for mod, pkg in (("pymupdf", "pymupdf"), ("playwright", "playwright")):
        if not has_module(mod) and a.install:
            pip_install([pkg])
        ok = has_module(mod)
        rows.append((pkg, ok, "ok" if ok else f"{sys.executable} -m pip install {pkg}"))
        if not ok:
            missing.append(pkg)

    if has_module("playwright"):
        where, err = playwright_browser_ok()
        if not where and a.install:
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"])
            where, err = playwright_browser_ok()
        rows.append(("browser", bool(where), where or f"{err}。{sys.executable} -m playwright install chromium "
                                                     f"／ {_deps.hint('browser')}"))
        if not where:
            missing.append("browser")

    tes = _deps.find_tesseract()
    rows.append(("tesseract", bool(tes), (run_version([tes, "--version"]) or tes) if tes else _deps.hint("tesseract")))
    if not tes:
        missing.append("tesseract")

    if not a.no_app:
        nv = run_version(["node", "--version"])
        npm = run_version(["npm.cmd" if _deps.SYSTEM == "Windows" else "npm", "--version"])
        ok = bool(nv and npm)
        rows.append(("node/npm", ok, f"node {nv} / npm {npm}" if ok else _deps.hint("node")))
        if not ok:
            missing.append("node")

    w = max(len(r[0]) for r in rows)
    for name, ok, detail in rows:
        print(f"{'OK  ' if ok else 'MISS'} {name.ljust(w)}  {detail}")
    print(f"SETUP: status={'READY' if not missing else 'MISSING'} os={_deps.SYSTEM} missing={','.join(missing)}")
    sys.exit(0 if not missing else 1)


if __name__ == "__main__":
    main()
