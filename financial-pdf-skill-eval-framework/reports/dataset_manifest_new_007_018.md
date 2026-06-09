# Dataset manifest: synthetic financial PDF cases input_007-input_018

| filename | case_id | band | pages | image_only | metrics_count | gt_source | diff_note | tests |
|---|---|---|---:|---|---:|---|---|---|
| input_007_income_statement.pdf | input_007_income_statement | normal | 1 | false | 8 | todo_manual_verify | 补充中文利润表场景，与已有资产负债表片段不同。 | financial_table>=1; metric_record>=5; GT numeric>=0.80 |
| input_008_cashflow_supplement.pdf | input_008_cashflow_supplement | normal | 1 | false | 6 | todo_manual_verify | 补充现金流量表补充资料样式，覆盖非资产负债表指标。 | financial_table>=1; metric_record>=5; GT numeric>=0.80 |
| input_009_balance_sheet_assets.pdf | input_009_balance_sheet_assets | normal | 1 | false | 8 | todo_manual_verify | 补充资产侧层级和小计，与已有资产负债表片段版式不同。 | financial_table>=1; metric_record>=5; GT numeric>=0.80 |
| input_010_bilingual_income_statement.pdf | input_010_bilingual_income_statement | normal | 2 | false | 7 | todo_manual_verify | 新增表头中英混排场景，正文项目和数值仍为中文财报表达。 | financial_table>=1; metric_record>=5; GT numeric>=0.80 |
| input_011_cross_page_income_statement.pdf | input_011_cross_page_income_statement | complex | 2 | false | 9 | todo_manual_verify | 跨页续表使用利润表和专门续表文案，区别于既有跨页表样本。 | financial_table>=1; metric_record>=5; GT numeric>=0.80 |
| input_012_no_border_financial_table.pdf | input_012_no_border_financial_table | complex | 1 | false | 5 | todo_manual_verify | 新增无竖线边框的坐标排版表，专测空白和列宽对齐。 | financial_table>=1; metric_record>=5; GT numeric>=0.80 |
| input_013_multi_header_performance_table.pdf | input_013_multi_header_performance_table | complex | 1 | false | 6 | todo_manual_verify | 新增营业总收入和净利润双指标多级表头，列名避开既有华电样式。 | financial_table>=1; metric_record>=5; GT numeric>=0.80 |
| input_014_main_table_with_notes.pdf | input_014_main_table_with_notes | complex | 2 | false | 8 | todo_manual_verify | 新增主表加两张附注表，覆盖主表与注释表联动场景。 | financial_table>=1; metric_record>=5; GT numeric>=0.80 |
| input_015_low_dpi_scan_sim.pdf | input_015_low_dpi_scan_sim | adversarial | 1 | true | 5 | todo_manual_verify | 先渲染为图再嵌入 PDF，带灰底、轻微倾斜和确定性噪声。 | image-only; financial_table>=1; metric_record>=5; GT numeric>=0.50 |
| input_016_stamp_watermark_table.pdf | input_016_stamp_watermark_table | adversarial | 1 | true | 5 | todo_manual_verify | 图像型 PDF 叠加红章和半透明样本水印，关键数字行保持可读。 | image-only; financial_table>=1; metric_record>=5; GT numeric>=0.50 |
| input_017_header_footer_noise.pdf | input_017_header_footer_noise | adversarial | 1 | false | 5 | todo_manual_verify | 新增重复页眉、页脚页码和横线噪声，表格位于页面中部。 | header/footer noise; financial_table>=1; metric_record>=5; GT numeric>=0.50 |
| input_018_meeting_minutes_no_table.pdf | input_018_meeting_minutes_no_table | boundary | 1 | false | 0 | todo_manual_verify | 金融语境会议纪要但无任何表格，区别于医疗域外样本。 | 无表; financial_table==0; metric_record==0 |

## 接入步骤

1. `python tools/generate_eval_pdfs.py`
2. 人工抽查 PDF vs GT。
3. （可选）人工核对后运行 `python tools/generate_eval_pdfs.py --promote-verified`。
4. 对每个 case 跑 real_las 或 mock，导入到 `data/real_las_outputs/<case_id>/`，再保持 `backend: fixture` 评测。
5. `python run.py --cases testcases/pdf_cases/input_007_income_statement.yaml --backend fixture --pipeline`
6. `python run.py --build-dashboard-bundle`
