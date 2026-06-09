# Acceptance Checklist

This list reflects the **actual** state of the framework, not aspirational
intent. Sections are split into completed / partially complete / blocked /
future. real_openclaw is NOT marked complete.

## Completed

- [x] Framework lives under `financial-pdf-skill-eval-framework/`, separate from the Skill.
- [x] Skill is unmodified.
- [x] `python run.py --help` exits 0.
- [x] `python run.py --import-real-outputs ../outputs` populated `data/real_las_outputs/{byd_caibao, 华电光大}` and wrote `configs/dataset_manifest.yaml`.
- [x] `pytest -q` passes locally without LAS credentials (49 tests).
- [x] `pytest -m smoke` selects at least one test and passes.
- [x] `pytest -m offline` runs only no-cost checks and passes.
- [x] `pytest -m abnormal` covers FILE_NOT_FOUND / INVALID_FILE_TYPE / NO_GROUND_TRUTH / AUTH_MISSING.
- [x] `pytest -m real_las` is skipped when `LAS_API_KEY` / `ALLOW_REAL_LAS=1` are absent.
- [x] Framework consumes only the `standard` output profile.
- [x] `validate_outputs.py` is delegated for contract checks; local fallback only if the script is missing.
- [x] `evaluate_with_ground_truth.py` is delegated for accuracy; framework refuses to compute when GT `source` is not `manual` / `human_verified`.
- [x] Reports state explicitly: output completeness ≠ accuracy; outputs fixtures ≠ Ground Truth; harness GT does not contribute to accuracy; real_las costs money; real_openclaw unverified.
- [x] Summary distinguishes `count_as_real_execution` from `count_as_accuracy_evaluation`.
- [x] `python run.py --collect-openclaw-evidence` writes the log even when the `openclaw` CLI is unavailable, and appends the `real_las != real_openclaw` disclaimer.
- [x] Stale harness-only `gt_eval_result.json` removed from BYD fixture; test that produced it now operates in tmp_path and asserts no fixture pollution.

## Partially complete

- [~] Ground Truth: only **templates** exist under `evaluation/ground_truth/`. `byd_manual_gt.json` has anchor rows but every `expected` is empty (`source: todo_manual_verify`). No accuracy can be reported until a human fills these.
- [~] Sample set: 2 real_las fixtures + 4 abnormal cases. Target is 20–30. Growth plan is in [docs/dataset_plan.md](dataset_plan.md).
- [~] `smoke_skill_standard.yaml` and `real_las_smoke.yaml` are wired but not exercised in CI because `data/samples/sample.pdf` is not shipped.

## Blocked / not verified

- [ ] **`real_openclaw` backend end-to-end.** No verified OpenClaw orchestration. All `real_openclaw` paths skip with a clear reason. Marking this complete would be dishonest.
- [ ] **Manual Ground Truth.** Cannot be auto-generated and is not present. Until then `accuracy-evaluation samples = 0`.
- [ ] **`real_las` paid run.** Default-off. Only the user can opt in (`LAS_API_KEY` + `ALLOW_REAL_LAS=1`).

## Future work

- [ ] Fill `evaluation/ground_truth/byd_manual_gt.json` with human-verified values; flip `source` to `manual`.
- [ ] Grow the sample set toward 20–30 cases (normal / complex / adversarial / abnormal).
- [ ] Verify `real_openclaw` end-to-end and remove the skip gates.
- [ ] Allure HTML report when the `allure` CLI is on PATH.
- [ ] Add `pioneer` and other case GTs once their PDFs are added under `data/samples/`.

## Definitions

- **count_as_real_execution** — A real_las or real_openclaw output was actually produced by the Skill. Independent of accuracy.
- **count_as_accuracy_evaluation** — A case has a human-verified Ground Truth (`source: manual` / `human_verified`) AND the case's YAML does not opt out (e.g. 华电光大 has `count_as_real_evaluation: false`).
- A case can have `count_as_real_execution=True` and `count_as_accuracy_evaluation=False`. The BYD fixture is exactly that today.
