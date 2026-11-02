# Changelog

All notable changes to **cull** are documented in this file.

## [0.3.0] — 2026-11-03

### Added
- **`verify` command** — confirms every duplicate is byte-identical (SHA-256) to a file in a reference tree (external drive, backup) before removal. Perceptual `dedup` output is treated as untrusted: unverified files are preserved in a quarantine folder instead of being deleted. Supports `--against` (one or more comma-separated roots), `--strategy trash|delete|list`, `--quarantine`, `--workers`, and a JSON report.
- `cull.verify` module: size-indexed reference scanning, parallel hashing, self-match exclusion, empty-directory pruning.
- `send_to_trash()` is now public in `cull.cleanup` (old private name kept as an alias).

## [0.2.0] — 2026-07-15

Initial public release.

### Added
- **Classification** — CLIP zero-shot (ViT-B-32 / ViT-L-14) across 21 categories; videos via single-frame extraction, PDFs by extension
- **Organisation** — move/copy files into category folders with collision handling and dry-run default
- **Deduplication** — perceptual hashing (`imagehash.dhash`) for images; frame extraction for videos
- **Cleanup** — `trash` / `delete` / `list` strategies with per-category filter, dry-run default
- **External drives** — mounted-volume discovery (macOS `/Volumes`, Linux `/media` + `/mnt`, Windows removable drives `D:`–`Z:`), mount validation, safe eject via `diskutil` (macOS)
- **Custom categories** — merge user-defined YAML categories with the built-ins
- **Interfaces** — Gradio GUI (Classify / Browse / Volumes tabs) and Streamlit report viewer
- **Reports** — JSON report plus rich terminal summary table
- **CLI** — `classify`, `organize`, `dedup`, `cleanup`, `volumes`, `categories`, `gui`, `browse`, `delete`, `version`
- **Tests** — 92 unit tests

### Design notes
- Every destructive operation is dry-run by default (`--execute` to commit)
- Each command validates the target mount before scanning
- File-extension sets live in one place (`media.py`); defaults live in `config.py`
