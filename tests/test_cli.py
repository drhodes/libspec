from click.testing import CliRunner

from libspec.cli import main


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "unified CLI for spec-driven development" in result.output
    assert "  snapshot  " not in result.output
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

        # init must create the .libspec/ project marker directory
        assert os.path.exists(".libspec"), ".libspec/ must be created by 'libspec init'"

        # Verify Git hook installation
        assert os.path.exists(".git/hooks/post-commit")
        with open(".git/hooks/post-commit") as f:
            hook_content = f.read()
        assert "libspec automated VCS linking hook" in hook_content

        # Verify hook is executable (on Unix/Linux systems)
        import stat

        assert (os.stat(".git/hooks/post-commit").st_mode & stat.S_IEXEC) != 0

        with open("spec/err.py", encoding="utf-8") as f:
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

        # 2. Programmatically save a snapshot
        from libspec.store import Component, get_store

        store = get_store()
        comp = Component(
            ref="spec.app.App",
            docstring="Application entrypoint",
            is_template=False,
            inherits=[],
            hash="a" * 64,
        )
        snap = store.store_snapshot([comp])
        assert snap is not None
        assert snap.git_commit is None

        # 3. Use CLI to link it to a revision
        link_result = runner.invoke(
            main,
            [
                "link",
                "--vcs",
                "git",
                "--revision",
                "abc123commit",
                "--metadata",
                "branch=feat/link",
                "--metadata",
                "author=antigravity",
            ],
        )
        assert link_result.exit_code == 0
        assert "Successfully linked snapshot" in link_result.output

        # 4. Reload the store and verify late-binding resolved the new commit
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

        # 2. Programmatically save the first snapshot
        from libspec.store import Component, get_store

        store = get_store()
        comp_a = Component(
            ref="spec.app.App",
            docstring="Application entrypoint",
            is_template=False,
            inherits=[],
            hash="a" * 64,
        )
        store.store_snapshot([comp_a])

        # 3. Programmatically save the second snapshot
        comp_b = Component(
            ref="spec.app.App",
            docstring="Application entrypoint",
            is_template=False,
            inherits=[],
            hash="b" * 64,
        )
        store.store_snapshot([comp_b])

        snapshots = store.list_snapshots()
        assert len(snapshots) == 2
        for s in snapshots:
            assert s.git_commit is None

        # 4. Call link without --snapshot
        link_result = runner.invoke(
            main,
            [
                "link",
                "--vcs",
                "git",
                "--revision",
                "commit777",
                "--metadata",
                "hook=test",
            ],
        )
        assert link_result.exit_code == 0
        assert "Successfully linked 2 snapshots" in link_result.output

        # 5. Verify both are successfully linked
        store2 = get_store()
        snapshots2 = store2.list_snapshots()
        assert len(snapshots2) == 2
        for s in snapshots2:
            assert s.git_commit == "commit777"


def test_cli_list_show_search_snapshots_log():
    runner = CliRunner()
    with runner.isolated_filesystem():
        # 1. Initialize
        runner.invoke(main, ["init"])

        # 2. Programmatically save a snapshot
        from libspec.store import Component, get_store

        store = get_store()
        comp = Component(
            ref="spec.app.App",
            docstring="Application entrypoint",
            is_template=False,
            inherits=[],
            hash="a" * 64,
        )
        store.store_snapshot([comp])

        # 3. Test list command
        list_res = runner.invoke(main, ["list"])
        assert list_res.exit_code == 0
        assert "spec.app.App" in list_res.output

        # 4. Test show command
        show_res = runner.invoke(main, ["show", "spec.app.App"])
        assert show_res.exit_code == 0
        assert "Reference:" in show_res.output
        assert "spec.app.App" in show_res.output

        # 5. Test search command
        search_res = runner.invoke(main, ["search", "App"])
        assert search_res.exit_code == 0
        assert "spec.app.App" in search_res.output

        # 6. Test list-snapshots command
        snapshots_res = runner.invoke(main, ["list-snapshots"])
        assert snapshots_res.exit_code == 0
        assert "#0" in snapshots_res.output

        # 7. Test log command
        log_res = runner.invoke(main, ["log"])
        assert log_res.exit_code == 0
        assert "SNAPSHOT" in log_res.output


def test_cli_agent_config():
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Test --list option
        list_res = runner.invoke(main, ["agent-config", "--list"])
        assert list_res.exit_code == 0
        assert "antigravity" in list_res.output.lower()

        # Test configuring gemini
        gemini_res = runner.invoke(main, ["agent-config", "gemini", "."])
        assert gemini_res.exit_code == 0
        assert (
            "settings.json" in gemini_res.output or "cli" in gemini_res.output.lower()
        )
        import os

        assert os.path.exists(".gemini/settings.json")


def test_cli_cwd_validation_blocks_store_commands():
    """Store-dependent commands must error when .libspec/ is absent (spec.cli.CwdValidation)."""
    runner = CliRunner()
    store_commands = [
        ["diff"],
        ["list"],
        ["list-snapshots"],
        ["log"],
        ["declare-dependency", "A", "B"],
        ["dependencies"],
    ]
    with runner.isolated_filesystem():
        # No init — no .libspec/ directory
        for cmd in store_commands:
            result = runner.invoke(main, cmd)
            assert result.exit_code != 0, (
                f"Command {cmd} should fail outside a libspec project, got exit {result.exit_code}"
            )
            assert ".libspec" in result.output or "libspec init" in result.output, (
                f"Command {cmd} error message should mention .libspec or libspec init, got: {result.output!r}"
            )


