# Santa 2026 提交 CSV

本目录只保留当前两个独立版本的完整 CSV。CSV 体积大且由官方题目派生，按根目录 `.gitignore` 的约定不入库；机器上保留文件，仓库用同一目录的 `latest.json` 记录成绩索引。

| 文件 | 版本 | 本地验证步数 |
| --- | --- | ---: |
| `elf-calculator-independent-v7.csv` | V7 | 198,388 |

V8 完成后以 `elf-calculator-independent-v8.csv` 加入，V7 保留用作对照。

`latest.json` 指向当前最佳版本，`../docs/reports/` 保存每次全量复跑的认证报告（题数、最长程序、来源哈希和命令）。

## 历史版本

263,575 到 270,771 的 9 份 `elf-calculator-score-*.csv` 已移出工作区，原文保存在提交 `64db409` 中，需要时按原名取回：

```bash
git show 64db409:competitions/santa-2026/submissions/elf-calculator-score-263575.csv > /tmp/263575.csv
```
