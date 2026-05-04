from lxml import etree
import pytest
from libspec.spec_diff import _print_inherited_context

def test_templated_superspec_renders_with_child_context(capsys):
    """
    Verify that a templated superspec (e.g. Requirement) is rendered
    using the child's context during diff generation.
    """
    root = etree.fromstring(
        """
        <specification_set>
          <!-- Templated Superspec -->
          <specification type='Requirement' ref='libspec.spec.Requirement' template='true'>
            <docstring_template>TITLE: {{title}}\nID: {{req_id}}</docstring_template>
          </specification>
          
          <!-- Child Spec inheriting from it -->
          <specification type='GridZoom' ref='sprocket.GridZoom'>
            <context>
              <title>GridZoom Component</title>
              <req_id>sprocket.GridZoom</req_id>
            </context>
            <inherits>
              <ref>libspec.spec.Requirement</ref>
            </inherits>
            <docstring>Local behavior</docstring>
          </specification>
        </specification_set>
        """
    )
    
    specs_by_ref = {spec.get("ref"): spec for spec in root.xpath("//specification")}
    child_spec = specs_by_ref["sprocket.GridZoom"]
    
    # We call _print_inherited_context for the child spec
    _print_inherited_context(child_spec, specs_by_ref)
    
    output = capsys.readouterr().out
    
    # Verify that the superspec is listed as a template instance
    assert "Requirement: libspec.spec.Requirement (template instance)" in output
    
    # Verify that it was rendered using the child's context
    assert "requirement:" in output
    assert "TITLE: GridZoom Component" in output
    assert "ID: sprocket.GridZoom" in output

def test_static_superspec_deduplication_indicator(capsys):
    """
    Verify that a static superspec is NOT rendered in-place when 
    a shared_superspecs context is provided, indicating it will 
    be shown at the top.
    """
    root = etree.fromstring(
        """
        <specification_set>
          <specification type='Err' ref='spec.err.Err' template='false'>
            <docstring>Standard Error Policy</docstring>
          </specification>
          
          <specification type='MyComp' ref='my.Comp'>
            <inherits>
              <ref>spec.err.Err</ref>
            </inherits>
          </specification>
        </specification_set>
        """
    )
    
    specs_by_ref = {spec.get("ref"): spec for spec in root.xpath("//specification")}
    child_spec = specs_by_ref["my.Comp"]
    shared_superspecs = {}
    
    _print_inherited_context(child_spec, specs_by_ref, shared_superspecs)
    
    output = capsys.readouterr().out
    
    # It should list the spec, but NOT the requirement prose (it's in shared_superspecs instead)
    assert "Err: spec.err.Err" in output
    assert "requirement:" not in output
    assert "spec.err.Err" in shared_superspecs
