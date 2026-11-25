# Santa 2026 · V9 合入：与任务书不一致处的调整、原因与证据

> 本文件供推送前的独立审查（如交给 GPT/代码评审）使用。它只记录**偏差、调整原因、影响与证据**，完整交付总结见对话回复和 `competitions/santa-2026/docs/progress.md`。审查时请优先核对第 3 节的 D1–D14，以及第 4 节的未验证清单。

> **状态（2026-11-26 更新）：** 本文件 §0–§7 是 **V9 推送前的审查快照**，内容按当时事实保留不改；V9 已随后合入远程 `main`（`8858a6a`），并完成 Linux + GCC 参考工具链的最终验收，结果见文末 **§8 合入后独立审查与最终验收**。§8 中的状态表取代 §0–§7 中"未推送/未验证"的旧状态，但历史偏差本身不追溯改写。

## 0. 审查上下文

| 项目 | 值 |
|---|---|
| 仓库 | `Leonardo-F/kaggle-lab` |
| 分支 | 本地 `feat/santa-v9`（**未推送**，`origin/main` 未变化） |
| 基线 | `origin/main` = `287519977aa85a19ef9e3074e6bfd2b9e578b5c3`（2026-11-25，V8 全量验收） |
| 主任务书 | `santa-v9-integration-plan.md`（2026-11-25 只读审计版，V9 合入） |
| 配套任务书 | `santa-v8-final-cleanup.md`（V8 重构后的工程收尾，其 P0/P1/P2 要求仍适用） |
| 交接输入 | `santa_v9_stage2_full_test.zip`（SHA-256 `b1d338d27d3998dc1785ad79217c6ecfbc3254bb51cb1e9993fcff7374cca758`）、`submission_v9_stage2.csv`、`submission_v8_v9_merged.csv`、`merge_v8_v9.py`、官方 `puzzles.csv`/`practice_puzzles.csv`；交接文件只在仓库外 `/tmp` 使用，未入 Git |
| 实际环境 | macOS 27.0.1 (26A434) arm64；Python 3.13.2；Apple Clang 21.0.0；Node v20.17.0；Chrome 158.0.8127.88；**无可用 GCC**（见 D1） |

**分支提交（5 个，均为中文提交信息）：**

| SHA | 标题 |
|---|---|
| `c40470699e54dcfacab0fbcf4a5922577e0b1b75` | `fix(santa): 修复 V8 历史验收和正式报告校验` |
| `d3f4cae70282e6a091670e6aa4c5a2743e5c21e5` | `feat(santa): 按功能合入冻结 V9 动态字典构造与寄存器压力调度` |
| `96ac38e84d621f5c7e7603e16d7a64906ea23125` | `test(santa): 记录 V9 独立全量复现与 V8+V9 混合归档` |
| `584652bfed09b6abb53d4b1a78ada3cc82149341` | `docs(santa): 更新 V9 学习报告、模拟器与离线回放` |
| `b0f63bd77fbefb73e62fef619b1805740265d677` | `docs(santa): 校正 V9 验证计数记录` |

本文件随第 6 个提交加入。`git diff --shortstat origin/main...HEAD`（不含本文件）为 43 files changed, +7046/−3093。

## 1. 核心结果与原定目标的对照（真实执行，非引用旧记录）

| 门槛（任务书 §4/§5） | 任务书期望 | 实际结果 | 结论 |
|---|---|---|---|
| 正式 1,000 题从零独立求解 | 1,000/1,000、stage1=182205、final=175604、max_steps=415 | **175,604、1,000/1,000、stage1=182205、max=415**（新 schema 3 检查点，6 进程，443.85 s，无 resume） | 达成 |
| 逐题程序与冻结记录一致 | 期望 CSV SHA-256 `5ab0b72c…` | 逐题程序 **999/1000 相同**；唯一差异 `scored_0775` 等长（181 步）但寄存器选择不同；新 CSV SHA-256 `05e7b630…` | **未逐字节复现**，见 D2；已按任务书"不同平台差异需记录、不声称精确复现"处理 |
| 阶段/逐题确定性指标 | 与冻结记录一致 | 两阶段总分、逐题 base/score/nodes/schedule_attempts、四路线分数与节点数、7 个位宽桶全部一致 | 达成 |
| 练习 200 题独立验证 | 真实分数 | **36,045 步、200/200、max 413、stage1 37,742、节省 1,697（86/114/0）、131.15 s** | 达成（无任务书预设练习分数） |
| V8+V9 混合独立验证 | 174,884、137/863、max 392 | **174,884、137/863（含 30 平局取 V9）、max 392**，SHA `fe973ac4…` | 达成；与上传参考文件 999/1000 程序相同，分数一致，见 D9 |
| 唯一公开入口/功能模块化 | 不保留 V1–V9 版本化 `.py`、不复制研究 runner | `algorithms/` 7 个功能模块 + `native/`（2 `.cpp`、兼容头、build.py）；唯一入口 `solve`；`SOLVER_VERSION = "v9"` 单源 | 达成 |
| 冻结搜索策略不变 | 路线顺序/种子/候选顺序/调度不变 | 逐行移植并在 11 题代表性样本 + `scored_0775` 上与原研究源码逐题比对；全量 1,000 题指标/桶与冻结记录一致 | 达成（工具链平局差异见 D2） |
| 原生构建与指纹 | 求解前构建、记录编译器/flags/源码/二进制哈希、CI 纳入 | `native/build.py`、manifest、schema 3 检查点绑定；CI 增加构建预检 | 达成；本机未用 GCC，见 D1/D7 |
| 测试、构建、断点、浏览器 | Python/Node/Web/native/断点/离线浏览器 | 全部执行并记录于第 2 节 | 达成，浏览器范围见 D11 |

