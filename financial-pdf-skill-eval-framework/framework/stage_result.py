"""统一的 pipeline stage 结果数据结构。

P0 pipeline 由多个独立 stage 组成（static_check / invoke / collect_artifacts /
assert_outputs / evaluate_ground_truth / compute_score / generate_report）。
每个 stage 必须返回一个 ``StageResult``，以便：
 - pipeline 编排可以基于 ``status`` 决定是否继续；
 - report_collector 可以按 stage 列举 failure 详情；
 - 单测可以独立比较 payload。

字段语义：
 - ``name``     : stage 唯一标识，例如 ``"static_check"``、``"score"``。
 - ``status``   : ``"success" | "failed" | "skipped" | "warning"``。
 - ``payload``  : stage 的产出（dict / list 等），不包含错误信息。
 - ``errors``   : 字符串列表，仅在 ``failed`` / ``warning`` 时填写。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


VALID_STATUSES = ("success", "failed", "skipped", "warning")


@dataclass
class StageResult:
    name: str
    status: str = "success"
    payload: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.status not in VALID_STATUSES:
            raise ValueError(f"invalid stage status: {self.status!r}; expected one of {VALID_STATUSES}")

    @property
    def ok(self) -> bool:
        return self.status in {"success", "warning", "skipped"}

    @property
    def passed(self) -> bool:
        return self.status == "success"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def success(name: str, payload: dict[str, Any] | None = None) -> StageResult:
    return StageResult(name=name, status="success", payload=payload or {})


def failed(name: str, errors: list[str], payload: dict[str, Any] | None = None) -> StageResult:
    return StageResult(name=name, status="failed", payload=payload or {}, errors=list(errors))


def skipped(name: str, reason: str, payload: dict[str, Any] | None = None) -> StageResult:
    return StageResult(name=name, status="skipped", payload=payload or {}, errors=[reason] if reason else [])


def warning(name: str, message: str, payload: dict[str, Any] | None = None) -> StageResult:
    return StageResult(name=name, status="warning", payload=payload or {}, errors=[message] if message else [])
