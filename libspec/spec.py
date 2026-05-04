import inspect
import os
import ast
import json
import argparse
import importlib.metadata
import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom
from jinja2 import Environment, meta, Template
from inspect import signature, cleandoc, isfunction
from libspec.err import UnimplementedMethodError
from libspec.util import fqn, easy_hash


SOURCE_MAP_CONTEXT_KEYS = {
    "req_id",
    "feature_name",
    "constraint_id",
    "model_name",
    "api_name",
    "title",
}
CTX_RESERVED_NAMES = {"ctx", "render", "render_xml", "to_xml_element"}
CTX_INTERNAL_NAMES = {
    "_base_template",
    "_instance_notes",
    "_source_info",
    "_to_xml_element",
}
SKIPPED_SOURCE_LINE_KEYS = {"start_line", "end_line"}
SKIP_SEARCH_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    "build",
    "dist",
    ".pytest_cache",
}
SKIP_SEARCH_FILE_SUFFIXES = (
    ".pyc",
    ".pyo",
    ".so",
    ".dll",
    ".exe",
    ".bin",
    ".xml",
    ".json",
    ".out",
)


class Spec:
    def modules(self):
        raise UnimplementedMethodError()

    def generate_xml(self):
        """Generate the complete specification as a structured XML document."""
        root = self._build_specification_set()
        return self._pretty_xml(root)

    def _build_specification_set(self):
        root = ET.Element("specification_set")
        root.set("libspec-version", self._libspec_version())
        self._append_module_spec_elements(root)
        return root

    def _libspec_version(self):
        try:
            return importlib.metadata.version("libspec")
        except importlib.metadata.PackageNotFoundError:
            return "unknown"

    def _append_module_spec_elements(self, root):
        for mod in self.modules():
            for spec in instantiate_module_specs(mod):
                root.append(spec.to_xml_element())

    def _pretty_xml(self, element):
        xml_bytes = ET.tostring(element, encoding="utf-8")
        return minidom.parseString(xml_bytes).toprettyxml(indent="  ")

    def write_xml(self, output_dir):
        """Write the XML specification to a hashed file in the given directory."""
        xml_content = self.generate_xml()
        path = self._spec_output_path(output_dir, xml_content)
        final_xml = self._inject_date_created(xml_content)
        self._write_text(path, final_xml)
        print(f"Specification written to {path}")
        self.generate_source_map(final_xml, path, output_dir)
        return path

    def _spec_output_path(self, output_dir, xml_content):
        os.makedirs(output_dir, exist_ok=True)
        digest = easy_hash(xml_content)[:20]
        return os.path.join(output_dir, f"spec-{digest}.xml")

    def _inject_date_created(self, xml_content):
        created_at = datetime.datetime.now().astimezone().isoformat()
        return xml_content.replace(
            "<specification_set",
            f'<specification_set date-created="{created_at}"',
            1,
        )

    def _write_text(self, path, content):
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def _class_line_span(self, file_path, class_name):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source)
        except Exception:
            return None, None

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                return getattr(node, "lineno", None), getattr(node, "end_lineno", None)
        return None, None

    def _search_workspace_for_id(self, directory, search_id):
        matches = []
        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if d not in SKIP_SEARCH_DIRS]
            matches.extend(self._search_files_for_id(root, files, search_id))
        return matches

    def _search_files_for_id(self, root, files, search_id):
        matches = []
        for filename in files:
            if filename.endswith(SKIP_SEARCH_FILE_SUFFIXES):
                continue
            path = os.path.join(root, filename)
            matches.extend(self._search_file_for_id(path, search_id))
        return matches

    def _search_file_for_id(self, path, search_id):
        matches = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                for lineno, line in enumerate(f, 1):
                    if search_id in line:
                        matches.append({"file": path, "line": lineno})
        except Exception:
            return []
        return matches

    def generate_source_map(self, xml_content, xml_path, output_dir):
        tree = self._parse_source_map_xml(xml_content)
        if tree is None:
            return

        workspace_dir = os.getcwd()
        source_map = []
        for spec_node in self._specification_nodes(tree):
            entry = self._build_source_map_entry(spec_node, xml_path, workspace_dir)
            source_map.append(entry)

        out_file = os.path.join(output_dir, "source_map.json")
        self._write_source_map_file(out_file, source_map)

    def _parse_source_map_xml(self, xml_content):
        from lxml import etree

        try:
            return etree.fromstring(xml_content.encode("utf-8"))
        except Exception as exc:
            print(f"Error parsing XML for source map: {exc}")
            return None

    def _specification_nodes(self, tree):
        return tree.xpath("//specification")

    def _build_source_map_entry(self, spec_node, xml_path, workspace_dir):
        entry = self._empty_source_map_entry(spec_node)
        entry["xml_spec"] = self._xml_source_ref(spec_node, xml_path)
        entry["python_spec"] = self._python_source_ref(spec_node)
        search_ids = self._collect_source_search_ids(spec_node)
        matches = self._find_generated_code_matches(search_ids, workspace_dir)
        entry["generated_code"] = self._dedupe_file_line_matches(matches)
        return entry

    def _empty_source_map_entry(self, spec_node):
        return {
            "component": spec_node.get("type", "Unknown"),
            "python_spec": None,
            "xml_spec": None,
            "generated_code": [],
        }

    def _xml_source_ref(self, spec_node, xml_path):
        if not spec_node.sourceline:
            return None
        return {"file": str(xml_path), "line": spec_node.sourceline}

    def _python_source_ref(self, spec_node):
        source_elem = spec_node.find("source")
        if source_elem is None:
            return None

        py_file = source_elem.get("file")
        target = source_elem.get("target")
        if not (py_file and target):
            return None

        start_line, end_line = self._class_line_span(py_file, target)
        return {
            "file": py_file,
            "target": target,
            "start_line": start_line,
            "end_line": end_line,
        }

    def _collect_source_search_ids(self, spec_node):
        ids = set()
        component_type = spec_node.get("type")
        if component_type:
            ids.add(component_type)

        context = spec_node.find("context")
        if context is None:
            return ids

        for child in context:
            if child.tag not in SOURCE_MAP_CONTEXT_KEYS:
                continue
            text = (child.text or "").strip()
            if text:
                ids.add(text)
        return ids

    def _find_generated_code_matches(self, search_ids, workspace_dir):
        matches = []
        for search_id in search_ids:
            if len(search_id) <= 2:
                continue
            matches.extend(self._search_workspace_for_id(workspace_dir, search_id))
        return matches

    def _dedupe_file_line_matches(self, matches):
        deduped = []
        seen = set()
        for match in matches:
            key = (match["file"], match["line"])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(match)
        return deduped

    def _write_source_map_file(self, out_file, source_map):
        try:
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(source_map, f, indent=2)
            print(f"Source map written to {out_file}")
        except Exception as exc:
            print(f"Error writing source map: {exc}")

    def handle_cli(self):
        """Handle command line interface for specification generation."""
        parser = argparse.ArgumentParser(description="libspec CLI")
        parser.add_argument("-o", "--output", help="Output directory for XML specification")
        parser.add_argument("--xml", action="store_true", help="Print XML specification to stdout")
        args = parser.parse_args()

        if args.output:
            self.write_xml(args.output)
            return
        if args.xml:
            print(self.generate_xml())
            return
        self.generate_xml()


