"""
Tests for the libspec CWD project detection utilities.
Covers spec.utils.IsLibspecProject, spec.utils.LibspecProjectGuard,
and spec.utils.NotALibspecProjectError.
"""
import pytest
from libspec.util import (
    is_libspec_project,
    require_libspec_project,
    NotALibspecProjectError,
)


def test_is_libspec_project_true(tmp_path):
    """Returns True when .libspec/ exists inside the path."""
    (tmp_path / ".libspec").mkdir()
    assert is_libspec_project(str(tmp_path)) is True


def test_is_libspec_project_false_no_dir(tmp_path):
    """Returns False when .libspec/ does not exist."""
    assert is_libspec_project(str(tmp_path)) is False


def test_is_libspec_project_false_file_not_dir(tmp_path):
    """Returns False when .libspec exists but is a file, not a directory."""
    (tmp_path / ".libspec").write_text("not a dir")
    assert is_libspec_project(str(tmp_path)) is False


def test_is_libspec_project_nonexistent_path():
    """Returns False (not raises) for a path that doesn't exist."""
    assert is_libspec_project("/this/path/does/not/exist/ever") is False


def test_is_libspec_project_defaults_to_cwd(tmp_path, monkeypatch):
    """When path=None, checks the current working directory."""
    monkeypatch.chdir(tmp_path)
    assert is_libspec_project() is False
    (tmp_path / ".libspec").mkdir()
    assert is_libspec_project() is True


def test_require_libspec_project_passes(tmp_path):
    """Does not raise when .libspec/ is present."""
    (tmp_path / ".libspec").mkdir()
    require_libspec_project(str(tmp_path))  # must not raise


def test_require_libspec_project_raises(tmp_path):
    """Raises NotALibspecProjectError when .libspec/ is absent."""
    with pytest.raises(NotALibspecProjectError) as exc_info:
        require_libspec_project(str(tmp_path))
    msg = str(exc_info.value)
    assert str(tmp_path) in msg, "Error message should include the checked path"
    assert "libspec init" in msg, "Error message should hint at 'libspec init'"


def test_not_a_libspec_project_error_is_exception():
    """NotALibspecProjectError must be a subclass of Exception."""
    assert issubclass(NotALibspecProjectError, Exception)


def test_require_libspec_project_defaults_to_cwd(tmp_path, monkeypatch):
    """When path=None, require_libspec_project checks CWD."""
    monkeypatch.chdir(tmp_path)
    with pytest.raises(NotALibspecProjectError):
        require_libspec_project()

    (tmp_path / ".libspec").mkdir()
    require_libspec_project()  # must not raise now
