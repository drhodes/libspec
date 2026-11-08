"""Inheritance changes must reach `libspec diff` through real compilation.

These go through Spec.get_components(), so the hashes are the real ones.
"""

import types
from unittest.mock import patch

from libspec import Ctx, Requirement, Spec
from libspec.spec_diff import _compare_components_natively, generate_native_patch


def compile_classes(*classes):
    module = types.ModuleType("fixture_specs")
    for cls in classes:
        cls.__module__ = module.__name__
        setattr(module, cls.__name__, cls)

    class FixtureSpec(Spec):
        def modules(self):
            return [module]

    return {c.ref: c for c in FixtureSpec().get_components()}


def get_snapshot_id(*classes):
    module = types.ModuleType("fixture_specs")
    for cls in classes:
        cls.__module__ = module.__name__
        setattr(module, cls.__name__, cls)

    class FixtureSpec(Spec):
        def modules(self):
            return [module]

    spec = FixtureSpec()
    components = spec.get_components()
    import hashlib

    sorted_components = sorted(components, key=lambda c: c.ref)
    hasher = hashlib.sha256()
    for comp in sorted_components:
        hasher.update(comp.ref.encode("utf-8"))
        hasher.update(comp.hash.encode("utf-8"))
    return hasher.hexdigest()[:16]


def changes_for(ref, old, new):
    return _compare_components_natively(old[ref], new[ref], old, new)


def make_ctx(name, doc, *bases):
    return type(name, bases or (Ctx,), {"__doc__": doc})


def make_req(name, doc, *bases):
    return type(name, (*bases, Requirement), {"__doc__": doc})


REQ = "fixture_specs.R"


def test_identical_specs_report_nothing():
    old = compile_classes(make_ctx("G", "guide"), make_req("R", "req"))
    new = compile_classes(make_ctx("G", "guide"), make_req("R", "req"))
    assert changes_for(REQ, old, new) == []


def test_gaining_a_ctx_base_is_a_change():
    g1, g2 = make_ctx("G", "guide"), make_ctx("G", "guide")
    old = compile_classes(g1, make_req("R", "req"))
    new = compile_classes(g2, make_req("R", "req", g2))
    assert any("inherits" in c for c in changes_for(REQ, old, new))


def test_losing_a_ctx_base_is_a_change():
    g1, g2 = make_ctx("G", "guide"), make_ctx("G", "guide")
    old = compile_classes(g1, make_req("R", "req", g1))
    new = compile_classes(g2, make_req("R", "req"))
    assert any("inherits" in c for c in changes_for(REQ, old, new))


def test_reordering_ctx_bases_is_a_change():
    a1, b1 = make_ctx("A", "a"), make_ctx("B", "b")
    a2, b2 = make_ctx("A", "a"), make_ctx("B", "b")
    old = compile_classes(a1, b1, make_req("R", "req", a1, b1))
    new = compile_classes(a2, b2, make_req("R", "req", b2, a2))
    assert any("inherits" in c for c in changes_for(REQ, old, new))


def test_rewriting_an_inherited_ctx_flags_the_inheritor():
    g1, g2 = make_ctx("G", "guide"), make_ctx("G", "rewritten guide")
    old = compile_classes(g1, make_req("R", "req", g1))
    new = compile_classes(g2, make_req("R", "req", g2))
    assert any("inherited spec" in c and "G" in c for c in changes_for(REQ, old, new))


def test_rewriting_a_grandparent_ctx_flags_the_inheritor():
    b1 = make_ctx("Base", "base")
    b2 = make_ctx("Base", "rewritten base")
    g1, g2 = make_ctx("G", "guide", b1), make_ctx("G", "guide", b2)
    old = compile_classes(b1, g1, make_req("R", "req", g1))
    new = compile_classes(b2, g2, make_req("R", "req", g2))
    assert any("inherited spec" in c for c in changes_for(REQ, old, new))


def test_snapshot_id_sensitive_to_inheritance():
    # Adding a Ctx base must produce a different snapshot ID
    g = make_ctx("G", "guide")
    snap_before = get_snapshot_id(g, make_req("R", "req"))
    snap_after = get_snapshot_id(g, make_req("R", "req", g))
    assert snap_before != snap_after


def test_changed_guidance_display(capsys):
    g1, g2 = (
        make_ctx("G", "Follow this special rule"),
        make_ctx("G", "Follow this special rule"),
    )
    old_comps = list(compile_classes(g1, make_req("R", "req")).values())
    new_comps = list(compile_classes(g2, make_req("R", "req", g2)).values())

    with patch(
        "libspec.spec_diff._resolve_diff_targets",
        return_value=(
            old_comps,
            new_comps,
            {c.ref: c for c in new_comps},
            "old",
            "new",
            "RESOLVED",
        ),
    ):
        generate_native_patch(old_commit="old", new_commit="new")

    captured = capsys.readouterr().out
    assert "[CHANGED] R" in captured
    assert "inherited_specs (STRICTLY FOLLOW THE GUIDANCE BELOW):" in captured
    assert "Follow this special rule" in captured


def test_cache_version_invalidation():
    import os

    from libspec.util import _get_live_fingerprint

    spec_file = os.path.abspath("spec/main_spec.py")
    with patch("libspec.util.get_libspec_version", return_value="1.0.0"):
        fp1 = _get_live_fingerprint(spec_file)
    with patch("libspec.util.get_libspec_version", return_value="1.0.1"):
        fp2 = _get_live_fingerprint(spec_file)
    assert fp1 != fp2


def test_git_cache_key_incorporates_version():
    from unittest.mock import MagicMock

    from libspec.util import compile_git_spec

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="fake_sha\n")
        with patch("libspec.util.is_libspec_project", return_value=True):
            with patch("os.path.exists", return_value=True):
                with patch("marshal.load", return_value=[]):
                    with patch(
                        "libspec.util.get_libspec_version", return_value="99.9.9"
                    ):
                        with patch("builtins.open", MagicMock()) as mock_open:
                            compile_git_spec("HEAD")
                            call_path = mock_open.call_args[0][0]
                            assert "fake_sha_99.9.9.bin" in call_path
