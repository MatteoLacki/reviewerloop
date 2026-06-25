from __future__ import annotations

import argparse
import json
import selectors
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


RED = "\033[31m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
YELLOW = "\033[33m"
DIM = "\033[2m"
RESET = "\033[0m"


def color(text: str, ansi: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"{ansi}{text}{RESET}"


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def combined_output(self) -> str:
        parts = []
        if self.stdout:
            parts.append(self.stdout)
        if self.stderr:
            parts.append(self.stderr)
        return "\n".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="reviewerloop",
        description="Run a reviewer/writer agent loop over a project.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run the review/write/test loop")
    run_parser.add_argument("--project", type=Path, default=Path.cwd(), help="Project folder to work in")
    run_parser.add_argument("--reviewer", required=True, help="Reviewer command; prompt is sent on stdin")
    run_parser.add_argument("--writer", required=True, help="Writer command; prompt is sent on stdin")
    run_parser.add_argument("--test-cmd", default="pytest -q", help="Test command run inside the project")
    run_parser.add_argument("--config", type=Path, default=None, help="Markdown file with reviewer and writer instructions")
    run_parser.add_argument("--max-cycles", type=int, default=5, help="Maximum reviewer/writer cycles")
    run_parser.add_argument("--workdir", default=".reviewerloop", help="Directory for state, issues, and logs")

    args = parser.parse_args(argv)
    if args.command == "run":
        return run_loop(args)
    return 2


def run_loop(args: argparse.Namespace) -> int:
    project = args.project.resolve()
    workspace = project / args.workdir
    issues_dir = workspace / "issues"
    open_issues_dir = issues_dir / "open"
    closed_issues_dir = issues_dir / "closed"
    runs_dir = workspace / "runs"
    open_issues_dir.mkdir(parents=True, exist_ok=True)
    closed_issues_dir.mkdir(parents=True, exist_ok=True)
    runs_dir.mkdir(parents=True, exist_ok=True)

    reviewer_instructions, writer_instructions = load_config(args.config)
    state = {
        "project": str(project),
        "max_cycles": args.max_cycles,
        "test_cmd": args.test_cmd,
        "config": str(args.config.resolve()) if args.config else None,
        "cycles": [],
    }

    final_tests = None
    for cycle in range(1, args.max_cycles + 1):
        run_dir = runs_dir / f"{cycle:03d}"
        run_dir.mkdir(parents=True, exist_ok=True)

        print(color(f"[reviewerloop] cycle {cycle}: reviewer", RED), flush=True)
        review_prompt = build_reviewer_prompt(project, open_issues_dir, closed_issues_dir, args.test_cmd, cycle, reviewer_instructions)
        reviewer_result = run_agent(args.reviewer, review_prompt, project)
        write_text(run_dir / "reviewer.prompt.md", review_prompt)
        write_result(run_dir / "reviewer", reviewer_result)
        if reviewer_result.returncode != 0:
            state["cycles"].append(agent_failure_state(cycle, "reviewer", reviewer_result))
            write_state(workspace / "state.json", state)
            return reviewer_result.returncode

        print(color(f"[reviewerloop] cycle {cycle}: tests after review", YELLOW), flush=True)
        first_tests = run_command(args.test_cmd, project)
        write_result(run_dir / "tests.after-review", first_tests)

        open_issues = list_open_issues(open_issues_dir)
        if not open_issues and first_tests.returncode == 0:
            final_tests = first_tests
            state["cycles"].append(cycle_state(cycle, open_issues, first_tests, skipped_writer=True))
            write_state(workspace / "state.json", state)
            return 0

        print(color(f"[reviewerloop] cycle {cycle}: writer", BLUE), flush=True)
        writer_prompt = build_writer_prompt(project, open_issues_dir, args.test_cmd, first_tests, writer_instructions)
        writer_result = run_agent(args.writer, writer_prompt, project)
        write_text(run_dir / "writer.prompt.md", writer_prompt)
        write_result(run_dir / "writer", writer_result)
        if writer_result.returncode != 0:
            state["cycles"].append(agent_failure_state(cycle, "writer", writer_result))
            write_state(workspace / "state.json", state)
            return writer_result.returncode

        print(color(f"[reviewerloop] cycle {cycle}: tests after writer", YELLOW), flush=True)
        second_tests = run_command(args.test_cmd, project)
        write_result(run_dir / "tests.after-writer", second_tests)

        print(color(f"[reviewerloop] cycle {cycle}: verifier", MAGENTA), flush=True)
        verify_prompt = build_verifier_prompt(project, open_issues_dir, closed_issues_dir, args.test_cmd, second_tests, reviewer_instructions)
        verifier_result = run_agent(args.reviewer, verify_prompt, project)
        write_text(run_dir / "verifier.prompt.md", verify_prompt)
        write_result(run_dir / "verifier", verifier_result)
        if verifier_result.returncode != 0:
            state["cycles"].append(agent_failure_state(cycle, "verifier", verifier_result))
            write_state(workspace / "state.json", state)
            return verifier_result.returncode

        print(color(f"[reviewerloop] cycle {cycle}: tests after verifier", YELLOW), flush=True)
        final_tests = run_command(args.test_cmd, project)
        write_result(run_dir / "tests.after-verifier", final_tests)

        open_issues = list_open_issues(open_issues_dir)
        state["cycles"].append(cycle_state(cycle, open_issues, final_tests, skipped_writer=False))
        write_state(workspace / "state.json", state)

        if not open_issues and final_tests.returncode == 0:
            return 0

    return final_tests.returncode if final_tests is not None else 1


