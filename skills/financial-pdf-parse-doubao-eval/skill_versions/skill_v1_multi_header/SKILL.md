---
name: financial-pdf-parse-doubao-eval
version: "0.3.0"
description: "Financial report PDF parsing skill based on Volcengine LAS Doubao PDF Parse. Parses scanned and digital financial PDFs into Markdown, normalized tables, financial metrics, quality checks, and evaluation reports. Optimized for balance sheets, income statements, cash flow statements, dense numeric tables, scanned documents, signatures, seals, and page footers."
---

# Financial PDF Parse Doubao Eval

## Skill 简介

`financial-pdf-parse-doubao-eval` 是一个金融财报 PDF 领域增强 Skill。它不重新训练 OCR 模型，而是在官方 `byted-las-pdf-parse-doubao` 的 LAS PDF 解析能力之上，增加金融表格标准化、关键财务指标抽取、质量校验、评测报告和错误兜底。

核心链路：

```text
PDF -> lasutil file-upload -> lasutil submit las_pdf_parse_doubao
-> lasutil poll -> raw outputs -> financial postprocess -> evaluation report
```

## 适用场景

- 金融财报 PDF、扫描件财报、多页财报。
- 资产负债表、利润表、现金流量表。
- 合并资产负债表、合并利润表、合并现金流量表。
- 密集金额表格、跨页表格、复杂版面。
- 印章、签名、页脚、`CONFIDENTIAL`、临时图片 URL 干扰。

## 不适用场景

- 非 PDF 文件，除非后续显式支持图片输入。
- 需要法律、审计、投资或合规结论的场景。
- 需要完全替代人工财务审阅的场景。

## 与官方 Skill 的关系

官方 `byted-las-pdf-parse-doubao` 是底层通用 PDF 解析能力，负责上传、提交、轮询并输出 `data.markdown` 和 `data.detail`。本 Skill 是财报领域封装，调用同一个 `las_pdf_parse_doubao` 算子，但额外生成 `normalized_tables.json`、`financial_summary.json`、`quality_checks.json` 和 `evaluation_report.md`。

直接 `lasutil` 调用必须标记为 `real_las`，不得称为 OpenClaw 调度。只有真实 OpenClaw 编排成功时才能标记为 `real_openclaw`。

## 与外层自动化测评框架的关系

本 Skill 是可独立交付、独立安装、独立运行的 OpenClaw Skill 包，不内置真实 PDF 数据集、人工 Ground Truth、Pytest 用例、YAML case 或 Allure 报告。

- 输入 PDF 必须由用户或外层测试框架通过 `--input` 显式传入。
- 输出目录由 `--output-dir` 指定；未指定时脚本默认写入当前工作目录下的 `outputs/financial_skill_demo`。
- `standard` profile 是后续自动化测评框架的默认消费协议。
- 外层测试框架可以把本 Skill 放在 `skills/financial-pdf-parse-doubao-eval/` 下，再通过 YAML case 指定 `input_pdf`、`ground_truth`、`output_dir`。
- 真实样例、人工 Ground Truth、Pytest 测试、Allure 报告不属于 Skill 包本体，属于外层评测项目。

## 工作流

### Step 0：前置检查

真实调用前必须检查：

- `LAS_API_KEY`
- `LAS_REGION`
- 输入 PDF 是否存在
- 输入是否为 PDF
- `parse_mode` 是否为 `normal` / `detail` / `auto`
- 是否需要用户确认价格
- 是否在 OpenClaw 环境中运行
- 当前环境是否支持后台长轮询

如果没有 `LAS_API_KEY`，提示用户配置：

Linux/macOS:

```bash
export LAS_API_KEY="..."
export LAS_REGION="cn-beijing"
```

Windows PowerShell:

```powershell
$env:LAS_API_KEY="..."
$env:LAS_REGION="cn-beijing"
```

### Step 1：环境初始化

Linux/macOS:

