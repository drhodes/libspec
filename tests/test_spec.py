import os

import pytest

from libspec.spec import Ctx, Feature, LeafMethods, UnimplementedMethodError


class ExternalBaseSpec(Ctx):
    """
    External base spec docstring
    """

    pass


class LocalSpec(ExternalBaseSpec):
    """
    Local spec docstring
    """

    pass


class TestCtxComponents:
    def test_basic_rendering(self):
        # Template must be in the parent class
        class SimpleTemplate(Ctx):
            """
            Hello {{name}}
            """

        class SimpleSpec(SimpleTemplate):
            def name(self):
                return "World"

        output = SimpleSpec().render_xml()
        assert "SimpleTemplate</ref>" in output
        assert "<name>World</name>" in output
        assert "Hello World" not in output
        assert '<source target="SimpleSpec"' in output

    def test_inheritance_rendering(self):
        class GrandParent(Ctx):
            """
            Header
            """

        class Parent(GrandParent):
            """
            Body
            """

        class Child(Parent):
            """
            Footer notes (not part of template rendering by default, just prepended)
            """

        output = Child().render_xml()
        assert "Footer" in output
        assert "<docstring>Footer notes" in output
        assert "<ref>test_spec." in output
        assert "GrandParent</ref>" in output
        assert "Parent</ref>" in output
        assert "Header" not in output
        assert "Body" not in output

    def test_missing_implementation_error(self):
        class BrokenTemplate(Ctx):
            """
            {{missing_method}}
            """

        class BrokenSpec(BrokenTemplate):
            pass

        with pytest.raises(
            AttributeError, match="The variable '{{missing_method}}' was found"
        ):
            BrokenSpec().render_xml()


class TestLeafMethods:
    def test_method_extraction(self):
        class MyApi(Ctx, LeafMethods):
            """
            API
            {% for m in methods %}
            {{m.name}}
            {% endfor %}
            """

            def endpoint_a(self):
                """Doc A"""
                pass

            def endpoint_b(self):
                pass

        inst = MyApi()
        methods = inst.methods()
        names = [m["name"] for m in methods]

        assert "endpoint_a" in names
        assert "endpoint_b" in names
        assert "methods" not in names  # Should skip itself from LeafMethods

    def test_method_source_info(self):
        class LocatedApi(Ctx, LeafMethods):
            def my_func(self):
                pass

        inst = LocatedApi()
        methods = inst.methods()
        target = next(m for m in methods if m["name"] == "my_func")

        assert target["source_ref"] is not None
        assert target["source_ref"]["name"] == "my_func"
        # Line numbers are tricky to assert exactly without being brittle,
        # but file path should match
        assert target["source_ref"]["file"] == os.path.abspath(__file__)

    def test_unimplemented_method(self):
        # Feature class triggers UnimplementedMethodError by default for date/desc
        class MyFeature(Feature):
            pass

        # Implementation of feature_name is in Feature base class, but others missing
        inst = MyFeature()
        assert inst.feature_name() == "MyFeature"

        with pytest.raises(UnimplementedMethodError):
            inst.date()


class TestClassFieldsRendering:
    def test_class_field_resolution(self):
        class FieldTemplate(Ctx):
            """
            Values: {{my_str}} and {{my_int}}
            """

        class FieldSpec(FieldTemplate):
            my_str = "hello"
            my_int = 42

        output = FieldSpec().render_xml()
        assert "<my_str>hello</my_str>" in output
        assert "<my_int>42</my_int>" in output

    def test_type_annotation_resolution_with_default(self):
        class AnnotationTemplate(Ctx):
            """
            Host: {{db_host}}
            """

            db_host: str = "127.0.0.1"

        class AnnotationSpec(AnnotationTemplate):
            pass

        output = AnnotationSpec().render_xml()
        assert "<db_host>127.0.0.1</db_host>" in output

    def test_type_annotation_resolution_without_default_raises(self):
        class NoDefaultTemplate(Ctx):
            """
            Value: {{api_key}}
            """

            api_key: str

        class NoDefaultSpec(NoDefaultTemplate):
            pass

        with pytest.raises(
            AttributeError,
            match="Field 'api_key' is declared via type annotations but lacks a value",
        ):
            NoDefaultSpec().render_xml()

    def test_resolution_priority_order(self):
        class BaseSpec(Ctx):
            def val(self):
                return "method_call"

        class PrioritySpec(BaseSpec):
            """
            Override: {{val}}
            """

            val = "static_field"

        output = PrioritySpec().render_xml()
        assert "<val>static_field</val>" in output

    def test_spec_compiler_dependency_flag(self):
        import types

        from libspec.spec import Spec

        ExternalBaseSpec.__module__ = "other_mod"
        LocalSpec.__module__ = "mock_mod"

        # Create simulated module
        mock_mod = types.ModuleType("mock_mod")
        mock_mod.LocalSpec = LocalSpec
        mock_mod.ExternalBaseSpec = ExternalBaseSpec

        # Mock Spec class running over our mock module
        class MySpecSuite(Spec):
            def modules(self):
                return [mock_mod]

        suite = MySpecSuite()
        comps = suite.get_components()

        assert len(comps) == 2
        comp_map = {c.ref: c for c in comps}

        assert "mock_mod.LocalSpec" in comp_map
        assert comp_map["mock_mod.LocalSpec"].is_dependency is False

        assert "other_mod.ExternalBaseSpec" in comp_map
        assert comp_map["other_mod.ExternalBaseSpec"].is_dependency is True


def test_dependency_stub_template_rendering(tmp_path):
    """Dependency stubs with Jinja templates must be rendered, not stored raw.

    Regression test for: get_components() Pass 2 previously set
    docstring = template_text unconditionally, leaving {{placeholders}} verbatim.

    Runs in a subprocess to avoid lru_cache cross-contamination between
    parallel pytest-xdist workers.
    """
    import subprocess
    import sys

    script = """
import sys, types
from libspec.spec import Ctx, Spec

base_mod_name = '_stub_base'
concrete_mod_name = '_stub_concrete'

base_mod = types.ModuleType(base_mod_name)
concrete_mod = types.ModuleType(concrete_mod_name)
sys.modules[base_mod_name] = base_mod
sys.modules[concrete_mod_name] = concrete_mod

class TemplatedBase(Ctx):
    '''
    ID: {{my_id}}
    '''
    def my_id(self):
        return 'rendered-value'

class ConcreteSpec(TemplatedBase):
    '''Concrete spec that inherits the templated base.'''

TemplatedBase.__module__ = base_mod_name
base_mod.TemplatedBase = TemplatedBase
ConcreteSpec.__module__ = concrete_mod_name
concrete_mod.ConcreteSpec = ConcreteSpec

class Suite(Spec):
    def modules(self):
        return [concrete_mod]

comps = Suite().get_components()
comp_map = {c.ref: c for c in comps}

stub = comp_map.get(f'{base_mod_name}.TemplatedBase')
assert stub is not None, f'stub missing; got refs: {list(comp_map)}'
assert stub.is_dependency is True, 'stub must be marked as dependency'
assert '{{' not in stub.docstring, f'unrendered template in: {stub.docstring!r}'
assert 'rendered-value' in stub.docstring, f'expected rendered value in: {stub.docstring!r}'
print('OK')
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.pathsep.join(sys.path)

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=str(tmp_path.parent),
        env=env,
    )
    assert result.returncode == 0, (
        f"Subprocess failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    )
    assert "OK" in result.stdout
