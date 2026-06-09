from __future__ import annotations

import argparse
import html
import json
import re
import sys
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = Path(__file__).resolve().parents[1]
STATEMENTS = ["合并资产负债表", "合并利润表", "合并现金流量表", "资产负债表", "利润表", "现金流量表"]
STATEMENTS_BY_LENGTH = sorted(STATEMENTS, key=len, reverse=True)
BALANCE_ITEMS = ["货币资金", "应收账款", "流动资产合计", "非流动资产合计", "资产总计", "短期借款", "应付账款", "流动负债合计", "非流动负债合计", "负债合计", "实收资本", "资本公积", "盈余公积", "未分配利润", "所有者权益合计", "负债和所有者权益总计"]
INCOME_ITEMS = ["营业收入", "营业成本", "税金及附加", "销售费用", "管理费用", "财务净收益", "信用减值损失", "资产处置收益", "其他收益", "营业利润", "营业外收入", "营业外支出", "利润总额", "所得税", "净利润"]
CASH_ITEMS = ["经营活动现金流入小计", "经营活动现金流出小计", "经营活动使用的现金流量净额", "经营活动产生的现金流量净额", "投资活动现金流入小计", "投资活动现金流出小计", "投资活动使用的现金流量净额", "筹资活动现金流入小计", "筹资活动现金流出小计", "筹资活动产生的现金流量净额", "现金及现金等价物增加额", "现金及现金等价物的年末金额"]
KEY_ITEMS = BALANCE_ITEMS + INCOME_ITEMS + CASH_ITEMS
FINANCIAL_STATEMENT_KEYWORDS = ["资产负债表", "利润表", "现金流量表"]
SIGNATURE_KEYWORDS = ["签名", "盖章", "法定代表人", "主管会计工作负责人", "会计机构负责人"]
LAYOUT_KEYWORDS = ["[IMAGE]", "[TEMP_IMAGE_URL]", "负责人", "签字", "印章"]

TABLE_RE = re.compile(r"<table[\s\S]*?</table>", re.I)
TEMP_URL_RE = re.compile(r"https?://[^\s)\"']*(?:tos-|las-|volces|presigned|tmp)[^\s)\"']*", re.I)
IMAGE_MD_RE = re.compile(r"!\[[^\]]*\]\((https?://[^)]+)\)")
NEGATIVE_RE = re.compile(r"[（(]\s*[-+]?\d[\d,，]*(?:\.\d+)?\s*[）)]")
DATE_RE = re.compile(r"(\d{1,2}/\d{1,2}/\d{4})|(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)|(\d{4}Q[1-4])", re.I)


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self.in_row = False
        self.in_cell = False
        self.row: list[str] = []
        self.cell: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "tr":
            self.in_row = True
            self.row = []
        elif tag.lower() in {"td", "th"} and self.in_row:
            self.in_cell = True
            self.cell = []

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"td", "th"} and self.in_cell:
            self.row.append(html.unescape(" ".join("".join(self.cell).split())).strip())
            self.in_cell = False
        elif tag.lower() == "tr" and self.in_row:
            if any(x.strip() for x in self.row):
                self.rows.append(self.row)
            self.in_row = False


def normalize_number(value: str) -> str:
    if value is None:
        return ""
    text = str(value).strip().replace("\u3000", "").replace("\xa0", "").replace(" ", "")
    if text in {"", "-", "－", "--", "—", "–"}:
        return ""
    negative = (text.startswith("(") and text.endswith(")")) or (text.startswith("（") and text.endswith("）"))
    if negative:
        text = text[1:-1]
    text = text.replace(",", "").replace("，", "").replace("人民币", "").replace("元", "").replace("￥", "")
    if text.startswith("+"):
        text = text[1:]
    if negative and not text.startswith("-"):
        text = "-" + text
    if re.fullmatch(r"-?\d+(?:\.\d+)?%?", text):
        return text.rstrip("%")
    return text


def clean_markdown(markdown: str) -> str:
    text = markdown.replace("\r\n", "\n").replace("\r", "\n")
    text = IMAGE_MD_RE.sub("[IMAGE]", text)
    text = TEMP_URL_RE.sub("[TEMP_IMAGE_URL]", text)
    lines = [line.rstrip() for line in text.splitlines() if line.strip().upper() != "CONFIDENTIAL"]
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    return text + "\n" if text else ""


