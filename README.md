<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
  <img src="https://img.shields.io/badge/CLIP-ViT--L--14-orange" alt="CLIP ViT-L-14">
  <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-999999" alt="macOS | Linux | Windows">
</p>

# cull — AI-powered orphan image cleaner

> **Classify → Organise → Deduplicate → Clean up**  
> Turn messy photo dumps into clean category folders using CLIP zero-shot vision.

```bash
cull classify ~/Downloads/messy/          # scan & classify with CLIP
cull organize --execute                   # sort into category folders
cull dedup sorted/ --execute              # move near-duplicates aside
cull cleanup --strategy trash --execute   # reclaim disk space from duplicates
cull volumes                              # list external drives
cull gui                                  # launch web interface
```

---

## Features

- **Zero-shot classification** — CLIP ViT-L-14 (or ViT-B-32) categorises images without any training data
- **21 categories** — person, screenshot, meme, document, food, landscape, animal, NSFW, video call, etc. (plus PDF by extension)
- **Custom categories** — extend or override the built-ins with a YAML file
- **Perceptual dedup** — `imagehash.dhash` on images; videos hashed via an extracted frame
- **External drive support** — auto-detect mounted volumes (macOS / Linux / Windows), mount validation before every run, safe eject on macOS
- **Cleanup strategies** — trash, permanent delete, or list-only, optionally per category
- **Dry-run by default** — every destructive operation requires explicit `--execute`
- **Dual interface** — CLI via `fire` + Gradio web GUI + Streamlit report viewer
- **Video & PDF** — frame extraction for videos (classification and dedup), extension-based PDF detection
- **Hardware accelerated** — MPS (Apple Silicon), CUDA, or CPU; ~11 img/s with ViT-L-14 on M-series

---

## Quick start

```bash
# Install
pip install cull

# Classify a folder
cull classify ~/Pictures/orphans/

# Preview what would be organised
cull organize

# Actually organise files
cull organize --execute

# Find and move near-duplicates
cull dedup ./orphans_sorted/ --execute

# See what you could clean up
cull cleanup

# Free space (moves duplicates to macOS Trash)
cull cleanup --strategy trash --execute

# Launch the web GUI
cull gui

# Browse results in Streamlit
cull browse
```

### On an external drive

```bash
cull volumes                          # list available drives
cull classify /Volumes/MyUSB/Photos/  # classify from USB
cull organize --execute               # organise on the drive
cull volumes --eject MyUSB            # safe eject when done
```

---

## CLI reference

| Command | Description | Default |
|---------|-------------|---------|
| `classify <path>` | Scan & classify images with CLIP | `--threshold 0.3` |
| `organize` | Move/copy into category folders | dry-run |
| `dedup <path>` | Find & move near-duplicates | dry-run |
| `cleanup` | Remove/trash duplicates (`--strategy trash\|delete\|list`, `--category X`) | dry-run, `--strategy trash` |
| `volumes [--eject X]` | List & eject external drives | — |
| `gui` | Launch Gradio web interface | — |
| `browse [--report]` | Launch Streamlit viewer | — |
| `categories` | Print available labels | — |
| `delete --category X` | Legacy bulk-delete | dry-run |
| `version` | Print version | — |

### classify options

| Flag | Default | Description |
|------|---------|-------------|
| `--threshold` | `0.3` | Minimum CLIP confidence (0–1) |
| `--batch-size` | `32` | Images per inference batch |
| `--model` | `ViT-B-32` | CLIP variant (`ViT-L-14` for accuracy) |
| `--pretrained` | `laion2b_s34b_b79k` | Weights tag |
| `--include-media` | `False` | Also classify videos and PDFs |
| `--categories` | `None` | YAML file with custom category definitions |

### Custom categories

Define your own categories in a YAML file — they merge with the built-in set:

```yaml
# my_categories.yaml
categories:
  receipt: ["a receipt", "a scanned receipt"]
  whiteboard: ["a whiteboard with writing"]
```

```bash
cull classify ./photos/ --categories my_categories.yaml
```

---

## How it works

```
                    ┌─────────────┐
                    │  CLIP Model  │  open-clip-torch (ViT-B-32 / ViT-L-14)
                    │ (zero-shot)  │  ~600MB / ~1.6GB
                    └──────┬──────┘
                           │ image embedding
                           ▼
               ┌───────────────────────┐
               │ Category Similarity   │  dot product with text embeddings
               │ Scores (top-K label)  │  "person: 0.89, screenshot: 0.07"
               └───────────────────────┘
                           │
                           ▼
               ┌───────────────────────┐
               │ Categorized Report    │  JSON + terminal table + Gradio
               └───────────────────────┘
```

### Categories (extensible)

```
person       screenshot   meme         document     wallpaper
food         landscape    animal       urban        object
text_heavy   low_quality  downloaded   NSFW
screencast   movie_clip   animation    video_call   gaming
short_clip   nsfw_video   pdf
```

---

## Architecture

```
cull/
├── __main__.py       CLI dispatch (fire)
├── config.py         Centralised defaults & constants
├── categories.py     Category definitions + prompts
├── media.py          File type detection + volume utilities (SSoT for extensions)
├── models.py         CLIP model singleton
├── classify.py       Classification service
├── organize.py       File organisation
├── dedup.py          Perceptual hashing dedup
├── cleanup.py        Duplicate cleanup strategies
├── volumes.py        External drive support
├── report.py         JSON report + terminal table
├── gui.py            Gradio web interface
├── browse.py         Streamlit report viewer
└── delete.py         Legacy bulk-delete
```

### Design principles

| Principle | How cull follows it |
|-----------|---------------------|
| **DRY** | Extension sets live in ONE place (`media.py`) |
| **SRP** | Each module has exactly one responsibility |
| **Fail-safe** | All destructive ops default to dry-run — opt in with `--execute` |
| **Mount-safe** | Every command checks the target path is reachable before scanning |

---

## Requirements

- **Python 3.10+**
- **macOS, Linux, or Windows** — volume discovery works on all three; eject uses `diskutil` (macOS-only)
- **~2 GB disk** for the CLIP ViT-L-14 model cache on first run (ViT-B-32 is ~600 MB)
- **ffmpeg** (optional, required for video frame extraction)

---

## License

MIT — see [LICENSE](LICENSE).

---

## Development

```bash
git clone https://github.com/Yogendra96/cull.git
cd cull
uv venv
source .venv/bin/activate
uv pip install -e ".[all]"
cull categories
```

Run tests:

```bash
uv pip install pytest
uv run pytest
```
