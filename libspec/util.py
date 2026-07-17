import difflib
import hashlib
import os
from pathlib import Path


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
        return "".join(
            difflib.unified_diff(
                f1.readlines(),
                f2.readlines(),
                fromfile=str(older),
                tofile=str(newer),
            )
        )


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


def _get_live_fingerprint(spec_file: str):
    import hashlib
    files_data = []

    # 1. Add spec_file itself
    if os.path.exists(spec_file):
        try:
            stat = os.stat(spec_file)
            files_data.append((spec_file, stat.st_mtime, stat.st_size))
        except Exception:
            pass

    # 2. Add files in spec/ directory if it exists
    spec_dir = os.path.join(os.getcwd(), "spec")
    if os.path.exists(spec_dir):
        for root, _, files in os.walk(spec_dir):
            for f in files:
                if f.endswith(".py"):
                    path = os.path.join(root, f)
                    if path != spec_file:  # avoid duplicate
                        try:
                            stat = os.stat(path)
                            files_data.append((path, stat.st_mtime, stat.st_size))
                        except Exception:
                            pass

    files_data.sort(key=lambda x: x[0])
    fingerprint_str = "|".join(f"{p}:{m}:{s}" for p, m, s in files_data)
    return hashlib.sha256(fingerprint_str.encode("utf-8")).hexdigest()


def compile_live_spec(spec_file: str | None = None):
    """Compile the live specification from a Python spec file into Component objects without writing to the store."""
    import glob
    import importlib
    import inspect
    import sys
    import marshal
    from libspec.store import Component

    if not spec_file:
        candidates = (
            glob.glob(os.path.join(os.getcwd(), "spec", "main_spec.py"))
            + glob.glob(os.path.join(os.getcwd(), "*_spec.py"))
            + glob.glob(os.path.join(os.getcwd(), "spec.py"))
            + glob.glob(os.path.join(os.getcwd(), "spec", "*_spec.py"))
        )
        if not candidates:
            raise ValueError(
                "Could not auto-discover a spec file. Please check that a specification exists."
            )
        spec_file = candidates[0]

    spec_file = os.path.abspath(spec_file)
    if not os.path.exists(spec_file):
        raise ValueError(f"Spec file '{spec_file}' does not exist.")

    fingerprint = None
    cache_file = None
    if is_libspec_project():
        try:
            fingerprint = _get_live_fingerprint(spec_file)
            cache_dir = os.path.join(os.getcwd(), ".libspec", "cache")
            cache_file = os.path.join(cache_dir, "live.bin")

            if fingerprint and os.path.exists(cache_file):
                with open(cache_file, "rb") as f:
                    cached_data = marshal.load(f)
                if cached_data.get("fingerprint") == fingerprint:
                    return [
                        Component(
                            ref=d[0],
                            docstring=d[1],
                            is_template=d[2],
                            inherits=d[3],
                            hash=d[4],
                            is_dependency=d[5],
                        )
                        for d in cached_data["components"]
                    ], spec_file
        except Exception:
            pass

    cwd = os.getcwd()
    if spec_file.startswith(cwd):
        rel_path = os.path.relpath(spec_file, cwd)
        module_name = os.path.splitext(rel_path)[0].replace(os.path.sep, ".")
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
    to_delete = [
        name
        for name in sys.modules
        if name == base_package or name.startswith(base_package + ".")
    ]

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
        components = explicit_spec().get_components()
    else:
        specs = module_specs(module)
        if not specs:
            raise ValueError(f"No spec classes found in '{spec_file}'.")

        class _ModuleSpec(Spec):
            def modules(self_inner):
                return [module]

        components = _ModuleSpec().get_components()

    # Write to cache if possible
    if fingerprint and cache_file:
        try:
            os.makedirs(os.path.dirname(cache_file), exist_ok=True)
            serialized_comps = [
                (c.ref, c.docstring, c.is_template, c.inherits, c.hash, c.is_dependency)
                for c in components
            ]
            cached_data = {"fingerprint": fingerprint, "components": serialized_comps}
            with open(cache_file, "wb") as f:
                marshal.dump(cached_data, f)
        except Exception:
            pass

    return components, spec_file


