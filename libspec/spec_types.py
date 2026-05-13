from inspect import signature, cleandoc, isfunction
from libspec.err import UnimplementedMethodError
from libspec.util import fqn
from libspec.spec import Ctx

class Feature(Ctx):
    """
    Feature Specification: {{feature_name}}

    """

    # Return the name of the feature based on its class name.
    def feature_name(self):
        return self.__class__.__name__

    # Return the date associated with the feature.
    def date(self):
        raise UnimplementedMethodError()

    # Return the description of the feature.
    def description(self):
        raise UnimplementedMethodError()


class Def(Ctx):
    """
    Definition: {{name}}:

    """

    # Return the fully qualified name of the definition.
    def name(self):
        return fqn(self)


class EdgeCase(Ctx):
    """
    Edge Case

    What happens when {{boundary_condition}}?
    How does system handle {{error_scenario}}?
    """

    # Return the boundary condition for the edge case.
    def boundary_condition(self):
        raise UnimplementedMethodError()

    # Return the error scenario for the edge case.
    def error_scenario(self):
        raise UnimplementedMethodError()


class Constraint(Ctx):
    """
    CONSTRAINT-ID: {{constraint_id}}
    DESCRIPTION: {{description}}
    ENFORCEMENT: {{enforcement_logic}}
    """

    # Return the ID of the constraint.
    def constraint_id(self):
        return self.__class__.__name__

    # Return the description of the constraint based on its docstring.
    def description(self):
        return self.__class__.__doc__


class Requirement(Ctx):
    """
    Requirement
    TITLE: {{title}}
    REQUIREMENT-ID: {{req_id}}

    Insert REQUIREMENT-ID into any source code for cross reference purposes.
    """

    # Return the title of the requirement.
    def title(self):
        return self.__class__.__name__

    # Return the ID of the requirement.
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

    # Return the name of the data model.
    def model_name(self):
        return self.__class__.__name__

    # Return the field annotations for the data model.
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
    # Return method descriptors for leaf-class public methods.
    def methods(self):
        """Return method descriptors for leaf-class public methods."""
        descriptors = []
        for name, func in self._leaf_public_functions():
            descriptors.append(self._method_descriptor(name, func))
        return descriptors

    # Yield names and function objects for public functions defined in the leaf class.
    def _leaf_public_functions(self):
        cls = self.__class__
        for name, attr in cls.__dict__.items():
            if name.startswith("_"):
                continue
            if isfunction(attr):
                yield name, attr

    # Construct a descriptor dictionary for a single method.
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

    # Return method parameter names excluding 'self'.
    def _method_params_without_self(self, func):
        return [p for p in signature(func).parameters.keys() if p != "self"]

    # Safely invoke a member to get a preview of its result.
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

    # Return the name of the API.
    def api_name(self):
        """Name of the API."""
        return self.__class__.__name__

    # Return a list of API-level constraints.
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


class UserStory(Feature):
    """
    brief-title: {{brief_title}}
    priority: {{priority}}
    user-journey: {{user_journey}}
    explanation: {{explanation}}
    acceptance-scenarios: {{acceptance_scenarios}}
    """
