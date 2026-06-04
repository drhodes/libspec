import difflib

def _patch_block(label, old_text, new_text):
    old_lines = (old_text or "").splitlines()
    new_lines = (new_text or "").splitlines()
    diff_lines = list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"old/{label}",
            tofile=f"new/{label}",
            lineterm="",
        )
    )
    if not diff_lines:
        return f"{label}: <no textual changes>"
    return f"{label}:\n" + "\n".join(diff_lines)


def generate_native_patch(old_snap=None, new_snap=None):
    """Generate a structured diff between two snapshots using the native Component model."""
    from libspec.store import get_store
    store = get_store()

    if old_snap is None and new_snap is None:
        try:
            snapshots = store.list_snapshots()
        except Exception as e:
            print(f"Error querying snapshots: {e}")
            return
            
        if not snapshots:
            print("Error: No snapshot builds found in the active SpecStore. Compile a specification first.")
            return
            
        if len(snapshots) == 1:
            old_snap = None
            new_snap = snapshots[0]
        else:
            old_snap = snapshots[-2]
            new_snap = snapshots[-1]

    old_commit = f" (Git: {old_snap.git_commit[:7]})" if old_snap and old_snap.git_commit else ""
    new_commit = f" (Git: {new_snap.git_commit[:7]})" if new_snap and new_snap.git_commit else ""

    if old_snap is None:
        print(f"Diffing State: <null spec> -> Build {new_snap.id}{new_commit}")
        old_components = []
    else:
        print(f"Diffing State: Build {old_snap.id}{old_commit} -> Build {new_snap.id}{new_commit}")
        try:
            old_components = store.get_components_for_snapshot(old_snap)
        except Exception as e:
            print(f"Error loading components for snapshot {old_snap.id}: {e}")
            return

    try:
        new_components = store.get_components_for_snapshot(new_snap)
    except Exception as e:
        print(f"Error loading components for snapshot {new_snap.id}: {e}")
        return
        
    print("=" * 60)

    old_map = {c.ref: c for c in old_components}
    new_map = {c.ref: c for c in new_components}

    all_refs = sorted(set(old_map.keys()) | set(new_map.keys()))

    diff_entries = []
    for ref in all_refs:
        old_comp = old_map.get(ref)
        new_comp = new_map.get(ref)
        comp_type = ref.split('.')[-1]

        if old_comp is None:
            diff_entries.append(('NEW', comp_type, ref, new_comp, []))
        elif new_comp is None:
            diff_entries.append(('REMOVED', comp_type, ref, old_comp, []))
        else:
            changes = _compare_components_natively(old_comp, new_comp, old_map, new_map)
            if changes:
                diff_entries.append(('CHANGED', comp_type, ref, new_comp, changes))

    # Warning for unresolved refs
    unresolved_by_comp = {}
    for ref, comp in new_map.items():
        unresolved = [r for r in comp.inherits if r not in new_map]
        if unresolved:
            unresolved_by_comp[ref.split('.')[-1]] = unresolved

    if not diff_entries and not unresolved_by_comp:
        print("No changes detected.")
        return

    for action, comp_type, ref, comp, changes in diff_entries:
        if action == 'NEW':
            # Skip components with empty docstrings/inherits for NEW output consistency
            if comp.docstring.strip() or comp.inherits:
                print(f"\n[NEW] {comp_type}")
                if comp.docstring.strip():
                    lines = comp.docstring.strip().splitlines()
                    print(f"  docstring: {lines[0]}")
                    for line in lines[1:]:
                        print(f"    {line}")
                if comp.inherits:
                    _print_inherited_specs_natively(comp.inherits, new_map)
        elif action == 'REMOVED':
            print(f"\n[REMOVED] {comp_type}")
        elif action == 'CHANGED':
            print(f"\n[CHANGED] {comp_type}")
            for change in changes:
                print(f"  - {change}")

    if unresolved_by_comp:
        print("\n[WARNING] The following specs inherit refs that are not present")
        print("  in this snapshot. Changes to those superspecs cannot be detected here.")
        for comp_type in sorted(unresolved_by_comp):
            for ref in unresolved_by_comp[comp_type]:
                print(f"  {comp_type} -> unresolved inherited ref: {ref}")


def _compare_components_natively(old_comp, new_comp, old_map, new_map, visited=None):
    """Compare two components natively using their hash and fields."""
    if old_comp.hash == new_comp.hash:
        return []

    if visited is None:
        visited = set()
    visited.add(new_comp.ref)

    changes = []
    
    # 1. Docstring Diff
    if old_comp.docstring != new_comp.docstring:
        changes.append(_patch_block("docstring", old_comp.docstring, new_comp.docstring))

    # 2. Inherits list diff
    if old_comp.inherits != new_comp.inherits:
        changes.append(f"inherits: {old_comp.inherits} -> {new_comp.inherits}")

    # 3. Recursive inheritance diff
    common_refs = set(old_comp.inherits) & set(new_comp.inherits)
    for ref in sorted(common_refs):
        if ref in visited:
            continue
        old_parent = old_map.get(ref)
        new_parent = new_map.get(ref)
        if old_parent and new_parent:
            parent_changes = _compare_components_natively(old_parent, new_parent, old_map, new_map, visited)
            if parent_changes:
                changes.append(f"inherited spec '{ref}' changed")

    return changes


def _inherited_specs_natively(inherits, new_map):
    specs = []
    unresolved_refs = []
    seen_refs = set()

    def visit(ref):
        if not ref or ref in seen_refs:
            return
        seen_refs.add(ref)
        parent_comp = new_map.get(ref)
        if parent_comp is not None:
            spec_name = ref.split('.')[-1]
            specs.append((ref, spec_name, parent_comp))
            for p in parent_comp.inherits:
                visit(p)
        else:
            unresolved_refs.append(ref)

    for ref in inherits:
        visit(ref)

    return specs, unresolved_refs


def _print_inherited_specs_natively(inherits, new_map):
    inherited_specs, unresolved_refs = _inherited_specs_natively(inherits, new_map)
    if inherited_specs:
        print("  inherited_specs (STRICTLY FOLLOW THE GUIDANCE BELOW):")
    for ref, spec_name, parent_comp in inherited_specs:
        is_template = parent_comp.is_template
        requirement_text = parent_comp.docstring.strip()
        
        comp_type_str = "requirement"
        try:
            import importlib
            from libspec.spec_types import Feature
            module_name, class_name = ref.rsplit(".", 1)
            module = importlib.import_module(module_name)
            cls = getattr(module, class_name)
            if issubclass(cls, Feature):
                comp_type_str = "feature"
        except Exception:
            pass

        if is_template:
            print(f"    {spec_name}: {ref} (template instance)")
        else:
            print(f"    {spec_name}: {ref}")
            
        if requirement_text:
            print(f"      {comp_type_str}:")
            for line in requirement_text.splitlines():
                print(f"        {line}")

    if unresolved_refs:
        print("  unresolved_inherited_refs:")
        for ref in unresolved_refs:
            print(f"    {ref}")
