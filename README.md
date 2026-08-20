<div align="center">

# 🎵 A Diagnostic Evaluation Framework for AI-Generated Cover Songs

[![Paper](https://img.shields.io/badge/arXiv-2607.19688-b31b1b.svg)](https://arxiv.org/abs/2607.19688)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Code and released numerical data for the accompanying paper.

</div>

This repository pairs expert listening ratings with MIR features to study melody, harmony, key stability, style match, and arrangement/production quality across 30 generated covers from five source songs and six generation systems.

## Evaluation framework

| ID | Dimension | What is assessed |
| --- | --- | --- |
| D1 | Melodic pitch accuracy | Pitch accuracy, melodic contour, and salient wrong notes in the generated vocal melody |
| D2 | Harmonic progression | Harmonic progression quality and functional support for the vocal phrase structure |
| D3 | Key consistency | Tonal-center stability and unintended key drift |
| D4 | Style consistency | Match between the target style prompt and the generated arrangement |
| D5 | Arrangement and production quality | Instrument completeness, timbre quality, mix balance, and frequency coverage |

The public numerical ratings are in `data/annotations/evaluation_scores.csv`. The original annotation process also produced time-stamped listening notes, but those notes are not included in this repository.

## Objective metrics

The pipeline computes nine MIR/acoustic metrics. Raw study audio and copyrighted source material are not redistributed.

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

D4 remains expert-only because style matching is not represented by these low-level features. IKNR is used only as a coarse tonal proxy for D2; it is not a chord-function metric.

## Repository layout

```text
data/
  annotations/evaluation_scores.csv
  sample_list.csv
features/
  extracted_features.csv
  diagnostic_thresholds.json
scripts/
  01_demucs_separate.sh
  02_basic_pitch.py
  03_extract_d1.py
  04_extract_d2d3.py
  05_extract_d5.py
  06_spearman_analysis.py
  07_rule_diagnostic.py
  08_bootstrap_ci.py
  09_diagnose.py
figures/
  spearman_table.csv
  loo_accuracy_summary.csv
  loo_binary_accuracy_summary.csv
  loo_confusion_matrix.png
  loo_binary_confusion_matrix.png
  bootstrap_ci.csv
  bootstrap_delta.png/.pdf
```

`audio_examples/` and `figures/daw_spectrum_examples/` are placeholders for optional demo material.

## Environment

```bash
pip install -r requirements.txt
```

The extraction pipeline also requires `ffmpeg` and a working Python environment supported by Demucs and Basic Pitch.

## Reproduce the released analysis

The released ratings and extracted features are sufficient to reproduce the feature-correlation and rule-pilot analyses without the study audio:

```bash
python scripts/06_spearman_analysis.py
python scripts/07_rule_diagnostic.py
python scripts/08_bootstrap_ci.py
```

`06_spearman_analysis.py` reports the nine prespecified Spearman correlations. Its `p` column contains uncorrected p-values; no significance-star column is used. The paper treats these correlations as exploratory and uses a Bonferroni reference threshold of `0.05/9 = 0.0056` for the nine prespecified comparisons.

`07_rule_diagnostic.py` performs genuine leave-one-out evaluation. In each fold, one cover is held out, percentile cutpoints are re-estimated from the remaining 29 covers, and those cutpoints are applied only to the held-out sample. The full-sample `features/diagnostic_thresholds.json` is saved for later diagnosis of new data and is not used to generate the LOO predictions.

The fold-wise majority baseline in `07_rule_diagnostic.py` is estimated from the remaining 29 labels. `08_bootstrap_ci.py` uses a fixed full-sample majority baseline for the reported paired-bootstrap comparison. On the released dataset, the fold-wise and fixed-majority definitions produce identical baseline predictions for every dimension and setting.

`08_bootstrap_ci.py` reports percentile 95% paired-bootstrap confidence intervals for `delta = rule - baseline`. It does not report bootstrap-derived p-values. All 16 dimension-level intervals in the released analysis include zero, so the rule pilot provides no confirmed improvement over the majority baseline at `n = 30`.

## Analyze your own audio

### 1. Extract features

```bash
bash scripts/01_demucs_separate.sh audio separated
python scripts/02_basic_pitch.py --separated-dir separated/htdemucs_ft --midi-dir midi
python scripts/03_extract_d1.py   --midi-dir midi  --output features/d1_features.csv
python scripts/04_extract_d2d3.py --midi-dir midi  --output features/d2d3_features.csv
python scripts/05_extract_d5.py   --audio-dir audio --output features/d5_features.csv
```

Feature tables use filename stems, so WAV, MP3, FLAC, and M4A inputs can be joined when the audio and MIDI files share the same stem.

### 2. Apply the published thresholds

```bash
python scripts/09_diagnose.py \
  --features features/my_features.csv \
  --out figures/my_diagnosis_labels.csv
```

The labels are diagnostic cues, not validated quality scores. A label of `0` can mean that no available metric crossed a threshold; it does not establish that the dimension is error-free.

### 3. Compare features with your own ratings

Provide integer ratings from 1 (worst) to 5 (best):

```csv
filename,D1,D2,D3,D4,D5
song1,4,3,5,2,4
song2,2,1,3,4,2
```

Then run:

```bash
python scripts/06_spearman_analysis.py \
  --annotations data/annotations/my_scores.csv \
  --features features/my_features.csv \
  --output-csv figures/my_spearman_table.csv \
  --output-png figures/my_spearman_table.png

python scripts/07_rule_diagnostic.py \
  --annotations data/annotations/my_scores.csv \
  --features features/my_features.csv \
  --out-dir figures/my_run

python scripts/08_bootstrap_ci.py \
  --annotations data/annotations/my_scores.csv \
  --features features/my_features.csv \
  --out-dir figures/my_run
```

## Result summary

In the released 30-cover analysis, LLR produced the largest observed feature-rating correlation with D1 (`rho = -0.429`, uncorrected `p = 0.018`). No feature correlation met the Bonferroni reference threshold for nine prespecified comparisons. Key-related features were weak proxies, and the low-level loudness/spectral summaries did not explain arrangement quality.

The rule pilot is reported as an exploratory diagnostic aid rather than a standalone evaluator. All 16 dimension-level paired-bootstrap 95% intervals for accuracy or weighted-F1 differences included zero. The pooled overall summaries are descriptive and are not treated as additional independent dimension-level tests.

Six released covers have acceptable key consistency (`D3 >= 4`) together with severe harmonic-progression ratings (`D2 <= 2`), supporting the distinction between tonal-center stability and harmonic correctness.

### Statistical scope

The 30 covers are nested within only five source songs. The current Spearman calculations and paired bootstrap operate at the cover-sample level rather than modeling source-song identity. Correlations may therefore contain both sample-level and shared song-level variation. Larger studies should include more source songs and use mixed-effects analysis or song-level resampling.

## Citation

```bibtex
@misc{liang2026coverdiagnosis,
  title = {A Diagnostic Evaluation Framework for AI-Generated Cover Songs Using Music-Theoretic and Acoustic Features},
  author = {Yingxin Liang},
  year = {2026},
  eprint = {2607.19688},
  archivePrefix = {arXiv},
  primaryClass = {cs.SD},
  url = {https://arxiv.org/abs/2607.19688}
}
```
