#!/usr/bin/env python3
"""Extract D1 melody metrics: LLR, PR, and PS."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np
import pretty_midi


FIELDS = ["filename", "LLR", "PR", "PS"]


def melody_metrics(midi_path: Path) -> dict[str, float | str | None]:
    pm = pretty_midi.PrettyMIDI(str(midi_path))
    notes = [note for inst in pm.instruments if not inst.is_drum for note in inst.notes]
    notes.sort(key=lambda note: (note.start, note.pitch, note.end))
    pitches = [int(note.pitch) for note in notes]
    intervals = [abs(pitches[i + 1] - pitches[i]) for i in range(len(pitches) - 1)]
    return {
        "filename": midi_path.stem,
        "LLR": round(sum(i > 7 for i in intervals) / len(intervals), 6) if intervals else None,
        "PR": max(pitches) - min(pitches) if pitches else None,
        "PS": round(float(np.std(intervals)), 6) if intervals else None,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--midi-dir", type=Path, default=Path("midi"))
    parser.add_argument("--output", type=Path, default=Path("features/d1_features.csv"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = [melody_metrics(path) for path in sorted(args.midi_dir.glob("*.mid"))]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
