from __future__ import annotations

import shutil
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: make_demo_project.py /tmp/reviewerloop-demo", file=sys.stderr)
        return 2

    project = Path(argv[1])
    if project.exists():
        shutil.rmtree(project)
    (project / "tests").mkdir(parents=True)

    (project / "calc.py").write_text(
        "def add(a, b):\n"
        "    return a - b\n",
        encoding="utf-8",
    )
    (project / "tests/test_smoke.py").write_text(
        "from calc import add\n\n\n"
        "def test_add_zero_identity():\n"
        "    assert add(4, 0) == 4\n",
        encoding="utf-8",
    )
    print(project)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