class Ctx:
    def _non_root_mro_classes(self):
        return [cls for cls in self.__class__.__mro__[1:] if cls not in (Ctx, object)]

    def _inherited_ctx_classes(self):
        classes = []
        for cls in self._non_root_mro_classes():
            if issubclass(cls, Ctx):
                classes.append(cls)
        return classes

    def _inherited_field_values(self):
        values = {}
        for cls in self._inherited_ctx_classes():
            values.update(self._class_zero_arg_values(cls))
        return values

    def _class_zero_arg_values(self, cls):
        values = {}
        for name in dir(cls):
            if self._skip_ctx_member(name):
                continue
            value = self._evaluate_zero_arg_class_member(cls, name)
            if value is not _Missing:
                values[f"{cls.__name__}.{name}"] = value
        return values

    def _evaluate_zero_arg_class_member(self, cls, name):
        try:
            member = getattr(cls, name, None)
            if not callable(member):
                return _Missing
            if len(signature(member).parameters) != 0:
                return _Missing
            return member()
        except Exception:
            return _Missing

    def _skip_ctx_member(self, name):
        return name.startswith("_") or name in CTX_RESERVED_NAMES

    def _detect_overrides(self):
        overrides = []
        parent_values = self._inherited_field_values()
        current_ctx = self.ctx(template_only=False)

        for key, value in current_ctx.items():
            if self._is_overridden_value(key, value, parent_values):
                overrides.append(key)
        return overrides

    def _is_overridden_value(self, key, value, parent_values):
        for parent_key, parent_value in parent_values.items():
            if key == parent_key.split(".")[-1] and value != parent_value:
                return True
        return False

    def _delta_requirements(self):
        deltas = {}
        own_doc = self._instance_notes()
        parent_docs = set(self._inherited_docstrings())
        if own_doc and own_doc not in parent_docs:
            deltas["notes"] = own_doc

        for key, value in self.ctx(template_only=False).items():
            if key == "_in_ctx":
                continue
            if not self._parent_has_same_value(key, value):
                deltas[key] = value
        return deltas

    def _inherited_docstrings(self):
        docs = []
        for cls in self._non_root_mro_classes():
            if cls.__doc__:
                docs.append(cleandoc(cls.__doc__))
        return docs

    def _parent_has_same_value(self, key, value):
        for cls in self._non_root_mro_classes():
            if not hasattr(cls, key):
                continue
            parent_val = self._safe_call(getattr(cls, key))
            if parent_val is _Missing:
                continue
            if parent_val == value:
                return True
        return False

    def _safe_call(self, maybe_callable):
        if not callable(maybe_callable):
            return _Missing
        try:
            return maybe_callable()
        except Exception:
            return _Missing

    def _effective_requirement_ids(self):
        req_ids = []
        for cls in self.__class__.__mro__:
            if not issubclass(cls, Requirement) or cls is Requirement:
                continue
            try:
                class_id = fqn(cls)
            except Exception:
                continue
            if class_id:
                req_ids.append(class_id)
        return req_ids

    def _base_template(self):
        templates = []
        for cls in self._non_root_mro_classes():
            if not cls.__doc__:
                continue
            cleaned = cleandoc(cls.__doc__)
            if cleaned:
                templates.append(cleaned)
        templates.reverse()
        return "\n\n".join(templates)

    def _instance_notes(self):
        doc = self.__class__.__doc__
        return cleandoc(doc) if doc else ""

    def _source_info(self, obj=None):
        target = obj if obj is not None else self.__class__
        try:
            source_file = inspect.getsourcefile(target)
            source_file = os.path.abspath(source_file) if source_file else None
            lines, start_line = inspect.getsourcelines(target)
            return {
                "file": source_file,
                "start_line": start_line,
                "end_line": start_line + len(lines) - 1,
                "name": getattr(target, "__name__", str(target)),
            }
        except (OSError, TypeError):
            return None

    def ctx(self, template_only=True):
        if getattr(self, "_in_ctx", False):
            return {}
        self._in_ctx = True
        try:
            return self._build_context(template_only)
        finally:
            self._in_ctx = False

    def _build_context(self, template_only=True):
        expected = self._expected_template_vars()
        context = self._collect_template_context(expected)
        if template_only:
            return context
        return self._collect_non_template_context(context)

    def _expected_template_vars(self):
        env = Environment()
        template_text = f"{self._base_template()}\n{self._instance_notes()}"
        return meta.find_undeclared_variables(env.parse(template_text))

    def _collect_template_context(self, expected_vars):
        context = {}
        if "fields" in expected_vars and hasattr(self, "fields"):
            context["fields"] = self.fields()

        for var_name in sorted(expected_vars):
            if var_name == "fields":
                continue
            context[var_name] = self._resolve_template_var(var_name)
        return context

    def _resolve_template_var(self, var_name):
        member_name = var_name.replace("-", "_")
        if hasattr(self, member_name):
            member = getattr(self, member_name)
            return member() if callable(member) else member
        raise AttributeError(self._missing_template_var_message(var_name, member_name))

    def _missing_template_var_message(self, var_name, member_name):
        src = self._source_info()
        location = f"{src['file']}:{src['start_line']}" if src else "unknown location"
        return (
            f"\nThe variable '{{{{{var_name}}}}}' was found in a docstring template "
            f"for class '{self.__class__.__name__}',\n"
            f"defined at {location},\n"
            f"but no matching method or attribute '{member_name}' was found.\n\n"
            f"FIX: implement 'def {member_name}(self):' in class "
            f"'{self.__class__.__name__}' or one of its bases.\n"
        )

    def _collect_non_template_context(self, context):
        for name in sorted(dir(self)):
            if self._skip_runtime_context_member(name, context):
                continue
            value = self._resolve_runtime_context_member(name)
            if value is not _Missing:
                context[name] = value
        return context

    def _skip_runtime_context_member(self, name, context):
        if name.startswith("_") or name in CTX_RESERVED_NAMES:
            return True
        if name in CTX_INTERNAL_NAMES or name in context:
            return True
        return False

    def _resolve_runtime_context_member(self, name):
        member = getattr(self, name)
        if not callable(member):
            return member
        try:
            if len(signature(member).parameters) != 0:
                return _Missing
            return member()
        except (TypeError, ValueError, UnimplementedMethodError):
            return _Missing

    def _to_xml_element(self, name, value):
        elem = ET.Element(name)
        if isinstance(value, dict):
            for key in sorted(value.keys()):
                if key in SKIPPED_SOURCE_LINE_KEYS:
                    continue
                child_name = str(key).replace("-", "_")
                elem.append(self._to_xml_element(child_name, value[key]))
            return elem

        if isinstance(value, list):
            for item in value:
                elem.append(self._to_xml_element("item", item))
            return elem

        elem.text = str(value)
        return elem

    def render_xml(self):
        """Render the specification as structured XML."""
        return minidom.parseString(
            ET.tostring(self.to_xml_element(),
                        encoding="utf-8")).toprettyxml(indent="  ")

    def to_xml_element(self):
        """Convert the specification to an XML element."""
        root = ET.Element("specification")
        root.set("type", self.__class__.__name__)
        ctx_data = self.ctx()
        self._append_source_metadata(root)
        self._append_description(root, ctx_data)
        self._append_notes(root, ctx_data)
        self._append_context(root)
        self._append_inheritance(root)
        self._append_effective_req_ids(root)
        self._append_overrides(root)
        self._append_delta_requirements(root)
        return root

    def _append_source_metadata(self, root):
        src = self._source_info()
        if not src:
            return
        source_elem = ET.SubElement(root, "source")
        source_elem.set("target", src["name"])
        source_elem.set("file", src["file"])

    def _append_description(self, root, ctx_data):
        rendered = Template(self._base_template()).render(**ctx_data).strip()
        if not rendered:
            return
        desc_elem = ET.SubElement(root, "description")
        desc_elem.text = rendered

    def _append_notes(self, root, ctx_data):
        notes = self._instance_notes()
        if not notes:
            return
        rendered = Template(notes).render(**ctx_data).strip()
        notes_elem = ET.SubElement(root, "notes")
        notes_elem.text = rendered

    def _append_context(self, root):
        context_elem = ET.SubElement(root, "context")
        for key, value in sorted(self.ctx(template_only=False).items()):
            name = str(key).replace("-", "_")
            context_elem.append(self._to_xml_element(name, value))

    def _append_inheritance(self, root):
        inherited = self._inherited_ctx_classes()
        if not inherited:
            return
        inherits_elem = ET.SubElement(root, "inherits")
        for cls in inherited:
            inherits_elem.append(self._to_xml_element("spec", fqn(cls)))

    def _append_effective_req_ids(self, root):
        req_ids = self._effective_requirement_ids()
        if not req_ids:
            return
        req_elem = ET.SubElement(root, "effective_req_ids")
        for req_id in req_ids:
            req_elem.append(self._to_xml_element("id", req_id))

    def _append_overrides(self, root):
        overrides = self._detect_overrides()
        if not overrides:
            return
        overrides_elem = ET.SubElement(root, "overrides")
        for name in overrides:
            overrides_elem.append(self._to_xml_element("field", name))

    def _append_delta_requirements(self, root):
        deltas = self._delta_requirements()
        if not deltas:
            return
        delta_elem = ET.SubElement(root, "delta_requirements")
        for key, value in deltas.items():
            name = str(key).replace("-", "_")
            delta_elem.append(self._to_xml_element(name, value))


