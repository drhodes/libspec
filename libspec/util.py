import hashlib
import os
from pathlib import Path
import difflib

def easy_hash(text):
    return hashlib.md5(text.encode()).hexdigest()

def fqn(obj):
    if isinstance(obj, type):
        return f"{obj.__module__}.{obj.__qualname__}"
    return f"{type(obj).__module__}.{type(obj).__qualname__}"
        

def diff_two_latest(dirpath):
    files = [p for p in Path(dirpath).iterdir() if p.is_file()]
    if len(files) < 2:
        raise ValueError("Need at least two files")

    latest = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[:2]
    newer, older = latest[0], latest[1]

    with older.open() as f1, newer.open() as f2:
        return "".join(difflib.unified_diff(
            f1.readlines(),
            f2.readlines(),
            fromfile=str(older),
            tofile=str(newer),
        ))

def get_libspec_version():
    import importlib.metadata
    try:
        return importlib.metadata.version("libspec")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


# ---------------------------------------------------------------------------
# spec.utils.NotALibspecProjectError
# spec.utils.IsLibspecProject
# spec.utils.LibspecProjectGuard
# ---------------------------------------------------------------------------

class NotALibspecProjectError(Exception):
    """
    Raised when the current working directory is not a valid libspec project.

    A valid libspec project must contain a `.libspec/` subdirectory.
    Run `libspec init` to initialize a new project.
    """


def is_libspec_project(path: str | None = None) -> bool:
    """
    Return True if `path` (defaulting to CWD) contains a `.libspec/` directory.

    Never raises — returns False for inaccessible or non-existent paths.
    Does not consult LIBSPEC_DATABASE_URL or any other env override.
    """
    # spec.utils.IsLibspecProject
    try:
        root = path if path is not None else os.getcwd()
        marker = os.path.join(root, ".libspec")
        return os.path.isdir(marker)
    except Exception:
        return False


def require_libspec_project(path: str | None = None) -> None:
    """
    Raise NotALibspecProjectError if the directory is not a libspec project.

    Args:
        path: Directory to check; defaults to CWD when None.
    """
    # spec.utils.LibspecProjectGuard
    root = path if path is not None else os.getcwd()
    if not is_libspec_project(root):
        raise NotALibspecProjectError(
            f"'{root}' is not a libspec project directory "
            f"(no .libspec/ folder found).\n"
            f"Run 'libspec init' to initialize a project here."
        )
