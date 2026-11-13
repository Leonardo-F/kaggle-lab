# 从思路到实现：2026-11-12 进度

本页记录沿两篇解题笔记实际完成的工作。[机器可读结果摘要](2026-11-12-results.json) 包含最终 CSV、官方验证器和数值代码的 SHA-256。完整逐题日志和大 CSV 可用下列命令重建，不放入 git。

## 正方形装箱

| 产物 | 本次证据 |
| --- | --- |
| 官方检查接入 | 固定 Kaggle metric v20，原代码不修改；保留 Apache 2.0 许可和 NOTICE |
| 网格完整 CSV | 500,500 行，1000/1000 实例通过原始十进制与 pandas 数值传输两条检查 |
| 旋转构造与删块迁移 | 独立实现旋转核心、四角方阵/阶梯；逐题与网格取优 |
| 构造完整 CSV | 两条检查均 1000/1000 通过，162 个实例改善 |
| 本地官方总分 | 网格 28.937669916550586 → 构造组合 **26.99315523902542**，减少约 1.9445146775 |
| 离线 HTML | 默认仍为 n=1000 网格；新增当前实例和全部实例的可选构造按钮；完整导出继续覆盖所有 n |

离线 HTML 的功能只经过无头 DOM 冒烟测试（完整 CSV 下载、导入/导出、忙碌锁、旋转、非法导出、小数点保留）；真实浏览器的视觉检查与 `file://` 本地下载未复验。

这是固定版本官方 metric 的**本地验证结果**，没有向 Kaggle 上传参赛作品，也没有得到平台榜单成绩。

几何构造分为两族：

1. 四角各 `k×k` 个方块，中间一个 45° 方块：容量 `4k²+1`，理想边长 `2k+1/√2`。
2. 中心旋转 `b×b` 核心，四角各 `m(m-1)/2` 个阶梯方块：容量 `b²+2m(m-1)`，理想边长 `m+b/√2`。条件 `2(m-2)²≤b²≤2m²` 保证阶梯和核心在相应区域内。

第二族左下角阶梯的每个方块顶点满足 `x+y≤m`，恰在中心菱形外；另三角由反射得到。删除任意方块保持几何有效，按离中心距离排序得到不同规模的前缀，再逐题比较。中心坐标稍作外扩以留出十进制传输余量，**最终有效性仍由实际导出文件的官方检查决定**。

实现没有下载他人的坐标库。数学构造受经典旋转核心思想启发，来源见原解题笔记；不把这些构造称为新纪录或全局最优解。

在仓库根目录复现：

```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
python -m pip install -r competitions/squares-in-squares/requirements.txt
python competitions/squares-in-squares/algorithms/constructions.py --output competitions/squares-in-squares/submissions/constructed.csv --manifest competitions/squares-in-squares/experiments/results/constructions.json
python competitions/squares-in-squares/algorithms/certify.py --input competitions/squares-in-squares/submissions/constructed.csv --complete --workers 4 --report competitions/squares-in-squares/experiments/results/certification.json
```

Windows 可用 `.venv\Scripts\python.exe` 代替 `python`。HTML 直接打开即可使用，不需要这些 Python 依赖。大文件认证耗时数分钟；退出码 0 且 `valid=true` 才表示两条本地检查均通过，单看总分不能判断有效。

对应路线：P0、P1、P2 已完成；P3 的删块迁移已实现，局部压缩/搜索预算比较仍待继续。接触图精修、结构拼接和 GPU 搜索仍是后续工作。

## 量子电路编译

首先补上此前未保存代码的数值实验。新模型明确采用：`[1,4)` 等距分段、两端点割线作为线性初值、一次 Newton 迭代、每个乘法 nearest-even 舍入、单独保留尺度指数。它不沿用旧笔记中来源代码缺失的数值表。

每组均遍历 **3,133,452** 个输入；通过精确整数不等式比较相对误差与 `2^-24`，不是靠浮点容差判断通过。下列最大误差为辅助显示的浮点估计：

| 分段 | 小数位 | 精确判定的失败数 | 最大相对误差约值 |
| ---: | ---: | ---: | ---: |
| 32 | 26 | 899508 | 8.6391e-7 |
| 32 | 28 | 895142 | 8.5401e-7 |
| 32 | 30 | 895592 | 8.5150e-7 |
| 64 | 26 | 4456 | 7.1758e-8 |
| 64 | 28 | 637 | 6.1597e-8 |
| 64 | 30 | 0 | 5.8873e-8 |
| 128 | 26 | 0 | 3.2805e-8 |
| 128 | 28 | 0 | 8.0175e-9 |
| 128 | 30 | 0 | 4.6774e-9 |

“64 段、30 位”虽然数值通过，但误差余量很窄；“128 段、26/28 位”值得做电路成本对照。表更大可能抬高 QROM 和清理代价，不能仅凭这张数值表选最终方案。

精确检查来自 `a=y/2^e` 的等价不等式：

$$
(2^{24}-1)^2\,2^{2e}\le y^2x\,2^{48}\le(2^{24}+1)^2\,2^{2e}.
$$

代码使用 Python 大整数完成该检查；NumPy 向量化中间乘法在限定的 20–30 位范围内不超出 int64。该结果只涉及定义清楚的整数数值模型，尚不含量子寄存器、反计算、测量分支或旋转合成，因此 `official_circuit_verified=false`。

复现命令与官方验证入口见 [量子项目 README](../../competitions/google-quantum-circuit-compilation/README.md)。依赖与装箱独立，建议单独建立虚拟环境。

### 当前接入限制

2026-11-12 访问官方数据下载 API 返回 401。云端 Kaggle 页面显示未登录，并要求登录后接受赛规才能下载 `verifiers/` 和 `sample_submission/`。GitHub 的登录状态不代表 Kaggle 已登录。

因此，Q0 的三项官方 baseline 尚未复现，Q1 资源剖析和 Q3 可逆候选仍待官方数据接入。已提供调用原始任务验证器的入口及缺失数据/重复格式/角度缺号的失败测试；入口与三项真实数据的集成验证仍待完成。Q2 的数值模型是可独立推进的部分，现已完成本页所列候选扫描。

接下来需要先在 Kaggle 登录并确认赛规，再下载官方数据；这涉及账户认证与赛规确认，不能由现有 GitHub 授权代替。数据无需公开到仓库。
