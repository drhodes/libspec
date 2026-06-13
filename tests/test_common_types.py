import datetime


def test_imports_from_common():
    """Verify that core types can be imported from libspec.common."""
    from libspec.common import Component, Implemented, Snapshot

    # Check that they are classes/dataclasses
    assert isinstance(Component, type)
    assert isinstance(Snapshot, type)
    assert isinstance(Implemented, type)


def test_backward_compatible_store_imports():
    """Verify that core types are still exposed/re-exported via libspec.store."""
    from libspec.common import (
        Component as CommonComponent,
    )
    from libspec.common import (
        Implemented as CommonImplemented,
    )
    from libspec.common import (
        Snapshot as CommonSnapshot,
    )
    from libspec.store import Component, Implemented, Snapshot

    assert Component is CommonComponent
    assert Snapshot is CommonSnapshot
    assert Implemented is CommonImplemented


def test_component_structure():
    """Verify Component field attributes."""
    from libspec.common import Component

    valid_hash = "a" * 64
    c = Component(
        ref="spec.app.App",
        docstring="desc",
        is_template=False,
        inherits=[],
        hash=valid_hash,
        is_dependency=False,
    )
    assert c.ref == "spec.app.App"
    assert c.docstring == "desc"
    assert c.is_template is False
    assert c.inherits == []
    assert c.hash == valid_hash
    assert c.is_dependency is False


def test_snapshot_structure():
    """Verify Snapshot field attributes."""
    from libspec.common import Snapshot

    now = datetime.datetime.now(datetime.UTC)
    valid_hash = "b" * 64
    s = Snapshot(
        id="snap123",
        created_at=now,
        master_hash=valid_hash,
        git_commit="commit123",
    )
    assert s.id == "snap123"
    assert s.created_at == now
    assert s.master_hash == valid_hash
    assert s.git_commit == "commit123"


def test_implemented_structure():
    """Verify Implemented field attributes."""
    from libspec.common import Implemented

    valid_hash = "c" * 64
    i = Implemented(
        ref="spec.app.App",
        spec_hash=valid_hash,
        file="app.py",
        line=10,
        session_id="session123",
    )
    assert i.ref == "spec.app.App"
    assert i.spec_hash == valid_hash
    assert i.file == "app.py"
    assert i.line == 10
    assert i.session_id == "session123"
