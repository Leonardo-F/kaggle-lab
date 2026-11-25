# Santa 2026 · V8 等价重构执行计划

> 交付对象：Codex / ChatGPT Work / 仓库维护者。本文是可执行任务说明，不是已经完成的实验报告。
>
> 审计基线：`Leonardo-F/kaggle-lab` 的 main，commit `9337a3549bea09257cbf36ae1f8da2cbd452942b`。工作开始时重新核对实际 HEAD；如果 V9 或其他修改已进入 main，不得覆盖，须先记录差异并调整本计划。

> **执行状态（2026-11-25）：** 本计划已执行。功能模块、CLI、检查点、测试、文档与模拟器均已更新；1,000 题独立复跑的逐题程序与八阶段比对可另存为可选的 `docs/reports/v8-refactor.json`；该文件缺失时 Web 构建使用原始 V8 记录，不视为遗漏或失败。历史 V1–V8 仍由提交 `9337a3549bea09257cbf36ae1f8da2cbd452942b` 保存，main 不再保留版本模块。

## 0. 任务目标与边界

在 `competitions/santa-2026` 内，把按 V1–V8 组织的实现改为按功能组织的一套最新求解器。历史版本保存在 Git 提交中；历史实验、提交 CSV、交互报告与回放功能继续保留。

本次只做 **V8 Final 等价重构**，不混入 V9 的搜索创新，不调参、不改变候选顺序、随机数调用、择优规则、整数运算或寄存器语义。当前仓库的基线为 1,000 题、194,444 条指令，逐题合法，历史复跑 CSV SHA-256 为 `6f15091bcfddf4335f69126c2088696dfa7a9a3fcb9c4de6dbaa448aca1279fd`。该数字来自既有报告，不是此次重构的测试结果。

必须遵守根目录 `AGENTS.md`。默认本地分支、本地提交；**未经明确授权，不得 push，也不得创建或修改任何远程分支、Tag、Release**。禁止把官方题目数据、SQLite、临时结果或凭据提交到公开仓库。历史答案仅可用于独立验证及回归比较，禁止作为求解器输入。

## 1. 现状与目标布局

当前 `src/algorithms/` 共 14 个 Python 文件：`__init__.py`, `common.py`, `v1.py`–`v8.py`, `v8_group.py`, `v8_register.py`, `v8_rewrite.py`, `v8_three.py`。V8 入口转发到 group，group 使用 three/rewrite/register，rewrite 从 V7 生成初始程序；V7 依赖 V6、V5，V6 依赖 V5，V5 依赖 V4、V3，V4 依赖 V3。V1/V2 文件不在 V8 当前算法调用链，但仍受旧 CLI 和测试引用。V3 内的 `optimize_v2` 仍有实际用途，不能因名称删除。

目标（约 7 个算法文件；允许为清晰的无环依赖作最小调整）：

```text
competitions/santa-2026/
├── README.md
├── Santa-2026-Interactive-Report.html
├── src/
│   ├── algorithms/
│   │   ├── __init__.py
│   │   ├── common.py       # 基础运算、回放、固定进制构造等公共逻辑
│   │   ├── construct.py    # 自适应构造、反查、邻近商、乘积与模余数
│   │   ├── graph.py        # 依赖图提取、闭包、图融合与路径选择
│   │   ├── rewrite.py      # 双/三运算重写、成组修复
│   │   ├── schedule.py     # 各种合法编译、寄存器调度与压力评估
│   │   └── solver.py       # 唯一公开完整求解流程、配置、阶段指标
│   ├── graph_solver.py     # CSV CLI
│   ├── checkpoint.py      # SQLite 与指纹
│   ├── verify.py          # 独立验证器
│   └── simulator.html
├── tests/
├── docs/
│   ├── algorithm-evolution.md
│   ├── diagrams/
│   └── reports/
└── submissions/
```

