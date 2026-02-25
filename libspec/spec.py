import inspect
import os
import ast
import json
import argparse
import xml.etree.ElementTree as ET
from xml.dom import minidom
from jinja2 import Environment, meta, Template
from inspect import signature, cleandoc, isfunction
from libspec.err import UnimplementedMethodError
from libspec.util import fqn, easy_hash


class Spec:
    def modules(self):
        raise UnimplementedMethodError()
        
    def generate_xml(self):
        """Generate the complete specification as a structured XML document."""
        root = ET.Element("specification_set")
        for mod in self.modules():
            for spec in module_specs(mod):
                root.append(spec.to_xml_element())
        
        xml_str = ET.tostring(root, encoding='utf-8')
        reparsed = minidom.parseString(xml_str)
        return reparsed.toprettyxml(indent="  ")

    def write_xml(self, output_dir):
        """Write the XML specification to a hashed file in the given directory."""
        xml_content = self.generate_xml()
        h = easy_hash(xml_content)[:20]
        os.makedirs(output_dir, exist_ok=True)
        filename = f"spec-{h}.xml"
        path = os.path.join(output_dir, filename)
        with open(path, "w") as f:
            f.write(xml_content)
        print(f"Specification written to {path}")
        
        # Generate inline source map
        self.generate_source_map(xml_content, path, output_dir)
        
        return path

    def _get_class_lines(self, file_path, class_name):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            tree = ast.parse(source)
        except Exception:
            return None, None
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                return getattr(node, 'lineno', None), getattr(node, 'end_lineno', None)
        return None, None

    def _search_workspace_for_id(self, directory, search_id):
        matches = []
        skip_dirs = {'.git', '.venv', '__pycache__', 'node_modules', 'build', 'dist', '.pytest_cache'}
        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for file in files:
                if file.endswith(('.pyc', '.pyo', '.so', '.dll', '.exe', '.bin', '.xml', '.json', '.out')):
                    continue
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        for lineno, line in enumerate(f, 1):
                            if search_id in line:
                                matches.append({"file": path, "line": lineno})
                except Exception:
                    pass
        return matches

    def generate_source_map(self, xml_content, xml_path, output_dir):
        from lxml import etree
        try:
            tree = etree.fromstring(xml_content.encode('utf-8'))
        except Exception as e:
            print(f"Error parsing XML for source map: {e}")
            return

        source_map = []
        workspace_dir = os.getcwd()

        for spec in tree.xpath('//specification'):
            spec_info = {
                "component": spec.get("type", "Unknown"),
                "python_spec": None,
                "xml_spec": None,
                "generated_code": []
            }

            if spec.sourceline:
                spec_info["xml_spec"] = {
                    "file": str(xml_path),
                    "line": spec.sourceline
                }
            
            source_elem = spec.find("source")
            if source_elem is not None:
                py_file = source_elem.get("file")
                target = source_elem.get("target")
                if py_file and target:
                    start_line, end_line = self._get_class_lines(py_file, target)
                    spec_info["python_spec"] = {
                        "file": py_file,
                        "target": target,
                        "start_line": start_line,
                        "end_line": end_line
                    }

            search_ids = set()
            if spec.get("type"):
                search_ids.add(spec.get("type"))
            
            ctx = spec.find("context")
            if ctx is not None:
                for child in ctx:
                    if child.tag in ['req_id', 'feature_name', 'constraint_id', 'model_name', 'api_name', 'title']:
                        if child.text:
                            search_ids.add(child.text.strip())
            
            generated_matches = []
            for search_id in search_ids:
                if len(search_id) > 2:
                    matches = self._search_workspace_for_id(workspace_dir, search_id)
                    generated_matches.extend(matches)
            
            dedup_matches = []
            seen = set()
            for m in generated_matches:
                k = (m["file"], m["line"])
                if k not in seen:
                    seen.add(k)
                    dedup_matches.append(m)

            spec_info["generated_code"] = dedup_matches
            source_map.append(spec_info)

        out_file = os.path.join(output_dir, "source_map.json")
        try:
            with open(out_file, 'w', encoding='utf-8') as f:
                json.dump(source_map, f, indent=2)
            print(f"Source map written to {out_file}")
        except Exception as e:
            print(f"Error writing source map: {e}")

    def handle_cli(self):
        """Handle command line interface for specification generation."""
        parser = argparse.ArgumentParser(description="libspec CLI")
        parser.add_argument("-o", "--output", help="Output directory for XML specification")
        parser.add_argument("--xml", action="store_true", help="Print XML specification to stdout")
        
        args = parser.parse_args()
        
        if args.output:
            self.write_xml(args.output)
        elif args.xml:
            print(self.generate_xml())
        else:
            self.generate_xml()

