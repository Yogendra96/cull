import json
from pathlib import Path
from collections import Counter, defaultdict
from typing import Optional


def generate_report(results: list[dict], threshold: float = 0.3) -> dict:
    by_category = defaultdict(list)
    errors = []

    for r in results:
        if "error" in r:
            errors.append(r)
            continue
        top = r["scores"][0]
        if top["score"] >= threshold:
            by_category[top["category"]].append(r)
        else:
            by_category["unclassified"].append(r)

    total = len(results)
    classified = sum(len(v) for k, v in by_category.items() if k != "unclassified")
    unclassified = len(by_category.get("unclassified", []))

    summary = {}
    for cat, items in sorted(by_category.items(), key=lambda x: -len(x[1])):
        summary[cat] = {
            "count": len(items),
            "files": [r["path"] for r in items],
        }

    return {
        "total": total,
        "classified": classified,
        "unclassified": unclassified,
        "errors": len(errors),
        "categories": summary,
    }


def print_summary(report: dict) -> None:
    from rich.console import Console
    from rich.table import Table

    console = Console()
    console.print(f"\n[bold]Results:[/bold] {report['total']} files")
    console.print(f"  Classified:   [green]{report['classified']}[/green]")
    console.print(f"  Unclassified: [yellow]{report['unclassified']}[/yellow]")
    console.print(f"  Errors:       [red]{report['errors']}[/red]\n")

    table = Table(show_header=True)
    table.add_column("Category", style="cyan")
    table.add_column("Count", justify="right")
    table.add_column("%", justify="right")

    for cat, info in sorted(
        report["categories"].items(), key=lambda x: -x[1]["count"]
    ):
        pct = info["count"] / max(report["total"], 1) * 100
        table.add_row(cat, str(info["count"]), f"{pct:.1f}")

    console.print(table)
    console.print()


def save_report(report: dict, path: str) -> None:
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
