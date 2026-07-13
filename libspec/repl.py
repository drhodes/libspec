import datetime
import difflib
import os
import sys
import traceback

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggest, Suggestion
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.styles import Style

from libspec.colors import Theme


class ReplCommand:
    """
    Base class interface for all REPL interactive commands.
    """

    def name(self) -> str:
        raise NotImplementedError()

    def desc(self) -> str:
        raise NotImplementedError()

    def run(self, repl, arg: str) -> bool:
        raise NotImplementedError()

    def usage(self) -> str:
        return (
            f"\n{Theme.BOLD_YELLOW}Command:{Theme.RESET}      {Theme.BOLD_GREEN}{self.name()}{Theme.RESET}\n"
            f"{Theme.BOLD_YELLOW}Description:{Theme.RESET}  {self.desc()}\n"
        )


class HelpCommand(ReplCommand):
    def name(self):
        return "help"

    def desc(self):
        return "Show this help message."

    def run(self, repl, arg):
        print(f"\n{Theme.BOLD_YELLOW}Available Commands:{Theme.RESET}")
        max_name_len = max(len(name) for name in repl.commander.commands.keys())
        for name in sorted(repl.commander.commands.keys()):
            cmd = repl.commander.commands[name]
            print(
                f"  {Theme.BOLD_GREEN}{name:<{max_name_len}}{Theme.RESET}  {cmd.desc()}"
            )
        print()
        return True


class ListCommand(ReplCommand):
    def name(self):
        return "list"

    def desc(self):
        return "List all specification components."

    def run(self, repl, arg):
        repl.load_components()
        comps = [c for c in repl.components if not getattr(c, "is_dependency", False)]
        if not comps:
            print(
                f"{Theme.YELLOW}No components found in the active SpecStore.{Theme.RESET}"
            )
            return True
        ctx_name = (
            f"Snapshot ({repl.active_session_id[:10]})"
            if repl.active_session_id
            else "Latest Snapshot"
        )
        print(
            f"\n{Theme.BOLD_YELLOW}{ctx_name} Components ({len(comps)} total):{Theme.RESET}"
        )
        for comp in comps:
            comp_type = "Template" if comp.is_template else "Component"
            print(
                f"  • {Theme.BOLD_CYAN}{comp.ref}{Theme.RESET} [{Theme.GREEN}{comp_type}{Theme.RESET}]"
            )
        print()
        return True


class ShowCommand(ReplCommand):
    def name(self):
        return "show"

    def desc(self):
        return "Show full details of a specific component."

    def usage(self):
        return (
            f"\n{Theme.BOLD_YELLOW}Command:{Theme.RESET}      {Theme.BOLD_GREEN}show{Theme.RESET}\n"
            f"{Theme.BOLD_YELLOW}Description:{Theme.RESET}  {self.desc()}\n"
            f"{Theme.BOLD_YELLOW}Usage:{Theme.RESET}        show <component_ref>\n"
            f"{Theme.BOLD_YELLOW}Example:{Theme.RESET}      show spec.app.App\n"
        )

    def run(self, repl, arg):
        repl._validate_ref(arg)
        comp = next((c for c in repl.components if c.ref == arg), None)
        if comp is None:
            self._handle_missing(repl, arg)
            return True

        print(Theme.BOLD_CYAN + "=" * 60 + Theme.RESET)
        print(
            f"{Theme.BOLD_YELLOW}Reference:{Theme.RESET}   {Theme.BOLD_GREEN}{comp.ref}{Theme.RESET}"
        )
        print(
            f"{Theme.BOLD_YELLOW}Type:{Theme.RESET}        {'Template Requirement' if comp.is_template else 'Requirement'}"
        )
        print(f"{Theme.BOLD_YELLOW}Hash:{Theme.RESET}        {comp.hash}")
        if comp.inherits:
            print(
                f"{Theme.BOLD_YELLOW}Inherits:{Theme.RESET}    "
                + ", ".join(comp.inherits)
            )
        print(
            f"{Theme.BOLD_YELLOW}Docstring:{Theme.RESET}\n{'-' * 60}\n{comp.docstring}\n{'-' * 60}"
        )
        repl._print_show_claims(arg)
        print(Theme.BOLD_CYAN + "=" * 60 + f"{Theme.RESET}\n")
        return True

    def _handle_missing(self, repl, ref):
        print(
            f"{Theme.BOLD_RED}Component '{ref}' not found in active snapshot context.{Theme.RESET}"
        )
        matches = [f for f in repl.fqns if ref.lower() in f.lower()]
        if matches:
            print(f"{Theme.BOLD_YELLOW}Did you mean:{Theme.RESET}")
            for m in matches[:5]:
                print(f"  • {m}")


class ListSnapshotsCommand(ReplCommand):
    def name(self):
        return "list-snapshots"

    def desc(self):
        return "List chronological build/snapshot history."

    def run(self, repl, arg):
        print(f"{Theme.BOLD_YELLOW}\nChronological Snapshot History:{Theme.RESET}")
        print("-" * 60)
        try:
            snapshots = repl.store.list_snapshots()
            repl._snapshot_registry = {}

            # Fetch pending components
            try:
                from libspec.util import compile_live_spec

                pending_comps, _ = compile_live_spec()
            except Exception:
                pending_comps = []

            # Calculate size of pending components
            pending_size = sum(
                len(c.ref.encode("utf-8"))
                + len(c.docstring.encode("utf-8"))
                + sum(len(x.encode("utf-8")) for x in c.inherits)
                + 64
                for c in pending_comps
            )

            # Gather all historical snapshot components and compute metrics
            snapshot_comps = []
            new_counts = []
            size_bytes_list = []

            for i, s in enumerate(snapshots):
                try:
                    comps = repl.store.get_components_for_snapshot(s)
                except Exception:
                    comps = []
                snapshot_comps.append(comps)

                sb = sum(
                    len(c.ref.encode("utf-8"))
                    + len(c.docstring.encode("utf-8"))
                    + sum(len(x.encode("utf-8")) for x in c.inherits)
                    + 64
                    for c in comps
                )
                size_bytes_list.append(sb)

                if i == 0:
                    nc = len(comps)
                else:
                    prev_refs = {c.ref for c in snapshot_comps[i - 1]}
                    current_refs = {c.ref for c in comps}
                    nc = len(current_refs - prev_refs)
                new_counts.append(nc)

            # Compute pending new count
            if snapshots:
                latest_recorded_comps = snapshot_comps[-1]
                prev_refs = {c.ref for c in latest_recorded_comps}
                current_refs = {c.ref for c in pending_comps}
                pending_new_count = len(current_refs - prev_refs)
            else:
                pending_new_count = len(pending_comps)

            # Determine padding widths
            all_new_counts = new_counts + [pending_new_count]
            all_sizes = size_bytes_list + [pending_size]
            max_new_w = max((len(str(x)) for x in all_new_counts), default=1)
            max_bytes_w = max((len(str(x)) for x in all_sizes), default=1)

            all_ids = [s.id for s in snapshots] + ["HEAD"]
            max_id_w = max((len(x) for x in all_ids), default=16)

            has_any_git = any(s.git_commit for s in snapshots) or os.path.exists(".git")

            # Print historical snapshots
            n = len(snapshots)
            w = len(str(n - 1)) if n > 0 else 1
            active_snap = repl.active_snapshot()

            for i, s in enumerate(snapshots):
                idx = n - 1 - i
                repl._snapshot_registry[str(idx)] = s
                repl._snapshot_registry[f"#{idx}"] = s

                is_active = (
                    active_snap
                    and active_snap.id == s.id
                    and active_snap.created_at.replace(tzinfo=None)
                    == s.created_at.replace(tzinfo=None)
                )
                active_marker = (
                    f" {Theme.BOLD_RED}(ACTIVE){Theme.RESET}" if is_active else ""
                )

                new_count = new_counts[i]
                size_bytes = size_bytes_list[i]

                git_info = ""
                if has_any_git:
                    if s.git_commit and s.git_commit != "HEAD":
                        git_str = f"(Git: {s.git_commit[:7]})"
                    else:
                        git_str = "(Git: HEAD)"
                    git_info = f" | {git_str:<14}"

                print(
                    f"  #{idx:>{w}} • {Theme.BOLD_CYAN}{s.created_at.strftime('%Y-%m-%d %H:%M:%S')}{Theme.RESET}"
                    f" | ID: {Theme.GREEN}{s.id:<{max_id_w}}{Theme.RESET}"
                    f" | {Theme.BOLD_MAGENTA}{new_count:>{max_new_w}}{Theme.RESET} new"
                    f" | {Theme.BOLD_MAGENTA}{size_bytes:>{max_bytes_w}}{Theme.RESET} bytes"
                    f"{git_info}{active_marker}"
                )

            # Print HEAD snapshot row
            head_active = repl.active_build is None
            head_active_marker = (
                f" {Theme.BOLD_RED}(ACTIVE){Theme.RESET}" if head_active else ""
            )

            import datetime

            current_time = datetime.datetime.now(datetime.UTC)

            head_git_info = ""
            if has_any_git:
                head_git_info = f" | {'(Git: HEAD)':<14}"

            head_idx_str = "  *" + " " * w

            print(
                f"{head_idx_str} • {Theme.BOLD_CYAN}{current_time.strftime('%Y-%m-%d %H:%M:%S')}{Theme.RESET}"
                f" | ID: {Theme.GREEN}{'HEAD':<{max_id_w}}{Theme.RESET}"
                f" | {Theme.BOLD_MAGENTA}{pending_new_count:>{max_new_w}}{Theme.RESET} new"
                f" | {Theme.BOLD_MAGENTA}{pending_size:>{max_bytes_w}}{Theme.RESET} bytes"
                f"{head_git_info}{head_active_marker}"
            )

        except Exception as e:
            print(f"Failed to query snapshots: {e}")
        print("-" * 60 + "\n")
        return True


