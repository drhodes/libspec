import inspect
from jinja2 import Environment, meta, Template
from inspect import signature, cleandoc, isfunction
from libspec.err import UnimplementedMethodError
from libspec.util import fqn



class Spec:
    def modules(self):
        raise UnimplementedMethodError()
        
    def generate(self):
        """Generate the complete specification document."""
        for mod in self.modules():
            for spec in module_specs(mod):
                print(80 * "-")
                print(spec.render())

class Ctx:
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

    def ctx(self):
        # Always use the base template to find expected variables
        doc = self._get_base_template()
        if not doc: return {}

        env = Environment()
        ast = env.parse(doc)
        expected_vars = meta.find_undeclared_variables(ast)

        context = {}
        # Ensure 'fields' is available if DataSchema is used
        if 'fields' in expected_vars and hasattr(self, 'fields'):
            context['fields'] = self.fields()

        for var in expected_vars:
            if var == 'fields': continue
            method_name = var.replace('-', '_')
            if hasattr(self, method_name):
                member = getattr(self, method_name)
                context[var] = member() if callable(member) else member
            else:
                raise AttributeError(f"Missing {method_name} in {self.__class__.__name__}")
        return context

    def render(self):
        base_template = self._get_base_template()
        instance_notes = self._get_instance_notes()
        
        rendered_body = Template(base_template).render(**self.ctx()).strip()
        
        final_output = rendered_body
        if instance_notes:
            final_output = f"{instance_notes}\n\n{rendered_body}"
            
        src = self._get_source_info()
        if src:
             return f'<source_ref target="{src["name"]}" file="{src["file"]}" lines="{src["start_line"]}-{src["end_line"]}">\n{final_output}\n</source_ref>'
        return final_output

class Feature(Ctx):
    '''
    Feature Specification: {{feature_name}}
    Feature Branch: [feat-{{feature_name}}]
    
    '''
    def feature_name(self):
        return self.__class__.__name__
    
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
