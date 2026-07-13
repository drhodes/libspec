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


def generate_native_patch(old_commit=None, new_commit=None):
    """Generate a structured diff between two Git revisions using the native Component model."""
    targets = _resolve_diff_targets(old_commit, new_commit)
    if targets is None:
        return
    old_components, new_components, new_map, label_old, label_new = targets
    print("=" * 60)
    diff_entries, unresolved_by_comp = _compute_diff_entries(
        old_components, new_components, new_map
    )
    _print_diff_patch(diff_entries, unresolved_by_comp, new_map)


def _resolve_diff_targets(old_commit, new_commit):
    from libspec.util import compile_live_spec, compile_git_spec

    is_new_pending = False

    if old_commit is None and new_commit is None:
        old_commit = "HEAD"
        is_new_pending = True
    elif old_commit is not None and new_commit is None:
        new_commit = "HEAD"

    # Compile new_components
    if is_new_pending:
        try:
            new_components, spec_file_path = compile_live_spec()
        except Exception as e:
            print(f"Error compiling live spec: {e}")
            return None
        import os

        rel_spec_file = (
            os.path.relpath(spec_file_path, os.getcwd())
            if spec_file_path
            else "spec/main_spec.py"
        )
        label_new = f"PENDING (Live Spec: {rel_spec_file})"
    else:
        try:
            new_components = compile_git_spec(new_commit)
            label_new = f"Git Ref: {new_commit}"
        except Exception as e:
            if "spec directory" in str(e).lower() or "not extract" in str(e).lower():
                new_components = []
                label_new = "<null spec>"
            else:
                print(f"Error compiling spec at revision '{new_commit}': {e}")
                return None

    # Compile old_components
    try:
        old_components = compile_git_spec(old_commit)
        label_old = f"Git Ref: {old_commit}"
    except Exception as e:
        if "spec directory" in str(e).lower() or "not extract" in str(e).lower():
            old_components = []
            label_old = "<null spec>"
        else:
            print(f"Error compiling spec at revision '{old_commit}': {e}")
            return None

    print(f"Diffing State: {label_old} -> {label_new}")

    new_map = {c.ref: c for c in new_components}
    return old_components, new_components, new_map, label_old, label_new



def _compute_diff_entries(old_components, new_components, new_map):
    old_map = {c.ref: c for c in old_components}
    all_refs = sorted(set(old_map.keys()) | set(new_map.keys()))

    cache = {}
    diff_entries = []
    for ref in all_refs:
        old_comp = old_map.get(ref)
        new_comp = new_map.get(ref)
        comp_type = ref.split(".")[-1]

        if old_comp is None:
            if not getattr(new_comp, "is_dependency", False):
                diff_entries.append(("NEW", comp_type, ref, new_comp, []))
        elif new_comp is None:
            if not getattr(old_comp, "is_dependency", False):
                diff_entries.append(("REMOVED", comp_type, ref, old_comp, []))
        else:
            if not getattr(new_comp, "is_dependency", False):
                changes = _compare_components_natively(
                    old_comp, new_comp, old_map, new_map, cache=cache
                )
                if changes:
                    diff_entries.append(("CHANGED", comp_type, ref, new_comp, changes))


    unresolved_by_comp = {}
    for ref, comp in new_map.items():
        unresolved = [r for r in comp.inherits if r not in new_map]
        if unresolved:
            unresolved_by_comp[ref.split(".")[-1]] = unresolved

    return diff_entries, unresolved_by_comp


def _print_diff_patch(diff_entries, unresolved_by_comp, new_map):
    if not diff_entries and not unresolved_by_comp:
        print("No changes detected.")
        return

    for action, comp_type, ref, comp, changes in diff_entries:
        if action == "NEW":
            if comp.docstring.strip() or comp.inherits:
                print(f"\n[NEW] {comp_type}")
                if comp.docstring.strip():
                    lines = comp.docstring.strip().splitlines()
                    print(f"  docstring: {lines[0]}")
                    for line in lines[1:]:
                        print(f"    {line}")
                if comp.inherits:
                    _print_inherited_specs_natively(comp.inherits, new_map)
        elif action == "REMOVED":
            print(f"\n[REMOVED] {comp_type}")
        elif action == "CHANGED":
            print(f"\n[CHANGED] {comp_type}")
            for change in changes:
                print(f"  - {change}")

    if unresolved_by_comp:
        print("\n[WARNING] The following specs inherit refs that are not present")
        print(
            "  in this snapshot. Changes to those superspecs cannot be detected here."
        )
        for comp_type in sorted(unresolved_by_comp):
            for ref in unresolved_by_comp[comp_type]:
                print(f"  {comp_type} -> unresolved inherited ref: {ref}")


def _compare_components_natively(old_comp, new_comp, old_map, new_map, visited=None, cache=None):
    """Compare two components natively using their hash and fields."""
    if cache is not None and new_comp.ref in cache:
        return cache[new_comp.ref]

    if old_comp.hash == new_comp.hash:
        if cache is not None:
            cache[new_comp.ref] = []
        return []

    if visited is None:
        visited = set()
    visited.add(new_comp.ref)

    changes = []

    # 1. Docstring Diff
    if old_comp.docstring != new_comp.docstring:
        changes.append(
            _patch_block("docstring", old_comp.docstring, new_comp.docstring)
        )

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
            parent_changes = _compare_components_natively(
                old_parent, new_parent, old_map, new_map, visited, cache
            )
            if parent_changes:
                changes.append(f"inherited spec '{ref}' changed")

    if cache is not None:
        cache[new_comp.ref] = changes
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
            spec_name = ref.split(".")[-1]
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
