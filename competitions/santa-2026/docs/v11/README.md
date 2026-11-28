# Santa V11 冻结 R16

正式求解从当前题的初值、目标、寄存器数和数值上限生成两组候选。R8 先用目标顺序、因子残差、双层构造和同余构造生成值图。超图合并把同一个值的不同表达式视作可选入边，MILP 从这些候选边中寻找共享子图，然后尝试以两步或三步局部合成替换昂贵子图。调度器把依赖图编译为寄存器指令，比较时按实际指令数计分，包含寄存器压力导致的重算。

另一组引入可供多个目标共享的自由基底，分别评价顺序构造、基底构造、三步合成、四步合成。两组候选逐一回放，同长度维持冻结枚举顺序。数学构造和搜索预算来自冻结源码。历史答案只用于事后比较。R16 后期多基底实验没有进入正式求解器。研究全量中 R8 单组 161,446，基底组单独 161,711。两组结合为 158,955。Dev100 的附件记录为 15,936，V10 对照为 16,494。

[17 轮研究记录](rounds/) · [千题研究报告](FULLTEST_REPORT.md) · [独立审计](audit.json) · [独立验证](validation.json) · [历史择优验证](merged_validation.json) · [机器可读报告（report-only）](../reports/v11.json)

从赛题目录运行以下命令。官方固定分层通过输入 SHA-256 识别。每组任务对应一道题的一条组路线，因此两组全部完成才计为一题。

```bash
python -m pip install -r requirements.txt
python src/algorithms/native/build.py
python src/graph_solver.py data/puzzles.csv --jobs 4 --checkpoint experiments/v11.sqlite \
  --output experiments/v11.csv --stop-after 16
python src/graph_solver.py data/puzzles.csv --jobs 4 --checkpoint experiments/v11.sqlite \
  --output experiments/v11.csv --resume
python src/verify.py data/puzzles.csv experiments/v11.csv
```

需要固定 Dev100 或留出集时，在首次运行和恢复时都传入相同的 `--split dev` 或 `--split holdout`，并使用独立数据库。任意练习输入可直接运行统一 CLI，也可使用新 schema 5 检查点。旧冻结运行数据库不能直接恢复。MILP 使用墙钟限时，编译器、依赖和负载可能影响重跑结果。实验快照完整保存在原始交付 ZIP 中，清单保存在本目录。

当前生产源码已按职责重构至 `src/algorithms/`，原实验目录和历史版本实现不再是运行依赖。详见[当前架构](../current-architecture.md)。上述成绩仍为原冻结研究记录。