class SearchCommand(ReplCommand):
    def name(self):
        return "search"

    def desc(self):
        return "Search components and docstrings."

    def run(self, repl, arg):
        if not isinstance(arg, str) or not arg.strip():
            raise ValueError("Query must be a non-empty string.")
        comps = [c for c in repl.components if not getattr(c, "is_dependency", False)]
        matches = [
            c
            for c in comps
            if arg.lower() in c.ref.lower() or arg.lower() in c.docstring.lower()
        ]
        if not matches:
            print(f"{Theme.YELLOW}No components found matching '{arg}'.{Theme.RESET}")
            return True

        print(
            f"\n{Theme.BOLD_YELLOW}Search Results for '{arg}' ({len(matches)} matches):{Theme.RESET}"
        )
        for comp in matches:
            comp_type = "Template" if comp.is_template else "Component"
            snippet = comp.docstring.split("\n")[0][:60]
            if len(comp.docstring.split("\n")[0]) > 60:
                snippet += "..."
            print(
                f"  • {Theme.BOLD_CYAN}{comp.ref}{Theme.RESET} [{Theme.GREEN}{comp_type}{Theme.RESET}] - {snippet}"
            )
        return True


class EnterCommand(ReplCommand):
    def name(self):
        return "enter"

    def desc(self):
        return "Scope REPL to a historical snapshot."

    def usage(self):
        return (
            f"\n{Theme.BOLD_YELLOW}Command:{Theme.RESET}      {Theme.BOLD_GREEN}enter{Theme.RESET}\n"
            f"{Theme.BOLD_YELLOW}Description:{Theme.RESET}  {self.desc()}\n"
            f"{Theme.BOLD_YELLOW}Usage:{Theme.RESET}        enter <snapshot_id_or_date_or_index>\n"
            f"{Theme.BOLD_YELLOW}Details:{Theme.RESET}      Accepts index (e.g. #0 for latest, #1 for second latest),\n"
            f"              hexadecimal snapshot ID prefix, or ISO timestamp.\n"
            f"{Theme.BOLD_YELLOW}Example:{Theme.RESET}      enter #2\n"
            f"              enter f92fb270\n"
        )

    def run(self, repl, arg):
        if not arg:
            raise ValueError("Snapshot ID or hash required.")
        if arg.lower() == "latest":
            repl.cmd_leave()
            return True

        build = repl.find_build_by_id(arg)
        if build:
            repl.active_build = build
            repl.load_components()
            print(
                f"{Theme.BOLD_GREEN}Entered snapshot context: {repl.active_session_id}{Theme.RESET}"
            )
        return True


class LeaveCommand(ReplCommand):
    def name(self):
        return "leave"

    def desc(self):
        return "Restore context to latest snapshot."

    def run(self, repl, arg):
        if repl.active_build is None:
            print("Already in the latest snapshot context.")
            return True
        repl.active_build = None
        repl.load_components()
        print(f"{Theme.BOLD_GREEN}Returned to latest snapshot context.{Theme.RESET}")
        return True


class ExitCommand(ReplCommand):
    def name(self):
        return "exit"

    def desc(self):
        return "Exit the REPL session."

    def run(self, repl, arg):
        print("An ounce of spec is worth a pound of code.")
        return False


class DiffCommand(ReplCommand):
    def name(self):
        return "diff"

    def desc(self):
        return "Color-coded overview of snapshot differences."

    def usage(self):
        return (
            f"\n{Theme.BOLD_YELLOW}Command:{Theme.RESET}      {Theme.BOLD_GREEN}diff{Theme.RESET}\n"
            f"{Theme.BOLD_YELLOW}Description:{Theme.RESET}  {self.desc()}\n"
            f"{Theme.BOLD_YELLOW}Usage:{Theme.RESET}        diff [snapshot_a] [snapshot_b] [-v] [-vv]\n"
            f"{Theme.BOLD_YELLOW}Flags:{Theme.RESET}        -v   Show granular unified diffs of component docstrings.\n"
            f"              -vv  Show full comprehensive semantic diff report including all properties.\n"
            f"{Theme.BOLD_YELLOW}Example:{Theme.RESET}      diff\n"
            f"              diff #1 -v\n"
            f"              diff #2 #0 -vv\n"
        )

    def run(self, repl, arg):
        parts = arg.split() if arg else []
        very_verbose = "-vv" in parts
        verbose = "-v" in parts or very_verbose
        if "-vv" in parts:
            parts.remove("-vv")
        if "-v" in parts:
            parts.remove("-v")

        try:
            old_snap, new_snap = repl._resolve_diff_snapshots(parts)
            if very_verbose:
                from libspec.spec_diff import generate_native_patch

                generate_native_patch(old_commit=old_snap.id if old_snap else None, new_commit=new_snap.id if new_snap else None)
            else:
                old_comps = repl.get_components_for_build(old_snap)
                builds = repl._get_chronological_builds()
                latest_snap = repl._make_snapshot_from_git(builds[-1]) if builds else None
                active_build = repl.active_build or latest_snap
                if new_snap and new_snap.id == "HEAD":
                    # Load components live
                    from libspec.util import compile_live_spec

                    try:
                        new_comps, _ = compile_live_spec()
                    except Exception as e:
                        print(
                            f"{Theme.BOLD_RED}Error compiling live spec: {e}{Theme.RESET}"
                        )
                        return True
                elif active_build and new_snap and new_snap.id == active_build.id:
                    new_comps = repl.components
                else:
                    new_comps = repl.get_components_for_build(new_snap)
                old_desc = repl._get_build_desc(old_snap)
                new_desc = repl._get_build_desc(new_snap)
                added, removed, changed = repl._compute_diff(old_comps, new_comps)

                # REQUIREMENT-ID: spec.repl.DiffProvenanceResolution
                # Precompute dynamic relative index map and cache intermediate components to prevent redundant parsing
                builds = repl._get_chronological_builds()
                all_snaps = []
                for b in builds:
                    snap = repl._make_snapshot_from_git(b)
                    if snap:
                        all_snaps.append(snap)
                n_stored_snaps = len(all_snaps)
                if new_snap and new_snap.id == "HEAD":
                    all_snaps.append(new_snap)

                snap_to_idx = {}
                for idx, s in enumerate(all_snaps):
                    if s.id == "HEAD":
                        snap_to_idx[s.id] = "HEAD"
                    else:
                        orig_idx = idx
                        rev_idx = n_stored_snaps - 1 - orig_idx
                        snap_to_idx[s.id] = f"#{rev_idx}"

                idx_b = next(
                    (
                        i
                        for i, s in enumerate(all_snaps)
                        if new_snap and s.id == new_snap.id
                    ),
                    len(all_snaps) - 1,
                )
                idx_a = (
                    next(
                        (
                            i
                            for i, s in enumerate(all_snaps)
                            if old_snap and s.id == old_snap.id
                        ),
                        -1,
                    )
                    if old_snap
                    else -1
                )

                snap_components = {}
                for i in range(idx_a + 1, idx_b + 1):
                    if 0 <= i < len(all_snaps):
                        s = all_snaps[i]
                        if s.id == "HEAD":
                            snap_components[s.id] = new_comps
                        elif active_build and s.id == active_build.id:
                            snap_components[s.id] = repl.components
                        else:
                            snap_components[s.id] = repl.get_components_for_build(s)

                def get_provenance_tag(c, action_verb: str) -> str:
                    intro_snap = new_snap
                    for i in range(idx_a + 1, idx_b + 1):
                        if 0 <= i < len(all_snaps):
                            s = all_snaps[i]
                            comps = snap_components.get(s.id, [])
                            match = next(
                                (comp for comp in comps if comp.ref == c.ref), None
                            )
                            if match and match.hash == c.hash:
                                intro_snap = s
                                break

                    if intro_snap is None:
                        return ""
                    rel_idx = snap_to_idx.get(intro_snap.id, intro_snap.id[:8])
                    if intro_snap.git_commit and intro_snap.git_commit != "HEAD":
                        git_info = f" | Git: {intro_snap.git_commit[:7]}"
                    else:
                        git_info = " | Git: HEAD"
                    # REQUIREMENT-ID: spec.repl.DiffProvenanceFormatting
                    return f" {Theme.BOLD_BLACK}({action_verb} in {rel_idx}{git_info}){Theme.RESET}"

                self._print_report(
                    old_desc,
                    new_desc,
                    added,
                    removed,
                    changed,
                    verbose,
                    get_provenance_tag,
                )
        except ValueError as e:
            print(f"{Theme.BOLD_RED}Error executing diff: {e}{Theme.RESET}")
        except Exception as e:
            print(f"{Theme.BOLD_RED}Error executing diff: {e}{Theme.RESET}")
            import traceback

            traceback.print_exc()
        return True

    def _print_report(
        self, old_desc, new_desc, added, removed, changed, verbose, get_provenance_tag
    ):
        print(f"\n{Theme.BOLD_YELLOW}Specification Diff Overview:{Theme.RESET}")
        print(
            f"  Comparing: {Theme.CYAN}{old_desc}{Theme.RESET} -> {Theme.GREEN}{new_desc}{Theme.RESET}"
        )
        print("-" * 60)

        if not added and not removed and not changed:
            print("  No changes detected.")
            print("-" * 60 + "\n")
            return

        self._print_added(added, verbose, get_provenance_tag)
        self._print_removed(removed)
        self._print_changed(changed, verbose, get_provenance_tag)
        print("-" * 60 + "\n")

    def _print_added(self, added, verbose, get_provenance_tag):
        if not added:
            return
        print(f"  {Theme.BOLD_GREEN}[ADDED]{Theme.RESET} Components:")
        for c in added:
            comp_type = "Template" if c.is_template else "Component"
            prov = get_provenance_tag(c, "introduced")
            print(f"    • {c.ref} [{comp_type}]{prov}")
            if verbose and c.docstring:
                print(
                    f"      {Theme.BOLD_BLACK}Docstring:{Theme.RESET}\n      {'-' * 56}"
                )
                for line in c.docstring.splitlines():
                    print(f"      {line}")
                print("      " + "-" * 56)
        print()

    def _print_removed(self, removed):
        if not removed:
            return
        print(f"  {Theme.BOLD_RED}[REMOVED]{Theme.RESET} Components:")
        for c in removed:
            comp_type = "Template" if c.is_template else "Component"
            print(f"    • {c.ref} [{comp_type}]")
        print()

    def _print_changed(self, changed, verbose, get_provenance_tag):
        if not changed:
            return
        print(f"  \033[1;34m[CHANGED]{Theme.RESET} Components:")
        for old_c, new_c in changed:
            comp_type = "Template" if new_c.is_template else "Component"
            prov = get_provenance_tag(new_c, "changed")
            print(f"    • {new_c.ref} [{comp_type}]{prov}")
            if verbose:
                self._print_docstring_diff(old_c, new_c)
        print()

    def _print_docstring_diff(self, old_c, new_c):
        old_lines = (old_c.docstring or "").splitlines()
        new_lines = (new_c.docstring or "").splitlines()
        diff = list(
            difflib.unified_diff(
                old_lines,
                new_lines,
                fromfile="old/docstring",
                tofile="new/docstring",
                lineterm="",
            )
        )
        if diff:
            print(
                f"      {Theme.BOLD_BLACK}Docstring Diff:{Theme.RESET}\n      {'-' * 56}"
            )
            for line in diff:
                if line.startswith("+") and not line.startswith("+++"):
                    print(f"      {Theme.GREEN}{line}{Theme.RESET}")
                elif line.startswith("-") and not line.startswith("---"):
                    print(f"      {Theme.RED}{line}{Theme.RESET}")
                elif line.startswith("@@"):
                    print(f"      {Theme.CYAN}{line}{Theme.RESET}")
                else:
                    print(f"      {line}")
            print("      " + "-" * 56)


