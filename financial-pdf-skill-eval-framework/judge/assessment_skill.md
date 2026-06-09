# Assessment Skill — v1 (static)

> 本文件是 LLM-as-a-Judge 的「可学习评分技能」载体，遵循 Learnable Assessment
> Skills 思想：固定 **scaffold** + 可迭代 **Rubric rules**。本版本为 v1 static，
> 仅做稳定评分，**不**做 Rubric 自动优化（留给后续 Agent）。

## Scaffold（固定评分流程）

1. 读取被测 Skill 的结构化输出（parsed.md / normalized_tables / financial_summary /
   quality_checks / run_meta）。
2. 针对每个可评维度，对照 Rubric rules 给出 0~1 浮点分。
3. 对每个扣分点产出一条 `deduction_items`（dimension + reason + evidence）。
4. 输出整体 `confidence`（评估自身判断的可靠度）。
5. 严格按 `judge_result_schema.json` 输出 JSON，不输出额外文本。

## 评分边界（红线）

- **只评**：`reading_order`、`table_structure`（Judge 视角）、`evidence_alignment`。
- **不评**：`output_contract`、`data_authenticity`、`financial_accuracy`、`cost_performance`。
- Judge 的 `table_structure_score` **不覆盖** deterministic 评分，仅作诊断信号。
- 不对财务数值做 Ground Truth 比对（那是确定性评测器的职责）。

## Rubric rules（item-agnostic，可迭代）

### reading_order
- 标题/正文/表格的顺序是否符合自然阅读顺序；多栏是否被错误交叉拼接。
- 跨页内容是否被错误割裂或重复。

### table_structure
- 多级表头是否展开为稳定二维结构（period 列可识别）。
- 是否存在合并单元格丢失、行列错位、数值串列。
- 表格类型（financial / layout / signature）是否被正确区分。

### evidence_alignment
- `financial_summary` 抽取的指标能否在 `normalized_tables` / `parsed.md` 中找到对应证据。
- 抽取的 period、item、value 是否与原文一致（结构层面，非数值精度）。

## 评分锚点（0~1）

- `0.9~1.0`：结构完整，几乎无可观察缺陷。
- `0.7~0.9`：基本正确，存在个别非关键缺陷。
- `0.4~0.7`：存在影响下游使用的结构缺陷。
- `0.0~0.4`：结构严重损坏或大量信息丢失。
