# 指标-样本-GT 清单模板（可直接复制）

> 用法：每新增一个评测指标，至少绑定一个样本与一个 GT 文件（或明确说明为何暂不需要 GT）。

## A. 指标映射总表（模板）

| metric_id | 指标维度 | 评测问题 | 打分规则（1~10） | 权重 | 样本类型 | case_id | case 文件 | GT 文件 | GT source | 通过阈值 | 备注 |
|---|---|---|---|---:|---|---|---|---|---|---|---|
| M-001 | output_contract | 输出是否齐全 | pass=10, fail=2 | 0.10 | normal | example_case | `testcases/pdf_cases/example.yaml` | N/A | N/A | 必需文件齐全 | |
| M-002 | financial_accuracy | 数值是否准确 | `1+9*accuracy` | 0.35 | normal | example_case | `testcases/pdf_cases/example.yaml` | `evaluation/ground_truth/example_gt.json` | manual_verified | >=8.0 | |
| M-003 | abnormal_handling | 异常是否可控 | 预期错误命中=10 | 0.10 | abnormal | missing_input_pdf | `testcases/pdf_cases/abnormal_cases.yaml` | N/A | N/A | 预期 error_code | |

---

## B. 样本清单（模板）

| sample_id | 文件名/来源 | 分层 | 页数 | 语言 | 难点标签 | 是否已建 case | case_id | 是否已建 GT | GT 文件 |
|---|---|---|---:|---|---|---|---|---|---|
| S-001 | `xxx.pdf` | Normal | 12 | zh | 标准财报 | 是 | case_xxx | 是 | `evaluation/ground_truth/case_xxx_gt.json` |
| S-002 | `yyy_scan.pdf` | Adversarial | 8 | zh | 扫描件/水印 | 是 | case_yyy | 否 | 待补 |
| S-003 | `zzz_long.pdf` | Long-doc | 120 | zh/en | 超长文档 | 否 | 待建 | 否 | 待补 |

---

## C. GT 填写模板（JSON）

```json
{
  "case_id": "replace_case_id",
  "source": "manual_verified",
  "note": "Human verified against original PDF pages.",
  "metrics": [
    {
      "statement": "合并资产负债表",
      "item": "资产总计",
      "period": "2025-12-31",
      "expected": "18,902,992,212.04",
      "page": 1,
      "evidence": "pdf_page_1_manual_check"
    }
  ]
}
```

### GT source 取值规范

- 进入准确率分母：`manual`, `human_verified`, `manual_verified`
- 不进入准确率分母：`todo_manual_verify`, `template`, `synthetic`, `auto`, `skill_output`, 空值

---

## D. case YAML 模板（可选字段已包含）

```yaml
case_id: replace_case_id
name: Replace Case Name
backend: fixture
output_profile: standard
output_dir: data/real_las_outputs/replace_case_id
ground_truth: evaluation/ground_truth/replace_case_id_gt.json
tags:
  - offline
  - normal

scoring:
  profile: pdf_financial_score

cost_guard:
  max_pages: 30
  allow_real_cost: false

validations:
  - type: output_contract
    profile: standard
  - type: data_authenticity
    require_non_synthetic: true
  - type: gt_numeric_accuracy_ge
    threshold: 0.80
    skip_if_no_ground_truth: true
```

---

## E. 每周维护动作（建议）

1. 新增样本后，先登记到 “样本清单”。
2. 新增 case 后，补充到 “指标映射总表”。
3. GT 完成人工核验后，更新 `source` 为 `manual_verified`。
4. 每次批量评测后，把低分 case 追加到 `docs/failure_cases.md` 的人工分析段。

---

## F. 当前仓库实填版：指标-样本-GT 映射

> 下面是基于当前仓库已有 case 的预填版本，可作为周四评审的“现状覆盖表”。  
> 注意：`todo_manual_verify` / `template` 不进入准确率分母；只有 `manual_verified` 当前可进入 `financial_accuracy`。

