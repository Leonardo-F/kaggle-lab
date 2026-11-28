# Santa 2026 V11 等价重构与教学系统同步 · 验收记录

本文件记录 `refactor/santa-current-solver` 分支上的工程重构：基线、改动、测试、独立求解对照、执行偏差和未完成事项。它是**工程验收**，不是新的数学算法版本，也不进入 V1–V11 的独立成绩曲线。

## 1. 基线与分支

| 项 | 值 |
|---|---|
| 仓库 | `Leonardo-F/kaggle-lab` |
| 基线 main | `01567f3912f56df937e46ff99dde56a2036cdc55`（V11 冻结研究已合入后的 main） |
| 重构分支 | `refactor/santa-current-solver`（从上述 main 创建） |
| 对照 worktree | `.worktrees/santa-baseline`，detached HEAD 指向同一 SHA |
| 远程写入 | **无**。未 push、未创建 PR、未改远程 main、未改其他竞赛 |

基线状态下工作区干净；旧 main 仍包含 V9/V10 运行代码、V11 转接层与 `v11_frozen_fulltest/`，因此本次按交接包 `MIGRATION.md` 的等价重构方案整体替换 `src/algorithms/`，而不是覆盖同名文件（该交接说明不进入仓库，正式记录以本文件为准）。

## 2. 改动清单

### 2.1 删除的运行代码

- `src/algorithms/v9.py`、`v10.py`、`v11.py`、`rewrite.py`；
- `src/algorithms/v11_frozen_fulltest/`（`run7.py`/`run8.py`/`scheduler*.py`/`exact_graph.py`、实验变体、研究用 `splits.json` 与未跟踪的旧二进制）；
- `src/algorithms/native/constructor_{wide,mitm,pressure,joint,cf,order_fast,order_cf}.cpp`；
- `.gitignore` 中针对 `v11_frozen_fulltest/*` 二进制的路径规则。

这些代码仍可从 Git 提交 `01567f3` 或其之前的发布提交复现；研究记录、17 轮 V11 记录、历史报告与提交 CSV 均保留。

### 2.2 新增/替换的生产代码

- 新模块：`algorithms/portfolio.py`、`basis.py`、`optimize.py`、`schedule_local.py`、`splits.json`；
- 八个内核：`algorithms/native/{order,factor,bilayer,congruence,hyper,synth,basis,synth_extended}.cpp`；
- 重写：`solver.py`、`construct.py`、`graph.py`、`schedule.py`、`checkpoint.py`（schema 5）、`graph_solver.py`（唯一 CLI）；
- `requirements.txt`（NumPy/SciPy 运行依赖）与根 `.gitignore` 的 Santa 规则。

