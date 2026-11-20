# Kaggle Lab

独立实现的 Kaggle 竞赛解法、实验与复现工具。各赛题独立管理代码和依赖。当前结果和验证范围见 [PROGRESS.md](PROGRESS.md)。

| 赛题 | 项目入口 | 官方页面 |
| --- | --- | --- |
| Squares in Squares · 正方形装箱 | [离线模拟器、最佳 CSV 与认证命令](competitions/squares-in-squares/README.md) | [Kaggle](https://www.kaggle.com/competitions/squares-in-squares) |
| Google 量子电路编译 | [三个子题、提交格式与验证命令](competitions/google-quantum-circuit-compilation/README.md) | [Kaggle](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation) |

## 目录

- `docs/` 收录各赛题的实验进展、版本结果和策略笔记。
- `competitions/<赛题>/algorithms/` 存放求解器和验证入口。`experiments/` 存放实验脚本、结果和测试。
- 装箱另含 `simulator/`、固定版本的官方评分器 `vendor/`，以及 `submissions/` 中的最佳 CSV 和逐题认证。量子电路和提交包在本地生成。

## 测试

在 Python 3.11+ 的虚拟环境中，从仓库根目录运行。JavaScript 测试需要 Node.js。[GitHub Actions 工作流](.github/workflows/test.yml)

```bash
python -m pip install -r competitions/squares-in-squares/requirements.txt -r competitions/google-quantum-circuit-compilation/requirements.txt
python -m unittest discover -s competitions/squares-in-squares/experiments -v
python -m unittest discover -s competitions/google-quantum-circuit-compilation/experiments -v
node --test competitions/squares-in-squares/experiments/test_core.cjs
```

原创代码采用 [MIT 许可](LICENSE)。装箱官方评分器保留 [Apache 2.0 许可和来源说明](competitions/squares-in-squares/vendor/NOTICE.md)。
