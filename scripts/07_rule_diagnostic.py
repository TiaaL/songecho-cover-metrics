#!/usr/bin/env python3
"""Learn rule-based diagnostic thresholds and validate them with LOO."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score


METRIC_RULES = [
    {"dimension": "D1", "metric": "LLR", "direction": "negative"},
    {"dimension": "D1", "metric": "PS", "direction": "negative"},
    {"dimension": "D2", "metric": "IKNR", "direction": "positive"},
    {"dimension": "D3", "metric": "IKNR", "direction": "positive"},
    {"dimension": "D3", "metric": "KC", "direction": "positive"},
    {"dimension": "D3", "metric": "KCR", "direction": "negative"},
    {"dimension": "D5", "metric": "LUFS_dev", "direction": "negative"},
    {"dimension": "D5", "metric": "LRA", "direction": "positive"},
    {"dimension": "D5", "metric": "SC", "direction": "positive"},
]
DIAGNOSTIC_DIMENSIONS = ["D1", "D2", "D3", "D5"]
SEVERITY_LABELS = [0, 1, 2]
BINARY_LABELS = [0, 1]


def score_to_severity(score: float | int) -> int:
    """Aggregate expert 5-point scores into 0/1/2 diagnostic severity."""
    if score in (4, 5):
        return 0
    if score == 3:
        return 1
    if score in (1, 2):
        return 2
    raise ValueError(f"Unsupported expert score: {score!r}")


def severity_to_binary(severity: int) -> int:
    """Collapse severity into acceptable/non-severe (0) vs severe (1)."""
    return 1 if severity == 2 else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--annotations", type=Path, default=Path("data/annotations/evaluation_scores.csv"))
    parser.add_argument("--features", type=Path, default=Path("features/extracted_features.csv"))
    parser.add_argument("--thresholds-json", type=Path, default=Path("features/diagnostic_thresholds.json"))
    parser.add_argument("--summary-csv", type=Path, default=Path("figures/loo_accuracy_summary.csv"))
    parser.add_argument("--confusion-png", type=Path, default=Path("figures/loo_confusion_matrix.png"))
    parser.add_argument("--binary-summary-csv", type=Path, default=Path("figures/loo_binary_accuracy_summary.csv"))
    parser.add_argument("--binary-confusion-png", type=Path, default=Path("figures/loo_binary_confusion_matrix.png"))
    parser.add_argument(
        "--diagnose-json",
        type=Path,
        help="Optional JSON file containing one cover feature vector to diagnose with all-data thresholds.",
    )
    return parser.parse_args()


def load_features(features_path: Path) -> pd.DataFrame:
    if features_path.exists():
        return pd.read_csv(features_path)

    d1_path = features_path.parent / "d1_features.csv"
    d2d3_path = features_path.parent / "d2d3_features.csv"
    d5_path = features_path.parent / "d5_features.csv"
    missing = [str(path) for path in (d1_path, d2d3_path, d5_path) if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing feature tables: " + ", ".join(missing))

    features = (
        pd.read_csv(d1_path)
        .merge(pd.read_csv(d2d3_path), on="filename", how="inner")
        .merge(pd.read_csv(d5_path), on="filename", how="inner")
    )
    features.to_csv(features_path, index=False)
    return features


def add_derived_metrics(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "LUFS" in out.columns and "LUFS_dev" not in out.columns:
        out["LUFS_dev"] = (out["LUFS"] - (-12.0)).abs()
    return out


def load_dataset(annotations_path: Path, features_path: Path) -> pd.DataFrame:
    annotations = pd.read_csv(annotations_path)
    features = add_derived_metrics(load_features(features_path))
    return annotations.merge(features, on="filename", how="inner")


def _severity_values(df: pd.DataFrame, dimension: str, metric: str, severity: int) -> pd.Series:
    labels = df[dimension].map(score_to_severity)
    return df.loc[labels == severity, metric].dropna()


def summarize_distribution(values: pd.Series) -> dict[str, float | int | None]:
    if values.empty:
        return {"count": 0, "q1": None, "median": None, "q3": None}
    return {
        "count": int(values.size),
        "q1": float(np.percentile(values, 25)),
        "median": float(np.median(values)),
        "q3": float(np.percentile(values, 75)),
    }


def ordered_thresholds(red: float | None, yellow: float | None, direction: str) -> tuple[float | None, float | None, bool]:
    """Return directionally valid yellow/red cutpoints."""
    if red is None or yellow is None:
        return yellow, red, False

    adjusted = False
    if direction == "negative":
        if yellow >= red:
            yellow, red = min(yellow, red), max(yellow, red)
            adjusted = True
        if yellow >= red:
            red = float(np.nextafter(red, np.inf))
            adjusted = True
    else:
        if yellow <= red:
            yellow, red = max(yellow, red), min(yellow, red)
            adjusted = True
        if yellow <= red:
            red = float(np.nextafter(red, -np.inf))
            adjusted = True
    return yellow, red, adjusted


def learn_thresholds(df: pd.DataFrame) -> dict[str, dict[str, dict[str, float | str | None]]]:
    """Learn red/yellow thresholds from severity-specific percentiles."""
    thresholds: dict[str, dict[str, dict[str, float | str | None]]] = {}
    for rule in METRIC_RULES:
        dimension = rule["dimension"]
        metric = rule["metric"]
        direction = rule["direction"]
        sev2 = _severity_values(df, dimension, metric, 2)
        sev1 = _severity_values(df, dimension, metric, 1)

        if direction == "negative":
            red = float(np.percentile(sev2, 25)) if not sev2.empty else None
        else:
            red = float(np.percentile(sev2, 75)) if not sev2.empty else None
        yellow = float(np.median(sev1)) if not sev1.empty else None
        raw_red = red
        raw_yellow = yellow
        yellow, red, adjusted = ordered_thresholds(red, yellow, direction)

        thresholds.setdefault(dimension, {})[metric] = {
            "direction": direction,
            "threshold_red": red,
            "threshold_yellow": yellow,
            "raw_threshold_red": raw_red,
            "raw_threshold_yellow": raw_yellow,
            "threshold_adjusted_for_order": adjusted,
            "red_source": "severity_2_q25" if direction == "negative" else "severity_2_q75",
            "yellow_source": "severity_1_median",
            "severity_distribution": {
                str(severity): summarize_distribution(_severity_values(df, dimension, metric, severity))
                for severity in SEVERITY_LABELS
            },
        }
    return thresholds


def validate_threshold_order(thresholds: dict[str, dict[str, dict[str, float | str | None]]]) -> None:
    problems = []
    for dimension, metrics in thresholds.items():
        for metric, rule_thresholds in metrics.items():
            yellow = rule_thresholds["threshold_yellow"]
            red = rule_thresholds["threshold_red"]
            direction = rule_thresholds["direction"]
            if yellow is None or red is None:
                continue
            if direction == "negative" and not yellow < red:
                problems.append(f"{dimension}/{metric}: expected yellow < red")
            if direction == "positive" and not yellow > red:
                problems.append(f"{dimension}/{metric}: expected yellow > red")
    if problems:
        raise ValueError("Invalid threshold ordering after adjustment: " + "; ".join(problems))


def metric_flag(value: float, rule_thresholds: dict[str, float | str | None]) -> int | None:
    if pd.isna(value):
        return None

    red = rule_thresholds["threshold_red"]
    yellow = rule_thresholds["threshold_yellow"]
    direction = rule_thresholds["direction"]
    if red is None or yellow is None:
        return None

    if direction == "negative":
        if value > red:
            return 2
        if value > yellow:
            return 1
    else:
        if value < red:
            return 2
        if value < yellow:
            return 1
    return 0


def majority_label(labels: pd.Series) -> int:
    counts = labels.value_counts().sort_index()
    max_count = counts.max()
    return int(counts[counts == max_count].index[0])


def vote_dimension(flags: list[int]) -> int:
    if not flags:
        return 0
    red_votes = sum(flag == 2 for flag in flags)
    warning_votes = sum(flag >= 1 for flag in flags)
    majority = len(flags) / 2
    if red_votes > majority:
        return 2
    if warning_votes > majority:
        return 1
    return 0


def diagnose_sample(
    sample: pd.Series | dict[str, float],
    thresholds: dict[str, dict[str, dict[str, float | str | None]]],
) -> dict[str, int]:
    """Return D1/D2/D3/D5 severity flags for one cover feature vector."""
    sample_series = pd.Series(sample)
    if "LUFS" in sample_series and "LUFS_dev" not in sample_series:
        sample_series["LUFS_dev"] = abs(float(sample_series["LUFS"]) + 12.0)

    diagnosis: dict[str, int] = {}
    for dimension in DIAGNOSTIC_DIMENSIONS:
        flags = []
        for metric, rule_thresholds in thresholds[dimension].items():
            if metric in sample_series:
                flag = metric_flag(float(sample_series[metric]), rule_thresholds)
                if flag is not None:
                    flags.append(flag)
        diagnosis[dimension] = vote_dimension(flags)
    return diagnosis


def summarize_predictions(loo: pd.DataFrame, labels: list[int]) -> pd.DataFrame:
    summary_rows = []
    for dimension in DIAGNOSTIC_DIMENSIONS:
        part = loo[loo["dimension"] == dimension]
        summary_rows.append(
            {
                "dimension": dimension,
                "rule_accuracy": accuracy_score(part["true"], part["pred"]),
                "rule_weighted_f1": f1_score(part["true"], part["pred"], labels=labels, average="weighted", zero_division=0),
                "baseline_accuracy": accuracy_score(part["true"], part["baseline_pred"]),
                "baseline_weighted_f1": f1_score(
                    part["true"], part["baseline_pred"], labels=labels, average="weighted", zero_division=0
                ),
                "support": len(part),
            }
        )

    summary_rows.append(
        {
            "dimension": "overall",
            "rule_accuracy": accuracy_score(loo["true"], loo["pred"]),
            "rule_weighted_f1": f1_score(loo["true"], loo["pred"], labels=labels, average="weighted", zero_division=0),
            "baseline_accuracy": accuracy_score(loo["true"], loo["baseline_pred"]),
            "baseline_weighted_f1": f1_score(
                loo["true"], loo["baseline_pred"], labels=labels, average="weighted", zero_division=0
            ),
            "support": len(loo),
        }
    )
    return pd.DataFrame(summary_rows)


def run_loo(df: pd.DataFrame, *, binary: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for holdout_idx, sample in df.iterrows():
        train = df.drop(index=holdout_idx)
        thresholds = learn_thresholds(train)
        validate_threshold_order(thresholds)
        prediction = diagnose_sample(sample, thresholds)
        for dimension in DIAGNOSTIC_DIMENSIONS:
            train_severity = train[dimension].map(score_to_severity)
            true = score_to_severity(sample[dimension])
            pred = prediction[dimension]
            if binary:
                train_labels = train_severity.map(severity_to_binary)
                true = severity_to_binary(true)
                pred = severity_to_binary(pred)
            else:
                train_labels = train_severity
            rows.append(
                {
                    "filename": sample["filename"],
                    "dimension": dimension,
                    "true": true,
                    "pred": pred,
                    "baseline_pred": majority_label(train_labels),
                }
            )

    loo = pd.DataFrame(rows)
    labels = BINARY_LABELS if binary else SEVERITY_LABELS
    return loo, summarize_predictions(loo, labels)


def save_thresholds(thresholds: dict[str, dict[str, dict[str, float | str | None]]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(thresholds, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def save_confusion_matrix(loo: pd.DataFrame, output_path: Path, labels: list[int]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 2, figsize=(8.2, 7.2), constrained_layout=True)
    for ax, dimension in zip(axes.ravel(), DIAGNOSTIC_DIMENSIONS):
        part = loo[loo["dimension"] == dimension]
        matrix = confusion_matrix(part["true"], part["pred"], labels=labels)
        image = ax.imshow(matrix, cmap="Blues")
        ax.set_title(dimension)
        ax.set_xlabel("Predicted severity")
        ax.set_ylabel("True severity")
        ax.set_xticks(range(len(labels)), labels=labels)
        ax.set_yticks(range(len(labels)), labels=labels)
        for row in range(matrix.shape[0]):
            for col in range(matrix.shape[1]):
                ax.text(col, row, str(matrix[row, col]), ha="center", va="center", color="black")
        fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    fig.savefig(output_path, dpi=220)
    plt.close(fig)


def threshold_table(thresholds: dict[str, dict[str, dict[str, float | str | None]]]) -> pd.DataFrame:
    rows = []
    for dimension in DIAGNOSTIC_DIMENSIONS:
        for metric, rule_thresholds in thresholds[dimension].items():
            rows.append(
                {
                    "dimension": dimension,
                    "metric": metric,
                    "direction": rule_thresholds["direction"],
                    "threshold_yellow": rule_thresholds["threshold_yellow"],
                    "threshold_red": rule_thresholds["threshold_red"],
                    "adjusted": rule_thresholds["threshold_adjusted_for_order"],
                }
            )
    return pd.DataFrame(rows)


def print_thresholds(thresholds: dict[str, dict[str, dict[str, float | str | None]]]) -> None:
    display = threshold_table(thresholds)
    for column in ("threshold_yellow", "threshold_red"):
        display[column] = display[column].map(lambda value: "NA" if pd.isna(value) else f"{value:.6f}")
    print("\nLearned diagnostic thresholds")
    print(display.to_string(index=False))


def print_summary(title: str, summary: pd.DataFrame) -> None:
    display = summary.copy()
    for column in ("rule_accuracy", "rule_weighted_f1", "baseline_accuracy", "baseline_weighted_f1"):
        display[column] = display[column].map("{:.3f}".format)
    print(f"\n{title}")
    print(display.to_string(index=False))


def main() -> int:
    args = parse_args()
    df = load_dataset(args.annotations, args.features)

    thresholds = learn_thresholds(df)
    validate_threshold_order(thresholds)
    save_thresholds(thresholds, args.thresholds_json)

    loo, summary = run_loo(df)
    binary_loo, binary_summary = run_loo(df, binary=True)

    args.summary_csv.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.summary_csv, index=False)
    binary_summary.to_csv(args.binary_summary_csv, index=False)
    save_confusion_matrix(loo, args.confusion_png, SEVERITY_LABELS)
    save_confusion_matrix(binary_loo, args.binary_confusion_png, BINARY_LABELS)

    print_thresholds(thresholds)
    print_summary("Rule-based diagnostic LOO summary (3-class severity)", summary)
    print_summary("Rule-based diagnostic LOO summary (binary acceptable/severe)", binary_summary)
    print("\nD4 is excluded because no objective diagnostic metric is defined for style matching.")

    if args.diagnose_json:
        sample = json.loads(args.diagnose_json.read_text(encoding="utf-8"))
        print("\nDiagnosis for input feature vector")
        print(json.dumps(diagnose_sample(sample, thresholds), indent=2, sort_keys=True))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
