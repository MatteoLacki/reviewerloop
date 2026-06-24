# reviewerloop

`reviewerloop` runs a small reviewer/writer/test loop over a project.

The reviewer command receives a prompt on stdin, writes markdown issue files under `.reviewerloop/issues`, and may add regression tests with docstrings explaining the problem. The writer command receives the open issues plus test output and makes the smallest code change needed. The reviewer then verifies and marks issues resolved.

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
  runs/
  state.json
```

The agent commands are plain subprocess commands. `reviewerloop` sends prompts on stdin and captures stdout, stderr, and return codes.
