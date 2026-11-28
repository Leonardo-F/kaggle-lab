# Santa 2026 报告目录说明

本目录保存 Santa 2026（The Elf Calculator）的机器可读历史证据：正式版本记录（V1–V11）、研究消融记录、工程等价重构验收和混合归档。V11 是**报告支持、未附 CSV** 的研究记录（`artifact_status: "report-only"`），不改变可下载最佳归档指针。这里只说明每份文件的用途与读取关系，不重复 [algorithm-evolution.md](../algorithm-evolution.md) 的完整成绩表。V10 另附两份逐题指标 CSV（正式 1,000 题与固定留出集 100 题）。

## 1. 四类报告

| 类别 | 文件 | 作用 | 是否被 [build_report.py](../build_report.py) 读取 |
|---|---|---|---|
| 正式版本 release | [v1.json](v1.json) – [v11.json](v11.json)（11 份） | 每代算法在同一官方计分集上的独立求解结果：分数、验证题数、输入/输出哈希、参数、源码/二进制指纹与复跑记录；V11 额外标注 `artifact_status: "report-only"` | 是。`load_report_data()` 读取全部 `vN.json` 生成正式成绩曲线，并用 [submissions/latest.json](../../submissions/latest.json) 指向的报告做交叉核对；report-only 记录再与 `docs/v11/` 的独立验证/审计逐字段核对 |
| 研究消融 ablation | [v3-handoff-ablation.json](v3-handoff-ablation.json)、[v5-handoff-ablation.json](v5-handoff-ablation.json)、[v9-stage2-ablation.json](v9-stage2-ablation.json)、[v10-holdout100.json](v10-holdout100.json)（4 份） | 小样本上的候选策略对照（V3 24 题、V5 8 题）、V9 Stage 2 冻结研究包的全量原始证据，以及 V10 固定留出集 100 题策略消融 | 否。只在 `algorithm-evolution.md` 以链接形式被引用 |
| 工程验收 validation | [v8-refactor.json](v8-refactor.json)（V8 重构）、[v9-integration.json](v9-integration.json)（V9 合入验收）（2 份） | V8 功能化等价重构与 V9 合入的工程验收记录：同环境双实现逐题对照、全量复现、归档校验、检查点、测试与 CI 结果 | 否（v9-integration 不进入成绩曲线；v8-refactor 作为可选面板读取并固定对照原始 [v8.json](v8.json)） |
| 混合归档 merge | [v8-v9-merged.json](v8-v9-merged.json)（1 份） | 两份独立提交 CSV 的逐题取短后处理结果（174,884 步），记录来源、逐题选取计数、验证与哈希 | 否。只在 `algorithm-evolution.md` 与 [submissions/README.md](../../submissions/README.md) 中单列展示 |

正式成绩曲线只包含 release；消融、验收与混合归档**不得**混入正式版本曲线：它们不是同一数据集/同一口径的独立算法发布，也不代表新的算法版本。

18 份 JSON 体积合计约 116 KB，全部是研究证据；两份 V10 逐题指标 CSV 合计约 61 KB。**保持现有路径，不做迁移**：数量少，分类信息由本 README 承担，避免无收益的路径变动带来的链接、构建常量和测试同步风险。

## 2. 每个文件的作用

### 2.1 正式版本（V1–V11）

| 文件 | 版本 | 首次记录提交 |
|---|---|---|
| [v1.json](v1.json) | V1 多进制、自适应构造 | `d24fe9e`（原路径 `experiments/reports/v1.json`） |
| [v2.json](v2.json) | V2 宽搜索与依赖压缩 | `d04d4af`（原路径 `experiments/reports/v2.json`） |
| [v3.json](v3.json) | V3 反推查找、联合融合 | `a8e0015`（原路径 `experiments/reports/v3.json`） |
| [v4.json](v4.json) | V4 廉价邻近商 | `1f8b1db`（原路径 `experiments/reports/v4.json`） |
| [v5.json](v5.json) | V5 乘积池与模余数 | `378f74b`（原路径 `experiments/reports/v5.json`） |
| [v6.json](v6.json) | V6 动态无环、路径联合 | `b539c05` |
| [v7.json](v7.json) | V7 多构造器、调度 | `64db409` |
| [v8.json](v8.json) | V8 Final 子图重写、组修复、寄存器 | `c9fdd61` |
| [v9.json](v9.json) | V9 动态字典构造与寄存器压力调度 | V9 合入提交（见报告 `solver_commit` 字段） |
| [v10.json](v10.json) | V10 Full 七构造器、联合调度、目标顺序 | 本次 V10 合入提交（见 Git 历史；报告记录 `solver_commit_note`） |
| [v11.json](v11.json) | V11 两组候选、超图联合、自由基底 | V11 冻结研究记录（`artifact_status: report-only`，未附 CSV） |

