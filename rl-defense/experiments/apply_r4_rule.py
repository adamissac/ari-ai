"""Apply the round-4 rule pre-registered in experiments/README.md to results/r4.json.

    python -m experiments.apply_r4_rule

Thresholds are copied verbatim from the pre-registration (reference: r3_1m_dr_nstep3_sel on
validation seeds 10-14). Prints a pass/fail table and the single winner, or "no winner".
"""

from __future__ import annotations

import json
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"
RULES = (  # (label, metric key in the ranking row, comparison, threshold)
    ("×1 false disruption ≤ 65.83%", "false_disruption_rate", "le", 0.6583),
    ("robust return ≥ −39.29", "robust_return", "ge", -39.29),
    ("×1 return ≥ −24.59", "return", "ge", -24.59),
    ("robust db loss ≤ 2.48%", "robust_db_loss_rate", "le", 0.0248),
    ("×1 compromise ≤ 13.50%", "compromise_rate", "le", 0.1350),
)


def check(row: dict) -> dict[str, bool]:
    out = {}
    for label, key, op, thr in RULES:
        v = row[key]
        out[label] = v <= thr if op == "le" else v >= thr
    return out


def main() -> None:
    rows = json.loads((RESULTS / "r4.json").read_text())["ranking"]
    winners = []
    print("| Candidate | " + " | ".join(r[0] for r in RULES) + " | Wins |")
    print("|---|" + "---|" * (len(RULES) + 1))
    for row in rows:
        res = check(row)
        win = all(res.values())
        if win:
            winners.append(row)
        cells = []
        for (_label, key, _op, _thr), ok in zip(RULES, res.values(), strict=True):
            v = row[key]
            shown = f"{100 * v:.1f}%" if "rate" in key else f"{v:.1f}"
            cells.append(f"{shown} {'✅' if ok else '❌'}")
        print(f"| {row['candidate']} | " + " | ".join(cells) + f" | {'**yes**' if win else 'no'} |")
    if not winners:
        print("\nNo candidate meets every pre-registered condition: v1 stays current.")
        return
    lead = max(winners, key=lambda r: r["robust_return"])
    close = [
        r
        for r in winners
        if r["robust_return"] >= lead["robust_return"] - lead["robust_return_std"]
    ]
    pick = min(close, key=lambda r: r["false_disruption_rate"])
    print(
        f"\nWinners: {[r['candidate'] for r in winners]}; leader {lead['candidate']}; "
        f"within one std: {[r['candidate'] for r in close]} -> WINNER: {pick['candidate']}"
    )


if __name__ == "__main__":
    main()
