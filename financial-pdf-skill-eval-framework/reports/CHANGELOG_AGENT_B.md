# CHANGELOG — Agent B (SkillOpt 最小增量接入，Step 4–6)

> 工作区非 git 仓库，无法 `git commit`，按 Prompt 要求改为本文件记录每个 Step。
> 设计原则：新增 Python ≤ 2（`optimizer/skill_patch.py` + `optimizer/gate.py`）；
> `framework/context.py` 仅加 SKILL_DIR_OVERRIDE（~10 行）；不碰评测器 / GT / baseline。

---

## step-4 (2026-05-30T22:00+08:00) — add SkillOpt dry-run patch proposer

建议 commit message：`step-4: add SkillOpt dry-run patch proposer`

变更文件：
- `optimizer/skill_patch.py`（新增）— propose_patches + apply_to_workspace + snapshot_version 合一。
- `optimizer/patch_schema.json`（新增）— patch JSON schema，校验 target_scope ∈ {skill, judge}，target_file 禁绝对路径 / `..`。
- `configs/skillopt.yaml`（新增）— splits + gate 规则 + workspace 白名单。
- `tests/test_14_skill_patch_dryrun.py`（新增，`pytestmark = pytest.mark.offline`）。

验证输出摘要：
```
$ python -m optimizer.skill_patch --propose
{ "proposed_count": 1, "patch_ids": ["patch_v1_multi_header"], ... }
```
- 读 `reports/traces/*_failure_trace.json`（JSON，不读 Markdown）→ 生成 `reports/optimization/proposed_patches/patch_v1_multi_header.json`。
- patch 使用 `target_scope: skill` + 相对 `target_file: rules/multi_header_table_rebuilder.yaml`，通过 schema 校验。
- 生产 Skill 目录（`skills/.../` 根）未被修改。

---

## step-5 (2026-05-30T22:05+08:00) — add validation and regression gate

建议 commit message：`step-5: add validation and regression gate`

变更文件：
- `optimizer/gate.py`（新增）— run_gate（validation_gate + regression_guard 合一）+ Step 6 报告写入函数。
- `framework/context.py`（改 ~10 行）— `load_config()` 读取 `SKILL_DIR_OVERRIDE`，覆盖 `skill.path` 及全部脚本路径（唯一允许的框架层改动；不改 `config.example.yaml`）。
- `.gitignore`（追加）— 忽略 `.skillopt_workspace/` 与 `gate_config.yaml`。
- `tests/test_15_validation_gate.py`（新增，`pytestmark = pytest.mark.offline`）。

验证输出摘要：
```
$ python -m optimizer.gate --patch reports/optimization/proposed_patches/patch_v1_multi_header.json
"accepted": true, "accept_type": "no_regression_accepted",
"evaluation_mode": "fixture_scores_only",
"skill_dir_used": ".../.skillopt_workspace/skill_candidate",
"validation_status": "ran",
"missing_cases": [{ "case_yaml": ".../smoke_skill_standard.yaml", "reason": "output_dir_invalid" }],
"score_diff": { "byd_real_las_fixture": {"baseline": 8.8, "candidate": 8.8} }
```
- accept（`no_regression_accepted`）与 reject（故意坏 patch `patch_v1_demo_reject`，白名单静态检查拦截）各演示一种。
- `GateResult.skill_dir_used` 指向 `skill_candidate/`，非生产 Skill 路径；test_15 断言 `SKILL_DIR_OVERRIDE` 生效且运行后环境被清除。
- missing case（smoke fixture 无完整 standard profile）记录入 `missing_cases`，不崩溃。
- validation 为空时 `validation_status: skipped_no_cases`，报告不宣称泛化提升。
- `score_diff` 写入 `reports/optimization/score_diff_v0_v1.json`；reject 写 `optimizer/rejected_patch_buffer.json`。
- `evaluation_mode=fixture_scores_only`：fixture backend 不 re-invoke Skill，candidate 分数与 baseline 相同，accept 仅证明 gate 机制与路径覆盖正确，**不证明**解析能力提升。

```
$ python -m pytest tests/test_14_skill_patch_dryrun.py tests/test_15_validation_gate.py -q -m offline
12 passed
$ python -m pytest -q -m offline
82 passed, 21 deselected
```
> 备注：跑全量 offline 前清理了一处**预存**的 fixture 污染文件
> `data/real_las_outputs/byd_caibao/evaluation/gt_eval_result.json`
> （`ground_truth_source=manual_verified`，来自历史运行，非本次 gate 产生——
> byd case 的 GT 为 `todo_manual_verify`，gate 跑 pipeline 时 gt 阶段 skipped，不写该文件）。
> 删除后 `test_04` fixture 防污染断言恢复通过；未改 GT / baseline / 评测器。

---

## step-6 (2026-05-30T22:09+08:00) — add skill version snapshots and optimization reports

建议 commit message：`step-6: add skill version snapshots and optimization reports`

变更文件（均为产物，非新 Python 模块）：
- `skills/financial-pdf-parse-doubao-eval/skill_versions/skill_v1_multi_header/`（新增快照，仅 gate accept 后；不覆盖 skill 根目录）。
- `reports/optimization/skillopt_iterations.md`（新增）— 含 P0 措辞红线说明、skill_dir_used、evaluation_mode、validation_status、missing_cases、score_diff 表、accept_type。
- `reports/optimization/accepted_patches.md` / `rejected_patches.md`（新增清单）。
- `reports/optimization/score_diff_v0_v1.json`（新增）。
- `reports/optimization/proposed_patches/patch_v1_multi_header.json`、`patch_v1_demo_reject.json`（dry-run 提案 / reject 演示输入）。
- `optimizer/rejected_patch_buffer.json`（被拒绝 patch 持久化）。

完成校验：
- `reports/optimization/skillopt_iterations.md` 存在且可读。
- baseline 目录 `reports/baseline/*` 未被改动。
- 生产 Skill 根目录未被 silent 修改（仅 `skill_versions/skill_v1_multi_header/` 新增快照；`Test-Path skills/.../rules` = False）。

## 红线遵守自查
- 未重写 Judge / scoring_model / failure_trace。
- 未修改 GT / 评测器 / baseline 提分。
- 未 copy `references/paper_skillopt/` 上游代码。
- 未实现多 epoch 自动循环。
- 新增 Python 文件 = 2（skill_patch.py + gate.py）；context.py 仅 SKILL_DIR_OVERRIDE。
- `no_regression_accepted` 未被表述为「优化成功 / 解析能力提升」。
- patch 全部使用 `target_scope` + 相对路径；gate 记录 `skill_dir_used`，不 silent 用生产路径。
