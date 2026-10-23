"""Render the completed v10 summary without executing any policy."""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    root = parser.parse_args().root
    summary = json.loads((root / "study_summary.json").read_text())
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 5.4), layout="constrained")
    contrast = summary["balanced_minus_uniform"]["reward"]
    left.axvline(0, color="#64748b", ls="--", lw=1)
    left.scatter(contrast["by_training_seed"], range(5), color="#2563eb", s=45)
    mean, (lo, hi) = contrast["mean"], contrast["ci95"]
    left.errorbar(mean, 6, xerr=[[mean - lo], [hi - mean]], fmt="o", capsize=5, color="#b45309")
    left.set_yticks([0, 1, 2, 3, 4, 6], [f"Seed {i}" for i in range(5)] + ["Mean + 95% CI"])
    left.invert_yaxis()
    left.set(title="Balanced minus uniform return", xlabel="Paired mean return difference")
    left.grid(axis="x", alpha=0.2)
    metrics = ["compromise_rate", "availability", "false_disruption"]
    for offset, (arm, policy, label, color) in enumerate(
        [
            ("uniform", "deployed", "v6 incumbent", "#64748b"),
            ("uniform", "candidate", "Uniform", "#2563eb"),
            ("balanced", "candidate", "Balanced", "#b45309"),
        ]
    ):
        values = summary["arms"][arm]["policies"][policy]
        right.bar(
            [i + (offset - 1) * 0.24 for i in range(3)],
            [100 * values[m]["mean"] for m in metrics],
            width=0.24,
            label=label,
            color=color,
        )
    right.set_xticks(
        range(3),
        ["Compromised\nattack requests", "Benign\navailability", "Quiet false\ndisruption"],
    )
    right.set(title="Safety tradeoffs across held-out episodes", ylabel="Percent", ylim=(0, 100))
    right.legend(frameon=False, fontsize=8)
    right.grid(axis="y", alpha=0.2)
    fig.suptitle("V10: all ten candidates rejected; primary hypothesis unsupported", fontsize=13)
    fig.supxlabel(
        "Five paired training seeds; 10,000 bootstrap resamples. Return Holm p=0.0895.\nOwned payments-lite lab only; no real-world effectiveness claim. V6 remains deployed.",
        fontsize=9,
    )
    fig.savefig(root / "study_figure.png", dpi=200, facecolor="white")
    fig.savefig(root / "study_figure.svg", facecolor="white")
    plt.close(fig)
    (root / "plot_runtime.json").write_text(
        json.dumps(
            {
                "matplotlib": matplotlib.__version__,
                "scope": "Saved statistics rendering only; no policy execution.",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
