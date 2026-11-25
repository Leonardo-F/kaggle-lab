# 网页入口

本目录集中存放可在浏览器中打开的页面：

- [interactive.html](interactive.html)：赛题互动页，只汇总正方形装箱与 Santa 2026 两个赛题，通过 iframe 引用各自原始 HTML。
- [simulators.html](simulators.html)：统一离线模拟器，单文件嵌入两个赛题的模拟器，由 [simulation/build.py](simulation/build.py) 生成。
- [simulation/README.md](simulation/README.md)：统一模拟器的更新与测试说明。

Google 量子电路赛题目前没有网页报告或模拟器，使用该赛题 README 中的命令行入口。

互动页需要与仓库中的原始 HTML 一起打开；统一模拟器可以单独下载使用。
