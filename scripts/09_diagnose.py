#!/usr/bin/env python3
"""Diagnose user audio and optionally compare against the user's own scores.

Two capabilities, both reusing the rule logic in ``07_rule_diagnostic.py``:

  1. Batch diagnosis: features CSV -> per-cover D1/D2/D3/D5 severity labels
     (0 acceptable / 1 warning / 2 severe). No expert scores needed.
  2. Diagnosis vs. human comparison: when the user also supplies their own
     expert scores, align the automatic labels against the human labels
     per cover and per dimension, and report agreement rates.

The rule diagnosis is an advisory signal, not a quality score. On the paper's
30-sample leave-one-out evaluation it does not significantly beat a
majority-class baseline, so a modest agreement rate here is expected.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
RULE_DIAGNOSTIC_PATH = SCRIPT_DIR / "07_rule_diagnostic.py"

AUDIO_EXTS = {".mp3", ".wav", ".flac", ".m4a"}

ADVISORY_NOTE = (
    "NOTE: rule diagnosis is an advisory diagnostic signal, not a quality score. "
    "On the paper's 30-sample LOO it does not significantly beat a majority-class "
    "baseline, so a modest agreement rate is expected and does not by itself judge audio quality."
)


def load_rule_diagnostic():
    spec = importlib.util.spec_from_file_location("rule_diagnostic", RULE_DIAGNOSTIC_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import {RULE_DIAGNOSTIC_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def join_key(filename: object) -> str:
    """Normalize a filename to a stem-only key (mirrors 06_spearman_analysis)."""
    name = str(filename)
    stem, dot, ext = name.rpartition(".")
    if dot and f".{ext.lower()}" in AUDIO_EXTS:
        return stem
    return name


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--features",
        type=Path,
        default=Path("features/extracted_features.csv"),
        help="Feature table to diagnose (filename + 9 metrics).",
    )
    parser.add_argument(
        "--thresholds-from-annotations",
        type=Path,
        default=Path("data/annotations/evaluation_scores.csv"),
        help="Expert scores used to LEARN thresholds. Defaults to the published paper scores.",
    )
    parser.add_argument(
        "--thresholds-from-features",
        type=Path,
        default=Path("features/extracted_features.csv"),
        help="Feature table paired with --thresholds-from-annotations for threshold learning.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("figures/diagnosis_labels.csv"),
        help="Output CSV of per-cover D1/D2/D3/D5 severity labels.",
    )
    parser.add_argument(
        "--annotations",
        type=Path,
        default=None,
        help="Optional: the user's OWN expert scores; enables diagnosis-vs-human comparison.",
    )
    parser.add_argument(
        "--compare-out",
        type=Path,
        default=Path("figures/diagnosis_vs_human.csv"),
        help="Per-sample per-dimension comparison long table (only with --annotations).",
    )
    parser.add_argument(
        "--compare-summary",
        type=Path,
        default=Path("figures/diagnosis_vs_human_summary.csv"),
        help="Per-dimension agreement summary (only with --annotations).",
    )
    return parser.parse_args()


def diagnose_table(rd, features: pd.DataFrame, thresholds) -> pd.DataFrame:
    """Capability 1: label every row with D1/D2/D3/D5 severities."""
    features = rd.add_derived_metrics(features)
    rows = []
    for _, sample in features.iterrows():
        diagnosis = rd.diagnose_sample(sample, thresholds)
        rows.append({"filename": sample["filename"], **diagnosis})
    return pd.DataFrame(rows, columns=["filename", *rd.DIAGNOSTIC_DIMENSIONS])


def compare_with_human(rd, labels: pd.DataFrame, annotations: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Capability 2: align auto labels vs human severities per cover/dimension."""
    labels = labels.copy()
    annotations = annotations.copy()
    labels["_key"] = labels["filename"].map(join_key)
    annotations["_key"] = annotations["filename"].map(join_key)

    kept = set(labels["_key"]) & set(annotations["_key"])
    for side, frame in (("diagnosis", labels), ("human-scores", annotations)):
        dropped = sorted({f for f in frame["filename"] if join_key(f) not in kept})
        if dropped:
            print(
                f"WARNING [compare]: {len(dropped)} {side} sample(s) had no match and "
                f"were dropped: {', '.join(dropped)}",
                file=sys.stderr,
            )

    merged = labels.merge(annotations, on="_key", how="inner", suffixes=("", "_human"))
    long_rows = []
    for _, row in merged.iterrows():
        for dimension in rd.DIAGNOSTIC_DIMENSIONS:
            pred = int(row[dimension])
            true = rd.score_to_severity(row[f"{dimension}_human"])
            long_rows.append(
                {
                    "filename": row["filename"],
                    "dimension": dimension,
                    "pred": pred,
                    "true": true,
                    "match": int(pred == true),
                }
            )
    long_df = pd.DataFrame(long_rows)

    summary_rows = []
    for dimension in rd.DIAGNOSTIC_DIMENSIONS:
        part = long_df[long_df["dimension"] == dimension]
        summary_rows.append(
            {
                "dimension": dimension,
                "accuracy": round(float(part["match"].mean()), 6) if len(part) else None,
                "support": int(len(part)),
            }
        )
    summary_rows.append(
        {
            "dimension": "overall",
            "accuracy": round(float(long_df["match"].mean()), 6) if len(long_df) else None,
            "support": int(len(long_df)),
        }
    )
    return long_df, pd.DataFrame(summary_rows)


def main() -> int:
    args = parse_args()
    rd = load_rule_diagnostic()

    print(ADVISORY_NOTE, file=sys.stderr)

    # Learn thresholds from a (scores, features) pair — defaults to the published paper data.
    train = rd.load_dataset(args.thresholds_from_annotations, args.thresholds_from_features)
    thresholds = rd.learn_thresholds(train)
    rd.validate_threshold_order(thresholds)

    # Capability 1: batch diagnosis.
    features = pd.read_csv(args.features)
    labels = diagnose_table(rd, features, thresholds)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    labels.to_csv(args.out, index=False)
    print(f"Wrote {len(labels)} diagnosis rows to {args.out}")

    # Capability 2: compare vs the user's own human scores (optional).
    if args.annotations is not None:
        annotations = pd.read_csv(args.annotations)
        long_df, summary = compare_with_human(rd, labels, annotations)
        args.compare_out.parent.mkdir(parents=True, exist_ok=True)
        long_df.to_csv(args.compare_out, index=False)
        summary.to_csv(args.compare_summary, index=False)
        print(f"Wrote per-sample comparison to {args.compare_out}")
        print("Diagnosis vs. human agreement (whole-sample re-substitution, NOT cross-validated):")
        print(summary.to_string(index=False))
        print(
            "For an unbiased estimate use the LOO/bootstrap in 07/08; this re-substitution "
            "agreement is optimistic."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