class CompactCommand(ReplCommand):
    def name(self):
        return "compact"

    def desc(self):
        return "Compact the specification store, squashing intermediate drafts and merging VCS links."

    def usage(self):
        return (
            f"\n{Theme.BOLD_YELLOW}Command:{Theme.RESET}      {Theme.BOLD_GREEN}compact{Theme.RESET}\n"
            f"{Theme.BOLD_YELLOW}Description:{Theme.RESET}  {self.desc()}\n"
            f"{Theme.BOLD_YELLOW}Usage:{Theme.RESET}        compact [--dry-run]\n"
        )

    def run(self, repl, arg):
        dry_run = "--dry-run" in arg.split()
        if not hasattr(repl.store, "compact"):
            print(
                f"{Theme.BOLD_RED}Error: Active store backend does not support compaction.{Theme.RESET}"
            )
            return True
        try:
            res = repl.store.compact(dry_run=dry_run)
            orig_kb = res["original_size"] / 1024.0
            comp_kb = res["compacted_size"] / 1024.0
            reclaimed_kb = res["reclaimed_bytes"] / 1024.0

            print("============================================================")
            print("                 LIBSPEC COMPACTION REPORT                  ")
            print("============================================================")
            if dry_run:
                print("MODE             : DRY RUN (No changes written)")
            else:
                print("MODE             : EXECUTION (Database compacted)")

            print(f"Snapshots Pruned : {res['pruned_snapshots_count']}")
            print(f"Original Size    : {orig_kb:.2f} KB")
            print(f"Compacted Size   : {comp_kb:.2f} KB")

            if res["reclaimed_bytes"] > 0 and orig_kb > 0:
                print(
                    f"Space Reclaimed  : {reclaimed_kb:.2f} KB ({reclaimed_kb / orig_kb * 100.0:.1f}%)"
                )
            else:
                print("Space Reclaimed  : 0.00 KB (Database already fully optimized)")

            if res["upgraded_legacy_format"]:
                if dry_run:
                    print("Format Upgrade   : PENDING (Legacy format detected)")
                else:
                    print("Format Upgrade   : COMPLETED (Legacy format migrated)")
            print("============================================================")

            if not dry_run:
                repl.load_components()
                if (
                    hasattr(repl, "last_mtime")
                    and hasattr(repl.store, "filepath")
                    and os.path.exists(repl.store.filepath)
                ):
                    repl.last_mtime = os.path.getmtime(repl.store.filepath)
        except Exception as e:
            print(f"{Theme.BOLD_RED}Failed to compact: {e}{Theme.RESET}")
        return True


class RmSnapshotCommand(ReplCommand):
    def name(self):
        return "rm-snapshot"

    def desc(self):
        return "Permanently delete a historical snapshot."

    def usage(self):
        return (
            f"\n{Theme.BOLD_YELLOW}Command:{Theme.RESET}      {Theme.BOLD_GREEN}rm-snapshot{Theme.RESET}\n"
            f"{Theme.BOLD_YELLOW}Description:{Theme.RESET}  {self.desc()}\n"
            f"{Theme.BOLD_YELLOW}Usage:{Theme.RESET}        rm-snapshot <snapshot_id_or_index>\n"
            f"{Theme.BOLD_YELLOW}Example:{Theme.RESET}      rm-snapshot #3\n"
        )

    def run(self, repl, arg):
        if not arg:
            raise ValueError("Snapshot ID or hash required.")

        target = repl.find_build_by_id(arg)
        if target is None:
            return True

        # Safety Check 1: Refuse to delete the LATEST snapshot
        latest = repl.store.current_snapshot()
        if latest and latest.id == target.id:
            print(
                f"{Theme.BOLD_RED}Error: Cannot delete snapshot '{target.id}' because it is the latest recorded build.{Theme.RESET}"
            )
            return True

        # Safety Check 2: Refuse to delete the currently active/entered snapshot
        if repl.active_session_id == target.id:
            print(
                f"{Theme.BOLD_RED}Error: Cannot delete snapshot '{target.id}' because it is the currently active/entered context.{Theme.RESET}"
            )
            print("Leave or enter a different snapshot first.")
            return True

        # Confirmation Prompt with detailed verification card
        git_info = f" {target.git_commit[:7]}" if target.git_commit else " <none>"
        print(
            f"{Theme.YELLOW}WARNING: You are about to delete (tombstone) the following snapshot:{Theme.RESET}"
        )
        print(Theme.YELLOW + "-" * 60 + Theme.RESET)
        print(f"  • Target Reference : {Theme.BOLD_CYAN}{arg.strip()}{Theme.RESET}")
        print(f"  • Resolved Hash ID : {Theme.GREEN}{target.id}{Theme.RESET}")
        print(f"  • Date Created     : {target.created_at.isoformat()}")
        print(f"  • Associated Git   :{git_info}")
        print(Theme.YELLOW + "-" * 60 + Theme.RESET)
        print(
            f"{Theme.YELLOW}Note: This can be recovered later using restore-snapshot.{Theme.RESET}"
        )
        try:
            confirm = (
                input(
                    f"{Theme.BOLD_YELLOW}Are you sure you want to proceed? (y/N):{Theme.RESET} "
                )
                .strip()
                .lower()
            )
        except EOFError:
            print("\nAborted.")
            return True

        if confirm not in ("y", "yes"):
            print("Aborted.")
            return True

        try:
            repl.store.delete_snapshot(target)
            print(
                f"{Theme.BOLD_GREEN}Snapshot '{target.id}' successfully deleted.{Theme.RESET}"
            )
            repl.load_components()
        except Exception as e:
            print(f"{Theme.BOLD_RED}Failed to delete snapshot: {e}{Theme.RESET}")

        return True