class Ctx:
    # No __init__ needed if we use getattr
    
    def _get_base_template(self):
        """Collect docstrings from parent classes and merge them into a single template."""
        templates = []  # List to hold cleaned docstrings

        # Traverse parent classes in the method resolution order,
        # skipping the current class.

        # (MRO stands for Method Resolution
        # Order. In Python, it's the order in which classes are
        # searched when you call a method or access an attribute on an
        # instance.)

        for cls in self.__class__.__mro__[1:]:
            if cls is Ctx:  # Stop at the ultimate base class
                break
            if cls.__doc__:  # Only process classes that have a docstring
                templates.append(cleandoc(cls.__doc__))  # Clean and add the docstring

        # Join all collected docstrings with double newlines, or return empty string
        return "\n\n".join(templates) if templates else ""

    def _get_instance_notes(self):
        """Gets the docstring from the leaf subclass implementation."""
        doc = self.__class__.__doc__
        return cleandoc(doc) if doc else ""

    def _get_source_info(self, obj=None):
        """Extracts source file and line information."""
        import inspect
        import os
        
        target = obj if obj is not None else self.__class__
        
        try:
            source_file = inspect.getsourcefile(target)
            if source_file:
                source_file = os.path.abspath(source_file)
            
            lines, start_line = inspect.getsourcelines(target)
            end_line = start_line + len(lines) - 1
            
            return {
                "file": source_file,
                "start_line": start_line,
                "end_line": end_line,
                "name": target.__name__ if hasattr(target, "__name__") else str(target)
            }
        except (OSError, TypeError):
             return None

    def ctx(self, template_only=True):
        if getattr(self, '_in_ctx', False):
            return {}
        
        self._in_ctx = True
        try:
            return self._do_ctx(template_only)
        finally:
            self._in_ctx = False

    def _do_ctx(self, template_only=True):
        # Always use the base template to find expected variables
        doc = self._get_base_template()
        notes = self._get_instance_notes()
        combined = f"{doc}\n{notes}"
        
        env = Environment()
        ast = env.parse(combined)
        expected_vars = meta.find_undeclared_variables(ast)

        context = {}
        
        # Helper to get member value
        def get_member(var_name):
            method_name = var_name.replace('-', '_')
            if hasattr(self, method_name):
                member = getattr(self, method_name)
                return member() if callable(member) else member
            else:
                src = self._get_source_info()
                loc = f"{src['file']}:{src['start_line']}" if src else "unknown location"
                msg = (
                    f"\nThe variable '{{{{{var_name}}}}}' was found in a docstring template for class '{self.__class__.__name__}',\n"
                    f"defined at {loc},\n"
                    f"but no matching method or attribute '{method_name}' was found.\n\n"
                    f"FIX: implement 'def {method_name}(self):' in class '{self.__class__.__name__}' or one of its bases.\n"
                )
                raise AttributeError(msg)




        # Ensure 'fields' is available if DataSchema is used
        if 'fields' in expected_vars and hasattr(self, 'fields'):
            context['fields'] = self.fields()

        for var in sorted(expected_vars):
            if var == 'fields': continue
            context[var] = get_member(var)

        if not template_only:
            # Also capture all other non-private members for XML/structured data
            # dir() is sorted by default, but we'll be explicit for clarity
            for name in sorted(dir(self)):
                if name.startswith('_') or name in ['ctx', 'render', 'render_xml', 'to_xml_element']:
                    continue
                if name in ['_get_base_template', '_get_instance_notes', '_get_source_info', '_to_xml_element']:
                    continue
                if name in context: # Already added from template
                    continue
                
                member = getattr(self, name)
                if callable(member):
                    try:
                        sig = signature(member)
                        if len(sig.parameters) == 0:
                            context[name] = member()
                    except (TypeError, ValueError, UnimplementedMethodError):
                        continue
                else:
                    context[name] = member

        return context

    def _to_xml_element(self, name, value):
        """Recursively convert context data to XML elements."""
        elem = ET.Element(name)
        if isinstance(value, dict):
            # Sort items for deterministic order in XML
            for k in sorted(value.keys()):
                if k in ['start_line', 'end_line']:
                    continue
                v = value[k]
                elem.append(self._to_xml_element(str(k).replace('-', '_'), v))
        elif isinstance(value, list):
            for item in value:
                elem.append(self._to_xml_element("item", item))
        else:
            elem.text = str(value)
        return elem

    def render_xml(self):
        """Render the specification as structured XML."""
        root = self.to_xml_element()
        # Pretty print
        xml_str = ET.tostring(root, encoding='utf-8')
        reparsed = minidom.parseString(xml_str)
        return reparsed.toprettyxml(indent="  ")

    def to_xml_element(self):
        """Convert the specification to an XML element."""
        root = ET.Element("specification")
        root.set("type", self.__class__.__name__)
        
        # Source info
        src = self._get_source_info()
        if src:
            source_elem = ET.SubElement(root, "source")
            source_elem.set("target", src["name"])
            source_elem.set("file", src["file"])

        # Docstrings
        base_template = self._get_base_template()
        instance_notes = self._get_instance_notes()
        
        ctx_data = self.ctx()
        rendered_body = Template(base_template).render(**ctx_data).strip()

        if rendered_body:
            desc_elem = ET.SubElement(root, "description")
            desc_elem.text = rendered_body

        if instance_notes:
            notes_elem = ET.SubElement(root, "notes")
            rendered_notes = Template(instance_notes).render(**ctx_data).strip()
            notes_elem.text = rendered_notes

        # Context data
        context_elem = ET.SubElement(root, "context")
        all_ctx_data = self.ctx(template_only=False)
        # Sort keys to ensure stable XML tag order
        for k in sorted(all_ctx_data.keys()):
            v = all_ctx_data[k]
            context_elem.append(self._to_xml_element(str(k).replace('-', '_'), v))
            
        return root

