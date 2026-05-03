import sys
import os
from pathlib import Path
from lxml import etree
from xmldiff import main

def get_latest_xml_files(directory):
    path = Path(directory)
    xml_files = list(path.glob('*.xml'))
    if len(xml_files) == 0:
        return None
    
    file_info = []
    import datetime
    for f in xml_files:
        try:
            tree = etree.parse(str(f))
            root = tree.getroot()
            date_str = root.get('date-created')
            if date_str:
                file_info.append((date_str, f))
            else:
                # Fallback to file mtime formatted as ISO string
                mtime = os.path.getmtime(str(f))
                dt = datetime.datetime.fromtimestamp(mtime).astimezone()
                file_info.append((dt.isoformat(), f))
        except Exception:
            mtime = os.path.getmtime(str(f))
            dt = datetime.datetime.fromtimestamp(mtime).astimezone()
            file_info.append((dt.isoformat(), f))
    
    # Sort by the timestamp (date-created string or mtime)
    file_info.sort(key=lambda x: x[0])
    
    if len(file_info) == 1:
        # Only one spec exists — bootstrap case; diff against a null spec
        return None, file_info[-1][1]
    
    return file_info[-2][1], file_info[-1][1]

def resolve_component(root, xpath):
    """
    Find the closest parent <specification> and return its type or name.
    """
    try:
        nodes = root.xpath(xpath)
        if not nodes:
            return "General System"
        
        node = nodes[0]
        # Traverse up to find 'specification'
        curr = node
        while curr is not None:
            if curr.tag == 'specification':
                spec_type = curr.get('type')
                if spec_type:
                    return f"[{spec_type}]"
                # Fallback to title in context
                titles = curr.xpath('.//title/text()')
                if titles:
                    return f"[{titles[0]}]"
                return "[Specification]"
            curr = curr.getparent()
    except Exception:
        pass
    return "Core System"

def to_human_readable(action, root):
    """
    Translates a raw xmldiff Action into a human-readable string.
    Returns None if the action is purely structural 'noise'.
    """
    action_type = type(action).__name__
    
    # Target node resolution
    target_path = getattr(action, 'node', getattr(action, 'target', '/'))
    try:
        nodes = root.xpath(target_path)
        tag = nodes[0].tag if nodes else "unknown"
    except Exception:
        tag = "unknown"

    # Filter out structural boilerplate
    if action_type == 'InsertNode' and tag in ['specification_set', 'specification', 'source', 'context', 'notes', 'description', 'req_id', 'title']:
        return None

    if action_type == 'UpdateTextIn':
        text = (action.text or "").strip().replace('\n', ' ')
            
        if tag == 'description':
            return f"Updated description: \"{text}\""
        if tag == 'notes':
            return f"Updated requirements: \"{text}\""
        if tag == 'req_id':
            return f"Updated cross-reference ID: {text}"
        if tag == 'title':
            return f"Updated title: {text}"
        return f"Updated {tag} text to \"{text}\""

    if action_type == 'InsertAttrib':
        name = action.name
        value = action.value
        if name == 'type':
            return f"Defined component type as '{value}'"
        if name == 'file':
            return f"Set source file to '{value}'"
        if name == 'lines':
            return f"Set source lines to {value}"
        if name == 'target':
            return f"Set tracking target to '{value}'"
        return f"Added attribute {name}='{value}'"

    if action_type == 'InsertNode':
        return f"Added new {tag} element"

    if action_type == 'DeleteNode':
        return ""

    if action_type == 'MoveNode':
        return ""

    if action_type == 'UpdateAttrib':
        return ""

    if action_type == 'RenameNode':
        return ""


    
    # Fallback for other actions
    return str(action).replace('\n', '\\n')

NULL_SPEC_XML = """<?xml version='1.0' encoding='utf-8'?>
<specification_set date-created="" />"""

def get_specs_for_compact_diff(dir_arg):
    """Return (old_file, new_file, old_tree, new_root) for diffing."""
    files = get_latest_xml_files(dir_arg)
    if not files:
        return None, None, None, None

    old_file, new_file = files

    if old_file is None:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.xml', mode='w', delete=False) as tmp:
            tmp.write(NULL_SPEC_XML)
            tmp_path = tmp.name
        try:
            new_tree = etree.parse(str(new_file))
            new_root = new_tree.getroot()
            return None, new_file, None, new_root
        finally:
            os.unlink(tmp_path)
    else:
        try:
            new_tree = etree.parse(str(new_file))
            new_root = new_tree.getroot()
            return old_file, new_file, None, new_root
        except Exception as e:
            print(f"Error parsing XML: {e}")
            return None, None, None, None


def generate_compact_diff(dir_arg):
    """Generate compact diff using structured fields."""
    old_file, new_file, _, new_root = get_specs_for_compact_diff(dir_arg)
    if new_file is None:
        print("Error: No XML spec files found in the directory.")
        return

    if old_file is None:
        print(f"Diffing State: <null spec> -> {new_file.name}")
    else:
        print(f"Diffing State: {old_file.name} -> {new_file.name}")
    print("=" * 60)

    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.xml', mode='w', delete=False) as tmp:
        tmp.write(NULL_SPEC_XML)
        tmp_path = tmp.name

    try:
        if old_file is None:
            old_tree = etree.parse(tmp_path)
        else:
            old_tree = etree.parse(str(old_file))
        old_root = old_tree.getroot()
    except Exception:
        old_root = etree.fromstring(NULL_SPEC_XML)
    finally:
        os.unlink(tmp_path)

    old_specs = {s.get('type'): s for s in old_root.xpath('//specification')}
    new_specs = {s.get('type'): s for s in new_root.xpath('//specification')}

    all_components = sorted(set(old_specs.keys()) | set(new_specs.keys()))

    for comp_type in all_components:
        old_spec = old_specs.get(comp_type)
        new_spec = new_specs.get(comp_type)

        if old_spec is None:
            print(f"\n[NEW] {comp_type}")
            if new_spec is not None:
                _print_compact_spec(new_spec)
        elif new_spec is None:
            print(f"\n[REMOVED] {comp_type}")
        else:
            changes = _compare_specs(old_spec, new_spec)
            if changes:
                print(f"\n[CHANGED] {comp_type}")
                for change in changes:
                    print(f"  - {change}")