class RestoreSnapshotCommand(ReplCommand):
    def name(self):
        return "restore-snapshot"

    def desc(self):
        return "Restore a previously deleted/tombstoned historical snapshot."

    def usage(self):
        return (
            f"\n{Theme.BOLD_YELLOW}Command:{Theme.RESET}      {Theme.BOLD_GREEN}restore-snapshot{Theme.RESET}\n"
            f"{Theme.BOLD_YELLOW}Description:{Theme.RESET}  {self.desc()}\n"
            f"{Theme.BOLD_YELLOW}Usage:{Theme.RESET}        restore-snapshot <snapshot_id_or_index>\n"
            f"{Theme.BOLD_YELLOW}Example:{Theme.RESET}      restore-snapshot #3\n"
        )

    def run(self, repl, arg):
        if not arg:
            raise ValueError("Snapshot ID or hash required.")

        target = repl.find_build_by_id(arg)
        if target is None:
            return True

        active_builds = repl._get_chronological_builds()
        if any(s.id == target.id for s in active_builds):
            print(f"Snapshot '{target.id}' is already active.")
            return True

        print(f"{Theme.BOLD_GREEN}Restoring snapshot:{Theme.RESET}")
        print(f"  • Hash ID      : {Theme.GREEN}{target.id}{Theme.RESET}")
        print(f"  • Date Created : {target.created_at.isoformat()}")

        try:
            repl.store.restore_snapshot(target)
            print(
                f"{Theme.BOLD_GREEN}Snapshot '{target.id}' successfully restored.{Theme.RESET}"
            )
            repl.load_components()
        except Exception as e:
            print(f"{Theme.BOLD_RED}Failed to restore snapshot: {e}{Theme.RESET}")

        return True


class LinkCommand(ReplCommand):
    def name(self):
        return "link"

    def desc(self):
        return "Link a compiled spec snapshot to a VCS revision."

    def usage(self):
        return (
            f"\n{Theme.BOLD_YELLOW}Command:{Theme.RESET}      {Theme.BOLD_GREEN}link{Theme.RESET}\n"
            f"{Theme.BOLD_YELLOW}Description:{Theme.RESET}  {self.desc()}\n"
            f"{Theme.BOLD_YELLOW}Usage:{Theme.RESET}        link [--snapshot <snapshot_id>] --vcs <vcs_type> --revision <revision> [--metadata <key=val>]\n"
        )

    def run(self, repl, arg):
        import shlex

        try:
            tokens = shlex.split(arg)
        except Exception as e:
            print(f"{Theme.BOLD_RED}Error: Failed to parse arguments: {e}{Theme.RESET}")
            return True

        snapshot_id = None
        vcs_type = "git"
        revision = None
        metadata_pairs = []

        i = 0
        while i < len(tokens):
            token = tokens[i]
            if token == "--snapshot":
                if i + 1 < len(tokens):
                    snapshot_id = tokens[i + 1]
                    i += 2
                else:
                    print(
                        f"{Theme.BOLD_RED}Error: Missing value for --snapshot{Theme.RESET}"
                    )
                    return True
            elif token == "--vcs":
                if i + 1 < len(tokens):
                    vcs_type = tokens[i + 1]
                    i += 2
                else:
                    print(
                        f"{Theme.BOLD_RED}Error: Missing value for --vcs{Theme.RESET}"
                    )
                    return True
            elif token == "--revision":
                if i + 1 < len(tokens):
                    revision = tokens[i + 1]
                    i += 2
                else:
                    print(
                        f"{Theme.BOLD_RED}Error: Missing value for --revision{Theme.RESET}"
                    )
                    return True
            elif token == "--metadata":
                if i + 1 < len(tokens):
                    metadata_pairs.append(tokens[i + 1])
                    i += 2
                else:
                    print(
                        f"{Theme.BOLD_RED}Error: Missing value for --metadata{Theme.RESET}"
                    )
                    return True
            else:
                print(f"{Theme.BOLD_RED}Error: Unknown argument '{token}'{Theme.RESET}")
                return True

        if not revision:
            print(f"{Theme.BOLD_RED}Error: --revision option is required.{Theme.RESET}")
            return True

        # Resolve snapshot
        target_ids = []
        if not snapshot_id:
            # Fallback to unlinked snapshots or current active snapshot
            snapshots = repl._get_chronological_builds()
            unlinked = [
                s.id for s in snapshots if not s.git_commit or s.git_commit == "HEAD"
            ]
            if unlinked:
                target_ids = unlinked
            else:
                if repl.active_session_id:
                    target_ids = [repl.active_session_id]
                else:
                    curr = repl.store.current_snapshot()
                    if curr:
                        target_ids = [curr.id]
        else:
            # Resolve via repl helper
            resolved = repl.find_build_by_id(snapshot_id)
            if resolved is None:
                print(
                    f"{Theme.BOLD_RED}Error: Snapshot '{snapshot_id}' not found.{Theme.RESET}"
                )
                return True
            target_ids = [resolved.id]

        if not target_ids:
            print(
                f"{Theme.BOLD_RED}Error: No snapshots to link. Compile a snapshot first.{Theme.RESET}"
            )
            return True

        metadata = {}
        for pair in metadata_pairs:
            if "=" in pair:
                k, v = pair.split("=", 1)
                metadata[k.strip()] = v.strip()
            else:
                metadata[pair.strip()] = ""

        success_count = 0
        for t_id in target_ids:
            try:
                repl.store.store_vcs_link(
                    t_id, vcs=vcs_type, revision=revision, metadata=metadata
                )
                success_count += 1
            except Exception as e:
                print(
                    f"{Theme.BOLD_RED}Error: Failed to link snapshot '{t_id}': {e}{Theme.RESET}"
                )

        if success_count > 1:
            print(
                f"{Theme.BOLD_GREEN}Successfully linked {success_count} snapshots to {vcs_type} revision {revision}.{Theme.RESET}"
            )
        elif success_count == 1:
            print(
                f"{Theme.BOLD_GREEN}Successfully linked snapshot {target_ids[0]} to {vcs_type} revision {revision}.{Theme.RESET}"
            )

        repl.load_components()
        return True


class LogCommand(ReplCommand):
    def name(self):
        return "log"

    def desc(self):
        return "Show specification Git commit history."

    def usage(self):
        return (
            f"\n{Theme.BOLD_YELLOW}Command:{Theme.RESET}      {Theme.BOLD_GREEN}log{Theme.RESET}\n"
            f"{Theme.BOLD_YELLOW}Description:{Theme.RESET}  {self.desc()}\n"
            f"{Theme.BOLD_YELLOW}Usage:{Theme.RESET}        log\n"
        )

    def run(self, repl, arg):
        try:
            import subprocess
            res = subprocess.run(
                ["git", "log", "-n", "20", "--oneline", "--decorate"],
                capture_output=True,
                text=True,
                check=True
            )
            print(f"\n{Theme.BOLD_YELLOW}Specification Git Commit History (Latest 20):{Theme.RESET}")
            print(Theme.GRAY + "-" * 80 + Theme.RESET)
            print(res.stdout)
            print(Theme.GRAY + "-" * 80 + Theme.RESET)
        except Exception as e:
            print(f"{Theme.BOLD_RED}Failed to read Git history: {e}{Theme.RESET}")
        return True


