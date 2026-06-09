# 金融 PDF 评测用例集

生成日期：2026-06-04

## 统计摘要

- 物理 PDF 数：41
- 注册 YAML/逻辑用例数：42
- manual/manual_verified GT 文件数：6
- real_las 已有输出目录数：17
- design_only 规则：有 PDF 但没有 `data/real_las_outputs/<case_id>` 的用例只做设计登记，不进入 `configs/dataset_manifest.yaml`，也不要求 pipeline 跑通。
- runnable 规则：只有已有真实 output_dir 的 fixture case 才进入 manifest 和代表样本 pipeline。
- 异常 PDF 规则：没有 `meta/error_result.json` 时不登记 expected_error/error_code，也不强制 output_contract。

## 主表

| case_id | PDF | 场景类别 | 难度 | backend | GT 状态 | 是否计入准确率 | 是否已实际跑测 | 备注 |
|---|---|---|---|---|---|---|---|---|
| input_001_financial_normal_statement | input_001_financial_normal_statement.pdf | 正常财报 | 基础 | fixture | todo_manual_verify / metrics=0 | 否（design_only） | 否 | 标准财务表格解析；等待 real_las fixture 后再启用输出契约断言。 |
| input_002_financial_complex_cross_page_table | input_002_financial_complex_cross_page_table.pdf | 复杂表 | 高 | fixture | todo_manual_verify / metrics=0 | 否（design_only） | 否 | 跨页表连续性和表头识别；等待 fixture 后再跑 pipeline。 |
| input_003_financial_two_column_reading_order | input_003_financial_two_column_reading_order.pdf | 复杂表 | 中高 | fixture | todo_manual_verify / metrics=0 | 否（design_only） | 否 | 双栏文本顺序与表格定位；未实际跑测。 |
| input_004_scanned_noisy_financial_table | input_004_scanned_noisy_financial_table.pdf | 扫描 OCR | 高 | fixture | todo_manual_verify / metrics=0 | 否（design_only） | 否 | OCR 噪声鲁棒性；等待真实输出目录。 |
| input_005_medical_record_structured | input_005_medical_record_structured.pdf | 非财报领域 | 边界 | fixture | todo_manual_verify / metrics=0 | 否（design_only） | 否 | 非财务场景不应进入 financial_accuracy 分母。 |
| input_006_edge_sparse_rotated_watermark | input_006_edge_sparse_rotated_watermark.pdf | 复杂表 | 高 | fixture | todo_manual_verify / metrics=0 | 否（design_only） | 否 | 旋转/水印干扰下的解析边界；未实际跑测。 |
| input_007_income_statement | input_007_income_statement.pdf | 正常财报 | 已跑 fixture | fixture | manual_verified / metrics=8 | 否（合成/负样本或未纳入） | 是 | Synthetic eval PDF; source-of-truth in tools/generate_eval_pdfs.py |
| input_008_cashflow_supplement | input_008_cashflow_supplement.pdf | 正常财报 | 已跑 fixture | fixture | todo_manual_verify / metrics=6 | 否（合成/负样本或未纳入） | 是 | Synthetic eval PDF; source-of-truth in tools/generate_eval_pdfs.py |
| input_009_balance_sheet_assets | input_009_balance_sheet_assets.pdf | 正常财报 | 已跑 fixture | fixture | todo_manual_verify / metrics=8 | 否（合成/负样本或未纳入） | 是 | Synthetic eval PDF; source-of-truth in tools/generate_eval_pdfs.py |
| input_010_bilingual_income_statement | input_010_bilingual_income_statement.pdf | 正常财报 | 已跑 fixture | fixture | todo_manual_verify / metrics=7 | 否（合成/负样本或未纳入） | 是 | Synthetic eval PDF; source-of-truth in tools/generate_eval_pdfs.py |
| input_011_cross_page_income_statement | input_011_cross_page_income_statement.pdf | 正常财报 | 已跑 fixture | fixture | todo_manual_verify / metrics=9 | 否（合成/负样本或未纳入） | 是 | Synthetic eval PDF; source-of-truth in tools/generate_eval_pdfs.py |
| input_012_no_border_financial_table | input_012_no_border_financial_table.pdf | 正常财报 | 已跑 fixture | fixture | todo_manual_verify / metrics=5 | 否（合成/负样本或未纳入） | 是 | Synthetic eval PDF; source-of-truth in tools/generate_eval_pdfs.py |
| input_013_multi_header_performance_table | input_013_multi_header_performance_table.pdf | 正常财报 | 已跑 fixture | fixture | todo_manual_verify / metrics=6 | 否（合成/负样本或未纳入） | 是 | Synthetic eval PDF; source-of-truth in tools/generate_eval_pdfs.py |
| input_014_main_table_with_notes | input_014_main_table_with_notes.pdf | 正常财报 | 已跑 fixture | fixture | todo_manual_verify / metrics=8 | 否（合成/负样本或未纳入） | 是 | Synthetic eval PDF; source-of-truth in tools/generate_eval_pdfs.py |
| input_015_low_dpi_scan_sim | input_015_low_dpi_scan_sim.pdf | 正常财报 | 已跑 fixture | fixture | todo_manual_verify / metrics=5 | 否（合成/负样本或未纳入） | 是 | Synthetic eval PDF; source-of-truth in tools/generate_eval_pdfs.py；image-only PDF，准确率仅参考。 |
| input_016_stamp_watermark_table | input_016_stamp_watermark_table.pdf | 正常财报 | 已跑 fixture | fixture | todo_manual_verify / metrics=5 | 否（合成/负样本或未纳入） | 是 | Synthetic eval PDF; source-of-truth in tools/generate_eval_pdfs.py；image-only PDF，准确率仅参考。 |
| input_017_header_footer_noise | input_017_header_footer_noise.pdf | 正常财报 | 已跑 fixture | fixture | todo_manual_verify / metrics=5 | 否（合成/负样本或未纳入） | 是 | Synthetic eval PDF; source-of-truth in tools/generate_eval_pdfs.py；含页眉页脚噪声，准确率仅参考。 |
| input_018_meeting_minutes_no_table | input_018_meeting_minutes_no_table.pdf | 正常财报 | 已跑 fixture | fixture | manual_verified / metrics=0 | 否（合成/负样本或未纳入） | 是 | Synthetic eval PDF; source-of-truth in tools/generate_eval_pdfs.py |
| input_019_encrypted_financial_report | input_019_encrypted_financial_report.pdf | 异常输入 | 异常 | fixture | todo_manual_verify / metrics=0 | 否（design_only） | 否 | 若未来产出 meta/error_result.json，再用真实 error_code 增加 error_type_eq。 |
| input_020_corrupted_pdf | input_020_corrupted_pdf.pdf | 异常输入 | 异常 | fixture | todo_manual_verify / metrics=0 | 否（design_only） | 否 | 不得臆造 FILE_CORRUPTED 等错误码；等待实测 error_result。 |
| input_021_blank_pdf | input_021_blank_pdf.pdf | 异常输入 | 边界 | fixture | todo_manual_verify / metrics=0 | 否（design_only） | 否 | 期望无表；若未来出现 error_result 再登记 error_type_eq。 |
| input_022_fake_pdf_extension | input_022_fake_pdf_extension.pdf | 异常输入 | 异常 | fixture | todo_manual_verify / metrics=0 | 否（design_only） | 否 | 不得臆造 INVALID_FILE_TYPE；等待实测 error_result。 |
| input_023_long_annual_report_80p | input_023_long_annual_report_80p.pdf | 长文档成本 | 高 | fixture | todo_manual_verify / metrics=0 | 否（design_only） | 否 | 长文档成本/抽样 GT；未实际跑测。 |
| input_024_landscape_wide_financial_table | input_024_landscape_wide_financial_table.pdf | 复杂表 | 高 | fixture | todo_manual_verify / metrics=3 | 否（design_only） | 否 | 宽表列对齐与期间识别；已补 PDF 文本抽样 GT，仍待人工复核。 |
| input_025_unit_mixed_financial_table | input_025_unit_mixed_financial_table.pdf | 正常财报 | 中高 | fixture | todo_manual_verify / metrics=0 | 否（design_only） | 否 | RMB thousand/million/USD/share 等单位归一；未实际跑测。 |
| input_026_negative_decimal_financial_table | input_026_negative_decimal_financial_table.pdf | 正常财报 | 中高 | fixture | todo_manual_verify / metrics=3 | 否（design_only） | 否 | 括号负数、负号、小数和千分位；已补 PDF 文本抽样 GT，仍待人工复核。 |
| input_027_cross_page_repeated_header | input_027_cross_page_repeated_header.pdf | 复杂表 | 高 | fixture | todo_manual_verify / metrics=4 | 否（design_only） | 否 | 跨页续表和重复表头合并；已补 PDF 文本抽样 GT，仍待人工复核。 |
| input_028_financial_table_with_notes | input_028_financial_table_with_notes.pdf | 复杂表 | 中高 | fixture | todo_manual_verify / metrics=0 | 否（design_only） | 否 | 脚注/星号不应污染主表数值；未实际跑测。 |
| input_029_scanned_image_only_financial_report | input_029_scanned_image_only_financial_report.pdf | 扫描 OCR | 高 | fixture | todo_manual_verify / metrics=0 | 否（design_only） | 否 | OCR 图片表格解析；未实际跑测。 |
| input_030_cover_only_no_table_report | input_030_cover_only_no_table_report.pdf | 无表负样本 | 边界 | fixture | todo_manual_verify / metrics=0 | 否（design_only） | 否 | 不应输出 financial_table 或 metric_record；不参与 financial_accuracy。 |
| byd_real_las_fixture_gt_test | byd_caibao-123-124.pdf 等 | 真实财报 | 真实 fixture | fixture | manual_verified / metrics=10 | 是 | 是 | BYD 真实 LAS 输出，作为 accuracy 链路代表样本。 |
| byd_caibao-13-14 | byd_caibao-13-14.pdf | 真实财报 | 设计分段 | n/a | todo_manual_verify | 否（未单独 fixture） | 否 | BYD 分段设计覆盖；不单独进入 manifest。 |
| byd_caibao-29-31 | byd_caibao-29-31.pdf | 真实财报 | 设计分段 | n/a | todo_manual_verify | 否（未单独 fixture） | 否 | BYD 分段设计覆盖；不单独进入 manifest。 |
| byd_caibao-41-44 | byd_caibao-41-44.pdf | 真实财报 | 设计分段 | n/a | todo_manual_verify | 否（未单独 fixture） | 否 | BYD 分段设计覆盖；不单独进入 manifest。 |
| byd_caibao-123-124 | byd_caibao-123-124.pdf | 真实财报 | 设计分段 | n/a | manual_verified / metrics=10 | 通过 BYD 聚合 fixture | 是（聚合 fixture） | 与 byd_real_las_fixture_gt_test 共用聚合输出。 |
| huadian_real_las_fixture | 华电光大.pdf | 真实扫描件 | 非标准结构 | fixture | manual_verified / metrics=5 | 否（非标准结构标注） | 是 | 当前输出 financial_table_count=0，作为 unknown_table/非标准结构样本。 |
| 先锋财报_扫码件-6-9 | 先锋财报_扫码件-6-9.pdf | 真实扫描件 | 高 | fixture | manual_verified / metrics=32 | 是 | 是 | 扫描件资产负债表；当前 GT 结果显示 metric not found，是保留的失败证据。 |
| missing_input_pdf | data/samples/not_exists.pdf | 异常输入 | 异常 | official_output_mock | n/a | 否（异常逻辑） | 是（mock） | abnormal_cases.yaml 逻辑用例。 |
| invalid_file_type | data/abnormal/invalid.txt | 异常输入 | 异常 | official_output_mock | n/a | 否（异常逻辑） | 是（mock） | abnormal_cases.yaml 逻辑用例。 |
| missing_ground_truth | byd fixture | 异常输入 | 异常 | fixture | 缺失 GT | 否（异常逻辑） | 是 | abnormal_cases.yaml 逻辑用例。 |
| real_las_missing_key | sample.pdf | 异常输入 | 异常 | real_las | n/a | 否（异常逻辑） | 否（需环境变量） | abnormal_cases.yaml 逻辑用例。 |
| paper_rubric_learnable_assessment | paper_rubric_learnable_assessment.pdf | 论文演示 | 演示 | fixture | todo_manual_verify | 否（论文演示） | 是 | 单独标注，不计入金融评测用例集。 |