| metric_id | 指标维度 | 评测问题 | 打分规则（1~10） | 权重 | 样本类型 | case_id | case 文件 | GT 文件 | GT source | 通过阈值 | 备注 |
|---|---|---|---|---:|---|---|---|---|---|---|---|
| M-001 | output_contract | standard profile 必需产物是否齐全 | pass=10, fail=2 | 0.10 | normal / real_las fixture | `byd_real_las_fixture` | `testcases/pdf_cases/byd_real_las_fixture.yaml` | N/A | N/A | 必需文件齐全 | BYD fixture 用于输出契约与结构统计 |
| M-002 | data_authenticity | 输出是否来自真实 LAS 且非 synthetic | pass=10, fail=1 | 0.10 | real_las fixture | `byd_real_las_fixture` | `testcases/pdf_cases/byd_real_las_fixture.yaml` | N/A | N/A | `expected_backend=real_las` | `count_as_real_evaluation=true`，但 GT 未完成 |
| M-003 | table_structure | 是否识别到财务表与财务指标 | 按 raw/financial/unknown table 分级 | 0.25 | normal financial report | `byd_real_las_fixture` | `testcases/pdf_cases/byd_real_las_fixture.yaml` | `evaluation/ground_truth/byd_manual_gt.json` | `todo_manual_verify` | `financial_table_count>=1`, `metric_record_count>=1` | 结构可评；准确率暂不进分母 |
| M-004 | financial_accuracy | 手工 GT 数值是否匹配 | `1+9*numeric_accuracy` | 0.35 | scanned financial report | `先锋财报_扫码件-6-9` | `testcases/pdf_cases/先锋财报_扫码件-6-9.yaml` | `evaluation/ground_truth/先锋财报_扫码件-6-9_manual_gt.json` | `manual_verified` | `numeric_accuracy>=0.80` | 当前唯一可进入准确率分母的人工 GT，含 32 条 metric |
| M-005 | table_structure | 非标准业绩报表是否被合理识别为非财务表 | 分级；非标准样本重点看 raw table 与 unknown table | 0.25 | non-standard report | `huadian_real_las_fixture` | `testcases/pdf_cases/huadian_real_las_fixture.yaml` | `evaluation/ground_truth/huadian_manual_gt.json` | `todo_manual_verify` | `raw_table_count>=1`, `financial_table_count==0`, `metric_record_count==0` | 该样本不作为准确率样本，主要用于结构分类和真实性 |
| M-006 | abnormal_handling | 输入 PDF 不存在是否输出预期错误 | 预期错误命中=10，否则=3 | 0.10 | abnormal | `missing_input_pdf` | `testcases/pdf_cases/abnormal_cases.yaml` | N/A | N/A | `FILE_NOT_FOUND` | 覆盖文件不存在场景 |
| M-007 | abnormal_handling | 非 PDF 文件是否输出预期错误 | 预期错误命中=10，否则=3 | 0.10 | abnormal | `invalid_file_type` | `testcases/pdf_cases/abnormal_cases.yaml` | N/A | N/A | `INVALID_FILE_TYPE` | 覆盖格式错误场景 |
| M-008 | abnormal_handling | 缺少 GT 是否 no_ground_truth 而非 fatal | 预期错误命中=10，否则=3 | 0.10 | abnormal | `missing_ground_truth` | `testcases/pdf_cases/abnormal_cases.yaml` | `evaluation/ground_truth/not_exists.json` | missing | `NO_GROUND_TRUTH` | 覆盖 GT 缺失场景 |
| M-009 | abnormal_handling / cost_guard | real_las 无 Key 时是否 skip 而非产生费用 | skip=10, fatal/cost=1 | 0.10 | abnormal / real_las gated | `real_las_missing_key` | `testcases/pdf_cases/abnormal_cases.yaml` | N/A | N/A | `AUTH_MISSING` / skipped | 覆盖真实调用成本门禁 |

---

## G. 当前仓库实填版：样本清单

| sample_id | 文件名/来源 | 分层 | 页数 | 语言 | 难点标签 | 是否已建 case | case_id | 是否已建 GT | GT 文件 |
|---|---|---|---:|---|---|---|---|---|---|
| S-001 | `data/real_las_outputs/byd_caibao` | Normal | 2 | zh | 标准财报、资产负债表、真实 LAS fixture | 是 | `byd_real_las_fixture` | 是（待人工填值） | `evaluation/ground_truth/byd_manual_gt.json` |
| S-002 | `data/real_las_outputs/华电光大` | Adversarial / non-standard | 未在清单中固定 | zh | 非标准业绩报表、unknown_table | 是 | `huadian_real_las_fixture` | 是（空模板） | `evaluation/ground_truth/huadian_manual_gt.json` |
| S-003 | `data/real_las_outputs/先锋财报_扫码件-6-9` | Adversarial / scanned | 4 | zh | 扫描件、资产负债表、OCR 挑战、manual GT | 是 | `先锋财报_扫码件-6-9` | 是（已人工核验） | `evaluation/ground_truth/先锋财报_扫码件-6-9_manual_gt.json` |
| S-004 | `data/samples/not_exists.pdf` | Abnormal | N/A | N/A | 文件不存在 | 是 | `missing_input_pdf` | 不需要 | N/A |
| S-005 | `data/abnormal/invalid.txt` | Abnormal | N/A | N/A | 非 PDF 文件 | 是 | `invalid_file_type` | 不需要 | N/A |
| S-006 | `data/real_las_outputs/byd_caibao` + missing GT path | Abnormal | 2 | zh | GT 缺失 | 是 | `missing_ground_truth` | 故意缺失 | `evaluation/ground_truth/not_exists.json` |
| S-007 | `data/samples/sample.pdf` | Abnormal / real_las gated | 未知 | N/A | real_las 无 Key / 成本门禁 | 是 | `real_las_missing_key` | 不需要 | N/A |

---

## H. 当前覆盖缺口（评审时可说明）

| 缺口 | 当前状态 | 建议补充 |
|---|---|---|
| BYD GT 未填人工 expected | `byd_manual_gt.json` 仍是 `todo_manual_verify`，5 条 anchor metric 均为空 | 优先人工填 5~10 个关键指标，并将 `source` 改为 `manual_verified` |
| 多语种/混合语言 PDF | 当前没有专门 case | 新增中英混排财报或英文年报 PDF |
| 长文档/超长 PDF | 当前没有专门 case | 新增 50+ 页样本，验证截断、稳定性、成本 |
| 图表/Bounding Box/版面层级 | 当前以表格结构为主，未单独设计 bbox GT | 后续 P1 增加 layout GT 或人工版面检查项 |
| 损坏 PDF | 当前 abnormal 有 missing/wrong type，但没有 corrupt PDF | 新增破损 PDF case，期望明确错误码 |
| 成本性能真实数据 | 需 API Key 后跑 `real_las` | 小批量 2~3 个样本先行，记录页数/价格/状态 |