class DeclareDependencyCommand(ReplCommand):
    def name(self):
        return "declare-dependency"

    def desc(self):
        return "Declare a logical dependency between components."

    def usage(self):
        return (
            f"\n{Theme.BOLD_YELLOW}Command:{Theme.RESET}      {Theme.BOLD_GREEN}declare-dependency{Theme.RESET}\n"
            f"{Theme.BOLD_YELLOW}Description:{Theme.RESET}  {self.desc()}\n"
            f"{Theme.BOLD_YELLOW}Usage:{Theme.RESET}        declare-dependency <ref> <depends_on> [--snapshot <id>]\n"
            f"{Theme.BOLD_YELLOW}Example:{Theme.RESET}      declare-dependency A B --snapshot PENDING\n"
        )

    def run(self, repl, arg):
        import shlex

        try:
            tokens = shlex.split(arg)
        except Exception as e:
            print(f"{Theme.BOLD_RED}Error: Failed to parse arguments: {e}{Theme.RESET}")
            return True

        args = []
        snapshot_id = "PENDING"

        i = 0
        while i < len(tokens):
            token = tokens[i]
            if token == "--snapshot" or token == "-s":
                if i + 1 < len(tokens):
                    snapshot_id = tokens[i + 1]
                    i += 2
                else:
                    print(
                        f"{Theme.BOLD_RED}Error: Missing value for --snapshot{Theme.RESET}"
                    )
                    return True
            else:
                args.append(token)
                i += 1

        if len(args) != 2:
            print(
                f"{Theme.BOLD_RED}Error: declare-dependency requires exactly two positional arguments: <ref> and <depends_on>{Theme.RESET}"
            )
            print(self.usage())
            return True

        ref, depends_on = args[0], args[1]
        try:
            repl.store.store_dependency(ref, depends_on, snapshot_id)
            print(
                f"{Theme.BOLD_GREEN}Successfully declared dependency: '{ref}' depends on '{depends_on}' (Snapshot: {snapshot_id}).{Theme.RESET}"
            )
        except Exception as e:
            print(
                f"{Theme.BOLD_RED}Error: Failed to declare dependency: {e}{Theme.RESET}"
            )
        return True


class DependenciesCommand(ReplCommand):
    def name(self):
        return "dependencies"

    def desc(self):
        return "List component dependencies."

    def usage(self):
        return (
            f"\n{Theme.BOLD_YELLOW}Command:{Theme.RESET}      {Theme.BOLD_GREEN}dependencies{Theme.RESET}\n"
            f"{Theme.BOLD_YELLOW}Description:{Theme.RESET}  {self.desc()}\n"
            f"{Theme.BOLD_YELLOW}Usage:{Theme.RESET}        dependencies [--snapshot <id>]\n"
            f"{Theme.BOLD_YELLOW}Example:{Theme.RESET}      dependencies --snapshot PENDING\n"
        )

    def run(self, repl, arg):
        import shlex

        try:
            tokens = shlex.split(arg)
        except Exception as e:
            print(f"{Theme.BOLD_RED}Error: Failed to parse arguments: {e}{Theme.RESET}")
            return True

        snapshot_id = "HEAD"

        i = 0
        while i < len(tokens):
            token = tokens[i]
            if token == "--snapshot" or token == "-s":
                if i + 1 < len(tokens):
                    snapshot_id = tokens[i + 1]
                    i += 2
                else:
                    print(
                        f"{Theme.BOLD_RED}Error: Missing value for --snapshot{Theme.RESET}"
                    )
                    return True
            else:
                print(f"{Theme.BOLD_RED}Error: Unknown argument '{token}'{Theme.RESET}")
                return True

        if snapshot_id == "HEAD":
            comps = repl.components
            label = "HEAD"
        else:
            build = repl.find_build_by_id(snapshot_id)
            if not build:
                print(
                    f"{Theme.BOLD_RED}Error: Snapshot '{snapshot_id}' not found.{Theme.RESET}"
                )
                return True
            comps = repl.get_components_for_build(build)
            label = build.id

        deps = {}
        for comp in comps:
            if comp.inherits:
                deps[comp.ref] = comp.inherits

        if not deps:
            print(f"No dependencies recorded for snapshot/state '{label}'.")
            return True

        print(
            f"{Theme.BOLD_YELLOW}Component Dependencies for '{label}':{Theme.RESET}"
        )
        for ref, depends_list in sorted(deps.items()):
            print(f"  • {Theme.BOLD_CYAN}{ref}{Theme.RESET}")
            for dep in sorted(depends_list):
                print(f"    └── depends on: {Theme.GREEN}{dep}{Theme.RESET}")
        return True


class AgentConfigCommand(ReplCommand):
    def name(self):
        return "agent-config"

    def desc(self):
        return "Configure local coding agent integrations."

    def usage(self):
        return (
            f"\n{Theme.BOLD_YELLOW}Command:{Theme.RESET}      {Theme.BOLD_GREEN}agent-config{Theme.RESET}\n"
            f"{Theme.BOLD_YELLOW}Description:{Theme.RESET}  {self.desc()}\n"
            f"{Theme.BOLD_YELLOW}Usage:{Theme.RESET}        agent-config <agent> [project_root] [--list]\n"
            f"{Theme.BOLD_YELLOW}Example:{Theme.RESET}      agent-config gemini\n"
            f"              agent-config --list\n"
        )

    def run(self, repl, arg):
        parts = arg.strip().split()
        list_agents = False
        agent = None
        project_root = None

        for part in parts:
            if part == "--list":
                list_agents = True
            elif part.startswith("-"):
                pass
            elif agent is None:
                agent = part
            elif project_root is None:
                project_root = part

        from libspec.agent_config import get_agent_config, list_supported_agents

        if list_agents:
            print(list_supported_agents())
            return True

        if not agent:
            print(
                f"{Theme.BOLD_RED}Error: Agent name or --list option required.{Theme.RESET}"
            )
            return True

        root = project_root or "."
        try:
            configurator = get_agent_config(agent, root)
            res = configurator.configure()
            print(res)
        except Exception as e:
            print(f"{Theme.BOLD_RED}Error: {e}{Theme.RESET}")
        return True


