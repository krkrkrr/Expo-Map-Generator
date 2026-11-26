"""外部ツールの場所を OS ごとに探す。extract_pdf.py、smoke.py、setup_check.py が共有する。"""
import glob
import os
import platform
import shutil

SYSTEM = platform.system()  # "Windows" / "Darwin" / "Linux"


def _first_existing(paths):
    for p in paths:
        for hit in sorted(glob.glob(os.path.expandvars(p))):
            if os.path.isfile(hit):
                return hit
    return None


def find_tesseract():
    """tesseract の実行ファイル。環境変数 TESSERACT_CMD を最優先にする。"""
    env = os.environ.get("TESSERACT_CMD")
    if env and os.path.isfile(env):
        return env
    hit = shutil.which("tesseract")
    if hit:
        return hit
    if SYSTEM == "Windows":
        return _first_existing([
            r"%ProgramFiles%\Tesseract-OCR\tesseract.exe",
            r"%ProgramFiles(x86)%\Tesseract-OCR\tesseract.exe",
            r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe",
        ])
    if SYSTEM == "Darwin":
        return _first_existing(["/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract"])
    return None


def find_system_browser():
    """Playwright 同梱のブラウザが無いときに使う、OS に入っている Chromium 系ブラウザ。

    環境変数 EXPO_MAP_BROWSER を最優先にする。
    """
    env = os.environ.get("EXPO_MAP_BROWSER")
    if env and os.path.isfile(env):
        return env
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "msedge"):
        hit = shutil.which(name)
        if hit:
            return hit
    if SYSTEM == "Windows":
        return _first_existing([
            r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
            r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
            r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
            r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
            r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
        ])
    if SYSTEM == "Darwin":
        return _first_existing([
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ])
    return None


INSTALL_HINTS = {
    "tesseract": {
        "Windows": "winget install --id UB-Mannheim.TesseractOCR -e   （入れた後、新しい端末を開く）",
        "Darwin": "brew install tesseract",
        "Linux": "sudo apt-get install -y tesseract-ocr   （Fedora: sudo dnf install tesseract）",
    },
    "node": {
        "Windows": "winget install --id OpenJS.NodeJS.LTS -e",
        "Darwin": "brew install node",
        "Linux": "sudo apt-get install -y nodejs npm   （古ければ https://nodejs.org の LTS）",
    },
    "browser": {
        "Windows": "Edge は標準で入っている。見つからなければ EXPO_MAP_BROWSER に msedge.exe のパスを設定",
        "Darwin": "brew install --cask google-chrome",
        "Linux": "sudo apt-get install -y chromium",
    },
}


def hint(name):
    return INSTALL_HINTS[name].get(SYSTEM, INSTALL_HINTS[name]["Linux"])