class Feature(Ctx):
    """
    Feature Specification: {{feature_name}}

    """

    def feature_name(self):
        return self.__class__.__name__

    def date(self):
        raise UnimplementedMethodError()

    def description(self):
        raise UnimplementedMethodError()


class Def(Ctx):
    """
    Definition: {{name}}:

    """

    def name(self):
        return fqn(self)


class EdgeCase(Ctx):
    """
    Edge Case

    What happens when {{boundary_condition}}?
    How does system handle {{error_scenario}}?
    """

    def boundary_condition(self):
        raise UnimplementedMethodError()

    def error_scenario(self):
        raise UnimplementedMethodError()


class Constraint(Ctx):
    """
    CONSTRAINT-ID: {{constraint_id}}
    DESCRIPTION: {{description}}
    ENFORCEMENT: {{enforcement_logic}}
    """

    def constraint_id(self):
        return self.__class__.__name__

    def description(self):
        return self.__class__.__doc__


class Requirement(Ctx):
    """
    Requirement
    TITLE: {{title}}
    REQUIREMENT-ID: {{req_id}}

    Insert REQUIREMENT-ID into any source code for cross reference purposes.
    """

    def title(self):
        return self.__class__.__name__

    def req_id(self):
        return fqn(self)


class SystemRequirement(Requirement):
    """
    System Requirement: This is a tool level requirement aimed at the
    toolchain supporting the project.
    """


