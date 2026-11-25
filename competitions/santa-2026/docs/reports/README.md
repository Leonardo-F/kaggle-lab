# Santa 2026 报告目录说明

本目录保存 Santa 2026（The Elf Calculator）的机器可读历史证据：正式版本记录、研究消融记录、工程等价重构验收和混合归档。这里只说明每份文件的用途与读取关系，不重复 [algorithm-evolution.md](../algorithm-evolution.md) 的完整成绩表。

## 1. 四类报告

| 类别 | 文件 | 作用 | 是否被 [build_report.py](../build_report.py) 读取 |
|---|---|---|---|
| 正式版本 release | [v1.json](v1.json) – [v9.json](v9.json)（9 份） | 每代算法在同一官方计分集上的独立求解结果：分数、验证题数、输入/输出哈希、参数、源码/二进制指纹与复跑记录 | 是。`load_report_data()` 读取全部 `vN.json` 生成正式成绩曲线，并用 [submissions/latest.json](../../submissions/latest.json) 指向的报告做交叉核对 |
| 研究消融 ablation | [v3-handoff-ablation.json](v3-handoff-ablation.json)、[v5-handoff-ablation.json](v5-handoff-ablation.json)、[v9-stage2-ablation.json](v9-stage2-ablation.json)（3 份） | 小样本上的候选策略对照（V3 24 题、V5 8 题），以及 V9 Stage 2 冻结研究包的全量原始证据 | 否。只在 `algorithm-evolution.md` 以链接形式被引用 |
| 工程验收 validation | [v8-refactor.json](v8-refactor.json)（1 份） | V8 功能化等价重构的全量验收记录：同一官方题的两次全量运行、逐题程序/八阶段指标对照、检查点与测试结果 | 是。作为可选面板读取，固定对照原始 [v8.json](v8.json)，不进入成绩曲线 |
| 混合归档 merge | [v8-v9-merged.json](v8-v9-merged.json)（1 份） | 两份独立提交 CSV 的逐题取短后处理结果（174,884 步），记录来源、逐题选取计数、验证与哈希 | 否。只在 `algorithm-evolution.md` 与 [submissions/README.md](../../submissions/README.md) 中单列展示 |

正式成绩曲线只包含 release；消融、验收与混合归档**不得**混入正式版本曲线：它们不是同一数据集/同一口径的独立算法发布，也不代表新的算法版本。

14 份 JSON 体积合计约 40 KB，全部是研究证据。**保持现有路径，不做迁移**：数量少，分类信息由本 README 承担，避免无收益的路径变动带来的链接、构建常量和测试同步风险。

## 2. 每个文件的作用

### 2.1 正式版本（V1–V9）

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
| [v9.json](v9.json) | V9 动态字典构造与寄存器压力调度 | 本次 V9 合入提交（见报告 `solver_commit` 字段） |

早期 7 份报告在提交 `35a688d`（`Simplify Santa test and report layout`）中从 `experiments/reports/` 移到 `docs/reports/`；[v6.json](v6.json) 起直接写在本目录。历史版本化源码基线仍可从固定提交 `9337a3549bea09257cbf36ae1f8da2cbd452942b` 复现。

当前正式提交的最佳指针是 [submissions/latest.json](../../submissions/latest.json)（见 §4），指向 V9（175,604 步）。[v1.json](v1.json)–[v8.json](v8.json) 是历史记录，不会因新版本改写；报告生成器只按版本号读取，新的正式版本需要新增 `vN.json` 并同步 `submissions/latest.json` 与 Markdown 正式成绩表。

[v9.json](v9.json) 记录本次从官方 1,000 题、全新 schema 3 检查点的独立全量复跑：分数 175,604、Stage 1 182,205、最长 415 步、CSV SHA-256 `05e7b630…`；同时保存输入/输出哈希、冻结参数、编译器与两个原生二进制哈希、检查点完整性、练习数据集单独记录，以及和冻结研究记录的对照：逐题程序 999/1000 相同，唯一差异题 `scored_0775` 等长（181 步）但寄存器选择不同，归因于本机 Apple Clang 工具链与冻结记录 Linux GCC 在等分平局时的顺序差异（用冻结源码在本机重跑可复现移植版程序）。两阶段总分、逐题分数/节点/调度尝试数与选择桶全部一致，**未声称逐字节复现冻结 CSV**。

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

### 2.5 V9 Stage 2 原始研究证据（ablation）

[v9-stage2-ablation.json](v9-stage2-ablation.json) 保存冻结 V9 研究包的全量原始记录（Stage 1 182,205 → Stage 2 175,604、逐题桶、resume 8 行 + 992 行 797.97 s、Python 3.13.5/GCC 构建信息、交接 ZIP/报告/CSV/日志哈希），只作阶段研究和逐题证据对照；本仓库自己的复跑记录在 [v9.json](v9.json)。其耗时和研究包工具链不能与本地复跑直接比较。

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

当前独立版本是 V9；复跑需要先构建两个原生构造内核，再运行唯一求解入口（官方题目需自备）：

```bash
python3 src/algorithms/native/build.py
python3 src/graph_solver.py data/puzzles.csv --version v9 --jobs 8 \
  --checkpoint experiments/v9.sqlite --output experiments/v9.csv
python3 src/verify.py data/puzzles.csv experiments/v9.csv
```

V1–V8 历史版本需要固定提交中的版本化源码复现（当前 main 只保留功能化 V9 管线）：

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
