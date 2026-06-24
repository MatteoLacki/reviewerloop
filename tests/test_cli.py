from reviewerloop.cli import CommandResult, issue_status, list_open_issues, trim


def test_issue_status_reads_frontmatter_style_status(tmp_path):
    issue = tmp_path / "RL-0001.md"
    issue.write_text("status: resolved\n\n# Fixed\n")

    assert issue_status(issue) == "resolved"


def test_list_open_issues_excludes_resolved_files(tmp_path):
    (tmp_path / "open.md").write_text("status: open\n")
    (tmp_path / "done.md").write_text("status: resolved\n")

    assert list_open_issues(tmp_path) == ["open.md"]


def test_trim_keeps_tail_of_long_output():
    text = "abc" * 10

    assert trim(text, limit=9) == "abcabcabc"


def test_command_result_combines_stdout_and_stderr():
    result = CommandResult(1, "out", "err")

    assert result.combined_output == "out\nerr"


def test_run_loop_stops_when_reviewer_finds_no_issues(tmp_path):
    import shlex
    import sys

    from reviewerloop.cli import main

    reviewer = tmp_path / "reviewer.py"
    reviewer.write_text("import sys; sys.stdin.read()\n")

    rc = main([
        "run",
        "--project",
        str(tmp_path),
        "--reviewer",
        f"{shlex.quote(sys.executable)} {shlex.quote(str(reviewer))}",
        "--writer",
        f"{shlex.quote(sys.executable)} {shlex.quote(str(reviewer))}",
        "--test-cmd",
        f"{shlex.quote(sys.executable)} -c pass",
        "--max-cycles",
        "1",
    ])

    assert rc == 0
    assert (tmp_path / ".reviewerloop" / "state.json").exists()
    assert not list((tmp_path / ".reviewerloop" / "issues").glob("*.md"))


def test_run_loop_stops_when_reviewer_command_fails(tmp_path):
    import json
    import shlex
    import sys

    from reviewerloop.cli import main

    reviewer = tmp_path / "reviewer.py"
    reviewer.write_text("import sys; sys.stdin.read(); sys.exit(7)\n")
    writer = tmp_path / "writer.py"
    writer.write_text("raise SystemExit(0)\n")

    rc = main([
        "run",
        "--project",
        str(tmp_path),
        "--reviewer",
        f"{shlex.quote(sys.executable)} {shlex.quote(str(reviewer))}",
        "--writer",
        f"{shlex.quote(sys.executable)} {shlex.quote(str(writer))}",
        "--test-cmd",
        f"{shlex.quote(sys.executable)} -c pass",
        "--max-cycles",
        "1",
    ])

    state = json.loads((tmp_path / ".reviewerloop" / "state.json").read_text())
    assert rc == 7
    assert state["cycles"] == [state["cycles"][0]]
    assert state["cycles"][0]["failed_role"] == "reviewer"
    assert not (tmp_path / ".reviewerloop" / "runs" / "001" / "tests.after-review.returncode.txt").exists()