早期 7 份报告在提交 `35a688d`（`Simplify Santa test and report layout`）中从 `experiments/reports/` 移到 `docs/reports/`；[v6.json](v6.json) 起直接写在本目录。历史版本化源码基线仍可从固定提交 `9337a3549bea09257cbf36ae1f8da2cbd452942b` 复现。

当前**可下载**正式提交的最佳指针是 [submissions/latest.json](../../submissions/latest.json)（见 §4），仍指向 V10 Full（164,306 步）。[v1.json](v1.json)–[v10.json](v10.json) 是历史归档，不会因新版本改写；[v11.json](v11.json) 是当前算法的研究报告，分数 158,955，但 `artifact_status` 为 `report-only`，没有 CSV，因此 latest.json 不能指向它，构建器也会拒绝这种指向。报告生成器只按版本号读取，新的正式版本需要新增 `vN.json` 并同步 `submissions/latest.json` 与 Markdown 正式成绩表。

[v10.json](v10.json) 记录 V10 Full 的正式结果：164,306 步、最长 349、1,000/1,000 合法，V9 175,604、Stage 3 165,110；逐题分数见 [v10-full1000-metrics.csv](v10-full1000-metrics.csv)，留出集消融见 [v10-holdout100.json](v10-holdout100.json)。该 CSV 由用户交付的 Linux/GCC 研究运行产生；本仓库用 `src/verify.py` 做了全量回放，并用本机 10 道代表性题和固定留出集 100 题独立重解，4 道差异题与冻结实现逐题对照。报告明确区分"研究全量成绩""本次回放验证"与"本次独立重解"，不声称本次合入完整重跑了 1,000 题。

[v11.json](v11.json) 记录当前 V11 的冻结研究结果：158,955 步、最长 348、1,000/1,000 合法；`r8` 单组 161,446、`basis` 单组 161,711、两组组合 158,955；Dev100 15,936（V10 16,494）；相对 V10 为 848/70/82。它的 `evidence.validation` 与 `evidence.audit` 分别指向 [../v11/validation.json](../v11/validation.json) 与 [../v11/audit.json](../v11/audit.json)，构建器在加载时逐字段核对分数、题数、最长步数与输入/输出哈希。归属 V8–V11 的归档择优 158,585 记录在 [../v11/merged_validation.json](../v11/merged_validation.json)，不是独立算法版本，也不进入版本曲线。

[v9.json](v9.json) 记录 V9 从官方 1,000 题、全新 schema 3 检查点的独立全量复跑：分数 175,604、Stage 1 182,205、最长 415 步、CSV SHA-256 `05e7b630…`；同时保存输入/输出哈希、冻结参数、编译器与两个原生二进制哈希、检查点完整性、练习数据集单独记录，以及和冻结研究记录的对照：逐题程序 999/1000 相同，唯一差异题 `scored_0775` 等长（181 步）但寄存器选择不同，归因于本机 Apple Clang 工具链与冻结记录 Linux GCC 在等分平局时的顺序差异（用冻结源码在本机重跑可复现移植版程序）。两阶段总分、逐题分数/节点/调度尝试数与选择桶全部一致，**未声称逐字节复现冻结 CSV**。

### 2.2 研究消融（V3/V5）

- [v3-handoff-ablation.json](v3-handoff-ablation.json)：24 道抽样题，控制组 6,941 步 vs 反查查找 6,537 步，22 改善、2 变长；逐题行保存在 `rows`。
- [v5-handoff-ablation.json](v5-handoff-ablation.json)：8 道抽样题，V4 构造器、乘积池、池+匹配、组合策略的逐题步数。

两份文件只用于说明“候选策略在样本上的方向性”，不能当全量分数，也不能与其他实验拼接成版本曲线。它们对应早期研究阶段的 handoff 结果；当前仓库不再保留当时的实验脚本，复现需要回到对应提交与原始交接包，而不要求本轮重新执行。

### 2.3 工程验收（V8 等价重构）

[v8-refactor.json](v8-refactor.json) 记录的是 V8 代码组织重构（按版本模块 → 按功能模块）的等价性验收，不是 V9 算法结果：

