# AGENTS.md

## Project

`reviewerloop` is a small Python CLI package that automates a reviewer/writer/test feedback loop over a target codebase.

The package intentionally stays minimal:

- Agents are plain subprocess commands.
- Prompts are sent on stdin.
- Outputs, errors, return codes, prompts, issue files, and state are written to files.
- There is no provider SDK, database, daemon, web UI, queue, or plugin system.

## Main User Workflow

Run:

```bash
reviewerloop run   --project .   --reviewer "codex exec"   --writer "claude"   --config reviewerloop.md   --test-cmd "pytest -q"   --max-cycles 5
```

The target project receives:

```text
.reviewerloop/
  issues/
    open/       # markdown issue files that still need work
    closed/     # issue files moved here after reviewer verification
  runs/         # prompts, stdout, stderr, and return codes per cycle
  state.json    # machine-readable loop state
```

## Instruction config

`reviewerloop run --config instructions.md` loads extra markdown instructions for both roles. The file must use these top-level headings:

```md
# Reviewer's instructions
...

# Writer's instructions
...
```

The reviewer section is appended to review and verification prompts. The writer section is appended to writer prompts. Missing sections are treated as empty.

## Roles

Reviewer responsibilities:

- Inspect the target project for correctness, regressions, corner cases, and YAGNI violations.
- Create or update one markdown issue file per issue under `.reviewerloop/issues/open`.
- Add regression tests when practical.
- Put rationale in pytest test docstrings so future agents know why failing tests exist.
- Close issues only by moving files from `.reviewerloop/issues/open` to `.reviewerloop/issues/closed` after tests pass and the fix has been reviewed.
- Avoid production fixes unless explicitly requested outside the normal loop.

Writer responsibilities:

- Read open issue files.
- Read failing pytest docstrings before debugging.
- Make the smallest production-code change that resolves open issues.
- Do not move issue files; the reviewer owns issue closure.

## Code Layout

```text
src/reviewerloop/cli.py   # CLI, prompts, subprocess execution, issue parsing, state/log writing
tests/test_cli.py         # unit and small integration tests
pyproject.toml            # package metadata and console script
```

`reviewerloop.cli` is deliberately the main module. Do not split it into a framework until there is real pressure from repeated behavior.

## Design Constraints

Follow YAGNI:

- Prefer one clear function over a class hierarchy.
- Prefer markdown files and JSON over a database.
- Prefer subprocess commands over provider-specific SDK abstractions.
- Add configuration only when a current use case requires it.
- Keep prompts explicit and versionable in code for now.

## Development

Demo target:

```bash
make demo
```

This creates `/tmp/reviewerloop-demo` with intentionally broken Python code and runs the real CLI with deterministic local reviewer/writer scripts from `examples/`.

Use the local virtualenv if present:

```bash
ve_reviewerloop/bin/python -m pytest -q
ve_reviewerloop/bin/python -m py_compile src/reviewerloop/*.py
```

If the venv is absent:

```bash
python3 -m venv ve_reviewerloop
ve_reviewerloop/bin/python -m pip install -e '.[dev]'
```

Generated files that should remain untracked:

- `ve_reviewerloop/`
- `.pytest_cache/`
- `__pycache__/`
- `.reviewerloop/`

## Review Checklist

Before committing changes:

1. Run tests.
2. Check that `reviewerloop run --help` still works.
3. Confirm no generated run artifacts are staged.
4. Keep the public CLI simple unless the new option is required by a concrete workflow.
