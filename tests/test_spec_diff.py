from lxml import etree

from libspec.spec_diff import (
    _compare_specs,
    _inherited_context,
    _inherited_docstrings,
    _print_inherited_specs,
    generate_patch,
)


def test_compare_specs_handles_missing_description_and_notes():
    old_spec = etree.fromstring("<specification type='A'><context/></specification>")
    new_spec = etree.fromstring("<specification type='A'><context/></specification>")

    changes = _compare_specs(old_spec, new_spec)

    assert changes == []


def test_compare_specs_reports_human_fields_changes():
    old_spec = etree.fromstring(
        """
        <specification type='MoveEntity'>
          <title>MoveEntity</title>
          <req_id>spec.actions.MoveEntity</req_id>
          <description>Old description text</description>
          <notes>Old notes text</notes>
        </specification>
        """
    )
    new_spec = etree.fromstring(
        """
        <specification type='MoveEntity'>
          <title>MoveEntityV2</title>
          <req_id>spec.actions.MoveEntityV2</req_id>
          <description>New description text</description>
          <notes>New notes text</notes>
        </specification>
        """
    )

    changes = _compare_specs(old_spec, new_spec)

    assert any(c.startswith("title: ") for c in changes)
    assert any(c.startswith("req_id: ") for c in changes)
    assert any(c.startswith("description: ") for c in changes)
    assert any(c.startswith("notes: ") for c in changes)


def test_compare_specs_reports_docstring_and_inherits_ref_changes():
    old_spec = etree.fromstring(
        """
        <specification type='MoveEntity' ref='spec.actions.MoveEntity'>
          <inherits>
            <ref>spec.actions.Action</ref>
          </inherits>
          <docstring>Old local behavior</docstring>
        </specification>
        """
    )
    new_spec = etree.fromstring(
        """
        <specification type='MoveEntity' ref='spec.actions.MoveEntity'>
          <inherits>
            <ref>spec.actions.Action</ref>
            <ref>spec.err.ErrPolicy</ref>
          </inherits>
          <docstring>New local behavior</docstring>
        </specification>
        """
    )

    changes = _compare_specs(old_spec, new_spec)

    assert any(c.startswith("inherits: ") for c in changes)
    assert any(c.startswith("docstring:") for c in changes)


def test_compare_specs_deduplicates_delta_notes_when_same_as_docstring_change():
    old_spec = etree.fromstring(
        """
        <specification type='GridZoom'>
          <docstring>Old line</docstring>
          <delta_requirements>
            <notes>Old line</notes>
          </delta_requirements>
        </specification>
        """
    )
    new_spec = etree.fromstring(
        """
        <specification type='GridZoom'>
          <docstring>New line</docstring>
          <delta_requirements>
            <notes>New line</notes>
          </delta_requirements>
        </specification>
        """
    )

    changes = _compare_specs(old_spec, new_spec)

    assert any(c.startswith("docstring:") for c in changes)
    assert not any(c.startswith("delta.notes:") for c in changes)


def test_inherited_docstrings_are_resolved_from_refs_after_diff():
    root = etree.fromstring(
        """
        <specification_set>
          <specification type='Action' ref='spec.actions.Action'>
            <docstring>Base action behavior</docstring>
          </specification>
          <specification type='MoveEntity' ref='spec.actions.MoveEntity'>
            <inherits>
              <ref>spec.actions.Action</ref>
            </inherits>
            <docstring>Move behavior</docstring>
          </specification>
        </specification_set>
        """
    )
    specs_by_ref = {spec.get("ref"): spec for spec in root.xpath("//specification")}

    docs = _inherited_docstrings(["spec.actions.Action"], specs_by_ref)

    assert docs == [("spec.actions.Action", "Base action behavior")]


def test_inherited_context_resolves_transitive_refs():
    root = etree.fromstring(
        """
        <specification_set>
          <specification type='Err' ref='spec.err.Err'>
            <docstring>Error behavior</docstring>
          </specification>
          <specification type='Action' ref='spec.actions.Action'>
            <inherits>
              <ref>spec.err.Err</ref>
            </inherits>
            <docstring>Base action behavior</docstring>
          </specification>
          <specification type='MoveEntity' ref='spec.actions.MoveEntity'>
            <inherits>
              <ref>spec.actions.Action</ref>
            </inherits>
            <docstring>Move behavior</docstring>
          </specification>
        </specification_set>
        """
    )
    specs_by_ref = {spec.get("ref"): spec for spec in root.xpath("//specification")}

    docs, unresolved_refs = _inherited_context(["spec.actions.Action"], specs_by_ref)

    assert docs == [
        ("spec.actions.Action", "Base action behavior"),
        ("spec.err.Err", "Error behavior"),
    ]
    assert unresolved_refs == []