八个内核源码与冻结研究逐字节一致，哈希表见[当前架构](current-architecture.md#迁移清单)；本次没有改动有效候选顺序、搜索预算、等长规则或原生源码。

### 2.3 教学、报告与仓库级同步

- `docs/algorithm-evolution.md`：重写开头的当前状态；新增 **09 V11 教学章**（题目→值 DAG→两组候选→超图 MILP→三/四步合成→寄存器调度→合法性回放，含数学、手算示例与消融表）；原 09–12 章顺延为 10–13；历史 V9/V10 章节保留当时的源码名、分数与提交。
- 新增 `docs/diagrams/v11-architecture.png` 与 `.mmd`（当前架构图）；`version-scores.png` 重绘为 V1–V11。
- 新增 `docs/reports/v11.json`：`artifact_status: "report-only"`，分数 158,955，证据指向 `docs/v11/validation.json` 与 `audit.json`；`docs/build_report.py` 加载时逐字段核对分数、题数、最长步数、输入/输出哈希，并**拒绝**把 report-only 记录设为 `latest.json`。
- `docs/report_template.html`：导航、页首、成绩条、内嵌模拟器说明、页脚同步到 V11；当前算法与可下载归档分开显示；V11 成绩条带 † 与“报告支持，未附 CSV”。
- `src/simulator.html`：保留 V1–V11 槽位与默认 V11；明确 V11 没有随仓库分发的 CSV；修复回放错误/成功提示写入自定义求解区而非回放区的问题；BigInt 的 10¹⁸ 路径保持不变并实测。
- `web/build/santa-review.json` 刷新为 23 个生产源码指纹，回放槽位保持 V1–V11；`web/simulators.html` 与互动报告重建。
- `README.md`、`docs/progress.md`、`docs/frontier-analysis.md`、`docs/reports/README.md`、`docs/v11/README.md`、`submissions/README.md`、`PROGRESS.md`、`AGENTS.md`、`web/build/README.md`、CI 与 Web 测试夹具同步。
- CI 新增 Santa 运行依赖（NumPy/SciPy），否则新的求解测试在 CI 中会因缺少 SciPy 失败。

### 2.4 未改动 / 未提交

- `data/`、`experiments/` 保持本地且被 Git 忽略；官方 `puzzles.csv`、`sample_submission.csv`、SQLite、编译产物、浏览器截图均未提交。
- 历史报告 `docs/reports/v1.json`–`v10.json`、`submissions/*.csv`、`docs/v11/rounds/` 未删除、未改写。
- `submissions/latest.json` 仍指向真实存在的 V10 CSV（164,306）；没有创建 V11 虚假 CSV。

## 3. 源码等价性对照

### 3.1 四题冒烟

从官方题构造 `scored_0001`、`scored_0128`、`scored_0500`、`scored_1000` 的子集 CSV，原版与重构版均用 `--jobs 4`、`OPENBLAS_NUM_THREADS=1`、`OMP_NUM_THREADS=1` 独立求解：

| 题 ID | 原 V11 | 重构 V11 | 程序 |
|---|---:|---:|---|
| scored_0001 | 258 | 258 | 一致 |
| scored_0128 | 124 | 124 | 一致 |
| scored_0500 | 96 | 96 | 一致 |
| scored_1000 | 261 | 261 | 一致 |
| 合计 | 739 | 739 | 4/4 |

两版 CSV 的 SHA-256 均为 `ef9bda35abd8385208f01c69d5da604e179a782fa617250a3601f1b16b50d32c`。

### 3.2 固定 Dev100 与 holdout100

使用 `src/algorithms/splits.json` 中的固定题 ID，原版与重构版各自新建 SQLite，不读取历史程序：

| 数据集 | 原 V11 | 重构 V11 | 最长 | 逐题程序差异 | 输出 CSV SHA-256 |
|---|---:|---:|---:|---:|---|
| Dev100 | 15,948 | 15,948 | 334 | 0 | `53f6ecb0c62f6d87f08d05a6011574fe03ca908512448f1cc73bcdfe151c7d6e` |
| holdout100 | 16,015 | 16,015 | 338 | 0 | `01837f1e49d0a13a2948377b8c4aeac3cc05ac9453e1749b59501a140dae0eb9` |

两次对照的输出都逐字节相同。研究记录中的 Dev100 为 **15,936**（Linux/GCC 14.2.0 + Python 3.13.5）；本机原版也得到 15,948，说明 12 步差异来自工具链/负载，而不是重构回归。

### 3.3 千题全量

本次从官方 1,000 题、全新 schema 5 检查点（`experiments/refactor-full.sqlite`）独立求解，未读取任何历史程序或历史检查点：

| 版本 | 验证 | 指令数 | 最长 | 墙钟 | 输出 SHA-256 |
|---|---:|---:|---:|---:|---|
| 重构 V11 | 1,000/1,000 | **159,057** | 354 | 1,378.6 s（4 进程） | `10ca22672a44fecc8e848ee7fa9df90e1ca4560fc817dc1e87567b36c5d5abfd` |
| 原 V11（基线 worktree） | 1,000/1,000 | **159,057** | 354 | 1,579.9 s（4 进程） | `10ca22672a44fecc8e848ee7fa9df90e1ca4560fc817dc1e87567b36c5d5abfd` |

重构版另用 `src/verify.py` 对完整 1,000 题再验证一次：`validated=1000`、`score=159057`、`max_steps=354`、输入与输出哈希如上，报告写入 `experiments/refactor-full.validation.json`（本地、未提交）。

**与原研究记录 158,955 的差异：** 本次多 102 步（0.064%）。两者不是同一环境：原研究是 Linux/GCC，本次是 macOS/Apple Clang；Dev100 的原版对照已经显示本机同样多 12 步（15,948 vs 15,936）。这是环境/墙钟差异，不是候选集合或搜索预算改动。

**基线千题对照：** 原版与重构版的 1,000 题输出 **逐字节相同**（同一 SHA-256、逐题程序差异 0、分数都是 159,057、最长 354）。因此 158,955 → 159,057 的差异完全由运行环境解释，重构没有引入算法性退化或候选变化。

**与 V10 归档的同题比较（仅用于口径）：** 本次 838 题更好 / 81 持平 / 81 退化，相对 V10 的 164,306 少 5,249 步（3.19%）。研究记录为 848/70/82、少 5,351 步；差异同样来自环境。



## 4. 自动化测试与构建

依赖环境：Python 3.13.2、NumPy 2.4.3、SciPy 1.17.1、Markdown 3.10.2、latex2mathml 3.81.1。`docs/requirements-docs.txt` 的两个文档依赖与安装值完全一致；`requirements.txt` 固定研究环境的 NumPy 2.3.5 / SciPy 1.17.0，但本机预装的是较新的 2.4.3 / 1.17.1。尝试用干净 venv 安装固定版本时 PyPI 连接被 SSL 拒绝，因此**没有**降级；本轮所有运行都记录为 NumPy 2.4.3 / SciPy 1.17.1。CI 会按 `requirements.txt` 安装固定版本，这不影响本次同环境对照的结论，但说明绝对分数可能与本机不同。

| 命令 | 实际结果 |
|---|---|
| `python src/algorithms/native/build.py` | 8/8 内核用 Apple Clang 21.0.0 + compat 头构建，记录 manifest 与二进制 SHA-256 |
| `python -m unittest discover -s tests -v` | **101 tests, OK**（约 201.8 s） |
| `node --test tests/test_replay.cjs` | **7 pass / 0 fail** |
| `python -m unittest discover -s ../../web/tests -p 'test_*.py' -v` | **17 tests, OK** |
| `python docs/build_report.py --check` | `Santa-2026-Interactive-Report.html is up to date` |
| `python ../../web/build/build.py --check` | exit 0（统一入口与 23 个源码指纹一致） |

```bash
python -m pip install -r requirements.txt
python -m pip install -r docs/requirements-docs.txt
python src/algorithms/native/build.py
python docs/build_report.py
python docs/build_report.py --check
python -m unittest discover -s tests -v
node --test tests/test_replay.cjs
python -m unittest discover -s ../../web/tests -p 'test_*.py' -v
python ../../web/build/build.py --check
```

另做了一次人工 CLI 边界检查：`--stop-after 0` 只建库不导出；换 `OPENBLAS_NUM_THREADS` 后 `--resume` 被“checkpoint fingerprint changed”拒绝；改回原环境后 `--resume` 正常求解并原子导出。这与 `tests/test_checkpoint.py` 的损坏记录/输入变化拒绝覆盖互补。

## 5. 浏览器验证

使用本机 Google Chrome（Playwright `channel=chrome`，headless）打开 `file://` 页面，并记录所有 http(s) 请求为零：

| 页面 | 检查 |
|---|---|
| `src/simulator.html` | 默认示例求解、逐步回放、寄存器面板、10¹⁸ BigInt 一步求解、导入题目 + V10 程序、同题比较、V11 无 CSV 时显示导入提示且不伪造结果、390px 窄屏无横向溢出 |
| `Santa-2026-Interactive-Report.html` | 离线打开、11 个成绩条、V11 report-only 标注与“未附 CSV”、页首当前算法/可下载归档分离、V8 等价重构面板、MathML、内嵌图片 data URI、内嵌模拟器求解、390px 窄屏 |
| `web/simulators.html` | 离线打开、切换到 Santa、iframe 内求解成功、无网络请求 |

截图保存在本地 `experiments/browser/`（未提交）。共 25 项检查全部通过；未在 Safari/Firefox 或真实手机设备上验证。

## 6. 执行偏差与判断

- **压缩包文档不完整。** `HANDOFF-STATUS.md` 说明 `report_template.html`、`test_acceptance_report.py` 等仍是旧内容；本次没有只依赖附件，而是按真实源码补齐了模板、loader、测试和 `docs/reports/v11.json`。
- **章节编号顺延。** 为了把 V11 放在 V9/V10 之后、演进实验之前，原 09–12 章改为 10–13，`docs/build_report.py` 的插入锚点（`101-`、`124-`、`131-`）与测试同步更新；历史章节内的版本字符串没有全局替换。
- **V11 不进入可下载最佳。** 原研究没有正式 CSV，因此只新增 report-only 记录；`latest.json` 保持 V10。构建器新增了“latest 不能指向 report-only”和“report-only 必须与独立验证/审计一致”的硬校验，没有弱化归档完整性。
- **模拟器提示修复。** 原页面的回放错误调用 `status()` 写到了自定义求解区；本次改为写回放区，成功时显示“导入程序回放校验通过”。这是显示层修复，不改变回放/合法性逻辑。
- **基线 worktree。** 旧 main 的 `v11_frozen_fulltest` 未跟踪二进制不在 Git 中，因此对照运行前在 worktree 内用同一编译器重新构建；原版与重构版都从源码构建。
- **未改算法。** 两个候选组、8 个内核源码、MILP 0.7 秒预算、调度种子/步数、等长规则均未改；本次不新增 V12 运行目录。

## 7. 未完成事项与风险

- 千题全量已完成：重构版 159,057、1,000/1,000 合法；基线同环境输出逐字节相同。没有用历史 158,955 冒充本次复跑，也没有把本次工程验收算作新算法版本。
- MILP 使用墙钟限时，跨机器/负载的逐题结果可能不同；即使本次与原版逐字节相同，也不构成跨平台确定性证明。
- 浏览器只在 Chrome headless 上验证，未覆盖 Safari/Firefox、真实触屏和打印分页。
- 未执行远程推送、PR 或 main 合并；这些需要用户进一步授权。
- 本地 `experiments/` 中的 SQLite、CSV、截图和编译产物保留用于复查，全部被 Git 忽略。

## 8. 合入建议

在以下条件满足后可考虑合入：Santa 测试、Node 回放、Web 测试、报告 `--check`、统一入口 `--check` 全绿；千题独立验证完成；`git diff --check` 干净且无数据/DB/二进制入库。合入前应再次核对 `submissions/latest.json` 仍指向真实 V10 CSV，并按流程刷新 `web/build/santa-review.json`。
