# A Diagnostic Evaluation Framework for AI-Generated Cover Songs

Code and data tables for the paper **"A Diagnostic Evaluation Framework for AI-Generated Cover Songs Using Music-Theoretic and Acoustic Features"** ([arXiv:2607.19688](https://arxiv.org/abs/2607.19688)). The pipeline pairs expert listening scores with MIR features to diagnose melody, harmony, key stability, style match, and production quality across 30 generated samples from 6 generation systems.

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
  spearman_table.png
  loo_confusion_matrix.png
  loo_binary_confusion_matrix.png
  bootstrap_delta.png
  daw_spectrum_examples/
audio_examples/
```

`audio_examples/` and `figures/daw_spectrum_examples/` are placeholders for optional demo material. This repository does not include raw audio for copyright reasons.

## Environment

```bash
pip install -r requirements.txt
```

The scripts also require `ffmpeg` and a working Python environment supported by Demucs and basic-pitch.

## Path A — Reproduce the paper analysis (no audio, no scoring needed)

The shipped `features/extracted_features.csv` and `data/annotations/evaluation_scores.csv` are enough to reproduce every figure and statistic. **You do not need any audio or your own expert scores for this path.**

```bash
python scripts/06_spearman_analysis.py   # figures/spearman_table.csv/.png
python scripts/07_rule_diagnostic.py     # features/diagnostic_thresholds.json + LOO summaries
python scripts/08_bootstrap_ci.py        # figures/bootstrap_ci.csv, bootstrap_delta.png/.pdf
```

`scripts/06_spearman_analysis.py` reads `features/extracted_features.csv` directly when it exists (otherwise it merges the D1, D2/D3, and D5 tables). `scripts/07_rule_diagnostic.py` learns per-metric diagnostic thresholds and validates the resulting rules against a majority-class baseline with leave-one-out cross-validation. `scripts/08_bootstrap_ci.py` computes paired bootstrap confidence intervals for the rule-vs-baseline deltas.

## Path B — Analyze your own audio

Feature extraction and diagnosis with the published thresholds do not require expert scores. Correlation analysis and comparison with human judgment do.

### B1. Extract features

The following commands extract the nine MIR/acoustic metrics:

```bash
bash scripts/01_demucs_separate.sh audio separated
python scripts/02_basic_pitch.py --separated-dir separated/htdemucs_ft --midi-dir midi
python scripts/03_extract_d1.py   --midi-dir midi  --output features/d1_features.csv
python scripts/04_extract_d2d3.py --midi-dir midi  --output features/d2d3_features.csv
python scripts/05_extract_d5.py   --audio-dir audio --output features/d5_features.csv
```

Feature tables use the bare filename stem (for example, `song1`). WAV, MP3, FLAC, and M4A inputs can therefore be joined as long as the audio and MIDI files for a sample share the same stem.

### B2. Apply the published diagnostic thresholds

`scripts/09_diagnose.py` assigns a severity to D1, D2, D3, and D5 for each cover: `0` acceptable, `1` warning, or `2` severe. D4 is omitted because the pipeline has no objective metric for style matching.

First merge the three tables from B1 on `filename` into one feature table, called `features/my_features.csv` below. Then run:

```bash
python scripts/09_diagnose.py \
  --features features/my_features.csv \
  --out figures/diagnosis_labels.csv
```

By default, the thresholds are learned from the paper's data. The labels are listening cues, not quality scores: in the 30-sample evaluation, the rules did not significantly outperform a majority-class baseline. A `0` can also mean that no metric was conclusive, rather than that the dimension is confirmed to be error-free.

### B3. Analyze features against your own ratings

To calculate correlations or learn and validate thresholds on another dataset, provide integer ratings from 1 (worst) to 5 (best). The annotation file has this schema:

```csv
filename,D1,D2,D3,D4,D5
song1,4,3,5,2,4
song2,2,1,3,4,2
```

Use the same stem in the annotation and feature tables. `scripts/06_spearman_analysis.py` reports unmatched samples on stderr. To keep the shipped table unchanged, use a separate path for your combined features:

```bash
python scripts/06_spearman_analysis.py \
  --annotations data/annotations/my_scores.csv \
  --features features/my_features.csv
python scripts/07_rule_diagnostic.py \
  --annotations data/annotations/my_scores.csv \
  --features features/my_features.csv
python scripts/08_bootstrap_ci.py \
  --annotations data/annotations/my_scores.csv \
  --features features/my_features.csv
```

If `features/my_features.csv` does not exist, script `06` builds it from `d1_features.csv`, `d2d3_features.csv`, and `d5_features.csv` in the same directory.

### B4. Compare automatic labels with your ratings

Pass your annotations to `09_diagnose.py` to produce a per-sample comparison and an agreement summary:

```bash
python scripts/09_diagnose.py \
  --features features/my_features.csv \
  --annotations data/annotations/my_scores.csv \
  --compare-out figures/diagnosis_vs_human.csv \
  --compare-summary figures/diagnosis_vs_human_summary.csv
```

The script maps ratings of 4–5 to `0`, 3 to `1`, and 1–2 to `2`, then reports agreement by dimension. With the command above, diagnosis thresholds still come from the published dataset; `--annotations` supplies only the comparison labels. Use scripts `07` and `08` to evaluate thresholds learned from your own ratings with leave-one-out validation and paired bootstrap confidence intervals.

## Result summary

In the 30-sample analysis, LLR has the clearest relationship with expert melody scores (`rho = -0.429`, `p = 0.018`). KCR follows the expected negative direction for key consistency, although it is not significant in this small sample. The production metrics are weakly correlated with D5, which is expected because D5 includes both signal-level mix quality and arrangement completeness.

The rule-based diagnosis is deliberately reported as a diagnostic aid rather than a classifier: under leave-one-out validation the learned thresholds do not significantly outperform a majority-class baseline (`figures/bootstrap_ci.csv`), and for the overall 3-class setting the baseline is in fact ahead (delta `-0.125`, 95% CI `[-0.233, -0.017]`). Harmonic progression (D2) and arrangement/production (D5) carry the highest expert error rates, while key consistency (D3) is comparatively reliable.

These results support the paper's main claim: low-level acoustic features work well as diagnostic cues that localize specific issues, but they cannot replace expert musical judgment for harmonic function, style consistency, and arrangement-level assessment.

## Citation

If you use this pipeline, please cite:

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
