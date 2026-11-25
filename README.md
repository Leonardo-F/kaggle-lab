# Kaggle Lab

独立实现的 Kaggle 竞赛解法、实验与复现工具。各赛题独立管理代码和依赖。当前结果和验证范围见 [PROGRESS.md](PROGRESS.md)。

| 赛题 | 项目入口 | 官方页面 |
| --- | --- | --- |
| Squares in Squares · 正方形装箱 | [离线模拟器、最佳 CSV 与认证命令](competitions/squares-in-squares/README.md) | [Kaggle](https://www.kaggle.com/competitions/squares-in-squares) |
| Google 量子电路编译 | [三个子题、提交格式与验证命令](competitions/google-quantum-circuit-compilation/README.md) | [Kaggle](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation) |
| Santa 2026 · The Elf Calculator | [求解器和验证命令](competitions/santa-2026/README.md) | [Kaggle](https://www.kaggle.com/competitions/santa-2026/overview) |

## 网页与互动页面

所有浏览器入口集中在 `web/`，目前只覆盖正方形装箱和 Santa 2026 两个赛题。Google 量子电路暂无网页报告，使用该赛题 README 中的命令行入口。

| 路径 | 作用 | 打开方式 |
| --- | --- | --- |
| [web/interactive.html](web/interactive.html) | 赛题互动页：两个标签，分别嵌入正方形装箱模拟器和 Santa 2026 算法互动报告 | 需与仓库文件一起打开；支持 `#squares` / `#santa` |
| [web/simulators.html](web/simulators.html) | 统一离线模拟器：把两个赛题模拟器嵌入成一个 HTML | 可单独下载，约 8.7 MB |
| [web/build/](web/build/) | 统一模拟器的构建源码：`build.py`、`template.html`、`santa-review.json` | 见 [web/build/README.md](web/build/README.md) |
| [web/tests/](web/tests/) | 构建一致性与互动页结构测试 | `python -m unittest discover -s web/tests -p 'test_*.py' -v` |

各赛题的原始页面仍可单独打开：

- 正方形装箱：[SquarePackingStudio-standalone.html](competitions/squares-in-squares/simulator/SquarePackingStudio-standalone.html)
- Santa 2026：[Santa-2026-Interactive-Report.html](competitions/santa-2026/Santa-2026-Interactive-Report.html)

`web/simulators.html` 是生成产物，不要手工修改。修改原始模拟器后按以下顺序重建并检查：

```bash
# 只有修改正方形装箱源码或认证布局时需要
python competitions/squares-in-squares/simulator/build_standalone.py
python web/build/build.py
python -m unittest discover -s web/tests -p 'test_*.py' -v
```

`web/build/santa-review.json` 锁定 Santa 求解器源码哈希和回放版本列表；源码变化但未复核时，构建会失败。

## 目录

- 各赛题的实验进展、版本结果和策略笔记放在 `competitions/<赛题>/docs/`。`web/` 集中存放浏览器入口、统一模拟器构建源码和测试。
- `competitions/<赛题>/algorithms/` 存放求解器和验证入口。`experiments/` 存放实验脚本、结果和测试。
- 装箱另含 `simulator/`、固定版本的官方评分器 `vendor/`，以及 `submissions/` 中的最佳 CSV 和逐题认证。量子电路和提交包在本地生成。

项目协作约定见 [AGENTS.md](AGENTS.md)。

## 测试

在 Python 3.11+ 的虚拟环境中，从仓库根目录运行。JavaScript 测试需要 Node.js。[GitHub Actions 工作流](.github/workflows/test.yml)

```bash
python -m pip install -r competitions/squares-in-squares/requirements.txt -r competitions/google-quantum-circuit-compilation/requirements.txt
python -m unittest discover -s competitions/squares-in-squares/experiments -v
python -m unittest discover -s competitions/google-quantum-circuit-compilation/experiments -v
python -m unittest discover -s competitions/santa-2026/tests -v
node --test competitions/squares-in-squares/experiments/test_core.cjs
node --test competitions/santa-2026/tests/test_replay.cjs
python -m unittest discover -s web/tests -p 'test_*.py' -v
```

原创代码采用 [MIT 许可](LICENSE)。装箱官方评分器保留 [Apache 2.0 许可和来源说明](competitions/squares-in-squares/vendor/NOTICE.md)。
