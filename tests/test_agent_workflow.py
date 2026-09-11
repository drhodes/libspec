from click.testing import CliRunner

from libspec.cli import main
from libspec.mcp_server import agent_workflow


def test_cli_agent_workflow():
    runner = CliRunner()

    # 1. Test default prefix
    res = runner.invoke(main, ["agent-workflow"])
    assert res.exit_code == 0
    assert "diff" in res.output

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
    assert "diff" in res

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


def test_workflow_spec_sync_check():
    from libspec.workflow import get_agent_workflow

    workflow_out = get_agent_workflow("libspec_")
    assert "Verify Specification Sync" in workflow_out
    assert "libspec_diff" in workflow_out


def test_workflow_semver_bump():
    from libspec.workflow import get_agent_workflow

    workflow_out = get_agent_workflow("libspec_")
    assert "Version Bump" in workflow_out
    assert "pyproject.toml" in workflow_out
    assert "Semantic Versioning" in workflow_out or "SemVer" in workflow_out


def test_workflow_phase_typing_and_paradigms():
    from libspec.workflow import get_agent_workflow

    workflow_out = get_agent_workflow("libspec_")
    # Verify Phase annotations
    assert "Phase 1: Edit Spec [DECLARATIVE]" in workflow_out
    assert (
        "Phase 2: Diff Spec (MANDATORY BEFORE CODING) [DECLARATIVE -> IMPERATIVE]"
        in workflow_out
    )
    assert "Phase 3: Sort Implementation Ordering [IMPERATIVE]" in workflow_out
    assert (
        "Phase 4: Test Driven Development [IMPERATIVE - Contract Driven]"
        in workflow_out
    )
    assert "Phase 5: Implement [IMPERATIVE - Goal Directed]" in workflow_out
    assert "Phase 6: Code Quality & Verification [IMPERATIVE]" in workflow_out
    assert "Phase 7: Verify Specification Sync [DECLARATIVE]" in workflow_out
    assert "Phase 8: Version Bump [IMPERATIVE]" in workflow_out
    assert (
        "Phase 9: Author a git message and present to user [IMPERATIVE]" in workflow_out
    )


def test_workflow_hooks_all_lifecycle_phases(tmp_path):
    # spec.cli.WorkflowHooksLifecycleReq
    # spec.cli.WorkflowYamlSchemaReq
    import os

    from libspec.workflow import get_agent_workflow

    mock_yaml = """
hooks:
  post-edit: "run spec validation"
  pre-diff: "compile before diff"
  post-diff: "review delta"
  post-dependencies: "generate dag diagram"
  pre-test: "sync test fixtures"
  post-test: "check tests failed (red)"
  pre-implement: "review contract invariants"
  post-implement: "run local pytest"
  pre-commit: "run ruff format check"
  post-quality: "run radon complexity"
  post-sync: "verify zero drift"
  pre-bump: "check git status"
  post-bump: "sync uv lock"
  post-commit: "present commit summary"
"""
    libspec_dir = tmp_path / ".libspec"
    libspec_dir.mkdir(parents=True, exist_ok=True)
    (libspec_dir / "workflow.yaml").write_text(mock_yaml, encoding="utf-8")

    out = get_agent_workflow("libspec_", project_root=str(tmp_path))

    assert "run spec validation" in out
    assert "compile before diff" in out
    assert "review delta" in out
    assert "generate dag diagram" in out
    assert "sync test fixtures" in out
    assert "check tests failed (red)" in out
    assert "review contract invariants" in out
    assert "run local pytest" in out
    assert "run ruff format check" in out
    assert "run radon complexity" in out
    assert "verify zero drift" in out
    assert "check git status" in out
    assert "sync uv lock" in out
    assert "present commit summary" in out


def test_workflow_yaml_resilience(tmp_path):
    # spec.cli.WorkflowYamlResilienceReq
    from libspec.workflow import get_agent_workflow

    libspec_dir = tmp_path / ".libspec"
    libspec_dir.mkdir(parents=True, exist_ok=True)

    # 1. Corrupted / Malformed YAML
    (libspec_dir / "workflow.yaml").write_text(
        ":::bad yaml [][} invalid", encoding="utf-8"
    )
    out1 = get_agent_workflow("libspec_", project_root=str(tmp_path))
    assert "Phase 1: Edit Spec [DECLARATIVE]" in out1

    # 2. Empty file
    (libspec_dir / "workflow.yaml").write_text("", encoding="utf-8")
    out2 = get_agent_workflow("libspec_", project_root=str(tmp_path))
    assert "Phase 1: Edit Spec [DECLARATIVE]" in out2

    # 3. Non-dict hooks
    (libspec_dir / "workflow.yaml").write_text(
        "hooks: 'not a dictionary'", encoding="utf-8"
    )
    out3 = get_agent_workflow("libspec_", project_root=str(tmp_path))
    assert "Phase 1: Edit Spec [DECLARATIVE]" in out3


def test_init_scaffolds_workflow_yaml():
    # spec.cli.InitWorkflowYamlReq
    import os

    from click.testing import CliRunner

    from libspec.cli import main

    runner = CliRunner()
    with runner.isolated_filesystem():
        res = runner.invoke(main, ["init"])
        assert res.exit_code == 0
        yaml_path = os.path.join(".libspec", "workflow.yaml")
        assert os.path.exists(yaml_path)
        content = open(yaml_path, encoding="utf-8").read()
        assert "hooks:" in content
        assert "Phase 1: Edit Spec" in content
        assert "post-implement:" in content
