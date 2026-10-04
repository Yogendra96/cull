# cull — AI-powered orphan image cleaner

CLI + GUI tool that classifies messy image collections (people? screenshots? memes? documents?)
using CLIP zero-shot vision, sorts them into clean category folders, finds and moves near-duplicates,
and supports external drive workflows.

```bash
pip install cull
cull classify ~/Pictures/          # → JSON report
cull organize --execute            # → category folders
cull dedup orphans_sorted/ --execute  # → duplicates moved aside
cull cleanup --strategy trash --execute  # → reclaim disk space
cull volumes                       # → see & eject external drives
cull gui                           # → Gradio web interface
```

---

## Directory Structure

```
cull/
├── pyproject.toml           # Package config (MIT, dependencies)
├── README.md
├── CHANGELOG.md
├── LICENSE
├── cull/
│   ├── __init__.py
│   ├── __main__.py          # CLI entry — fire, thin dispatch
│   ├── config.py            # Centralized constants & defaults
│   ├── categories.py        # Category definitions + prompts (+ YAML loading)
│   ├── media.py             # File type detection + volume utilities (single source of truth)
│   ├── models.py            # CLIP model loading & inference (module-level cache)
│   ├── classify.py          # Classification service — scans dirs, runs CLIP
│   ├── organize.py          # File organisation — move/copy into category folders
│   ├── dedup.py             # Duplicate detection — perceptual hashing (dhash)
│   ├── cleanup.py           # Duplicate cleanup — trash/delete/report
│   ├── volumes.py           # External drive support — list, mount-check, eject
│   ├── report.py            # Report generation — JSON + rich terminal table
│   ├── gui.py               # Gradio web interface (fully wired)
│   ├── browse.py            # Streamlit report viewer
│   └── delete.py            # Legacy bulk-delete by category
└── tests/                   # Unit tests (92)
```

## Architecture

```
                            ┌─────────────┐
                            │  CLI (fire)  │  __main__.py
                            └──────┬──────┘
                                   │ dispatch
          ┌────────────────────────┼────────────────────────┐
          │                        │                        │
   ┌──────▼──────┐         ┌──────▼──────┐         ┌───────▼───────┐
   │  classify   │         │  organize   │         │    dedup      │
   │  CLIP zero- │         │  move/copy  │         │  perceptual   │
   │  shot       │         │  cat dirs   │         │  hashing      │
   └──────┬──────┘         └──────┬──────┘         └───────┬───────┘
          │                      │                         │
   ┌──────▼──────┐        ┌──────▼──────┐         ┌───────▼───────┐
   │  models.py  │        │  media.py   │         │   cleanup.py  │
   │  CLIP load  │        │  ext sets   │         │   trash/del   │
   │  + infer    │        │  + volumes  │         │   + report    │
   └─────────────┘        └─────────────┘         └───────────────┘
```

### Design principles

| Principle | How cull follows it |
|-----------|---------------------|
| **Single Responsibility** | Each module has one job: `models.py` = model, `classify.py` = CLIP logic, `volumes.py` = drives, etc. |
| **Open/Closed** | Add new categories by editing `categories.py` or loading a YAML config — no code changes needed in classify. |
| **DRY** | Extension sets live in ONE place (`media.py`). Every module imports from there. |
| **KISS** | No ORM, no async, no web framework dependency. CLI via `fire` (zero boilerplate), GUI via Gradio (same codebase). |
| **Dependency Inversion** | High-level modules (`classify`, `organize`, `dedup`) depend on `config.py` for defaults, not hardcoded constants. |
| **Fail-safe** | Every destructive operation (move, delete) defaults to **dry-run** — opt in with `--execute`. |

### External drive support

- **Auto-discovery:** `cull volumes` lists mounted external drives
- **Mount validation:** Every command checks the target path is reachable before starting
- **GUI volume picker:** The Gradio interface has a dedicated "Volumes" tab with refresh and eject
- **Safe eject:** `cull volumes --eject MyUSB` runs `diskutil eject` (macOS)
- **Cross-platform:** `/Volumes` (macOS), `/media` + `/mnt` (Linux), removable drive letters (Windows)

### CLI Commands

| Command | Description |
|---------|-------------|
| `cull classify <path>` | Scan & classify images with CLIP |
| `cull organize [--execute]` | Move files into category folders |
| `cull dedup <path> [--execute]` | Find & move near-duplicates |
| `cull cleanup [--strategy trash\|delete\|list] [--execute]` | Remove/trash duplicates |
| `cull volumes [--eject NAME]` | List & eject external drives |
| `cull gui` | Launch Gradio web UI |
| `cull browse [--report]` | Launch Streamlit report viewer |
| `cull categories` | Print available category labels |
| `cull delete --category X` | Legacy bulk-delete by category |
| `cull version` | Print version |

## Build Order

### Phase 1 — Core ✅
1. `pyproject.toml` — deps
2. `categories.py` — 21 category labels + prompts
3. `models.py` — CLIP load + inference
4. `classify.py` — scan dirs, run CLIP, handle videos/PDFs
5. `report.py` — JSON report + rich terminal table
6. `__main__.py` — wire CLI via fire

### Phase 2 — Organisation ✅
7. `organize.py` — move/copy into category folders
8. `dedup.py` — perceptual hashing for near-duplicates

### Phase 3 — GUI & External drives ✅
9. `gui.py` — Gradio interface (classify + browse + volumes tabs)
10. `browse.py` — Streamlit report viewer
11. `volumes.py` — auto-detect, validate, eject external drives
12. `cleanup.py` — duplicate cleanup strategies

### Phase 4 — Polish ✅
13. README, LICENSE, CHANGELOG
14. User-defined categories via YAML config
15. Frame-level video hashing (replaces size-only fallback)
16. Windows drive-letter detection

### Phase 5 — Future
17. PyPI publish
18. YOLO integration for object detection
