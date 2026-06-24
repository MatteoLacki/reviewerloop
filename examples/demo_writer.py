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
    (project / "calc.py").write_text(
        "def add(a, b):\n"
        "    return a + b\n",
        encoding="utf-8",
    )
    shutil.rmtree(project / "__pycache__", ignore_errors=True)
    print("fixed calc.add")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