## 2. 实际验证结果（用于交叉核对，均为本次真实执行）

- Santa Python：`python3 -m unittest discover -s competitions/santa-2026/tests -p 'test_*.py'` → **98 tests OK**（report 44、solver 27、checkpoint 11、merge 11、verify 5）。
- Santa Node：`node --test competitions/santa-2026/tests/test_replay.cjs` → **7/7 pass**。
- Web Python：`python3 -m unittest discover -s web/tests -p 'test_*.py'` → **17 tests OK**；`python web/build/build.py --check` → exit 0。
- 其他赛题回归：装箱 Python **27 OK**、装箱 Node **15/15 pass**、量子 Python **13 OK（0 skip）**（本机用 `/tmp` 临时目录安装公开 requirements，未改仓库）。
- 报告与原生：`python3 competitions/santa-2026/docs/build_report.py` 重建；`--check` → up to date（exit 0）；`python3 competitions/santa-2026/src/algorithms/native/build.py` → 两个内核构建成功，`ensure_built(force=True)` 二进制 SHA 稳定。
- 真实数据断点恢复：5 题先 `--stop-after 2` → `PARTIAL 2/5`、不导出 CSV；`--resume` → `resumed_at_start=2`、5/5 完成并通过 `verify.py`（该 5 题子集分数 1,023 仅用于断点演示，不作为正式成绩）。
- 干净 worktree（检出最终 HEAD）重跑：Santa 98 OK、Node 7、Web 17、报告/统一入口 `--check` 全绿、`git status` 干净。
- 浏览器（真实 Chrome 158.0.8127.88 headless，macOS 27.0.1 arm64；`file://` 打开，Playwright 拦截全部 `http(s)` 请求模拟离线；互动页用本地 HTTP 验证相对路径）：模拟器页 **23/23**；互动报告/统一入口/互动页 **26/26**（含 390px 窄屏、`#santa`/`#squares`、内嵌模拟器回放）。
- 归档 CSV 独立复核：V9 `175,604`、V8 `194,444`、混合 `174,884`，均 1,000/1,000 合法。
- 仓库卫生：未跟踪官方题目数据、SQLite、日志、编译二进制或凭据；`git diff --check` 通过。

## 3. 偏差逐项说明（D1–D14）

### D1（重要）本机没有 GCC，实际构建使用 Apple Clang + 兼容头

- **任务书要求（§3.3）**："使用 GCC/libstdc++、C++17 与 `-O3`；`<bits/stdc++.h>`、`__int128` 不保证 MSVC/Apple Clang 原生可用。推荐 Linux/WSL/Codespace；macOS 使用经过测试的 GCC 或 Linux，记录实际支持范围。"
- **实际做法**：本机 `g++` 是 Apple Clang 21.0.0（`/usr/bin/g++`），无系统 GCC、无 Docker/podman；Homebrew GCC 16.2.0 bottle（ghcr，164,214,067 B，blob `b468e0bd…`）下载多次失败（`curl: (92) HTTP/2 stream 1 was not closed cleanly: PROTOCOL_ERROR`），断点重试实测约 40–170 KB/s，无法在本次窗口内完成安装。最终本地全量复现使用 **Apple Clang 21.0.0 + `native/compat/bits/stdc++.h` 兼容头**，`-O3 -std=c++17`；`native/build.py` 仍优先探测真实 GCC（`g++-15…g++-10`、`SANTA_CXX`），CI 的 Ubuntu 环境使用 g++ 走同一构建入口。
- **影响**：本地构建不是任务书推荐的参考工具链；任务书明确"不要声称跨平台逐字节等价"，本次也未声称。C++ 源码与交接包**逐字节相同**（`constructor_wide.cpp` = `99a05ebc…`、`constructor_mitm.cpp` = `14b3885b…`）；编译器/flags/二进制 SHA 已写入 `docs/reports/v9.json` 的 `native` 字段与 schema 3 检查点。
- **证据**：全量 1,000 题的分数、两阶段总分、逐题指标与 7 个位宽桶与冻结记录一致；999/1000 程序相同（D2）。
- **建议审查**：若要求必须 GCC/libstdc++ 本机实测，请在 Linux/GCC 环境重跑（命令见第 5 节）；这是本分支最明确的"未按推荐工具链"偏差。

### D2（重要）1/1000 逐题程序与冻结记录有等长平局差异

