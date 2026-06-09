from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from framework.context import FRAMEWORK_ROOT


DEFAULTS = {
    "output_profile": "standard",
    "parse_mode": "detail",
    "tags": [],
    "validations": [],
    "thresholds": {},
    "count_as_real_evaluation": False,
}


def _read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def normalize_case(case: dict) -> dict:
    out = dict(case or {})
    for k, v in DEFAULTS.items():
        out.setdefault(k, v if not isinstance(v, (list, dict)) else type(v)(v))
    if "case_id" not in out:
        raise ValueError(f"case missing case_id: {case}")
    return out


def load_case(path: str | Path) -> dict:
    p = Path(path)
    if not p.is_absolute():
        p = (FRAMEWORK_ROOT / p).resolve()
    if not p.exists():
        raise FileNotFoundError(p)
    data = _read_yaml(p)
    if isinstance(data, dict) and "cases" in data:
        raise ValueError(f"{p} is a multi-case file; use load_abnormal_cases or load_cases_from_dir")
    case = normalize_case(data)
    case["__source__"] = str(p)
    return case


def load_cases_from_dir(path: str | Path, include_multi: bool = False) -> list[dict]:
    p = Path(path)
    if not p.is_absolute():
        p = (FRAMEWORK_ROOT / p).resolve()
    cases: list[dict] = []
    for f in sorted(p.glob("*.yaml")):
        data = _read_yaml(f)
        if isinstance(data, dict) and "cases" in data:
            if include_multi:
                for c in data["cases"] or []:
                    nc = normalize_case(c)
                    nc["__source__"] = str(f)
                    cases.append(nc)
            continue
        if isinstance(data, dict):
            nc = normalize_case(data)
            nc["__source__"] = str(f)
            cases.append(nc)
    return cases


def load_abnormal_cases(path: str | Path) -> list[dict]:
    p = Path(path)
    if not p.is_absolute():
        p = (FRAMEWORK_ROOT / p).resolve()
    if not p.exists():
        return []
    data = _read_yaml(p) or {}
    raw_cases = data.get("cases") or []
    out: list[dict] = []
    for c in raw_cases:
        nc = normalize_case(c)
        nc.setdefault("tags", []).append("abnormal")
        nc["__source__"] = str(p)
        out.append(nc)
    return out
