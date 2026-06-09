from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}


def run_openclaw_command(args: list[str]) -> tuple[str, str, int]:
    try:
        completed = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        return completed.stdout.strip(), completed.stderr.strip(), completed.returncode
    except Exception as exc:
        return "", str(exc), 1


def iter_run_meta(outputs_dir: Path) -> list[tuple[str, Path, dict[str, Any]]]:
    items: list[tuple[str, Path, dict[str, Any]]] = []
    for path in sorted(outputs_dir.glob("*/meta/run_meta.json")):
        case_id = path.parents[1].name
        items.append((case_id, path, read_json(path)))
    for path in sorted(outputs_dir.glob("*/run_meta.json")):
        case_id = path.parent.name
        items.append((case_id, path, read_json(path)))
    return items


def generate(skill_dir: Path, outputs_dir: Path, output: Path) -> Path:
    lines = [
        "# OpenClaw Invocation Evidence",
        "",
        f"- Skill path: `{skill_dir}`",
        f"- SKILL.md exists: `{(skill_dir / 'SKILL.md').exists()}`",
        f"- _meta.json exists: `{(skill_dir / '_meta.json').exists()}`",
        "",
        "## Detected Invocation Methods",
        "- OpenClaw Skill package directory with SKILL.md and _meta.json.",
        "- Direct LAS fallback through `lasutil` when execution_backend is `real_las`.",
        "",
        "## OpenClaw CLI Check",
    ]

    if shutil.which("openclaw"):
        for command in (["openclaw", "skills", "list"], ["openclaw", "skills", "check", str(skill_dir)]):
            stdout, stderr, returncode = run_openclaw_command(command)
            lines.extend(
                [
                    f"### `{' '.join(command)}`",
                    f"- returncode: `{returncode}`",
                    "",
                    "```text",
                    stdout or "(empty stdout)",
                    "```",
                    "",
                    "```text",
                    stderr or "(empty stderr)",
                    "```",
                ]
            )
    else:
        lines.append("- `OPENCLAW_CLI_NOT_FOUND`: openclaw CLI was not found on PATH. This is recorded as evidence, not a script failure.")

    lines.extend(
        [
            "",
            "## Output Run Metadata Summary",
            "",
            "| case_id | execution_backend | output_source | task_id | output_dir | is_synthetic | count_as_real_evaluation |",
            "|---|---|---|---|---|---:|---:|",
        ]
    )
    has_real_openclaw = False
    for case_id, path, meta in iter_run_meta(outputs_dir):
        backend = meta.get("execution_backend", "unknown")
        if backend == "real_openclaw":
            has_real_openclaw = True
        lines.append(
            "| {case_id} | {backend} | {source} | {task_id} | {output_dir} | {synthetic} | {real_eval} |".format(
                case_id=case_id,
                backend=backend,
                source=meta.get("output_source", "unknown"),
                task_id=meta.get("task_id", ""),
                output_dir=path.parent.parent if path.parent.name == "meta" else path.parent,
                synthetic=meta.get("is_synthetic", False),
                real_eval=meta.get("count_as_real_evaluation", False),
            )
        )

    lines.extend(
        [
            "",
            "## Notes",
            "- 当前 backend 为 real_las 时，表示 Skill 内部直接调用 LAS / lasutil，不等同于 real_openclaw 后端调度。",
        ]
    )
    if not has_real_openclaw:
        lines.append("- real_openclaw backend 尚未验证。")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect OpenClaw invocation evidence for this skill.")
    parser.add_argument("--skill-dir", required=True, type=Path)
    parser.add_argument("--outputs-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    path = generate(args.skill_dir, args.outputs_dir, args.output)
    print(str(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