class DataSchema(Ctx):
    """
    DATA-MODEL: {{model_name}}
    FIELDS:
    {% if fields is mapping %}
    {% for name, type_obj in fields.items() %}
      - {{name}}: {{type_obj}}
    {% endfor %}
    {% else %}
      - No fields defined.
    {% endif %}
    """

    def model_name(self):
        return self.__class__.__name__

    def fields(self):
        return self.__class__.__annotations__


class SQLite3(DataSchema):
    """
    SQLite3 Database.

    The following schema should be implemented for SQLite3. Write
    tests to ensure the database behaves as expected.

    The database file should be located at {{dbpath}}
    """


class PeeWee(DataSchema):
    """
    Python PeeWee Database.

    The following schema should be implemented for PeeWee. Write
    tests to ensure the database behaves as expected.

    The database file should be located at {{dbpath}}
    """


class LeafMethods:
    def methods(self):
        """Return method descriptors for leaf-class public methods."""
        descriptors = []
        for name, func in self._leaf_public_functions():
            descriptors.append(self._method_descriptor(name, func))
        return descriptors

    def _leaf_public_functions(self):
        cls = self.__class__
        for name, attr in cls.__dict__.items():
            if name.startswith("_"):
                continue
            if isfunction(attr):
                yield name, attr

    def _method_descriptor(self, name, func):
        params = self._method_params_without_self(func)
        member = getattr(self, name)
        return {
            "name": name,
            "params": params,
            "description": cleandoc(func.__doc__ or "No description provided"),
            "result": self._invoke_member_for_preview(member, len(params)),
            "source_ref": self._source_info(func),
        }

    def _method_params_without_self(self, func):
        return [p for p in signature(func).parameters.keys() if p != "self"]

    def _invoke_member_for_preview(self, member, arg_count):
        if callable(member):
            return member(*([None] * arg_count))
        return member


