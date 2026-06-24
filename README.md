# reviewerloop

`reviewerloop` runs a small reviewer/writer/test loop over a project.

The reviewer command receives a prompt on stdin, writes markdown issue files under `.reviewerloop/issues/open`, and may add regression tests with docstrings explaining the problem. The writer command receives the open issues plus test output and makes the smallest code change needed. The reviewer then verifies and closes issues by moving files to `.reviewerloop/issues/closed`.

## Usage

```bash
reviewerloop run \
  --project . \
  --reviewer "codex exec" \
  --writer "claude" \
  --test-cmd "pytest -q" \
  --max-cycles 5
```

Artifacts are stored in the target project:

```text
.reviewerloop/
  issues/
    open/
    closed/
  runs/
  state.json
```

The agent commands are plain subprocess commands. `reviewerloop` sends prompts on stdin and captures stdout, stderr, and return codes.

## Demo

Run a deterministic local demo against a broken project in `/tmp/reviewerloop-demo`:

```bash
make demo
```

The demo creates a broken `calc.add` implementation, uses local Python scripts as reviewer and writer agents, adds a regression test with a rationale docstring, fixes the code, and verifies the issue file moved from `issues/open` to `issues/closed`.
