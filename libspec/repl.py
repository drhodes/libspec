import sys
import os
import traceback
import difflib
from libspec.store import (
    get_store,
    SpecStoreNotFoundError,
    Component
)

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.shortcuts import CompleteStyle


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


class HelpCommand(ReplCommand):
    def name(self): return "help"
    def desc(self): return "Show this help message."
    def run(self, repl, arg):
        print("\n\033[1;33mAvailable Commands:\033[0m")
        for name in sorted(repl.commander.commands.keys()):
            cmd = repl.commander.commands[name]
            print(f"  \033[1;32m{name:<15}\033[0m {cmd.desc()}")
        print()
        return True


class ListCommand(ReplCommand):
    def name(self): return "list"
    def desc(self): return "List all specification components."
    def run(self, repl, arg):
        repl.load_components()
        if not repl.components:
            print("\033[93mNo components found in the active SpecStore.\033[0m")
            return True
        ctx_name = f"Snapshot ({repl.active_session_id[:10]})" if repl.active_session_id else "Latest Snapshot"
        print(f"\n\033[1;33m{ctx_name} Components ({len(repl.components)} total):\033[0m")
        for comp in repl.components:
            comp_type = "Template" if comp.is_template else "Component"
            print(f"  • \033[1;36m{comp.ref}\033[0m [\033[32m{comp_type}\033[0m]")
        print()
        return True


class ShowCommand(ReplCommand):
    def name(self): return "show"
    def desc(self): return "Show full details of a specific component."
    def run(self, repl, arg):
        repl._validate_ref(arg)
        comp = next((c for c in repl.components if c.ref == arg), None)
        if comp is None:
            self._handle_missing(repl, arg)
            return True
            
        print("\033[1;36m" + "="*60 + "\033[0m")
        print(f"\033[1;33mReference:\033[0m   \033[1;32m{comp.ref}\033[0m")
        print(f"\033[1;33mType:\033[0m        {'Template Requirement' if comp.is_template else 'Requirement'}")
        print(f"\033[1;33mHash:\033[0m        {comp.hash}")
        if comp.inherits:
            print(f"\033[1;33mInherits:\033[0m    " + ", ".join(comp.inherits))
        print(f"\033[1;33mDocstring:\033[0m\n{'-' * 60}\n{comp.docstring}\n{'-' * 60}")
        repl._print_show_claims(arg)
        print("\033[1;36m" + "="*60 + "\033[0m\n")
        return True

    def _handle_missing(self, repl, ref):
        print(f"\033[91mComponent '{ref}' not found in active snapshot context.\033[0m")
        matches = [f for f in repl.fqns if ref.lower() in f.lower()]
        if matches:
            print("\033[1;33mDid you mean:\033[0m")
            for m in matches[:5]:
                print(f"  • {m}")


class SnapshotsCommand(ReplCommand):
    def name(self): return "snapshots"
    def desc(self): return "List chronological build/snapshot history."
    def run(self, repl, arg):
        print("\033[1;33m\nChronological Snapshot History:\033[0m")
        print("-" * 60)
        try:
            snapshots = repl.store.list_snapshots()
            repl._snapshot_registry = {}
            if not snapshots:
                print("No snapshots recorded yet.")
            else:
                active_snap = repl.active_snapshot()
                n = len(snapshots)
                w = len(str(n - 1))
                
                snapshot_comps = []
                for s in snapshots:
                    try:
                        comps = repl.store.get_components_for_snapshot(s)
                    except Exception:
                        comps = []
                    snapshot_comps.append(comps)

                for i, s in enumerate(snapshots):
                    idx = n - 1 - i
                    repl._snapshot_registry[str(idx)] = s
                    repl._snapshot_registry[f"#{idx}"] = s
                    git_info = f" (Git: {s.git_commit[:7]})" if s.git_commit else ""
                    is_active = (
                        active_snap
                        and active_snap.id == s.id
                        and active_snap.created_at.replace(tzinfo=None) == s.created_at.replace(tzinfo=None)
                    )
                    active_marker = " \033[1;31m(ACTIVE)\033[0m" if is_active else ""
                    
                    comps = snapshot_comps[i]
                    size_bytes = sum(
                        len(c.ref.encode("utf-8")) +
                        len(c.docstring.encode("utf-8")) +
                        sum(len(x.encode("utf-8")) for x in c.inherits) +
                        64
                        for c in comps
                    )
                    
                    if i == 0:
                        new_count = len(comps)
                    else:
                        prev_refs = {c.ref for c in snapshot_comps[i-1]}
                        current_refs = {c.ref for c in comps}
                        new_count = len(current_refs - prev_refs)
                        
                    print(f"  #{idx:>{w}} • \033[1;36m{s.created_at.isoformat()}\033[0m | ID: \033[32m{s.id}\033[0m | \033[1;35m{new_count}\033[0m new | \033[1;35m{size_bytes}\033[0m bytes{git_info}{active_marker}")
        except Exception as e:
            print(f"Failed to query snapshots: {e}")
        print("-" * 60 + "\n")
        return True


