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


def test_repl_diff_head_offset_hint():
    repl = LibspecRepl()
    # Force components to match old_snap to simulate zero pending drift
    old_snap = repl.find_build_by_id("HEAD~1")
    repl.components = repl.get_components_for_build(old_snap)

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
