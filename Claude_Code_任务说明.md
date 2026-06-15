# Claude Code 任务说明

## 目标
构建一个 Python 脚本，输入一个 cover 音频文件路径，输出 10 个客观指标数值。

---

## 需要上传到 GitHub 的文件

### 必须上传（Claude Code 需要读）
1. `客观工具方案_定稿v3.md` — pipeline 的完整 spec，作为 source of truth
2. 本说明文件

### 需要准备但不上传到 repo（本地运行用）
- 30 个 cover 音频文件（.wav）
- 评分表（results.csv，手动维护，跑完指标后填入）

---

## 脚本需求

### 脚本 A：`extract_metrics.py`（Mac 上跑，9 个指标）

**输入：** 一个 cover 音频文件路径
**输出：** 打印 9 个指标数值（CSV 格式一行）

**流程：**
```
cover.wav
├→ Demucs (htdemucs_ft, --two-stems=vocals)
│   ├→ vocals.wav (mono)
│   │   └→ basic-pitch → vocals.mid
│   │       ├→ pretty_midi: LLR, PR, PS
│   │       └→ music21: IKNR, KC, KCR (固定10秒窗口)
│   └→ no_vocals.wav (保留,供脚本B使用)
├→ pyloudnorm (stereo, 原始采样率): LUFS, LRA
└→ librosa.spectral_contrast (内部转mono): SC
```

**9 个指标定义（严格按此实现）：**

| 指标 | 缩写 | 计算方式 | 数据源 |
|------|------|---------|--------|
| 大跳比例 | LLR | 相邻音符音程>7 semitones的比例 | vocals.mid |
| 音域范围 | PR | max(pitch) - min(pitch), 单位semitone | vocals.mid |
| 音程变化标准差 | PS | 所有相邻音程的std | vocals.mid |
| 调内音比例 | IKNR | pitch class属于检测调性音阶的比例 | vocals.mid |
| 调性置信度 | KC | music21 analyze('key').correlationCoefficient | vocals.mid |
| 调性变化率 | KCR | 相邻10秒窗口调性变化次数 / (窗口数-1) | vocals.mid |
| 综合响度 | LUFS | pyloudnorm ITU-R BS.1770-4 | 原始cover.wav (stereo) |
| 响度范围 | LRA | pyloudnorm loudness_range | 原始cover.wav (stereo) |
| 频谱对比度 | SC | librosa.spectral_contrast 全帧全频段均值 | 原始cover.wav (转mono) |

**KCR 实现细节：**
- 用固定 10 秒窗口切分（不用段落标注）
- 每个窗口内音符数 < 5 则跳过
- 对每个窗口独立做 music21 调性检测
- KCR = 相邻窗口调性变化次数 / max(窗口数-1, 1)

**LUFS/LRA 注意：**
- 用 soundfile.read() 读取，保留原始采样率和 stereo
- 不做任何预处理（不转mono、不resample）

**SC 注意：**
- librosa.load() 时 sr=None, mono=False
- 如果是 stereo 则内部 librosa.to_mono()
- spectral_contrast 后取 np.mean(contrast)

**输出格式：**
```
filename,LLR,PR,PS,IKNR,KC,KCR,LUFS,LRA,SC
song1_model1.wav,0.120,18,3.21,0.870,0.820,0.100,-11.2,8.5,19.3
```

**依赖：**
```
pip install librosa basic-pitch pretty-midi music21 scipy matplotlib pandas demucs pyloudnorm soundfile numpy
```

---

### 脚本 B：`extract_ikcr.py`（⚠️ Windows 上跑）

**输入：** Demucs 输出的 no_vocals.wav + 对应的 vocals.mid（用于调性检测）
**输出：** IKCR 值

**流程：**
```
no_vocals.wav → autochord.recognize() → 和弦序列
vocals.mid → music21 analyze('key') → 检测调性
→ 判断每个和弦根音是否在调内
→ IKCR = 调内和弦数 / 总和弦数
```

**实现：**
```python
import autochord
import music21

chords = autochord.recognize("no_vocals.wav")
score = music21.converter.parse("vocals.mid")
key = score.analyze('key')
key_obj = music21.key.Key(key.tonic.name, key.mode)
diatonic_roots = [p.name for p in key_obj.getScale().getPitches()[:-1]]

in_key = 0
total = 0
for start, end, label in chords:
    if label == 'N':
        continue
    root = label.split(':')[0]
    total += 1
    if root in diatonic_roots:
        in_key += 1
IKCR = in_key / max(total, 1)
```

**依赖（Windows）：**
```
pip install autochord music21
```

**⚠️ autochord 不支持 Mac (Apple Silicon)，必须在 Windows 上跑。**

**需要从 Mac 传到 Windows 的文件（每个样本2个）：**
- `no_vocals.wav`（Demucs 输出的伴奏轨）
- `vocals.mid`（basic-pitch 输出的 MIDI，用于调性检测）

---

### 脚本 C：`run_spearman.py`（Mac 上跑）

**输入：** results.csv（包含 D1-D5 评分 + 10 个指标）
**输出：** Spearman 相关表

```python
import pandas as pd
from scipy.stats import spearmanr

df = pd.read_csv("results.csv")
df['LUFS_dev'] = abs(df['LUFS'] - (-12))

correlations = [
    ('D1', 'LLR', 'neg'), ('D1', 'PS', 'neg'),
    ('D2', 'IKNR', 'pos'), ('D2', 'IKCR', 'pos'),
    ('D3', 'KC', 'pos'), ('D3', 'IKNR', 'pos'), ('D3', 'KCR', 'neg'),
    ('D5', 'LUFS_dev', 'neg'), ('D5', 'LRA', 'pos'), ('D5', 'SC', 'pos'),
]

for dim, metric, direction in correlations:
    rho, p = spearmanr(df[dim], df[metric])
    sig = '***' if p < 0.001 else '**' if p < 0.01 else '*' if p < 0.05 else 'n.s.'
    print(f"{dim} vs {metric}: rho={rho:.3f}, p={p:.3f} {sig} (expected {direction})")
```

---

## 文件结构

```
project/
├── extract_metrics.py      # 脚本A: Mac跑9个指标
├── extract_ikcr.py         # 脚本B: Windows跑IKCR
├── run_spearman.py         # 脚本C: Spearman分析
├── results.csv             # 汇总表（手动+脚本输出合并）
├── audio/                  # 30个cover音频（不上传GitHub）
│   ├── song1_model1.wav
│   └── ...
├── separated/              # Demucs输出（不上传GitHub）
│   └── htdemucs_ft/
│       └── song1_model1/
│           ├── vocals.wav
│           └── no_vocals.wav
├── midi/                   # basic-pitch输出（不上传GitHub）
│   └── song1_model1_vocals.mid
└── README.md
```

**上传 GitHub 的：** 脚本A/B/C + results.csv + README.md
**不上传 GitHub 的：** audio/ separated/ midi/（版权+文件太大）

---

## 验证标准

脚本写完后，先用 1 个样本跑通，检查：
- LLR 在 0-1 之间
- PR 在 10-40 之间（人声合理音域）
- IKNR 在 0.5-1.0 之间
- KC 在 0-1 之间
- KCR 在 0-1 之间
- LUFS 在 -20 到 -5 之间
- LRA 在 2-20 之间
- SC 在 10-30 之间（粗略范围）

数值明显超出范围 = 代码有bug，需排查。
