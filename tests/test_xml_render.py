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

    docstring = root.find("docstring")
    assert docstring is not None
    assert "Instance notes" in docstring.text
    assert root.find("description") is None
    assert root.find("notes") is None

    inherits = root.find("inherits")
    assert inherits is not None
    refs = [ref.text for ref in inherits.findall("ref")]
    assert any(ref.endswith("TestBase") for ref in refs)

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
    spec_by_type = {spec.attrib["type"]: spec for spec in specs}
    assert "MyFeature" in spec_by_type
    assert "Feature" in spec_by_type
    assert spec_by_type["MyFeature"].attrib["ref"].endswith("MyFeature")
    assert spec_by_type["MyFeature"].attrib["ref"].startswith("mock_mod.")
    assert spec_by_type["MyFeature"].find("context").find("val").text == "1"
    assert spec_by_type["Feature"].attrib.get("dependency") == "true"
    assert spec_by_type["Feature"].find("docstring_template") is not None

    del sys.modules["mock_mod"]


def test_spec_generate_xml_emits_external_inherited_dependency():
    from libspec.spec import Spec
    import sys
    from types import ModuleType

    base_mod = ModuleType("base_mod")
    class ExternalBase(Ctx):
        """External base template {{name}}"""
    ExternalBase.__module__ = "base_mod"
    base_mod.ExternalBase = ExternalBase
    sys.modules["base_mod"] = base_mod

    child_mod = ModuleType("child_mod")
    class ChildSpec(ExternalBase):
        """Local child"""
        def name(self):
            return "x"
    ChildSpec.__module__ = "child_mod"
    child_mod.ChildSpec = ChildSpec
    sys.modules["child_mod"] = child_mod

    class MySpec(Spec):
        def modules(self):
            return [child_mod]

    rendered = MySpec().generate_xml()
    root = ET.fromstring(rendered)
    specs = root.findall("specification")
    child = next(spec for spec in specs if spec.attrib["type"] == "ChildSpec")
    external = next(spec for spec in specs if spec.attrib["type"] == "ExternalBase")

    assert child.attrib["ref"].startswith("child_mod.")
    assert child.attrib["ref"].endswith("ChildSpec")
    assert external.attrib["ref"].startswith("base_mod.")
    assert external.attrib["ref"].endswith("ExternalBase")
    assert external.attrib.get("dependency") == "true"
    assert external.find("docstring_template").text == "External base template {{name}}"

    del sys.modules["child_mod"]
    del sys.modules["base_mod"]

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
        assert "<specification_set" in content
        assert 'date-created="' in content
        assert 'libspec-version="' in content
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

def test_spec_generate_xml_no_date_created():
    from libspec.spec import Spec
    import sys
    from types import ModuleType

    # Mock a module with specs
    mock_mod = ModuleType("mock_mod_date")
    from libspec.spec import Feature
    class MyFeature(Feature):
        """Doc"""
        def val(self): return 1
    
    MyFeature.__module__ = "mock_mod_date"
    mock_mod.MyFeature = MyFeature
    sys.modules["mock_mod_date"] = mock_mod

    class MySpec(Spec):
        def modules(self):
            return [mock_mod]

    rendered = MySpec().generate_xml()
    root = ET.fromstring(rendered)

    assert root.tag == "specification_set"
    assert "date-created" not in root.attrib

    del sys.modules["mock_mod_date"]
