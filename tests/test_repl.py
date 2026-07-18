import subprocess
from unittest.mock import MagicMock, patch

from libspec.common import Component
from libspec.repl import LibspecRepl


def test_repl_init():
    with patch(
        "libspec.util.compile_live_spec",
        return_value=([], "spec/main_spec.py"),
    ):
        repl = LibspecRepl()
        assert isinstance(repl.components, list)
        assert isinstance(repl.fqns, set)


def test_repl_welcome(capsys):
    with patch(
        "libspec.util.compile_live_spec",
        return_value=([], "spec/main_spec.py"),
    ):
        repl = LibspecRepl()
        repl._print_welcome()
        out = capsys.readouterr().out
        assert "Backend : Git-Native (Stateless)" in out
        assert "Context : Live Workspace" in out


def test_repl_enter_leave(capsys):
    import datetime

    from libspec.common import Snapshot

    with patch(
        "libspec.util.compile_live_spec",
        return_value=([], "spec/main_spec.py"),
    ):
        repl = LibspecRepl()
        # Enter valid ref
        mock_snap = Snapshot(
            id="HEAD~1",
            created_at=datetime.datetime.now(),
            master_hash="a" * 64,
            git_commit="HEAD~1",
        )
        with (
            patch(
                "libspec.repl.LibspecRepl._make_snapshot_from_git",
                return_value=mock_snap,
            ),
            patch("libspec.util.compile_git_spec", return_value=[]),
        ):
            res = repl.commander.run("enter HEAD~1", repl)
            assert res is True
            assert repl.active_build == mock_snap
            assert repl.active_session_id == mock_snap

        # Leave ref
        res = repl.commander.run("leave", repl)
        assert res is True
        assert repl.active_build is None
        assert repl.active_session_id == "HEAD"


def test_repl_log(capsys):
    with patch(
        "libspec.util.compile_live_spec",
        return_value=([], "spec/main_spec.py"),
    ):
        repl = LibspecRepl()
        with patch.object(
            repl, "_get_chronological_builds", return_value=["a1b2c3d4e5f6"]
        ):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0, stdout="a1b2c3d - derek, 2026-07-04 : Initial commit"
                )
                res = repl.commander.run("log", repl)
                assert res is True
                out = capsys.readouterr().out
                assert "Specification Git Commit History" in out
                assert "[#0]" in out
                assert "a1b2c3d" in out


def test_repl_dependencies(capsys):
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
        repl = LibspecRepl()
        res = repl.commander.run("dependencies", repl)
        assert res is True
        out = capsys.readouterr().out
        assert "Component Dependencies for 'HEAD':" in out
        assert "spec.app.Sub" in out
        assert "└── depends on: spec.app.App" in out


def test_repl_show_claims(capsys):
    mock_comp = Component(
        ref="spec.app.App",
        docstring="App",
        is_template=False,
        inherits=[],
        hash="a" * 64,
    )
    with patch(
        "libspec.util.compile_live_spec",
        return_value=([mock_comp], "spec/main_spec.py"),
    ):
        repl = LibspecRepl()
        with patch(
            "libspec.util.find_implementations_in_workspace",
            return_value=[{"file": "app.py", "line": 42}],
        ):
            res = repl.commander.run("show spec.app.App", repl)
            assert res is True
            out = capsys.readouterr().out
            assert "Reference:   spec.app.App" in out
            assert "Implementation Claims (1):" in out
            assert "app.py:42" in out


def test_repl_autocompletion():
    from unittest.mock import MagicMock, patch

    from prompt_toolkit.document import Document

    from libspec.repl import LibspecCompleter, LibspecRepl

    with patch(
        "libspec.util.compile_live_spec",
        return_value=([], "spec/main_spec.py"),
    ):
        repl = LibspecRepl()
        completer = LibspecCompleter(repl)

        # Mock git log execution inside _get_chronological_builds and log command run
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="c927651c92\n78d7cd378d\n"
            )
            # 1. Test completing when entering "enter " with no prefix (word is empty)
            doc_empty = Document(text="enter ", cursor_position=6)
            completions = list(completer.get_completions(doc_empty, None))
            assert len(completions) > 0
            assert any(c.text == "c927651c92" for c in completions)

            # 2. Test completing when typing a prefix
            doc_prefix = Document(text="enter c9", cursor_position=8)
            completions_prefix = list(completer.get_completions(doc_prefix, None))
            assert len(completions_prefix) > 0
            assert completions_prefix[0].text == "c927651c92"


def test_repl_git_history_filtering():
    with patch(
        "libspec.util.compile_live_spec",
        return_value=([], "spec/main_spec.py"),
    ):
        repl = LibspecRepl()
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="a1b2c3d4e5f6 2026-07-17T12:00:00Z\n"
            )
            builds = repl._get_chronological_builds()
            assert builds == ["a1b2c3d4e5f6"]

            args = mock_run.call_args[0][0]
            assert "git" in args
            assert "log" in args
            assert "--" in args
            assert "spec/" in args


def test_repl_log_all_commits(capsys):
    with patch(
        "libspec.util.compile_live_spec",
        return_value=([], "spec/main_spec.py"),
    ):
        repl = LibspecRepl()
        with patch.object(
            repl, "_get_chronological_builds", return_value=["a1b2c3d4e5f6"]
        ):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0, stdout="a1b2c3d - derek, 2026-07-04 : Initial commit"
                )
                res = repl.commander.run("log -a", repl)
                assert res is True
                args = mock_run.call_args_list[0][0][0]
                assert "--" not in args
                assert "spec/" not in args
                assert "-n" not in args