- **任务书要求（§4）**：逐题程序及确定性指标与冻结记录一致，期望 CSV SHA-256 `5ab0b72c…`；若不同平台结果合法但有差异，记录实际分数和原因，**不声称精确复现**、不自动替换冻结发布。
- **实际结果**：999/1000 程序相同；`scored_0775` 两版程序**等长（均 181 步）**，仅寄存器目标不同（首个差异为第 97 条指令的目的寄存器 6 vs 47）。两阶段总分、逐题 base/score/nodes/schedule_attempts、四路线分数/节点、逐题位宽桶全部一致。本机输出 CSV SHA-256 为 `05e7b630…`，冻结记录为 `5ab0b72c…`。
- **原因定位**：用冻结研究源码在本机重新编译（同 Apple Clang、同源码）并运行，得到与移植版**相同**的程序；因此差异来自本机 Apple Clang 与冻结记录 Linux GCC 在等分候选平局时的容器迭代顺序差异，不是移植逻辑差异（详见 D10 的全量对照）。
- **处理**：未替换/改写冻结证据；新结果作为本次独立发布单独归档并在 `v9.json`、`progress.md`、算法演进正文中明确披露；未声称逐字节复现。

### D3 分步提交的中间提交不是可独立发布构建

- **任务书要求（§2/§7）**：V8 收尾阶段独立提交，使 V8 仍是当前 solver、latest 仍指 V8、构建可通过；§3.4 允许"若分步提交暂时导致 Web review 过期，明确标注中间提交仅供本地开发，最终必须恢复完整构建"。
- **实际做法**：按计划分 4 个功能提交；第 1 个提交（`c404706`）只含报告校验源码与测试，未重建互动报告 HTML（其内容依赖后续提交的 V9 文档/数据），因此该中间提交单独 checkout 时 `build_report.py --check` 会失败；第 4 个提交才统一重建 HTML/统一入口/审查指纹。提交信息中已注明"本提交是本地开发中间态，不单独作为可发布构建"。
- **最终状态**：最终 HEAD（干净 worktree 验证）所有测试、两个 `--check`、浏览器验收全部通过。
- **建议审查**：若要求每个提交都独立绿，可只在最终 HEAD 做 review，或由你决定 squash；仓库历史保持按阶段可审。

### D4 `test_report.py` 的"未来版本"测试夹具从 V9 改为 V10

- **任务书要求（§2.4）**：用临时 V9 fixture（例如 185,000）验证"最新版本变化仍显示历史 V8 通过"等场景。
- **实际做法**：本轮 V9 已成为**真实正式报告**，若继续用 V9 作"模拟未来版本"会与真实 `v9.json` 冲突。测试改为以 V10（185,000）作为模拟未来版本，保留原测试强度（V8 历史验收不依赖最新版本、正式曲线版本配对、交换分数/错行失败等），并更新了 V8 固定参考的版本列表断言（v1–v9）。
- **影响**：测试语义等价，仅"未来版本"的标签从 V9 换成 V10；原因已在提交说明与测试代码注释中记录。

### D5 正式报告保留平铺 schema + `schema_version: 1`，未立即迁移到分组 2.0 schema

- **任务书要求**：V9 起使用约定的 `schema_version` 与兼容读取器；V8 收尾任务书 §3.3 同时要求"采用新格式时必须同时新增单一兼容读取函数…在解析器落地前，新版本报告应继续使用当前平铺字段"。
- **实际做法**：`docs/reports/v9.json` 使用与 V1–V8 兼容的平铺字段（`version/puzzles/validated/score/max_steps/submission_sha256/puzzles_sha256`），并额外记录 `schema_version: 1`、`kind`、阶段、源码/原生指纹、检查点、测试与局限性等**不重复分数**的来源字段；`docs/reports/README.md` §6 明确记录分组 2.0 schema 是后续目标、迁移前继续用平铺字段，避免同时维护两套正式分数来源。
- **影响**：读取器无需迁移即可正确构建与 `--check`；分组 schema 解析器**未实现**（按任务书允许延后）。

### D6 分支在现有工作区创建，而不是任务书示例的独立 worktree

- **任务书要求（§1）**：示例命令使用 `git worktree add -b feat/santa-v9 ../kaggle-lab-santa-v9 origin/main`。
- **实际做法**：审计时主工作区干净、无他人改动，直接在当前仓库 `git checkout -b feat/santa-v9`；未创建额外 worktree。所有交接文件、官方数据、检查点、实验输出都在仓库外 `/tmp`。
- **影响**：无；仅为执行方式差异，避免额外目录/复制。

### D7 CI 已更新但未在远端实际执行

- **任务书要求（§6.2）**：CI 加入明确 C++17 编译预检，执行同一 native 构建入口、合成小题、checkpoint、merge、Python/Node/Web 全部测试。
- **实际做法**：`.github/workflows/test.yml` 已加入 `g++ --version` + `native/build.py` 预检并保留全部测试步骤；本机按 CI 等价命令全部执行通过（Python 3.13.2/macOS 与 CI 的 Python 3.11/Ubuntu 不同，CI 未跑）。
- **原因**：未获推送授权，GitHub Actions 不可能运行。
- **影响**：CI 配置正确性未在真实 Actions 环境验证；`tests/test_merge.py` 额外在 Python 3.11.15 下单独验证过 11/11，但完整 CI 组合未跑。

