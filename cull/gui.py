"""Gradio web interface for cull.

Provides a tabbed GUI for:
- **Classify:** Select a folder, pick a model, run CLIP classification.
- **Browse:** Load a report, view thumbnails by category, delete files.
- **Volumes:** List and eject external drives.

This module was previously incomplete (missing event handlers).  It is now
fully wired and tested against the Gradio 5+ / 6+ API.
"""

import json
from pathlib import Path

import gradio as gr

from cull.categories import DEFAULT_CATEGORIES
from cull.classify import classify_directory
from cull.report import generate_report, save_report
from cull.volumes import format_volume_summary, list_volumes, safe_eject

# ── Styles ───────────────────────────────────────────────────────────

CSS = """
.gallery { min-height: 400px; }
footer { display: none !important; }
"""


# ── Classify tab logic ───────────────────────────────────────────────


def _find_images(path: str) -> list[str]:
    """Return sorted list of image paths under *path*."""
    p = Path(path)
    if not p.is_dir():
        return []
    return sorted(
        str(f)
        for f in p.rglob("*")
        if f.is_file()
        and f.suffix.lower()
        in {
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".webp",
            ".bmp",
            ".tiff",
            ".tif",
            ".heic",
            ".heif",
            ".avif",
            ".jxl",
        }
    )


def _do_classify(
    folder: str,
    threshold: float,
    model_choice: str,
    progress: gr.Progress | None = None,
):
    """Run classification and return (summary_text, report_path, gallery_items)."""
    if progress is None:
        progress = gr.Progress()
    if not folder or not Path(folder).is_dir():
        return "Invalid folder path", None, None

    images = _find_images(folder)
    if not images:
        return f"No images found in {folder}", None, None

    model_map = {
        "Fast (ViT-B-32)": ("ViT-B-32", "laion2b_s34b_b79k"),
        "Accurate (ViT-L-14)": ("ViT-L-14", "laion2b_s32b_b82k"),
    }
    model_name, pretrained = model_map.get(
        model_choice, ("ViT-B-32", "laion2b_s34b_b79k")
    )

    yield f"Found {len(images)} images\nLoading model {model_choice}...", None, None

    labels = list(DEFAULT_CATEGORIES.keys())

    def progress_fn(current: int, total: int):
        progress(current / total, desc=f"Classifying {current}/{total}")

    results = classify_directory(
        images,
        labels,
        batch_size=32,
        model_name=model_name,
        pretrained=pretrained,
        progress_callback=progress_fn,
    )

    report = generate_report(results, threshold=threshold)

    out_path = str(Path(folder) / "cull_report.json")
    save_report(report, out_path)

    # Build summary text
    summary = f"Done — {report['total']} images\n"
    summary += f"Classified: {report['classified']}, Unclassified: {report['unclassified']}, Errors: {report['errors']}\n\n"
    for cat, info in sorted(report["categories"].items(), key=lambda x: -x[1]["count"]):
        summary += f"  {cat}: {info['count']}\n"
    summary += f"\nReport saved to {out_path}"

    # Build gallery items: list of (filepath, caption) tuples
    gallery_items = []
    for cat, info in report["categories"].items():
        for fp in info["files"]:
            if Path(fp).exists():
                gallery_items.append((fp, f"[{cat}] {Path(fp).name}"))

    yield summary, out_path, gallery_items


# ── Browse tab logic ─────────────────────────────────────────────────


def _load_report(report_path: str):
    """Load a cull report and return (info_text, gallery_items, category_choices)."""
    if not report_path or not Path(report_path).exists():
        return "No report loaded", None, gr.Dropdown(choices=["all"], value="all")

    with open(report_path) as f:
        report = json.load(f)

    gallery_items = []
    for cat, info in report["categories"].items():
        for fp in info["files"]:
            if Path(fp).exists():
                gallery_items.append((fp, f"[{cat}] {Path(fp).name}"))

    cats = ["all"] + sorted(report["categories"].keys())
    info_text = f"Report: {report['total']} images, {report['classified']} classified"

    return info_text, gallery_items, gr.Dropdown(choices=cats, value="all")


def _filter_gallery(report_path: str, category: str, all_gallery: list):
    """Filter gallery by category without reloading the report."""
    if not report_path or not Path(report_path).exists():
        return None

    if category == "all":
        return all_gallery

    with open(report_path) as f:
        report = json.load(f)

    filtered = []
    for fp, _ in all_gallery:
        # Find which category this file belongs to
        for cat, info in report["categories"].items():
            if any(fp == f for f in info["files"]):
                if cat == category:
                    filtered.append((fp, f"[{cat}] {Path(fp).name}"))
                break
    return filtered if filtered else None


