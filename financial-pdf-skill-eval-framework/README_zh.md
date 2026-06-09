<div style="font-size: 20px">
# financial-pdf-skill-eval-framework

用于 OpenClaw Skill **financial-pdf-parse-doubao-eval** 的外层自动化评测框架。

Skill 是**被测系统**，不是本框架的一部分。本框架负责管理测试样本、YAML 用例、Ground Truth、pytest 分层测试、可选的 Allure 附件，以及聚合后的 Markdown 报告。

## 为什么该框架要与 Skill 分离？

Skill 作为一个自包含的 OpenClaw 插件发布，必须保持独立，不能绑定任何特定测试项目。真实 PDF、人工 Ground Truth、pytest 用例和 Allure 报告都属于评测项目资产，因此放在本框架中维护。

## Skill 契约

本框架通过 **standard** 输出 profile 消费 Skill 结果。`standard` 是唯一稳定的自动化接口。`debug` 仅用于排错，`minimal` 仅用于展示。

每个用例的必需文件位于 `outputs/<case_id>/` 下：

- `raw/parsed.md`
- `normalized/normalized_tables.json`
- `normalized/financial_summary.json`
- `evaluation/quality_checks.json`
- `meta/run_meta.json`

standard profile 还会生成 `evaluation/evaluation_report.md`。当存在人工 Ground Truth 时，会生成 `evaluation/gt_eval_result.json`。

## `data/real_las_outputs/` 是什么，以及不是什么

- 它保存的是从 OpenClaw + LAS 返回的 **real_las** Skill 输出。
- 这些输出可以作为 fixture，用于输出契约、结构统计和数据真实性测试。
- 它们**不是** Ground Truth。`financial_summary.json` 是 Skill 的抽取结果，不能作为标准答案。
- 只有当 `evaluation/ground_truth/` 下存在真实人工 Ground Truth 文件，并且其中包含非空 `expected` 值时，才能计算准确率。

## 快速开始（Windows PowerShell）

```powershell
cd financial-pdf-skill-eval-framework

python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

# 导入框架旁边已经存在的 OpenClaw + real_las 输出
python run.py --import-real-outputs ..\outputs

# 运行全部离线测试，不会真实调用 LAS，也不会产生费用
pytest -q
pytest -m smoke
pytest -m offline
pytest -m abnormal

# 生成 Markdown 报告
python run.py --summary
python run.py --fixture-summary
python run.py --collect-openclaw-evidence
python run.py --generate-final-report
```

Linux / macOS / Git Bash：

```bash
cd financial-pdf-skill-eval-framework
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py --import-real-outputs ../outputs
pytest -q
```

## `real_las`：默认禁用

调用 LAS 会产生费用。除非同时满足以下两个条件，否则框架会拒绝调用 LAS：

- 已设置 `LAS_API_KEY`
- `ALLOW_REAL_LAS=1`

如果不满足这些条件，`real_las` 用例会被**跳过**，而不是失败。

```powershell
$env:LAS_API_KEY="..."
$env:LAS_REGION="cn-beijing"
$env:ALLOW_REAL_LAS="1"
pytest -m real_las
```

## `real_openclaw`：尚未验证

Skill 声明了 `real_openclaw` backend，但本次提交尚未完成端到端验证。针对 `real_openclaw` 的用例默认跳过，直到完成验证为止。OpenClaw 证据日志 `reports/markdown/openclaw_invocation_log.md` 会明确说明这一点。

## 学术论文样本（域外泛化）

| 用例 ID | 论文 | 页数 | fixture |
|---------|------|------|---------|
| `paper_rubric_learnable_assessment` | Learnable Assessment Skills (Rubric) | 12 | `data/real_las_outputs/paper_rubric_learnable_assessment` |
| `paper_skill_evolver` | SkillEvolver (Meta-Skill) | 20 | `data/real_las_outputs/paper_skill_evolver` |

GT 均为 `source=todo_manual_verify`，默认不参与 `financial_accuracy`；断言以契约 + 表统计 + `text_contains` 为主。

```powershell
python run.py --pipeline --cases testcases/pdf_cases/paper_rubric_learnable_assessment.yaml --backend fixture
python run.py --pipeline --cases testcases/pdf_cases/paper_skill_evolver.yaml --backend fixture
```

