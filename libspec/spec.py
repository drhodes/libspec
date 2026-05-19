import inspect
import os
import argparse
import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom
from jinja2 import Environment, meta, Template
from inspect import signature, cleandoc
from libspec.err import UnimplementedMethodError
from libspec.util import fqn, easy_hash, get_libspec_version



CTX_RESERVED_NAMES = {"ctx", "render", "render_xml", "to_xml_element"}
CTX_INTERNAL_NAMES = {
    "_base_template",
    "_class_docstring",
    "_compiled_docstring_template",
    "_instance_notes",
    "_source_info",
    "_to_xml_element",
}
SKIPPED_SOURCE_LINE_KEYS = {"start_line", "end_line"}



class Spec:
    # Return the list of modules that contain specifications.
    def modules(self):
        raise UnimplementedMethodError()

    # Generate the complete specification as a structured XML document.
    def generate_xml(self):
        root = self._build_specification_set()
        return self._pretty_xml(root)

    # Pretty-print the XML root element.
    def _pretty_xml(self, element):
        try:
            xml_bytes = ET.tostring(element, encoding="utf-8")
            return minidom.parseString(xml_bytes).toprettyxml(indent="  ")
        except Exception as e:
            return f"<!-- Error formatting XML: {e} -->\n" + ET.tostring(element, encoding="unicode")

    # Build the complete specification set as an XML element.
    def _build_specification_set(self):
        root = ET.Element("specification_set")
        root.set("libspec-version", get_libspec_version())
        self._append_module_spec_elements(root)
        return root


    # Append specification elements from all modules to the root.
    def _append_module_spec_elements(self, root):
        emitted_refs = set()
        all_module_specs = []
        for mod in self.modules():
            all_module_specs.extend(instantiate_module_specs(mod))

        # Pass 1: emit all full module-defined specs first so no class is
        # eclipsed by a thin dependency stub added when processing a sibling
        # that happens to sort earlier (e.g. HumanTask before Task).
        for spec in all_module_specs:
            self._append_spec(root, spec.to_xml_element(), emitted_refs)

        # Pass 2: emit dependency stubs for inherited classes not already seen
        for spec in all_module_specs:
            self._append_inherited_dependencies(root, spec, emitted_refs)

    # Append a single specification element to the root, avoiding duplicates.
    def _append_spec(self, root, element, emitted_refs):
        ref = element.get("ref") or element.get("type")
        if not ref or ref in emitted_refs:
            return
        root.append(element)
        emitted_refs.add(ref)

    # Recursively append all inherited dependency specifications to the root.
    def _append_inherited_dependencies(self, root, spec, emitted_refs):
        pending = [
            cls for cls in spec._non_root_mro_classes()
            if self._docstring_template_for_class(cls)
        ]
        while pending:
            cls = pending.pop(0)
            dep_ref = fqn(cls)
            if dep_ref in emitted_refs:
                continue

            dep_elem = self._dependency_spec_element(cls)
            self._append_spec(root, dep_elem, emitted_refs)

            for parent in cls.__mro__[1:]:
                if parent in (Ctx, object):
                    continue
                if self._docstring_template_for_class(parent):
                    pending.append(parent)

    # Create an XML element representing a dependency specification for a class.
    def _dependency_spec_element(self, cls):
        elem = ET.Element("specification")
        elem.set("type", cls.__name__)
        elem.set("ref", fqn(cls))
        elem.set("dependency", "true")

        template_text = self._docstring_template_for_class(cls)
        is_template = "{{" in template_text or "{%" in template_text
        elem.set("template", "true" if is_template else "false")

        source_info = self._source_info_for_class(cls)
        if source_info:
            source_elem = ET.SubElement(elem, "source")
            source_elem.set("target", source_info["name"])
            source_elem.set("file", source_info["file"])

        template_text = self._docstring_template_for_class(cls)
        if template_text:
            docstring_template_elem = ET.SubElement(elem, "docstring_template")
            docstring_template_elem.text = template_text

        inherited = [
            parent for parent in cls.__mro__[1:]
            if parent not in (Ctx, object) and self._docstring_template_for_class(parent)
        ]
        if inherited:
            inherits_elem = ET.SubElement(elem, "inherits")
            for parent in inherited:
                parent_ref = ET.SubElement(inherits_elem, "ref")
                parent_ref.text = fqn(parent)
        return elem

    # Return source file and line information for a given class.
    def _source_info_for_class(self, cls):
        try:
            source_file = inspect.getsourcefile(cls)
            source_file = os.path.abspath(source_file) if source_file else None
            lines, start_line = inspect.getsourcelines(cls)
            return {
                "file": source_file,
                "start_line": start_line,
                "end_line": start_line + len(lines) - 1,
                "name": getattr(cls, "__name__", str(cls)),
            }
        except (OSError, TypeError):
            return None

    # Return the cleaned docstring template for a given class.
    def _docstring_template_for_class(self, cls):
        doc = cls.__doc__
        return cleandoc(doc) if doc else ""

    def get_components(self):
        """Compile specifications from all modules into Component dataclasses."""
        from libspec.store import Component
        import hashlib
        
        emitted_refs = set()
        components = []
        all_module_specs = []
        for mod in self.modules():
            all_module_specs.extend(instantiate_module_specs(mod))
            
        # Collect full specs first
        for spec in all_module_specs:
            ref = fqn(spec.__class__)
            if ref in emitted_refs:
                continue
                
            template_text = self._docstring_template_for_class(spec.__class__)
            is_template = "{{" in template_text or "{%" in template_text
            
            if is_template:
                ctx_data = spec.ctx()
                try:
                    docstring = Template(template_text).render(**ctx_data).strip()
                except Exception as e:
                    print(f"Error rendering template docstring for {spec.__class__.__name__}: {e}")
                    docstring = template_text
            else:
                docstring = template_text
                
            inherited = [
                fqn(parent) for parent in spec.__class__.__mro__[1:]
                if parent not in (Ctx, object) and self._docstring_template_for_class(parent)
            ]
            
            comp_hash = hashlib.sha256(docstring.encode("utf-8")).hexdigest()
            
            components.append(Component(
                ref=ref,
                docstring=docstring,
                is_template=is_template,
                inherits=inherited,
                hash=comp_hash
            ))
            emitted_refs.add(ref)
            
        # Collect inherited dependencies not already emitted
        for spec in all_module_specs:
            pending = [
                cls for cls in spec._non_root_mro_classes()
                if self._docstring_template_for_class(cls)
            ]
            while pending:
                cls = pending.pop(0)
                dep_ref = fqn(cls)
                if dep_ref in emitted_refs:
                    continue
                    
                template_text = self._docstring_template_for_class(cls)
                is_template = "{{" in template_text or "{%" in template_text
                
                docstring = template_text
                
                inherited = [
                    fqn(parent) for parent in cls.__mro__[1:]
                    if parent not in (Ctx, object) and self._docstring_template_for_class(parent)
                ]
                
                comp_hash = hashlib.sha256(docstring.encode("utf-8")).hexdigest()
                
                components.append(Component(
                    ref=dep_ref,
                    docstring=docstring,
                    is_template=is_template,
                    inherits=inherited,
                    hash=comp_hash
                ))
                emitted_refs.add(dep_ref)
                
                for parent in cls.__mro__[1:]:
                    if parent in (Ctx, object):
                        continue
                    if self._docstring_template_for_class(parent):
                        pending.append(parent)
                        
        return components

    # Write the XML specification and source map to the output directory.
    def write_xml(self, output_dir):
        """Write the XML specification to a hashed file in the given directory using SpecStore."""
        components = self.get_components()
        
        # Resolve store from unified factory
        from libspec.store import get_store, XmlSpecStore
        store = get_store()
            
        # Get active git commit if possible
        git_commit = None
        try:
            import subprocess
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            if result.returncode == 0:
                git_commit = result.stdout.strip()
        except Exception:
            pass
            
        # Write snapshot!
        snapshot = store.store_snapshot(components, git_commit=git_commit)
        
        if isinstance(store, XmlSpecStore):
            path = store._latest_xml_path or os.path.join(output_dir, f"spec-{snapshot.id}.xml")
        else:
            path = f"database://{snapshot.id}"
            
        print(f"Specification written to {path}")
        return path

    # Calculate the hashed output path for the XML specification.
    def _spec_output_path(self, output_dir, xml_content):
        os.makedirs(output_dir, exist_ok=True)
        digest = easy_hash(xml_content)[:20]
        return os.path.join(output_dir, f"spec-{digest}.xml")

    # Inject the current timestamp into the specification set element.
    def _inject_date_created(self, xml_content):
        created_at = datetime.datetime.now().astimezone().isoformat()
        return xml_content.replace(
            "<specification_set",
            f'<specification_set date-created="{created_at}"',
            1,
        )

    # Write text content to a file, handling potential IO errors.
    def _write_text(self, path, content):
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        except IOError as e:
            print(f"Error writing to {path}: {e}")

    # Process command line arguments for standalone specification generation.
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
    # Return all classes in the MRO excluding Ctx and object.
    def _non_root_mro_classes(self):
        return [cls for cls in self.__class__.__mro__[1:] if cls not in (Ctx, object)]

    # Return all Ctx-derived classes in the MRO.
    def _inherited_ctx_classes(self):
        classes = []
        for cls in self._non_root_mro_classes():
            if issubclass(cls, Ctx):
                classes.append(cls)
        return classes

    # Collect values from zero-argument methods in inherited Ctx classes.
    def _inherited_field_values(self):
        values = {}
        for cls in self._inherited_ctx_classes():
            values.update(self._class_zero_arg_values(cls))
        return values

    # Return field values defined in a specific class's methods.
    def _class_zero_arg_values(self, cls):
        values = {}
        for name in dir(cls):
            if self._skip_ctx_member(name):
                continue
            value = self._evaluate_zero_arg_class_member(cls, name)
            if value is not _Missing:
                values[f"{cls.__name__}.{name}"] = value
        return values

    # Safely evaluate a zero-argument method from a class.
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

    # Return True if the member name should be skipped during context collection.
    def _skip_ctx_member(self, name):
        return name.startswith("_") or name in CTX_RESERVED_NAMES

    # Identify fields that override values defined in parent classes.
    def _detect_overrides(self):
        overrides = []
        parent_values = self._inherited_field_values()
        current_ctx = self.ctx(template_only=False)

        for key, value in current_ctx.items():
            if self._is_overridden_value(key, value, parent_values):
                overrides.append(key)
        return overrides

    # Return True if the field value differs from any parent class definition.
    def _is_overridden_value(self, key, value, parent_values):
        for parent_key, parent_value in parent_values.items():
            if key == parent_key.split(".")[-1] and value != parent_value:
                return True
        return False

    # Calculate the set of requirements that differ from parent classes.
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

    # Return a list of docstrings from all inherited classes.
    def _inherited_docstrings(self):
        docs = []
        for cls in self._non_root_mro_classes():
            if cls.__doc__:
                docs.append(cleandoc(cls.__doc__))
        return docs

    # Return True if any parent class shares the same field value.
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

    # Safely invoke a callable and return its result or _Missing on failure.
    def _safe_call(self, maybe_callable):
        if not callable(maybe_callable):
            return _Missing
        try:
            return maybe_callable()
        except Exception:
            return _Missing

    # Collect FQNs of all Requirement-derived classes in the MRO.
    def _effective_requirement_ids(self):
        from .spec_types import Requirement
        req_ids = []
        for cls in self.__class__.__mro__:
            if not issubclass(cls, Requirement) or cls is Requirement:
                continue
            try:
                class_id = fqn(cls)
                if class_id:
                    req_ids.append(class_id)
            except Exception:
                continue
        return req_ids

    # Concatenate docstring templates from parent classes.
    def _base_template(self):
        templates = []
        for cls in self._non_root_mro_classes():
            cleaned = self._class_docstring(cls)
            if cleaned:
                templates.append(cleaned)
        templates.reverse()
        return "\n\n".join(templates)

    # Return the cleaned docstring for a given class.
    def _class_docstring(self, cls):
        doc = cls.__doc__
        return cleandoc(doc) if doc else ""

    # Return the docstring template for the current class.
    def _compiled_docstring_template(self):
        return self._class_docstring(self.__class__)

    # Return notes specific to the current instance (its docstring).
    def _instance_notes(self):
        return self._compiled_docstring_template()

    # Return source location metadata for an object or the current class.
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

    # Build and return the context data used for template rendering.
    def ctx(self, template_only=True):
        if getattr(self, "_in_ctx", False):
            return {}
        self._in_ctx = True
        try:
            return self._build_context(template_only)
        finally:
            self._in_ctx = False

    # Internal method to assemble the template context.
    def _build_context(self, template_only=True):
        expected = self._expected_template_vars()
        context = self._collect_template_context(expected)
        if template_only:
            return context
        return self._collect_non_template_context(context)

    # Identify all undeclared variables in the docstring templates.
    def _expected_template_vars(self):
        env = Environment()
        template_text = f"{self._base_template()}\n{self._instance_notes()}"
        return meta.find_undeclared_variables(env.parse(template_text))

    # Resolve and collect values for all required template variables.
    def _collect_template_context(self, expected_vars):
        context = {}
        if "fields" in expected_vars and hasattr(self, "fields"):
            context["fields"] = self.fields()

        for var_name in sorted(expected_vars):
            if var_name == "fields":
                continue
            context[var_name] = self._resolve_template_var(var_name)
        return context

    # Map template variable names to methods or attributes and return their values.
    def _resolve_template_var(self, var_name):
        member_name = var_name.replace("-", "_")
        if hasattr(self, member_name):
            member = getattr(self, member_name)
            return member() if callable(member) else member
        raise AttributeError(self._missing_template_var_message(var_name, member_name))

    # Generate a descriptive error message for missing template variables.
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

    # Supplement the context with all available public methods and attributes.
    def _collect_non_template_context(self, context):
        for name in sorted(dir(self)):
            if self._skip_runtime_context_member(name, context):
                continue
            value = self._resolve_runtime_context_member(name)
            if value is not _Missing:
                context[name] = value
        return context

    # Return True if a member should be excluded from the runtime context.
    def _skip_runtime_context_member(self, name, context):
        if name.startswith("_") or name in CTX_RESERVED_NAMES:
            return True
        if name in CTX_INTERNAL_NAMES or name in context:
            return True
        return False

    # Resolve a member name to its value for runtime context inclusion.
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

    # Recursively convert Python values to XML elements.
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

    # Render the specification as structured XML using minidom for formatting.
    def render_xml(self):
        try:
            return minidom.parseString(
                ET.tostring(self.to_xml_element(),
                            encoding="utf-8")).toprettyxml(indent="  ")
        except Exception as e:
            return f"<!-- Error rendering XML: {e} -->\n" + ET.tostring(self.to_xml_element(), encoding="unicode")

    # Build the XML representation of the specification.
    def to_xml_element(self):
        """Convert the specification to an XML element."""
        root = ET.Element("specification")
        root.set("type", self.__class__.__name__)
        root.set("ref", fqn(self.__class__))
        ctx_data = self.ctx()
        self._append_source_metadata(root)
        self._append_docstring(root, ctx_data)
        self._append_context(root)
        self._append_inheritance(root)
        self._append_effective_req_ids(root)
        self._append_overrides(root)
        self._append_delta_requirements(root)
        return root

    # Append source file and line information to the XML element.
    def _append_source_metadata(self, root):
        src = self._source_info()
        if not src:
            return
        source_elem = ET.SubElement(root, "source")
        source_elem.set("target", src["name"])
        source_elem.set("file", src["file"])

    # Render and append the docstring to the XML element.
    def _append_docstring(self, root, ctx_data):
        template_text = self._compiled_docstring_template()
        if not template_text:
            return
        try:
            rendered = Template(template_text).render(**ctx_data).strip()
            docstring_elem = ET.SubElement(root, "docstring")
            docstring_elem.text = rendered
        except Exception as e:
            print(f"Error rendering docstring for {self.__class__.__name__}: {e}")

    # Append all context fields to the XML element.
    def _append_context(self, root):
        context_elem = ET.SubElement(root, "context")
        for key, value in sorted(self.ctx(template_only=False).items()):
            name = str(key).replace("-", "_")
            context_elem.append(self._to_xml_element(name, value))

    # Append inheritance references to the XML element.
    def _append_inheritance(self, root):
        inherited = [cls for cls in self._non_root_mro_classes()
                     if self._class_docstring(cls)]
        if not inherited:
            return
        inherits_elem = ET.SubElement(root, "inherits")
        for cls in inherited:
            try:
                ref_elem = self._to_xml_element("ref", fqn(cls))
                inherits_elem.append(ref_elem)
            except Exception:
                continue

    # Append all effective requirement IDs to the XML element.
    def _append_effective_req_ids(self, root):
        req_ids = self._effective_requirement_ids()
        if not req_ids:
            return
        req_elem = ET.SubElement(root, "effective_req_ids")
        for req_id in req_ids:
            req_elem.append(self._to_xml_element("id", req_id))

    # Append field override information to the XML element.
    def _append_overrides(self, root):
        overrides = self._detect_overrides()
        if not overrides:
            return
        overrides_elem = ET.SubElement(root, "overrides")
        for name in overrides:
            overrides_elem.append(self._to_xml_element("field", name))

    # Append requirement deltas to the XML element.
    def _append_delta_requirements(self, root):
        deltas = self._delta_requirements()
        if not deltas:
            return
        delta_elem = ET.SubElement(root, "delta_requirements")
        for key, value in deltas.items():
            name = str(key).replace("-", "_")
            delta_elem.append(self._to_xml_element(name, value))




# Return all Ctx-derived classes defined in a module.
def ctx_spec_classes_in_module(module):
    classes = []
    for _, obj in inspect.getmembers(module, inspect.isclass):
        if obj.__module__ != module.__name__:
            continue
        if issubclass(obj, Ctx) and obj is not Ctx:
            classes.append(obj)
    return classes


# Instantiate all specification classes found in a module.
def instantiate_module_specs(module):
    return [cls() for cls in ctx_spec_classes_in_module(module)]


class _MissingType:
    pass


_Missing = _MissingType()


# Legacy alias for ctx_spec_classes_in_module.
def classes_with_ctx_superclass(module):
    return ctx_spec_classes_in_module(module)


# Legacy alias for instantiate_module_specs.
def module_specs(mod):
    return instantiate_module_specs(mod)

from .spec_types import *