## 用例计入规则

- 设计用例覆盖：input_001 至 input_030 共 30 条，加 BYD 分段、华电、先锋与 abnormal_cases.yaml 逻辑用例，形成 40+ 条场景说明。
- `SkillOpt.pdf`、`skillEolver.pdf`、`Rubric Construction via Iterative Optimization.pdf` 是附件或论文材料，不计入金融 PDF 评测主集。
- `paper_rubric_learnable_assessment` 和 `paper_skill_evolver` 仅作论文/演示样本；即使存在 fixture，也不放入本轮 financial manifest。
- `financial_accuracy` 只由 manual/manual_verified 且有非空 `metrics[].expected`、并且未被标为 `count_as_real_evaluation: false` 的代表 fixture 贡献。

## 场景覆盖矩阵

| 场景类别 | 代表 case_id |
|---|---|
| 正常财报 | input_001, input_007, input_025, input_026, byd_real_las_fixture_gt_test |
| 复杂表 | input_002, input_003, input_011, input_024, input_027, input_028 |
| 扫描 OCR | input_004, input_015, input_016, input_029, 先锋财报_扫码件-6-9 |
| 异常输入 | input_019, input_020, input_021, input_022, abnormal_cases.yaml |
| 长文档成本 | input_023 |
| 无表负样本 | input_005, input_018, input_030 |
| 真实扫描件 | 华电光大, 先锋财报_扫码件-6-9, BYD 分段 PDF |
| 非财报领域 | input_005, input_018, input_030 |
