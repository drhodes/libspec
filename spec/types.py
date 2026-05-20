"""
Built-in specification vocabulary types.
"""

from .err import Feat, Req


from libspec import (
    Ctx,
    Feature,
    Requirement,
    LeafMethods,
    API,
    LibraryAPI,
    CmdLine,
    Implementation,
    UserStory,
)


class BuiltInVocabulary(Req):
    """libspec ships a library of Ctx-derived base classes that projects can
    use to structure their specifications. These are the canonical spec types
    exported from `libspec` (via the top-level __init__.py).

    Projects should import from this vocabulary and compose with multiple
    inheritance rather than writing raw Ctx classes, so that the XML output
    carries rich structured metadata for review and diff.
    """


class FeatureType(Feat):
    """Feature is a Ctx subclass for describing named product features.

    Its docstring template renders the field `feature_name`, which defaults
    to the subclass class name. Projects may override `feature_name()` to
    return a custom display name.

    Subclasses must also implement `date()` and `description()` if those
    fields appear in the template; they raise UnimplementedMethodError by
    default to force explicit overrides.
    """


class RequirementType(Feat):
    """Requirement is a Ctx subclass for describing formal requirements.

    Its docstring template renders two fields: `title` (defaults to the class
    name) and `req_id` (defaults to the fully qualified class name). The
    req_id is intended to be embedded as a comment in generated source code so
    that downstream tooling can trace generated code back to the spec source.
    """


class SystemRequirementType(Feat):
    """SystemRequirement extends Requirement with an additional note that the
    requirement is aimed at the toolchain supporting the project rather than
    product behavior.

    Use SystemRequirement for specs that constrain the build system, CI
    pipeline, packaging, or other infrastructure.
    """


class ConstraintType(Feat):
    """Constraint is a Ctx subclass for describing formal constraints.

    Its docstring template renders three fields:
    - `constraint_id`: defaults to the class name.
    - `description`: defaults to the class docstring.
    - `enforcement_logic`: must be provided by the subclass.
    """


class DefType(Feat):
    """Def is a Ctx subclass for capturing project-specific definitions
    and glossary terms.

    Its docstring template renders the field `name`, which returns the fully
    qualified class name by default.
    """


class EdgeCaseType(Feat):
    """EdgeCase is a Ctx subclass for documenting boundary conditions and
    exceptional scenarios.

    Its docstring template renders two fields: `boundary_condition` and
    `error_scenario`. Both raise UnimplementedMethodError by default and
    must be overridden by subclasses.
    """


class DataSchemaType(Feat):
    """DataSchema is a Ctx subclass for describing data models.

    Its docstring template renders `model_name` (defaults to the class name)
    and a `fields` list derived from `__annotations__`. Subclasses define
    fields using Python type annotations, which are rendered as a bullet list.
    """


class SQLite3Type(Feat):
    """SQLite3 extends DataSchema with guidance to implement the schema
    using SQLite3 and write tests verifying database behavior.

    Adds the template field `dbpath` requiring subclasses to specify
    the database file location.
    """


class PeeWeeType(Feat):
    """PeeWee extends DataSchema with guidance to implement the schema
    using the PeeWee ORM and write tests verifying database behavior.

    Adds the template field `dbpath` requiring subclasses to specify
    the database file location.
    """


class APIType(Feat):
    """API is a Ctx subclass (also mixing in LeafMethods) for specifying
    class-level APIs.

    Its docstring template enumerates all zero-argument and single-argument
    public methods defined directly on the subclass (via LeafMethods), showing
    each method name, parameter list, and its docstring description.

    `api_name()` defaults to the class name. `constraints()` returns an
    empty list by default; subclasses may override to add constraint strings.

    LeafMethods inspects the leaf class `__dict__` (not inherited members) to
    avoid duplicating inherited method listings.
    """


class LibraryAPIType(Feat):
    """LibraryAPI extends API with a version display and the clarification
    that this is a library API, not a network API.

    Subclasses must implement `version()`.
    """


class RestMixinType(Feat):
    """RestMixin is a plain Ctx mixin carrying the guidance to develop a REST
    API with best practices around the interface.

    Mix RestMixin into an API subclass to layer REST-specific guidance onto
    an existing API specification.
    """


class CmdLineType(Feat):
    """CmdLine is a Ctx subclass (also mixing in LeafMethods) for specifying
    command-line interfaces.

    Its docstring template enumerates all public methods on the leaf class,
    showing the command name, parameter list, description, and a live preview
    of the return value obtained by calling the method with None arguments.
    """


class ImplementationType(Feat):
    """Implementation extends Requirement with guidance that implementations
    must include tests and specifies the target directory.

    The template field `implementation_directory` must be provided by the
    subclass to indicate where generated files should live.
    """


class UserStoryType(Feat):
    """UserStory extends Feature with a structured user story template.

    The template uses single-brace placeholder syntax (not Jinja2 double-brace)
    as a documentation convention. Fields like brief-title, priority,
    user-journey, explanation, and acceptance scenarios are filled in by the
    spec author as free text in the subclass docstring rather than resolved
    from Python methods.
    """


class LeafMethodsMixin(Feat):
    """LeafMethods is a plain Python mixin (not Ctx-derived) that provides
    method introspection for API and CmdLine spec classes.

    `methods()` returns a list of descriptor dicts for every public function
    defined directly in the leaf class `__dict__` (not inherited members),
    preventing duplicate listings of inherited methods.

    Each descriptor contains:
    - `name`: the method name.
    - `params`: parameter names excluding "self".
    - `description`: the cleaned docstring of the function.
    - `result`: a live preview obtained by calling the method with None
      arguments (for zero- and single-argument methods).
    - `source_ref`: source file and line range from `_source_info()`.

    API and CmdLine both inherit from both Ctx and LeafMethods via multiple
    inheritance. The `methods` attribute is consumed by their Jinja2 docstring
    templates to enumerate endpoints or commands.
    """
