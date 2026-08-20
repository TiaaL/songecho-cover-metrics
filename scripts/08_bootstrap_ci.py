#!/usr/bin/env python3
"""Paired bootstrap CIs for rule-vs-baseline diagnostic deltas."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
from typing import Callable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score


SCRIPT_DIR = Path(__file__).resolve().parent
RULE_DIAGNOSTIC_PATH = SCRIPT_DIR / "07_rule_diagnostic.py"


def load_rule_diagnostic():
    spec = importlib.util.spec_from_file_location("rule_diagnostic", RULE_DIAGNOSTIC_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import {RULE_DIAGNOSTIC_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--annotations", type=Path, default=Path("data/annotations/evaluation_scores.csv"))
    parser.add_argument("--features", type=Path, default=Path("features/extracted_features.csv"))
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help=(
            "Redirect all outputs into this directory using their standard file names, "
            "so runs on your own data do not overwrite the published paper artifacts. "
            "Any explicit --output-csv/--output-png/--output-pdf still takes precedence."
        ),
    )
    parser.add_argument("--output-csv", type=Path, default=None)
    parser.add_argument("--output-png", type=Path, default=None)
    parser.add_argument("--output-pdf", type=Path, default=None)
    parser.add_argument("--n-boot", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=20260709)
    return parser.parse_args()


def weighted_f1(y_true: pd.Series | np.ndarray, y_pred: pd.Series | np.ndarray, labels: list[int]) -> float:
    return float(f1_score(y_true, y_pred, labels=labels, average="weighted", zero_division=0))


def weighted_f1_np(y_true: np.ndarray, y_pred: np.ndarray, labels: list[int]) -> float:
    total = len(y_true)
    if total == 0:
        return 0.0

    weighted = 0.0
    for label in labels:
        true_mask = y_true == label
        pred_mask = y_pred == label
        support = int(true_mask.sum())
        tp = int((true_mask & pred_mask).sum())
        fp = int((~true_mask & pred_mask).sum())
        fn = int((true_mask & ~pred_mask).sum())
        denom = (2 * tp) + fp + fn
        f1 = 0.0 if denom == 0 else (2 * tp) / denom
        weighted += support * f1
    return weighted / total


def score_values(part: pd.DataFrame, score_fn: Callable[[pd.Series, pd.Series], float]) -> tuple[float, float, float]:
    rule = score_fn(part["true"], part["pred"])
    baseline = score_fn(part["true"], part["baseline_pred"])
    return rule, baseline, rule - baseline


def bootstrap_indices(
    part: pd.DataFrame,
    rng: np.random.Generator,
    dimension: str,
    grouped_indices: list[np.ndarray] | None = None,
) -> np.ndarray:
    if dimension != "overall":
        return rng.integers(0, len(part), size=len(part))

    if grouped_indices is None:
        raise ValueError("Overall bootstrap requires precomputed grouped indices.")
    sampled = rng.integers(0, len(grouped_indices), size=len(grouped_indices))
    return np.concatenate([grouped_indices[idx] for idx in sampled])


def bootstrap_delta(
    part: pd.DataFrame,
    metric: str,
    labels: list[int],
    rng: np.random.Generator,
    n_boot: int,
    dimension: str,
) -> np.ndarray:
    local = part.reset_index(drop=True)
    true = local["true"].to_numpy()
    pred = local["pred"].to_numpy()
    baseline = local["baseline_pred"].to_numpy()
    grouped_indices = None
    if dimension == "overall":
        sample_keys = local["sample_key"].drop_duplicates().to_numpy()
        grouped_indices = [local.index[local["sample_key"] == key].to_numpy() for key in sample_keys]

    deltas = np.empty(n_boot, dtype=float)
    for idx in range(n_boot):
        sampled_idx = bootstrap_indices(local, rng, dimension, grouped_indices)
        sampled_true = true[sampled_idx]
        if metric == "accuracy":
            rule = float(np.mean(sampled_true == pred[sampled_idx]))
            baseline_score = float(np.mean(sampled_true == baseline[sampled_idx]))
        else:
            rule = weighted_f1_np(sampled_true, pred[sampled_idx], labels)
            baseline_score = weighted_f1_np(sampled_true, baseline[sampled_idx], labels)
        deltas[idx] = rule - baseline_score
    return deltas


def add_sample_key(loo: pd.DataFrame) -> pd.DataFrame:
    out = loo.copy()
    out["sample_key"] = out["filename"]
    return out


def use_fixed_full_sample_baseline(loo: pd.DataFrame) -> pd.DataFrame:
    out = loo.copy()
    for dimension in out["dimension"].drop_duplicates():
        mask = out["dimension"] == dimension
        counts = out.loc[mask, "true"].value_counts().sort_index()
        mode = int(counts[counts == counts.max()].index[0])
        out.loc[mask, "baseline_pred"] = mode
    return out


def paired_slice(loo: pd.DataFrame, dimension: str) -> pd.DataFrame:
    if dimension == "overall":
        return loo.copy()
    return loo[loo["dimension"] == dimension].copy()


def build_rows(
    loo: pd.DataFrame,
    setting: str,
    labels: list[int],
    dimensions: list[str],
    rng: np.random.Generator,
    n_boot: int,
) -> list[dict[str, float | str]]:
    rows = []
    metric_fns: list[tuple[str, Callable[[pd.Series, pd.Series], float]]] = [
        ("accuracy", lambda true, pred: float(accuracy_score(true, pred))),
        ("weighted_f1", lambda true, pred: weighted_f1(true, pred, labels)),
    ]
    for dimension in dimensions + ["overall"]:
        part = paired_slice(loo, dimension)
        for metric, score_fn in metric_fns:
            rule, baseline, delta = score_values(part, score_fn)
            deltas = bootstrap_delta(part, metric, labels, rng, n_boot, dimension)
            rows.append(
                {
                    "dimension": dimension,
                    "setting": setting,
                    "metric": metric,
                    "rule_score": rule,
                    "baseline_score": baseline,
                    "delta": delta,
                    "CI_low": float(np.percentile(deltas, 2.5)),
                    "CI_high": float(np.percentile(deltas, 97.5)),
                }
            )
    return rows


def save_forest_plot(results: pd.DataFrame, output_png: Path, output_pdf: Path) -> None:
    output_png.parent.mkdir(parents=True, exist_ok=True)
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    display = results[results["dimension"] != "overall"].sort_values(["setting", "metric", "dimension"]).reset_index(drop=True)
    labels = [
        f"{row.setting} | {'weighted F1' if row.metric == 'weighted_f1' else row.metric} | {row.dimension}"
        for row in display.itertuples(index=False)
    ]
    y_pos = np.arange(len(display))

    fig_height = max(5.0, 0.36 * len(display))
    fig, ax = plt.subplots(figsize=(8.4, fig_height))
    ax.axvline(0, color="black", linewidth=1)
    ax.axhline(7.5, color="#c7c7c7", linewidth=1)
    ax.errorbar(
        display["delta"],
        y_pos,
        xerr=[display["delta"] - display["CI_low"], display["CI_high"] - display["delta"]],
        fmt="o",
        color="#1f77b4",
        ecolor="#555555",
        elinewidth=1.2,
        capsize=3,
    )
    ax.set_yticks(y_pos, labels=labels)
    ax.invert_yaxis()
    ax.set_xlabel("Δ (rule - majority baseline)")
    ax.set_title("Paired bootstrap diagnostic deltas")
    fig.tight_layout()
    fig.savefig(output_png, dpi=220)
    fig.savefig(output_pdf)
    plt.close(fig)


def print_summary(results: pd.DataFrame, n_boot: int, seed: int) -> None:
    display = results.copy()
    for column in ("rule_score", "baseline_score", "delta", "CI_low", "CI_high"):
        display[column] = display[column].map("{:.3f}".format)
    print(f"\nPaired bootstrap CI summary ({n_boot} repeats, seed={seed})")
    print(display.to_string(index=False))
    print("\nBaseline predictions are fixed full-sample majority predictions; the majority class is not recomputed inside bootstrap resamples.")


def resolve_outputs(args: argparse.Namespace) -> None:
    """Fill in output paths: explicit flag > --out-dir > published default location."""
    defaults = {
        "output_csv": "bootstrap_ci.csv",
        "output_png": "bootstrap_delta.png",
        "output_pdf": "bootstrap_delta.pdf",
    }
    for attr, basename in defaults.items():
        if getattr(args, attr) is not None:
            continue
        parent = args.out_dir if args.out_dir is not None else Path("figures")
        setattr(args, attr, parent / basename)


def main() -> int:
    args = parse_args()
    resolve_outputs(args)
    rule_diagnostic = load_rule_diagnostic()
    df = rule_diagnostic.load_dataset(args.annotations, args.features)
    loo, _ = rule_diagnostic.run_loo(df)
    binary_loo, _ = rule_diagnostic.run_loo(df, binary=True)

    rng = np.random.default_rng(args.seed)
    rows = []
    rows.extend(
        build_rows(
            use_fixed_full_sample_baseline(add_sample_key(loo)),
            "3-class",
            rule_diagnostic.SEVERITY_LABELS,
            rule_diagnostic.DIAGNOSTIC_DIMENSIONS,
            rng,
            args.n_boot,
        )
    )
    rows.extend(
        build_rows(
            use_fixed_full_sample_baseline(add_sample_key(binary_loo)),
            "binary",
            rule_diagnostic.BINARY_LABELS,
            rule_diagnostic.DIAGNOSTIC_DIMENSIONS,
            rng,
            args.n_boot,
        )
    )

    results = pd.DataFrame(rows)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(args.output_csv, index=False)
    save_forest_plot(results, args.output_png, args.output_pdf)
    print_summary(results, args.n_boot, args.seed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
