"""
Core engine: Spec base class and Ctx base class.
"""

from .err import Feat, Req


class SpecBase(Req):
    """
    The Spec base class is the entry point for a project's specification set.

    Subclasses must implement `modules()` returning the list of Python modules
    that contain Ctx-derived specification classes. `Spec` discovers all such
    classes, instantiates them, and assembles them into a single XML document.

    Key responsibilities:
    - `generate_xml()`: Return the full specification as a pretty-printed XML
      string.
    - `write_xml(output_dir)`: Write the hashed XML file.
    - `handle_cli()`: Parse basic -o/--output and --xml flags for standalone
      use.
    """


class TwoPassXmlAssembly(Feat):
    """
    Specification XML is assembled in two passes to avoid eclipse bugs.

    Pass 1 emits every full spec defined directly in the listed modules, in the
    order they are discovered. This ensures that a class defined in the project
    is never silently replaced by a thin dependency stub.

    Pass 2 emits dependency stubs for inherited superspec classes that were not
    already emitted in Pass 1. Stubs carry the superspec docstring template and
    inheritance chain so that the diff engine can resolve inherited
    requirements.

    A ref-based deduplication set prevents any class from being emitted twice
    across both passes.
    """


class DependencyStub(Feat):
    """
    Inherited superspecs that are not directly listed in modules() are emitted
    as lightweight dependency stub elements.

    A stub carries:
    - type and ref attributes identifying the class.
    - A dependency="true" marker.
    - A template="true/false" flag indicating whether the docstring contains
      Jinja2 template syntax.
    - The raw docstring_template text.
    - A source element with file path and class name.
    - An inherits element listing the stub's own parent refs.

    Stubs enable the diff engine to detect changes to inherited specs even when
    those superspecs live in a separate project or artifact.
    """


class CtxBase(Req):
    """
    The Ctx base class provides the template rendering and XML serialization
    engine that every specification class inherits.

    Ctx-derived classes are discovered by `ctx_spec_classes_in_module()` which
    filters module members to those whose `__module__` matches the module being
    inspected (preventing re-emission of imported base classes).

    Key properties:
    - The class docstring is the specification text / Jinja2 template.
    - Zero-argument public methods and attributes become template variables
      that are resolved automatically at render time.
    - `ctx(template_only=True)` returns the dict of resolved template vars.
    - `to_xml_element()` produces the full <specification> XML element.
    """


class TemplateRendering(Feat):
    """
    Specification docstrings are treated as Jinja2 templates.

    Undeclared variables in the combined base+instance template are collected
    via `jinja2.meta.find_undeclared_variables`. Each variable name is mapped
    to a same-named (with hyphens replaced by underscores) method or attribute
    on the Ctx instance.

    If a required variable has no matching member, an `AttributeError` is
    raised with a precise diagnostic pointing to the spec file, line number,
    class name, variable name, and the fix needed.

    The special variable `fields` is resolved via `self.fields()` if present,
    allowing DataSchema subclasses to expose annotated field dictionaries.
    """


class InheritanceResolution(Feat):
    """
    Ctx tracks the full MRO to correctly compute inherited context.

    `_non_root_mro_classes()` returns all MRO classes excluding Ctx and object.
    `_base_template()` concatenates docstrings from all ancestor classes
    (innermost-first) into a single base template string so that inherited
    requirements are visible alongside the subclass docstring.

    `_inherited_field_values()` collects the return values of zero-argument
    methods from each inherited Ctx class to detect field overrides.
    `_detect_overrides()` compares the current instance context against
    inherited values and tags fields that have been overridden.
    """


class DeltaRequirements(Feat):
    """
    Delta requirements capture what a subclass adds beyond its parents.

    `_delta_requirements()` computes the set of context fields and docstring
    notes that differ from all ancestor classes. Only the deltas are included
    in the <delta_requirements> XML element, keeping the diff output focused on
    what is actually new.

    The `notes` key is treated specially: if the instance docstring differs
    from all inherited docstrings it is included as `notes`.
    """


class XmlSerialization(Feat):
    """
    `to_xml_element()` builds the canonical <specification> XML element.

    The element includes:
    - type (class name) and ref (fully qualified name) attributes.
    - <source> with target class name and absolute file path.
    - <docstring> rendered from the Jinja2 template with the resolved context.
    - <context> containing all resolved context fields as child elements.
    - <inherits> listing fully qualified names of ancestor specs.
    - <effective_req_ids> listing FQNs of all Requirement-derived ancestors.
    - <overrides> listing field names that override parent values.
    - <delta_requirements> containing fields that are new in this subclass.

    Nested Python values (dicts, lists) are recursively serialized to XML
    elements by `_to_xml_element()`. start_line and end_line keys are omitted
    from context to avoid noisy diffs on line number changes.
    """


class SourceInfoIntrospection(Feat):
    """
    Source file and line range are captured via Python introspection.

    `inspect.getsourcefile()` and `inspect.getsourcelines()` are used to locate
    each Ctx class in the filesystem at serialization time. The result is
    stored in the <source> element and also used in error messages for missing
    template variables.

    If introspection fails (e.g. for dynamically generated classes), the source
    element is omitted gracefully rather than raising an exception.
    """
