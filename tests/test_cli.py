from reviewerloop.cli import (
    CommandResult,
    build_reviewer_prompt,
    build_writer_prompt,
    load_config,
    list_open_issues,
    markdown_h1_section,
    trim,
)


def test_markdown_h1_section_extracts_until_next_h1():
    markdown = """# Intro
ignore
# Reviewer's instructions
Be sharp.

## Detail
Keep this.
# Writer's instructions
Be small.
"""

    assert markdown_h1_section(markdown, "Reviewer's instructions") == "Be sharp.\n\n## Detail\nKeep this."
    assert markdown_h1_section(markdown, "Writer's instructions") == "Be small."


def test_load_config_returns_reviewer_and_writer_sections(tmp_path):
    config = tmp_path / "reviewerloop.md"
    config.write_text(
        "# Reviewer's instructions\nFocus on edge cases.\n"
        "# Writer's instructions\nPrefer the smallest fix.\n"
    )

    assert load_config(config) == ("Focus on edge cases.", "Prefer the smallest fix.")


def test_config_sections_are_added_to_prompts(tmp_path):
    reviewer_prompt = build_reviewer_prompt(
        tmp_path,
        tmp_path / "issues" / "open",
        tmp_path / "issues" / "closed",
        "pytest -q",
        1,
        "Focus on invariants.",
    )
    writer_prompt = build_writer_prompt(
        tmp_path,
        tmp_path / "issues" / "open",
        "pytest -q",
        CommandResult(1, "failed", ""),
        "Touch only production code.",
    )

    assert "Additional reviewer instructions from config:" in reviewer_prompt
    assert "Focus on invariants." in reviewer_prompt
    assert "Additional writer instructions from config:" in writer_prompt
    assert "Touch only production code." in writer_prompt


def test_list_open_issues_returns_markdown_files_from_open_dir(tmp_path):
    open_dir = tmp_path / "issues" / "open"
    closed_dir = tmp_path / "issues" / "closed"
    open_dir.mkdir(parents=True)
    closed_dir.mkdir(parents=True)
    (open_dir / "open.md").write_text("# Open\n")
    (closed_dir / "closed.md").write_text("# Closed\n")
    (open_dir / "notes.txt").write_text("not an issue\n")

    assert list_open_issues(open_dir) == ["open.md"]


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

    config = tmp_path / "instructions.md"
    config.write_text("# Reviewer's instructions\nUse config reviewer text.\n# Writer's instructions\nUse config writer text.\n")

    rc = main([
        "run",
        "--project",
        str(tmp_path),
        "--config",
        str(config),
        "--reviewer",
        f"{shlex.quote(sys.executable)} {shlex.quote(str(reviewer))}",
        "--writer",
        f"{shlex.quote(sys.executable)} {shlex.quote(str(reviewer))}",
        "--test-cmd",
        f"{shlex.quote(sys.executable)} -c pass",
        "--max-cycles",
        "1",
    ])

    issues_dir = tmp_path / ".reviewerloop" / "issues"
    assert rc == 0
    assert (tmp_path / ".reviewerloop" / "state.json").exists()
    assert "Use config reviewer text." in (tmp_path / ".reviewerloop" / "runs" / "001" / "reviewer.prompt.md").read_text()
    assert (issues_dir / "open").is_dir()
    assert (issues_dir / "closed").is_dir()
    assert not list((issues_dir / "open").glob("*.md"))


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