重新拉 LAS 结果（仅当 fixture 缺失或需重跑时）：

```powershell
$env:ALLOW_REAL_LAS = "1"
$env:PYTHONIOENCODING = "utf-8"
python run.py --case testcases/pdf_cases/paper_skill_evolver.yaml  # yaml 中 backend 改为 real_las
# 若返回 pending，用 poll_task.py --max-seconds 420 轮询 task_id，再 postprocess
```

## 添加新样本

1. 将 PDF 放到 `data/samples/`。
2. 在 `testcases/pdf_cases/` 下新增 YAML 用例。
3. 在 `evaluation/ground_truth/<case>_manual_gt.json` 下创建 Ground Truth 模板。
4. 手工填写 `expected` 值，**不要**从 `financial_summary.json` 复制。

## 添加 Ground Truth

`evaluation/ground_truth/<case>_manual_gt.json`：

```json
{
  "case_id": "case",
  "source": "manual",
  "metrics": [
    {"statement": "合并资产负债表", "item": "资产总计", "period": "2025-12-31", "expected": "100,000,000.00", "page": 1, "evidence": "manual"}
  ]
}
```

- `expected` 为空的行不会计入准确率分母，并会计入 `pending_manual_verify_count`。
- 只要至少填写了一个 `expected`，即可生成准确率报告。

## 报告

- `reports/markdown/evaluation_summary.md`：主运行摘要，包含 4 个部分。
- `reports/markdown/failure_cases.md`：列出至少有一项校验失败的所有用例。
- `reports/markdown/fixture_summary.md`：导入 fixture 的快速统计。
- `reports/markdown/openclaw_invocation_log.md`：OpenClaw 证据与免责声明。
- `reports/final/final_project_report.md`：用于项目提交的综合报告。
- `reports/allure-results/`、`reports/allure-html/`：可选 Allure 输出，仅在已安装 `allure-pytest` 且 `allure` CLI 位于 PATH 中时可用。

## 展示 UI（Streamlit Dashboard，只读）

本项目提供一个只读评测展示 Dashboard，参考 Auto_prd_test_agent 的三层 Streamlit 结构
（`main` / `sidebar` / `components`），但不包含聊天生成、RAG 入库、API Key 配置等业务逻辑。

```powershell
pip install -r requirements-dashboard.txt
python run.py --build-dashboard-bundle
streamlit run dashboard/streamlit_app.py
# 浏览器打开 http://localhost:8501
```

也可以用一条命令生成 bundle 并启动（未安装 Streamlit 时会提示安装命令）：

```powershell
python run.py --serve-dashboard
```

说明：

- UI **只读**已有产物（`reports/dashboard/dashboard_bundle.json` 及其引用的 JSON / Markdown），
  不触发任何评估、推理、pipeline、Skill 调用或 patch gate，也不会调用真实 LAS / OpenClaw。
- `python run.py --build-dashboard-bundle` 仅扫描并读取本地文件，写入
  `reports/dashboard/dashboard_bundle.json`，并打印生成路径与 case 数量。
- 如果页面提示缺数据，请先运行 pipeline：
  `python run.py --pipeline --cases testcases/pdf_cases/byd_real_las_fixture.yaml --backend fixture`。
- 侧边栏「刷新 bundle」按钮只重新扫描本地文件，不会运行真实 LAS / OpenClaw。
- 页面分为：总览 / Judge 诊断 / 叙事对比 / Failure Trace & SkillOpt / 解析产物 / Rubric。
- 所有分数（`weighted_score`、`level`、Judge 三维分、trace 内容）均从真实 JSON 动态读取，
  不硬编码；LLM Judge 分数仅作结构质量诊断，**不**参与 `weighted_score` 重算。
- Streamlit 依赖单独维护在 `requirements-dashboard.txt`，未写入主 `requirements.txt`。

## 待完成事项

- `real_openclaw` backend：尚未验证。
- 人工 Ground Truth：目前只有模板，真实值需要人工填写。
- 样本集应扩展到 20–30 个具有代表性的用例，覆盖正常、复杂、对抗和异常场景。
- 没有 Ground Truth 的用例只能评测输出契约、结构统计和数据真实性，不能评测准确率。
