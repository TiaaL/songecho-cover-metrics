# cover_metrics

输入一个 cover 音频，输出客观指标（方案见 `客观工具方案_定稿v3.md`）。

## 脚本

| 文件 | 平台 | 用途 |
|------|------|------|
| `extract_metrics.py` | Mac | 输出 9 个 Mac 侧指标 CSV：LLR、PR、PS、IKNR、KC、KCR、LUFS、LRA、SC |
| `extract_ikcr.py` | Windows | 输入 `no_vocals.wav` + `vocals.mid`，输出 IKCR |
| `run_spearman.py` | Mac/Windows | 输入 `results.csv`，输出 Spearman 相关表 |
| `cover_metrics.py` | Mac/Windows | 底层完整 JSON 版本，供调试和复用 |

## Mac：跑 9 个指标

安装依赖：

```bash
pip install -r requirements-mac.txt
```

运行：

```bash
python extract_metrics.py /path/to/cover.wav
```

底层 JSON 调试：

```bash
python cover_metrics.py /path/to/cover.wav          # 输出格式化 JSON
python cover_metrics.py cover.wav --compact         # 单行 JSON
python cover_metrics.py cover.wav --force           # 忽略缓存重算中间文件
python cover_metrics.py cover.wav --work-dir DIR    # 指定中间文件目录（默认 .cover_metrics_work）
```

Pipeline：Demucs（htdemucs_ft，--two-stems vocals）→ ffmpeg 转 mono → basic-pitch → 各指标。
中间文件按音频签名缓存，重复跑同一文件不会重算。

## Windows：跑 IKCR

Windows 需要的仓库文件：

- `extract_ikcr.py`
- `requirements-windows.txt`

从 Mac 拷到 Windows 的每个样本文件：

- Demucs 输出的 `no_vocals.wav`
- basic-pitch 输出的 `vocals.mid`

安装依赖：

```bash
pip install -r requirements-windows.txt
```

运行：

```bash
python extract_ikcr.py separated/htdemucs_ft/song1_model1/no_vocals.wav midi/song1_model1_vocals.mid
```

`audio/`、`separated/`、`midi/` 不上传 GitHub，需要本地自行准备或从 Mac 拷贝。

## 10 个指标

| 缩写 | 含义 | 维度 | 数据源 | 工具 |
|------|------|------|--------|------|
| LLR | 大跳比例（音程>7） | D1 | vocals.mid | pretty_midi |
| PR | 音域范围 | D1 | vocals.mid | pretty_midi |
| PS | 音程变化标准差 | D1 | vocals.mid | pretty_midi |
| IKNR | 调内音比例 | D2/D3 | vocals.mid | music21 |
| IKCR | 调内和弦比例 | D2 | no_vocals.wav | autochord+music21 |
| KC | 调性置信度 | D3 | vocals.mid | music21 |
| KCR | 调性变化率（固定 10 秒窗口） | D3 | vocals.mid | music21 |
| LUFS_dev | 综合响度偏差 \|LUFS-(-12)\| | D5 | 原始 audio(stereo) | pyloudnorm |
| LRA | 响度范围 | D5 | 原始 audio(stereo) | pyloudnorm |
| SC | 频谱对比度 | D5 | 原始 audio(转 mono) | librosa |

KCR 用固定 10 秒不重叠窗口（非段落标注）。

## 平台说明

**IKCR 依赖 autochord，autochord 不支持 Mac (Apple Silicon)。**
- Mac 上：IKCR 输出 `null`（`status: skipped`），其余 9 个指标正常。
- Windows 上：`pip install autochord` 后 IKCR 自动计算。

30 个样本的 IKCR 列需在 Windows 上单独补跑。

## 相关分析

手动合并 D1-D5 评分、Mac 侧 9 个指标和 Windows 侧 IKCR 后，写入 `results.csv`，再运行：

```bash
python run_spearman.py results.csv
```

## 输出示例

```json
{
  "audio_path": "...",
  "global_key": "C minor",
  "duration_sec": 209.52,
  "supporting_values": { "LUFS": -15.66, "note_count": 517, ... },
  "metrics": {
    "LLR": 0.277, "PR": 65.0, "PS": 8.824,
    "IKNR": 0.988, "IKCR": null, "KC": 0.728, "KCR": 0.5,
    "LUFS_dev": 3.66, "LRA": 2.21, "SC": 22.46
  }
}
```

出错时向 stderr 打印 `{"error": "..."}` 并以退出码 1 结束。
