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


def compile_live_spec(spec_file: str | None = None):
    """Compile the live specification from a Python spec file into Component objects without writing to the store."""
    import glob
    import sys
    import inspect
    import importlib

    if not spec_file:
        candidates = (
            glob.glob(os.path.join(os.getcwd(), "spec", "main_spec.py")) +
            glob.glob(os.path.join(os.getcwd(), "*_spec.py")) +
            glob.glob(os.path.join(os.getcwd(), "spec.py")) +
            glob.glob(os.path.join(os.getcwd(), "spec", "*_spec.py"))
        )
        if not candidates:
            raise ValueError("Could not auto-discover a spec file. Please check that a specification exists.")
        spec_file = candidates[0]

    spec_file = os.path.abspath(spec_file)
    if not os.path.exists(spec_file):
        raise ValueError(f"Spec file '{spec_file}' does not exist.")

    cwd = os.getcwd()
    if spec_file.startswith(cwd):
        rel_path = os.path.relpath(spec_file, cwd)
        module_name = os.path.splitext(rel_path)[0].replace(os.path.sep, '.')
        root_dir = cwd
    else:
        root_dir = os.path.dirname(spec_file)
        module_name = os.path.splitext(os.path.basename(spec_file))[0]

    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

    # Ensure all modules under the top-level spec package (e.g. 'spec') are cleared
    # so we do not import stale cached submodules
    parts = module_name.split(".")
    base_package = parts[0]
    to_delete = [name for name in sys.modules if name == base_package or name.startswith(base_package + ".")]

    for i in range(1, len(parts)):
        parent = ".".join(parts[:i])
        if parent in sys.modules:
            p_mod = sys.modules[parent]
            p_file = getattr(p_mod, "__file__", "") or ""
            if not p_file or not p_file.startswith(root_dir):
                if parent not in to_delete:
                    to_delete.append(parent)

    for name in to_delete:
        if name in sys.modules:
            del sys.modules[name]

    try:
        module = importlib.import_module(module_name)
    except Exception as e:
        raise ValueError(f"Error loading spec file '{spec_file}': {e}")

    from libspec.spec import Spec, module_specs

    explicit_spec = None
    for _, obj in inspect.getmembers(module, inspect.isclass):
        if obj.__module__ == module_name and issubclass(obj, Spec) and obj is not Spec:
            explicit_spec = obj
            break

    if explicit_spec:
        return explicit_spec().get_components(), spec_file

    specs = module_specs(module)
    if not specs:
        raise ValueError(f"No spec classes found in '{spec_file}'.")

    class _ModuleSpec(Spec):
        def modules(self_inner):
            return [module]

    return _ModuleSpec().get_components(), spec_file

