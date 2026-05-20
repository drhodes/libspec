"""
Top-level features and requirements for libspec.
"""

from .err import Feat, Req


class LibSpec(Req):
    """
    Libspec is a spec-driven development library for LLM-assisted coding.

    It provides a Python-native way to write, build, and diff structured
    specifications. Specifications are authored as Python class hierarchies
    where the class docstring is the canonical requirement text.

    The library generates versioned XML artifacts from these specs that serve
    as the source of truth for LLM-assisted code generation and cross-
    referencing between requirements and source code.

    """


class SpecDrivenDevelopment(Feat):
    """
    Specifications are the primary artifact of development.

    Source code is generated from specifications, not the other way around.
    Every component of a project should have a corresponding specification
    class that describes its behavior, requirements, and constraints. The spec
    is the contract; the implementation must satisfy it.

    The workflow is:
    1. Author or update spec classes in the spec/ directory. 2. Run `libspec
    build` to generate a versioned XML artifact. 3. Run `libspec diff` to
    surface what has changed since the last build. 4. Use the diff output as
    context for LLM-assisted code generation.

    """


class BootstrapIntegrity(Req):
    """
    Libspec must spec itself using libspec.

        The library's own spec/ directory must be kept up to date and at feature
        parity with the actual capabilities of the library. This ensures that the
        tool demonstrates the exact workflow it advocates for and that its own
        development remains disciplined.

    """


class PythonNativeAuthoring(Feat):
    """
    Specifications are written as ordinary Python classes.

    No special DSL, no separate config files. A spec class is a Python class
    that inherits from Ctx (or a Ctx-derived convenience base like Feature or
    Requirement) and carries its requirements as a class-level docstring.

    This means specs benefit from Python's class hierarchy and multiple
    inheritance for composing cross-cutting concerns (e.g. error handling,
    refactoring guidelines) into every requirement without repetition.

    """


class VersionedXmlArtifacts(Feat):
    """
    Each `libspec build` run produces a content-hashed XML file.

    The filename embeds a 20-character MD5 digest of the XML content so that
    successive builds produce distinct, traceable artifacts. A date-created
    timestamp is injected into the root element at write time.

    The XML is human-readable (pretty-printed) and carries the libspec version
    that generated it so that cross-version diffs can be detected and rejected
    safely.

    """