- `baseline`：冻结基线提交 `9337a354…`、归档 V8 CSV 及哈希、八阶段总分；
- `baseline_run` / `refactored_run`：两次独立全量运行（1,000 题）的分数、题数、阶段总分、检查点状态与提交哈希；
- `equivalence`：CSV 字节一致、逐题程序一致、八阶段总分一致、逐题指标差异计数为 0 等标志；
- `tests`：Python/Node/Web 测试、独立验证、报告与构建检查记录；
- `practice_run`：练习题数据集（200 题）的单独运行记录；
- `limitations`：未验证事项与不可比口径。

[build_report.py](../build_report.py) 的 `load_refactor_status()` 把它与**固定的** [v8.json](v8.json) 对照：顶层字段、嵌套基线/两次运行、八阶段键、哈希、检查点、测试分组和练习题隔离都要一致；任何一项矛盾都会显示“校验未通过”，不会展示等价重构成功。该文件是可选输入，缺失时报告照常构建并显示“未提供”。

### 2.4 V8+V9 混合归档（merge）

[v8-v9-merged.json](v8-v9-merged.json) 不是算法版本：它由独立的 [merge_submissions.py](../../src/merge_submissions.py) 对两份独立提交 CSV 做归档后处理——先用 [verify.py](../../src/verify.py) 完整验证两份输入，再按题号对齐、解析 JSON 程序并按 `len(program)` 取较短者，平局取 V9。结果是 1,000/1,000 合法、174,884 步、最长 392 步，V8 严格更短 137 题、V9 胜出 863 题（其中 30 题平局按规则取 V9），比独立 V9 再省 720 步。报告记录来源与输出 SHA-256、逐题选取计数和验证结果；该工具不参与求解，检查点源码清单也不包含它。

### 2.5 V9 合入与参考工具链验收（validation）

[v9-integration.json](v9-integration.json) 记录 V9 合入后的最终工程验收：在 Linux + GCC 14.2.0 参考工具链下从官方 1,000 题独立复现（175,604、最长 415、输出 CSV 与冻结研究包逐字节一致 `5ab0b72c…`），同一工具链下冻结研究源码与功能化移植实现逐题对照 1,000/1,000 一致，归档 CSV 回放与混合重建校验、schema 3 检查点与原生编译器缓存回归、真实 GitHub Actions 结果（main `8858a6a`）。它是工程验收证据，不是新的正式算法版本，也不进入 V1–V9 成绩曲线；正式成绩仍以 [v9.json](v9.json) 和 [submissions/latest.json](../../submissions/latest.json) 为准。

### 2.6 V9 Stage 2 原始研究证据（ablation）

[v9-stage2-ablation.json](v9-stage2-ablation.json) 保存冻结 V9 研究包的全量原始记录（Stage 1 182,205 → Stage 2 175,604、逐题桶、resume 8 行 + 992 行 797.97 s、Python 3.13.5/GCC 构建信息、交接 ZIP/报告/CSV/日志哈希），只作阶段研究和逐题证据对照；本仓库自己的复跑记录在 [v9.json](v9.json)。其耗时和研究包工具链不能与本地复跑直接比较。

### 2.7 V10 正式发布、逐题指标与留出集消融

[v10.json](v10.json) 是 V10 Full 的正式发布记录：1,000 题、164,306 步、最长 349、1,000/1,000 合法；V9 175,604、Stage 3 165,110；改善/持平/退化 857/143/0；order_fast 胜 102 题、order_cf 胜 131 题。它明确把"研究全量成绩""本次合入回放""本次独立重解"分开，`limitations` 说明没有在本次合入中完整重跑 1,000 题。逐题分数见 [v10-full1000-metrics.csv](v10-full1000-metrics.csv)（1,000 行，`id,v9,stage3,full,winner,seconds,repeat`）。

[v10-holdout100.json](v10-holdout100.json) 与 [v10-holdout100-metrics.csv](v10-holdout100-metrics.csv) 是固定留出集 100 题的策略消融：V9 18,192、Stage 1 17,023、Stage 3 16,912、Stage 3+Order 16,902、Stage 3+Hybrid 16,844、Adaptive 16,874、Full 16,842；Full 相对 Stage 3 改善 19 题。留出集是独立评测子集，不能与正式 1,000 题相加或替代正式成绩。

**V10 "Stage 1" 口径：** 指联合调度 + pressure 构造 + 两轮反馈修复之后、joint/cf 两条联合路线之前的成绩；它不是四路线原始编译长度，也不等同于 V9 的 `v9_stage1` 口径。正式集没有单独记录这一阶段总分，只有逐题 CSV 的 `v9/stage3/full` 三列与留出集消融。

