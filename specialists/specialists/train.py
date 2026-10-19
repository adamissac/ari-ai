"""Train, evaluate and checkpoint the specialist models.

    uv run --extra train python -m specialists.train            # all seven
    uv run --extra train python -m specialists.train scout probe

For each agent: build the dataset (deterministic), train on ``train`` with early stopping on
``val``, write the checkpoint, reload it through the pure-Python inference path, and score that
reloaded artifact and every baseline on the held-out ``test`` split. Results go to
``specialists/results/<agent>.json`` and the summary table to ``specialists/results/REPORT.md``.
"""

from __future__ import annotations

import json
import platform
import sys
import time
from pathlib import Path
from typing import Any

from .data.datasets import BUILDERS, CORPUS_TASKS, DATASET_VERSION, bundled_digest, digest
from .metrics import detection, label_counts, ranked, single_label
from .model import CHECKPOINT_ROOT, SpecialistModel, write_checkpoint
from .tasks import TASKS, Task

RESULTS = Path(__file__).resolve().parent.parent / "results"
VERSION = "1.1.0"


def _score(task: Task, labels: list[str], gold: list[Any], pred: list[Any]) -> dict[str, Any]:
    if task.multilabel:
        return ranked(gold, pred, task.top_k)
    out = single_label(gold, pred, labels)
    if task.agent == "scout":
        out["detection"] = detection(gold, pred)
    return out


def _bootstrap_delta(
    task: Task, labels: list[str], gold: list[Any], a: list[Any], b: list[Any], n: int = 1000
) -> tuple[float, float]:
    """Paired bootstrap 95% interval of (model - baseline) on the primary metric (seeded)."""
    import random

    rng = random.Random(11)
    deltas = []
    for _ in range(n):
        idx = [rng.randrange(len(gold)) for _ in gold]
        g = [gold[i] for i in idx]
        deltas.append(
            _score(task, labels, g, [a[i] for i in idx])[task.primary_metric]
            - _score(task, labels, g, [b[i] for i in idx])[task.primary_metric]
        )
    deltas.sort()
    return round(deltas[int(0.025 * n)], 4), round(deltas[int(0.975 * n) - 1], 4)


