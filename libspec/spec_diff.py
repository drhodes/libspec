import sys
import os
from pathlib import Path
from lxml import etree
from xmldiff import main

def get_latest_xml_files(directory):
    path = Path(directory)
    files = sorted(path.glob('*.xml'), key=os.path.getmtime)
    if len(files) < 2:
        return None
    return files[-2], files[-1]

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

def generate_patch(dir_arg):
    files = get_latest_xml_files(dir_arg)
    if not files:
        print("Error: Need at least two XML files in the directory.")
        return

    old_file, new_file = files
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
    if len(sys.argv) != 2:
        print("Usage: python -m spec_diff.py <directory>")
    else:
        generate_patch(sys.argv[1])
