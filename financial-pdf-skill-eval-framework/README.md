# financial-pdf-skill-eval-framework

External automation evaluation framework for the OpenClaw Skill
**financial-pdf-parse-doubao-eval**.

The Skill is the **system under test**, not part of this framework. This
framework owns the test samples, YAML cases, Ground Truth, pytest layers,
optional Allure attachments, and aggregated Markdown reports.

## Why is this framework separate from the Skill?

The Skill is shipped as a self-contained OpenClaw plugin and must remain
independent of any specific test project. Real PDFs, human Ground Truth,
pytest cases, and Allure reports are evaluation-project assets — they live
here.

## Skill contract

The framework consumes the Skill via the **standard** output profile, which is
the only stable automation interface. `debug` is for troubleshooting only;
`minimal` is for display only.

Required files per case (under `outputs/<case_id>/`):

- `raw/parsed.md`
- `normalized/normalized_tables.json`
- `normalized/financial_summary.json`
- `evaluation/quality_checks.json`
- `meta/run_meta.json`

`evaluation/evaluation_report.md` is also produced by the standard profile.
`evaluation/gt_eval_result.json` is produced when human Ground Truth exists.

## What `data/real_las_outputs/` is — and is not

- It contains **real_las** Skill outputs that came back from OpenClaw + LAS.
- They are valid fixtures for output-contract, structure, and authenticity tests.
- They are **NOT** Ground Truth. `financial_summary.json` is the Skill's
  extraction; it cannot be used as the answer key.
- Accuracy can only be computed when an actual human Ground Truth file exists
  under `evaluation/ground_truth/` with non-empty `expected` values.

## Quickstart (Windows PowerShell)

```powershell
cd financial-pdf-skill-eval-framework

python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

# Import the OpenClaw + real_las outputs that already exist next to the framework
python run.py --import-real-outputs ..\outputs

# Run all offline tests (no real LAS calls, no money spent)
pytest -q
pytest -m smoke
pytest -m offline
pytest -m abnormal

# Generate Markdown reports
python run.py --summary
python run.py --fixture-summary
python run.py --collect-openclaw-evidence
python run.py --generate-final-report
```

Linux / macOS / Git Bash:

```bash
cd financial-pdf-skill-eval-framework
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py --import-real-outputs ../outputs
pytest -q
```

## `real_las` — disabled by default

Calling LAS costs money. The framework refuses to call it unless **both**:

- `LAS_API_KEY` is set
- `ALLOW_REAL_LAS=1`

Without those, `real_las` cases are **skipped**, never failed.

```powershell
$env:LAS_API_KEY="..."
$env:LAS_REGION="cn-beijing"
$env:ALLOW_REAL_LAS="1"
pytest -m real_las
```

## `real_openclaw` — unverified

The Skill declares a `real_openclaw` backend, but this submission has not
verified it end-to-end. Cases targeting `real_openclaw` are skipped by default
until verified. The OpenClaw evidence log (`reports/markdown/openclaw_invocation_log.md`)
states this explicitly.

## Adding a new sample

1. Drop the PDF under `data/samples/`.
2. Add a YAML case under `testcases/pdf_cases/`.
3. Create a Ground Truth template under `evaluation/ground_truth/<case>_manual_gt.json`.
4. Fill `expected` values **by hand** — do NOT copy from `financial_summary.json`.

## Adding Ground Truth

`evaluation/ground_truth/<case>_manual_gt.json`:

```json
{
  "case_id": "case",
  "source": "manual",
  "metrics": [
    {"statement": "合并资产负债表", "item": "资产总计", "period": "2025-12-31", "expected": "100,000,000.00", "page": 1, "evidence": "manual"}
  ]
}
```

- The GT file's top-level `source` field **must** be `manual` or
  `human_verified`. Any other value (`todo_manual_verify`, `template`,
  `harness_only`, `synthetic`, …) is rejected by `gt_evaluator` and treated as
  `no_ground_truth`. This guards against accidentally publishing harness-only
  accuracy.
- Empty `expected` rows are ignored in accuracy and counted as
  `pending_manual_verify_count`.
- Once at least one `expected` is filled **and** `source` is human-verified,
  accuracy is reported.

### Two distinct counters

- `count_as_real_execution` — a `real_las` / `real_openclaw` Skill output was
  actually produced. A fixture without GT can still count.
- `count_as_accuracy_evaluation` — the case has a human-verified Ground Truth
  filled in. Only these cases contribute to `numeric_accuracy` /
  `exact_match_accuracy`.

The two counters are reported separately in
`reports/markdown/evaluation_summary.md` and
`reports/final/final_project_report.md`.

## Reports

- `reports/markdown/evaluation_summary.md` — main run summary (4 sections).
- `reports/markdown/failure_cases.md` — every case that failed at least one validation.
- `reports/markdown/fixture_summary.md` — quick stats for imported fixtures.
- `reports/markdown/openclaw_invocation_log.md` — OpenClaw evidence + disclaimer.
- `reports/final/final_project_report.md` — composite report for project submission.
- `reports/allure-results/`, `reports/allure-html/` — optional Allure outputs
  (only when `allure-pytest` is installed and `allure` CLI is on PATH).

## Open items

- `real_openclaw` backend: not verified.
- Manual Ground Truth: only templates exist; values must be filled in by hand.
- Sample set should grow to 20–30 representative cases (normal / complex /
  adversarial / abnormal).
- Cases without Ground Truth can only be evaluated for output contract,
  structure stats, and authenticity — not accuracy.
