"""Render completed-study JSON; plotting dependencies stay outside the training env."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib.ticker import FuncFormatter


def main() -> None:
    from matplotlib import pyplot as plt

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", type=Path)
    root = ap.parse_args().root
    data = json.loads((root / "figure_data.json").read_text())
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.titleweight": "bold",
            "axes.labelcolor": "#263746",
            "text.color": "#263746",
            "xtick.color": "#475569",
            "ytick.color": "#475569",
            "svg.fonttype": "none",
        }
    )
    fig, (left, right) = plt.subplots(
        1, 2, figsize=(12, 5.2), layout="constrained", gridspec_kw={"width_ratios": [1.2, 1]}
    )
    x = data["steps"]
    low = [ci[0] for ci in data["ci95"]]
    high = [ci[1] for ci in data["ci95"]]
    for values in data["by_training_seed"]:
        left.plot(x, values, color="#94a3b8", alpha=0.6, lw=0.9)
    left.fill_between(x, low, high, color="#2563eb", alpha=0.16, label="95% CI across five seeds")
    left.plot(x, data["mean"], color="#2563eb", lw=2, label="Mean validation score")
    left.scatter(
        [s["step"] for s in data["selected"]],
        [s["score"] for s in data["selected"]],
        s=35,
        c="#d97706",
        edgecolors="white",
        linewidths=0.6,
        zorder=5,
        label="Selected checkpoints",
    )
    left.set(
        title="Validation during training",
        xlabel="Online environment steps",
        ylabel="Validation selection score",
    )
    left.xaxis.set_major_formatter(
        FuncFormatter(lambda v, pos: "0" if v == 0 else f"{v / 1000:g}k")
    )
    left.grid(axis="y", color="#e2e8f0", lw=0.7)
    left.legend(frameon=False, fontsize=8, loc="lower left")
    paired = data["heldout_paired_return"]
    values = paired["by_training_seed"]
    right.axvline(0, color="#64748b", lw=1, ls="--")
    right.scatter(values, list(range(5)), s=45, c="#2563eb", zorder=3)
    mean = paired["mean"]
    lo, hi = paired["ci95"]
    right.errorbar(
        [mean],
        [6],
        xerr=[[mean - lo], [hi - mean]],
        fmt="o",
        color="#b45309",
        ecolor="#b45309",
        capsize=5,
        markersize=7,
        lw=2,
    )
    right.set_yticks(
        [0, 1, 2, 3, 4, 6],
        labels=["Seed 0", "Seed 1", "Seed 2", "Seed 3", "Seed 4", "All five: mean + 95% CI"],
    )
    right.invert_yaxis()
    right.margins(x=0.18, y=0.12)
    right.set(
        title="Held-out return against incumbent v6",
        xlabel="Paired mean return gain (candidate − v6)",
    )
    right.grid(axis="x", color="#e2e8f0", lw=0.7)
    fig.suptitle("V9: quiet-validation study · five training seeds", fontsize=14, fontweight="bold")
    fig.supxlabel(
        "Owned, isolated payments-lite lab. Validation is used for selection; right panel uses fresh held-out episodes.\nIntervals use 10,000 resamples of five seed means. Does not establish real-world effectiveness.",
        fontsize=8,
        color="#64748b",
    )
    fig.savefig(root / "study_figure.png", dpi=220, facecolor="white")
    fig.savefig(root / "study_figure.svg", facecolor="white")
    plt.close(fig)
    (root / "plot_runtime.json").write_text(
        json.dumps(
            {
                "matplotlib": matplotlib.__version__,
                "note": "Rendering only; primary statistics and figure_data.json computed in the frozen training environment.",
            },
            indent=2,
        )
    )
    print("Scientific comparison figure rendered from saved statistics only.")


if __name__ == "__main__":
    main()
