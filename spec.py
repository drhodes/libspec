from err import UnimplementedMethodError

import re
from jinja2 import Template
from inspect import cleandoc

class Ctx:
    def _get_template_doc(self):
        for cls in self.__class__.__mro__:
            if cls is Ctx: break
            if cls.__doc__: return cleandoc(cls.__doc__)
        return ""

    def ctx(self):
        doc = self._get_template_doc()
        # Find all {{ var }} or {{ var-name }}
        vars_found = re.findall(r'\{\{\s*([\w-]+)\s*\}\}', doc)
        
        context = {}
        missing_methods = []

        for var in set(vars_found):
            # Map hyphenated template vars to snake_case methods
            method_name = var.replace('-', '_')
            
            if hasattr(self, method_name):
                context[method_name] = getattr(self, method_name)()
            else:
                missing_methods.append(method_name)

        if missing_methods:
            raise AttributeError(f"Missing methods for template variables: {', '.join(missing_methods)}")
            
        return context

    def render(self):
        template_str = self._get_template_doc()
        # Normalize hyphens in the template string so Jinja can read the dict keys
        normalized_template = re.sub(r'\{\{\s*([\w]+)-([\w-]+)\s*\}\}', r'{{\1_\2}}', template_str)
        
        return Template(normalized_template).render(**self.ctx()).strip()
    

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
    STRUCTURE: {{fields}}
    INVARIANTS: {{invariants}}
    """
    pass
