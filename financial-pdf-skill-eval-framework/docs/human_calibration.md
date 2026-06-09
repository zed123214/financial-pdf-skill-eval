# 人工校准说明

生成日期：2026-06-04

## 目的

自动化产物 `score_result.json`、`judge_result.json`、`gt_eval_result.json` 只能说明输出契约、结构统计、评分模型和可选 Judge 诊断信号，不能替代人工对 PDF 原文和 Ground Truth 的核对。本项目结项口径采用“自动化报告 + 人工校准叙述”。

## 校准范围

本轮深度校准控制在 5 条代表样本：

- byd_real_las_fixture_gt_test -> evaluation/ground_truth/byd_real_las_fixture_gt.json
- input_007_income_statement -> evaluation/ground_truth/input_007_income_statement_manual_gt.json
- input_018_meeting_minutes_no_table -> evaluation/ground_truth/input_018_meeting_minutes_no_table_manual_gt.json
- huadian_real_las_fixture -> evaluation/ground_truth/huadian_manual_gt.json
- 先锋财报_扫码件-6-9 -> evaluation/ground_truth/先锋财报_扫码件-6-9_manual_gt.json

仍处于 `todo_manual_verify` 的 GT 包括：input_008 至 input_017 中未列入深校的合成样本、input_001 至 input_006、input_019 至 input_030，以及 BYD 分段设计样本。`input_024`、`input_026`、`input_027` 已写入少量 PDF 文本抽样 metrics，但因无 fixture 且未人工终审，仍不进入准确率分母。

## 可复现步骤

1. 打开原始 PDF，同时查看对应输出目录中的 `raw/parsed.md` 与 `normalized/normalized_tables.json`。
2. 逐条核对 GT 的 `metrics[].expected` 是否来自 PDF 单元格、生成脚本或人工转录记录；禁止从 `normalized/financial_summary.json` 复制数值。
3. 核对 `evaluation/quality_checks.json` 中的 `financial_table_count`、`unknown_table_count`、`metric_record_count` 是否与肉眼观察一致。
4. 若启用 Judge，只把 mock/live 的扣分项作为结构诊断，不重算 deterministic weighted_score，也不覆盖 `financial_accuracy`。
5. 对异常 PDF，只有已经存在 `meta/error_result.json` 的 case 才能登记 `error_type_eq`；没有实测错误码时只保留设计异常说明。

## 抽样策略

- 深校：从 fixture-backed 样本中选 5 条，覆盖真实财报、合成利润表、无表负样本、非标准结构和扫描件。
- spot-check：input_007 至 input_018 已有 real_las 输出，可作为 12 条离线结构统计抽查样本。
- design-only：input_001 至 input_006、input_019 至 input_030 用于补齐场景矩阵，不代表已真实跑测。

## 结论模板

自动化报告置信度：中。理由：输出契约与评分链路可离线复现，BYD 样本能形成有效 `financial_accuracy`；但多个合成/扫描样本的 Skill 输出尚未抽出金融指标，019/020/022 等异常 PDF 也未产生实测 `error_result.json`，不能声称异常处理已经真实跑通。

## 报告对应

- `reports/markdown/score_summary.md`：查看代表样本的 weighted_score、维度分与 Judge 状态。
- `reports/markdown/failure_cases.md`：manifest 级输出契约失败清单；本轮 manifest 视角可能为空，不能替代低分/低准确率分析。
- `reports/final/final_project_report.md`：查看最终计数、准确率口径、低分样本和项目 caveats。