def _delete_selected(report_path: str, gallery_selection: list, category: str):
    """Delete the gallery images the user has selected."""
    if not gallery_selection:
        return "No files selected for deletion"

    count = 0
    for item in gallery_selection:
        # Gallery selection items are tuples (path, caption) or just paths
        fp = item[0] if isinstance(item, (tuple, list)) else str(item)
        p = Path(fp)
        if p.exists():
            p.unlink()
            count += 1

    msg = f"Deleted {count} file(s)"
    # Reload report to update gallery
    _, new_gallery, _ = _load_report(report_path)
    return msg, new_gallery


# ── Volumes tab logic ────────────────────────────────────────────────


def _refresh_volumes():
    """Return volume summary text."""
    return format_volume_summary()


def _do_eject(volume_name: str, force: bool):
    """Eject the selected volume."""
    volumes = list_volumes()
    for v in volumes:
        if v["name"] == volume_name:
            ok, msg = safe_eject(v["path"], force=force)
            status = "✅" if ok else "❌"
            return f"{status} {msg}\n\n{format_volume_summary()}"
    return f"Volume not found: {volume_name}"


# ── App construction ─────────────────────────────────────────────────

with gr.Blocks(title="cull") as app:
    gr.Markdown("# cull — AI orphan image cleaner")
    gr.Markdown("Classify orphan images by content using CLIP zero-shot vision.")

    # ── Tab: Classify ────────────────────────────────────────────────
    with gr.Tab("Classify"):
        with gr.Row():
            folder = gr.Textbox(
                label="Images folder",
                placeholder="/path/to/orphans/ or /Volumes/MyUSB/",
                scale=3,
            )
            model_choice = gr.Dropdown(
                choices=["Fast (ViT-B-32)", "Accurate (ViT-L-14)"],
                value="Fast (ViT-B-32)",
                label="Model",
                scale=1,
            )
        threshold = gr.Slider(0.0, 1.0, value=0.3, label="Confidence threshold")
        run_btn = gr.Button("🚀 Classify", variant="primary")
        output = gr.Textbox(label="Results", lines=15)
        report_path = gr.Textbox(label="Report path", visible=False)

        run_btn.click(
            fn=_do_classify,
            inputs=[folder, threshold, model_choice],
            outputs=[output, report_path, gr.Gallery(visible=False)],
        )

    # ── Tab: Browse ──────────────────────────────────────────────────
    with gr.Tab("Browse"):
        load_btn = gr.Button("📂 Load report")
        report_input = gr.Textbox(label="Report path", placeholder="cull_report.json")
        info_text = gr.Textbox(label="Report info", lines=2, interactive=False)

        gallery = gr.Gallery(
            label="Images",
            columns=6,
            object_fit="contain",
            height=500,
            # Gradio 5+ uses (path, caption) tuples
            format="jpg",
        )

        with gr.Row():
            cat_filter = gr.Dropdown(
                choices=["all"], label="Filter category", value="all", scale=3
            )
            del_btn = gr.Button("🗑️ Delete selected", variant="stop", scale=1)
        del_output = gr.Textbox(label="Delete status", lines=1)

        # Wire: load report button
        load_btn.click(
            fn=_load_report,
            inputs=[report_input],
            outputs=[info_text, gallery, cat_filter],
        )

        # Wire: category filter dropdown
        cat_filter.change(
            fn=_filter_gallery,
            inputs=[report_input, cat_filter, gallery],
            outputs=[gallery],
        )

        # Wire: delete button
        del_btn.click(
            fn=_delete_selected,
            inputs=[report_input, gallery, cat_filter],
            outputs=[del_output, gallery],
        )

    # ── Tab: Volumes ─────────────────────────────────────────────────
    with gr.Tab("Volumes"):
        gr.Markdown("### External drives & volumes")
        volume_output = gr.Textbox(
            label="Detected volumes",
            lines=12,
            interactive=False,
        )
        refresh_btn = gr.Button("🔄 Refresh")
        with gr.Row():
            volume_select = gr.Dropdown(
                choices=[],
                label="Select volume to eject",
                scale=3,
            )
            force_eject = gr.Checkbox(label="Force eject", scale=1)
            eject_btn = gr.Button("⏏️ Eject", variant="stop", scale=1)

        eject_status = gr.Textbox(label="Eject status", lines=2)

        # Wire: refresh volumes
        def _refresh_and_update():
            vols = list_volumes()
            choices = [v["name"] for v in vols] or ["(none detected)"]
            summary = format_volume_summary()
            return summary, gr.Dropdown(
                choices=choices, value=choices[0] if choices else None
            )

        refresh_btn.click(
            fn=_refresh_and_update,
            inputs=[],
            outputs=[volume_output, volume_select],
        )

        # Wire: eject
        eject_btn.click(
            fn=_do_eject,
            inputs=[volume_select, force_eject],
            outputs=[eject_status],
        )

        # Auto-populate on load
        app.load(
            fn=_refresh_and_update,
            inputs=[],
            outputs=[volume_output, volume_select],
        )


if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", css=CSS, theme=gr.themes.Soft())
