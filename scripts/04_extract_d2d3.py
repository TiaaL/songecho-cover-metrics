#!/usr/bin/env python3
"""Extract D2/D3 key metrics with fixed 10-second KCR windows."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

import music21
import pretty_midi


MIN_NOTES_PER_WINDOW = 5
FIELDS = ["filename", "IKNR", "KC", "KCR"]


def key_name(key_obj: Any) -> str:
    tonic = getattr(key_obj, "tonic", None)
    mode = getattr(key_obj, "mode", "")
    return f"{tonic.name} {mode}".strip() if tonic else str(key_obj)


def pitch_classes_for_key(key_obj: Any) -> set[int]:
    return {int(p.pitchClass) for p in key_obj.getScale().getPitches()}


def key_from_pitches(pitches: list[int]) -> str:
    stream = music21.stream.Stream()
    for pitch in pitches:
        stream.append(music21.note.Note(pitch))
    return key_name(stream.analyze("key"))


def extract_metrics(midi_path: Path) -> dict[str, float | str | None]:
    pm = pretty_midi.PrettyMIDI(str(midi_path))
    notes = [note for inst in pm.instruments if not inst.is_drum for note in inst.notes]
    notes.sort(key=lambda note: (note.start, note.pitch, note.end))
    pitches = [int(note.pitch) for note in notes]

    score = music21.converter.parse(str(midi_path))
    global_key = score.analyze("key")
    in_key = pitch_classes_for_key(global_key)
    iknr = sum((pitch % 12) in in_key for pitch in pitches) / len(pitches) if pitches else None
    kc = getattr(global_key, "correlationCoefficient", None)

    window_keys: list[str] = []
    duration = max((note.end for note in notes), default=0.0)
    start = 0.0
    while start < duration:
        end = start + 10.0
        window_pitches = [int(note.pitch) for note in notes if start <= note.start < end]
        if len(window_pitches) >= MIN_NOTES_PER_WINDOW:
            window_keys.append(key_from_pitches(window_pitches))
        start = end

    changes = sum(a != b for a, b in zip(window_keys, window_keys[1:]))
    kcr = changes / (len(window_keys) - 1) if len(window_keys) > 1 else None

    return {
        "filename": f"{midi_path.stem}.mp3",
        "IKNR": round(float(iknr), 6) if iknr is not None else None,
        "KC": round(float(kc), 6) if kc is not None else None,
        "KCR": round(float(kcr), 6) if kcr is not None else None,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--midi-dir", type=Path, default=Path("midi"))
    parser.add_argument("--output", type=Path, default=Path("features/d2d3_features.csv"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = [extract_metrics(path) for path in sorted(args.midi_dir.glob("*.mid"))]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