### D8 `docs/reports/README.md` 内容范围大于"最小说明"

- **任务书要求（V8 收尾 §3.1）**：新增 README 解释三类报告、读取关系、Git 历史、复现方式；建议最小方案不迁移旧 JSON。
- **实际做法**：README 覆盖任务书要求，并扩展记录了本轮新增的 v9/merge/ablation 四类、V9 平铺 schema 规则、`latest.json` 与 `santa-review.json` 的区别、14 份 JSON 的体积与路径不迁移决定。
- **影响**：无；旧 11 份 JSON 路径未迁移，历史证据未改写。

### D9 混合归档使用本次独立 V9（非上传参考）重建，平局计数口径需注意

- **任务书要求（§5.1）**：`merged[id] == (v9[id] if len(v9[id]) <= len(v8[id]) else v8[id])`，验证 137/863、174,884、max 392；上传参考文件只作对照。
- **实际做法**：用本次独立 V9（SHA `05e7b630…`，非冻结 `5ab0b72c…`）与归档 V8 通过新工具 `src/merge_submissions.py` 重建，结果 174,884、max 392；`from_first=137`（V8 严格更短），`from_second=863`（其中 **30 题等长平局按"取后者 V9"**，即 V9 严格更短 833 + 平局 30）。与上传参考文件对比：999/1000 程序相同（同 `scored_0775` 等长差异），分数/max 相同，文件 SHA 因平局程序不同而不等于 `bde4b4c4…`。
- **影响**：报告与 README 明确写明 30 平局归属，避免"863 全是 V9 严格更好"的误读；混合归档不作为独立版本、不进入曲线。

### D10 同工具链"原版 vs 移植版"全量一致性（本文件新增验证）

- **任务书要求（§4）**："同工具链原版 vs 移植版必须一致才能声称等价"。
- **实际做法与结果**：用冻结研究源码 + 本机重建的同一 Clang 二进制做逐题对照，与移植版比较完整程序、`base/score/nodes/schedule_attempts` 与四路线指标：
  - 代表性样本（11 题，覆盖各位宽段、Stage 1 退化题、attempts=72 题）：**全部一致**；
  - 差异题 `scored_0775`：参考实现复现的程序与**移植版相同**，因此与冻结记录的差异来自工具链而非移植逻辑；
  - 补充的全量对照（后台从零跑 1,000 题）在完稿前已比较 **368/1000 题，0 处不一致**（程序、阶段、节点、尝试数、路线指标全部相同），因时间窗口未跑完剩余部分。因此"同工具链全量 1,000 题逐题一致"**未完整证明**，现有证据为上述范围 + 移植版与冻结记录 999/1000 一致 + 差异题的同工具链复现。
- **说明**：该验证只用于事后对照，不读取任何历史程序作为求解输入；参考实现与移植版独立运行。

### D11 浏览器验收为真实 Chrome headless 自动化，不是人工逐项点击

- **任务书要求（§6.3）**：使用已有浏览器或临时本地自动化，记录浏览器/OS/版本、`file://`/HTTP、断网方式、移动尺寸和真实结果；不得伪造。
- **实际做法**：Playwright 驱动本机真实 **Google Chrome 158**（headless），打开 `file://` 页面；通过请求拦截**阻止全部 `http(s)` 请求**模拟断网/离线；互动页在本地 HTTP 服务下检查相对路径；记录 390px 移动视口无横向溢出。模拟器页 23/23、互动报告/统一入口/互动页 26/26。
- **限制**：只测 Chrome（未测 Safari/Firefox/真实手机）；未做人工逐项点击；`file://` 下剪贴板真实写入权限未测试（只验证了页面内原始 JSON 内容与回放）；截图仅存于 `/tmp`，未作为人工验收证据提交。

### D12 `version-scores.png` 未重绘

- **任务书要求（V8 收尾 §6）**：核对 `version-scores.png` 是否只覆盖 V1–V5；选择保留并明确标注范围，或同步更新 PNG/Mermaid。
- **实际做法**：更新 `docs/diagrams/version-scores.mmd` 的源文本到 V1–V9，并注释说明 PNG 未重绘（本机无离线 Mermaid 渲染器）、以互动报告动态成绩曲线为准；PNG 原文件保留并明确覆盖范围。
- **影响**：仅文档图示范围说明问题；正式成绩曲线由 `score-data`/报告动态生成，不受影响。

### D13 旧历史报告源码指纹未用 `git show` 逐文件复核

- **任务书要求（V8 收尾 §2.1）**："旧报告的源码指纹应匹配该实验对应的提交…**可**在本次本地审计用 `git show <sha>:<path>` 核对…记录实际核查范围"。
- **实际做法**：实现了正常构建**不读 Git、不联网**的格式与固定提交映射校验（`DOCUMENTED_COMMITS`），并保留历史报告原样；未逐文件执行 `git show ... | sha256` 核对旧报告 `source_hashes`。
- **影响**：属于任务书中"可选"审计项，未执行；历史指纹仍以报告声明为准，构建不将其冒充当前工作树验证。