```bash
source skills/financial-pdf-parse-doubao-eval/scripts/env_init.sh
```

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\skills\financial-pdf-parse-doubao-eval\scripts\env_init_windows.ps1
```

初始化脚本检查 Python、pip、`las-sdk` / `lasutil`、`jq`，打印 `lasutil --version`，不写真实密钥，不修改用户永久环境变量。

### Step 2：文件上传 / URL 校验

本地 PDF 使用：

```bash
lasutil file-upload <local_pdf>
```

提交数据：

```json
{
  "url": "<presigned_url>",
  "parse_mode": "detail"
}
```

可选字段：

```json
{
  "start_page": 1,
  "num_pages": 10
}
```

### Step 3：解析模式选择

- `normal`：电子版、普通文本、低成本快速解析。
- `detail`：扫描件、复杂表格、多栏排版、财报正式评测。
- `auto`：根据 PDF 文本层、页数、关键词、用户输入自动选择。

`auto` 策略：

1. 扫描件或无文本层选择 `detail`。
2. 用户明确说“财报评测”“复杂表格”“跨页表格”“扫描件”选择 `detail`。
3. 只要求快速转 Markdown 选择 `normal`。
4. 无法判断时默认 `normal`，并提醒 `detail` 更适合复杂财报。

### Step 4：价格预估和用户确认

必须使用 [references/prices.md](references/prices.md)，读取 PDF 页数并输出页数、`parse_mode`、单页价格、预估总价和计费声明。真实 LAS 调用前必须确认价格。脚本自动模式支持 `--yes`，并在 `meta/run_meta.json` 中记录 `user_confirmed_cost=true`。

### Step 5：submit 任务

```bash
lasutil submit las_pdf_parse_doubao '<data_json>'
```

提交成功后保存：

- `raw/submit.json`
- `meta/run_meta.json.task_id`

`meta/task_id.txt` 已 deprecated，默认不生成。只有兼容旧 debug / poll 工作流时才使用 `--legacy-task-id-file` 显式生成。

### Step 6：短轮询

不能死循环。支持 timeout 和短轮询。若环境不支持长时间等待，返回 `task_id` 让用户稍后继续查询。

状态处理：

- `COMPLETED`：继续后处理。
- `RUNNING` / `PENDING`：返回 `task_id` 和下一步指令。
- `FAILED`：保存 `meta/error_result.json`。
- 业务码非 0：保存 `meta/error_result.json`。

### Step 7：保存原始输出

- `data.markdown` -> `raw/parsed.md`
- `data.detail` -> `raw/pages_detail.json`

### Step 8：金融后处理

生成：

- `normalized/cleaned.md`
- `normalized/normalized_tables.json`
- `normalized/financial_summary.json`
- `evaluation/quality_checks.json`
- `meta/run_meta.json`

### Step 9：质量校验

支持表格数量、关键财务表识别、资产负债表勾稽、括号负数、小数点保留、期间列识别、噪声识别、`pages_detail.json` schema、`parsed.md` 非空、`result.json` business code。

### Step 10：结果呈现

生成 `evaluation/evaluation_report.md`，展示任务信息、输出文件、解析摘要、文本预览和注意事项。报告必须区分 `real_openclaw`、`real_las`、`official_output_mock`、`fallback_synthetic_mock`。

## 输出文件协议

### Output Profile

`run_financial_parse.py` supports `--output-profile minimal|standard|debug`. Default is `standard`.

- `minimal`: root-level `parsed.md`, `financial_summary.json`, `evaluation_report.md`, `run_meta.json`; suitable for final display.
- `standard`: `raw/parsed.md`, `normalized/normalized_tables.json`, `normalized/financial_summary.json`, `evaluation/quality_checks.json`, `evaluation/evaluation_report.md`, `meta/run_meta.json`; this is the stable default for future automation tests.
- `debug`: keeps raw LAS `result.json`, `pages_detail.json`, `submit.json`, `cleaned.md`, and logs for troubleshooting.

`result.json`, `pages_detail.json`, `cleaned.md`, and `task_id.txt` are not default required files. `task_id` is written to `run_meta.json`. `meta/task_id.txt` is deprecated and is only generated when `--legacy-task-id-file` is explicitly used for old debug workflows. Use `--keep-pages-detail` if the standard profile must retain `raw/pages_detail.json`.

Output completeness checks are not accuracy checks. “输出完整性检查 100% 通过” only means required files, JSON validity, Markdown non-empty, schema completeness, and authenticity markers passed. It does not mean parsing accuracy is 100%. True parsing accuracy must be measured by human Ground Truth with `evaluation/gt_eval_result.json`.

```text
output/<case_id_or_task_id>/
  raw/
    submit.json
    result.json
    parsed.md
    pages_detail.json
  normalized/
    cleaned.md
    normalized_tables.json
    financial_summary.json
  evaluation/
    quality_checks.json
    evaluation_report.md
  meta/
    run_meta.json
    task_id.txt  # deprecated, only with --legacy-task-id-file
    error_result.json
