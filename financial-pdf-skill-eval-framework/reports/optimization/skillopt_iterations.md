# SkillOpt Iterations

## skill_v0_baseline -> skill_v1_multi_header

> P0 说明：若 accept_type=no_regression_accepted，表示 patch 未造成回归且 gate 通过，
> **不代表**真实解析能力已提升。能力提升需 patch 被 postprocess 消费且在 validation case 上可量化提高。

### 修改了什么
- patch_id: `patch_v1_multi_header`
- target_scope: `skill`
- target_file: `rules/multi_header_table_rebuilder.yaml`
- edit_type: `add`
- change 摘要: {"rule_id": "multi_header_table_rebuilder", "description": "当表格前两行均包含日期/期间字段时，合并为多级表头并展开 period 列", "trigger": "table_top_rows_contain_period_tokens", "action": "merge_into_multilevel_header"}

### skill_dir_used
- `C:\Users\zed\Desktop\skillv4\financial-pdf-skill-eval-framework\.skillopt_workspace\skill_candidate`

### evaluation_mode
- `fixture_scores_only`（fixture backend 不 re-invoke Skill，只对比已有 fixture 分数）

### 为什么修改
- failure_trace 来源: `byd_caibao`；reason: failure_trace 显示多级日期表头未展开为稳定二维结构，period 列识别失败

### accept_type
- `no_regression_accepted`

### validation_status
- `ran`

### resolved_splits
- train: ['byd_real_las_fixture']
- validation: ['huadian_real_las_fixture']
- regression: ['byd_real_las_fixture']

### missing_cases
- `testcases/pdf_cases/smoke_skill_standard.yaml` -> output_dir_invalid

### 哪些 case 提升 / 未提升

| case | baseline | candidate |
|------|----------|-----------|
| byd_real_las_fixture | 8.8 | 8.8 |
| huadian_real_las_fixture | None | 6.3 |

### 是否回归
- 无回归

### 是否通过 validation gate
- accepted: True

---
## skill_v0_baseline -> skill_v1_demo_reject

> P0 说明：若 accept_type=no_regression_accepted，表示 patch 未造成回归且 gate 通过，
> **不代表**真实解析能力已提升。能力提升需 patch 被 postprocess 消费且在 validation case 上可量化提高。

### 修改了什么
- patch_id: `patch_v1_demo_reject`
- target_scope: `skill`
- target_file: `../../framework/scoring_model.py`
- edit_type: `replace`
- change 摘要: {"text": "weighted_score = 10.0  # cheating"}

### skill_dir_used
- `None`

### evaluation_mode
- `fixture_scores_only`（fixture backend 不 re-invoke Skill，只对比已有 fixture 分数）

### 为什么修改
- failure_trace 来源: `synthetic_negative_example`；reason: 故意坏 patch：试图越权改写评测器以提分，必须被 gate 白名单静态检查拦截

### accept_type
- `rejected`

### validation_status
- `skipped_no_cases`

### resolved_splits
- train: []
- validation: []
- regression: []

### missing_cases
- 无

### 哪些 case 提升 / 未提升
- validation split 为空：不宣称泛化能力提升，仅证明 gate 机制可运行。
- N/A

### 是否回归
- 存在问题：patch failed whitelist/schema check: unsafe target_file (absolute / '..' / drive not allowed): '../../framework/scoring_model.py'

### 是否通过 validation gate
- accepted: False

---
## skill_v0_baseline -> skill_v1_multi_header

> P0 说明：若 accept_type=no_regression_accepted，表示 patch 未造成回归且 gate 通过，
> **不代表**真实解析能力已提升。能力提升需 patch 被 postprocess 消费且在 validation case 上可量化提高。

### 修改了什么
- patch_id: `patch_v1_multi_header`
- target_scope: `skill`
- target_file: `rules/multi_header_table_rebuilder.yaml`
- edit_type: `add`
- change 摘要: {"rule_id": "multi_header_table_rebuilder", "description": "当表格前两行均包含日期/期间字段时，合并为多级表头并展开 period 列", "trigger": "table_top_rows_contain_period_tokens", "action": "merge_into_multilevel_header"}

### skill_dir_used
- `C:\Users\zed\Desktop\skillv4\financial-pdf-skill-eval-framework\.skillopt_workspace\skill_candidate`

### evaluation_mode
- `fixture_scores_only`（fixture backend 不 re-invoke Skill，只对比已有 fixture 分数）

### 为什么修改
- failure_trace 来源: `byd_caibao`；reason: failure_trace 显示多级日期表头未展开为稳定二维结构，period 列识别失败

### accept_type
- `no_regression_accepted`

### validation_status
- `ran`

### resolved_splits
- train: ['byd_real_las_fixture']
- validation: ['huadian_real_las_fixture']
- regression: ['byd_real_las_fixture']

### missing_cases
- `testcases/pdf_cases/smoke_skill_standard.yaml` -> output_dir_invalid

### 哪些 case 提升 / 未提升

