"""
Utility layer: error sentinels, hashing, FQN resolution, and version helpers.
"""

from .err import Feat, Req


class UnimplementedMethod(Req):
    """
    UnimplementedMethodError is a NotImplementedError subclass raised by
    abstract methods in Ctx-derived spec classes that have no default behavior.

    On construction it uses Python frame introspection to automatically include
    the calling method name and the instance class name in the error message,
    so callers get a precise diagnostic without any boilerplate in the raiser:

    def my_method(self):
    raise UnimplementedMethodError() # -> "Method 'my_method' is not
    implemented in class 'MyClass'"

    An optional `message` argument appends extra context to the auto-generated
    text. The class lives in `libspec.err` and is the only custom exception
    exported from the library.
    """


class UtilityFunctions(Feat):
    """
    `libspec.util` provides a handful of pure utility helpers used internally
    across the library.

    - `fqn(obj)`: Returns the fully qualified name of a class or instance as
      "module.qualname", used as the canonical XML ref attribute.

    - `easy_hash(text)`: Returns the MD5 hex digest of a UTF-8 string, used to
      compute the content-addressed XML filename.

    - `get_libspec_version()`: Returns the installed package version via
      `importlib.metadata`, falling back to "unknown" if unavailable.

    - `diff_two_latest(dirpath)`: (Legacy) Returns a unified diff of the two
      most-recently-modified files in a directory. Superseded by the richer
      `generate_patch` in `spec_diff.py`.
    """


class SpecDiscovery(Feat):
    """
    Module-level functions that discover and instantiate Ctx-derived classes.

    `ctx_spec_classes_in_module(module)` scans a module's members and returns
    all classes whose `__module__` attribute matches the module being
    inspected. This prevents re-emitting imported base classes like Ctx itself.

    `instantiate_module_specs(module)` calls `ctx_spec_classes_in_module` and
    returns a list of zero-argument instances, one per discovered class.

    `module_specs(mod)` is a legacy alias for `instantiate_module_specs`.
    `classes_with_ctx_superclass(module)` is a legacy alias for
    `ctx_spec_classes_in_module`.

    The `_MissingType` / `_Missing` sentinel is a private singleton used
    internally by Ctx to distinguish "no value returned" from `None`.
    """


class LibspecProjectDetection(Feat):
    """
    Utilities for detecting whether a given filesystem path is a valid,
    initialized libspec project directory.

    A directory is considered a valid libspec project if and only if a
    `.libspec/` subdirectory exists within it. The presence of `.libspec/`
    is the canonical marker created by `libspec init` and by the store
    layer on first write.

    This detection mechanism must NOT consult the `LIBSPEC_DATABASE_URL`
    environment variable or any other runtime override — the check is
    solely based on filesystem structure.
    """


class IsLibspecProject(Req):
    """
    `is_libspec_project(path: str | None = None) -> bool`

    Returns `True` if the given path (defaulting to the current working
    directory when `None`) contains a `.libspec/` subdirectory, and
    `False` otherwise.

    Requirements:
    - Accepts an optional `path` argument; when omitted, uses `os.getcwd()`.
    - Returns `True` if and only if `<path>/.libspec/` exists and is a
      directory.
    - Must not raise any exception for inaccessible or non-existent paths;
      return `False` instead.
    - Must not create, modify, or delete any filesystem entries.
    """


class LibspecProjectGuard(Req):
    """
    `require_libspec_project(path: str | None = None) -> None`

    Enforces that the current working directory is a valid libspec project.
    Raises `NotALibspecProjectError` if the check fails.

    Requirements:
    - Calls `is_libspec_project(path)` internally.
    - If the check passes, returns `None` with no side-effects.
    - If the check fails, raises `NotALibspecProjectError` with a clear,
      actionable error message that:
        1. States the directory that was checked.
        2. Tells the user to run `libspec init` to initialize a project.
    - Must not catch or suppress the raised exception.
    """


class NotALibspecProjectError(Req):
    """
    `NotALibspecProjectError` is a custom exception raised by
    `require_libspec_project()` when the current working directory does
    not contain a `.libspec/` directory.

    Requirements:
    - Must be a subclass of `Exception`.
    - Must be importable from `libspec.utils` (or `libspec.err`).
    - The exception message must include the checked directory path and a
      hint to run `libspec init`.
    """