class SearchCommand(ReplCommand):
    def name(self): return "search"
    def desc(self): return "Search components and docstrings."
    def run(self, repl, arg):
        if not isinstance(arg, str) or not arg.strip():
            raise ValueError("Query must be a non-empty string.")
        matches = [c for c in repl.components if arg.lower() in c.ref.lower() or arg.lower() in c.docstring.lower()]
        if not matches:
            print(f"\033[93mNo components found matching '{arg}'.\033[0m")
            return True
            
        print(f"\n\033[1;33mSearch Results for '{arg}' ({len(matches)} matches):\033[0m")
        for comp in matches:
            comp_type = "Template" if comp.is_template else "Component"
            snippet = comp.docstring.split("\n")[0][:60]
            if len(comp.docstring.split("\n")[0]) > 60:
                snippet += "..."
            print(f"  • \033[1;36m{comp.ref}\033[0m [\033[32m{comp_type}\033[0m] - {snippet}")
        return True


class EnterCommand(ReplCommand):
    def name(self): return "enter"
    def desc(self): return "Scope REPL to a historical snapshot."
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
            print(f"\033[1;32mEntered snapshot context: {repl.active_session_id}\033[0m")
        return True
class LeaveCommand(ReplCommand):
    def name(self): return "leave"
    def desc(self): return "Restore context to latest snapshot."
    def run(self, repl, arg):
        if repl.active_build is None:
            print("Already in the latest snapshot context.")
            return True
        repl.active_build = None
        repl.load_components()
        print("\033[1;32mReturned to latest snapshot context.\033[0m")
        return True


class ExitCommand(ReplCommand):
    def name(self): return "exit"
    def desc(self): return "Exit the REPL session."
    def run(self, repl, arg):
        print("An ounce of spec is worth a pound of code.")
        return False


class DiffCommand(ReplCommand):
    def name(self): return "diff"
    def desc(self): return "Color-coded overview of snapshot differences."
    def run(self, repl, arg):
        parts = arg.split() if arg else []
        verbose = "-v" in parts
        if verbose:
            parts.remove("-v")
            
        try:
            old_comps, new_comps, old_desc, new_desc = repl._resolve_diff_by_parts(parts)
            added, removed, changed = repl._compute_diff(old_comps, new_comps)
            self._print_report(old_desc, new_desc, added, removed, changed, verbose)
        except Exception as e:
            print(f"\033[91mError executing diff: {e}\033[0m")
        return True

    def _print_report(self, old_desc, new_desc, added, removed, changed, verbose):
        print("\n\033[1;33mSpecification Diff Overview:\033[0m")
        print(f"  Comparing: \033[36m{old_desc}\033[0m -> \033[32m{new_desc}\033[0m")
        print("-" * 60)
        
        if not added and not removed and not changed:
            print("  No changes detected.")
            print("-" * 60 + "\n")
            return
            
        self._print_added(added, verbose)
        self._print_removed(removed)
        self._print_changed(changed, verbose)
        print("-" * 60 + "\n")

    def _print_added(self, added, verbose):
        if not added:
            return
        print("  \033[1;32m[ADDED]\033[0m Components:")
        for c in added:
            comp_type = "Template" if c.is_template else "Component"
            print(f"    • {c.ref} [{comp_type}]")
            if verbose and c.docstring:
                print(f"      \033[1;30mDocstring:\033[0m\n      {'-' * 56}")
                for line in c.docstring.splitlines():
                    print(f"      {line}")
                print("      " + "-" * 56)
        print()

    def _print_removed(self, removed):
        if not removed:
            return
        print("  \033[1;31m[REMOVED]\033[0m Components:")
        for c in removed:
            comp_type = "Template" if c.is_template else "Component"
            print(f"    • {c.ref} [{comp_type}]")
        print()

    def _print_changed(self, changed, verbose):
        if not changed:
            return
        print("  \033[1;34m[CHANGED]\033[0m Components:")
        for old_c, new_c in changed:
            comp_type = "Template" if new_c.is_template else "Component"
            print(f"    • {new_c.ref} [{comp_type}]")
            if verbose:
                self._print_docstring_diff(old_c, new_c)
        print()

    def _print_docstring_diff(self, old_c, new_c):
        old_lines = (old_c.docstring or "").splitlines()
        new_lines = (new_c.docstring or "").splitlines()
        diff = list(difflib.unified_diff(old_lines, new_lines, fromfile="old/docstring", tofile="new/docstring", lineterm=""))
        if diff:
            print(f"      \033[1;30mDocstring Diff:\033[0m\n      {'-' * 56}")
            for line in diff:
                if line.startswith("+") and not line.startswith("+++"):
                    print(f"      \033[32m{line}\033[0m")
                elif line.startswith("-") and not line.startswith("---"):
                    print(f"      \033[31m{line}\033[0m")
                elif line.startswith("@@"):
                    print(f"      \033[36m{line}\033[0m")
                else:
                    print(f"      {line}")
            print("      " + "-" * 56)


