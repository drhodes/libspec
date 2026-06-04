# Native specification diffing tests
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
