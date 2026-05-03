from lxml import etree

from libspec.spec_diff import _compare_specs


def test_compare_specs_handles_missing_description_and_notes():
    old_spec = etree.fromstring("<specification type='A'><context/></specification>")
    new_spec = etree.fromstring("<specification type='A'><context/></specification>")

    changes = _compare_specs(old_spec, new_spec)

    assert changes == []