class RmSnapshotCommand(ReplCommand):
    def name(self): return "rm-snapshot"
    def desc(self): return "Permanently delete a historical snapshot."
    def run(self, repl, arg):
        if not arg:
            raise ValueError("Snapshot ID or hash required.")
            
        target = repl.find_build_by_id(arg)
        if target is None:
            return True
            
        # Safety Check 1: Refuse to delete the LATEST snapshot
        latest = repl.store.current_snapshot()
        if latest and latest.id == target.id:
            print(f"\033[91mError: Cannot delete snapshot '{target.id}' because it is the latest recorded build.\033[0m")
            return True

        # Safety Check 2: Refuse to delete the currently active/entered snapshot
        if repl.active_session_id == target.id:
            print(f"\033[91mError: Cannot delete snapshot '{target.id}' because it is the currently active/entered context.\033[0m")
            print("Leave or enter a different snapshot first.")
            return True

        # Confirmation Prompt with detailed verification card
        git_info = f" {target.git_commit[:7]}" if target.git_commit else " <none>"
        print(f"\033[93mWARNING: You are about to permanently delete the following snapshot:\033[0m")
        print(f"\033[93m" + "-" * 60 + "\033[0m")
        print(f"  • Target Reference : \033[1;36m{arg.strip()}\033[0m")
        print(f"  • Resolved Hash ID : \033[32m{target.id}\033[0m")
        print(f"  • Date Created     : {target.created_at.isoformat()}")
        print(f"  • Associated Git   :{git_info}")
        print(f"\033[93m" + "-" * 60 + "\033[0m")
        try:
            confirm = input(f"\033[1;33mAre you sure you want to proceed? (y/N):\033[0m ").strip().lower()
        except EOFError:
            print("\nAborted.")
            return True
            
        if confirm not in ("y", "yes"):
            print("Aborted.")
            return True
            
        try:
            repl.store.delete_snapshot(target)
            print(f"\033[1;32mSnapshot '{target.id}' successfully deleted.\033[0m")
            repl.load_components()
        except Exception as e:
            print(f"\033[91mFailed to delete snapshot: {e}\033[0m")
            
        return True


class RestoreSnapshotCommand(ReplCommand):
    def name(self): return "restore-snapshot"
    def desc(self): return "Restore a previously deleted/tombstoned historical snapshot."
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
            
        print(f"\033[92mRestoring snapshot:\033[0m")
        print(f"  • Hash ID      : \033[32m{target.id}\033[0m")
        print(f"  • Date Created : {target.created_at.isoformat()}")
        
        try:
            repl.store.restore_snapshot(target)
            print(f"\033[1;32mSnapshot '{target.id}' successfully restored.\033[0m")
            repl.load_components()
        except Exception as e:
            print(f"\033[91mFailed to restore snapshot: {e}\033[0m")
            
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
            SnapshotsCommand(),
            SearchCommand(),
            EnterCommand(),
            LeaveCommand(),
            DiffCommand(),
            RmSnapshotCommand(),
            RestoreSnapshotCommand(),
            ExitCommand()
        ]
        for cmd in cmd_list:
            self.commands[cmd.name()] = cmd
            
        self.aliases["h"] = "help"
        self.aliases["?"] = "help"
        self.aliases["components"] = "list"
        self.aliases["quit"] = "exit"
        self.aliases["q"] = "exit"
        self.aliases["rm"] = "rm-snapshot"
        self.aliases["restore"] = "restore-snapshot"

    def run(self, txt, repl) -> bool:
        parts = txt.strip().split(None, 1)
        if not parts:
            return True
            
        cmd_name = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""
        
        actual_cmd = self.aliases.get(cmd_name, cmd_name)
        
        if actual_cmd in self.commands:
            try:
                return self.commands[actual_cmd].run(repl, arg)
            except Exception as e:
                print(f"\033[91mError executing {cmd_name}: {e}\033[0m")
        else:
            print(f"\033[91mUnknown command: '{cmd_name}'. Type 'help' for available commands.\033[0m")
        return True


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
        elif actual_cmd in ("enter", "diff", "rm-snapshot", "rm", "restore-snapshot", "restore"):
            yield from self._get_snapshot_completions(word)

    def _get_command_completions(self, word):
        commands = sorted(list(self.repl.commander.commands.keys()) + list(self.repl.commander.aliases.keys()))
        for cmd in commands:
            if cmd.startswith(word):
                yield Completion(cmd, start_position=-len(word))

    def _get_fqn_completions(self, word):
        meta = {c.ref: self.repl.get_summary(c.docstring) for c in self.repl.components if c.docstring}
        for fqn in sorted(list(self.repl.fqns)):
            if fqn.startswith(word):
                yield Completion(fqn, start_position=-len(word), display_meta=meta.get(fqn, ""))

    def _get_snapshot_completions(self, word):
        if not word:
            print()
            self.repl.commander.commands["snapshots"].run(self.repl, "")
            
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
                print(f"\n\033[91mNo snapshots match prefix '{word}'. Type 'snapshots' to see all recorded builds.\033[0m")
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



