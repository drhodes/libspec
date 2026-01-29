import re
from jinja2 import Environment, meta, Template
from inspect import signature, cleandoc, isfunction


from libspec.err import UnimplementedMethodError

class Ctx:
    def _get_base_template(self):
        """
        Collect all template docstrings from the class hierarchy and merge them.
        Start from the most specific (closest parent) to most general.
        """
        templates = []

        # Walk the MRO, skipping the leaf class and Ctx itself
        for cls in self.__class__.__mro__[1:]:
            if cls is Ctx:
                break  # Stop at Ctx
            if cls.__doc__:
                templates.append(cleandoc(cls.__doc__))

        # Join all templates with double newline
        return "\n\n".join(templates) if templates else ""


    def _get_instance_notes(self):
        """Gets the docstring from the leaf subclass implementation."""
        doc = self.__class__.__doc__
        return cleandoc(doc) if doc else ""

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
        
        if instance_notes:
            return f"{instance_notes}\n\n{rendered_body}"
        return rendered_body


class Feature(Ctx):
    '''
    Feature Specification: {{feature_name}}
    Feature Branch: [feat-{{feature_name}}]
    Created: [{{date}}]
    Status: Draft
    Input: User description: {{description}}
    '''
    def feature_name(self):
        return self.__class__.__name__
    def date(self):
        raise UnimplementedMethodError()
    def description(self):
        raise UnimplementedMethodError()


class EdgeCase():
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
    pass


class Requirement(Ctx):
    """
    Requirement
    REQUIREMENT-ID: {{req_id}}
    TITLE: {{title}}
    USER-STORY: As a `{{actor}}`, I want to `{{action}}` so that `{{benefit}}`.
    """
    pass

class SystemRequirement(Requirement):
    """System Requirement: This is a tool level requirement aimed at the
    toolchain supporting the project.
    """
    pass



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


class LeafMethods:   
    def methods(self):
        """
        Return only methods declared on the **leaf subclass**, ignoring Ctx or other base classes.
        """
        method_list = []
        cls = self.__class__

        # Get only methods defined on this class, not inherited
        for name, attr in cls.__dict__.items():
            if name.startswith('_'):  # Skip private/dunder methods
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
