#!/usr/bin/env python3
"""Extract D5 production metrics: LUFS, LRA, and spectral contrast."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import librosa
import numpy as np
import pyloudnorm as pyln
import soundfile as sf


FIELDS = ["filename", "LUFS", "LRA", "SC"]
AUDIO_EXTS = {".wav", ".mp3", ".flac", ".m4a"}


def extract_metrics(audio_path: Path) -> dict[str, float | str]:
    data, rate = sf.read(str(audio_path), always_2d=True)
    meter = pyln.Meter(rate)
    lufs = float(meter.integrated_loudness(data))
    lra = float(meter.loudness_range(data))

    y, sr = librosa.load(str(audio_path), sr=None, mono=False)
    y_mono = librosa.to_mono(y) if getattr(y, "ndim", 1) > 1 else y
    contrast = librosa.feature.spectral_contrast(y=y_mono, sr=sr)

    return {
        "filename": audio_path.stem,
        "LUFS": round(lufs, 6),
        "LRA": round(lra, 6),
        "SC": round(float(np.mean(contrast)), 6),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio-dir", type=Path, default=Path("audio"))
    parser.add_argument("--output", type=Path, default=Path("features/d5_features.csv"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = sorted(path for path in args.audio_dir.iterdir() if path.suffix.lower() in AUDIO_EXTS)
    rows = [extract_metrics(path) for path in paths]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
