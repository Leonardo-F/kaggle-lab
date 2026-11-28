# Santa 2026 提交 CSV

本目录保留独立求解版本与一份独立后处理混合归档，均可入库（独立 CSV 约 2.5–4 MB）。文件只含题号和我们自产的指令程序，不含官方题目数据。

| 文件 | 类型 | 本地验证步数 |
| --- | --- | ---: |
| `elf-calculator-independent-v10-score-164306.csv` | **当前独立 V10 Full** | **164,306** |
| `elf-calculator-independent-v9-score-175604.csv` | 独立 V9（历史，可用 `--version v9` 重跑） | 175,604 |
| `elf-calculator-independent-v8-score-194444.csv` | 独立 V8 Final（历史） | 194,444 |
| `elf-calculator-independent-v7-score-198388.csv` | 独立 V7（历史） | 198,388 |
| `elf-calculator-merged-v8-v9-score-174884.csv` | V8+V9 混合归档（非算法版本） | 174,884 |

命名规则：`elf-calculator-independent-<版本>-score-<本地验证步数>.csv`；混合归档为 `elf-calculator-merged-v8-v9-score-<步数>.csv`。分数写在文件名里，不同结果不会重名，也不会覆盖旧文件；旧版本按同一规则并存，方便逐题对照。

`latest.json` 是**当前可下载、已验证的独立发布指针**，现在指向 **V10 Full**（164,306 步、1,000/1,000 题通过独立验证、最长 349、输出 SHA-256 `171e6e00…`）。它不指向混合归档：174,884 是两份独立结果逐题取短后的后处理结果，不是独立算法版本，也不进入正式版本曲线。

当前算法 V11 的研究成绩是 **158,955**（1,000/1,000 本地验证、最长 348），但原研究交付没有正式提交 CSV；`docs/reports/v11.json` 以 `artifact_status: "report-only"` 记录它，构建器会拒绝把它当作可下载最佳。V8–V11 归档择优 **158,585** 同样只有验证记录（`docs/v11/merged_validation.json`），不进入本目录。

V10 CSV 由用户交付的 Linux/GCC 研究运行生成；本仓库用 `src/verify.py` 对官方 1,000 题做了全量回放，确认 1,000/1,000 合法、164,306 步。本次合入没有重新跑完整 1,000 题，因此 `latest.json` 指向的是**已验证的研究结果**，不是本机全量重解结果；本机独立重解的证据见 [v10.json](../docs/reports/v10.json) 与 [逐题指标](../docs/reports/v10-full1000-metrics.csv)。

混合归档必须由独立后处理工具从两份独立 CSV 重新生成并独立验证，不能作为求解输入：

```bash
python src/merge_submissions.py data/puzzles.csv \
  submissions/elf-calculator-independent-v8-score-194444.csv \
  submissions/elf-calculator-independent-v9-score-175604.csv \
  -o /tmp/v8-v9-merged.csv --expect-score 174884
python src/verify.py data/puzzles.csv /tmp/v8-v9-merged.csv
```

`../docs/reports/` 保存每次全量复跑的认证报告（题数、最长程序、来源哈希、阶段分数和命令）；V10 的报告是 `../docs/reports/v10.json`，V9 的报告是 `../docs/reports/v9.json`，混合归档是 `../docs/reports/v8-v9-merged.json`，原始研究交接证据在 `../docs/reports/v9-stage2-ablation.json`。

## 历史版本

263,575 到 270,771 的 9 份 `elf-calculator-score-*.csv` 已移出工作区，原文保存在提交 `64db409` 中，需要时按原名取回：

```bash
git show 64db409:competitions/santa-2026/submissions/elf-calculator-score-263575.csv > /tmp/263575.csv
```