### D14 练习集运行参数与归档方式

- **任务书要求**：练习 200 题从零独立求解并报告真实分数；不得混入正式计分报告。
- **实际做法**：6 进程、全新检查点、131.15 s，结果 36,045 步（stage1 37,742、节省 1,697、86/114/0、max 413、SHA `64a67f68…`）；结果记录在 `v9.json` 的 `practice_run`，练习 CSV/检查点只保留在 `/tmp`，按要求不进正式提交曲线、不覆盖正式题报告。
- **说明**：任务书示例命令用 4 进程，本次用 6 进程（只影响耗时，不影响确定性结果）。

## 4. 未验证 / 未完成事项（审查时应视为残余风险）

1. **未推送**（无授权）；`origin/main` 未变化；GitHub Actions 未运行（D7）。
2. **未做 Kaggle 提交/榜单成绩**；175,604 等均为本地独立验证值。
3. **本机未用 GCC/libstdc++ 实测**（D1）；跨平台逐字节等价未证明。
4. **1/1000 逐题程序平局差异**（D2），分数与全部确定性指标一致，但未逐字节复现冻结 CSV。
5. **浏览器范围**：仅 Chrome headless 自动化；未测 Safari/Firefox/真实手机/剪贴板真实权限/人工点击（D11）。
6. **旧报告历史源码指纹**未做 `git show` 复核（D13，任务书为可选）。
7. **正式报告分组 2.0 schema 解析器**未实现（D5，任务书允许延后）。
8. **`version-scores.png`** 未重绘（D12）。
9. **Windows/MSVC 未验证**（任务书本身不要求，且 `__int128`/`<bits/stdc++.h>` 不保证）。
10. **同工具链全量对照未跑完**：已比较 368/1000 题、0 处不一致，另有 11 题代表性样本与差异题 `scored_0775` 的逐题一致证据（D10）；未跑的剩余题号不阻塞最终结果（移植版与冻结记录已 999/1000 一致）。
11. **V10 及未验证探索算法未开始**（按要求）。

## 5. 审查者可复现的命令

以下命令均在仓库根目录执行；官方题目需自备于 `competitions/santa-2026/data/`（不入库）。

```bash
git log --oneline origin/main..HEAD
git diff --shortstat origin/main...HEAD

# 原生构建 + 全部测试
python3 competitions/santa-2026/src/algorithms/native/build.py
python3 -m unittest discover -s competitions/santa-2026/tests -p 'test_*.py'
node --test competitions/santa-2026/tests/test_replay.cjs
python3 -m unittest discover -s web/tests -p 'test_*.py'

# 两个 --check
python3 competitions/santa-2026/docs/build_report.py --check
python3 web/build/build.py --check

# 归档 CSV 独立验证
python3 competitions/santa-2026/src/verify.py competitions/santa-2026/data/puzzles.csv \
  competitions/santa-2026/submissions/elf-calculator-independent-v9-score-175604.csv
python3 competitions/santa-2026/src/verify.py competitions/santa-2026/data/puzzles.csv \
  competitions/santa-2026/submissions/elf-calculator-merged-v8-v9-score-174884.csv

# 如需重跑正式 1,000 题（会生成实验文件到 experiments/，已 gitignore）
cd competitions/santa-2026
python3 src/graph_solver.py data/puzzles.csv --version v9 --jobs 6 \
  --checkpoint experiments/review-v9.sqlite --output experiments/review-v9.csv
python3 src/verify.py data/puzzles.csv experiments/review-v9.csv

# 如需 GCC/libstdc++ 复核（建议 Linux/CI）
SANTA_CXX=g++-14 python3 src/algorithms/native/build.py --force
python3 src/graph_solver.py data/puzzles.csv --version v9 --jobs 4 \
  --checkpoint experiments/gcc-v9.sqlite --output experiments/gcc-v9.csv
python3 src/verify.py data/puzzles.csv experiments/gcc-v9.csv
```

报告与证据位置：`competitions/santa-2026/docs/reports/v9.json`（独立发布）、`v8-v9-merged.json`（混合归档）、`v9-stage2-ablation.json`（冻结研究包原始证据）、`docs/reports/README.md`（报告目录与读取规则）、`docs/progress.md`（进展与偏差摘要）、`submissions/latest.json`（最佳独立发布指针）。

## 6. 关键哈希与环境附表

