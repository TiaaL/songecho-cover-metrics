#!/usr/bin/env python3
"""Resume batch extraction for the 30 cover metric samples."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from cover_metrics import extract_metrics


AUDIO_DIR = Path("/Users/xy/Desktop/1/code/music/english")
WORK_DIR = Path(".cover_metrics_work")
RESULTS_DIR = Path("results")
PARTIAL_JSON = RESULTS_DIR / "cover_metrics_results.partial.json"
FINAL_JSON = RESULTS_DIR / "cover_metrics_results.json"
FINAL_CSV = RESULTS_DIR / "cover_metrics_results.csv"

CSV_FIELDS = [
    "filename",
    "LLR",
    "PR",
    "PS",
    "IKNR",
    "IKCR",
    "KC",
    "KCR",
    "LUFS",
    "LUFS_dev",
    "LRA",
    "SC",
    "global_key",
    "duration_sec",
    "note_count",
    "interval_count",
    "kcr_valid_windows",
]


def is_target_audio(path: Path) -> bool:
    return path.suffix.lower() in {".mp3", ".wav", ".flac", ".m4a"} and not path.stem.startswith("original_")


def load_partial() -> list[dict]:
    if not PARTIAL_JSON.exists():
        return []
    return json.loads(PARTIAL_JSON.read_text(encoding="utf-8"))


def save_json(path: Path, rows: list[dict]) -> None:
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(rows: list[dict]) -> None:
    with FINAL_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            metrics = row["metrics"]
            support = row["supporting_values"]
            writer.writerow(
                {
                    "filename": Path(row["audio_path"]).name,
                    "LLR": metrics["LLR"],
                    "PR": metrics["PR"],
                    "PS": metrics["PS"],
                    "IKNR": metrics["IKNR"],
                    "IKCR": metrics["IKCR"],
                    "KC": metrics["KC"],
                    "KCR": metrics["KCR"],
                    "LUFS": support["LUFS"],
                    "LUFS_dev": metrics["LUFS_dev"],
                    "LRA": metrics["LRA"],
                    "SC": metrics["SC"],
                    "global_key": row["global_key"],
                    "duration_sec": row["duration_sec"],
                    "note_count": support["note_count"],
                    "interval_count": support["interval_count"],
                    "kcr_valid_windows": support["kcr_valid_windows"],
                }
            )


def main() -> int:
    RESULTS_DIR.mkdir(exist_ok=True)
    rows = load_partial()
    done = {Path(row["audio_path"]).name for row in rows}
    audio_files = sorted(path for path in AUDIO_DIR.iterdir() if is_target_audio(path))

    print(f"found={len(audio_files)} done={len(done)} remaining={len(audio_files) - len(done)}", flush=True)
    for index, audio_path in enumerate(audio_files, start=1):
        if audio_path.name in done:
            print(f"[{index}/{len(audio_files)}] skip {audio_path.name}", flush=True)
            continue
        print(f"[{index}/{len(audio_files)}] start {audio_path.name}", flush=True)
        result = extract_metrics(audio_path.resolve(), WORK_DIR.resolve(), force=False)
        rows.append(result)
        rows.sort(key=lambda item: Path(item["audio_path"]).name)
        save_json(PARTIAL_JSON, rows)
        write_csv(rows)
        done.add(audio_path.name)
        print(f"[{index}/{len(audio_files)}] done {audio_path.name}", flush=True)

    save_json(FINAL_JSON, rows)
    write_csv(rows)
    print(f"complete rows={len(rows)} json={FINAL_JSON} csv={FINAL_CSV}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