def test_inherited_context_reports_unresolved_refs():
    root = etree.fromstring(
        """
        <specification_set>
          <specification type='MoveEntity' ref='spec.actions.MoveEntity'>
            <inherits>
              <ref>spec.actions.MissingAction</ref>
            </inherits>
            <docstring>Move behavior</docstring>
          </specification>
        </specification_set>
        """
    )
    specs_by_ref = {spec.get("ref"): spec for spec in root.xpath("//specification")}

    docs, unresolved_refs = _inherited_context(
        ["spec.actions.MissingAction"],
        specs_by_ref,
    )

    assert docs == []
    assert unresolved_refs == ["spec.actions.MissingAction"]


def test_inherited_renderer_prints_specs_with_requirement_text(capsys):
    root = etree.fromstring(
        """
        <specification_set>
          <specification type='Action' ref='spec.actions.Action'>
            <docstring>Base action behavior that should not be summarized here</docstring>
          </specification>
          <specification type='MoveEntity' ref='spec.actions.MoveEntity'>
            <inherits>
              <ref>spec.actions.Action</ref>
              <ref>spec.actions.MissingAction</ref>
            </inherits>
            <docstring>Move behavior</docstring>
          </specification>
        </specification_set>
        """
    )
    specs_by_ref = {spec.get("ref"): spec for spec in root.xpath("//specification")}

    _print_inherited_specs(
        ["spec.actions.Action", "spec.actions.MissingAction"],
        specs_by_ref,
    )

    output = capsys.readouterr().out
    assert "inherited_specs:" in output
    assert "Action: spec.actions.Action" in output
    assert "requirement:" in output
    assert "Base action behavior that should not be summarized here" in output
    assert "unresolved_inherited_refs:" in output
    assert "spec.actions.MissingAction" in output


def test_generate_patch_refuses_different_libspec_major_versions(tmp_path, capsys):
    old_file = tmp_path / "old.xml"
    new_file = tmp_path / "new.xml"
    old_file.write_text(
        """
        <specification_set date-created="2026-01-01T00:00:00" libspec-version="1.9.0">
          <specification type="A"/>
        </specification_set>
        """,
        encoding="utf-8",
    )
    new_file.write_text(
        """
        <specification_set date-created="2026-01-02T00:00:00" libspec-version="2.0.0">
          <specification type="A"/>
        </specification_set>
        """,
        encoding="utf-8",
    )

    generate_patch(str(tmp_path))

    output = capsys.readouterr().out
    assert "refusing to diff specs generated by different libspec major versions" in output
    assert "old.xml: 1.9.0" in output
    assert "new.xml: 2.0.0" in output
    assert "regenerate both XML specs with the same libspec major version" in output
    assert "docs/cross-major-version-diffs.org" in output
    assert "Diffing State" not in output


def test_generate_patch_uses_one_diff_style(tmp_path, capsys):
    old_file = tmp_path / "old.xml"
    new_file = tmp_path / "new.xml"
    old_file.write_text(
        """
        <specification_set date-created="2026-01-01T00:00:00" libspec-version="2.0.0">
          <specification type="A">
            <docstring>Old text</docstring>
          </specification>
        </specification_set>
        """,
        encoding="utf-8",
    )
    new_file.write_text(
        """
        <specification_set date-created="2026-01-02T00:00:00" libspec-version="2.1.0">
          <specification type="A">
            <docstring>New text</docstring>
          </specification>
        </specification_set>
        """,
        encoding="utf-8",
    )

    generate_patch(str(tmp_path))

    output = capsys.readouterr().out
    assert "[CHANGED] A" in output
    assert "docstring:" in output
    assert "--- old/docstring" in output
    assert "+++ new/docstring" in output
    assert "-Old text" in output
    assert "+New text" in output