| 对象 | 值 |
|---|---|
| 基线 `main` / `origin/main` | `287519977aa85a19ef9e3074e6bfd2b9e578b5c3` |
| 官方题 `puzzles.csv` | `b0c70d849eca078a0e1cf9a4f7b47fd40b7435663f6f84de6725f84724500428` |
| 交接 ZIP | `b1d338d27d3998dc1785ad79217c6ecfbc3254bb51cb1e9993fcff7374cca758` |
| 冻结 V9 CSV | `5ab0b72c170272591f4d9485730b9805c82d9b2b857827bc017ab53ca3f3ce63` |
| 本机独立 V9 CSV | `05e7b630f9b9a26889a74e09dbc1317ece799e5d28d948ce28c02b99b0660cb8` |
| V8 归档 CSV | `6f15091bcfddf4335f69126c2088696dfa7a9a3fcb9c4de6dbaa448aca1279fd` |
| 本机混合归档 CSV | `fe973ac4ed3ec8a587e18ce31b922daae4ec1060ad2bdc511d2130960978942a` |
| 上传参考混合 CSV | `bde4b4c4bf9bf7b5adceb50c516f9b407134c87753d5cdcbd2d8f2df73eec556` |
| 练习 200 题 CSV（本地） | `64a67f68de1a8d67b33b498006c797867fef0e2d215d54ee909bfc30d0a0f112` |
| 本机工具链 | Apple Clang 21.0.0 / Python 3.13.2 / Node v20.17.0 / Chrome 158.0.8127.88 / macOS 27.0.1 arm64 |
| 冻结研究环境（记录值） | Python 3.13.5（构建信息 GCC 14.2.0）、1,000 题报告 797.97 s（自 8 行 resume 后），二进制为研究包预编译 Linux ELF，未作为本地发布依赖 |

## 7. 建议审查重点（3 件事）

1. **工具链偏差 D1 是否可接受**：本次全量结果由 Apple Clang 21 + 兼容头构建；若要求严格 GCC/libstdc++ 证据，请在 Linux/GCC 环境按第 5 节命令重跑。
2. **D2 的 1/1000 等长程序差异是否可接受**：分数、阶段、逐题指标、位宽桶完全一致，仅 `scored_0775` 平局程序不同；已定位为工具链差异并披露，未声称逐字节复现冻结 CSV。
3. **D3 中间提交非独立绿是否可接受**：最终 HEAD 全绿；若要求逐提交可构建，可在推送前 squash/重排，仓库本身不依赖中间提交状态。

---

**D10 补充说明：** 同工具链逐题对照已覆盖 11 题代表性样本 + 差异题 `scored_0775` + 全量对照中的 368/1000 题，均为 0 处不一致；受本次时间窗口限制未跑完 1,000 题。"同工具链全量一致"未完整证明，但移植版与冻结记录的 999/1000 逐题一致、且唯一差异题可由同工具链参考实现复现移植版程序，足以支持"差异来自工具链而非移植逻辑"的结论。

---

# 8. 合入后独立审查与最终验收（2026-11-26）

本节是 V9 合入远程 `main` 后的收尾验收记录，按"实际执行结果"填写；不修改 §0–§7 的历史快照。

## 8.1 远程与本地状态

