# AI Cover Song Evaluation Demo

This repository contains a reproducible diagnostic pipeline for evaluating AI-generated cover songs in a DAFx26 demo submission. It combines expert listening scores with lightweight MIR features to inspect melody, harmony, key consistency, style matching, and production quality across 30 generated samples.

## Evaluation Framework

The demo uses five expert-rated dimensions:

| ID | Dimension | What is assessed |
| --- | --- | --- |
| D1 | Melody plausibility | Pitch accuracy, melodic contour, and solo coherence |
| D2 | Harmonic plausibility | Chord progression quality and melody-harmony compatibility |
| D3 | Key consistency | Tonal-center stability and unintended key drift |
| D4 | Style consistency | Match between the prompt style and the generated arrangement |
| D5 | Arrangement and production quality | Instrument completeness, timbre quality, mix balance, and frequency coverage |

Scores are stored in `data/annotations/evaluation_scores.csv`. The full listening notes are intentionally not required to reproduce the numeric analysis.

## Objective Metrics

The released pipeline computes nine objective metrics. It does not include raw audio, copyrighted material, Windows-only scripts, or any autochord code.

| Metric | Dimension | Definition | Expected relation |
| --- | --- | --- | --- |
| LLR | D1 | Large-leap ratio in the transcribed vocal melody | Negative |
| PR | D1 | Vocal pitch range in semitones | Descriptive |
| PS | D1 | Standard deviation of adjacent melodic intervals | Negative |
| IKNR | D2/D3 | Ratio of vocal notes inside the detected global key | Positive |
| KC | D3 | `music21` key-analysis confidence | Positive |
| KCR | D3 | Key-change rate across fixed 10-second vocal-MIDI windows | Negative |
| LUFS | D5 | Integrated loudness of the stereo mix | Used as `abs(LUFS + 12)` |
| LRA | D5 | Loudness range | Positive |
| SC | D5 | Mean spectral contrast | Positive |

D4 is kept as an expert-only dimension because style matching requires semantic listening beyond the scope of these MIR features.

## Repository Layout

```text
data/
  annotations/evaluation_scores.csv
  sample_list.csv
features/
  extracted_features.csv
scripts/
  01_demucs_separate.sh
  02_basic_pitch.py
  03_extract_d1.py
  04_extract_d2d3.py
  05_extract_d5.py
  06_spearman_analysis.py
figures/
  spearman_table.png
  daw_spectrum_examples/
audio_examples/
```

`audio_examples/` and `figures/daw_spectrum_examples/` are placeholders for optional demo material. Raw audio is not included in this repository for copyright reasons.

## Environment

```bash
pip install -r requirements.txt
```

The scripts also require `ffmpeg` and a working Python environment supported by Demucs and basic-pitch.

## Reproduce

Place local evaluation audio files under `audio/`. File names should match `data/sample_list.csv`.

```bash
bash scripts/01_demucs_separate.sh audio separated
python scripts/02_basic_pitch.py --separated-dir separated/htdemucs_ft --midi-dir midi
python scripts/03_extract_d1.py --midi-dir midi --output features/d1_features.csv
python scripts/04_extract_d2d3.py --midi-dir midi --output features/d2d3_features.csv
python scripts/05_extract_d5.py --audio-dir audio --output features/d5_features.csv
python scripts/06_spearman_analysis.py
```

`scripts/06_spearman_analysis.py` merges the D1, D2/D3, and D5 feature tables into `features/extracted_features.csv` if that file is not already present, then writes `figures/spearman_table.csv` and `figures/spearman_table.png`.

## Result Summary

The included 30-sample analysis shows that LLR has the clearest relationship with expert melody scores (`rho = -0.429`, `p = 0.018`). KCR follows the expected negative direction for key consistency but is not significant in this small sample. The production metrics are weakly correlated with D5, which is expected because D5 includes both signal-level mix quality and higher-level arrangement completeness.

These results support the demo's main claim: automatic features are useful as diagnostic cues, but expert listening remains necessary for harmonic function, style matching, and arrangement-level judgments.

## Citation

If you use this demo pipeline, please cite:

```bibtex
@misc{ai_cover_evaluation_demo_2026,
  title = {AI Cover Song Evaluation Demo: Objective Diagnostics and Expert Ratings},
  author = {Anonymous},
  year = {2026},
  note = {DAFx26 demo submission}
}
```
