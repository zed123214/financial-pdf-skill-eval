# Baseline v0 — Evaluation Summary (frozen)

_skill_version: skill_v0_baseline_
_created: 2026-05-30T18:50:00+08:00_
_backend: fixture (offline)_

> 本报告冻结 Assessment-Skill Judge / failure_trace 接入**之前**的确定性评分基线。
> 仅供后续差异对比，不参与任何提分逻辑。Judge 尚未启用。

## 验证命令

```powershell
python run.py --cases testcases/pdf_cases/byd_real_las_fixture.yaml --backend fixture --pipeline
pytest tests/test_09_pipeline_fixture.py tests/test_10_scoring_model.py -q -m offline
```

- pipeline: `status=success`, `weighted_score=8.8`, `level=good`
- pytest: `16 passed`

## Cases × Dimensions

| case_id | output_contract | data_authenticity | table_structure | financial_accuracy | abnormal_handling | cost_performance | weighted_score | level | gt_status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| byd_real_las_fixture | 10 | 10 | 8 | null | 8 | 10 | 8.8 | good | skipped |

## 说明

- `financial_accuracy = null`：fixture 对应的 ground truth 为 todo/manual_verify，`evaluate_ground_truth` stage 判定 `no_ground_truth`，按 profile 重分配该维度的 35% 权重（`financial_accuracy unavailable, redistributed`）。
- 该基线**零业务逻辑改动**，仅新增 baseline 目录与 `skill_versions/skill_v0_baseline/` 快照。