| 项目 | 值 |
|---|---|
| 远程 `main`（合入后） | `8858a6a09e4ba37498f831e4350a8787d1e08c2c`（merge `feat/santa-v9`） |
| V9 合入内容 | `c404706`、`d3f4cae`、`96ac38e`、`584652b`、`b0f63bd`、`105cc83` 六个提交 |
| GitHub Actions（main 合并提交） | [run 45673883392](https://github.com/Leonardo-F/kaggle-lab/actions/runs/45673883392)，**completed / success**，含 `Build Santa native C++17 constructors` 步骤，全部 16 个步骤 success（使用 `gh run view --json jobs` 核实） |
| 本轮验收分支 | `fix/santa-v9-final-acceptance`（从 `8858a6a` 创建，本地提交，未推送） |

## 8.2 D1–D14 当前状态

| 偏差 | 原状态 | 最终状态 | 依据 |
|---|---|---|---|
| D1 本机无 GCC，用 Apple Clang 构建 | 未解决 | **关闭** | Linux + GCC 14.2.0 参考工具链全量复现，输出与冻结 CSV 逐字节一致（§8.3） |
| D2 1/1000 等长程序平局差异 | 已披露 | **关闭** | GCC 环境下 port、参考实现、冻结记录三方 `scored_0775` 程序完全相同；三份 CSV SHA 均为 `5ab0b72c…` |
| D3 中间提交非独立可发布 | 可接受 | 保持可接受（未改历史） | 最终 `main` 与验收分支树已验证 |
| D4 测试夹具用 V10 模拟未来版本 | 可接受 | 保持 | — |
| D5 正式报告平铺 schema 1 | 可接受 | 保持 | 未迁移；验收报告独立为 `v9-integration.json` |
| D6 未用独立 worktree | 可接受 | 保持 | — |
| D7 CI 未远端执行 | 未解决 | **关闭（针对已合入 main）** | 真实 Actions run 成功；本轮本地验收提交因未推送仍未跑 CI（见 §8.9） |
| D8 报告 README 扩展 | 可接受 | 保持，补充 v9-integration 条目 | `docs/reports/README.md` |
| D9 混合归档用本次 V9 重建 | 可接受 | 保持，并完成逐题公式校验 | §8.6 |
| D10 同工具链全量等价性未完成 | 部分完成（368/1000） | **关闭** | Linux GCC 同环境双实现 1,000/1,000 全量对照，0 差异（§8.4） |
| D11 浏览器为 Chrome headless 自动化 | 可接受 | 保持（本轮复验报告/模拟器） | §8.8 |
| D12 version-scores.png 未重绘 | 未解决 | **关闭** | 已用 mermaid.ink 由更新后的 `version-scores.mmd` 重新渲染 V1–V9 PNG，正文说明同步更新 |
| D13 历史指纹未逐文件复核 | 未完成 | **部分完成** | 抽查 `v8.json` 4 个文件、`v8-refactor.json` 10 个文件，全部与会话记录提交一致（§8.7） |
| D14 练习集 6 进程 | 可接受 | 保持 | — |

## 8.3 P0-2：Linux + GCC 参考工具链全量复现（实际结果）

环境（VM 内实测）：Ubuntu 25.04、Linux 6.14.0-37-generic aarch64（Apple 虚拟化，6 vCPU）、
`g++-14 (Ubuntu 14.2.0-19ubuntu2) 14.2.0`、glibc 2.41、`libstdc++-14-dev 14.2.0-19ubuntu2`、
Python 3.13.3（GCC 14.2.0 构建）。原生构建记录：`SANTA_CXX=/usr/bin/g++-14`、flags `-O3 -std=c++17`、
`compat_include=false`；GCC 二进制 SHA-256：`constructor_wide 9682b6e6…`、`constructor_mitm 8379e5b3…`；
两个 `.cpp` 与冻结研究包逐字节相同（`99a05ebc…` / `14b3885b…`）。

命令（全新 schema 3 检查点、6 进程、无 resume）：

```bash
cd competitions/santa-2026
export SANTA_CXX=/usr/bin/g++-14
python3 src/algorithms/native/build.py
python3 src/graph_solver.py data/puzzles.csv --version v9 --jobs 6   --checkpoint experiments/v9-gcc.sqlite --output experiments/v9-gcc.csv
python3 src/verify.py data/puzzles.csv experiments/v9-gcc.csv
```

结果：

| 指标 | 冻结 V9 | 本次 Linux/GCC 实测 |
|---|---:|---:|
| 题数 / 合法 | 1,000 / 1,000 | **1,000 / 1,000** |
| Stage 1 | 182,205 | **182,205** |
| Final | 175,604 | **175,604** |
| Stage 2 节省 | 6,601（394/606/0） | **6,601（394/606/0）** |
| 最长程序 | 415 | **415** |
| CSV SHA-256 | `5ab0b72c…` | **`5ab0b72c…`（逐字节一致）** |
| 耗时 / 进程 | 研究包记录 797.97 s（8 行 resume 后 992 行，不可直接比较） | **443.96 s / 6 进程** |
| 检查点 | 研究包完整 | schema 3、1,000 条、`PRAGMA integrity_check=ok`、SHA `c5d7f15…` |

逐题与冻结记录对照：程序 1,000/1,000 相同、base/score/nodes/schedule_attempts 0 差异、四路线
（config/nodes/score/error）0 差异、7 个位宽桶完全一致；`scored_0775` 在本环境下程序与冻结记录
完全相同（181 步、`attempts=0`）。**未直接替换历史归档**：仓库归档仍保留 macOS 运行产出的
`05e7b630…`，两份都是独立的合法 175,604 结果，差异仅来自工具链平局；参考工具链结果与冻结记录的
一致性记录在 `docs/reports/v9-integration.json`。

## 8.4 P0-3：同工具链全量等价性验收（实际结果）

方法：使用冻结研究包源码（`v9_stage2/` 的 `experiment/optimized/polish/scheduler/stage2/run_full`）
与当前功能化移植实现，分别用**同一台 VM、同一 Python 3.13.3、同一 `g++-14`、同一 flags、同一官方
题目数据、同一冻结参数/种子**从零独立求解 1,000 题；参考实现使用本机重新编译的 GCC 二进制，
移植实现使用 `native/build.py` 构建的同一 SHA 二进制。两个实现进程互相独立，不共享输出或检查点。
参考实现结果：1,000/1,000、175,604、最长 415、CSV `5ab0b72c…`、耗时 429.97 s（6 进程）。

| 对照项 | 差异数 |
|---|---:|
| 完整最终程序 | **0 / 1,000** |
| Stage 1 分数 | 0 |
| Stage 2 最终分数 | 0 |
| DAG 节点数 | 0 |
| 调度尝试次数 | 0 |
| 四条构造路线（config/nodes/score/error） | 0 |
| 路线失败状态 | 参考 0 / 移植 0 |
| 最终程序合法性（独立 `verify.py`） | 两者均 1,000/1,000 |
| 三份 CSV（冻结、参考实现、移植实现）逐字节 | **全部相同** |

两者与冻结记录也完全一致（`submission_v9_stage2.csv` / 研究检查点逐题 0 差异），因此
"同工具链原版 vs 移植版一致"的验收条件已满足，且 `scored_0775` 的差异被确认为 macOS Apple Clang
与 Linux GCC 的容器迭代/平局行为差异，不是移植逻辑错误。证据汇总：`docs/reports/v9-integration.json`。

## 8.5 P0-1：原生编译器缓存修复

发现的真实问题（两处）：`_manifest_matches()` 不比较显式 `SANTA_CXX`，缓存 Clang 构建会静默满足
后来的 GCC 请求；`_build_locked()` 在因其他原因重建时优先复用旧 manifest 编译器，忽略新显式指定。
修复：显式编译器（`SANTA_CXX`/参数）经 PATH/绝对路径/symlink 解析后拥有最高优先级；manifest
（schema 2）比较 resolved 路径、版本、family、flags、compat 使用、源码哈希、二进制路径与哈希；
显式编译器缺失/不可用立即报错且不回退；未指定时保持原有自动探测与缓存复用；`construct.py` 的
进程级二进制缓存改为按 manifest 文件签名失效，重建/换编译器后不会沿用旧路径；AppleDouble
`._*`/`.DS_Store` 元数据文件排除出源码指纹。新增 `tests/test_native_build.py` 15 个回归测试
（本地 macOS 与 Linux GCC 均通过），覆盖任务要求的 9 个场景 + manifest 字段篡改 + 检查点因编译器
变化拒绝恢复；CI 的 Ubuntu 环境使用真实 g++，macOS 使用真实 Apple Clang，双编译器切换用包装脚本
模拟身份差异（真实编译仍由本机编译器完成）。

## 8.6 P1-1：正式归档 CSV 回放与混合重建（实际结果）

用官方 `puzzles.csv` + 独立 `src/verify.py` 完整回放：

| 归档 | 题数/合法 | 指令数 | 最长程序 | SHA-256 | 与报告一致 |
|---|---:|---:|---:|---|---|
| V8 独立 | 1,000/1,000 | 194,444 | 535 | `6f15091b…` | 是 |
| V9 独立 | 1,000/1,000 | 175,604 | 415 | `05e7b630…` | 是 |
| V8+V9 混合 | 1,000/1,000 | 174,884 | 392 | `fe973ac4…` | 是 |

用 `src/merge_submissions.py` 从两份独立 CSV 重新生成到临时目录：1,000/1,000、174,884、392、
`from_first=137`、`from_second=863`（含 30 平局按规则取 V9）、逐题公式错误 **0**，重新生成文件与
归档混合 CSV **逐字节一致**（`fe973ac4…`）。混合工具不在求解/检查点路径中。

## 8.7 P1-2 / P2-3：验收报告与历史指纹审计

- 新增 `docs/reports/v9-integration.json`（kind=`santa-v9-integration-acceptance`，不进入 V1–V9
  成绩曲线，不被 `build_report.py` 当作正式报告），包含环境、源码/原生指纹、全量复现、同工具链对照、
  归档校验、检查点、测试、CI、限制与 `acceptance_status=conditional_pass`；
  新增 `tests/test_acceptance_report.py` 7 个一致性测试（归档哈希与工作树、源码指纹、曲线隔离）。
- 历史指纹抽查（`git show <commit>:<path>` + SHA-256）：`v8.json` 的 4 个记录文件全部对应
  `c9fdd61`；`v8-refactor.json` 的 10 个 solver 源码全部对应 `0ec0ec0`。未全量复核所有历史报告，
  已列为限制。

## 8.8 P0-4 / P1-4 / P2：CI、文档与 Web

- CI：main 合并提交的真实 Actions run **success**（见 §8.1）；本轮验收提交未推送，未跑 CI。
- 文档：更新 `docs/progress.md`（追加本节验收记录）、`competitions/santa-2026/README.md`
  （参考工具链复现与缓存规则）、`docs/reports/README.md`（v9-integration 类别）、`AGENTS.md`
  （`SANTA_CXX` 优先级规则）。
- 生成物：`Santa-2026-Interactive-Report.html`、`web/simulators.html` 重建并通过
  `--check`；`web/build/santa-review.json` 按项目流程在测试与回放核对后显式刷新；
  `version-scores.png` 由 `version-scores.mmd` 用 mermaid.ink 重绘为 V1–V9；浏览器复验
  模拟器与报告（Chrome 158 headless、离线）见 `docs/progress.md` 与 `v9-integration.json`。
- 仓库卫生：确认无官方数据、SQLite、编译产物、日志、`._*`/`.DS_Store` 被跟踪；
  `.gitignore` 增加 `._*`；无新增临时/重复文档。

## 8.9 剩余限制与最终结论

仍未完成/不可验证：

1. **本轮验收提交未推送**（未获推送授权），因此没有针对 `fix/santa-v9-final-acceptance` 的 CI 结果；
   已验证的是已合入 `main`（`8858a6a`）的 CI。
2. GCC 参考复现环境为 Ubuntu 25.04 / GCC 14.2.0 / Python 3.13.3（冻结记录 Python 3.13.5），
   输出仍逐字节一致；未在 x86_64 或 Windows 复验。
3. 浏览器只做 Chrome 158 headless 自动化离线验收，未测 Safari/Firefox、真机与人工逐项点击。
4. 历史报告源码指纹为抽查（14 个文件），未全量复核。
5. V9 无全局最优性证明；本轮未改动冻结搜索策略，未开始 V10。

**最终状态：V9 有条件通过**。条件：把本轮验收提交推送并让 GitHub Actions 通过（本地测试、构建、
Linux/GCC 全量复现、同工具链全量等价、归档回放、检查点与浏览器复验均已实际执行并通过）。
