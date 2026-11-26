# Expo-Map-Generator

A Claude Code plugin that turns an exhibition floor-plan PDF into a searchable, offline venue map (a single HTML file) from one sentence of input.

## Why

Exhibition floor plans are PDFs: you cannot search them, mark booths, or keep notes on a phone. Say "look at this floor-plan PDF and make a nice map", and the `expo-map-factory` skill builds the map on its own without asking questions along the way. Its assumptions are fixed: the map is for exhibitions you are about to visit, used by one person who opens an HTML file; the skill picks the genre breakdown from exhibitor descriptions, and does not do GPS location or hosting. It places every exhibitor on the organizer's own floor plan and checks the result with automated gates and a sampled visual audit.

The plugin is named `oneshot-factory` and contains:

| Skill | Role |
|---|---|
| `expo-map-factory` | Floor-plan PDF → venue map (search, favorites, visited marks, notes, offline, mobile) |
| `external-api-tos-check`, `unresolved-questions`, `playwright-test` | Bundled skills used by `expo-map-factory` (each keeps its own LICENSE) |

## Install

```bash
claude plugin marketplace add krkrkrr/Expo-Map-Generator
claude plugin install oneshot-factory@expo-map-generator
```

External tools: Python 3.10+, `pymupdf`, `playwright` with a Chromium-based browser, `tesseract` (OCR for booth numbers drawn as outlines), and Node.js (to build the map app the first time). The skill runs `scripts/setup_check.py` before it starts. It installs the Python packages and the browser itself, and prints the OS command for anything else (for example `winget install --id UB-Mannheim.TesseractOCR -e` on Windows).

## Quick Start

In Claude Code, inside the repository where you want the map app to live:

```
https://www.inter-bee.com/assets/dl/pdf/ja/BEE26_map_web_j.pdf を見て、良い感じのマップを作って
```

Output goes to `dist/<event>_map.html` (open it on a phone) and `dist/<event>_map-data.json`. The plain-language report goes to `doc/increments/<date>-<event>/factory/report.md`. The first run also builds the map app in `app/`, and later runs reuse it and only regenerate the data. `dist/` and `work/` hold the organizer's copyrighted material: keep them out of git and do not publish them.

## License

MIT. The bundled prerequisite skills under `skills/` keep their own licenses (see the LICENSE file in each skill directory).
