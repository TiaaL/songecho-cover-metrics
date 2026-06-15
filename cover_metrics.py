#!/usr/bin/env python3
"""Single-file objective metric extractor for one cover audio.

Input: one stereo cover audio path.
Output: one JSON object containing the 10 metrics from "客观工具方案（定稿 v3）".

KCR follows the explicit note at the end of the markdown file: fixed 10-second
windows, not manually annotated sections.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

import numpy as np


LUFS_TARGET = -12.0
MIN_NOTES_FOR_KEY_WINDOW = 5


def require_module(name: str, pip_name: str | None = None) -> None:
    if importlib.util.find_spec(name) is None:
        install_name = pip_name or name
        raise RuntimeError(f"Missing Python module '{name}'. Install with: pip install {install_name}")


@contextlib.contextmanager
def redirect_output_to_stderr() -> Iterable[None]:
    original_stdout = sys.stdout
    sys.stdout = sys.stderr
    try:
        yield
    finally:
        sys.stdout = original_stdout


def command_path(name: str) -> str:
    found = shutil.which(name)
    if not found:
        raise RuntimeError(f"Required command not found: {name}")
    return found


def run(cmd: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        joined = " ".join(cmd)
        tail = (proc.stderr or proc.stdout)[-1600:]
        raise RuntimeError(f"Command failed ({joined}):\n{tail}")
    return proc


def safe_round(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    if not math.isfinite(float(value)):
        return None
    return round(float(value), digits)


def audio_signature(path: Path) -> str:
    stat = path.stat()
    safe_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", path.stem).strip("_") or "audio"
    return f"{safe_stem}_{stat.st_size}_{int(stat.st_mtime)}"


def demucs_output_paths(audio_path: Path, work_dir: Path) -> tuple[Path, Path, Path]:
    stem = audio_path.stem
    demucs_dir = work_dir / "demucs" / "htdemucs_ft" / stem
    return demucs_dir / "vocals.wav", demucs_dir / "no_vocals.wav", demucs_dir


def ensure_demucs_stems(audio_path: Path, work_dir: Path, force: bool) -> tuple[Path, Path]:
    vocals, no_vocals, _ = demucs_output_paths(audio_path, work_dir)
    if not force and vocals.exists() and no_vocals.exists():
        return vocals, no_vocals

    require_module("demucs")
    work_dir.mkdir(parents=True, exist_ok=True)
    run(
        [
            sys.executable,
            "-m",
            "demucs",
            "-n",
            "htdemucs_ft",
            "--two-stems",
            "vocals",
            "-o",
            str(work_dir / "demucs"),
            str(audio_path),
        ]
    )
    if not vocals.exists() or not no_vocals.exists():
        raise RuntimeError(f"Demucs finished but expected stems were not found under {work_dir / 'demucs'}")
    return vocals, no_vocals


def ensure_mono_wav(input_wav: Path, output_wav: Path, force: bool) -> Path:
    if not force and output_wav.exists():
        return output_wav
    ffmpeg = command_path("ffmpeg")
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    run([ffmpeg, "-hide_banner", "-y", "-i", str(input_wav), "-ac", "1", str(output_wav)])
    return output_wav


def find_basic_pitch_midi(midi_dir: Path, audio_path: Path) -> Path:
    candidates = sorted(midi_dir.glob(f"{audio_path.stem}*.mid")) + sorted(midi_dir.glob("*.mid"))
    if not candidates:
        raise RuntimeError(f"basic-pitch did not create a MIDI file in {midi_dir}")
    return candidates[0]


def ensure_vocal_midi(vocals_mono_wav: Path, work_dir: Path, force: bool) -> Path:
    midi_dir = work_dir / "basic_pitch"
    if not force:
        existing = sorted(midi_dir.glob("*.mid"))
        if existing:
            return existing[0]

    require_module("basic_pitch")
    import basic_pitch
    from basic_pitch.inference import predict_and_save

    midi_dir.mkdir(parents=True, exist_ok=True)
    model_path = Path(basic_pitch.__file__).resolve().parent / "saved_models" / "icassp_2022" / "nmp.onnx"
    with redirect_output_to_stderr():
        predict_and_save(
            [str(vocals_mono_wav)],
            str(midi_dir),
            save_midi=True,
            sonify_midi=False,
            save_model_outputs=False,
            save_notes=False,
            model_or_model_path=model_path,
        )
    return find_basic_pitch_midi(midi_dir, vocals_mono_wav)


def load_pretty_midi_notes(midi_path: Path) -> list[Any]:
    require_module("pretty_midi", "pretty-midi")
    import pretty_midi

    pm = pretty_midi.PrettyMIDI(str(midi_path))
    notes = [
        note
        for inst in pm.instruments
        if not inst.is_drum
        for note in inst.notes
    ]
    notes.sort(key=lambda note: (note.start, note.pitch, note.end))
    return notes


def melody_metrics(notes: list[Any]) -> dict[str, float | int | None]:
    pitches = [int(note.pitch) for note in notes]
    intervals = [abs(pitches[i + 1] - pitches[i]) for i in range(len(pitches) - 1)]
    if not pitches:
        return {"LLR": None, "PR": None, "PS": None, "note_count": 0, "interval_count": 0}
    if not intervals:
        return {"LLR": None, "PR": max(pitches) - min(pitches), "PS": None, "note_count": len(pitches), "interval_count": 0}
    return {
        "LLR": sum(1 for interval in intervals if interval > 7) / len(intervals),
        "PR": max(pitches) - min(pitches),
        "PS": float(np.std(intervals)),
        "note_count": len(pitches),
        "interval_count": len(intervals),
    }


def analyze_midi_key(midi_path: Path) -> Any:
    require_module("music21")
    import music21

    score = music21.converter.parse(str(midi_path))
    return score.analyze("key")


def key_pitch_classes(key_obj: Any) -> set[int]:
    pitches = key_obj.getScale().getPitches()
    return {int(p.pitchClass) for p in pitches}


def in_key_note_ratio(notes: list[Any], key_obj: Any) -> float | None:
    if not notes:
        return None
    pcs = key_pitch_classes(key_obj)
    hits = sum(1 for note in notes if int(note.pitch) % 12 in pcs)
    return hits / len(notes)


def key_confidence(key_obj: Any) -> float | None:
    value = getattr(key_obj, "correlationCoefficient", None)
    return float(value) if value is not None else None


def key_name(key_obj: Any) -> str:
    tonic = getattr(key_obj, "tonic", None)
    mode = getattr(key_obj, "mode", "")
    if tonic is None:
        return str(key_obj)
    return f"{tonic.name} {mode}".strip()


def stream_key_from_notes(notes: list[Any]) -> str:
    import music21

    stream = music21.stream.Stream()
    for item in notes:
        stream.append(music21.note.Note(int(item.pitch)))
    return key_name(stream.analyze("key"))


def key_change_rate_10s(notes: list[Any], duration_sec: float) -> tuple[float | None, list[dict[str, Any]]]:
    if duration_sec <= 0:
        return None, []

    rows: list[dict[str, Any]] = []
    start = 0.0
    while start < duration_sec:
        end = min(start + 10.0, duration_sec)
        window_notes = [note for note in notes if note.start >= start and note.start < end]
        if len(window_notes) >= MIN_NOTES_FOR_KEY_WINDOW:
            rows.append(
                {
                    "start": round(start, 3),
                    "end": round(end, 3),
                    "note_count": len(window_notes),
                    "key": stream_key_from_notes(window_notes),
                }
            )
        start += 10.0

    if len(rows) < 2:
        return None, rows
    changes = sum(1 for i in range(len(rows) - 1) if rows[i]["key"] != rows[i + 1]["key"])
    return changes / (len(rows) - 1), rows


def normalize_chord_root(root: str) -> int | None:
    import music21

    root = root.strip()
    if not root or root == "N":
        return None
    root = root.replace("♭", "-").replace("b", "-").replace("♯", "#")
    try:
        return int(music21.pitch.Pitch(root).pitchClass)
    except Exception:
        return None


def parse_autochord_item(item: Any) -> str | None:
    if isinstance(item, dict):
        label = item.get("chord") or item.get("label") or item.get("name")
        return str(label) if label is not None else None
    if isinstance(item, (list, tuple)) and item:
        label = item[-1]
        return str(label) if label is not None else None
    return None


def in_key_chord_ratio(no_vocals_wav: Path, key_obj: Any) -> tuple[float | None, dict[str, Any]]:
    if importlib.util.find_spec("autochord") is None:
        return None, {"status": "skipped", "reason": "autochord is not installed on this machine"}

    import autochord

    chords = autochord.recognize(str(no_vocals_wav))
    diatonic_roots = key_pitch_classes(key_obj)
    total = 0
    hits = 0
    skipped = 0
    for item in chords:
        label = parse_autochord_item(item)
        if not label or label == "N":
            skipped += 1
            continue
        root_text = label.split(":")[0].split("/")[0]
        root_pc = normalize_chord_root(root_text)
        if root_pc is None:
            skipped += 1
            continue
        total += 1
        hits += int(root_pc in diatonic_roots)

    value = hits / total if total else None
    return value, {"status": "ok", "total_chords": total, "in_key_chords": hits, "skipped_chords": skipped}


def loudness_metrics(audio_path: Path) -> dict[str, float]:
    require_module("soundfile")
    require_module("pyloudnorm")
    import pyloudnorm as pyln
    import soundfile as sf

    data, rate = sf.read(str(audio_path), always_2d=True)
    meter = pyln.Meter(rate)
    lufs = float(meter.integrated_loudness(data))
    lra = float(meter.loudness_range(data))
    return {"LUFS": lufs, "LUFS_dev": abs(lufs - LUFS_TARGET), "LRA": lra}


def spectral_contrast_metric(audio_path: Path) -> float:
    require_module("librosa")
    import librosa

    y, sr = librosa.load(str(audio_path), sr=None, mono=False)
    y_mono = librosa.to_mono(y) if getattr(y, "ndim", 1) > 1 else y
    contrast = librosa.feature.spectral_contrast(y=y_mono, sr=sr)
    return float(np.mean(contrast))


def duration_from_audio(audio_path: Path) -> float:
    require_module("soundfile")
    import soundfile as sf

    info = sf.info(str(audio_path))
    return float(info.frames / info.samplerate)


def extract_metrics(audio_path: Path, work_root: Path, force: bool) -> dict[str, Any]:
    signature = audio_signature(audio_path)
    work_dir = work_root / signature
    work_dir.mkdir(parents=True, exist_ok=True)

    vocals_wav, no_vocals_wav = ensure_demucs_stems(audio_path, work_dir, force=force)
    vocals_mono_wav = ensure_mono_wav(vocals_wav, work_dir / "vocals_mono.wav", force=force)
    vocals_midi = ensure_vocal_midi(vocals_mono_wav, work_dir, force=force)

    notes = load_pretty_midi_notes(vocals_midi)
    key_obj = analyze_midi_key(vocals_midi)
    duration_sec = duration_from_audio(audio_path)

    d1 = melody_metrics(notes)
    iknr = in_key_note_ratio(notes, key_obj)
    kc = key_confidence(key_obj)
    kcr, kcr_windows = key_change_rate_10s(notes, duration_sec)
    ikcr, ikcr_meta = in_key_chord_ratio(no_vocals_wav, key_obj)
    loudness = loudness_metrics(audio_path)
    sc = spectral_contrast_metric(audio_path)

    metrics = {
        "LLR": safe_round(d1["LLR"]),
        "PR": safe_round(d1["PR"], 3),
        "PS": safe_round(d1["PS"], 6),
        "IKNR": safe_round(iknr),
        "IKCR": safe_round(ikcr),
        "KC": safe_round(kc),
        "KCR": safe_round(kcr),
        "LUFS_dev": safe_round(loudness["LUFS_dev"], 6),
        "LRA": safe_round(loudness["LRA"], 6),
        "SC": safe_round(sc, 6),
    }
    return {
        "audio_path": str(audio_path),
        "work_dir": str(work_dir),
        "intermediate_files": {
            "vocals_wav": str(vocals_wav),
            "no_vocals_wav": str(no_vocals_wav),
            "vocals_mono_wav": str(vocals_mono_wav),
            "vocals_midi": str(vocals_midi),
        },
        "global_key": key_name(key_obj),
        "duration_sec": safe_round(duration_sec, 3),
        "supporting_values": {
            "LUFS": safe_round(loudness["LUFS"], 6),
            "note_count": d1["note_count"],
            "interval_count": d1["interval_count"],
            "kcr_valid_windows": len(kcr_windows),
            "ikcr": ikcr_meta,
        },
        "metrics": metrics,
    }


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract the 10 v3 objective metrics from one cover audio.")
    parser.add_argument("audio_path", type=Path, help="Path to one cover audio file")
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path(".cover_metrics_work"),
        help="Directory for Demucs/basic-pitch intermediate files",
    )
    parser.add_argument("--force", action="store_true", help="Recompute intermediate files even if cached")
    parser.add_argument("--compact", action="store_true", help="Print compact JSON")
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] = sys.argv[1:]) -> int:
    args = parse_args(argv)
    audio_path = args.audio_path.expanduser().resolve()
    if not audio_path.is_file():
        raise FileNotFoundError(audio_path)

    work_root = args.work_dir.expanduser().resolve()
    result = extract_metrics(audio_path, work_root, force=args.force)
    if args.compact:
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        raise SystemExit(1)
