#!/usr/bin/env python3
"""Convert Demucs vocal stems to MIDI with basic-pitch."""

from __future__ import annotations

import argparse
from pathlib import Path

import basic_pitch
from basic_pitch.inference import predict_and_save


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--separated-dir", type=Path, default=Path("separated/htdemucs_ft"))
    parser.add_argument("--midi-dir", type=Path, default=Path("midi"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.midi_dir.mkdir(parents=True, exist_ok=True)
    model_path = Path(basic_pitch.__file__).resolve().parent / "saved_models" / "icassp_2022" / "nmp.onnx"

    vocals = sorted(args.separated_dir.glob("*/vocals.wav"))
    if not vocals:
        raise SystemExit(f"No vocals.wav files found under {args.separated_dir}")

    for vocal_path in vocals:
        target = args.midi_dir / f"{vocal_path.parent.name}.mid"
        if target.exists():
            continue
        tmp_dir = args.midi_dir / f".basic_pitch_tmp_{vocal_path.parent.name}"
        tmp_dir.mkdir(exist_ok=True)
        predict_and_save(
            [str(vocal_path)],
            str(tmp_dir),
            save_midi=True,
            sonify_midi=False,
            save_model_outputs=False,
            save_notes=False,
            model_or_model_path=model_path,
        )
        created = next(tmp_dir.glob("*.mid"))
        created.replace(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