| case | baseline | candidate |
|------|----------|-----------|
| byd_real_las_fixture | 8.8 | 8.8 |
| huadian_real_las_fixture | None | 4.9 |

### 是否回归
- 无回归

### 是否通过 validation gate
- accepted: True

---
## skill_v0_baseline -> skill_v1_demo_reject

> P0 说明：若 accept_type=no_regression_accepted，表示 patch 未造成回归且 gate 通过，
> **不代表**真实解析能力已提升。能力提升需 patch 被 postprocess 消费且在 validation case 上可量化提高。

### 修改了什么
- patch_id: `patch_v1_demo_reject`
- target_scope: `skill`
- target_file: `../../framework/scoring_model.py`
- edit_type: `replace`
- change 摘要: {"text": "weighted_score = 10.0  # cheating"}

### skill_dir_used
- `None`

### evaluation_mode
- `fixture_scores_only`（fixture backend 不 re-invoke Skill，只对比已有 fixture 分数）

### 为什么修改
- failure_trace 来源: `synthetic_negative_example`；reason: 故意坏 patch：试图越权改写评测器以提分，必须被 gate 白名单静态检查拦截

### accept_type
- `rejected`

### validation_status
- `skipped_no_cases`

### resolved_splits
- train: []
- validation: []
- regression: []

### missing_cases
- 无

### 哪些 case 提升 / 未提升
- validation split 为空：不宣称泛化能力提升，仅证明 gate 机制可运行。
- N/A

### 是否回归
- 存在问题：patch failed whitelist/schema check: unsafe target_file (absolute / '..' / drive not allowed): '../../framework/scoring_model.py'

### 是否通过 validation gate
- accepted: False

---
## skill_v0_baseline -> skill_v1_multi_header

> P0 说明：若 accept_type=no_regression_accepted，表示 patch 未造成回归且 gate 通过，
> **不代表**真实解析能力已提升。能力提升需 patch 被 postprocess 消费且在 validation case 上可量化提高。

### 修改了什么
- patch_id: `patch_v1_multi_header`
- target_scope: `skill`
- target_file: `rules/multi_header_table_rebuilder.yaml`
- edit_type: `add`
- change 摘要: {"rule_id": "multi_header_table_rebuilder", "description": "当表格前两行均包含日期/期间字段时，合并为多级表头并展开 period 列", "trigger": "table_top_rows_contain_period_tokens", "action": "merge_into_multilevel_header"}

### skill_dir_used
- `C:\Users\zed\Desktop\skillv4\financial-pdf-skill-eval-framework\.skillopt_workspace\skill_candidate`

### evaluation_mode
- `fixture_scores_only`（fixture backend 不 re-invoke Skill，只对比已有 fixture 分数）

### 为什么修改
- failure_trace 来源: `byd_caibao`；reason: failure_trace 显示多级日期表头未展开为稳定二维结构，period 列识别失败

### accept_type
- `no_regression_accepted`

### validation_status
- `ran`

### resolved_splits
- train: ['byd_real_las_fixture']
- validation: ['huadian_real_las_fixture']
- regression: ['byd_real_las_fixture']

### missing_cases
- `testcases/pdf_cases/smoke_skill_standard.yaml` -> output_dir_invalid

### 哪些 case 提升 / 未提升

| case | baseline | candidate |
|------|----------|-----------|
| byd_real_las_fixture | 8.8 | 8.8 |
| huadian_real_las_fixture | None | 4.9 |

### 是否回归
- 无回归

### 是否通过 validation gate
- accepted: True

---
## skill_v0_baseline -> skill_v1_demo_reject

> P0 说明：若 accept_type=no_regression_accepted，表示 patch 未造成回归且 gate 通过，
> **不代表**真实解析能力已提升。能力提升需 patch 被 postprocess 消费且在 validation case 上可量化提高。

### 修改了什么
- patch_id: `patch_v1_demo_reject`
- target_scope: `skill`
- target_file: `../../framework/scoring_model.py`
- edit_type: `replace`
- change 摘要: {"text": "weighted_score = 10.0  # cheating"}

### skill_dir_used
- `None`

### evaluation_mode
- `fixture_scores_only`（fixture backend 不 re-invoke Skill，只对比已有 fixture 分数）

### 为什么修改
- failure_trace 来源: `synthetic_negative_example`；reason: 故意坏 patch：试图越权改写评测器以提分，必须被 gate 白名单静态检查拦截

### accept_type
- `rejected`

### validation_status
- `skipped_no_cases`

### resolved_splits
- train: []
- validation: []
- regression: []

### missing_cases
- 无

### 哪些 case 提升 / 未提升
- validation split 为空：不宣称泛化能力提升，仅证明 gate 机制可运行。
- N/A

### 是否回归
- 存在问题：patch failed whitelist/schema check: unsafe target_file (absolute / '..' / drive not allowed): '../../framework/scoring_model.py'

### 是否通过 validation gate
- accepted: False

---
