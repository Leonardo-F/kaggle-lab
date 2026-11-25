# 统一离线模拟器

下载 `../simulators.html` 到本地后，用浏览器打开并选择赛题。页面将两个赛题原始离线 HTML 完整嵌入，首次切换时载入；不需要启动服务器或联网。原始赛题页面仍可单独使用。

- 正方形装箱使用 `competitions/squares-in-squares/simulator/SquarePackingStudio-standalone.html`，包含已认证的布局数据。该页面通过 `competitions/squares-in-squares/simulator/build_standalone.py` 从赛题源码和当前认证 CSV 生成。
- Santa 原始页面位于 `competitions/santa-2026/src/simulator.html`。自定义题由网页内置的 JavaScript 求解，Python 独立算法的输出可导入页面回放。
- Google 量子赛题目前没有网页模拟器；请使用该赛题 README 中的命令行入口。

## 更新

修改装箱模拟器源码、认证结果或布局后先生成装箱单文件，然后更新统一文件：

```bash
python competitions/squares-in-squares/simulator/build_standalone.py
python web/simulation/build.py
python -m unittest discover -s web/simulation -p 'test_*.py' -v
```

修改 Santa 原始 HTML 后运行后两条命令。CI 会检查嵌入内容是否是当前版本；修改了原始 HTML 却没更新统一文件时，检查会失败。

## Santa 独立版本回放

在 Santa 页导入官方题目 CSV 与相应槽位的版本程序 CSV。导入文件时会显示该 CSV 的总指令数；选同一题号可比较各版本的实际步数、合法性和计算图规模（唯一中间值、共享值、重算步），查看逐步寄存器状态，并复制当前程序 JSON。文件读取与 BigInt 回放在本地完成。Python 版本的复现命令见 [算法演进](../../competitions/santa-2026/docs/algorithm-evolution.md)。

变更统一入口、验证器或算法模块后，核对离线 CSV 回放与版本列表。通过检查后同步 `santa-review.json` 的 `independent_replay` 版本列表和文件 SHA-256，再重建统一 HTML。文件路径以 Santa 的 `src/` 为基准。

```bash
node --test competitions/santa-2026/tests/test_replay.cjs
python -m unittest discover -s competitions/santa-2026/tests -v
```
