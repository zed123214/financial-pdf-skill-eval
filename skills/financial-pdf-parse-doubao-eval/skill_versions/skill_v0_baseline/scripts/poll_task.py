from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


OPERATOR_ID = "las_pdf_parse_doubao"
TERMINAL = {"COMPLETED", "FAILED", "TIMEOUT", "CANCELED"}


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def error(output_dir: Path, code: str, msg: str, retryable: bool = True, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    data = {"status": "failed", "error_code": code, "message": msg, "retryable": retryable}
    if extra:
        data.update(extra)
    write_json(output_dir / "meta" / "error_result.json", data)
    return data


def run(command: list[str], timeout: int) -> tuple[int, str, str]:
    p = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, env=os.environ.copy())
    return p.returncode, p.stdout, p.stderr


def extract_result_files(output_dir: Path, result: dict[str, Any]) -> None:
    raw = output_dir / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    data = result.get("data", {}) if isinstance(result, dict) else {}
    (raw / "parsed.md").write_text(str(data.get("markdown") or ""), encoding="utf-8")
    write_json(raw / "pages_detail.json", data.get("detail") if data.get("detail") is not None else [])


def poll(task_id: str, output_dir: Path, max_seconds: int, interval_seconds: int = 5, legacy_task_id_file: bool = False) -> dict[str, Any]:
    if not os.getenv("LAS_API_KEY"):
        return error(output_dir, "AUTH_MISSING", "LAS_API_KEY is not configured.")
    (output_dir / "raw").mkdir(parents=True, exist_ok=True)
    (output_dir / "meta").mkdir(parents=True, exist_ok=True)
    if legacy_task_id_file:
        # Deprecated compatibility artifact. Prefer run_meta.json.task_id.
        (output_dir / "meta" / "task_id.txt").write_text(task_id, encoding="utf-8")
    started = time.monotonic()
    attempts = 0
    while time.monotonic() - started <= max_seconds:
        attempts += 1
        code, stdout, stderr = run(["lasutil", "poll", OPERATOR_ID, task_id], min(max_seconds, 120))
        if code != 0:
            return error(output_dir, "TASK_FAILED", "lasutil poll failed.", True, {"stdout": stdout, "stderr": stderr, "task_id": task_id})
        try:
            result = json.loads(stdout)
        except json.JSONDecodeError:
            return error(output_dir, "OUTPUT_SCHEMA_INVALID", "lasutil poll returned non-JSON output.", True, {"stdout": stdout[:1000], "stderr": stderr})
        write_json(output_dir / "raw" / "last_poll.json", result)
        meta = result.get("metadata", {})
        status = str(meta.get("task_status", "")).upper()
        bc = meta.get("business_code", 0)
        if bc not in {0, "0", None}:
            write_json(output_dir / "raw" / "result.json", result)
            return error(output_dir, "TASK_FAILED", f"LAS business_code is {bc}.", True, {"task_id": task_id})
        if status == "COMPLETED":
            write_json(output_dir / "raw" / "result.json", result)
            extract_result_files(output_dir, result)
            return {"status": "success", "task_id": task_id, "task_status": status, "attempts": attempts}
        if status in TERMINAL:
            write_json(output_dir / "raw" / "result.json", result)
            return error(output_dir, "TASK_FAILED", f"LAS task ended with status {status}.", True, {"task_id": task_id})
        time.sleep(max(1, interval_seconds))
    return {"status": "pending", "error_code": "TASK_TIMEOUT", "message": "Short polling reached max_seconds. Poll later with task_id.", "task_id": task_id, "output_dir": str(output_dir)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--max-seconds", type=int, default=60)
    parser.add_argument("--interval-seconds", type=int, default=5)
    parser.add_argument("--legacy-task-id-file", action="store_true", help="Deprecated: also write meta/task_id.txt for old workflows.")
    args = parser.parse_args()
    try:
        result = poll(args.task_id, args.output_dir, args.max_seconds, args.interval_seconds, args.legacy_task_id_file)
        print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stdout if result.get("status") in {"success", "pending"} else sys.stderr)
        return 0 if result.get("status") in {"success", "pending"} else 1
    except subprocess.TimeoutExpired as exc:
        result = error(args.output_dir, "TASK_TIMEOUT", str(exc), True, {"task_id": args.task_id})
        print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
