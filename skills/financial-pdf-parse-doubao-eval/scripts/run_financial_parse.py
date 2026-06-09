from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from estimate_price import count_pdf_pages, estimate  # noqa: E402
from generate_result_md import generate as generate_report  # noqa: E402
from poll_task import extract_result_files  # noqa: E402
from postprocess_financial import postprocess  # noqa: E402


SKILL_NAME = "financial-pdf-parse-doubao-eval"
SKILL_VERSION = "0.3.0"
BASE_SKILL = "byted-las-pdf-parse-doubao"
OPERATOR_ID = "las_pdf_parse_doubao"
TERMINAL = {"COMPLETED", "FAILED", "TIMEOUT", "CANCELED"}


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8", errors="ignore"))


def make_dirs(output_dir: Path) -> None:
    for name in ("raw", "normalized", "evaluation", "meta"):
        (output_dir / name).mkdir(parents=True, exist_ok=True)


def error(output_dir: Path, code: str, msg: str, retryable: bool, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    data = {"status": "failed", "error_code": code, "message": msg, "retryable": retryable}
    if extra:
        data.update(extra)
    write_json(output_dir / "meta" / "error_result.json", data)
    return data


def run_meta(backend: str, source: str, parse_mode: str, task_id: str, input_file: str, page_count: int, estimated_price: float, confirmed: bool, status: str, is_synthetic: bool = False, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    meta = {
        "skill_name": SKILL_NAME,
        "skill_version": SKILL_VERSION,
        "base_skill": BASE_SKILL,
        "operator_id": OPERATOR_ID,
        "execution_backend": backend,
        "parse_mode": parse_mode,
        "task_id": task_id,
        "input_file": input_file,
        "page_count": page_count,
        "estimated_price": estimated_price,
        "user_confirmed_cost": confirmed,
        "output_source": source,
        "is_synthetic": is_synthetic,
        "count_as_real_evaluation": (not is_synthetic and backend in {"real_openclaw", "real_las"}),
        "status": status,
    }
    if extra:
        meta.update(extra)
    return meta


def validate_input(path: Path, output_dir: Path) -> bool:
    if not path.exists():
        error(output_dir, "FILE_NOT_FOUND", f"Input file not found: {path}", True)
        return False
    if path.suffix.lower() != ".pdf":
        error(output_dir, "INVALID_FILE_TYPE", "Only PDF input is supported.", False)
        return False
    return True


def has_text_layer(path: Path) -> bool:
    for package in ("pypdf", "PyPDF2"):
        try:
            mod = __import__(package, fromlist=["PdfReader"])
            reader = mod.PdfReader(str(path))
            text = "\n".join((p.extract_text() or "") for p in reader.pages[:3])
            return len(text.strip()) >= 80
        except Exception:
            pass
    data = path.read_bytes()[:2_000_000]
    return len(re.findall(rb"\b(?:Tj|TJ|BT|ET)\b", data)) > len(re.findall(rb"/(?:Image|Subtype\s*/Image)\b", data))


def resolve_mode(path: Path, mode: str) -> tuple[str, str]:
    if mode in {"normal", "detail"}:
        return mode, "explicit"
    name = path.name.lower()
    if any(k in name for k in ["scan", "扫描", "扫码", "财报", "复杂表格", "跨页表格"]):
        return "detail", "auto: filename indicates scanned/financial report"
    if not has_text_layer(path):
        return "detail", "auto: no reliable text layer detected"
    return "normal", "auto: text layer detected"


def billed_pages(total: int, start: int | None, count: int | None) -> int:
    start = start or 1
    if total <= 0 or start > total:
        return 0
    available = total - start + 1
    return max(0, min(count if count is not None else available, available))


def confirm(price: dict[str, Any], yes: bool, output_dir: Path, backend: str) -> bool:
    if backend == "official_output_mock":
        return False
    if yes:
        return True
    print(json.dumps(price, ensure_ascii=False, indent=2))
    try:
        answer = input("Continue with real LAS call? Type 'yes': ").strip().lower()
    except EOFError:
        error(output_dir, "PRICE_CONFIRMATION_REQUIRED", "Cost confirmation is required before real LAS calls.", True)
        return False
    if answer not in {"yes", "y", "继续", "确认"}:
        error(output_dir, "PRICE_CONFIRMATION_REQUIRED", "Cost confirmation is required before real LAS calls.", True)
        return False
    return True


def cmd(command: list[str], timeout: int) -> tuple[int, str, str]:
    p = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, env=os.environ.copy())
    return p.returncode, p.stdout, p.stderr


def first(data: Any, keys: set[str]) -> Any:
    if isinstance(data, dict):
        for k, v in data.items():
            if k in keys and v:
                return v
        for v in data.values():
            found = first(v, keys)
            if found:
                return found
    if isinstance(data, list):
        for item in data:
            found = first(item, keys)
            if found:
                return found
    return None


def upload(path: Path, output_dir: Path) -> str | None:
    code, stdout, stderr = cmd(["lasutil", "file-upload", str(path)], 300)
    if code != 0:
        error(output_dir, "URL_NOT_ACCESSIBLE", "lasutil file-upload failed.", True, {"stdout": stdout, "stderr": stderr})
        return None
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        error(output_dir, "OUTPUT_SCHEMA_INVALID", "file-upload returned non-JSON.", True, {"stdout": stdout[:1000], "stderr": stderr})
        return None
    write_json(output_dir / "raw" / "upload.json", data)
    url = first(data, {"presigned_url", "url", "file_url"})
    if not isinstance(url, str) or not url:
        error(output_dir, "URL_NOT_ACCESSIBLE", "Upload returned no URL.", True, {"upload_result": data})
        return None
    return url


def write_legacy_task_id_file(output_dir: Path, task_id: str) -> None:
    # Deprecated compatibility artifact. Prefer meta/run_meta.json.task_id.
    (output_dir / "meta" / "task_id.txt").write_text(task_id, encoding="utf-8")


def submit(url: str, mode: str, output_dir: Path, start: int | None, count: int | None, legacy_task_id_file: bool = False) -> str | None:
    payload: dict[str, Any] = {"url": url, "parse_mode": mode}
    if start is not None:
        payload["start_page"] = start
    if count is not None:
        payload["num_pages"] = count
    code, stdout, stderr = cmd(["lasutil", "submit", OPERATOR_ID, json.dumps(payload, ensure_ascii=False)], 300)
    if code != 0:
        error(output_dir, "TASK_FAILED", "lasutil submit failed.", True, {"stdout": stdout, "stderr": stderr, "data": payload})
        return None
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        error(output_dir, "OUTPUT_SCHEMA_INVALID", "submit returned non-JSON.", True, {"stdout": stdout[:1000], "stderr": stderr})
        return None
    write_json(output_dir / "raw" / "submit.json", data)
    task_id = first(data, {"task_id"})
    if not isinstance(task_id, str) or not task_id:
        error(output_dir, "TASK_ID_MISSING", "submit did not return task_id.", True, {"submit": data})
        return None
    if legacy_task_id_file:
        write_legacy_task_id_file(output_dir, task_id)
    return task_id


def short_poll(task_id: str, output_dir: Path, max_seconds: int) -> dict[str, Any]:
    started = time.monotonic()
    while time.monotonic() - started <= max_seconds:
        code, stdout, stderr = cmd(["lasutil", "poll", OPERATOR_ID, task_id], min(max_seconds, 120))
        if code != 0:
            return error(output_dir, "TASK_FAILED", "lasutil poll failed.", True, {"stdout": stdout, "stderr": stderr, "task_id": task_id})
        try:
            result = json.loads(stdout)
        except json.JSONDecodeError:
            return error(output_dir, "OUTPUT_SCHEMA_INVALID", "poll returned non-JSON.", True, {"stdout": stdout[:1000], "stderr": stderr})
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
            return {"status": "success", "task_id": task_id, "task_status": status}
        if status in TERMINAL:
            write_json(output_dir / "raw" / "result.json", result)
            return error(output_dir, "TASK_FAILED", f"LAS task ended with status {status}.", True, {"task_id": task_id})
        time.sleep(5)
    return {"status": "pending", "task_id": task_id, "message": "Short polling timed out; poll later with task_id."}


def mock_candidates(input_path: Path, output_dir: Path, mock_dir: Path | None) -> list[Path]:
    if mock_dir:
        return [mock_dir]
    return []


def official_mock(input_path: Path, output_dir: Path, mock_dir: Path | None, legacy_task_id_file: bool = False) -> tuple[bool, str]:
    chosen = None
    for c in mock_candidates(input_path, output_dir, mock_dir):
        if all((c / n).exists() for n in ("result.json", "parsed.md", "pages_detail.json")):
            chosen = c
            break
    if chosen is None:
        error(output_dir, "OUTPUT_INCOMPLETE", "No official output mock directory was found. Pass --mock-dir with result.json, parsed.md, and pages_detail.json when using official_output_mock.", True)
        return False, ""
    raw = output_dir / "raw"
    shutil.copy2(chosen / "result.json", raw / "result.json")
    shutil.copy2(chosen / "parsed.md", raw / "parsed.md")
    shutil.copy2(chosen / "pages_detail.json", raw / "pages_detail.json")
    write_json(raw / "submit.json", {"backend": "official_output_mock", "source_dir": str(chosen)})
    task_id = f"official_output_mock_{chosen.name}"
    if legacy_task_id_file:
        write_legacy_task_id_file(output_dir, task_id)
    return True, task_id


def update_meta_from_outputs(output_dir: Path, output_profile: str, keep_pages_detail: bool) -> None:
    meta_path = output_dir / "meta" / "run_meta.json"
    meta = read_json(meta_path, {})
    quality = read_json(output_dir / "evaluation" / "quality_checks.json", {})
    table_stats = quality.get("table_statistics", {})
    metric_stats = quality.get("metric_statistics", {})
    meta["output_profile"] = output_profile
    meta["keep_pages_detail"] = keep_pages_detail
    meta.update(table_stats)
    meta.update(metric_stats)
    write_json(meta_path, meta)

    if quality:
        quality["data_authenticity"] = {
            "execution_backend": meta.get("execution_backend", "unknown"),
            "output_source": meta.get("output_source", "unknown"),
            "is_synthetic": bool(meta.get("is_synthetic", False)),
            "count_as_real_evaluation": bool(meta.get("count_as_real_evaluation", False)),
        }
        write_json(output_dir / "evaluation" / "quality_checks.json", quality)


def remove_known_file(path: Path) -> None:
    if path.exists() and path.is_file():
        path.unlink()


def remove_empty_dirs(output_dir: Path) -> None:
    for relative in ("raw", "normalized", "evaluation", "meta"):
        path = output_dir / relative
        if path.exists() and path.is_dir():
            try:
                path.rmdir()
            except OSError:
                pass


def apply_output_profile(output_dir: Path, output_profile: str, keep_pages_detail: bool, legacy_task_id_file: bool = False) -> None:
    if output_profile == "debug":
        (output_dir / "raw" / "raw_stdout.log").touch(exist_ok=True)
        (output_dir / "raw" / "raw_stderr.log").touch(exist_ok=True)
        if not legacy_task_id_file:
            remove_known_file(output_dir / "meta" / "task_id.txt")
        return

    if output_profile == "minimal":
        for source, target in (
            (output_dir / "raw" / "parsed.md", output_dir / "parsed.md"),
            (output_dir / "normalized" / "financial_summary.json", output_dir / "financial_summary.json"),
            (output_dir / "meta" / "run_meta.json", output_dir / "run_meta.json"),
        ):
            if source.exists():
                shutil.copy2(source, target)
        for relative in (
            "raw/submit.json",
            "raw/upload.json",
            "raw/result.json",
            "raw/last_poll.json",
            "raw/parsed.md",
            "raw/pages_detail.json",
            "raw/raw_stdout.log",
            "raw/raw_stderr.log",
            "normalized/cleaned.md",
            "normalized/normalized_tables.json",
            "normalized/financial_summary.json",
            "evaluation/quality_checks.json",
            "evaluation/gt_eval_result.json",
            "meta/task_id.txt",
            "meta/run_meta.json",
        ):
            remove_known_file(output_dir / relative)
        remove_empty_dirs(output_dir)
        return

    for relative in (
        "raw/submit.json",
        "raw/upload.json",
        "raw/result.json",
        "raw/last_poll.json",
        "raw/raw_stdout.log",
        "raw/raw_stderr.log",
        "normalized/cleaned.md",
        "meta/task_id.txt",
    ):
        remove_known_file(output_dir / relative)
    if not keep_pages_detail:
        remove_known_file(output_dir / "raw" / "pages_detail.json")


def postprocess_report(output_dir: Path, output_profile: str, keep_pages_detail: bool, legacy_task_id_file: bool = False) -> bool:
    try:
        postprocess(output_dir / "raw" / "parsed.md", output_dir / "raw" / "pages_detail.json", output_dir, output_dir / "raw" / "result.json")
        update_meta_from_outputs(output_dir, output_profile, keep_pages_detail)
        apply_output_profile(output_dir, output_profile, keep_pages_detail, legacy_task_id_file)
        generate_report(output_dir)
        return True
    except Exception as exc:
        error(output_dir, "POSTPROCESS_FAILED", str(exc), True)
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--parse-mode", required=True, choices=["normal", "detail", "auto"])
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/financial_skill_demo"))
    parser.add_argument("--start-page", type=int)
    parser.add_argument("--num-pages", type=int)
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--short-poll-seconds", type=int, default=60)
    parser.add_argument("--backend", choices=["real_las", "real_openclaw", "official_output_mock"], default="real_las")
    parser.add_argument("--mock-dir", type=Path)
    parser.add_argument("--output-profile", choices=["minimal", "standard", "debug"], default="standard")
    parser.add_argument("--keep-pages-detail", action="store_true")
    parser.add_argument("--legacy-task-id-file", action="store_true", help="Deprecated: also write meta/task_id.txt for old debug workflows. Prefer run_meta.json.task_id.")
    args = parser.parse_args()

    make_dirs(args.output_dir)
    if not validate_input(args.input, args.output_dir):
        return 1
    try:
        total_pages = count_pdf_pages(args.input)
    except Exception as exc:
        error(args.output_dir, "OUTPUT_SCHEMA_INVALID", f"Unable to read PDF page count: {exc}", True)
        return 1
    mode, reason = resolve_mode(args.input, args.parse_mode)
    pages = billed_pages(total_pages, args.start_page, args.num_pages)
    price = estimate(str(args.input), mode, pages, SKILL_ROOT / "references" / "prices.md")
    est = float(price["estimated_price"])

    if args.backend == "real_openclaw":
        code = "OPENCLAW_NOT_CONFIGURED" if not (os.getenv("OPENCLAW_BASE_URL") and os.getenv("OPENCLAW_API_KEY")) else "REAL_MODE_NOT_IMPLEMENTED"
        msg = "OPENCLAW_BASE_URL and OPENCLAW_API_KEY are required." if code == "OPENCLAW_NOT_CONFIGURED" else "real_openclaw is not implemented in this local package."
        error(args.output_dir, code, msg, code == "OPENCLAW_NOT_CONFIGURED")
        write_json(args.output_dir / "meta" / "run_meta.json", run_meta("real_openclaw", "real_openclaw", mode, "", str(args.input), pages, est, False, "failed", extra={"parse_mode_reason": reason, "input_page_count": total_pages, "output_profile": args.output_profile, "keep_pages_detail": args.keep_pages_detail}))
        return 1

    if args.backend == "official_output_mock":
        ok, task_id = official_mock(args.input, args.output_dir, args.mock_dir, args.legacy_task_id_file)
        meta = run_meta("official_output_mock", "external_official_output", mode, task_id, str(args.input), pages, est, False, "success" if ok else "failed", extra={"parse_mode_reason": reason, "input_page_count": total_pages, "output_profile": args.output_profile, "keep_pages_detail": args.keep_pages_detail, "legacy_task_id_file": args.legacy_task_id_file})
        write_json(args.output_dir / "meta" / "run_meta.json", meta)
        if not ok:
            return 1
        if not postprocess_report(args.output_dir, args.output_profile, args.keep_pages_detail, args.legacy_task_id_file):
            meta["status"] = "failed"
            write_json(args.output_dir / "meta" / "run_meta.json", meta)
            return 1
        return 0

    if not os.getenv("LAS_API_KEY"):
        error(args.output_dir, "AUTH_MISSING", "LAS_API_KEY is not configured.", True)
        write_json(args.output_dir / "meta" / "run_meta.json", run_meta("real_las", "real_las", mode, "", str(args.input), pages, est, False, "failed", extra={"parse_mode_reason": reason, "input_page_count": total_pages, "output_profile": args.output_profile, "keep_pages_detail": args.keep_pages_detail, "legacy_task_id_file": args.legacy_task_id_file}))
        return 1
    if not confirm(price, args.yes, args.output_dir, args.backend):
        write_json(args.output_dir / "meta" / "run_meta.json", run_meta("real_las", "real_las", mode, "", str(args.input), pages, est, False, "failed", extra={"parse_mode_reason": reason, "input_page_count": total_pages, "output_profile": args.output_profile, "keep_pages_detail": args.keep_pages_detail, "legacy_task_id_file": args.legacy_task_id_file}))
        return 1
    url = upload(args.input, args.output_dir)
    if not url:
        return 1
    task_id = submit(url, mode, args.output_dir, args.start_page, args.num_pages, args.legacy_task_id_file)
    if not task_id:
        return 1
    result = short_poll(task_id, args.output_dir, args.short_poll_seconds)
    status = "success" if result.get("status") == "success" else "pending" if result.get("status") == "pending" else "failed"
    meta = run_meta("real_las", "real_las", mode, task_id, str(args.input), pages, est, True, status, extra={"parse_mode_reason": reason, "input_page_count": total_pages, "poll_result": result, "output_profile": args.output_profile, "keep_pages_detail": args.keep_pages_detail, "legacy_task_id_file": args.legacy_task_id_file})
    write_json(args.output_dir / "meta" / "run_meta.json", meta)
    if status == "pending":
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if status != "success":
        print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    if not postprocess_report(args.output_dir, args.output_profile, args.keep_pages_detail, args.legacy_task_id_file):
        meta["status"] = "failed"
        write_json(args.output_dir / "meta" / "run_meta.json", meta)
        return 1
    print(json.dumps({"status": "success", "task_id": task_id, "output_dir": str(args.output_dir)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