依赖方向：`solver` 调用 `construct/graph/rewrite/schedule`；`rewrite` 可调用 `graph/schedule/common`；`schedule` 可调用 `graph/common`；`graph/construct` 使用 `common`。若原构造器与图优化有双向依赖，将完整阶段编排提升到 `solver`；不要通过循环 import 或延迟 import 掩盖结构问题。不要为凑文件数量把不相关模块合并。

## 2. P0：冻结基线

- [ ] 在本地执行 `git status --short`、`git branch --show-current`、`git log -1 --oneline`，阅读根 `AGENTS.md`、赛题 README、现有 docs/reports 与相关测试。
- [ ] 有未提交修改时保护它们，不用 `reset --hard`、`clean -fd` 或覆盖用户文件。创建本地分支 `refactor/santa-v8`（若已存在，先检查）。
- [ ] 记录实际基线完整 commit、Python 实现/版本、平台、输入 SHA-256、参数、进程数、`PYTHONHASHSEED`（若设置）、历史输出及报告哈希。
- [ ] 核查历史复现入口；本审计提交同时含 V1–V8，可直接用这个 SHA 的 Git worktree 执行旧版本。进一步核对各版本的真实发布提交；Tag 仅在获授权后创建，不伪造历史标签。
- [ ] 在独立 worktree 运行当前 V8 的原有单测及固定小样本，记录逐题 program、阶段指标和耗时。若资源允许，原版全量复跑；若不执行，注明以既有归档为全量回归参考，不称为新鲜复跑。

```bash
# 从仓库根目录，在无冲突且有本地可用 Git 对象时
BASE=9337a3549bea09257cbf36ae1f8da2cbd452942b
git worktree add --detach ../kaggle-lab-santa-baseline "$BASE"
git switch -c refactor/santa-v8
```

## 3. P1：先迁移，后去重

| 旧文件/函数 | 新归属 | 迁移要求 |
|---|---|---|
| `common.py`：`ops`, `replay`, `sparse` | `common.py` | 原语义保留；`verify.py` 仍独立 |
| V3 `adaptive`、V4 `adaptive_v4`、V5 `adaptive_v5` | `construct.py` | 初期保留三种策略实现、参数与生成顺序，不直接用 V5 替代全部 |
| V3 `joint_polish` | `graph.py` | 保留融合及循环安全检查 |
| V3 `optimize_v2/optimize`、V4/V5 优化入口 | `solver.py` 或适当的私有阶段 | 改为功能命名；保留候选、早停、失败回退、严格比较 |
| V6 `global_select`, `path_union` | `graph.py` | 维持 180/300/120/400 等各调用点预算区别；保留内部候选轨迹 |
| V7 `extract`, `plans` | `graph.py`, `construct.py` | 首次出现图及特征候选次序不变 |
| V7 `schedule`，V8 `compile_graph`，V8 register `schedule` | `schedule.py` | 区分三种调度器，避免名称覆盖；维护各自择优、寄存器保护及重算规则 |
| V8 rewrite `closures`, `pairs` | `graph.py` 或 `rewrite.py` | 注意图有环/缺失值处理、缓存、枚举顺序 |
| V8 rewrite `rewrite`、three `inverse/exclusive/three`、group `cut_repair` | `rewrite.py` | 原搜索、随机种子、strict/neutral 两套策略不变 |
| V6/V7/V8 多级 `optimize` | `solver.py` | 展开为功能阶段；保留所有在本轮生成的合法基线 |

迁移后的公开接口建议：

```python
# algorithms/__init__.py
from .solver import SOLVER_VERSION, solve
```

`solve(row)` 返回 `(puzzle_id, program, metrics)`，`SOLVER_VERSION = "v8"`。阶段函数可返回辅助候选及图状态，但不是公开多版本求解器。内部阶段名优先功能语义；现有报告的 `v7`, `list_schedule`, `v8`, `v81`, `v82`, `v8group_strict`, `v8group_neutral`, `v8final` 键保留为兼容指标，不等于独立版本模块。若需改指标名，显式提供旧键映射，保证 JSON 消费方正常。