class LibspecRepl:
    def __init__(self):
        self.store = get_store()
        self.components = []
        self.fqns = set()
        self.active_build = None
        self.active_session_id = None
        self.commander = Commander()
        self._snapshot_registry = {}
        self.load_components()

        # Initialize storage file modification tracking for auto-reloading
        self.last_mtime = None
        store_path = self._store_path()
        if store_path and os.path.exists(store_path):
            self.last_mtime = os.path.getmtime(store_path)

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

    def active_snapshot(self):
        return self.active_build or self.store.current_snapshot()

    def _get_chronological_builds(self):
        try:
            return self.store.list_snapshots()
        except Exception:
            return []

    def _get_predecessor_build(self, target):
        builds = self._get_chronological_builds()
        if target in builds:
            idx = builds.index(target)
            return builds[idx - 1] if idx > 0 else None
        return None

    def _get_build_desc(self, build):
        if build is None:
            return "<null spec>"
        return f"Build {build.id[:10]}"

    def get_components_for_build(self, build):
        if build is None:
            return []
        try:
            return self.store.get_components_for_snapshot(build)
        except Exception:
            return []

    def load_components(self):
        try:
            build = self.active_build or self.store.current_snapshot()
            if build:
                self.components = self.store.get_components_for_snapshot(build)
                self.active_session_id = build.id
            else:
                self.components = self.store.list_components()
                self.active_session_id = None
            self.fqns = {c.ref for c in self.components}
        except Exception as e:
            print(f"\033[91mError loading components: {e}\033[0m")
            self.components, self.fqns, self.active_session_id = [], set(), None
            
        if not isinstance(self.components, list):
            raise RuntimeError("Postcondition failed: self.components must be a list.")

    def _print_welcome(self):
        print("\033[1;36m")
        print(r" _ _ _                         ")
        print(r"| (_) |__  ___ _ __   ___  ___ ")
        print(r"| | | '_ \/ __| '_ \ / _ \/ __|")
        print(r"| | | |_) \__ \ |_) |  __/ (__ ")
        print(r"|_|_|_.__/|___/ .__/ \___|\___|")
        print(r"              |_|              ")
        print("\033[0m")
        print(f"\033[1;32m  Backend : {self.store.__class__.__name__}  {self._store_path()}\033[0m")
        print(f"\033[1;32m  Snapshot: {self.active_session_id or '<none>'}\033[0m")
        print("\033[1;32m  Type 'help' to list available commands. Press Ctrl+C/Ctrl+D to exit.\033[0m")

    def _store_path(self):
        if hasattr(self.store, "filepath"):
            return self.store.filepath
        if hasattr(self.store, "db_path"):
            return self.store.db_path
        if hasattr(self.store, "xml_path"):
            return self.store.xml_path
        return ""

    def start(self):
        completer = LibspecCompleter(self)
        session = PromptSession(completer=completer, complete_style=CompleteStyle.READLINE_LIKE)
        
        self._print_welcome()

        store_path = self._store_path()
        if self.last_mtime is None and store_path and os.path.exists(store_path):
            self.last_mtime = os.path.getmtime(store_path)
        
        while True:
            try:
                # Check for external file modifications right before prompting
                if store_path and os.path.exists(store_path):
                    current_mtime = os.path.getmtime(store_path)
                    if self.last_mtime is not None and current_mtime != self.last_mtime:
                        print("\n\033[1;36m[libspec] Detected change in storage file. Reloading...\033[0m")
                        try:
                            if hasattr(self.store, "_replay"):
                                self.store._replay()
                            self.load_components()
                            print(f"\033[1;32m  Successfully reloaded active context. Current Snapshot: {self.active_session_id or '<none>'}\033[0m")
                        except Exception as re:
                            print(f"\033[91mError during reload: {re}\033[0m")
                        self.last_mtime = current_mtime

                sess_id = f"({self.active_session_id[:10]})" if self.active_session_id else ""
                prompt_str = f"\033[1;35mlibspec{sess_id}>\033[0m "
                line = session.prompt(ANSI(prompt_str)).strip()
                if not line:
                    continue
                keep_going = self.commander.run(line, self)
                if keep_going is False:
                    break
            except KeyboardInterrupt:
                print("\nUse 'exit' or Ctrl+D to quit.")
            except EOFError:
                print("\nAn ounce of spec is worth a pound of code.")
                break
            except Exception as e:
                print(f"\033[91mUnexpected error: {e}\033[0m")
                traceback.print_exc()

    # Legacy method delegators for backward compatibility with testing suites
    def cmd_help(self):
        return self.commander.commands["help"].run(self, "")

    def cmd_list(self):
        return self.commander.commands["list"].run(self, "")

    def cmd_show(self, ref):
        return self.commander.commands["show"].run(self, ref)

    def cmd_snapshots(self):
        return self.commander.commands["snapshots"].run(self, "")

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
            build = self.active_build or self.store.current_snapshot()
            if build:
                claims = [c for c in self.store.list_implemented(build) if c.ref == ref]
                self._render_claims(claims)
        except Exception:
            pass

    def _render_claims(self, claims):
        if claims:
            print(f"\033[1;33mImplementation Claims ({len(claims)}):\033[0m")
            for cl in claims:
                print(f"  • \033[32m{cl.file}:{cl.line}\033[0m (Session: {cl.session_id})")
        else:
            print("\033[93mNo implementation claims recorded for this component.\033[0m")

    def find_build_by_id(self, arg):
        try:
            if isinstance(arg, str):
                cleaned = arg.strip()
                if cleaned.startswith("#"):
                    # If registry is empty, populate it as a smart/friendly fallback
                    if not self._snapshot_registry:
                        snapshots = self._get_chronological_builds()
                        n = len(snapshots)
                        for i, s in enumerate(snapshots):
                            idx = n - 1 - i
                            self._snapshot_registry[f"#{idx}"] = s
                            self._snapshot_registry[str(idx)] = s
                    
                    if cleaned in self._snapshot_registry:
                        return self._snapshot_registry[cleaned]
            return self.store.get_snapshot(arg)
        except Exception as e:
            print(f"\033[91mError: {e}\033[0m")
            return None

    def _resolve_diff_default(self):
        new_comps = self.components
        active_build = self.active_build or self.store.current_snapshot()
        
        old_build = self._get_predecessor_build(active_build)
        old_comps = self.get_components_for_build(old_build)
        return old_comps, new_comps, self._get_build_desc(old_build), self._get_build_desc(active_build)

    def _resolve_diff_one_arg(self, arg):
        target = self.find_build_by_id(arg)
        if target is None:
            raise ValueError(f"Snapshot '{arg}' not found.")
            
        old_comps = self.get_components_for_build(target)
        new_comps = self.components
        
        active_build = self.active_build or self.store.current_snapshot()
        return old_comps, new_comps, self._get_build_desc(target), self._get_build_desc(active_build)

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
        
        added = [new_map[r] for r in sorted(new_map.keys()) if r not in old_map]
        removed = [old_map[r] for r in sorted(old_map.keys()) if r not in new_map]
        changed = [(old_map[r], new_map[r]) for r in sorted(new_map.keys()) if r in old_map and old_map[r].hash != new_map[r].hash]
        
        return added, removed, changed

    def _resolve_diff_by_parts(self, parts):
        if len(parts) == 0:
            return self._resolve_diff_default()
        elif len(parts) == 1:
            return self._resolve_diff_one_arg(parts[0])
        elif len(parts) == 2:
            return self._resolve_diff_two_args(parts[0], parts[1])
        raise ValueError("Too many arguments for diff command.")
