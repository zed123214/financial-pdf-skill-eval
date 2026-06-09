# Output Schema

This skill supports three output profiles: `minimal`, `standard`, and `debug`.

本 Skill 不内置真实 PDF 数据集、人工 Ground Truth、Pytest 用例、YAML case 或 Allure 报告。输入 PDF 由用户或外层测试框架通过 `--input` 传入，外层测试框架可把 Skill 放在 `skills/financial-pdf-parse-doubao-eval/` 下，并用 YAML case 指定 `input_pdf`、`ground_truth`、`output_dir`。真实样例、人工 Ground Truth、Pytest 测试和 Allure 报告属于外层评测项目，不属于 Skill 包本体。

## Profile Summary

| Profile | Purpose | Default |
|---|---|---:|
| `minimal` | Final display or compact attachment for mentors. | No |
| `standard` | Stable contract for the next automation test framework. | Yes |
| `debug` | Troubleshooting, audit, and raw LAS inspection. | No |

`result.json`, `pages_detail.json`, `cleaned.md`, and `task_id.txt` are not default required submission files. `task_id` is stored in `run_meta.json`. `meta/task_id.txt` is deprecated and is only generated when `--legacy-task-id-file` is explicitly used for old debug workflows.

## minimal

Root-level files only:

```text
outputs/<case_id>/
  parsed.md
  financial_summary.json
  evaluation_report.md
  run_meta.json
```

## standard

Default automation contract:

```text
outputs/<case_id>/
  raw/
    parsed.md
  normalized/
    normalized_tables.json
    financial_summary.json
  evaluation/
    quality_checks.json
    evaluation_report.md
  meta/
    run_meta.json
```

If `--keep-pages-detail` is used, standard may additionally include:

```text
raw/pages_detail.json
```

## debug

Full diagnostic output:

```text
outputs/<case_id>/
  raw/
    submit.json
    result.json
    parsed.md
    pages_detail.json
    raw_stdout.log
    raw_stderr.log
  normalized/
    cleaned.md
    normalized_tables.json
    financial_summary.json
  evaluation/
    quality_checks.json
    evaluation_report.md
    gt_eval_result.json
  meta/
    run_meta.json
    error_result.json
```

`meta/task_id.txt` may appear in debug mode only when `--legacy-task-id-file` is explicitly used for backward compatibility. It is deprecated. Use `meta/run_meta.json.task_id`.

## run_meta.json

```json
{
  "skill_name": "financial-pdf-parse-doubao-eval",
  "skill_version": "0.3.0",
  "base_skill": "byted-las-pdf-parse-doubao",
  "operator_id": "las_pdf_parse_doubao",
  "execution_backend": "real_las",
  "parse_mode": "detail",
  "task_id": "...",
  "input_file": "...",
  "page_count": 6,
  "estimated_price": 0.24,
  "output_profile": "standard",
  "output_source": "real_las",
  "is_synthetic": false,
  "count_as_real_evaluation": true,
  "raw_table_count": 90,
  "financial_table_count": 72,
  "metric_record_count": 191,
  "status": "success"
}
```

Allowed `execution_backend`:

- `real_las`
- `real_openclaw`
- `official_output_mock`
- `fallback_synthetic_mock`

Allowed `output_source`:

- `real_las`
- `real_openclaw`
- `external_official_output`
- `test1_output`
- `fallback_synthetic_mock`

`external_official_output` 表示外部测试框架通过 `--mock-dir` 提供的离线官方 output。`test1_output` 只是兼容旧外部测试框架的离线官方 output 来源标记，不表示 Skill 包内置 `test1` 项目数据，也不表示 Skill 自带真实样例。

Rules:

- If `is_synthetic=true`, then `count_as_real_evaluation=false`.
- `fallback_synthetic_mock` must not enter real accuracy summaries.
- `real_las` means direct LAS / lasutil invocation and is not `real_openclaw`.

## normalized_tables.json

```json
{
  "tables": [
    {
      "table_id": "table_001",
      "page": 1,
      "statement": "合并资产负债表",
      "table_type": "financial_table",
      "columns": ["项目", "3/31/2026", "12/31/2025"],
      "rows": [
        {
          "项目": "资产总计",
          "3/31/2026": "20,262,595,475.25",
          "12/31/2025": "18,902,992,212.04"
        }
      ]
    }
  ]
}
```

`table_type` is heuristic and can be:

- `financial_table`
- `layout_table`
- `signature_table`
- `unknown_table`

## financial_summary.json

```json
{
  "company": "示例融资租赁有限公司",
  "document_type": "financial_report",
  "period": "2026Q1",
  "metric_statistics": {
    "metric_record_count": 191,
    "unique_item_count": 45,
    "unique_statement_count": 6
  },
  "metrics": [
    {
      "statement": "合并资产负债表",
      "item": "资产总计",
      "period": "3/31/2026",
      "value": "20,262,595,475.25",
      "normalized_value": "20262595475.25"
    }
  ]
}
```

## quality_checks.json

```json
{
  "data_authenticity": {
    "execution_backend": "real_las",
    "output_source": "real_las",
    "is_synthetic": false,
    "count_as_real_evaluation": true
  },
  "table_statistics": {
    "raw_table_count": 90,
    "financial_table_count": 72,
    "layout_table_count": 8,
    "signature_table_count": 4,
    "unknown_table_count": 6
  },
  "metric_statistics": {
    "metric_record_count": 191,
    "unique_item_count": 45,
    "unique_statement_count": 6
  },
  "checks": [],
  "scores": {}
}
```

Output completeness checks are not parsing accuracy checks. Table and metric counts represent extraction scale, not correctness.

## Ground Truth Accuracy

True parsing accuracy must be computed from human Ground Truth:

```text
evaluation/gt_eval_result.json
```

Use `scripts/evaluate_with_ground_truth.py` to produce:

- `exact_match_accuracy`
- `numeric_accuracy`
- `failed_items`

Cases without human Ground Truth are only link validation or structure extraction validation cases.

## Automation Interface Contract

The future automation framework consumes `standard` profile by default. `standard` is the only stable automation interface. `debug` is only for troubleshooting, and `minimal` is only for display.

Input directory:

```text
outputs/<case_id>/
```

Required files (必读文件):

- `raw/parsed.md`
- `normalized/normalized_tables.json`
- `normalized/financial_summary.json`
- `evaluation/quality_checks.json`
- `meta/run_meta.json`

Optional files (可选文件):

- `evaluation/gt_eval_result.json`
- `evaluation/evaluation_report.md`
- `raw/pages_detail.json`

Path requirements:

- Required and optional paths must stay stable across releases.
- Automation test frameworks must depend only on `standard` profile.
- `debug` profile may include extra raw files and logs, but automation must not require them.
- `minimal` profile may flatten files for presentation, but automation must not consume it as the default contract.

The automation framework will use these paths for:

1. Output completeness checks.
2. Table count statistics.
3. Financial metric count statistics.
4. Ground Truth expected vs actual evaluation.
5. Data authenticity checks.
6. Backend checks.
7. Abnormal case checks.
8. Allure attachment upload.

要求保持这些路径稳定。
