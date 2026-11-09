# Contribute to kaggle-lab / 本地开发与更新

This repository has been created at <https://github.com/Leonardo-F/kaggle-lab>.

## Clone / 克隆

```bash
git clone https://github.com/Leonardo-F/kaggle-lab.git
cd kaggle-lab
```

## Test / 测试

```bash
python -m unittest discover -s competitions/squares-in-squares/experiments -v
python -m unittest discover -s competitions/google-quantum-circuit-compilation/experiments -v
node --check competitions/squares-in-squares/simulator/app.js
```

## Commit changes / 提交修改

```bash
git add .
git commit -m "Improve Kaggle solution"
git push origin main
```

## Optional GitHub Pages / 网页部署

The packing simulator is in `competitions/squares-in-squares/simulator/` and can be deployed as a static site using GitHub Pages Actions. Pages deployment is **not** enabled automatically by this repository. The portable standalone file `SquarePackingStudio-standalone.html` can be opened locally without a build step.

## Privacy and provenance / 注意事项

Competition outputs, credentials, large datasets, and experimental logs should stay local (`.gitignore`). This repository is currently public. Before publishing optimized competition solutions, review Kaggle rules on shared code and prize eligibility; cite any third-party components, and respect their licenses.