def compile_git_spec(ref: str, spec_file: str | None = None):
    """Compile spec files from a specific Git reference in memory."""
    import shutil
    import subprocess
    import tempfile
    import marshal
    from libspec.store import Component

    # Try resolving ref to a full git commit SHA to use cache
    sha = None
    try:
        res = subprocess.run(
            ["git", "rev-parse", ref],
            capture_output=True,
            text=True,
            check=True
        )
        sha = res.stdout.strip()
    except Exception:
        pass

    cache_file = None
    if sha and is_libspec_project():
        cache_dir = os.path.join(os.getcwd(), ".libspec", "cache")
        cache_file = os.path.join(cache_dir, f"{sha}.bin")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "rb") as f:
                    data = marshal.load(f)
                return [
                    Component(
                        ref=d[0],
                        docstring=d[1],
                        is_template=d[2],
                        inherits=d[3],
                        hash=d[4],
                        is_dependency=d[5],
                    )
                    for d in data
                ]
            except Exception:
                pass

    temp_dir = tempfile.mkdtemp(prefix="libspec_git_spec_")
    try:
        # Extract the 'spec' directory from the given Git ref
        try:
            subprocess.run(
                f"git archive --format=tar {ref} spec | tar -xC {temp_dir}",
                shell=True,
                check=True,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
            )
        except subprocess.CalledProcessError:
            raise ValueError(f"Could not extract 'spec' directory from git ref '{ref}'")

        orig_cwd = os.getcwd()
        os.chdir(temp_dir)
        try:
            components, _ = compile_live_spec(spec_file)

            # Write to cache if possible
            if cache_file:
                try:
                    os.makedirs(os.path.dirname(cache_file), exist_ok=True)
                    serialized = [
                        (c.ref, c.docstring, c.is_template, c.inherits, c.hash, c.is_dependency)
                        for c in components
                    ]
                    with open(cache_file, "wb") as f:
                        marshal.dump(serialized, f)
                except Exception:
                    pass

            return components
        finally:
            os.chdir(orig_cwd)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def find_implementations_in_workspace(ref: str) -> list[dict]:
    """Scan codebase files for REQUIREMENT-ID comments matching the ref."""
    import re

    claims = []
    pattern = re.compile(rf"REQUIREMENT-ID:\s*{re.escape(ref)}\b", re.IGNORECASE)

    exclude_dirs = {".git", ".venv", "build", "dist", ".mypy_cache", ".pytest_cache", ".ruff_cache", "site"}
    for root, dirs, files in os.walk(os.getcwd()):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            if not file.endswith((".py", ".sh", ".md", ".jsonl")):
                continue
            path = os.path.join(root, file)
            try:
                with open(path, encoding="utf-8", errors="ignore") as f:
                    for line_no, line in enumerate(f, 1):
                        if pattern.search(line):
                            claims.append({
                                "file": os.path.relpath(path, os.getcwd()),
                                "line": line_no
                            })
            except Exception:
                pass
    return claims


def get_git_log(all_commits: bool = False) -> list[tuple[int | None, str]]:
    """
    Retrieve Git commit log lines.
    Returns a list of tuples: (chronological_index_or_None, log_line_text)
    """
    import subprocess
    cmd = ["git", "log", "--oneline", "--decorate"]
    if not all_commits:
        cmd.extend(["-n", "20", "--", "spec/"])
        
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        lines = res.stdout.splitlines()
    except Exception:
        return []
        
    builds = []
    try:
        res_builds = subprocess.run(
            ["git", "log", "--reverse", "--format=%H %cI", "--", "spec/"],
            capture_output=True,
            text=True,
            check=True
        )
        for line in res_builds.stdout.splitlines():
            line = line.strip()
            if line:
                builds.append(line.split()[0])
    except Exception:
        pass
        
    results = []
    for line in lines:
        parts = line.strip().split()
        if not parts:
            continue
        sha_prefix = parts[0].strip().rstrip("-")
        idx = None
        for i, b in enumerate(builds):
            if b.startswith(sha_prefix):
                idx = len(builds) - 1 - i
                break
        results.append((idx, line))
    return results



