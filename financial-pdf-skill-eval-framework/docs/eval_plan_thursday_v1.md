# PDF 解析系统性评测方案（周四评审版 V1）

## 1. 评测目标与边界

- **目标**：建立可复用、可扩展、可解释的 PDF 解析能力灰度评测体系，输出 `1~10` 分区间分。
- **当前阶段（P0）**：先基于确定性信号跑通评测闭环（不引入 LLM Judge）。
- **边界约束**：
  - 不修改被测 Skill 业务逻辑（`skills/financial-pdf-parse-doubao-eval/`）。
  - 先做离线设计与样本准备，待 API Key 到位后执行真实调用。
  - 严格控制成本（页数、调用次数、Token 消耗）。

---

## 2. 评测体系总览（模块化）

本仓库按以下模块协作：

1. **用例编排层**：`testcases/pdf_cases/*.yaml`
2. **执行层**：`framework/skill_invoker.py`
3. **契约与断言层**：`framework/output_contract.py` + `framework/assertion_engine.py`
4. **GT 评估层**：`framework/gt_evaluator.py`（仅 manual/human_verified 进入准确率）
5. **评分层**：`framework/scoring_model.py` + `configs/scoring/pdf_financial_score.yaml`
6. **报告层**：`framework/report_collector.py`（summary/failure/score/final）
7. **静态守门层**：`static_tests/*.py` + `static_tests/run_static.py`

---

## 3. 评分模型（1~10 分）

### 3.1 维度与权重（V1）

| 维度 | 权重 | 说明 |
|---|---:|---|
| output_contract | 10% | 标准输出产物完整性 |
| data_authenticity | 10% | 执行来源真实性（real/mock/synthetic） |
| table_structure | 25% | 表格结构与财务表识别质量 |
| financial_accuracy | 35% | GT 数值准确率（仅合格 GT） |
| abnormal_handling | 10% | 异常场景处理与预期报错 |
| cost_performance | 10% | 页数/状态/成本表现 |

### 3.2 评分规则（V1）

- 布尔类：`pass=10`，`fail` 按严重度映射到 `1~4`。
- 比率类：`score = round(1 + 9 * ratio, 1)`。
- 当 `financial_accuracy=null`（例如 GT 不可用）时，将其权重按配置重分配给 `table_structure + output_contract`。

### 3.3 分数解释

- `>=8`：good（可上线候选）
- `>=6` 且 `<8`：fair（可灰度，但需优化）
- `<6`：poor（需重点修复后再评估）

---

## 4. 数据集构建策略（因果关系驱动）

### 4.1 原则

每个指标必须由可验证样本支撑，形成链路：

`指标 -> 样本类型 -> case.yaml -> ground_truth -> 断言/评分`

### 4.2 样本分层（建议）

| 分层 | 目标覆盖 | 样本建议 |
|---|---|---|
| Normal | 标准财务报表 | 资产负债表/利润表/现金流量表 |
| Complex | 跨页/密集/无边框 | 跨页长表、列头复杂、细粒度金额 |
| Adversarial | OCR 干扰 | 扫描件、印章水印、噪声页脚 |
| Abnormal | 鲁棒性 | 损坏文件、非 PDF、缺 GT、无密钥 |
| Multi-lang | 语言泛化 | 中英混排、多语种财务文本 |
| Long-doc | 长文档能力 | 超长页数（分页、截断、稳定性） |

### 4.3 GT 生产规范

- GT canonical 统一使用 `metrics[]`。
- `source` 必须明确：
  - `manual` / `human_verified` / `manual_verified`：可进入准确率分母
  - `todo_manual_verify` / `template` / `synthetic` / `auto` / `skill_output`：不进入分母
- `metrics[].expected` 为空时必须被记录为 `skipped_expected_items`，不得污染准确率。

---

## 5. 周四评审可展示产物

1. **体系图**：模块划分 + 数据流（case -> invoke -> assert -> gt -> score -> report）
2. **评分口径**：维度、权重、1~10 映射、缺失重分配逻辑
3. **样本策略**：按分层给出当前覆盖与缺口
4. **GT 规范**：source gating + 空 expected 处理机制
5. **成本门禁策略**：real_las 双门禁（`LAS_API_KEY` + `ALLOW_REAL_LAS=1`）

---

## 6. 执行计划与里程碑

### 6.1 本周四前（方案评审）

- 完成评测体系文档（本文件）
- 完成“指标-样本-GT 清单”初版（见模板文件）
- 落地 10~15 个 case 清单（允许部分 GT 先留空）

### 6.2 API Key 到位后（灰度跑测）

- 先跑 2~3 个 real_las 核心样本，校验真实性与成本
- 观察页数/价格/错误率，再扩大到全量
- 每批次都输出 `score_summary.md` 与 `failure_cases.md`

### 6.3 下周（结果交付）

- 产出最终分布（维度分 + 加权分 + 案例分析）
- 给出可执行优化建议（按 failure type 聚类）

---

## 7. 成本与风险控制

### 7.1 成本控制

- 默认使用 `fixture` / `official_output_mock` 进行离线验证。
- `real_las` 必须手动开启，且建议 case 配置 `cost_guard`：
  - `max_pages`
  - `allow_real_cost`
- 先小样本试跑，再逐步扩容，避免一次性全量烧钱。

### 7.2 风险清单

- **风险 A**：GT 不足导致 `financial_accuracy` 长期为空。  
  **应对**：优先填充高价值样本 GT（每类至少 1~2 个）。
- **风险 B**：真实调用成本不可控。  
  **应对**：设置分批预算与页数门槛，超过即停止批次。
- **风险 C**：异常样本覆盖不足。  
  **应对**：为损坏文件/非标准格式/超长文档追加专门 case。

---

## 8. 评审答疑建议话术（简版）

- “我们把 PDF 解析评测拆成了 7 个可独立验证模块，避免只看单一准确率。”
- “准确率只对人工核验 GT 生效，模板或自动生成 GT 一律不进分母，防止虚高。”
- “先离线跑通确定性链路，再小规模 real_las 灰度，确保成本可控。”
- “最终结论不止一个总分，还会给出按失败类型分组的可执行改进建议。”

