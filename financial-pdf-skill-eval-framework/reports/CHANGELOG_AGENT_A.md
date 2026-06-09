# CHANGELOG — Agent A (Assessment-Skill Judge + failure_trace 接入)

> 工作区非 git 仓库，无法 `git commit`，按任务约定改为此文件记录每个 step。

## step-0 (2026-05-30T18:50:00+08:00)

freeze skill_v0_baseline and baseline reports

**变更文件（仅新增数据/快照，零业务逻辑改动）：**

- `skills/financial-pdf-parse-doubao-eval/skill_versions/skill_v0_baseline/`（25 文件快照，排除 `__pycache__`/`.pytest_cache`/`outputs`/`logs`）
- `reports/baseline/baseline_v0_summary.json`
- `reports/baseline/baseline_v0_evaluation_summary.md`
- `reports/CHANGELOG_AGENT_A.md`（本文件）

**建议 commit message：** `step-0: freeze skill_v0_baseline and baseline reports`

**验证输出摘要：**

```
python run.py --cases testcases/pdf_cases/byd_real_las_fixture.yaml --backend fixture --pipeline
  -> status=success weighted_score=8.8 level=good (gt skipped)
pytest tests/test_09_pipeline_fixture.py tests/test_10_scoring_model.py -q -m offline
  -> 16 passed
```

## step-1 (2026-05-30T18:51:00+08:00)

add score_sources to score_result.json

**变更文件：**

- `framework/scoring_model.py`：`compute()` 返回值追加 `score_sources`（`deterministic` 列出全部确定性维度，`llm_judge` 默认 `[]`）。未改动 `dimensions` 嵌套结构、权重公式或 `weighted_score`。
- `tests/test_10_scoring_model.py`：新增 `test_compute_emits_score_sources` 断言 `score_sources` 存在且 deterministic 与 dimensions key 一致。

**建议 commit message：** `step-1: add score_sources to score_result.json`

**验证输出摘要：**

```
python run.py --cases testcases/pdf_cases/byd_real_las_fixture.yaml --backend fixture --pipeline
  -> score_result.json 含 score_sources，weighted_score 仍为 8.8（无 LLM 调用）
pytest tests/test_10_scoring_model.py tests/test_09_pipeline_fixture.py -q -m offline
  -> 17 passed
```

## step-2 (2026-05-30T18:56:00+08:00)

add offline-capable LLM judge layer

**变更文件：**

- `configs/judge.yaml`（新增，默认 `enabled: false`，`mode: mock`）
- `judge/__init__.py`（新增，使 judge 可作为包导入）
- `judge/assessment_skill.md`、`judge/judge_prompt_template.md`、`judge/judge_result_schema.json`（新增静态文件）
- `judge/llm_judge.py`（新增，mock/live/skip 三模式 + 行为矩阵，含降级逻辑）
- `judge/fixtures/byd_caibao_judge_mock.json`（新增 offline mock 输出）
- `framework/pipeline.py`：在 `compute_score` 之后新增可选 stage `run_judge`（`enabled=false` 时 skipped、不写文件、不调用 API；`enabled=true` 时把 judge 维度追加进 `score_sources.llm_judge`，**不重算** weighted_score）
- `framework/report_collector.py`：`summarize_case` 读取 `judge_result.json`；新增「Judge 辅助评分（不参与总分）」小节，接入 score_summary 与 final report
- `tests/test_12_judge_offline.py`（新增，`pytestmark = pytest.mark.offline`）

**建议 commit message：** `step-2: add offline-capable LLM judge layer`

**验证输出摘要：**

```
python run.py --cases ... --pipeline   (默认 judge.enabled=false)
  -> stages 含 run_judge=skipped；fixture 目录无 judge_result.json；weighted_score=8.8
pytest tests/test_12_judge_offline.py -q -m offline
  -> 6 passed（disabled 不写文件 / mock 写 judge_result / skip / live 无 Key 降级 /
     pipeline enabled=true 追加 score_sources.llm_judge 且 weighted_score 不变）
python run.py --generate-report  -> ok（Judge 未启用时显示「Judge 未启用」）
```

## step-3 (2026-05-30T18:58:00+08:00)

add failure_trace for SkillOpt handoff

**变更文件：**

- `optimizer/__init__.py`（新增，使 optimizer 可作为包导入）
- `optimizer/failure_trace.py`（新增，collect + analyze 合一：读 score_result /
  judge_result / gt_eval_result / assertions，产出 `reports/traces/<case_id>_failure_trace.json`；
  judge.enabled=false 时 `judge_failures=[]`）
- `run.py`：`cmd_pipeline` 在每个 case pipeline 完成后调用 `failure_trace.run_for_case` 落盘 trace
- `tests/test_13_failure_trace.py`（新增，`pytestmark = pytest.mark.offline`）

**未创建任何 SkillOpt / patch / gate / skill_version_manager 文件。**

**建议 commit message：** `step-3: add failure_trace for SkillOpt handoff`

**验证输出摘要：**

```
python run.py --cases ... --pipeline
  -> 生成 reports/traces/byd_real_las_fixture_failure_trace.json
     （baseline 全通过，failed_dimensions / deterministic_failures / judge_failures 均为 []）
pytest tests/test_13_failure_trace.py -q -m offline   -> 4 passed
pytest tests/test_09 tests/test_10 tests/test_12 tests/test_13 -q -m offline -> 27 passed
pytest -q -m offline (全量回归)  -> 70 passed, 21 deselected
```
