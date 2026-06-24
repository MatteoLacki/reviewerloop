from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path


def prompt_path(prompt: str, label: str) -> Path:
    match = re.search(rf"^{re.escape(label)}: (.+)$", prompt, flags=re.MULTILINE)
    if not match:
        raise SystemExit(f"missing prompt field: {label}")
    return Path(match.group(1).strip())


def main() -> int:
    prompt = sys.stdin.read()
    project = prompt_path(prompt, "Project")
    open_dir = prompt_path(prompt, "Open issues directory")
    closed_dir = prompt_path(prompt, "Closed issues directory")
    open_dir.mkdir(parents=True, exist_ok=True)
    closed_dir.mkdir(parents=True, exist_ok=True)

    issue = open_dir / "RL-0001-addition.md"
    closed_issue = closed_dir / issue.name
    regression = project / "tests" / "test_addition_regression.py"
    source = (project / "calc.py").read_text(encoding="utf-8")

    if "return a + b" in source:
        lower_prompt = prompt.lower()
        verifier_has_passing_tests = "latest test output:" in lower_prompt and "failed" not in lower_prompt and "error" not in lower_prompt
        if issue.exists() and verifier_has_passing_tests:
            shutil.move(str(issue), str(closed_issue))
            print(f"closed {closed_issue}")
        elif issue.exists():
            print("fix detected, but tests are not passing yet; keeping issue open")
        else:
            print("no open issue")
        return 0

    if not closed_issue.exists():
        issue.write_text(
            "# RL-0001: add subtracts the second operand\n\n"
            "The `add(a, b)` function returns `a - b`, so ordinary positive operands produce the wrong sum.\n\n"
            "Regression test: `tests/test_addition_regression.py::test_add_handles_positive_operands`.\n",
            encoding="utf-8",
        )
        regression.write_text(
            "from calc import add\n\n\n"
            "def test_add_handles_positive_operands():\n"
            "    \"\"\"Regression: add must sum operands; the original implementation subtracted b.\"\"\"\n"
            "    assert add(2, 3) == 5\n",
            encoding="utf-8",
        )
        print(f"opened {issue}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
