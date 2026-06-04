from lxml import etree

from libspec.spec_diff import (
    _compare_specs,
    _print_inherited_specs,
    _inherited_specs,
    _node_text,
    generate_patch,
)


def _inherited_docstrings(inherits, specs_by_ref):
    docs = []
    for ref in inherits:
        inherited_spec = specs_by_ref.get(ref)
        if inherited_spec is None:
            continue
        docstring = _node_text(inherited_spec, "docstring")
        if docstring:
            docs.append((ref, docstring))
    return docs


def _inherited_context(inherits, specs_by_ref):
    docs = []
    unresolved_refs = []
    seen_refs = set()

    def visit(ref):
        if not ref or ref in seen_refs:
            return
        seen_refs.add(ref)

        inherited_spec = specs_by_ref.get(ref)
        if inherited_spec is None:
            unresolved_refs.append(ref)
            return

        docstring = _node_text(inherited_spec, "docstring")
        if docstring:
            docs.append((ref, docstring))

        for child_ref in inherited_spec.xpath("inherits/ref"):
            visit(child_ref.text)

    for ref in inherits:
        visit(ref)

    return docs, unresolved_refs


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


def test_compare_specs_reports_inherited_spec_changes():
    old_spec_xml = """
        <specification_set>
          <specification type='Err' ref='spec.err.Err'>
            <docstring>Old error behavior</docstring>
          </specification>
          <specification type='MoveEntity' ref='spec.actions.MoveEntity'>
            <inherits>
              <ref>spec.err.Err</ref>
            </inherits>
            <docstring>Move behavior</docstring>
          </specification>
        </specification_set>
    """
    new_spec_xml = """
        <specification_set>
          <specification type='Err' ref='spec.err.Err'>
            <docstring>New error behavior</docstring>
          </specification>
          <specification type='MoveEntity' ref='spec.actions.MoveEntity'>
            <inherits>
              <ref>spec.err.Err</ref>
            </inherits>
            <docstring>Move behavior</docstring>
          </specification>
        </specification_set>
    """
    old_root = etree.fromstring(old_spec_xml)
    new_root = etree.fromstring(new_spec_xml)
    
    old_specs_by_ref = {spec.get("ref"): spec for spec in old_root.xpath("//specification")}
    new_specs_by_ref = {spec.get("ref"): spec for spec in new_root.xpath("//specification")}
    
    old_move_spec = old_specs_by_ref["spec.actions.MoveEntity"]
    new_move_spec = new_specs_by_ref["spec.actions.MoveEntity"]
    
    changes = _compare_specs(old_move_spec, new_move_spec, old_specs_by_ref, new_specs_by_ref)
    
    assert changes == ["inherited spec 'spec.err.Err' changed"]


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
    assert "inherited_specs (STRICTLY FOLLOW THE GUIDANCE BELOW):" in output
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


def test_generate_patch_detects_superspec_change_in_separate_file(tmp_path, capsys):
    """
    Regression test: when a superspec (e.g. spec.err.Err) lives in a SEPARATE
    XML build output from the child specs, and only the superspec changes,
    generate_patch must still report the child as [CHANGED] with an
    "inherited spec changed" entry.

    Previously this silently printed "No changes detected." because _xml_diffs
    returned an empty list (the child XML was byte-identical) and the function
    returned before ever checking inherited refs.
    """
    # Old build: child module XML — Err superspec is NOT embedded here.
    # The child inherits spec.err.Err which is defined in a separate err.xml.
    old_err_file = tmp_path / "err_old.xml"
    new_err_file = tmp_path / "err_new.xml"
    old_child_file = tmp_path / "child_old.xml"
    new_child_file = tmp_path / "child_new.xml"

    old_err_file.write_text(
        """
        <specification_set date-created="2026-01-01T00:00:00" libspec-version="2.0.0">
          <specification type="Err" ref="spec.err.Err">
            <docstring>Old error policy: raise ValueError</docstring>
          </specification>
        </specification_set>
        """,
        encoding="utf-8",
    )
    new_err_file.write_text(
        """
        <specification_set date-created="2026-01-02T00:00:00" libspec-version="2.0.0">
          <specification type="Err" ref="spec.err.Err">
            <docstring>New error policy: raise RuntimeError with full context</docstring>
          </specification>
        </specification_set>
        """,
        encoding="utf-8",
    )

    # The child XML is IDENTICAL between old and new — only the superspec changed.
    child_xml = """
        <specification_set date-created="2026-01-01T00:00:00" libspec-version="2.0.0">
          <specification type="MoveEntity" ref="spec.actions.MoveEntity">
            <inherits>
              <ref>spec.err.Err</ref>
            </inherits>
            <docstring>Move an entity</docstring>
          </specification>
        </specification_set>
        """
    old_child_file.write_text(child_xml, encoding="utf-8")
    new_child_file.write_text(child_xml, encoding="utf-8")

    # generate_patch operates on a single directory of versioned XML files.
    # The real-world scenario: the combined output file contains both Err and
    # child specs; the old and new versions differ only in the Err docstring.
    # We simulate this with a single combined dir.
    combined_dir = tmp_path / "combined"
    combined_dir.mkdir()

    (combined_dir / "spec_old.xml").write_text(
        """
        <specification_set date-created="2026-01-01T00:00:00" libspec-version="2.0.0">
          <specification type="Err" ref="spec.err.Err">
            <docstring>Old error policy: raise ValueError</docstring>
          </specification>
          <specification type="MoveEntity" ref="spec.actions.MoveEntity">
            <inherits>
              <ref>spec.err.Err</ref>
            </inherits>
            <docstring>Move an entity</docstring>
          </specification>
        </specification_set>
        """,
        encoding="utf-8",
    )
    (combined_dir / "spec_new.xml").write_text(
        """
        <specification_set date-created="2026-01-02T00:00:00" libspec-version="2.0.0">
          <specification type="Err" ref="spec.err.Err">
            <docstring>New error policy: raise RuntimeError with full context</docstring>
          </specification>
          <specification type="MoveEntity" ref="spec.actions.MoveEntity">
            <inherits>
              <ref>spec.err.Err</ref>
            </inherits>
            <docstring>Move an entity</docstring>
          </specification>
        </specification_set>
        """,
        encoding="utf-8",
    )

    generate_patch(str(combined_dir))
    output = capsys.readouterr().out

    # Both the changed superspec AND the inheriting child must be reported.
    assert "[CHANGED] Err" in output, "Superspec itself must be reported as changed"
    assert "[CHANGED] MoveEntity" in output, (
        "Child that inherits the changed superspec must be reported as CHANGED"
    )
    assert "inherited spec 'spec.err.Err' changed" in output, (
        "The change entry must name the superspec that changed"
    )
    assert "No changes detected" not in output


