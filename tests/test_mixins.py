import pytest
from libspec.spec import Ctx, Feature

def test_mixin_docstring_included():
    class MyMixin:
        """
        Mixin info: {{mixin_var}}
        """
        def mixin_var(self):
            return "from mixin"

    class BaseFeature(Feature):
        """
        Base info: {{base_var}}
        """
        def base_var(self):
            return "from base"

    class CombinedSpec(BaseFeature, MyMixin):
        """
        Leaf notes
        """
        def date(self): return "2024-01-01"
        def description(self): return "desc"

    inst = CombinedSpec()
    xml = inst.render_xml()
    
    # Check if both docstrings are in the description
    assert "Base info: from base" in xml
    assert "Mixin info: from mixin" in xml
    assert "Leaf notes" in xml

def test_multiple_mixins():
    class MixinA:
        """A: {{a}}"""
        def a(self): return "A"
    
    class MixinB:
        """B: {{b}}"""
        def b(self): return "B"
        
    class MultiSpec(Feature, MixinA, MixinB):
        def date(self): return "2024-01-01"
        def description(self): return "desc"
        
    xml = MultiSpec().render_xml()
    assert "A: A" in xml
    assert "B: B" in xml
