# 当前求解器架构 · V11 等价重构

## 目标与边界

只保留当前算法，不把一次研究发布变成一个永远存在的 Python 模块。原 V11 的两个有效候选组合、搜索参数、执行顺序、等长选择规则与八个 C++ 内核均保留。没有使用任何历史答案作为候选。此改造属于工程重构，而非新的数学算法版本；`SOLVER_VERSION` 仍为 `v11`。

本次重构的基线是 main `01567f3912f56df937e46ff99dde56a2036cdc55`。工作在独立分支 `refactor/santa-current-solver` 上进行，未直接改动远程 main。

## 职责划分

| 模块 | 责任 |
|---|---|
| `graph_solver.py` | 唯一 CLI、参数及输入检查、固定分层选择、原生构建预检 |
| `checkpoint.py` | 组任务调度、schema 5 持久化、恢复、完整性检查及原子导出 |
| `algorithms/solver.py` | 两个候选组 `r8`/`basis`、逐候选 replay 与等长选择 |
| `algorithms/portfolio.py` | 顺序/因子/双层/同余构造、超图联合、限时 MILP、局部合成 |
| `algorithms/basis.py` | 自由基底组合与三步/四步合成 |
| `algorithms/construct.py` | 原生执行、协议解析与统一序列化 |
| `algorithms/graph.py` | 算术 DAG 编译 |
| `algorithms/schedule.py` | 寄存器压力调度及共享候选评价 |
| `algorithms/schedule_local.py` | 调度次序局部搜索 |
| `algorithms/optimize.py` | 从新构造图的受限无环超图 MILP 中选边 |
| `algorithms/common.py` | 算术与内部回放 |
| `algorithms/native/` | 八个独立内核、C++17 构建/缓存/指纹 |
| `verify.py` | 独立验证，不 import 算法 |
| `merge_submissions.py` | 归档后处理，不进入求解路径 |

旧 V9/V10、V11 转接层、实验目录和 `run7.py` 重复 runner 全部退出生产路径。候选名称 `r8`、`basis` 及部分旧路径式指标名称只用于保持冻结运行的指标与等长顺序，不代表历史求解版本。原生内核源码保持逐字节相同，避免改动 C++ 搜索顺序和性能。

## 迁移清单

**删除的运行代码**（历史仍可从 Git 提交 `01567f3` 取得）：

- `algorithms/v9.py`、`algorithms/v10.py`、`algorithms/v11.py`、`algorithms/rewrite.py`；
- `algorithms/v11_frozen_fulltest/`（含 `run7.py`、`run8.py`、`scheduler*.py`、`exact_graph.py`、各实验变体、研究用 `splits.json`；其中 8 个内核源码移入 `algorithms/native/`）；
- `algorithms/native/constructor_{wide,mitm,pressure,joint,cf,order_fast,order_cf}.cpp`；
- 仓库中未跟踪的旧编译二进制（`v11_frozen_fulltest/{order,factor,...}`）同时清理，`experiments/native-current/` 是唯一构建输出。

**新增/替换的源码**：

- `algorithms/portfolio.py`、`basis.py`、`optimize.py`、`schedule_local.py`、`splits.json`；
- `algorithms/native/{order,factor,bilayer,congruence,hyper,synth,basis,synth_extended}.cpp`；
- 重写的 `solver.py`、`construct.py`、`graph.py`、`schedule.py`、`checkpoint.py`、`graph_solver.py`；
- `requirements.txt`（NumPy/SciPy）与新的 CLI 参数约束。

八份内核源码与冻结研究逐字节一致：

| 内核 | SHA-256 |
|---|---|
| `order.cpp` | `a8b3339099a65176e4efb97f85a0dbb1d676cd9b0b07fdeedf91cd7421f17d9c` |
| `factor.cpp` | `7587d875aca8a8947a744c51aa581b51c41ae3c1133eb9104ca76b72ba1cf657` |
| `bilayer.cpp` | `97f1d209fafb056c5b9001db8ede61198ee726d3c995becdff0f78e2508ddaf2` |
| `congruence.cpp` | `ee2cbc3b9122777fed7bab3194f6df8e7ae150f91abb83ff68a6950dc90163c1` |
| `hyper.cpp` | `56cd2141b39d554642ddb445044ee684bfa72a5cfb6c1a4850f375c27d83f5db` |
| `synth.cpp` | `6913779bd1065c203ded8a9e224cfaba1ad049f9bd63d489fa5fead1e5ac5b1f` |
| `basis.cpp` | `9e2f06a861b8f9a520b63482c19346b00baca607dd4cd1ac3f557d55400360bb` |
| `synth_extended.cpp` | `3eec2c229022f38f8fb2691e4af7b1a7344d97458b1f9d161313f0b99e4e80db` |

## 求解与检查点