**实际执行顺序必须按原 V8 冻结代码迁移，而不是按架构图重新排序。** 构造、全局融合及编译存在交叉调用，不能简单写成四次独立调用。保留 `portfolio=3`、`path_rounds=400`、`schedule=True`、`retain_v6_graphs=False` 的 V7 内部配置及 V8 后续所有默认配置。保留 V8 双运算两轮、三运算/等成本阶段原预算、严格成组 6 轮、等成本成组 8 轮、最终 32 个顺序候选的行为；以源码为准逐个核对。

- [ ] 迁移后运行小样本对比，先确认逐题程序、阶段成本、错误回退一致，再删除旧实现文件。
- [ ] 从根目录搜索 `algorithms.v*`、`--version`、`optimize_v*`、`DEFAULT_VERSION`、`CONFIGS`、`santa-review` 等引用，分类处理。历史文档中的版本名允许存在。

## 4. P2：去重（只做经过证明的等价修改）

V3–V5 构造器存在结构重复，但搜索宽度、候选排序和评分可能不同。优先抽取纯函数和共同数据结构（表达式合法性、成本计算、寄存器公共原语）。对同一输入运行旧/新策略，验证返回候选和顺序一致。不能证明等价的重复代码可以暂时保留于同一功能模块，并记录原因；禁止为了减少行数或文件数牺牲分数。

保留排序 tie-break、字典插入顺序、集合遍历、随机数实例与消耗次序、缓存键、异常边界、短路及 `len(program)` 比较。每次小提交后跑回归；P2 如果改变输出，回退相应修改或把它单独列为 V9 研究，不纳入本次。

## 5. P3：CLI、检查点、测试

CLI 默认只求解最新算法：

```bash
python src/graph_solver.py data/puzzles.csv --output experiments/v8-refactored.csv --jobs 8
```

保留 `--version v8` 作为当前版本的兼容别名（旧版 v1–v7 给出明确的 Git worktree 复现指引）；删除只对旧版生效的 CLI 参数或明确报错，不能默默接受并忽略。实验配置留在 `solver` 中可审计；不要将每个旧阶段恢复成独立 CLI 版本。

`checkpoint.py`：统一 worker 调用同一个 `solve`，自动从算法模块目录收集源码文件指纹（排序、相对路径确定），同时绑定 CLI/检查点/验证器源码、输入、参数及 Python 版本；保留记录摘要、回放、原子导出、文件锁和拒绝篡改的机制。旧布局的检查点必须明确拒绝续算，提示使用原 SHA 或新建 SQLite；不要跨指纹复制结果来凑全量测试。完整输出的条件是所有输入题均已完成，而正式集的验收数量为 1,000。

- [ ] 更新 `tests/test_solver.py`，测试默认入口、显式 v8 别名、旧版本错误信息、只读 puzzle CSV、3 步小题、阶段输出接口、禁止 `--reference`。
- [ ] 更新 `tests/test_checkpoint.py`，覆盖中断/续跑、源码和配置不匹配、记录篡改、重复运行、并发锁、完整后才导出、V8 八阶段指标。
- [ ] 保持 `verify.py` 独立；增加/保留除法、未初始化、寄存器编号、边界、目标曾经命中和指令限制测试。
- [ ] 使用 practice 数据核验（实际行数以 CSV 为准），再使用正式数据独立求解；测试 jobs=1 与多进程，固定样本逐题比对。

```bash
# 在赛题目录，命令以实际可用数据位置为准
python -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/test_replay.cjs
python src/graph_solver.py data/practice_puzzles.csv --output experiments/practice-refactored.csv --jobs 4
python src/verify.py data/practice_puzzles.csv experiments/practice-refactored.csv
python src/graph_solver.py data/puzzles.csv --output experiments/v8-refactored.csv \
  --checkpoint experiments/v8-refactored.sqlite --jobs 8
# 如中断：同一命令追加 --resume
python src/verify.py data/puzzles.csv experiments/v8-refactored.csv
```