## 3. 读取与校验边界

[build_report.py](../build_report.py) 读取本目录时遵守以下规则：

1. 只把文件名形如 `vN.json` 的文件当作正式版本报告；消融文件不参与解析。
2. 正式报告必须有整数 `version`、`puzzles`、`validated`、`score`；`version` 必须与文件名一致；版本号唯一并按数值排序（V10 排在 V9 之后）；`score >= 0`、`puzzles > 0`、`0 <= validated <= puzzles`。
3. 正式报告如记录 `puzzles_sha256` / `submission_sha256`，必须是 64 位小写十六进制；所有记录了输入哈希的正式报告必须指向同一官方数据集。
4. 当前最佳提交必须完整：[submissions/latest.json](../../submissions/latest.json) 与其指向的 `vN.json` 在 `version`、`score`、`validated`、`submission_sha256`、`puzzles_sha256` 上一致；该报告必须记录输入/输出哈希；`latest.json` 指向的实际归档 CSV 必须存在且 SHA-256 相符。其它历史 CSV 不要求都留在当前 checkout（`.gitignore` 规则也只跟踪命名规范的提交文件）。
5. 历史格式兼容：若旧报告缺少 `puzzles_sha256`/`submission_sha256`，只跳过该字段核对并在构建数据中记录兼容说明，**不补造数值**；当前最佳报告不允许走这条兼容路径。
6. Markdown 正式成绩表按“版本 → 分数”逐行结构化核对，而不是只检查全文出现过某个数字；表中缺少正式版本、出现没有报告文件的版本，或版本与分数对调都会导致构建失败。
7. 报告声明的源码指纹（`source_hashes`、[v8-refactor.json](v8-refactor.json) 的 `sources`）属于当时实验提交；正常构建只校验格式，不读 Git 历史、不联网、不把旧指纹当作当前工作树验证。

## 4. `submissions/latest.json` 与 `web/build/santa-review.json` 不是一回事

- [competitions/santa-2026/submissions/latest.json](../../submissions/latest.json) 是**当前最佳已验证独立发布指针**：记录版本、分数、验证题数、归档 CSV 文件名、该 CSV 的 SHA-256、题目集 SHA-256 和对应正式报告路径。它只应由真实的、通过独立验证的新全量正式结果更新。报告生成器用它展示当前最佳成绩与正式曲线末节点。
- [web/build/santa-review.json](../../../../web/build/santa-review.json) 是**源码审查指纹**：`solver.current_version` 加 [graph_solver.py](../../src/graph_solver.py)、[checkpoint.py](../../src/checkpoint.py)、[verify.py](../../src/verify.py) 和 `algorithms/*.py` 的源码 SHA-256，以及历史 CSV 回放槽位列表；由 `web/build/build.py` 静态读取、校验并在显式 `--refresh-santa-review` 时刷新。它不包含竞赛分数，也不是最佳提交指针。

两者必须分别核对、不能互相替代：`latest.json` 不能证明当前源码未被改动，`santa-review.json` 也不能证明某个 CSV 的分数或合法性。历史 CSV 回放槽位来自人工审核，不由 Python 文件名推断。

## 5. 本地复现方式

以下命令均在 `competitions/santa-2026/` 目录下执行；官方题目需按赛题规则下载到本地 `data/`，数据与检查点不入库。

```bash
# 重建 / 校验互动报告（报告读取 submissions/latest.json 与 docs/reports/*.json）
python3 docs/build_report.py
python3 docs/build_report.py --check

# 报告相关测试（含固定 V8 验收、反例和 Markdown 结构化核对）
python3 -m unittest discover -s tests -p 'test_report.py' -v
```

当前运行算法是 V11；本快照的正式归档索引仍为 V10，因为没有附带 V11 正式提交 CSV。当前求解与复现命令见 [V11 说明](../v11/README.md)。V1–V10 的历史代码使用原发布提交；以下 V1–V8 的固定提交保持有效。

```bash
# 在仓库根目录创建临时 worktree（已知提交，不依赖 Tag）
git worktree add --detach ../kaggle-lab-santa-history 9337a3549bea09257cbf36ae1f8da2cbd452942b
cd ../kaggle-lab-santa-history/competitions/santa-2026
python3 src/graph_solver.py /absolute/path/data/puzzles.csv --version v8 \
  --output experiments/v8-rerun.csv --jobs 8
python3 src/verify.py /absolute/path/data/puzzles.csv experiments/v8-rerun.csv
```

