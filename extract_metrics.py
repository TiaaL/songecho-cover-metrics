#!/usr/bin/env python3
"""Extract the 9 Mac-side metrics for one cover audio and print one CSV row."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from cover_metrics import extract_metrics


FIELDS = ["filename", "LLR", "PR", "PS", "IKNR", "KC", "KCR", "LUFS", "LRA", "SC"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract 9 objective metrics from one cover audio.")
    parser.add_argument("audio_path", type=Path, help="Path to one cover audio file")
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path(".cover_metrics_work"),
        help="Directory for Demucs/basic-pitch intermediate files",
    )
    parser.add_argument("--force", action="store_true", help="Recompute intermediate files even if cached")
    parser.add_argument("--no-header", action="store_true", help="Only print the data row")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    audio_path = args.audio_path.expanduser().resolve()
    result = extract_metrics(audio_path, args.work_dir.expanduser().resolve(), force=args.force)
    metrics = result["metrics"]
    row = {
        "filename": audio_path.name,
        "LLR": metrics["LLR"],
        "PR": metrics["PR"],
        "PS": metrics["PS"],
        "IKNR": metrics["IKNR"],
        "KC": metrics["KC"],
        "KCR": metrics["KCR"],
        "LUFS": result["supporting_values"]["LUFS"],
        "LRA": metrics["LRA"],
        "SC": metrics["SC"],
    }

    writer = csv.DictWriter(sys.stdout, fieldnames=FIELDS, lineterminator="\n")
    if not args.no_header:
        writer.writeheader()
    writer.writerow(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

