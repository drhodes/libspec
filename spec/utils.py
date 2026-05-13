'''
Utility layer: error sentinels, hashing, FQN resolution, and version helpers.
'''

from .err import Feat, Req


class UnimplementedMethod(Req):
    '''UnimplementedMethodError is a NotImplementedError subclass raised by
    abstract methods in Ctx-derived spec classes that have no default behavior.

    On construction it uses Python frame introspection to automatically include
    the calling method name and the instance class name in the error message,
    so callers get a precise diagnostic without any boilerplate in the raiser:

        def my_method(self):
            raise UnimplementedMethodError()
        # -> "Method 'my_method' is not implemented in class 'MyClass'"

    An optional `message` argument appends extra context to the auto-generated
    text. The class lives in `libspec.err` and is the only custom exception
    exported from the library.
    '''


class UtilityFunctions(Feat):
    '''`libspec.util` provides a handful of pure utility helpers used
    internally across the library.

    - `fqn(obj)`: Returns the fully qualified name of a class or instance
      as "module.qualname", used as the canonical XML ref attribute.

    - `easy_hash(text)`: Returns the MD5 hex digest of a UTF-8 string,
      used to compute the content-addressed XML filename.

    - `get_libspec_version()`: Returns the installed package version via
      `importlib.metadata`, falling back to "unknown" if unavailable.

    - `diff_two_latest(dirpath)`: (Legacy) Returns a unified diff of the
      two most-recently-modified files in a directory. Superseded by the
      richer `generate_patch` in `spec_diff.py`.
    '''


class SpecDiscovery(Feat):
    '''Module-level functions that discover and instantiate Ctx-derived classes.

    `ctx_spec_classes_in_module(module)` scans a module's members and returns
    all classes whose `__module__` attribute matches the module being inspected.
    This prevents re-emitting imported base classes like Ctx itself.

    `instantiate_module_specs(module)` calls `ctx_spec_classes_in_module` and
    returns a list of zero-argument instances, one per discovered class.

    `module_specs(mod)` is a legacy alias for `instantiate_module_specs`.
    `classes_with_ctx_superclass(module)` is a legacy alias for
    `ctx_spec_classes_in_module`.

    The `_MissingType` / `_Missing` sentinel is a private singleton used
    internally by Ctx to distinguish "no value returned" from `None`.
    '''


class DeprecatedQueryMap(Feat):
    '''`libspec.query_map` is a deprecated backwards-compatibility shim.

    Its logic was moved to `libspec.cli`. The module is kept so that
    `python -m libspec.query_map` still works for callers that have not
    yet migrated to `libspec query`. It prepends "query" to sys.argv and
    delegates to the unified CLI main().

    New code should use `libspec query <source_map> [term]` directly.
    '''
