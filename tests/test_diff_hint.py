import io
import sys

from click.testing import CliRunner

from libspec.cli import main
from libspec.mcp_server import diff as mcp_diff
from libspec.repl import LibspecRepl


def test_cli_diff_head_offset_hint():
    runner = CliRunner()
    # Diff HEAD~1 against HEAD~1 (identical spec state)
    res = runner.invoke(main, ["diff", "HEAD~1", "HEAD~1"])
    assert res.exit_code == 0
    assert "No changes detected." in res.output
    assert "diff #1" in res.output
    assert "Hint" in res.output or "hint" in res.output


def test_mcp_diff_head_offset_hint():
    res = mcp_diff(commit_a="HEAD~1", commit_b="HEAD~1")
    assert "No changes detected." in res
    assert "diff #1" in res
    assert "Hint" in res or "hint" in res


def test_repl_diff_head_offset_hint(monkeypatch):
    import datetime

    from libspec.store import Snapshot

    repl = LibspecRepl()
    mock_snap = Snapshot(
        id="HEAD~1",
        created_at=datetime.datetime.now(),
        master_hash="0" * 64,
        git_commit="HEAD~1",
    )
    monkeypatch.setattr(
        repl,
        "find_build_by_id",
        lambda arg: mock_snap if "HEAD~1" in str(arg) else None,
    )
    monkeypatch.setattr(
        repl, "get_components_for_build", lambda snap: list(repl.components)
    )

    captured = io.StringIO()
    old_stdout = sys.stdout
    try:
        sys.stdout = captured
        repl.cmd_diff("HEAD~1")
    finally:
        sys.stdout = old_stdout

    output = captured.getvalue()
    assert "No changes detected." in output
    assert "diff #1" in output
    assert "Hint" in output or "hint" in output


def test_cli_diff_hash_index_resolution():
    runner = CliRunner()
    # #0 is latest spec commit (b8a05c7), diffing against itself should be No changes detected without <null spec>
    res = runner.invoke(main, ["diff", "#0", "#0"])
    assert res.exit_code == 0
    assert "No changes detected." in res.output
    assert "<null spec>" not in res.output
