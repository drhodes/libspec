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


def test_workflow_hooks_parsing():
    import os

    import yaml

    from libspec.workflow import get_agent_workflow

    mock_yaml_data = """
hooks:
  pre-diff:
    - "Compile project specs: `npm run spec`"
  post-implement:
    - "Run project linting: `npm run lint`"
"""
    workflow_path = ".libspec/workflow.yaml"
    os.makedirs(".libspec", exist_ok=True)

    backup_data = None
    if os.path.exists(workflow_path):
        with open(workflow_path) as f:
            backup_data = f.read()

    try:
        with open(workflow_path, "w") as f:
            f.write(mock_yaml_data)

        workflow_out = get_agent_workflow("libspec_")
        assert "Compile project specs: `npm run spec`" in workflow_out
        assert "Run project linting: `npm run lint`" in workflow_out
    finally:
        if backup_data is not None:
            with open(workflow_path, "w") as f:
                f.write(backup_data)
        else:
            if os.path.exists(workflow_path):
                os.remove(workflow_path)