class Feature(Ctx):
    '''
    Feature Specification: {{feature_name}}
    Feature Branch: [feat-{{feature_name}}]
    
    '''
    def feature_name(self):
        return self.__class__.__name__

    def date(self):
        raise UnimplementedMethodError()
    
    def description(self):
        raise UnimplementedMethodError()
    
class Def(Ctx):
    '''
    Definition: {{name}}:
    
    '''
    def name(self):
        return fqn(self)
        
    
class EdgeCase(Ctx):
    '''
    Edge Case

    What happens when {{boundary_condition}}?
    How does system handle {{error_scenerio}}?
    '''
    def bounary_condition(self):
        raise UnimplementedMethodError()
    def error_scenerio(self):
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
        """
        Return only methods declared on the **leaf subclass**, ignoring Ctx or other base classes.
        """
        method_list = []
        cls = self.__class__

        # Get only methods defined on this class, not inherited
        for name, attr in cls.__dict__.items():
            if name.startswith('_'):  # Skip private methods
                continue
            if not isfunction(attr):
                continue

            sig = signature(attr)
            params = [p for p in sig.parameters.keys() if p != 'self']
            doc = cleandoc(attr.__doc__ or "No description provided")
            
            member = getattr(self, name)
            
            if callable(member):
                k = member(*[None] * len(params))
            else:
                k = member
            
            method_list.append({
                "name": name,
                "params": params,
                "description": doc,
                "result": k,
                "source_ref": self._get_source_info(attr)
            })

        return method_list

    
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
    '''
    Library API Version: {{version}}
    This is not a network API, rather this is a library API. 
    '''

    
class RestMixin:
    '''
    Develop a REST API with best practices around this interface
    '''


class CmdLine(Ctx, LeafMethods):
    '''
    Command Line Specification

    implement these commands:
    {% for method in methods %}
      | {{method.name}}({{method.params|join(', ')}})
      | Description: {{method.description}}
      | {{method.result}}
    {% endfor %}
    '''

class Implementation(Requirement):
    '''
    Implementation requirements.
    Implementations must include tests.
    
    All files generated by this implementation should live in the
    directory:{{implementation_directory}}
    '''

def classes_with_ctx_superclass(module):
    result = []
    for _, obj in inspect.getmembers(module, inspect.isclass):
        # ensure the class is defined in this module (optional but common)
        if obj.__module__ != module.__name__:
            continue
        if issubclass(obj, Ctx) and obj is not Ctx:
            result.append(obj)
    return result

def module_specs(mod):
    cs = classes_with_ctx_superclass(mod)
    return [C() for C in cs]
