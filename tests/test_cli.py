import pytest
from click.testing import CliRunner
from libspec.cli import main

def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "unified CLI for spec-driven development" in result.output
    assert "build" in result.output
    assert "diff" in result.output
    assert "init" in result.output

def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "libspec, version" in result.output

def test_cli_init():
    runner = CliRunner()
    with runner.isolated_filesystem():
        import os
        os.makedirs(".git")
        result = runner.invoke(main, ["init"])
        assert result.exit_code == 0
        
        assert os.path.exists("spec")
        assert os.path.exists("spec/__init__.py")
        assert os.path.exists("spec/main_spec.py")
        assert os.path.exists("spec/app.py")
        assert os.path.exists("spec/err.py")
        
        # Verify Git hook installation
        assert os.path.exists(".git/hooks/post-commit")
        with open(".git/hooks/post-commit", "r") as f:
            hook_content = f.read()
        assert "libspec automated VCS linking hook" in hook_content
        
        # Verify hook is executable (on Unix/Linux systems)
        import stat
        assert (os.stat(".git/hooks/post-commit").st_mode & stat.S_IEXEC) != 0
        
        with open("spec/err.py", "r", encoding="utf-8") as f:
            err_content = f.read()
            
        # Verify it copied templates/err.py which includes DefensiveProgramming, Refactor, Robustness
        assert "class DefensiveProgramming" in err_content
        assert "class Robustness" in err_content
        assert "class Refactor" in err_content

def test_cli_link():
    runner = CliRunner()
    with runner.isolated_filesystem():
        # 1. Initialize empty spec
        runner.invoke(main, ["init"])
        
        # 2. Build the spec (compiles into .libspec/libspec.jsonl)
        build_result = runner.invoke(main, ["build", "spec/main_spec.py"])
        assert build_result.exit_code == 0
        
        # 3. Get the latest snapshot ID from the store
        from libspec.store import get_store
        store = get_store()
        snap = store.current_snapshot()
        assert snap is not None
        assert snap.git_commit is None
        
        # 4. Use CLI to link it to a revision
        link_result = runner.invoke(main, [
            "link",
            "--vcs", "git",
            "--revision", "abc123commit",
            "--metadata", "branch=feat/link",
            "--metadata", "author=antigravity"
        ])
        assert link_result.exit_code == 0
        assert "Successfully linked snapshot" in link_result.output
        
        # 5. Reload the store and verify late-binding resolved the new commit
        store2 = get_store()
        snap2 = store2.current_snapshot()
        assert snap2 is not None
        assert snap2.id == snap.id
        assert snap2.git_commit == "abc123commit"


def test_cli_link_multiple_pending():
    runner = CliRunner()
    with runner.isolated_filesystem():
        # 1. Initialize empty spec
        runner.invoke(main, ["init"])
        
        # 2. Build the first snapshot
        runner.invoke(main, ["build", "spec/main_spec.py"])
        
        # 3. Dynamically modify spec/app.py to change spec content and force a second distinct snapshot
        with open("spec/app.py", "a", encoding="utf-8") as f:
            f.write("\n\nclass DummyFeature(Req):\n    \"\"\"A new temporary feature requirement.\"\"\"\n")
            
        # Clear Python sys.modules cache to force a fresh re-import of spec modules
        import sys
        for m in list(sys.modules.keys()):
            if m.startswith("spec"):
                del sys.modules[m]
            
        # 4. Build the second snapshot

        runner.invoke(main, ["build", "spec/main_spec.py"])
        
        from libspec.store import get_store
        store = get_store()
        snapshots = store.list_snapshots()
        assert len(snapshots) == 2
        for s in snapshots:
            assert s.git_commit is None
            
        # 5. Call link without --snapshot
        link_result = runner.invoke(main, [
            "link",
            "--vcs", "git",
            "--revision", "commit777",
            "--metadata", "hook=test"
        ])
        assert link_result.exit_code == 0
        assert "Successfully linked 2 snapshots" in link_result.output
        
        # 6. Verify both are successfully linked
        store2 = get_store()
        snapshots2 = store2.list_snapshots()
        assert len(snapshots2) == 2
        for s in snapshots2:
            assert s.git_commit == "commit777"



