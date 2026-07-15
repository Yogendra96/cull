"""Streamlit report viewer for cull.

Launched via ``cull browse`` or ``streamlit run cull/browse.py cull_report.json``.
Displays classified images in a filterable thumbnail grid with per-file
delete checkboxes.
"""

import sys
import json
from pathlib import Path

import streamlit as st
from PIL import Image

from cull.media import is_image

st.set_page_config(layout="wide", page_title="cull — browse orphans")

# ── Load report ─────────────────────────────────────────────────────

report_path = sys.argv[-1] if len(sys.argv) > 1 else "cull_report.json"
report_file = Path(report_path)

if not report_file.exists():
    st.error(f"Report not found: {report_path}")
    st.info("Run `cull classify <folder>` first to generate a report.")
    st.stop()

with open(report_file) as f:
    report = json.load(f)

st.title("cull — orphan image browser")
st.caption(
    f"{report['total']} images · {report['classified']} classified · "
    f"{report['unclassified']} unclassified"
)

# ── Category filter ─────────────────────────────────────────────────

categories = list(report["categories"].keys())
selected = st.selectbox("Filter by category", ["all"] + categories)

# ── Build file list ─────────────────────────────────────────────────

all_files: list[dict] = []
for cat, info in report["categories"].items():
    for fp in info["files"]:
        all_files.append({"path": fp, "category": cat})

if selected != "all":
    all_files = [f for f in all_files if f["category"] == selected]

st.write(f"Showing {len(all_files)} files")

# ── Thumbnail grid ──────────────────────────────────────────────────

cols = st.columns(6)
to_delete: list[str] = []

for i, entry in enumerate(all_files):
    with cols[i % 6]:
        fp = entry["path"]
        if is_image(fp) and Path(fp).exists():
            try:
                img = Image.open(fp)
                st.image(img, width=200)
            except Exception:
                st.caption("(failed to load)")
        else:
            st.caption("(non-image or missing)")

        st.caption(f"{Path(fp).name}")
        st.caption(f"[{entry['category']}]")
        if st.checkbox("delete", key=fp):
            to_delete.append(fp)

# ── Delete action ───────────────────────────────────────────────────

if to_delete and st.button(f"Delete {len(to_delete)} selected files"):
    deleted = 0
    for fp in to_delete:
        p = Path(fp)
        if p.exists():
            p.unlink()
            deleted += 1
    st.success(f"Deleted {deleted} file(s)")
    st.rerun()
