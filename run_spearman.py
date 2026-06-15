#!/usr/bin/env python3
"""Run the planned Spearman correlation checks against results.csv."""

from __future__ import annotations

import argparse

import pandas as pd
from scipy.stats import spearmanr


CORRELATIONS = [
    ("D1", "LLR", "neg"),
    ("D1", "PS", "neg"),
    ("D2", "IKNR", "pos"),
    ("D2", "IKCR", "pos"),
    ("D3", "KC", "pos"),
    ("D3", "IKNR", "pos"),
    ("D3", "KCR", "neg"),
    ("D5", "LUFS_dev", "neg"),
    ("D5", "LRA", "pos"),
    ("D5", "SC", "pos"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Spearman correlations for objective metrics.")
    parser.add_argument("csv_path", nargs="?", default="results.csv", help="Merged ratings and metrics CSV")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    df = pd.read_csv(args.csv_path)
    if "LUFS_dev" not in df:
        df["LUFS_dev"] = abs(df["LUFS"] - (-12))

    for dim, metric, direction in CORRELATIONS:
        rho, p = spearmanr(df[dim], df[metric])
        sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "n.s."
        print(f"{dim} vs {metric}: rho={rho:.3f}, p={p:.3f} {sig} (expected {direction})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