[v8-refactor.json](v8-refactor.json) 中 `commands` 记录了这次等价重构的全量命令和基线 worktree 命令；重跑后用 [verify.py](../../src/verify.py) 独立验证，再与归档 V8 结果比较。复跑记录属于研究证据，不要求每次文档改动都重跑 1,000 题。

## 6. 从 V9 开始的报告规范（推荐 schema）

V1–V8 的旧平铺格式保持不变。**V9 在解析器迁移完成前继续使用兼容的平铺字段**（`version`/`puzzles`/`validated`/`score`/`submission_sha256`/`puzzles_sha256`），并额外记录 `schema_version: 1`、`kind`、阶段分数、源码/原生指纹、检查点与局限性等不重复分数的来源字段；[v9.json](v9.json) 就是这样落地的。下面的 2.0 分组 schema 是后续版本的推荐目标，不是已存在的报告；采用新格式时必须同时新增单一兼容读取函数，把旧平铺和新格式归一为内部模型并补测试，不能同时维护两套正式分数来源。

| 字段 | 内容 |
|---|---|
| `schema_version` | 报告 schema 版本（整数）；旧平铺格式视为 `1`，新格式从 `2` 开始 |
| `metadata` | `kind`（`release` / `ablation` / `validation`）、算法版本、报告日期、完整 Git commit、生成者 |
| `input` | 数据集类型（official/practice/sample）、题数、输入 SHA-256；练习题必须明确标为独立数据集 |
| `config` | 搜索参数、随机种子、Python 版本、平台、工作进程数 |
| `result` | `score`、`validated`、`max_steps`、`elapsed_seconds` |
| `stages` | 有序阶段名称与对应分数，保留阶段语义；只允许同一轮运行的累加记录 |
| `artifacts` | 归档输出路径及哈希、必要的比较证据（如与基线 CSV 的逐字节/逐题对照） |
| `validation` | 合法性、回归/对照结果、测试命令与结果、验证范围（是否全量、是否重新求解） |
| `limitations` | 未验证事项、不可直接比较的实验资源、浏览器未覆盖项等 |

结构示例（**占位符，不是真实报告**）：

```json
{
  "schema_version": 2,
  "metadata": {
    "kind": "release",
    "version": "v9",
    "report_date": "YYYY-MM-DD",
    "commit": "<40 位完整 Git commit>"
  },
  "input": {
    "dataset": "official",
    "puzzles": 1000,
    "puzzles_sha256": "<64 位十六进制占位>"
  },
  "config": {
    "python": "3.x.y",
    "platform": "<OS>",
    "jobs": 8,
    "parameters": {},
    "seed": null
  },
  "result": {"score": 0, "validated": 0, "max_steps": 0, "elapsed_seconds": null},
  "stages": {"<stage>": 0},
  "artifacts": {
    "submission_path": "submissions/<name>.csv",
    "submission_sha256": "<64 位十六进制占位>"
  },
  "validation": {
    "full_scale": true,
    "verifier": "src/verify.py",
    "tests": {"passed": 0, "failed": 0}
  },
  "limitations": ["<未验证事项>"]
}
```

采用新格式时必须同时新增单一兼容读取函数，把旧平铺格式和新格式归一为内部模型并补测试；在解析器落地前，新版本报告应继续使用当前平铺字段（至少包含 `version`、`puzzles`、`validated`、`score`、`submission_sha256`、`puzzles_sha256`）。不要同时维护两套正式分数来源，也不要创建没有真实求解支撑的版本记录。

## 7. 历史验收字段的解释约定

- [v8-refactor.json](v8-refactor.json) 的 `pushed: false` 是**报告生成时**的远程状态（`pushed_at_report_creation` 的语义），不代表现在的 GitHub 仓库状态；它不应被改写为“当前未推送”。
- `unverified: []` 表示该次验收范围内“核心等价性没有未完成项”；浏览器手工逐项点击不在这次验收范围内，由 Node 回放测试、报告内容测试和构建/嵌入一致性检查覆盖，不能据此声称做过真实浏览器交互。
- `practice_run` 是独立练习题数据集，不能与正式 1,000 题混算、累加或拼成同一条阶段曲线。
- 历史报告的源码指纹只对应其声明的实验提交（例如重构报告对应重构提交），不是对之后 main 或当前工作树的验证；如需核对可用 `git show <commit>:<path>` 与 SHA-256 工具离线检查。
