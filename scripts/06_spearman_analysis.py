#!/usr/bin/env python3
"""Run Spearman correlations and save a compact result table."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from scipy.stats import spearmanr


AUDIO_EXTS = {".mp3", ".wav", ".flac", ".m4a"}


def join_key(filename: object) -> str:
    """Normalize a filename to a stem-only join key.

    Extraction scripts emit bare stems while the published tables carry a
    ``.mp3`` suffix. Stripping a known audio extension makes both forms join,
    regardless of the user's audio format, without altering any stored values.
    """

    name = str(filename)
    stem, dot, ext = name.rpartition(".")
    if dot and f".{ext.lower()}" in AUDIO_EXTS:
        return stem
    return name


def merge_on_filename(left: pd.DataFrame, right: pd.DataFrame, *, context: str) -> pd.DataFrame:
    """Inner-merge on the normalized filename key and warn on dropped rows."""

    merged = left.merge(
        right.drop(columns=["filename"], errors="ignore"),
        left_on=left["filename"].map(join_key),
        right_on=right["filename"].map(join_key),
        how="inner",
    ).drop(columns=["key_0"], errors="ignore")

    kept = set(left["filename"].map(join_key)) & set(right["filename"].map(join_key))
    for side, frame in (("left", left), ("right", right)):
        dropped = sorted(set(frame["filename"]) - {f for f in frame["filename"] if join_key(f) in kept})
        if dropped:
            print(
                f"WARNING [{context}]: {len(dropped)} {side} sample(s) had no match and "
                f"were dropped: {', '.join(dropped)}",
                file=sys.stderr,
            )
    return merged


CORRELATIONS = [
    ("D1", "LLR", "negative"),
    ("D1", "PS", "negative"),
    ("D2", "IKNR", "positive"),
    ("D3", "KC", "positive"),
    ("D3", "IKNR", "positive"),
    ("D3", "KCR", "negative"),
    ("D5", "LUFS_dev", "negative"),
    ("D5", "LRA", "positive"),
    ("D5", "SC", "positive"),
]


def significance(p_value: float) -> str:
    if p_value < 0.001:
        return "***"
    if p_value < 0.01:
        return "**"
    if p_value < 0.05:
        return "*"
    return "n.s."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--annotations", type=Path, default=Path("data/annotations/evaluation_scores.csv"))
    parser.add_argument("--features", type=Path, default=Path("features/extracted_features.csv"))
    parser.add_argument("--output-csv", type=Path, default=Path("figures/spearman_table.csv"))
    parser.add_argument("--output-png", type=Path, default=Path("figures/spearman_table.png"))
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

    features = merge_on_filename(
        pd.read_csv(d1_path), pd.read_csv(d2d3_path), context="d1+d2d3"
    )
    features = merge_on_filename(features, pd.read_csv(d5_path), context="+d5")
    features.to_csv(features_path, index=False)
    return features


def main() -> int:
    args = parse_args()
    df = merge_on_filename(
        pd.read_csv(args.annotations), load_features(args.features), context="scores+features"
    )
    df["LUFS_dev"] = (df["LUFS"] - (-12.0)).abs()

    rows = []
    for dim, metric, expected in CORRELATIONS:
        valid = df[[dim, metric]].dropna()
        rho, p_value = spearmanr(valid[dim], valid[metric])
        rows.append(
            {
                "dimension": dim,
                "metric": metric,
                "expected": expected,
                "rho": round(float(rho), 3),
                "p": round(float(p_value), 3),
                "sig": significance(float(p_value)),
            }
        )

    out = pd.DataFrame(rows)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.output_csv, index=False)

    display = out.copy()
    display["rho"] = display["rho"].map("{:.3f}".format)
    display["p"] = display["p"].map("{:.3f}".format)

    fig, ax = plt.subplots(figsize=(8.4, 3.4))
    ax.axis("off")
    table = ax.table(cellText=display.values, colLabels=display.columns, cellLoc="center", loc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1, 1.35)
    fig.tight_layout()
    fig.savefig(args.output_png, dpi=220)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
