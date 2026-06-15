#!/usr/bin/env python3
"""Extract IKCR from Demucs no_vocals.wav and the matching vocals MIDI."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import autochord
import music21


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract in-key chord ratio from accompaniment audio.")
    parser.add_argument("no_vocals_wav", type=Path, help="Demucs no_vocals.wav path")
    parser.add_argument("vocals_mid", type=Path, help="Matching vocals.mid path")
    parser.add_argument("--no-header", action="store_true", help="Only print the data row")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    chords = autochord.recognize(str(args.no_vocals_wav.expanduser()))
    score = music21.converter.parse(str(args.vocals_mid.expanduser()))
    key = score.analyze("key")
    key_obj = music21.key.Key(key.tonic.name, key.mode)
    diatonic_roots = [p.name for p in key_obj.getScale().getPitches()[:-1]]

    in_key = 0
    total = 0
    for _, _, label in chords:
        if label == "N":
            continue
        root = label.split(":")[0]
        total += 1
        if root in diatonic_roots:
            in_key += 1

    row = {
        "no_vocals": args.no_vocals_wav.name,
        "vocals_mid": args.vocals_mid.name,
        "key": f"{key.tonic.name} {key.mode}",
        "IKCR": in_key / max(total, 1),
        "in_key_chords": in_key,
        "total_chords": total,
    }
    writer = csv.DictWriter(sys.stdout, fieldnames=list(row), lineterminator="\n")
    if not args.no_header:
        writer.writeheader()
    writer.writerow(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