def _fallback(agent: str, train_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The deterministic lookup the runtime uses if this model is not promoted."""
    from collections import Counter, defaultdict

    from .data.datasets import PROBE_CWE_TO_STRATEGY

    if agent == "probe":
        top = Counter(r["label"] for r in train_rows).most_common(1)[0][0]
        return {
            "name": "cwe_lookup",
            "key": "cwe",
            "table": dict(PROBE_CWE_TO_STRATEGY),
            "default": top,
        }
    if agent == "trace":
        top = [
            label
            for label, _ in Counter(lab for r in train_rows for lab in r["label"]).most_common(3)
        ]
        return {"name": "prior_top3", "key": "", "table": {}, "default": top}
    if agent == "fortify":
        by: dict[str, Counter] = defaultdict(Counter)
        for r in train_rows:
            for t in r["tactics"].split():
                by[t].update(r["label"])
        prior = [
            label
            for label, _ in Counter(lab for r in train_rows for lab in r["label"]).most_common(5)
        ]
        return {
            "name": "tactic_frequency",
            "key": "tactics",
            "table": {t: [x for x, _ in c.most_common(5)] for t, c in sorted(by.items())},
            "default": prior,
        }
    if agent in ("diagnose", "patch"):
        table: dict[str, Counter] = defaultdict(Counter)
        for r in train_rows:
            table[r["cwe"]][r["label"]] += 1
        top = Counter(r["label"] for r in train_rows).most_common(1)[0][0]
        return {
            "name": "cwe_lookup",
            "key": "cwe",
            "table": {c: n.most_common(1)[0][0] for c, n in sorted(table.items())},
            "default": top,
        }
    return None


def _family_cv(task: Task, labels: list[str]) -> dict[str, Any]:
    """Leave-one-family-out: each of the four families per class is the unseen test set once."""
    from .trainer import matrix, predict_proba, targets, train

    folds: list[dict[str, Any]] = []
    for fold in range(4):
        data = BUILDERS[task.agent](test_family=fold)
        tr, va, te = data["train"], data["val"], data["test"]
        x, xv, xt = (
            matrix(rows, task.fields, task.config.input_dim, char_ngrams=task.char_ngrams)
            for rows in (tr, va, te)
        )
        y, yv = (targets([r["label"] for r in rows], labels, False) for rows in (tr, va))
        net, _ = train(x, y, xv, yv, multilabel=False, cfg=task.config)
        pred = [labels[i] for i in predict_proba(net, xt, False).argmax(axis=1)]
        gold = [r["label"] for r in te]
        row: dict[str, Any] = {
            "test_family": fold,
            "model": _score(task, labels, gold, pred)[task.primary_metric],
        }
        for name, fit in task.baselines.items():
            predict = fit(tr)
            row[name] = _score(task, labels, gold, [predict(r) for r in te])[task.primary_metric]
        folds.append(row)
    names = ["model", *task.baselines]
    mean = {n: round(sum(f[n] for f in folds) / len(folds), 4) for n in names}
    return {"metric": task.primary_metric, "folds": folds, "mean": mean}


def run(agent: str) -> dict[str, Any]:
    import numpy as np

    from .trainer import matrix, predict_proba, targets, train

    task = TASKS[agent]
    data = BUILDERS[agent]()
    train_rows, val_rows, test_rows = data["train"], data["val"], data["test"]
    if task.multilabel:
        labels = sorted({lab for split in data.values() for r in split for lab in r["label"]})
    else:
        labels = sorted({r["label"] for split in data.values() for r in split})
    dim = task.config.input_dim
    x, xv = (
        matrix(rows, task.fields, dim, char_ngrams=task.char_ngrams)
        for rows in (train_rows, val_rows)
    )
    y, yv = (
        targets([r["label"] for r in rows], labels, task.multilabel)
        for rows in (train_rows, val_rows)
    )

    started = time.perf_counter()
    net, log = train(x, y, xv, yv, multilabel=task.multilabel, cfg=task.config)
    train_seconds = round(time.perf_counter() - started, 2)

    # Multi-label decision: top-k (k fixed per task). Single-label: argmax.
    manifest = {
        "model_id": task.model_id,
        "agent": agent,
        "version": VERSION,
        "description": task.description,
        "task": {"type": "multilabel" if task.multilabel else "multiclass", "top_k": task.top_k},
        "labels": labels,
        "features": {
            "fields": task.fields,
            "char_ngrams": task.char_ngrams,
            "hashing": "crc32 signed, log-count, L2",
            "input_dim": dim,
        },
        "architecture": {
            "input_dim": dim,
            "hidden": task.config.hidden,
            "type": "mlp-relu" if task.config.hidden else "linear",
            "output": "sigmoid" if task.multilabel else "softmax",
        },
        "dataset": {
            "version": DATASET_VERSION,
            "sha256": digest(data),
            "bundled_sha256": bundled_digest(data),
            "real_rows": sum(1 for rows in data.values() for r in rows if r.get("src") == "real"),
            "sizes": {k: len(v) for k, v in data.items()},
            "train_label_counts": label_counts(train_rows, task.multilabel),
        },
        "training": {
            **task.config.to_json(),
            **{k: v for k, v in log.items() if k != "history"},
            "seconds": train_seconds,
            "numpy": np.__version__,
            "python": platform.python_version(),
        },
    }
    ckpt = CHECKPOINT_ROOT / f"{agent}"
    write_checkpoint(ckpt, manifest, net.flat())

    # Score the shipped artifact through the production inference path, not the numpy net.
    model = SpecialistModel.load(ckpt)
    t0 = time.perf_counter()
    if task.multilabel:
        model_pred = [[p.label for p in model.predict(r, top_k=task.top_k)] for r in test_rows]
    else:
        model_pred = [model.predict(r, top_k=1)[0].label for r in test_rows]
    latency_ms = round((time.perf_counter() - t0) * 1000 / max(1, len(test_rows)), 3)
    # Cross-check the pure-Python path against numpy on the test set (same argmax).
    xt = matrix(test_rows, task.fields, dim, char_ngrams=task.char_ngrams)
    np_top = predict_proba(net, xt, task.multilabel).argmax(axis=1)
    py_top = [labels.index(model.predict(r, top_k=1)[0].label) for r in test_rows]
    parity = float(np.mean(np_top == np.array(py_top)))

    gold = [r["label"] for r in test_rows]
    results: dict[str, Any] = {
        "agent": agent,
        "model": model.model_id,
        "primary_metric": task.primary_metric,
        "test_split": "held out by family"
        if agent not in ("trace", "fortify")
        else "held out by CWE / ATT&CK parent technique",
        "model_scores": _score(task, labels, gold, model_pred),
        "baselines": {},
        "inference": {
            "mean_latency_ms_pure_python": latency_ms,
            "llm_tokens": 0,
            "usd": 0.0,
            "numpy_parity_argmax": round(parity, 4),
        },
        "training_history": log["history"],
    }
    for name, fit in task.baselines.items():
        predict = fit(train_rows)
        results["baselines"][name] = _score(task, labels, gold, [predict(r) for r in test_rows])
    if agent in CORPUS_TASKS:
        results["cross_validation"] = _family_cv(task, labels)
    best_name, best = max(results["baselines"].items(), key=lambda kv: kv[1][task.primary_metric])
    mine = results["model_scores"][task.primary_metric]
    base_pred = [task.baselines[best_name](train_rows)(r) for r in test_rows]
    lo, hi = _bootstrap_delta(task, labels, gold, model_pred, base_pred)
    results["comparison"] = {
        "model": mine,
        "best_baseline": best_name,
        "best_baseline_score": best[task.primary_metric],
        "delta": round(mine - best[task.primary_metric], 4),
        "delta_ci95": [lo, hi],
        "significant": lo > 0 or hi < 0,
    }
    # Promote only on evidence: the paired-bootstrap 95% interval of the gain must exclude zero.
    results["promoted"] = lo > 0
    # Record the outcome in the manifest so the runtime can refuse an unpromoted model.
    manifest_path = ckpt / "manifest.json"
    final = json.loads(manifest_path.read_text())
    fallback = _fallback(agent, train_rows)
    if fallback:
        final["fallback"] = fallback
    final["evaluation"] = {
        "primary_metric": task.primary_metric,
        "test": mine,
        "best_baseline": best_name,
        "best_baseline_test": best[task.primary_metric],
        "promoted": results["promoted"],
    }
    manifest_path.write_text(json.dumps(final, indent=1, sort_keys=True) + "\n")
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"{agent}.json").write_text(json.dumps(results, indent=1, sort_keys=True) + "\n")
    return results


def report(all_results: dict[str, dict[str, Any]]) -> str:
    lines = [
        "| Agent | Model | Metric (test) | Model | Best baseline | Baseline score | Δ | Δ 95% CI | Promoted |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for agent, r in all_results.items():
        c = r["comparison"]
        lines.append(
            f"| {agent} | `{r['model']}` | {r['primary_metric']} | {c['model']:.3f} | {c['best_baseline']} | {c['best_baseline_score']:.3f} | {c['delta']:+.3f} | [{c['delta_ci95'][0]:+.3f}, {c['delta_ci95'][1]:+.3f}]{' (significant)' if c['significant'] else ''} | {'yes' if r['promoted'] else 'no'} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    agents = argv or list(TASKS)
    done: dict[str, dict[str, Any]] = {}
    for agent in agents:
        r = run(agent)
        done[agent] = r
        c = r["comparison"]
        print(
            f"{agent:9s} {r['primary_metric']:9s} model={c['model']:.3f} best_baseline({c['best_baseline']})={c['best_baseline_score']:.3f} ci95={c['delta_ci95']} promoted={r['promoted']}",
            flush=True,
        )
    existing = {
        a: json.loads((RESULTS / f"{a}.json").read_text())
        for a in TASKS
        if (RESULTS / f"{a}.json").exists()
    }
    (RESULTS / "REPORT.md").write_text(report({a: existing[a] for a in TASKS if a in existing}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
