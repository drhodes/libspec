import os
import pytest
import xml.etree.ElementTree as ET
from libspec.spec import Ctx, Feature

def test_render_xml_basic():
    class TestBase(Ctx):
        """
        Base description {{name}}
        """

    class TestSpec(TestBase):
        """
        Instance notes
        """
        def name(self):
            return "TestName"

    rendered = TestSpec().render_xml()
    root = ET.fromstring(rendered)

    assert root.tag == "specification"
    assert root.attrib["type"] == "TestSpec"
    
    source = root.find("source")
    assert source is not None
    assert source.attrib["target"] == "TestSpec"

    description = root.find("description")
    assert description is not None
    assert "Base description TestName" in description.text

    notes = root.find("notes")
    assert notes is not None
    assert "Instance notes" in notes.text

    context = root.find("context")
    assert context is not None
    name_elem = context.find("name")
    assert name_elem is not None
    assert name_elem.text == "TestName"

def test_render_xml_complex_data():
    class ComplexCtx(Ctx):
        """Doc"""
        def data(self):
            return {
                "key1": "value1",
                "key2": [1, 2, {"nested": "val"}],
                "dashed-key": "ok"
            }

    rendered = ComplexCtx().render_xml()
    root = ET.fromstring(rendered)
    
    context = root.find("context")
    data_elem = context.find("data")
    assert data_elem is not None
    
    assert data_elem.find("key1").text == "value1"
    
    key2 = data_elem.find("key2")
    items = key2.findall("item")
    assert len(items) == 3
    assert items[0].text == "1"
    assert items[1].text == "2"
    assert items[2].find("nested").text == "val"
    
    assert data_elem.find("dashed_key").text == "ok"

def test_spec_generate_xml():
    from libspec.spec import Spec
    import sys
    from types import ModuleType

    # Mock a module with specs
    mock_mod = ModuleType("mock_mod")
    class MyFeature(Feature):
        """Doc"""
        def val(self): return 1
    
    MyFeature.__module__ = "mock_mod" # Important for module_specs
    mock_mod.MyFeature = MyFeature
    sys.modules["mock_mod"] = mock_mod

    class MySpec(Spec):
        def modules(self):
            return [mock_mod]

    rendered = MySpec().generate_xml()
    root = ET.fromstring(rendered)

    assert root.tag == "specification_set"
    specs = root.findall("specification")
    assert len(specs) == 1
    assert specs[0].attrib["type"] == "MyFeature"
    assert specs[0].find("context").find("val").text == "1"

    del sys.modules["mock_mod"]

def test_spec_write_xml(tmp_path):
    from libspec.spec import Spec
    from types import ModuleType
    import sys

    output_dir = tmp_path / "specs"
    
    mock_mod = ModuleType("mock_mod_write")
    class MyFeature(Feature):
        """Doc"""
        def val(self): return 1
    
    MyFeature.__module__ = "mock_mod_write"
    mock_mod.MyFeature = MyFeature
    sys.modules["mock_mod_write"] = mock_mod

    class MySpec(Spec):
        def modules(self):
            return [mock_mod]

    path = MySpec().write_xml(str(output_dir))
    
    assert os.path.exists(path)
    assert os.path.basename(path).startswith("spec-")
    
    with open(path) as f:
        content = f.read()
        assert "<specification_set>" in content
        assert "MyFeature" in content

    del sys.modules["mock_mod_write"]

def test_recursion_protection():
    class RecursiveCtx(Ctx):
        """{{me}}"""
        def me(self):
            return self.render_xml() # This would normally recurse infinitely

    # This should not raise RecursionError now
    rendered = RecursiveCtx().render_xml()
    assert "<specification" in rendered
    # The nested context should be empty because of the guard
    # It will be escaped because it's returned as a string and then put in XML
    assert "&lt;context/&gt;" in rendered or "&lt;context&gt;&lt;/context&gt;" in rendered
    # AND the outer context should have 'me'
    assert "<me>" in rendered

def test_no_line_numbers_in_xml():
    class TestSpec(Ctx):
        """Doc"""
        def val(self): return 1
    
    rendered = TestSpec().render_xml()
    assert 'lines="' not in rendered
    assert 'start_line' not in rendered
    assert 'end_line' not in rendered