```

完整 schema 见 [references/output_schema.md](references/output_schema.md)。

外层自动化测评框架只应依赖 `standard` profile 的稳定路径。`debug` profile 仅用于排错，`minimal` profile 仅用于展示；真实样例、官方离线 output、人工 Ground Truth 和报告聚合由外层项目传入或生成。

## 错误码

| 错误码 | 触发条件 | 用户可见提示 | 建议修复方式 | 可重试 |
|---|---|---|---|---|
| `FILE_NOT_FOUND` | 输入不存在 | 未找到输入 PDF | 检查路径 | 是 |
| `INVALID_FILE_TYPE` | 非 PDF | 当前仅支持 PDF | 使用 PDF | 否 |
| `AUTH_MISSING` | 缺少 `LAS_API_KEY` | LAS API Key 未配置 | 设置环境变量 | 是 |
| `AUTH_INVALID` | Key 无效 | 鉴权失败 | 检查 Key | 是 |
| `REGION_MISMATCH` | 区域不匹配 | Region 不匹配 | 设置正确 `LAS_REGION` | 是 |
| `URL_NOT_ACCESSIBLE` | URL 过期或不可访问 | LAS 无法读取 PDF | 重新上传 | 是 |
| `TASK_ID_MISSING` | submit 无 task_id | 提交结果不完整 | 查看 `raw/submit.json` | 是 |
| `TASK_TIMEOUT` | 短轮询超时 | 任务未完成 | 稍后 poll | 是 |
| `SERVER_BUSY` | 限流或服务忙 | 服务繁忙 | 降低并发重试 | 是 |
| `TASK_FAILED` | 任务失败 | LAS 任务失败 | 查看 error_result | 视原因 |
| `OUTPUT_SCHEMA_INVALID` | 输出结构异常 | schema 无效 | 检查 raw 输出 | 是 |
| `OUTPUT_INCOMPLETE` | 缺少文件 | 输出不完整 | 重新 poll/postprocess | 是 |
| `NO_MARKDOWN_OUTPUT` | markdown 为空 | 无 Markdown 输出 | 改用 detail | 是 |
| `NO_TABLE_DETECTED` | 无表格 | 未检测到表格 | 改用 detail 或人工确认 | 是 |
| `POSTPROCESS_FAILED` | 后处理异常 | 后处理失败 | 查看 error_result | 是 |
| `PRICE_CONFIRMATION_REQUIRED` | 未确认价格 | 需要确认预估计费 | 交互确认或 `--yes` | 是 |
| `OPENCLAW_NOT_CONFIGURED` | OpenClaw 缺配置 | OpenClaw 未配置 | 设置端点和凭证 | 是 |
| `REAL_MODE_NOT_IMPLEMENTED` | 后端未实现 | 真实后端未实现 | 使用 `real_las` | 否 |

## 计费声明

本 Skill 只展示预估计费，最终费用以火山引擎账单为准。

## 安全要求

- 不硬编码 API Key。
- 不写入真实 `env.sh` 密钥。
- `real_las` 失败要保存 stdout/stderr/error_result。
- `fallback_synthetic_mock` 必须 `is_synthetic=true` 且 `count_as_real_evaluation=false`。
- `official_output_mock` 是离线复用官方输出，不是新真实调用。

## 验收命令

以下示例都从 Skill 包根目录执行，不要求 Skill 内置任何 PDF 样例。

Windows PowerShell:

```powershell
python .\scripts\estimate_price.py --input "<PDF_PATH>" --parse-mode detail
```

```powershell
python .\scripts\run_financial_parse.py `
  --input "<PDF_PATH>" `
  --parse-mode detail `
  --output-dir "<OUTPUT_DIR>" `
  --output-profile standard `
  --yes
```

```powershell
python .\scripts\validate_outputs.py --output-dir "<OUTPUT_DIR>" --output-profile standard
```

Linux/macOS:

```bash
python scripts/run_financial_parse.py \
  --input "<PDF_PATH>" \
  --parse-mode detail \
  --output-dir "<OUTPUT_DIR>" \
  --output-profile standard \
  --yes
```
