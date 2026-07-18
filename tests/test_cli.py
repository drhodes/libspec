import os
import subprocess
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from libspec.cli import main
from libspec.common import Component


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "libspec - unified CLI" in result.output


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "libspec" in result.output


def test_cli_init():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["init"])
        assert result.exit_code == 0
        assert "Initialized empty spec directory" in result.output
        assert os.path.exists("spec/main_spec.py")
        assert os.path.exists("spec/app.py")
        assert os.path.exists(".libspec")


def test_cli_cwd_validation_blocks_store_commands():
    runner = CliRunner()
    with runner.isolated_filesystem():
        # Without init, commands should fail
        result = runner.invoke(main, ["list"])
        assert result.exit_code != 0
        assert "not a libspec project" in result.output.lower()


def test_cli_cwd_validation_init_and_agent_config_are_exempt():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["agent-config", "--list"])
        assert result.exit_code == 0


def test_cli_list_show_search_log():
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(main, ["init"])

        mock_comp = Component(
            ref="spec.app.App",
            docstring="Application entrypoint",
            is_template=False,
            inherits=[],
            hash="a" * 64,
        )

        # 1. Test list
        with patch(
            "libspec.util.compile_live_spec",
            return_value=([mock_comp], "spec/main_spec.py"),
        ):
            list_res = runner.invoke(main, ["list"])
            assert list_res.exit_code == 0
            assert "spec.app.App" in list_res.output

        # 2. Test show
        with (
            patch(
                "libspec.util.compile_live_spec",
                return_value=([mock_comp], "spec/main_spec.py"),
            ),
            patch(
                "libspec.util.find_implementations_in_workspace",
                return_value=[{"file": "app.py", "line": 10}],
            ),
        ):
            show_res = runner.invoke(main, ["show", "spec.app.App"])
            assert show_res.exit_code == 0
            assert "Reference:   spec.app.App" in show_res.output
            assert "app.py:10" in show_res.output

        # 3. Test search
        with patch(
            "libspec.util.compile_live_spec",
            return_value=([mock_comp], "spec/main_spec.py"),
        ):
            search_res = runner.invoke(main, ["search", "entrypoint"])
            assert search_res.exit_code == 0
            assert "spec.app.App" in search_res.output

        # 4. Test log
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="a1b2c3d - derek, 2026-07-04 : Initial commit"
            )
            log_res = runner.invoke(main, ["log"])
            assert log_res.exit_code == 0
            assert "Specification Git Commit History:" in log_res.output
            assert "a1b2c3d" in log_res.output


def test_cli_dependencies():
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(main, ["init"])

        mock_comp = Component(
            ref="spec.app.App",
            docstring="App",
            is_template=False,
            inherits=[],
            hash="a" * 64,
        )
        mock_dep_comp = Component(
            ref="spec.app.Sub",
            docstring="Sub",
            is_template=False,
            inherits=["spec.app.App"],
            hash="b" * 64,
        )

        with patch(
            "libspec.util.compile_live_spec",
            return_value=([mock_comp, mock_dep_comp], "spec/main_spec.py"),
        ):
            dep_res = runner.invoke(main, ["dependencies"])
            assert dep_res.exit_code == 0
            assert "Component Dependencies for 'HEAD (Live Spec)':" in dep_res.output
            assert "spec.app.Sub" in dep_res.output
            assert "└── depends on: spec.app.App" in dep_res.output
