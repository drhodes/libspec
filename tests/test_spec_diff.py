from lxml import etree

from libspec.spec_diff import _compare_specs


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
