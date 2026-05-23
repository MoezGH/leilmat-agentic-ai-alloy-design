"""
Shared utilities for case study scripts: literature comparison, CSV/JSON writers,
matplotlib figure generators.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

# Make `apps.api.ml.*` importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def predict_for_literature(alloys: dict[str, dict[str, float]]) -> dict[str, dict[str, Any]]:
    """Predict properties for a dict of {name: composition_dict}."""
    from apps.api.ml.matgl_models import predict_properties
    out = {}
    for name, comp in alloys.items():
        props = predict_properties(comp)
        out[name] = props
    return out


def save_candidates_csv(candidates: list[Any], path: Path, property_keys: list[str]) -> None:
    rows = []
    for c in candidates:
        row = {
            "rank": c.pareto_rank,
            "is_pareto": c.is_pareto,
            "score": round(c.score, 3),
            "composition": " ".join(f"{el}{round(v,1)}" for el, v in c.composition.items() if v > 0.05),
        }
        for k in property_keys:
            row[k] = c.properties.get(k)
        rows.append(row)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def save_summary_json(data: dict, path: Path) -> None:
    def serializable(x):
        if hasattr(x, "__dict__"):
            return x.__dict__
        return str(x)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=serializable)


def compare_table(name: str, predicted: dict, literature: dict, keys: list[str]) -> dict[str, Any]:
    """Build a row of {alloy, pred, lit, delta_pct} for each property key."""
    out = {"alloy": name, "literature": literature}
    for k in keys:
        p = predicted.get(k)
        L = literature.get(k)
        delta_pct = None
        if p is not None and L is not None and L != 0:
            delta_pct = round(100 * (p - L) / L, 1)
        out[f"predicted_{k}"] = p
        out[f"delta_{k}_pct"] = delta_pct
    return out


# ─────────────────────────────────────────────────────────────────────────
# Matplotlib figures (dark theme, no UI dependencies)
# ─────────────────────────────────────────────────────────────────────────

def _dark_axes(ax):
    ax.set_facecolor("#0c0e13")
    ax.tick_params(colors="#94a3b8", labelsize=9)
    for spine in ax.spines.values():
        spine.set_color("#334155")
    ax.grid(True, color="#1e293b", linewidth=0.5)


def plot_pareto_scatter(
    candidates: list[Any],
    x_key: str, y_key: str,
    x_label: str, y_label: str,
    literature: dict[str, dict[str, Any]] | None,
    path: Path,
    title: str,
) -> None:
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 5.5), facecolor="#0a0b0f")
    _dark_axes(ax)

    pareto = [c for c in candidates if c.is_pareto]
    dom    = [c for c in candidates if not c.is_pareto]

    if dom:
        ax.scatter([c.properties.get(x_key) for c in dom],
                   [c.properties.get(y_key) for c in dom],
                   s=20, color="#94a3b8", alpha=0.4, label=f"dominated ({len(dom)})")
    if pareto:
        ps = sorted(pareto, key=lambda c: c.properties.get(x_key, 0) or 0)
        ax.plot([c.properties.get(x_key) for c in ps],
                [c.properties.get(y_key) for c in ps],
                color="#38bdf8", linewidth=1.0, alpha=0.5, linestyle=":")
        ax.scatter([c.properties.get(x_key) for c in pareto],
                   [c.properties.get(y_key) for c in pareto],
                   s=110, marker="h", c=[c.score for c in pareto], cmap="viridis",
                   edgecolor="#38bdf8", linewidth=1.0, label=f"Pareto ({len(pareto)})", zorder=3)

    if literature:
        for name, props in literature.items():
            x = props.get(x_key)
            y = props.get(y_key)
            if x is None or y is None: continue
            ax.scatter([x], [y], s=170, marker="*", c="#facc15", edgecolor="#000", linewidth=0.7, zorder=5)
            ax.annotate(name, (x, y), xytext=(7, 7), textcoords="offset points",
                        fontsize=9, color="#facc15", fontweight="bold")

    ax.set_xlabel(x_label, color="#cbd5e1", fontsize=10)
    ax.set_ylabel(y_label, color="#cbd5e1", fontsize=10)
    ax.set_title(title, color="#f1f5f9", fontsize=12, fontweight="bold")
    leg = ax.legend(loc="best", facecolor="#15171d", edgecolor="#334155", labelcolor="#cbd5e1", fontsize=9)
    for text in leg.get_texts(): text.set_color("#cbd5e1")
    fig.tight_layout()
    fig.savefig(path, dpi=110, facecolor="#0a0b0f")
    plt.close(fig)


def plot_property_bars(
    bars: list[dict],         # [{"label": "Ti-6-4 ELI", "predicted": 800, "literature": 795}, ...]
    property_label: str,
    path: Path,
    title: str,
) -> None:
    """Side-by-side predicted vs literature bar chart."""
    import matplotlib.pyplot as plt
    import numpy as np

    labels = [b["label"] for b in bars]
    pred   = [b.get("predicted") or 0 for b in bars]
    lit    = [b.get("literature") or 0 for b in bars]

    x = np.arange(len(labels))
    w = 0.38

    fig, ax = plt.subplots(figsize=(9, 5), facecolor="#0a0b0f")
    _dark_axes(ax)
    ax.bar(x - w/2, pred, w, label="LeilMat predicted", color="#38bdf8", edgecolor="#0ea5e9", linewidth=0.7)
    ax.bar(x + w/2, lit,  w, label="Literature",        color="#facc15", edgecolor="#ca8a04", linewidth=0.7)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, color="#cbd5e1", fontsize=9, rotation=15, ha="right")
    ax.set_ylabel(property_label, color="#cbd5e1", fontsize=10)
    ax.set_title(title, color="#f1f5f9", fontsize=12, fontweight="bold")
    leg = ax.legend(loc="best", facecolor="#15171d", edgecolor="#334155", fontsize=9)
    for text in leg.get_texts(): text.set_color("#cbd5e1")
    fig.tight_layout()
    fig.savefig(path, dpi=110, facecolor="#0a0b0f")
    plt.close(fig)


def plot_radar_comparison(
    series: list[dict],              # [{"label": "...", "values": {k: v, ...}, "color": "#xxx"}, ...]
    property_keys: list[str],
    property_labels: list[str],
    path: Path,
    title: str,
) -> None:
    """Radar chart overlaying multiple alloys."""
    import matplotlib.pyplot as plt
    import numpy as np

    # Normalise each axis 0-1 to the max value seen across all series
    n = len(property_keys)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    angles += angles[:1]

    maxes = []
    for k in property_keys:
        vals = [s["values"].get(k) for s in series if s["values"].get(k) is not None]
        maxes.append(max(vals) if vals else 1.0)

    fig = plt.figure(figsize=(7, 7), facecolor="#0a0b0f")
    ax = plt.subplot(111, polar=True)
    ax.set_facecolor("#0c0e13")
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(property_labels, color="#cbd5e1", fontsize=9)
    ax.tick_params(colors="#64748b")
    ax.grid(color="#1e293b")

    for s in series:
        normalised = []
        for k, m in zip(property_keys, maxes):
            v = s["values"].get(k)
            normalised.append((v or 0) / m if m > 0 else 0)
        normalised += normalised[:1]
        ax.plot(angles, normalised, color=s["color"], linewidth=2.0, label=s["label"])
        ax.fill(angles, normalised, color=s["color"], alpha=0.12)

    ax.set_title(title, color="#f1f5f9", fontsize=12, pad=20, fontweight="bold")
    leg = ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.05), facecolor="#15171d", edgecolor="#334155", fontsize=9)
    for text in leg.get_texts(): text.set_color("#cbd5e1")
    fig.tight_layout()
    fig.savefig(path, dpi=110, facecolor="#0a0b0f")
    plt.close(fig)