def test_cli_cwd_validation_init_and_agent_config_are_exempt():
    """init and agent-config must NOT require a .libspec/ directory."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        # init works without .libspec/
        result = runner.invoke(main, ["init"])
        assert result.exit_code == 0, (
            f"init should work without .libspec/, got: {result.output!r}"
        )

    with runner.isolated_filesystem():
        # agent-config --list works without .libspec/
        result = runner.invoke(main, ["agent-config", "--list"])
        assert result.exit_code == 0, (
            f"agent-config --list should work without .libspec/, got: {result.output!r}"
        )


def test_cli_self_healing_bypassed_in_non_project():
    """Verify that Git hook and agent skill self-healing is bypassed outside a project."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Setup: Create .git and .gemini/antigravity/mcp_config.json, but NO .libspec/ directory
        import os

        os.makedirs(".git")
        os.makedirs(".gemini/antigravity")
        with open(".gemini/antigravity/mcp_config.json", "w") as f:
            f.write("{}")

        # Invoke CLI group main with a command like repl (which executes main() but fails due to no .libspec/)
        result = runner.invoke(main, ["repl"])
        assert result.exit_code != 0

        # Assert no self-healing logs were printed to stdout or stderr
        assert "[libspec] Installed/Healed" not in result.output
        assert "[libspec] Auto-healed" not in result.output

        # Assert no post-commit hook script was created in .git/hooks/
        assert not os.path.exists(".git/hooks/post-commit")


def test_cli_dependencies():
    runner = CliRunner()
    with runner.isolated_filesystem():
        # 1. Initialize
        runner.invoke(main, ["init"])

        # 2. Declare dependency
        res = runner.invoke(main, ["declare-dependency", "A", "B"])
        assert res.exit_code == 0
        assert "Successfully declared dependency" in res.output

        # 3. List dependency
        res_list = runner.invoke(main, ["dependencies"])
        assert res_list.exit_code == 0
        assert "A" in res_list.output
        assert "depends on: B" in res_list.output

        # 4. Check for invalid snapshot
        res_invalid = runner.invoke(main, ["dependencies", "-s", "invalid_snap"])
        assert res_invalid.exit_code != 0
        assert "Snapshot 'invalid_snap' not found." in res_invalid.output


def test_cli_link_only_on_changes_success():
    from unittest.mock import MagicMock, patch

    runner = CliRunner()

    # Test Case 1: Both spec and code files modified -> should link successfully
    with runner.isolated_filesystem():
        runner.invoke(main, ["init"])
        from libspec.store import Component, get_store

        store = get_store()
        comp = Component(
            ref="spec.app.App",
            docstring="App entrypoint",
            is_template=False,
            inherits=[],
            hash="a" * 64,
        )
        store.store_snapshot([comp])

        with patch("subprocess.run") as mock_run:
            mock_res = MagicMock()
            mock_res.stdout = "spec/app.py\nlibspec/cli.py\n"
            mock_run.return_value = mock_res

            res = runner.invoke(
                main, ["link", "--revision", "commit123", "--only-on-changes"]
            )
            assert res.exit_code == 0
            assert "Successfully linked snapshot" in res.output

            # Verify snapshot git_commit is updated
            store2 = get_store()
            snap2 = store2.current_snapshot()
            assert snap2.git_commit == "commit123"


def test_cli_link_only_on_changes_skip_spec_only():
    from unittest.mock import MagicMock, patch

    runner = CliRunner()

    # Test Case 2: Only spec files modified -> should skip linking
    with runner.isolated_filesystem():
        runner.invoke(main, ["init"])
        from libspec.store import Component, get_store

        store = get_store()
        comp = Component(
            ref="spec.app.App",
            docstring="App entrypoint",
            is_template=False,
            inherits=[],
            hash="a" * 64,
        )
        store.store_snapshot([comp])

        with patch("subprocess.run") as mock_run:
            mock_res = MagicMock()
            mock_res.stdout = "spec/app.py\n"
            mock_run.return_value = mock_res

            res = runner.invoke(
                main, ["link", "--revision", "commit123", "--only-on-changes"]
            )
            assert res.exit_code == 0
            assert "Successfully linked" not in res.output

            # Verify snapshot git_commit is NOT updated
            store2 = get_store()
            snap2 = store2.current_snapshot()
            assert snap2.git_commit is None


def test_cli_link_only_on_changes_skip_code_only():
    from unittest.mock import MagicMock, patch

    runner = CliRunner()

    # Test Case 3: Only code files modified -> should skip linking
    with runner.isolated_filesystem():
        runner.invoke(main, ["init"])
        from libspec.store import Component, get_store

        store = get_store()
        comp = Component(
            ref="spec.app.App",
            docstring="App entrypoint",
            is_template=False,
            inherits=[],
            hash="a" * 64,
        )
        store.store_snapshot([comp])

        with patch("subprocess.run") as mock_run:
            mock_res = MagicMock()
            mock_res.stdout = "libspec/cli.py\n"
            mock_run.return_value = mock_res

            res = runner.invoke(
                main, ["link", "--revision", "commit123", "--only-on-changes"]
            )
            assert res.exit_code == 0
            assert "Successfully linked" not in res.output

            # Verify snapshot git_commit is NOT updated
            store2 = get_store()
            snap2 = store2.current_snapshot()
            assert snap2.git_commit is None