def _print_compact_spec(spec):
    """Print compact representation of a spec."""
    inherits = [e.text for e in spec.xpath('inherits/spec')]
    if inherits:
        print(f"  inherits: {', '.join(inherits)}")

    eff_ids = [e.text for e in spec.xpath('effective_req_ids/id')]
    if eff_ids:
        print(f"  effective_req_ids: {', '.join(eff_ids)}")

    overrides = [e.text for e in spec.xpath('overrides/field')]
    if overrides:
        print(f"  overrides: {', '.join(overrides)}")

    deltas = spec.xpath('delta_requirements/*')
    if deltas:
        print("  delta_requirements:")
        for d in deltas:
            print(f"    {d.tag}: {d.text or ''}".strip())


def _compare_specs(old_spec, new_spec):
    """Compare two specs and return list of changes."""
    changes = []

    def _node_text(spec, tag):
        node = spec.find(tag)
        if node is None or node.text is None:
            return ""
        return node.text.strip()

    old_inherits = set(e.text for e in old_spec.xpath('inherits/spec'))
    new_inherits = set(e.text for e in new_spec.xpath('inherits/spec'))
    if old_inherits != new_inherits:
        changes.append(f"inherits: {old_inherits} -> {new_inherits}")

    old_eff = set(e.text for e in old_spec.xpath('effective_req_ids/id'))
    new_eff = set(e.text for e in new_spec.xpath('effective_req_ids/id'))
    if old_eff != new_eff:
        changes.append(f"effective_req_ids: {old_eff} -> {new_eff}")

    old_overrides = set(e.text for e in old_spec.xpath('overrides/field'))
    new_overrides = set(e.text for e in new_spec.xpath('overrides/field'))
    if old_overrides != new_overrides:
        changes.append(f"overrides: {old_overrides} -> {new_overrides}")

    old_deltas = {d.tag: d.text for d in old_spec.xpath('delta_requirements/*')}
    new_deltas = {d.tag: d.text for d in new_spec.xpath('delta_requirements/*')}
    if old_deltas != new_deltas:
        for tag in sorted(set(old_deltas.keys()) | set(new_deltas.keys())):
            old_val = old_deltas.get(tag, '<missing>')
            new_val = new_deltas.get(tag, '<missing>')
            if old_val != new_val:
                changes.append(f"delta.{tag}: {old_val} -> {new_val}")

    old_desc = _node_text(old_spec, 'description')
    new_desc = _node_text(new_spec, 'description')
    if old_desc != new_desc:
        changes.append(f"description: (changed)")

    old_notes = _node_text(old_spec, 'notes')
    new_notes = _node_text(new_spec, 'notes')
    if old_notes != new_notes:
        changes.append(f"notes: (changed)")

    return changes


def generate_patch(dir_arg, compact=False):
    if compact:
        generate_compact_diff(dir_arg)
        return

    files = get_latest_xml_files(dir_arg)
    if not files:
        print("Error: No XML spec files found in the directory.")
        return

    old_file, new_file = files

    if old_file is None:
        # Bootstrap case: first spec ever — diff against an empty null spec
        print(f"Diffing State: <null spec> -> {new_file.name}")
        print("=" * 60)
        import tempfile, io
        with tempfile.NamedTemporaryFile(suffix='.xml', mode='w', delete=False) as tmp:
            tmp.write(NULL_SPEC_XML)
            tmp_path = tmp.name
        try:
            new_tree = etree.parse(str(new_file))
            new_root = new_tree.getroot()
            diffs = main.diff_files(tmp_path, str(new_file))
        finally:
            os.unlink(tmp_path)
    else:
        print(f"Diffing State: {old_file.name} -> {new_file.name}")
        print("=" * 60)
        try:
            new_tree = etree.parse(str(new_file))
            new_root = new_tree.getroot()
        except Exception as e:
            print(f"Error parsing XML: {e}")
            return
        diffs = main.diff_files(str(old_file), str(new_file))
    if not diffs:
        print("No changes detected.")
        return

    groups = {}
    for op in diffs:
        target_path = getattr(op, 'node', getattr(op, 'target', '/'))
        component = resolve_component(new_root, target_path)

        readable = to_human_readable(op, new_root)
        if readable:
            if component not in groups:
                groups[component] = []
            groups[component].append(readable)

    for component, descriptions in groups.items():
        print(f"\nCOMPONENT: {component}")
        for desc in descriptions:
            print(f"  - {desc}")

if __name__ == "__main__":
    # Delegate to the unified CLI: `libspec diff <dir>`
    import sys as _sys
    from libspec.cli import main as _cli_main
    _sys.argv.insert(1, 'diff')
    _cli_main()
