# Santa 2026 算法图表

[算法演进](../algorithm-evolution.md) 使用本目录的 PNG 显示图表，因此不依赖 Markdown 预览器的 Mermaid 支持。

- `*.mmd`：Mermaid 源文件，保留图形结构，便于以后修改。
- `*.png`：对应源文件的渲染结果，白底，供文档直接引用。

修改 `.mmd` 后重新渲染同名 PNG。流程图通过 `mermaid.ink/img/<base64>?type=png&bgColor=white` 生成；`version-scores` 使用同目录 `xychart-beta` 源。不要直接把 Mermaid 代码贴回 Markdown，否则不支持的预览器会把它显示成代码块。

`v11-architecture.mmd` 记录当前 V11 求解器的结构；同名 PNG 按原图风格手工绘制（Pillow），以便控制 1440×1040 的两阶段布局与中文排版。修改结构时同时更新 `.mmd` 与 PNG。`version-scores.png` 覆盖 V1–V11，其中 V11 是报告支持、未附 CSV 的研究记录。
