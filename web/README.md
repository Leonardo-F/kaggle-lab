# 网页入口

本目录集中存放可在浏览器中打开的页面：

- [interactive.html](interactive.html)：赛题互动页，只汇总正方形装箱与 Santa 2026 两个赛题，通过 iframe 引用各自原始 HTML；支持 `#squares` / `#santa`。
- [simulators.html](simulators.html)：统一离线模拟器，单文件嵌入两个赛题的模拟器，由 [build/build.py](build/build.py) 生成。
- [build/README.md](build/README.md)：统一模拟器与 Santa 互动报告的构建、审核和更新说明。
- [tests/](tests/)：统一模拟器构建一致性与互动页结构测试。

Santa 互动报告（`../competitions/santa-2026/Santa-2026-Interactive-Report.html`）由 `competitions/santa-2026/docs/build_report.py` 从学习正文 `algorithm-evolution.md` 生成，公式在构建期转为离线 MathML，图表与模拟器内嵌。修改正文、图表或模拟器后重建并运行 `--check`，命令见 [build/README.md](build/README.md)。报告的构建测试位于 `competitions/santa-2026/tests/test_report.py`。

Google 量子电路赛题目前没有网页报告或模拟器，使用该赛题 README 中的命令行入口。

互动页需要与仓库中的原始 HTML 一起打开；统一模拟器可以单独下载使用。
