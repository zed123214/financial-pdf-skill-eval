# Failure Cases (manual journal)

This file holds **narrative** notes about interesting failures, not the
auto-generated list at `reports/markdown/failure_cases.md`.

## 华电光大 — non-standard 业绩报表

- Skill behavior: `raw_table_count=1, financial_table_count=0, metric_record_count=0`.
- Diagnosis: this PDF is a press-release-style 业绩 summary, not a structured
  financial statement. The Skill correctly classifies the only table as
  `unknown_table`.
- Decision: keep this fixture for **structure / authenticity** tests; exclude
  from accuracy. `count_as_real_evaluation=false` in the YAML.

## (template) Missing Ground Truth

- Symptom: `numeric_accuracy=null`, `no_ground_truth=true`.
- Resolution: write a manual GT file. Until then, accuracy assertions in the
  case must use `skip_if_no_ground_truth: true`.
