# Dataset Plan

Target: 20–30 representative cases across four bands.

## Bands

| Band | Description | Target count |
|---|---|---|
| Normal | Clean digital balance sheet / income statement / cash flow | 8–10 |
| Complex | Cross-page, borderless, dense numeric, multi-column reading | 6–8 |
| Adversarial | Scanned, stamped, watermarked, footers, signatures | 4–6 |
| Abnormal | Missing file, wrong type, missing GT, missing LAS key | 4 (covered by `abnormal_cases.yaml`) |

## Current state

| case_id | band | source | has GT |
|---|---|---|---|
| byd_caibao | Normal (BYD interim balance sheet) | real_las fixture | template only |
| 华电光大 | Adversarial (non-standard 业绩报表) | real_las fixture | n/a (no metrics) |
| pioneer | placeholder | not yet added | template only |

## Next steps

1. Add 6 more clean financial PDFs as `data/samples/*.pdf` and matching YAML
   single-case files.
2. For each, write a manual GT file with 5–10 expected anchor metrics.
3. Run `pytest -m core` once GT is in place.
4. Promote `regression` once accuracy stabilises above 0.80.
