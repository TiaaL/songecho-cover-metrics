# Time-Stamped Musical Error Diagnosis for AI-Generated Cover Songs

This repository provides the code and data tables for evaluating AI-generated cover songs, accompanying a technical report. The pipeline pairs expert listening scores with MIR features to diagnose melody, harmony, key stability, style match, and production quality across 30 generated samples from 6 generation systems.

## Evaluation framework

The evaluation uses five expert-rated dimensions:

| ID | Dimension | What is assessed |
| --- | --- | --- |
| D1 | Melodic pitch accuracy | Pitch accuracy, melodic contour, and salient wrong notes in the generated vocal melody |
| D2 | Harmonic progression | Harmonic progression quality and functional support for the vocal phrase structure |
| D3 | Key consistency | Tonal-center stability and unintended key drift |
| D4 | Style consistency | Match between the target style prompt and the generated arrangement |
| D5 | Arrangement and production quality | Instrument completeness, timbre quality, mix balance, and frequency coverage |

The numeric scores are in `data/annotations/evaluation_scores.csv`. You do not need the full listening notes to reproduce the analysis.

## Objective metrics

The pipeline computes nine objective metrics. It does not include raw audio, copyrighted material, or automated chord-recognition components.

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

We keep D4 as an expert-only dimension because style matching requires semantic listening beyond these MIR features.

## Repository layout

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

`audio_examples/` and `figures/daw_spectrum_examples/` are placeholders for optional demo material. This repository does not include raw audio for copyright reasons.

## Environment

```bash
pip install -r requirements.txt
```

The scripts also require `ffmpeg` and a working Python environment supported by Demucs and basic-pitch.

## Reproducing the analysis

Place local evaluation audio files under `audio/`. File names should match `data/sample_list.csv`.

```bash
bash scripts/01_demucs_separate.sh audio separated
python scripts/02_basic_pitch.py --separated-dir separated/htdemucs_ft --midi-dir midi
python scripts/03_extract_d1.py --midi-dir midi --output features/d1_features.csv
python scripts/04_extract_d2d3.py --midi-dir midi --output features/d2d3_features.csv
python scripts/05_extract_d5.py --audio-dir audio --output features/d5_features.csv
python scripts/06_spearman_analysis.py
```

`scripts/06_spearman_analysis.py` merges the D1, D2/D3, and D5 feature tables into `features/extracted_features.csv` when that file is missing. It then writes `figures/spearman_table.csv` and `figures/spearman_table.png`.

## Result summary

In the 30-sample analysis, LLR has the clearest relationship with expert melody scores (`rho = -0.429`, `p = 0.018`). KCR follows the expected negative direction for key consistency, although it is not significant in this small sample. The production metrics are weakly correlated with D5, which is expected because D5 includes both signal-level mix quality and arrangement completeness.

These results support the demo's main claim: automatic features work well as diagnostic cues, while expert listening is still needed for harmonic function, style consistency, and arrangement-level judgments.

## Citation

If you use this demo pipeline, please cite:

```bibtex
@misc{liang2026coverdiagnosis,
  title = {Time-Stamped Musical Error Diagnosis for AI-Generated Cover Songs: A Demo System},
  author = {Yingxin Liang},
  year = {2026},
  note = {Technical report}
}
```
