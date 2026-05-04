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
    
    # Inherited docstrings are referenced instead of compiled into the child.
    assert "BaseFeature</ref>" in xml
    assert "MyMixin</ref>" in xml
    assert "Base info: from base" not in xml
    assert "Mixin info: from mixin" not in xml
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
    assert "MixinA</ref>" in xml
    assert "MixinB</ref>" in xml
    assert "A: A" not in xml
    assert "B: B" not in xml
