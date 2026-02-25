import pytest
import os
import inspect
from libspec.spec import Ctx, Feature, LeafMethods, UnimplementedMethodError

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
        assert "Hello World" in output
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
        assert "Header" in output
        assert "Body" in output
        assert "Footer" in output
        
        # Verify order
        assert output.find("Header") < output.find("Body")
        assert output.find("Body") < output.find("Footer")

    def test_missing_implementation_error(self):
        class BrokenTemplate(Ctx):
             """
             {{missing_method}}
             """
        
        class BrokenSpec(BrokenTemplate):
            pass
        
        with pytest.raises(AttributeError, match="The variable '{{missing_method}}' was found"):
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
        names = [m['name'] for m in methods]
        
        assert "endpoint_a" in names
        assert "endpoint_b" in names
        assert "methods" not in names # Should skip itself from LeafMethods
        
    def test_method_source_info(self):
        class LocatedApi(Ctx, LeafMethods):
            def my_func(self):
                pass
                
        inst = LocatedApi()
        methods = inst.methods()
        target = next(m for m in methods if m['name'] == 'my_func')
        
        assert target['source_ref'] is not None
        assert target['source_ref']['name'] == 'my_func'
        # Line numbers are tricky to assert exactly without being brittle, 
        # but file path should match
        assert target['source_ref']['file'] == os.path.abspath(__file__)

    def test_unimplemented_method(self):
        # Feature class triggers UnimplementedMethodError by default for date/desc
        class MyFeature(Feature):
            pass
            
        # Implementation of feature_name is in Feature base class, but others missing
        inst = MyFeature()
        assert inst.feature_name() == "MyFeature"
        
        with pytest.raises(UnimplementedMethodError):
            inst.date()
