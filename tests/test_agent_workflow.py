from click.testing import CliRunner

from libspec.cli import main
from libspec.mcp_server import agent_workflow


def test_cli_agent_workflow():
    runner = CliRunner()

    # 1. Test default prefix
    res = runner.invoke(main, ["agent-workflow"])
    assert res.exit_code == 0
    assert "libspec_diff" in res.output

    # 2. Test explicit prefix
    res = runner.invoke(main, ["agent-workflow", "--prefix", "my_prefix_"])
    assert res.exit_code == 0
    assert "my_prefix_diff" in res.output

    # 3. Test explicit agent (e.g. antigravity)
    res = runner.invoke(main, ["agent-workflow", "--agent", "antigravity"])
    assert res.exit_code == 0
    assert "mcp_libspec_diff" in res.output

    # 4. Test explicit agent (e.g. claude)
    res = runner.invoke(main, ["agent-workflow", "--agent", "claude"])
    assert res.exit_code == 0
    assert "`diff`" in res.output or " diff " in res.output


def test_mcp_agent_workflow():
    # 1. Test default prefix
    res = agent_workflow()
    assert "libspec_diff" in res

    # 2. Test explicit prefix
    res = agent_workflow(prefix="foo_")
    assert "foo_diff" in res

    # 3. Test explicit agent
    res = agent_workflow(agent="gemini")
    assert "mcp_libspec_diff" in res