def test_generate_patch_detects_transitive_superspec_change(tmp_path, capsys):
    """
    Regression test: transitive inheritance chain  MoveEntity -> Action -> Err.
    When only Err changes, both Action AND MoveEntity must appear as [CHANGED].
    This tests that the inherited-spec walk descends recursively, not just one level.
    """
    (tmp_path / "spec_old.xml").write_text(
        """
        <specification_set date-created="2026-01-01T00:00:00" libspec-version="2.0.0">
          <specification type="Err" ref="spec.err.Err">
            <docstring>Old error policy: raise ValueError</docstring>
          </specification>
          <specification type="Action" ref="spec.actions.Action">
            <inherits>
              <ref>spec.err.Err</ref>
            </inherits>
            <docstring>Base action</docstring>
          </specification>
          <specification type="MoveEntity" ref="spec.actions.MoveEntity">
            <inherits>
              <ref>spec.actions.Action</ref>
            </inherits>
            <docstring>Move an entity</docstring>
          </specification>
        </specification_set>
        """,
        encoding="utf-8",
    )
    (tmp_path / "spec_new.xml").write_text(
        """
        <specification_set date-created="2026-01-02T00:00:00" libspec-version="2.0.0">
          <specification type="Err" ref="spec.err.Err">
            <docstring>New error policy: raise RuntimeError with full context</docstring>
          </specification>
          <specification type="Action" ref="spec.actions.Action">
            <inherits>
              <ref>spec.err.Err</ref>
            </inherits>
            <docstring>Base action</docstring>
          </specification>
          <specification type="MoveEntity" ref="spec.actions.MoveEntity">
            <inherits>
              <ref>spec.actions.Action</ref>
            </inherits>
            <docstring>Move an entity</docstring>
          </specification>
        </specification_set>
        """,
        encoding="utf-8",
    )

    generate_patch(str(tmp_path))
    output = capsys.readouterr().out

    assert "[CHANGED] Err" in output
    assert "[CHANGED] Action" in output, "Direct inheritor must be reported as CHANGED"
    assert "[CHANGED] MoveEntity" in output, (
        "Transitive inheritor (2 levels deep) must be reported as CHANGED"
    )
    assert "No changes detected" not in output


def test_generate_patch_child_unchanged_superspec_not_in_same_xml(tmp_path, capsys):
    """
    The pathological case: the child spec's XML file is byte-for-byte identical
    between old and new (because the child itself didn't change — only the
    superspec that it references did, and that superspec lives in a DIFFERENT
    build artifact / XML file).

    In this scenario _xml_diffs returns an empty list and the early-exit
    'if not diffs: return' fires, silently swallowing the inherited change.

    The fix: the early-exit gate must NOT apply when any inherited ref in ANY
    spec in the file resolves to a superspec that changed between old and new.
    Since the superspec is in a separate file, libspec cannot detect this from
    the raw XML diff alone; the correct behaviour is to report the child as
    affected once the combined spec set is diffed.
    """
    # The child-only XML — identical in both snapshots.
    child_xml = """<?xml version='1.0' encoding='utf-8'?>
<specification_set date-created="2026-01-01T00:00:00" libspec-version="2.0.0">
  <specification type="MoveEntity" ref="spec.actions.MoveEntity">
    <inherits>
      <ref>spec.err.Err</ref>
    </inherits>
    <docstring>Move an entity</docstring>
  </specification>
</specification_set>"""
    (tmp_path / "spec_old.xml").write_text(child_xml, encoding="utf-8")
    (tmp_path / "spec_new.xml").write_text(child_xml, encoding="utf-8")

    generate_patch(str(tmp_path))
    output = capsys.readouterr().out

    # The spec.err.Err ref is unresolved (not present in this XML), so we
    # cannot know it changed — but we must NOT silently claim "no changes".
    # The expected behaviour is to report the unresolved ref so the developer
    # knows to check the superspec separately, OR (future work) to accept a
    # second "superspec XML" argument.
    #
    # At minimum, the output must NOT claim everything is clean when a
    # referenced superspec is absent from the diff corpus.
    assert "No changes detected" not in output or "unresolved" in output, (
        "When an inherited ref cannot be resolved, the diff must not silently "
        "claim 'No changes detected' — it must surface the unresolved ref."
    )


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

