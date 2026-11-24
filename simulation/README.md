# 统一离线模拟器

下载 `index.html` 到本地后，用浏览器打开并选择赛题。页面将两个赛题原始离线 HTML 完整嵌入，首次切换时载入；不需要启动服务器或联网。原始赛题页面仍可单独使用。

- 正方形装箱使用 `competitions/squares-in-squares/simulator/SquarePackingStudio-standalone.html`，包含已认证的布局数据。该页面通过 `competitions/squares-in-squares/simulator/build_standalone.py` 从赛题源码和当前认证 CSV 生成。
- Santa 使用 `competitions/santa-2026/simulator.html`。它的求解器是浏览器 JavaScript，与 `competitions/santa-2026/solve.py` 是分别维护的实现；浏览器没有直接执行 Python，不能保证结果或搜索能力一致。Python 批量求解与验证仍以赛题目录命令行程序为准。
- Google 量子赛题目前没有网页模拟器；请使用该赛题 README 中的命令行入口。

## 更新

修改装箱模拟器源码、认证结果或布局后先生成装箱单文件，然后更新统一文件：

```bash
python competitions/squares-in-squares/simulator/build_standalone.py
python simulation/build.py
python -m unittest discover -s simulation -p 'test_*.py' -v
```

修改 Santa 原始 HTML 后运行后两条命令。CI 会检查嵌入内容是否是当前版本；修改了原始 HTML 却没更新统一文件时，检查会失败。

Santa 的 Python 求解器更新时，构建会停止并要求检查网页求解器。请对照 Python 的算法和规则，评估并更新 JavaScript 实现，验证合法性和预期功能；确认完成后，更新 `santa-review.json` 的 `python_sha256` 为 `solve.py` 的 SHA-256，再重建。这个检查提醒维护者进行人工同步，并不证明两种实现完全一致或自动移植 Python。可用 `sha256sum competitions/santa-2026/solve.py` 计算哈希。

## Santa 独立版本回放

在 Santa 页导入官方题目 CSV 与相应槽位的版本程序 CSV。可对同题比较指令数与合法性，查看逐步寄存器状态，并复制当前程序 JSON。文件读取与 BigInt 回放在本地完成。Python 版本的复现命令见 [算法演进](../competitions/santa-2026/docs/algorithm-evolution.md)。

变更统一入口、验证器或算法模块后，核对离线 CSV 回放与版本列表。通过检查后同步 `santa-review.json` 的 `independent_replay` 版本列表和文件 SHA-256，再重建统一 HTML。自定义题继续使用浏览器的 JavaScript 求解器，原有 `python_sha256` 对应 `solve.py`。

```bash
node --test competitions/santa-2026/experiments/test_replay.cjs
python -m unittest discover -s competitions/santa-2026/experiments -v
```
