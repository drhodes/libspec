import re
from jinja2 import Environment, meta, Template
from inspect import cleandoc

from err import UnimplementedMethodError
class Ctx:
    def _get_base_template(self):
        """Finds the template docstring in the first parent class (e.g. Feature)."""
        for cls in self.__class__.__mro__:
            # We look for the class that is a direct child of Ctx
            # This is our 'Template' layer (Feature, Constraint, etc.)
            if Ctx in cls.__bases__:
                return cleandoc(cls.__doc__ or "")
        return ""

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
        raise UnimplementedMethodError()
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
    USER-STORY: As a {{actor}}, I want to {{action}} so that {{benefit}}.
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
    def fields(self):
        return self.__class__.__annotations__

    