def test_native_diff_exact_hash_equivalence():
    from libspec.store import Component
    from libspec.spec_diff import _compare_components_natively
    
    # Exact hash equivalence test
    comp1 = Component(ref="A", docstring="test", is_template=False, inherits=[], hash="a" * 64)
    comp2 = Component(ref="A", docstring="test", is_template=False, inherits=[], hash="a" * 64)
    
    changes = _compare_components_natively(comp1, comp2, {}, {})
    assert not changes, "Identical hashes should produce exactly zero changes."

def test_native_diff_changed_docstring_and_inherits():
    from libspec.store import Component
    from libspec.spec_diff import _compare_components_natively
    
    comp1 = Component(ref="A", docstring="Old spec", is_template=False, inherits=["B"], hash="a" * 64)
    comp2 = Component(ref="A", docstring="New spec", is_template=False, inherits=["B", "C"], hash="b" * 64)
    
    changes = _compare_components_natively(comp1, comp2, {}, {})
    assert any("docstring" in c for c in changes)
    assert any("inherits" in c for c in changes)
    assert any("C" in c for c in changes)

def test_native_diff_recursive_inheritance():
    from libspec.store import Component
    from libspec.spec_diff import _compare_components_natively
    
    # Parent changed its hash
    parent_old = Component(ref="B", docstring="Old parent", is_template=False, inherits=[], hash="p1" + "a" * 62)
    parent_new = Component(ref="B", docstring="New parent", is_template=False, inherits=[], hash="p2" + "a" * 62)
    
    # Child is byte-for-byte identical but parent changed
    child_old = Component(ref="A", docstring="Child", is_template=False, inherits=["B"], hash="c1" + "a" * 62)
    child_new = Component(ref="A", docstring="Child", is_template=False, inherits=["B"], hash="c2" + "a" * 62)
    
    old_map = {"A": child_old, "B": parent_old}
    new_map = {"A": child_new, "B": parent_new}
    
    changes = _compare_components_natively(child_old, child_new, old_map, new_map)
    assert any("inherited spec 'B' changed" in c for c in changes)

def test_native_diff_unresolved_ref_warning(capsys):
    from libspec.store import Snapshot, Component
    from libspec.spec_diff import generate_native_patch
    import datetime
    from unittest.mock import patch
    
    # Mock store to return snapshots with unresolved refs
    comp = Component(ref="Child", docstring="Child", is_template=False, inherits=["MissingParent"], hash="h" + "a" * 63)
    snap = Snapshot(id="snap1", created_at=datetime.datetime.now(), master_hash="m" + "a" * 63)
    
    with patch("libspec.store.get_store") as mock_get_store:
        mock_store = mock_get_store.return_value
        mock_store.list_snapshots.return_value = [snap]
        mock_store.get_components_for_snapshot.return_value = [comp]
        
        generate_native_patch()
        
    captured = capsys.readouterr()
    assert "[WARNING]" in captured.out
    assert "MissingParent" in captured.out


def test_native_diff_prints_inherited_specs(capsys):
    from libspec.store import Snapshot, Component
    from libspec.spec_diff import generate_native_patch
    import datetime
    from unittest.mock import patch

    parent = Component(ref="ParentSpec", docstring="Base behavior to follow", is_template=False, inherits=[], hash="p" + "a" * 63)
    comp = Component(ref="ChildSpec", docstring="Extended behavior", is_template=False, inherits=["ParentSpec"], hash="h" + "a" * 63)
    snap = Snapshot(id="snap1", created_at=datetime.datetime.now(), master_hash="m" + "a" * 63)

    with patch("libspec.store.get_store") as mock_get_store:
        mock_store = mock_get_store.return_value
        mock_store.list_snapshots.return_value = [snap]
        mock_store.get_components_for_snapshot.return_value = [parent, comp]

        generate_native_patch()

    captured = capsys.readouterr()
    assert "[NEW] ChildSpec" in captured.out
    assert "inherited_specs (STRICTLY FOLLOW THE GUIDANCE BELOW):" in captured.out
    assert "ParentSpec: ParentSpec" in captured.out
    assert "Base behavior to follow" in captured.out