正式基线阶段总分：198388 → 198374 → 195705 → 195090 → 194881 → 194819 → 194797 → **194444**。逐题 JSON 程序优先要求完全一致；若 CSV 编码不同，区分文件字节哈希与规范化程序哈希，报告差异；如果实际程序不同，视为本次等价重构未通过，定位原因而不是仅接受总分相等。逐题比较和合法性验证只能在求解结束后进行，基线文件不得传进 solver。

## 6. P4：文档和交互模拟器

- [ ] 将随附的 `algorithm-evolution.md` 放入 `competitions/santa-2026/docs/`；保留原 `diagrams/`、`reports/` 目录。该稿清晰标记目标架构未验证，待重构完成后按实际实现更新状态、函数名、测试记录和命令。
- [ ] README 默认运行命令、Git worktree 复现、checkpoint 指南同步；保留历史提交 CSV 和 `submissions/latest.json`（等价重构不需要替换当前最佳结果）。
- [ ] 根 `AGENTS.md` 增加：main 仅保留当前求解器，历史代码使用 Git；算法变更必须独立求解与验证；历史结果和证据不得随源码删除。
- [ ] 检查 `src/simulator.html`、`Santa-2026-Interactive-Report.html`：旧版 CSV 导入和逐步回放保持，清楚标注内置 JS 自定义求解器不是 Python V8；更新实际源码链接与使用说明。保留现有离线交互能力。
- [ ] 根据根规则更新 `web/build/santa-review.json`，阅读 `web/build/README.md` 后运行已有生成脚本，不只手工编辑产物。

```bash
# 仓库根目录
python web/build/build.py
python -m unittest discover -s web/tests -p 'test_*.py' -v
```

检查统一入口 `web/simulators.html`、离线 HTML、CSV 导入、版本切换、寄存器回放、数学公式与相对链接；确认重构后的源码链接没有 404。若现有互动报告有独立生成器，以仓库实际构建流程为准。

## 7. 最终验收与交付

| 项目 | 通过标准 |
|---|---|
| 当前算法 | 仅一套公开求解器；约 7 个功能文件，无 `v1.py`–`v8*.py` 遗留运行依赖 |
| 全量 | 正式数据 1,000/1,000，独立验证合法 |
| 等价性 | 194,444；逐题程序与全部八阶段成绩一致 |
| 历史 | 原 commit 可 checkout/worktree；历史报告、CSV 与互动回放保留 |
| 检查点 | 新指纹可恢复，旧指纹拒绝，完整数据才导出 |
| 测试 | Python、Node、统一网页测试实际通过；记录未运行项 |
| 数据 | 不把官方题目或临时数据提交到 Git |
| 远程 | 未获明确授权则仅本地提交；不得擅自 push 或创建远程标签 |

可选记录一个重构报告 `docs/reports/v8-refactor.json`：实际基线 SHA、重构 commit、输入与输出哈希、逐题/阶段一致性、测试结果、运行时间、文件/行数变化、未验证项。缺失时 Web 使用原始 `v8.json`；存在但校验不通过时不得展示为等价重构成功。不修改历史 `v8.json` 的原始证据。

本地提交建议 `refactor(santa): consolidate V8 solver by algorithm responsibility`。交付时列出真实 commit SHA、diff 概要、实际运行命令及测试结果、失败项、剩余风险、是否推送。若全量未完成，只能标记未验收，保留 SQLite，不能声称已复现 194,444。

## 8. V9 后续研究

V8 等价重构验收后，再从它创建 V9 研究分支；直接修改相应功能模块，不再永久叠加 `v9.py`。V9 探索可以允许单题或阶段退化，以全量合法分数和实验记录评估；这与本次等价重构的严格逐题一致性要求不同。正式合并前独立复跑并报告。任何远程写操作遵守 `AGENTS.md`。
