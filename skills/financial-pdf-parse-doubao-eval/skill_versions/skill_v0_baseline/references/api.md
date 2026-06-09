# API Reference

## Operator

- Operator ID: `las_pdf_parse_doubao`
- Workflow: `lasutil file-upload -> lasutil submit -> lasutil poll`
- Required env for direct LAS: `LAS_API_KEY`
- Recommended env: `LAS_REGION=cn-beijing`

## Submit Data

```json
{
  "url": "https://example.com/report.pdf",
  "parse_mode": "detail",
  "start_page": 1,
  "num_pages": 10
}
```

Run:

```bash
lasutil submit las_pdf_parse_doubao '<data_json>'
```

Save submit response to `raw/submit.json`; save `metadata.task_id` or nested `task_id` to `meta/task_id.txt`.

## Poll

```bash
lasutil poll las_pdf_parse_doubao <task_id>
```

Expected result:

```json
{
  "metadata": {
    "task_status": "COMPLETED",
    "business_code": 0
  },
  "data": {
    "markdown": "...",
    "detail": []
  }
}
```

Extract `data.markdown` to `raw/parsed.md` and `data.detail` to `raw/pages_detail.json`.

## Error Codes

| Error Code | Trigger | User Message | Suggested Fix | Retry |
|---|---|---|---|---|
| `FILE_NOT_FOUND` | Input missing | Input PDF was not found. | Check path. | Yes |
| `INVALID_FILE_TYPE` | Not PDF | Only PDF input is supported. | Use PDF. | No |
| `AUTH_MISSING` | Missing `LAS_API_KEY` | LAS_API_KEY is not configured. | Export env var. | Yes |
| `AUTH_INVALID` | Invalid key | Authentication failed. | Verify key. | Yes |
| `REGION_MISMATCH` | Region mismatch | Region mismatch. | Set matching `LAS_REGION`. | Yes |
| `URL_NOT_ACCESSIBLE` | URL expired/unavailable | LAS cannot access PDF URL. | Re-upload. | Yes |
| `TASK_ID_MISSING` | No task id | Submit did not return task id. | Inspect submit JSON. | Yes |
| `TASK_TIMEOUT` | Short poll timeout | Task still running. | Poll later. | Yes |
| `SERVER_BUSY` | Rate limited | Service busy. | Reduce concurrency. | Yes |
| `TASK_FAILED` | LAS task failed | Task failed. | Inspect error_result. | Depends |
| `OUTPUT_SCHEMA_INVALID` | Bad JSON/schema | Output schema invalid. | Inspect raw output. | Yes |
| `OUTPUT_INCOMPLETE` | Missing files | Output incomplete. | Re-run poll/postprocess. | Yes |
| `NO_MARKDOWN_OUTPUT` | Empty markdown | No Markdown output. | Try detail mode. | Yes |
| `NO_TABLE_DETECTED` | No table | No table detected. | Try detail mode. | Yes |
| `POSTPROCESS_FAILED` | Exception | Postprocess failed. | Inspect error_result. | Yes |
| `PRICE_CONFIRMATION_REQUIRED` | No cost confirmation | Confirmation required. | Confirm or pass `--yes`. | Yes |
| `OPENCLAW_NOT_CONFIGURED` | OpenClaw env missing | OpenClaw not configured. | Set endpoint/key. | Yes |
| `REAL_MODE_NOT_IMPLEMENTED` | Unsupported backend | Backend not implemented. | Use `real_las`. | No |

## Authenticity

- `real_las`: direct `lasutil`.
- `real_openclaw`: real OpenClaw orchestration.
- `official_output_mock`: offline reuse of official output.
- `fallback_synthetic_mock`: framework self-check only; must not count as real evaluation.
