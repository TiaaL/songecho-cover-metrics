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

## Path B — Bring your own audio

You can run the pipeline on your own cover songs. There are two independent goals:

**B1. Extract objective features only — no expert scores required.** This gives you the nine MIR/acoustic metrics for your own audio, which you can inspect or compare across systems on their own:

```bash
bash scripts/01_demucs_separate.sh audio separated
python scripts/02_basic_pitch.py --separated-dir separated/htdemucs_ft --midi-dir midi
python scripts/03_extract_d1.py   --midi-dir midi  --output features/d1_features.csv
python scripts/04_extract_d2d3.py --midi-dir midi  --output features/d2d3_features.csv
python scripts/05_extract_d5.py   --audio-dir audio --output features/d5_features.csv
```

Feature-table `filename` values are the bare file stem (e.g. `song1`), so **any audio format works** — WAV, MP3, FLAC, or M4A all join correctly as long as a sample's audio and MIDI share the same stem.

**B2. Reproduce the correlation/diagnosis on your audio — this step, and only this step, needs expert scores.** The rule diagnosis and Spearman correlations relate features to human judgment, so they require a `data/annotations/evaluation_scores.csv` you fill in yourself. D1–D5 are integer expert listening ratings from 1 (worst) to 5 (best); there is no automatic scorer. The minimal schema is:

```csv
filename,D1,D2,D3,D4,D5
song1,4,3,5,2,4
song2,2,1,3,4,2
```

`filename` is matched to the feature tables by stem, so `song1` and `song1.mp3` refer to the same sample. With that file in place, run Path A's three commands (delete or point `--features` away from the shipped `features/extracted_features.csv` so your own features are used). `scripts/06_spearman_analysis.py` prints a warning to stderr and lists any samples that fail to join, so a filename mismatch never silently produces an empty result.

**B3. Get an automatic per-dimension diagnosis of your covers — no expert scores needed.** `scripts/09_diagnose.py` applies the rule thresholds (learned from the published paper data by default) to your feature table and writes a severity label per cover and per dimension: `0` acceptable, `1` warning, `2` severe.

```bash
python scripts/09_diagnose.py --features features/extracted_features.csv --out figures/diagnosis_labels.csv
```

Output columns are `filename, D1, D2, D3, D5` (D4 style-matching has no objective metric and is never diagnosed). This is fully automatic: audio in, diagnosis out. **It is an advisory signal, not a quality score** — on the paper's 30-sample evaluation the rules do not significantly beat a majority-class baseline (see *Result summary*), so treat the labels as cues that localize where to listen, not as verdicts. A dimension can read `0` because no metric was conclusive, which is not the same as "confirmed fine".

**B4. Check how well the automatic diagnosis matches your own listening.** If you *also* provide your own expert scores, `09_diagnose.py` lines up the automatic label against your human label for every cover and dimension, and reports the agreement rate:

```bash
python scripts/09_diagnose.py \
  --features features/extracted_features.csv \
  --annotations data/annotations/evaluation_scores.csv \
  --compare-out figures/diagnosis_vs_human.csv \
  --compare-summary figures/diagnosis_vs_human_summary.csv
```

Concretely: your 1–5 human ratings are folded to the same 0/1/2 severities, then compared cell by cell against the automatic labels; `figures/diagnosis_vs_human_summary.csv` reports the fraction that agree per dimension. This answers "can I trust the automatic diagnosis on *my* music?" — and it requires your own scores precisely because there is nothing to compare against otherwise. Note this default comparison is *whole-sample re-substitution* (optimistic, not cross-validated); the leave-one-out and bootstrap in `07`/`08` are the unbiased estimates.

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