class DashboardCommand(ReplCommand):
    def name(self):
        return "dashboard"

    def desc(self):
        return "Show an overview of the current scheduler state and progress."

    def run(self, repl, arg):
        try:
            import libspec_scheduler.mcp as mcp_mod
        except ImportError:
            print(
                f"{Theme.BOLD_RED}Error: libspec-scheduler is not installed or available.{Theme.RESET}"
            )
            return True

        scheduler = mcp_mod._scheduler
        patch_manager = mcp_mod._patch_manager

        if scheduler is None:
            print(
                f"{Theme.BOLD_RED}Error: Scheduler is not initialized. Call init_scheduler first.{Theme.RESET}"
            )
            return True

        # Collect counts
        states = {}
        for node in scheduler.graph.nodes:
            states[node] = scheduler.get_state(node)

        total = len(states)
        counts = {
            "PENDING": 0,
            "READY": 0,
            "ASSIGNED": 0,
            "IMPLEMENTED": 0,
            "FAILED": 0,
        }
        for s in states.values():
            if s in counts:
                counts[s] += 1

        # Calculate completion percent
        pct = int(counts["IMPLEMENTED"] * 100 / total) if total > 0 else 0
        bar_len = 20
        filled_len = int(bar_len * pct // 100)
        bar = "█" * filled_len + "░" * (bar_len - filled_len)

        # Display Overview Header
        print(f"\n{Theme.BOLD_CYAN}" + "=" * 60 + Theme.RESET)
        print(f" {Theme.BOLD_YELLOW}SCHEDULER PROGRESS DASHBOARD{Theme.RESET}")
        print(f"{Theme.BOLD_CYAN}" + "=" * 60 + Theme.RESET)
        print(f"Status Bar   : [{Theme.BOLD_GREEN}{bar}{Theme.RESET}] {pct}% Complete")
        print(f"Task Summary : {Theme.BOLD_CYAN}{total}{Theme.RESET} total tasks")
        print(f"  • {Theme.GREEN}Implemented{Theme.RESET} : {counts['IMPLEMENTED']}")
        print(f"  • {Theme.YELLOW}Assigned{Theme.RESET}    : {counts['ASSIGNED']}")
        print(f"  • {Theme.CYAN}Ready{Theme.RESET}       : {counts['READY']}")
        print(f"  • {Theme.GRAY}Pending{Theme.RESET}     : {counts['PENDING']}")
        if counts["FAILED"] > 0:
            print(f"  • {Theme.BOLD_RED}Failed{Theme.RESET}      : {counts['FAILED']}")
        else:
            print(f"  • {Theme.GRAY}Failed{Theme.RESET}      : 0")

        # Active Workers
        print(f"\n{Theme.BOLD_YELLOW}Active Workers:{Theme.RESET}")
        if not scheduler.assignments:
            print("  No active worker assignments.")
        else:
            import time

            now = time.time()
            for ref, assignment in scheduler.assignments.items():
                elapsed = int(now - assignment.assigned_at)
                elapsed_str = f"{elapsed // 60}m {elapsed % 60}s"
                print(
                    f"  • {Theme.BOLD_CYAN}{assignment.subagent_id}{Theme.RESET} -> {ref} (leased {elapsed_str} ago)"
                )

        # Recent Activity (Latest Patches)
        print(f"\n{Theme.BOLD_YELLOW}Recent Activity (Latest Patches):{Theme.RESET}")
        patches = patch_manager.patches
        if not patches:
            print("  No micro-patches published yet.")
        else:
            for p in reversed(patches[-3:]):
                print(
                    f"  • [{Theme.GREEN}{p.patch_id}{Theme.RESET}] {Theme.BOLD_CYAN}{p.subagent_id}{Theme.RESET}: {p.description} ({p.file_path})"
                )

        # Next Ready Tasks
        print(f"\n{Theme.BOLD_YELLOW}Next Ready Tasks in Queue:{Theme.RESET}")
        ready_tasks = scheduler.get_ready_tasks()
        if not ready_tasks:
            print("  No ready tasks in queue.")
        else:
            for i, ref in enumerate(ready_tasks[:5], 1):
                print(f"  {i}. {Theme.BOLD_GREEN}{ref}{Theme.RESET}")

        print(f"{Theme.BOLD_CYAN}" + "=" * 60 + Theme.RESET + "\n")
        return True


class Commander:
    def __init__(self):
        self.commands = {}
        self.aliases = {}
        self.aliases = {}
        self._setup()

    def _setup(self):
        cmd_list = [
            HelpCommand(),
            ListCommand(),
            ShowCommand(),
            SearchCommand(),
            EnterCommand(),
            LeaveCommand(),
            DiffCommand(),
            LogCommand(),
            ExitCommand(),
            DependenciesCommand(),
            AgentConfigCommand(),
            DashboardCommand(),
        ]
        for cmd in cmd_list:
            self.commands[cmd.name()] = cmd

        self.aliases["h"] = "help"
        self.aliases["?"] = "help"
        self.aliases["components"] = "list"
        self.aliases["quit"] = "exit"
        self.aliases["q"] = "exit"
        self.aliases["dep"] = "dependencies"
        self.aliases["deps"] = "dependencies"
        self.aliases["dash"] = "dashboard"
        self.aliases["db"] = "dashboard"

    def run(self, txt, repl) -> bool:
        parts = txt.strip().split(None, 1)
        if not parts:
            return True

        cmd_name = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        actual_cmd = self.aliases.get(cmd_name, cmd_name)

        if actual_cmd in self.commands:
            command_obj = self.commands[actual_cmd]
            arg_parts = arg.split() if arg else []
            if "--help" in arg_parts or "-h" in arg_parts:
                print(command_obj.usage())
                return True
            try:
                return command_obj.run(repl, arg)
            except Exception as e:
                print(f"{Theme.BOLD_RED}Error executing {cmd_name}: {e}{Theme.RESET}")
        else:
            print(
                f"{Theme.BOLD_RED}Unknown command: '{cmd_name}'. Type 'help' for available commands.{Theme.RESET}"
            )
        return True


class HybridAutoSuggest(AutoSuggest):
    def __init__(self, repl):
        self.repl = repl

    def get_suggestion(self, buffer, document) -> Suggestion | None:
        text = document.text
        if not text.strip():
            return None

        # 1. Do not suggest anything if the input ends with a space (never guess next argument)
        if text.endswith(" "):
            return None

        # 2. Guess the command name first (only if typing the first word)
        parts = text.lstrip().split()

        if len(parts) == 1:
            word = parts[0].lower()
            # Match against sorted list of primary commands
            matches = [
                cmd
                for cmd in sorted(self.repl.commander.commands.keys())
                if cmd.startswith(word)
            ]
            if matches:
                matched_cmd = matches[0]
                suffix = matched_cmd[len(word) :]
                # Ensure the suggestion does not contain any spaces
                if suffix and " " not in suffix:
                    return Suggestion(suffix)

        # 3. Fallback: Match against REPL session history
        if buffer and buffer.history:
            history_strings = buffer.history.get_strings()
            for hist in reversed(history_strings):
                if hist.startswith(text) and hist != text:
                    suffix = hist[len(text) :]
                    # Ensure the suggestion does not start with or contain any space
                    if suffix and " " not in suffix:
                        return Suggestion(suffix)

        return None


class LibspecCompleter(Completer):
    def __init__(self, repl):
        self.repl = repl

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        parts = text.lstrip().split()
        word = document.get_word_before_cursor(WORD=True)

        is_command_mode = len(parts) <= 1 and not text.endswith(" ")

        if is_command_mode:
            yield from self._get_command_completions(word)
            return

        first_word = parts[0].lower()
        actual_cmd = self.repl.commander.aliases.get(first_word, first_word)

        if actual_cmd == "show":
            yield from self._get_fqn_completions(word)
        elif actual_cmd in (
            "enter",
            "diff",
            "rm-snapshot",
            "rm",
            "restore-snapshot",
            "restore",
        ):
            yield from self._get_snapshot_completions(word)

    def _get_command_completions(self, word):
        commands = sorted(list(self.repl.commander.commands.keys()))
        for cmd in commands:
            if cmd.startswith(word):
                yield Completion(cmd, start_position=-len(word))

    def _get_fqn_completions(self, word):
        meta = {
            c.ref: self.repl.get_summary(c.docstring)
            for c in self.repl.components
            if c.docstring and not getattr(c, "is_dependency", False)
        }
        for fqn in sorted(list(self.repl.fqns)):
            if fqn.startswith(word):
                yield Completion(
                    fqn, start_position=-len(word), display_meta=meta.get(fqn, "")
                )

    def _get_snapshot_completions(self, word):
        if not word:
            print()
            self.repl.commander.commands["list-snapshots"].run(self.repl, "")

        suggestions = self._get_snapshot_suggestions()

        if not word:
            # Guide user with 10 most recent builds when no prefix is entered
            hash_suggestions = [s for s in suggestions if not s.startswith("#")]
            for sug in hash_suggestions[:10]:
                yield Completion(sug, start_position=-len(word))
            idx_suggestions = [s for s in suggestions if s.startswith("#")]
            for sug in idx_suggestions[:10]:
                yield Completion(sug, start_position=-len(word))
        else:
            filtered_suggestions = [s for s in suggestions if s.startswith(word)]
            if not filtered_suggestions:
                print(
                    f"\n{Theme.BOLD_RED}No snapshots match prefix '{word}'. Type 'snapshots' to see all recorded builds.{Theme.RESET}"
                )
            else:
                for sug in filtered_suggestions:
                    yield Completion(sug, start_position=-len(word))

    def _get_snapshot_suggestions(self):
        builds = self.repl._get_chronological_builds()
        suggestions = []
        n = len(builds)
        for idx in range(n):
            suggestions.append(f"#{idx}")
        for b in reversed(builds):
            suggestions.append(b.id[:10])

        # De-duplicate while preserving chronological/reversed order
        seen = set()
        unique_suggestions = []
        for s in suggestions:
            if s not in seen:
                seen.add(s)
                unique_suggestions.append(s)
        return unique_suggestions


class CapturingStdout:
    def __init__(self, original_stdout, print_history):
        self.original_stdout = original_stdout
        self.print_history = print_history

    def write(self, string):
        self.print_history.append(string)
        return self.original_stdout.write(string)

    def flush(self):
        return self.original_stdout.flush()

    def isatty(self):
        if hasattr(self.original_stdout, "isatty"):
            return self.original_stdout.isatty()
        return False

    def __getattr__(self, name):
        return getattr(self.original_stdout, name)


class LibspecRepl:
    def __init__(self):
        # spec.repl.ReplCwdValidation — validate CWD before initialization
        from libspec.util import NotALibspecProjectError, require_libspec_project

        try:
            require_libspec_project()
        except NotALibspecProjectError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

        self.components = []
        self.fqns = set()
        self.active_build = None
        self.active_session_id = None
        self.commander = Commander()
        self._snapshot_registry = {}
        self.load_components()

        # Initialize spec files modification tracking for auto-reloading
        self.last_mtimes = {}
        self._check_watched_files_changed()

    def _validate_ref(self, ref):
        if not isinstance(ref, str) or not ref.strip():
            raise ValueError("Reference must be a non-empty string.")

    def get_summary(self, docstring):
        if not docstring:
            return ""
        for line in docstring.splitlines():
            line = line.strip()
            if line:
                return line[:60] + "..." if len(line) > 60 else line
        return ""

    def _make_snapshot_from_git(self, commit_ref):
        import datetime
        import subprocess
        from libspec.common import Snapshot
        if commit_ref == "HEAD":
            return Snapshot(
                id="HEAD",
                created_at=datetime.datetime.now(),
                master_hash="0" * 64,
                git_commit="HEAD"
            )
        try:
            res = subprocess.run(
                ["git", "show", "-s", "--format=%H%n%cI", commit_ref],
                capture_output=True,
                text=True,
                check=True
            )
            lines = [l.strip() for l in res.stdout.splitlines() if l.strip()]
            sha = lines[0]
            dt = datetime.datetime.fromisoformat(lines[1])
            return Snapshot(
                id=sha,
                created_at=dt,
                master_hash=sha,
                git_commit=sha
            )
        except Exception:
            return None

    def active_snapshot(self):
        return self.active_build

    def _get_chronological_builds(self):
        try:
            import subprocess
            res = subprocess.run(
                ["git", "log", "--reverse", "--format=%H"],
                capture_output=True,
                text=True,
                check=True
            )
            return [line.strip() for line in res.stdout.splitlines() if line.strip()]
        except Exception:
            return []

    def _get_predecessor_build(self, target):
        if target == "HEAD":
            builds = self._get_chronological_builds()
            return builds[-1] if builds else None
        builds = self._get_chronological_builds()
        if target in builds:
            idx = builds.index(target)
            return builds[idx - 1] if idx > 0 else None
        try:
            import subprocess
            res = subprocess.run(["git", "rev-parse", target], capture_output=True, text=True)
            if res.returncode == 0:
                sha = res.stdout.strip()
                if sha in builds:
                    idx = builds.index(sha)
                    return builds[idx - 1] if idx > 0 else None
        except Exception:
            pass
        return None

    def _get_build_desc(self, build):
        if build is None:
            return "<null spec>"
        if build.id == "HEAD":
            return "HEAD (Live Spec)"
        return f"Git Ref: {build.id[:10]}"

    def get_components_for_build(self, build):
        if build is None:
            return []
        if build.id == "HEAD":
            from libspec.util import compile_live_spec

            try:
                comps, _ = compile_live_spec()
                return comps
            except Exception:
                return []
        from libspec.util import compile_git_spec
        try:
            return compile_git_spec(build.id)
        except Exception:
            return []

    def load_components(self):
        try:
            if self.active_build is None:
                from libspec.util import compile_live_spec

                try:
                    self.components, _ = compile_live_spec()
                    self.active_session_id = "HEAD"
                except Exception as e:
                    print(
                        f"{Theme.BOLD_RED}Error compiling live specification: {e}{Theme.RESET}"
                    )
                    self.components = []
                    self.active_session_id = None
            else:
                from libspec.util import compile_git_spec

                try:
                    self.components = compile_git_spec(self.active_build)
                    self.active_session_id = self.active_build
                except Exception as e:
                    print(
                        f"{Theme.BOLD_RED}Error loading specification at '{self.active_build}': {e}{Theme.RESET}"
                    )
                    self.components = []
                    self.active_session_id = None
            self.fqns = {
                c.ref for c in self.components if not getattr(c, "is_dependency", False)
            }
        except Exception as e:
            print(f"{Theme.BOLD_RED}Error loading components: {e}{Theme.RESET}")
            self.components, self.fqns, self.active_session_id = [], set(), None

        if not isinstance(self.components, list):
            raise RuntimeError("Postcondition failed: self.components must be a list.")


    def _print_welcome(self):
        print(Theme.BOLD_CYAN)
        print(r" _ _ _                         ")
        print(r"| (_) |__  ___ _ __   ___  ___ ")
        print(r"| | | '_ \/ __| '_ \ / _ \/ __|")
        print(r"| | | |_) \__ \ |_) |  __/ (__ ")
        print(r"|_|_|_.__/|___/ .__/ \___|\___|")
        print(r"              |_|              ")
        print(Theme.RESET)
        print(
            f"{Theme.BOLD_GREEN}  Backend : Git-Native (Stateless){Theme.RESET}"
        )
        ctx_desc = "Live Workspace" if self.active_session_id == "HEAD" else self.active_session_id
        print(
            f"{Theme.BOLD_GREEN}  Context : {ctx_desc or 'Live Workspace'}{Theme.RESET}"
        )
        print(
            f"{Theme.BOLD_GREEN}  Type 'help' to list available commands. Press Ctrl+C/Ctrl+D to exit.{Theme.RESET}"
        )

    def _get_watch_paths(self):
        paths = []
        spec_dir = os.path.abspath("spec")
        if os.path.exists(spec_dir):
            paths.append(spec_dir)
            for root, _, files in os.walk(spec_dir):
                paths.append(os.path.abspath(root))
                for f in files:
                    paths.append(os.path.abspath(os.path.join(root, f)))
        return paths

    def _check_watched_files_changed(self):
        any_changed = False
        current_paths = self._get_watch_paths()
        # Clean up untracked or deleted paths
        self.last_mtimes = {
            p: t for p, t in self.last_mtimes.items() if p in current_paths
        }

        for path in current_paths:
            if os.path.exists(path):
                current_mtime = os.path.getmtime(path)
                last_mtime = self.last_mtimes.get(path)
                if last_mtime is None:
                    any_changed = True
                    self.last_mtimes[path] = current_mtime
                elif current_mtime != last_mtime:
                    any_changed = True
                    self.last_mtimes[path] = current_mtime
        return any_changed

    def _perform_reload(self, original_stdout=None, force=False):
        if not force and not self._check_watched_files_changed():
            return

        if original_stdout is None:
            import sys

            original_stdout = sys.stdout

        # 1. Clear terminal screen
        original_stdout.write("\033[H\033[2J")

        # 2. Reprint history
        for i in range(len(self._print_history)):
            corrupted = self._print_history[i].replace(" ", "·")
            self._print_history[i] = corrupted
            original_stdout.write(corrupted)

        print(
            f"\n{Theme.BOLD_CYAN}[libspec] Detected change in specification files. Reloading...{Theme.RESET}"
        )
        try:
            self.load_components()
            print(
                f"{Theme.BOLD_GREEN}  Successfully reloaded active context. Current Context: {self.active_session_id or 'Live Workspace'}{Theme.RESET}"
            )
        except Exception as re:
            print(f"{Theme.BOLD_RED}Error during reload: {re}{Theme.RESET}")

    def _schedule_debounced_reload(self):
        if hasattr(self, "_reload_handle") and self._reload_handle:
            self._reload_handle.cancel()
            self._reload_handle = None

        from prompt_toolkit.application import run_in_terminal

        def do_reload():
            self._reload_handle = None
            run_in_terminal(lambda: self._perform_reload(force=True))

        loop = self.session.app.loop
        self._reload_handle = loop.call_later(0.15, do_reload)

    def _on_file_changed(self):
        if self._check_watched_files_changed():
            if hasattr(self, "session") and self.session.app.is_running:
                loop = self.session.app.loop
                loop.call_soon_threadsafe(self._schedule_debounced_reload)
            else:
                self._perform_reload(force=True)


    def start(self):
        self._print_history = []
        original_stdout = sys.stdout
        sys.stdout = CapturingStdout(original_stdout, self._print_history)

        self.watcher = None

        try:
            completer = LibspecCompleter(self)
            auto_suggest = HybridAutoSuggest(self)

            style = Style.from_dict(
                {
                    "auto-suggest": "#666666",
                }
            )

            kb = KeyBindings()

            @kb.add("right")
            def _(event):
                b = event.current_buffer
                if b.suggestion and b.document.is_cursor_at_the_end_of_line:
                    b.insert_text(b.suggestion.text)
                else:
                    b.cursor_right()

            @kb.add("end")
            def _(event):
                b = event.current_buffer
                if b.suggestion:
                    b.insert_text(b.suggestion.text)
                else:
                    b.cursor_to_end_of_line()

            @kb.add("c-f")
            def _(event):
                b = event.current_buffer
                if b.suggestion and b.document.is_cursor_at_the_end_of_line:
                    b.insert_text(b.suggestion.text)
                else:
                    b.cursor_right()

            @kb.add("c-e")
            def _(event):
                b = event.current_buffer
                if b.suggestion:
                    b.insert_text(b.suggestion.text)
                else:
                    b.cursor_to_end_of_line()

            @kb.add("enter")
            def _(event):
                b = event.current_buffer
                if b.suggestion:
                    b.insert_text(b.suggestion.text)
                b.validate_and_handle()

            self.session = PromptSession(
                completer=completer,
                complete_style=CompleteStyle.READLINE_LIKE,
                auto_suggest=auto_suggest,
                style=style,
                key_bindings=kb,
            )

            self._print_welcome()

            # Setup InotifyFileWatcher with manual polling fallback
            use_polling_fallback = True
            watched_paths = self._get_watch_paths()

            try:
                from libspec.watcher import InotifyFileWatcher

                self.watcher = InotifyFileWatcher(watched_paths, self._on_file_changed)
                self.watcher.start()
                use_polling_fallback = False
            except Exception:
                use_polling_fallback = True

            while True:
                try:
                    if use_polling_fallback:
                        if self._check_watched_files_changed():
                            self._perform_reload(original_stdout, force=True)

                    sess_id = (
                        f"({self.active_session_id})"
                        if self.active_session_id
                        else ""
                    )
                    prompt_str = f"{Theme.BOLD_MAGENTA}libspec{sess_id}>{Theme.RESET} "
                    line = self.session.prompt(ANSI(prompt_str)).strip()
                    if not line:
                        continue
                    if self.active_build is None:
                        self.load_components()
                    keep_going = self.commander.run(line, self)
                    if keep_going is False:
                        break
                except KeyboardInterrupt:
                    print("\nUse 'exit' or Ctrl+D to quit.")
                except EOFError:
                    print("\nAn ounce of spec is worth a pound of code.")
                    break
                except Exception as e:
                    print(f"{Theme.BOLD_RED}Unexpected error: {e}{Theme.RESET}")
                    traceback.print_exc()
        finally:
            if self.watcher:
                self.watcher.stop()
                self.watcher = None
            sys.stdout = original_stdout

    # Legacy method delegators for backward compatibility with testing suites
    def cmd_help(self):
        return self.commander.commands["help"].run(self, "")

    def cmd_list(self):
        return self.commander.commands["list"].run(self, "")

    def cmd_show(self, ref):
        return self.commander.commands["show"].run(self, ref)

    def cmd_list_snapshots(self):
        return self.commander.commands["list-snapshots"].run(self, "")

    def cmd_search(self, query):
        return self.commander.commands["search"].run(self, query)

    def cmd_enter(self, snapshot_id):
        return self.commander.commands["enter"].run(self, snapshot_id)

    def cmd_leave(self):
        return self.commander.commands["leave"].run(self, "")

    def cmd_diff(self, arg):
        return self.commander.commands["diff"].run(self, arg)

    def cmd_restore(self, snapshot_id):
        return self.commander.commands["restore-snapshot"].run(self, snapshot_id)

    def _print_show_claims(self, ref):
        try:
            from libspec.util import find_implementations_in_workspace
            claims = find_implementations_in_workspace(ref)
            if claims:
                print(
                    f"{Theme.BOLD_YELLOW}Implementation Claims ({len(claims)}):{Theme.RESET}"
                )
                for cl in claims:
                    print(
                        f"  • {Theme.GREEN}{cl['file']}:{cl['line']}{Theme.RESET}"
                    )
            else:
                print(
                    f"{Theme.YELLOW}No implementation claims found in codebase.{Theme.RESET}"
                )
        except Exception as e:
            print(f"{Theme.BOLD_RED}Error scanning workspace: {e}{Theme.RESET}")

    def find_build_by_id(self, arg):
        try:
            if isinstance(arg, str):
                cleaned = arg.strip()
                if cleaned.startswith("#"):
                    builds = self._get_chronological_builds()
                    n = len(builds)
                    for i, b in enumerate(builds):
                        idx = n - 1 - i
                        self._snapshot_registry[f"#{idx}"] = b
                        self._snapshot_registry[str(idx)] = b

                    if cleaned in self._snapshot_registry:
                        commit_ref = self._snapshot_registry[cleaned]
                        return self._make_snapshot_from_git(commit_ref)
                    return None

                # Otherwise check if it's a valid Git commit ref
                snap = self._make_snapshot_from_git(cleaned)
                if snap:
                    return snap
            return None
        except Exception as e:
            print(f"{Theme.BOLD_RED}Error: {e}{Theme.RESET}")
            return None

    def _resolve_diff_default(self):
        new_comps = self.components
        builds = self._get_chronological_builds()
        latest_snap = self._make_snapshot_from_git(builds[-1]) if builds else None
        active_build = self.active_build or latest_snap

        old_build = self._get_predecessor_build(active_build.id if active_build else "HEAD")
        old_snap = self._make_snapshot_from_git(old_build) if old_build else None
        old_comps = self.get_components_for_build(old_snap)
        return (
            old_comps,
            new_comps,
            self._get_build_desc(old_snap),
            self._get_build_desc(active_build),
        )

    def _resolve_diff_one_arg(self, arg):
        target = self.find_build_by_id(arg)
        if target is None:
            raise ValueError(f"Snapshot '{arg}' not found.")

        old_comps = self.get_components_for_build(target)
        new_comps = self.components

        builds = self._get_chronological_builds()
        latest_snap = self._make_snapshot_from_git(builds[-1]) if builds else None
        active_build = self.active_build or latest_snap
        return (
            old_comps,
            new_comps,
            self._get_build_desc(target),
            self._get_build_desc(active_build),
        )

    def _resolve_diff_two_args(self, arg1, arg2):
        bx = self.find_build_by_id(arg1)
        by = self.find_build_by_id(arg2)
        if bx is None or by is None:
            raise ValueError("One or both snapshots could not be resolved.")

        old_comps = self.get_components_for_build(bx)
        new_comps = self.get_components_for_build(by)
        return old_comps, new_comps, self._get_build_desc(bx), self._get_build_desc(by)

    def _compute_diff(self, old_comps, new_comps):
        old_map = {c.ref: c for c in old_comps}
        new_map = {c.ref: c for c in new_comps}

        added = [
            new_map[r]
            for r in sorted(new_map.keys())
            if r not in old_map and not getattr(new_map[r], "is_dependency", False)
        ]
        removed = [
            old_map[r]
            for r in sorted(old_map.keys())
            if r not in new_map and not getattr(old_map[r], "is_dependency", False)
        ]
        changed = [
            (old_map[r], new_map[r])
            for r in sorted(new_map.keys())
            if r in old_map
            and old_map[r].hash != new_map[r].hash
            and not getattr(new_map[r], "is_dependency", False)
        ]

        return added, removed, changed

    def _resolve_diff_by_parts(self, parts):
        if len(parts) == 0:
            return self._resolve_diff_default()
        elif len(parts) == 1:
            return self._resolve_diff_one_arg(parts[0])
        elif len(parts) == 2:
            return self._resolve_diff_two_args(parts[0], parts[1])
        raise ValueError("Too many arguments for diff command.")

    def _resolve_diff_snapshots(self, parts):
        import datetime

        from libspec.store import Snapshot

        HEAD_SNAPSHOT = Snapshot(
            id="HEAD",
            created_at=datetime.datetime.now(),
            master_hash="0000000000000000000000000000000000000000000000000000000000000000",
            git_commit="HEAD",
        )
        if len(parts) == 0:
            if self.active_build is None:
                builds = self._get_chronological_builds()
                old_snap = self._make_snapshot_from_git(builds[-1]) if builds else None
                new_snap = HEAD_SNAPSHOT
            else:
                new_snap = self.active_build
                pred_ref = self._get_predecessor_build(new_snap.id)
                old_snap = self._make_snapshot_from_git(pred_ref) if pred_ref else None
            return old_snap, new_snap
        elif len(parts) == 1:
            if parts[0].startswith("@"):
                val_str = parts[0][1:]
                try:
                    n = int(val_str)
                except ValueError as e:
                    raise ValueError(
                        f"Invalid successor diff syntax '{parts[0]}': {e}"
                    ) from None
                old_snap = self.find_build_by_id(f"#{n}")
                if old_snap is None:
                    raise ValueError(
                        f"Could not resolve snapshots for successor diff target '{parts[0]}'."
                    )
                if n == 0:
                    new_snap = HEAD_SNAPSHOT
                else:
                    new_snap = self.find_build_by_id(f"#{n - 1}")
                    if new_snap is None:
                        raise ValueError(
                            f"Could not resolve snapshots for successor diff target '{parts[0]}'."
                        )
                return old_snap, new_snap
            old_snap = self.find_build_by_id(parts[0])
            if old_snap is None:
                raise ValueError(f"Snapshot '{parts[0]}' not found.")
            builds = self._get_chronological_builds()
            new_snap = self._make_snapshot_from_git(builds[-1]) if builds else None
            return old_snap, new_snap
        elif len(parts) == 2:
            old_snap = self.find_build_by_id(parts[0])
            new_snap = self.find_build_by_id(parts[1])
            if (
                old_snap is None
                or old_snap is False
                or new_snap is None
                or new_snap is False
            ):
                raise ValueError("One or both snapshots could not be resolved.")
            return old_snap, new_snap
        raise ValueError("Too many arguments for diff command.")
