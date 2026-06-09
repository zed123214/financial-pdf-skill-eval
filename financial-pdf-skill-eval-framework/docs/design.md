# Design

## Roles

- **Skill** (`skills/financial-pdf-parse-doubao-eval`): system under test.
  Calls LAS, produces `standard`/`debug`/`minimal` profile outputs, exposes
  helper scripts (validate, gt-eval, evidence, final-report).
- **Framework** (this project): drives the Skill, validates the standard
  output profile, optionally runs Ground Truth comparison, aggregates reports.

## Modules

```
framework/
  context.py            paths + FrameworkConfig (loaded from configs/config.example.yaml)
  bootstrap.py          adds FRAMEWORK_ROOT to sys.path
  logger.py             single stdout logger
  case_loader.py        YAML loading (single, dir, abnormal-multi)
  skill_invoker.py      backend dispatch (fixture / official_output_mock / real_las / real_openclaw)
  output_contract.py    delegate to Skill validate_outputs.py, fall back to local file checks
  gt_evaluator.py       delegate to Skill evaluate_with_ground_truth.py
  assertion_engine.py   uniform validation runner
  report_collector.py   summary / failure / final-report markdown
  allure_helper.py      no-op if allure-pytest is missing
evaluation/
  ground_truth/         templates + manual GT files (mostly empty until filled by hand)
  metrics.py            tiny helpers
  summary_report.py     re-exports from report_collector for ergonomics
testcases/pdf_cases/    YAML driven cases
tests/                  pytest layers
data/                   samples / mocks / fixtures / abnormal inputs
reports/                generated markdown + allure
```

## Backends

| backend | When | Side effects |
|---|---|---|
| `fixture` | Pre-existing real_las output dir under `data/real_las_outputs/<case>/` | None |
| `official_output_mock` | Skill is run with `--backend official_output_mock --mock-dir <dir>` | Local Skill subprocess |
| `real_las` | LAS_API_KEY + ALLOW_REAL_LAS=1 | **Costs money** |
| `real_openclaw` | Unverified | Skipped by default |

## Validation types (assertion_engine)

`output_contract`, `data_authenticity`, `table_stat_ge`/`_eq`,
`metric_stat_ge`/`_eq`, `gt_exact_match_accuracy_ge`,
`gt_numeric_accuracy_ge`, `backend_eq`, `error_type_eq`, `file_exists`,
`text_contains`, `no_ground_truth_allowed`.

Each returns `{type, passed, message, expected, actual}`.

## Where reports come from

- `evaluation_summary.md` — `report_collector.write_summary_markdown` over the
  manifest summaries.
- `failure_cases.md` — same source, filtered to failed validations.
- `final_project_report.md` — composes our summary with the Skill's own
  `generate_final_project_report.py` output (if it produces one).

## Why we delegate to the Skill's helper scripts

`validate_outputs.py` and `evaluate_with_ground_truth.py` are the **authoritative**
implementations of the contract and of the accuracy metric. Re-implementing them
in the framework would create drift. The framework calls them as subprocesses;
local fallbacks exist only for `validate_outputs.py` so that import-time tests
still work if the Skill script is temporarily unavailable.
