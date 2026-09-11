import os


def test_diffs_guide_content():
    diffs_doc_path = os.path.join("docs", "how-to", "diffs.md")
    assert os.path.exists(diffs_doc_path), "docs/how-to/diffs.md must exist"
    with open(diffs_doc_path, encoding="utf-8") as f:
        content = f.read()

    # Verify key sections covering multi-commit diffing, Git vs Spec builds, and resolution
    assert "Git Commits vs. Specification Builds" in content
    assert "HEAD~1" in content
    assert "@0" in content or "@1" in content
    assert "diff main" in content


def test_repl_guide_content():
    repl_doc_path = os.path.join("docs", "how-to", "repl.md")
    assert os.path.exists(repl_doc_path), "docs/how-to/repl.md must exist"
    with open(repl_doc_path, encoding="utf-8") as f:
        content = f.read()

    # Verify key sections covering snapshot indexing and diffing in REPL
    assert "Snapshot Diffing" in content
    assert "@0" in content
    assert "@" in content or "@N" in content


def test_workflow_yaml_reference_content():
    # spec.docs.WorkflowYamlReferenceReq
    ref_path = os.path.join("docs", "reference", "workflow-yaml.md")
    assert os.path.exists(ref_path), "docs/reference/workflow-yaml.md must exist"
    with open(ref_path, encoding="utf-8") as f:
        content = f.read()

    assert "Workflow Configuration Reference" in content
    assert ".libspec/workflow.yaml" in content
    assert "hooks:" in content
    assert "post-edit" in content
    assert "post-implement" in content
    assert "pre-commit" in content
    assert "Error Resilience & Fallback" in content


def test_agent_workflow_guide_content():
    # spec.docs.AgentWorkflowGuideReq
    guide_path = os.path.join("docs", "how-to", "agent-workflow.md")
    assert os.path.exists(guide_path), "docs/how-to/agent-workflow.md must exist"
    with open(guide_path, encoding="utf-8") as f:
        content = f.read()

    assert "The 9-Step Phase-Typed Developer Agent Loop" in content
    assert "Customizing Workflow Hooks (.libspec/workflow.yaml)" in content
    assert "hooks:" in content
    assert "workflow-yaml.md" in content
