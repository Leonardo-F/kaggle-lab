# 统一离线模拟器构建

下载 [simulators.html](../simulators.html) 到本地后，用浏览器打开并选择赛题。页面将两个赛题原始离线 HTML 完整嵌入，首次切换时载入；不需要启动服务器或联网。原始赛题页面仍可单独使用。

- 正方形装箱使用 `competitions/squares-in-squares/simulator/SquarePackingStudio-standalone.html`，包含已认证的布局数据。该页面通过 `competitions/squares-in-squares/simulator/build_standalone.py` 从赛题源码和当前认证 CSV 生成。
- Santa 原始页面位于 `competitions/santa-2026/src/simulator.html`。自定义题由网页内置的 JavaScript 求解，Python 独立算法的输出可导入页面回放。
- Google 量子赛题目前没有网页模拟器；请使用该赛题 README 中的命令行入口。

## 更新

修改装箱模拟器源码、认证结果或布局后先生成装箱单文件，然后更新统一文件：

```bash
python competitions/squares-in-squares/simulator/build_standalone.py
python web/build/build.py
python -m unittest discover -s web/tests -p 'test_*.py' -v
```

修改 Santa 原始 HTML 后运行后两条命令。CI 会检查嵌入内容是否是当前版本；修改了原始 HTML 却没更新统一文件时，检查会失败。

## Santa 独立版本回放与审核

在 Santa 页导入官方题目 CSV 与相应槽位的版本程序 CSV。导入文件时会显示该 CSV 的总指令数、覆盖题数、未知题号、无法解析的程序和未提供程序的题数；选同一题号可比较各版本的实际步数、合法性和计算图规模（唯一中间值、共享值、重算步），查看逐步寄存器状态，并复制当前程序 JSON。文件读取与 BigInt 回放在本地完成。

V1–V8 是已归档结果的历史回放槽位，与当前 Python 模块无关。页面还可以添加**会话内**自定义结果标签（1–40 字符，不能与已有标签重复），导入自己的 CSV 参与同题比较；自定义槽位可移除，数据不保存、不上传。默认 V1–V8 槽位不能删除。内嵌的 JavaScript 自定义题求解器是教学实现，不是当前 Python V8。

`santa-review.json` 是人工审核记录，分两部分：

- `solver.current_version` 与 `solver.source_sha256`：当前 CLI 发布标识，以及 `graph_solver.py`、`checkpoint.py`、`verify.py` 和 `algorithms/` 下全部 `.py` 文件的真实 SHA-256。`build.py` 用 AST 读取版本常量，不执行求解器。
- `independent_replay.versions`：历史 CSV 回放槽位，必须与模拟器 `data-versions` 完全一致；不根据 Python 文件名推断。

修改 Santa 求解入口、验证器或算法模块后，先重放/核对受影响的历史 CSV，运行测试，再显式刷新审核：

```bash
node --test competitions/santa-2026/tests/test_replay.cjs
python -m unittest discover -s competitions/santa-2026/tests -v
python web/build/build.py --refresh-santa-review   # 只更新源码指纹，保留历史槽位
python web/build/build.py
python web/build/build.py --check
```

普通 `build` 和 `--check` 不会接受新指纹，也不会自动改写 `santa-review.json`；源码增删改、版本常量与审核不一致、槽位列表与模拟器不一致时都会失败。最佳成绩不在这里重复记录，以 `competitions/santa-2026/submissions/latest.json` 和对应报告为准。

## Santa 互动报告

报告正文唯一来源是 `competitions/santa-2026/docs/algorithm-evolution.md`，页面框架和原有互动组件在 `docs/report_template.html`。构建脚本把 Markdown 渲染为 HTML、在构建期把数学公式转成离线 MathML，并内嵌图表与模拟器：

```bash
python -m pip install -r competitions/santa-2026/docs/requirements-docs.txt
python competitions/santa-2026/docs/build_report.py
python competitions/santa-2026/docs/build_report.py --check
```

构建依赖固定为 `Markdown==3.10.2` 与 `latex2mathml==3.81.1`；两者只在构建时使用，生成的报告不依赖网络、CDN 或客户端渲染器。输出路径固定为 `competitions/santa-2026/Santa-2026-Interactive-Report.html`，`--output` 可写到临时路径。