官方输入不入库；新 CLI 自动检查并构建原生内核。`--version v11` 保留作兼容选项；旧版本及 V10 policy 不再支持。组任务检查点 schema 5 不兼容旧版，必须创建新 SQLite 文件；指纹绑定输入、固定分层、两组任务、全部生产 Python 与八个 C++ 源、兼容头、构建脚本、实际二进制、编译器/flags、Python/NumPy/SciPy 与线程环境。`--stop-after N` 指 N 个新组任务而非 N 道题，有该参数时不导出；每题两组都完成才计入总分。程序和检查点始终从当前输入生成，历史 CSV 只可事后验证或回放。

## 实际验证

环境：macOS `Darwin-27.2.0-arm64`、Apple Clang 21.0.0（`/usr/bin/g++`，通过 `compat/bits/stdc++.h`）、Python 3.13.2、NumPy 2.4.3、SciPy 1.17.1，`OPENBLAS_NUM_THREADS=1`、`OMP_NUM_THREADS=1`，4 个并发进程。原版与重构版使用同一工具链，各自从官方题重建；没有读取历史提交或答案。

### 四题冒烟对照

| 官方题 ID | 原 V11 指令数 | 重构 V11 指令数 | 程序 |
|---|---:|---:|---|
| scored_0001 | 258 | 258 | 完全一致 |
| scored_0128 | 124 | 124 | 完全一致 |
| scored_0500 | 96 | 96 | 完全一致 |
| scored_1000 | 261 | 261 | 完全一致 |
| 合计 | 739 | 739 | 4/4，CSV 字节相同 |

原版与重构版输出 CSV 的 SHA-256 均为 `ef9bda35abd8385208f01c69d5da604e179a782fa617250a3601f1b16b50d32c`。

### 固定 Dev100

两版使用 `algorithms/splits.json` 中同一批 100 个题 ID、独立 SQLite 与相同 `--jobs 4`：

| 版本 | 完成 | 指令数 | 输出 CSV SHA-256 |
|---|---:|---:|---|
| 原 V11 | 100/100 | 15,948 | `53f6ecb0c62f6d87f08d05a6011574fe03ca908512448f1cc73bcdfe151c7d6e` |
| 重构 V11 | 100/100 | 15,948 | `53f6ecb0c62f6d87f08d05a6011574fe03ca908512448f1cc73bcdfe151c7d6e` |

逐题程序差异 0。研究记录的 Dev100 是 15,936（Linux/GCC 环境）；本机同一工具链下两版都得到 15,948，因此差异来自环境而非重构。

### 固定 holdout100

同一批 100 个留出题 ID，独立检查点与输出：

| 版本 | 完成 | 指令数 | 最长 | 输出 CSV SHA-256 |
|---|---:|---:|---:|---|
| 原 V11 | 100/100 | 16,015 | 338 | `01837f1e49d0a13a2948377b8c4aeac3cc05ac9453e1749b59501a140dae0eb9` |
| 重构 V11 | 100/100 | 16,015 | 338 | `01837f1e49d0a13a2948377b8c4aeac3cc05ac9453e1749b59501a140dae0eb9` |

逐题程序差异 0。Dev100 与 holdout100 的输出都在同一工具链、同一并发下**逐字节相同**，这比"总分接近"更强地支持等价性。

### 千题全量

| 版本 | 验证 | 指令数 | 最长 | 墙钟 | 输出 CSV SHA-256 |
|---|---:|---:|---:|---:|---|
| 重构 V11 | 1,000/1,000 | **159,057** | 354 | 1,378.6 s（4 进程） | `10ca22672a44fecc8e848ee7fa9df90e1ca4560fc817dc1e87567b36c5d5abfd` |
| 原 V11（基线 worktree） | 1,000/1,000 | **159,057** | 354 | 1,579.9 s（4 进程） | `10ca22672a44fecc8e848ee7fa9df90e1ca4560fc817dc1e87567b36c5d5abfd` |

重构版另用 `src/verify.py` 对完整 1,000 题再验证一次，结果相同。原版与重构版的千题输出**逐字节相同**（分数 159,057、最长 354、逐题程序差异 0），因此等价性在完整题集上成立。与原研究记录 158,955（最长 348）相差 +102 步（0.064%）；原研究是 Linux/GCC 环境，本机 Dev100/holdout100/千题的原版对照都显示同类环境差异，不是重构回归。

## 未完成/合入验收

- 千题全量复跑与独立验证已完成（重构版 159,057、1,000/1,000 合法；基线同环境逐字节相同），详见 [refactor-acceptance.md](refactor-acceptance.md)。
- 旧 V9/V10 与冻结 V11 只能从 Git 提交 `01567f3` 复现，不能与 schema 5 检查点混用。
- MILP 使用墙钟时间预算，因此跨机器、不同负载下不能保证逐题完全复现；本机 Dev100 与研究记录差 12 步即属于此类环境差异，已用原版对照排除重构回归。
- `submissions/latest.json` 仍指向真实存在的 V10 CSV（164,306）；V11 的 158,955 记录为 report-only，没有伪造 CSV。