def run_agent(command: str, prompt: str, cwd: Path) -> CommandResult:
    return run_command(command, cwd, stdin=prompt)


def run_command(command: str, cwd: Path, stdin: str | None = None) -> CommandResult:
    print(color(f"[reviewerloop] running: {command}", DIM), flush=True)
    process = subprocess.Popen(
        shlex.split(command),
        cwd=cwd,
        stdin=subprocess.PIPE if stdin is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    if stdin is not None and process.stdin is not None:
        process.stdin.write(stdin)
        process.stdin.close()

    selector = selectors.DefaultSelector()
    assert process.stdout is not None
    assert process.stderr is not None
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []

    while selector.get_map():
        for key, _ in selector.select():
            chunk = key.fileobj.readline()
            if not chunk:
                selector.unregister(key.fileobj)
                continue
            if key.data == "stdout":
                stdout_parts.append(chunk)
                print(chunk, end="", file=sys.stdout, flush=True)
            else:
                stderr_parts.append(chunk)
                print(chunk, end="", file=sys.stderr, flush=True)

    returncode = process.wait()
    return CommandResult(returncode, "".join(stdout_parts), "".join(stderr_parts))


def build_reviewer_prompt(
    project: Path,
    open_issues_dir: Path,
    closed_issues_dir: Path,
    test_cmd: str,
    cycle: int,
    reviewer_instructions: str = "",
) -> str:
    return f"""You are the reviewer in an automated code review loop.

Project: {project}
Open issues directory: {open_issues_dir}
Closed issues directory: {closed_issues_dir}
Test command: {test_cmd}
Cycle: {cycle}

Review the project for correctness, regressions, missing corner cases, and YAGNI violations.
Print a concise human-readable summary of what you inspected, what you found, and why it matters.
Create or update one markdown file per open issue in the open issues directory.
If practical, add regression tests that fail until the issue is fixed.
Every new pytest regression test must have a docstring explaining why the test exists and what behavior it guards.
Do not implement production fixes. Close issues only by moving issue files from open to closed after tests pass and you have re-reviewed the fix.
{format_extra_instructions("Reviewer", reviewer_instructions)}"""


def build_writer_prompt(
    project: Path,
    open_issues_dir: Path,
    test_cmd: str,
    tests: CommandResult,
    writer_instructions: str = "",
) -> str:
    return f"""You are the writer in an automated review loop.

Project: {project}
Open issues directory: {open_issues_dir}
Test command: {test_cmd}

Read the open issue files and the failing pytest docstrings before editing code.
Print a concise human-readable summary of what is failing, what change you made, and why that should fix it.
Make the smallest production-code change that resolves the open issues.
Do not move issue files; the reviewer owns issue closure.
{format_extra_instructions("Writer", writer_instructions)}
Latest test output:
```
{trim(tests.combined_output)}
```
"""


def build_verifier_prompt(
    project: Path,
    open_issues_dir: Path,
    closed_issues_dir: Path,
    test_cmd: str,
    tests: CommandResult,
    reviewer_instructions: str = "",
) -> str:
    return f"""You are the reviewer verifying the writer's changes.

Project: {project}
Open issues directory: {open_issues_dir}
Closed issues directory: {closed_issues_dir}
Test command: {test_cmd}

Review the current code and test output.
Print a concise human-readable verification note explaining whether the fix is complete.
Move only genuinely fixed issue files from open to closed.
Keep unresolved issues in open and add concise notes if the fix is incomplete.
Add new issue files only for real regressions or newly discovered risks.
{format_extra_instructions("Reviewer", reviewer_instructions)}
Latest test output:
```
{trim(tests.combined_output)}
```
"""


def load_config(path: Path | None) -> tuple[str, str]:
    if path is None:
        return "", ""
    text = path.read_text(encoding="utf-8")
    return (
        markdown_h1_section(text, "Reviewer's instructions"),
        markdown_h1_section(text, "Writer's instructions"),
    )


def markdown_h1_section(markdown: str, heading: str) -> str:
    lines = markdown.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip() == f"# {heading}":
            start = index + 1
            break
    if start is None:
        return ""

    end = len(lines)
    for index in range(start, len(lines)):
        stripped = lines[index].strip()
        if stripped.startswith("# "):
            end = index
            break
    return "\n".join(lines[start:end]).strip()


def format_extra_instructions(role: str, instructions: str) -> str:
    if not instructions.strip():
        return ""
    return f"\nAdditional {role.lower()} instructions from config:\n{instructions.strip()}\n"


def list_open_issues(open_issues_dir: Path) -> list[str]:
    if not open_issues_dir.exists():
        return []
    return sorted(path.name for path in open_issues_dir.glob("*.md"))


def cycle_state(cycle: int, open_issues: list[str], tests: CommandResult, skipped_writer: bool) -> dict:
    return {
        "cycle": cycle,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "open_issues": open_issues,
        "test_returncode": tests.returncode,
        "skipped_writer": skipped_writer,
    }


def agent_failure_state(cycle: int, role: str, result: CommandResult) -> dict:
    return {
        "cycle": cycle,
        "failed_role": role,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "returncode": result.returncode,
    }


def write_state(path: Path, state: dict) -> None:
    write_text(path, json.dumps(state, indent=2, sort_keys=True) + "\n")


def write_result(prefix: Path, result: CommandResult) -> None:
    write_text(prefix.with_suffix(".stdout.txt"), result.stdout)
    write_text(prefix.with_suffix(".stderr.txt"), result.stderr)
    write_text(prefix.with_suffix(".returncode.txt"), f"{result.returncode}\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def trim(text: str, limit: int = 12000) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


if __name__ == "__main__":
    raise SystemExit(main())