class API(Ctx, LeafMethods):
    """
    API Specification: {{api_name}}

    Endpoints:
    {% for method in methods %}
      - {{method.name}}({{method.params|join(', ')}})

        Description: {{method.description}}
    {% endfor %}

    Constraints:
    {% for constraint in constraints %}
      - {{constraint}}
    {% endfor %}
    """

    def api_name(self):
        """Name of the API."""
        return self.__class__.__name__

    def constraints(self):
        """Return a list of strings describing API-level business constraints."""
        return []


class LibraryAPI(API):
    """
    Library API Version: {{version}}
    This is not a network API, rather this is a library API.
    """


class RestMixin:
    """
    Develop a REST API with best practices around this interface
    """


class CmdLine(Ctx, LeafMethods):
    """
    Command Line Specification

    implement these commands:
    {% for method in methods %}
      | {{method.name}}({{method.params|join(', ')}})
      | Description: {{method.description}}
      | {{method.result}}
    {% endfor %}
    """


class Implementation(Requirement):
    """
    Implementation requirements.
    Implementations must include tests.

    All files generated by this implementation should live in the
    directory:{{implementation_directory}}
    """


def ctx_spec_classes_in_module(module):
    classes = []
    for _, obj in inspect.getmembers(module, inspect.isclass):
        if obj.__module__ != module.__name__:
            continue
        if issubclass(obj, Ctx) and obj is not Ctx:
            classes.append(obj)
    return classes


def instantiate_module_specs(module):
    return [cls() for cls in ctx_spec_classes_in_module(module)]


class _MissingType:
    pass


_Missing = _MissingType()


def classes_with_ctx_superclass(module):
    return ctx_spec_classes_in_module(module)


def module_specs(mod):
    return instantiate_module_specs(mod)
