from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


DEFAULT_PRICES = {"normal": 0.02, "detail": 0.04}
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PRICES_PATH = SKILL_ROOT / "references" / "prices.md"


def count_pdf_pages(path: Path) -> int:
    if not path.exists():
        raise FileNotFoundError(str(path))
    if path.suffix.lower() != ".pdf":
        raise ValueError("INVALID_FILE_TYPE")
    for package in ("pypdf", "PyPDF2"):
        try:
            module = __import__(package, fromlist=["PdfReader"])
            return len(module.PdfReader(str(path)).pages)
        except Exception:
            pass
    data = path.read_bytes()
    matches = re.findall(rb"/Type\s*/Page\b(?!s)", data)
    if matches:
        return len(matches)
    raise RuntimeError("Unable to determine PDF page count. Pass --page-count explicitly.")


def load_prices(path: Path) -> dict[str, float]:
    prices = dict(DEFAULT_PRICES)
    if not path.exists():
        return prices
    text = path.read_text(encoding="utf-8", errors="ignore")
    for mode in ("normal", "detail"):
        match = re.search(rf"`?{mode}`?\s*\|\s*([0-9]+(?:\.[0-9]+)?)", text, re.I)
        if match:
            prices[mode] = float(match.group(1))
    return prices


def estimate(input_path: str, parse_mode: str, page_count: int | None, prices_path: Path) -> dict[str, Any]:
    if parse_mode not in {"normal", "detail", "auto"}:
        raise ValueError("parse_mode must be normal/detail/auto")
    resolved = "normal" if parse_mode == "auto" else parse_mode
    pages = page_count if page_count is not None else count_pdf_pages(Path(input_path))
    unit = load_prices(prices_path)[resolved]
    return {
        "input": input_path,
        "page_count": pages,
        "parse_mode": parse_mode,
        "resolved_parse_mode": resolved,
        "unit_price": unit,
        "estimated_price": round(pages * unit, 6),
        "currency": "CNY",
        "billing_notice": "This is an estimate only. Final charges are determined by the Volcengine bill after execution."
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--parse-mode", required=True, choices=["normal", "detail", "auto"])
    parser.add_argument("--page-count", type=int)
    parser.add_argument("--prices", type=Path, default=DEFAULT_PRICES_PATH)
    args = parser.parse_args()
    try:
        print(json.dumps(estimate(args.input, args.parse_mode, args.page_count, args.prices), ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_code": "INVALID_FILE_TYPE" if str(exc) == "INVALID_FILE_TYPE" else "PRICE_ESTIMATE_FAILED", "message": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
