# financial-pdf-parse-doubao-eval Skill 自检清单

本清单用于 Skill 包自身交付前自检，不是整个课题项目验收清单。

| 自检项 | 状态 | 说明 |
|---|---|---|
| Skill 可独立安装 | 已具备 | 包内包含 `SKILL.md`、`_meta.json`、`scripts/`、`references/`、`evals/`、`examples/`。 |
| Skill 可独立运行 | 已具备 | 用户通过 `--input` 传入 PDF，通过 `--output-dir` 指定输出目录；未指定输出目录时默认写入当前工作目录 `outputs/financial_skill_demo`。 |
| 不内置真实样例 | 已确认 | 真实 PDF 样例由用户或外层自动化测评框架提供。 |
| 不内置人工 Ground Truth | 已确认 | Ground Truth 由外层自动化测评框架提供，并通过 `evaluate_with_ground_truth.py` 消费。 |
| standard profile 自动化接口 | 已具备 | 外层测试框架默认消费 `raw/`、`normalized/`、`evaluation/`、`meta/` 下的稳定路径。 |
| real_las backend | 已支持 | 支持直接调用 LAS / `lasutil`，并在 `run_meta.json` 中标记 `execution_backend=real_las`。 |
| real_openclaw backend | 尚未验证 | 当前仅保留元数据和错误兜底，真实 OpenClaw 编排仍需外层环境验证。 |
| examples 结构示例 | 已保留 | `examples/*.json` 仅作为结构示例，不依赖真实 PDF。 |
| Pytest/YAML/Allure | 不属于包本体 | 后续课题验收需要外层 Pytest/YAML/Allure 自动化测评框架补充。 |
| 20-30 样本集 | 不属于包本体 | 样本集扩展属于后续外层评测项目。 |