def unique_columns(cols: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    out: list[str] = []
    for i, col in enumerate(cols):
        name = col.strip() or ("项目" if i == 0 else f"列{i + 1}")
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 1
        out.append(name)
    return out


def statement_from(prefix: str, rows: list[list[str]] | None = None) -> str:
    best: tuple[int, int, str] | None = None
    for name in STATEMENTS_BY_LENGTH:
        pos = prefix.rfind(name)
        if pos >= 0:
            cand = (pos + len(name), len(name), name)
            if best is None or cand > best:
                best = cand
    if best:
        return best[2]
    joined = "\n".join(" ".join(r) for r in (rows or [])[:5])
    for name in STATEMENTS_BY_LENGTH:
        if name in joined:
            return name
    return "unknown"


def rows_to_table(rows: list[list[str]], table_id: str, statement: str) -> dict[str, Any] | None:
    if not rows:
        return None
    header = 0
    for i, row in enumerate(rows[:4]):
        if "项目" in "".join(row) or len(row) >= 2:
            header = i
            break
    cols = unique_columns(rows[header])
    body: list[dict[str, str]] = []
    for row in rows[header + 1:]:
        cells = row[:len(cols)] + [""] * max(0, len(cols) - len(row))
        if any(x.strip() for x in cells):
            body.append({cols[i]: cells[i] for i in range(len(cols))})
    if not body:
        return None
    table = {"table_id": table_id, "page": 1, "statement": statement, "columns": cols, "rows": body}
    table["table_type"] = classify_table(table)
    return table


def table_text(table: dict[str, Any]) -> str:
    parts: list[str] = [str(table.get("statement", ""))]
    parts.extend(str(col) for col in table.get("columns", []))
    for row in table.get("rows", []):
        if isinstance(row, dict):
            parts.extend(str(value) for value in row.values())
    return " ".join(parts)


def classify_table(table: dict[str, Any]) -> str:
    text = table_text(table)
    statement = str(table.get("statement", ""))
    if any(keyword in statement for keyword in FINANCIAL_STATEMENT_KEYWORDS):
        return "financial_table"
    if any(keyword in text for keyword in SIGNATURE_KEYWORDS):
        return "signature_table"
    columns = table.get("columns", [])
    rows = table.get("rows", [])
    if len(columns) <= 3 and any(keyword in text for keyword in LAYOUT_KEYWORDS):
        return "layout_table"
    if len(columns) <= 3 and len(rows) <= 4 and not any(char.isdigit() for char in text):
        return "layout_table"
    return "unknown_table"


def table_statistics(tables: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "raw_table_count": len(tables),
        "financial_table_count": sum(1 for table in tables if table.get("table_type") == "financial_table"),
        "layout_table_count": sum(1 for table in tables if table.get("table_type") == "layout_table"),
        "signature_table_count": sum(1 for table in tables if table.get("table_type") == "signature_table"),
        "unknown_table_count": sum(1 for table in tables if table.get("table_type") == "unknown_table"),
    }


def parse_html_rows(table_html: str) -> list[list[str]]:
    parser = TableParser()
    parser.feed(table_html)
    return parser.rows


def parse_markdown_tables(markdown: str) -> list[list[list[str]]]:
    blocks: list[list[list[str]]] = []
    current: list[str] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            current.append(stripped)
        else:
            if len(current) >= 2:
                blocks.append(markdown_block_rows(current))
            current = []
    if len(current) >= 2:
        blocks.append(markdown_block_rows(current))
    return [b for b in blocks if b]


def markdown_block_rows(lines: list[str]) -> list[list[str]]:
    rows = []
    for line in lines:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and all(re.fullmatch(r":?-{3,}:?", c.replace(" ", "")) for c in cells):
            continue
        rows.append(cells)
    return rows


def extract_tables(markdown: str) -> list[dict[str, Any]]:
    tables: list[dict[str, Any]] = []
    for match in TABLE_RE.finditer(markdown):
        rows = parse_html_rows(match.group(0))
        table = rows_to_table(rows, f"table_{len(tables) + 1:03d}", statement_from(markdown[:match.start()], rows))
        if table:
            tables.append(table)
    for rows in parse_markdown_tables(TABLE_RE.sub("", markdown)):
        table = rows_to_table(rows, f"table_{len(tables) + 1:03d}", statement_from(markdown, rows))
        if table:
            tables.append(table)
    return tables


def clean_label(value: str) -> str:
    text = re.sub(r"\s+", "", str(value))
    text = re.sub(r"^[一二三四五六七八九十\d、.．（）()]+", "", text)
    text = re.sub(r"^(加|减|其中)[:：]?", "", text)
    return text.strip(":：")


def match_item(value: str) -> str | None:
    cleaned = clean_label(value)
    for item in KEY_ITEMS:
        if cleaned == item:
            return item
    return None


def item_col(cols: list[str]) -> str:
    return next((c for c in cols if "项目" in c), cols[0] if cols else "项目")


def normalize_period(value: str) -> str:
    text = " ".join(str(value).split())
    m = re.search(r"\d{1,2}/\d{1,2}/\d{4}", text)
    if m:
        return m.group(0)
    m = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", text)
    if m:
        y, mo, d = m.groups()
        return f"{int(mo)}/{int(d)}/{y}"
    m = re.search(r"\d{4}Q[1-4]", text, re.I)
    return m.group(0).upper() if m else text


def extract_company(markdown: str) -> str:
    m = re.search(r"([\u4e00-\u9fffA-Za-z0-9（）()]{2,40}有限公司)", markdown)
    return m.group(1) if m else ""


def infer_period(metrics: list[dict[str, Any]]) -> str:
    for metric in metrics:
        m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", str(metric.get("period", "")))
        if m:
            month, _day, year = m.groups()
            return f"{year}Q{(int(month) - 1) // 3 + 1}"
    return ""


def extract_summary(markdown: str, tables: list[dict[str, Any]]) -> dict[str, Any]:
    metrics: list[dict[str, Any]] = []
    for table in tables:
        cols = table.get("columns", [])
        if not cols:
            continue
        ic = item_col(cols)
        value_cols = [c for c in cols if c != ic and "附注" not in c and "注释" not in c]
        for row in table.get("rows", []):
            item = match_item(str(row.get(ic, "")))
            if not item:
                continue
            for col in value_cols:
                raw = str(row.get(col, "")).strip()
                norm = normalize_number(raw)
                if raw and norm:
                    metrics.append({"statement": table.get("statement", "unknown"), "item": item, "period": normalize_period(col), "value": raw, "normalized_value": norm, "table_id": table.get("table_id", "")})
    metric_stats = metric_statistics(metrics)
    return {
        "company": extract_company(markdown),
        "document_type": "financial_report",
        "period": infer_period(metrics),
        "metrics": metrics,
        "metric_statistics": metric_stats,
    }


def metric_statistics(metrics: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "metric_record_count": len(metrics),
        "unique_item_count": len({str(metric.get("item", "")) for metric in metrics if metric.get("item")}),
        "unique_statement_count": len({str(metric.get("statement", "")) for metric in metrics if metric.get("statement")}),
    }


def dec(value: str) -> Decimal | None:
    try:
        return Decimal(normalize_number(value))
    except (InvalidOperation, ValueError):
        return None


def approx(a: Decimal, b: Decimal) -> bool:
    return abs(a - b) <= max(Decimal("1.00"), abs(a) * Decimal("0.0001"))


def balance_checks(summary: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    by_key: dict[tuple[str, str, str], Decimal] = {}
    for metric in summary.get("metrics", []):
        value = dec(str(metric.get("normalized_value", "")))
        if value is not None:
            by_key[(str(metric.get("statement")), str(metric.get("item")), str(metric.get("period")))] = value
    statements = sorted({s for s, item, _p in by_key if "资产负债表" in s})
    for statement in statements:
        periods = sorted({p for s, _i, p in by_key if s == statement})
        for period in periods:
            assets = by_key.get((statement, "资产总计", period))
            total = by_key.get((statement, "负债和所有者权益总计", period))
            liabilities = by_key.get((statement, "负债合计", period))
            equity = by_key.get((statement, "所有者权益合计", period))
            if assets is not None and total is not None:
                ok = approx(assets, total)
                checks.append({"name": "balance_equation_check", "statement": statement, "period": period, "passed": ok, "message": "资产总计等于负债和所有者权益总计" if ok else "资产总计与负债和所有者权益总计不一致"})
            if liabilities is not None and equity is not None and total is not None:
                ok = approx(liabilities + equity, total)
                checks.append({"name": "liabilities_equity_total_check", "statement": statement, "period": period, "passed": ok, "message": "负债合计加所有者权益合计约等于负债和所有者权益总计" if ok else "负债合计加所有者权益合计与总计不一致"})
    return checks


def load_json(path: Path | None, default: Any) -> Any:
    if not path or not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8", errors="ignore"))


def quality(
    original: str,
    cleaned: str,
    pages_detail: Any,
    tables: list[dict[str, Any]],
    summary: dict[str, Any],
    result_json: dict[str, Any] | None,
    run_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    checks = [
        {"name": "table_count_check", "statement": "", "passed": len(tables) > 0, "message": f"检测到 {len(tables)} 个表格" if tables else "未检测到表格"},
        {"name": "financial_statement_detection_check", "statement": ",".join(sorted({t.get("statement", "") for t in tables if t.get("statement") != "unknown"})), "passed": any(t.get("statement") in STATEMENTS for t in tables), "message": "关键财务表识别检查完成"},
    ]
    checks.extend(balance_checks(summary))
    neg = bool(NEGATIVE_RE.search(original))
    decimal_ok = not re.search(r"\d+\.\d+", original) or any("." in str(m.get("normalized_value", "")) for m in summary.get("metrics", []))
    period = any(DATE_RE.search(c) for t in tables for c in t.get("columns", []))
    noise = any(x in original for x in ["CONFIDENTIAL", "签名", "盖章"]) or bool(TEMP_URL_RE.search(original))
    pages_ok = isinstance(pages_detail, list) and all(isinstance(x, dict) for x in pages_detail)
    checks += [
        {"name": "negative_number_check", "statement": "", "passed": True, "message": "检测到括号负数" if neg else "未检测到括号负数"},
        {"name": "decimal_preservation_check", "statement": "", "passed": decimal_ok, "message": "小数点保留检查通过" if decimal_ok else "小数点保留检查失败"},
        {"name": "period_column_check", "statement": "", "passed": period, "message": "检测到期间列" if period else "未检测到期间列"},
        {"name": "noise_detection_check", "statement": "", "passed": True, "message": "检测到噪声" if noise else "未检测到已知噪声"},
        {"name": "pages_detail_schema_check", "statement": "", "passed": pages_ok, "message": "pages_detail.json schema 检查通过" if pages_ok else "pages_detail.json 不是页面对象数组"},
        {"name": "parsed_markdown_non_empty_check", "statement": "", "passed": bool(cleaned.strip()), "message": "parsed.md 非空" if cleaned.strip() else "parsed.md 为空"},
    ]
    if result_json is not None:
        bc = result_json.get("metadata", {}).get("business_code", 0) if isinstance(result_json, dict) else None
        checks.append({"name": "result_business_code_check", "statement": "", "passed": bc in {0, "0", None}, "message": f"business_code={bc}"})
    bal = [c for c in checks if c["name"] in {"balance_equation_check", "liabilities_equity_total_check"}]
    table_stats = table_statistics(tables)
    metric_stats = metric_statistics(summary.get("metrics", []))
    meta = run_meta or {}
    return {
        "data_authenticity": {
            "execution_backend": meta.get("execution_backend", "unknown"),
            "output_source": meta.get("output_source", "unknown"),
            "is_synthetic": bool(meta.get("is_synthetic", False)),
            "count_as_real_evaluation": bool(meta.get("count_as_real_evaluation", False)),
        },
        "table_statistics": table_stats,
        "metric_statistics": metric_stats,
        "checks": checks,
        "scores": {
            "table_count": table_stats["raw_table_count"],
            "financial_metric_count": metric_stats["metric_record_count"],
            "raw_table_count": table_stats["raw_table_count"],
            "financial_table_count": table_stats["financial_table_count"],
            "layout_table_count": table_stats["layout_table_count"],
            "signature_table_count": table_stats["signature_table_count"],
            "unknown_table_count": table_stats["unknown_table_count"],
            "metric_record_count": metric_stats["metric_record_count"],
            "unique_item_count": metric_stats["unique_item_count"],
            "unique_statement_count": metric_stats["unique_statement_count"],
            "balance_check_pass_rate": round(sum(1 for c in bal if c.get("passed")) / len(bal), 4) if bal else 0.0,
            "negative_number_detected": neg,
            "noise_blocks_detected": noise,
        },
    }


def postprocess(parsed_md: Path, pages_detail_path: Path, output_dir: Path, result_json_path: Path | None = None) -> dict[str, Any]:
    original = parsed_md.read_text(encoding="utf-8", errors="ignore") if parsed_md.exists() else ""
    pages = load_json(pages_detail_path, [])
    result_json = load_json(result_json_path, None)
    cleaned = clean_markdown(original)
    tables = extract_tables(cleaned)
    summary = extract_summary(cleaned, tables)
    run_meta = load_json(output_dir / "meta" / "run_meta.json", {})
    qc = quality(original, cleaned, pages, tables, summary, result_json, run_meta)
    (output_dir / "normalized").mkdir(parents=True, exist_ok=True)
    (output_dir / "evaluation").mkdir(parents=True, exist_ok=True)
    (output_dir / "normalized" / "cleaned.md").write_text(cleaned, encoding="utf-8")
    (output_dir / "normalized" / "normalized_tables.json").write_text(json.dumps({"tables": tables}, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "normalized" / "financial_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "evaluation" / "quality_checks.json").write_text(json.dumps(qc, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "table_count": len(tables),
        "metric_count": len(summary.get("metrics", [])),
        "table_statistics": qc["table_statistics"],
        "metric_statistics": qc["metric_statistics"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parsed-md", required=True, type=Path)
    parser.add_argument("--pages-detail", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--result-json", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps({"status": "success", **postprocess(args.parsed_md, args.pages_detail, args.output_dir, args.result_json)}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        error = {"status": "failed", "error_code": "POSTPROCESS_FAILED", "message": str(exc)}
        (args.output_dir / "meta").mkdir(parents=True, exist_ok=True)
        (args.output_dir / "meta" / "error_result.json").write_text(json.dumps(error, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(error, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
