import sys
import os
import traceback
import difflib
from libspec.store import (
    get_store,
    SpecStoreNotFoundError,
    DBBuild,
    DBSpec,
    DBEdge,
    DBImplemented,
    SQLiteSpecStore,
    XmlSpecStore,
    Component
)

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.shortcuts import CompleteStyle


class LibspecCompleter(Completer):
    def __init__(self, commands, fqns, meta):
        self.commands = commands
        self.fqns = sorted(list(fqns))
        self.meta = meta

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        parts = text.lstrip().split()
        is_fqn = len(parts) > 1 or (len(parts) == 1 and text.endswith(" "))
        word = document.get_word_before_cursor(WORD=True)
        
        if is_fqn:
            for fqn in self.fqns:
                if fqn.startswith(word):
                    yield Completion(fqn, start_position=-len(word), display_meta=self.meta.get(fqn, ""))
        else:
            for cmd in self.commands:
                if cmd.startswith(word):
                    yield Completion(cmd, start_position=-len(word))


class LibspecRepl:
    def __init__(self):
        self.store = get_store()
        self.components = []
        self.fqns = set()
        self.active_build = None
        self.active_session_id = None
        self.load_components()

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

    def _get_chronological_builds(self):
        if isinstance(self.store, SQLiteSpecStore):
            return list(DBBuild.select().order_by(DBBuild.created_at.asc()))
        elif isinstance(self.store, XmlSpecStore) and self.store.is_dir:
            import glob
            files = glob.glob(os.path.join(self.store.directory, "spec-*.xml"))
            files.sort(key=os.path.getmtime)
            return files
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
        if isinstance(self.store, SQLiteSpecStore):
            return f"Build {build.session_id[:10]}"
        return os.path.basename(build)

    def _load_sqlite_components(self, build):
        if build is None:
            return []
        specs = DBSpec.select().where(DBSpec.build == build)
        comps = []
        for spec in specs:
            edges = DBEdge.select().where(DBEdge.build == build, DBEdge.child_ref == spec.ref).order_by(DBEdge.position.asc())
            inherits = [edge.parent_ref for edge in edges]
            comps.append(Component(
                 ref=spec.ref,
                 docstring=spec.docstring,
                 is_template=spec.is_template,
                 inherits=inherits,
                 hash=spec.hash
            ))
        return comps

    def _load_xml_components(self, filepath):
        if filepath is None:
            return self.store.list_components()
        store = XmlSpecStore(filepath)
        return store.list_components()

    def _get_xml_session_id(self):
        if self.active_build is None:
            return None
        base = os.path.basename(self.active_build)
        return base[5:-4] if base.startswith("spec-") and base.endswith(".xml") else base

    def load_components(self):
        try:
            if isinstance(self.store, SQLiteSpecStore):
                build = self.active_build or self.store._get_latest_build()
                self.components = self._load_sqlite_components(build)
                self.active_session_id = build.session_id if build else None
            elif isinstance(self.store, XmlSpecStore):
                self.components = self._load_xml_components(self.active_build)
                self.active_session_id = self._get_xml_session_id()
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
        print(r" _ _ _                                          _ ")
        print(r"| (_) |__  ___ _ __   ___  ___   _ __ ___ _ __ | |")
        print(r"| | | '_ \/ __| '_ \ / _ \/ __| | '__/ _ \ '_ \| |")
        print(r"| | | |_) \__ \ |_) |  __/ (__  | | |  __/ |_) | |")
        print(r"|_|_|_.__/|___/ .__/ \___|\___| |_|  \___| .__/|_|")
        print(r"              |_|                        |_|      ")
        print("\033[0m")
        print(f"\033[1;32m  Active Store: {self.store.__class__.__name__}\033[0m")
        if hasattr(self.store, "db_path"):
            print(f"\033[1;32m  Database Path: {self.store.db_path}\033[0m")
        elif hasattr(self.store, "xml_path"):
            print(f"\033[1;32m  XML Path: {self.store.xml_path}\033[0m")
        print("\033[1;32m  Type 'help' to list available commands. Press Ctrl+C/Ctrl+D to exit.\033[0m")

    def _process_repl_line(self, line, completer):
        parts = line.split(None, 1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""
        
        if cmd in ("exit", "quit", "q"):
            print("Goodbye!")
            return False
        self._dispatch_command(cmd, arg, completer)
        return True

    def _dispatch_command(self, cmd, arg, completer):
        if cmd in ("help", "h", "?"):
            self.cmd_help()
        elif cmd in ("list", "components"):
            self.cmd_list()
        elif cmd == "show":
            self.cmd_show(arg)
        elif cmd == "snapshots":
            self.cmd_snapshots()
        elif cmd == "search":
            self.cmd_search(arg)
        elif cmd in ("enter", "leave"):
            self._handle_navigation(cmd, arg, completer)
        elif cmd == "diff":
            self.cmd_diff(arg)
        else:
            print(f"\033[91mUnknown command: '{cmd}'. Type 'help'.\033[0m")

    def _handle_navigation(self, cmd, arg, completer):
        if cmd == "enter":
            self.cmd_enter(arg)
        else:
            self.cmd_leave()
        completer.fqns = sorted(list(self.fqns))
        completer.meta = {c.ref: self.get_summary(c.docstring) for c in self.components if c.docstring}

    def start(self):
        commands = ["help", "list", "components", "show", "snapshots", "search", "enter", "leave", "diff", "exit", "quit", "h", "q"]
        meta = {c.ref: self.get_summary(c.docstring) for c in self.components if c.docstring}
        completer = LibspecCompleter(commands, self.fqns, meta)
        session = PromptSession(completer=completer, complete_style=CompleteStyle.READLINE_LIKE)
        
        self._print_welcome()
        
        while True:
            try:
                sess_id = f"({self.active_session_id[:10]})" if self.active_session_id else ""
                prompt_str = f"\033[1;35mlibspec{sess_id}>\033[0m "
                line = session.prompt(ANSI(prompt_str)).strip()
                if not line:
                    continue
                if not self._process_repl_line(line, completer):
                    break
            except KeyboardInterrupt:
                print("\nUse 'exit' or Ctrl+D to quit.")
            except EOFError:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"\033[91mUnexpected error: {e}\033[0m")
                traceback.print_exc()

    def cmd_help(self):
        print("\n\033[1;33mAvailable Commands:\033[0m")
        print("  \033[1;32mhelp\033[0m                          Show this help message.")
        print("  \033[1;32mlist\033[0m | \033[1;32mcomponents\033[0m             List all specification components.")
        print("  \033[1;32mshow <FQN>\033[0m                    Show full details of a specific component.")
        print("  \033[1;32msnapshots\033[0m                     List chronological build/snapshot history.")
        print("  \033[1;32msearch <query>\033[0m                Search components and docstrings.")
        print("  \033[1;32mdiff [snapshot_a] [snapshot_b] [-v]\033[0m Color-coded overview of snapshot differences.")
        print("  \033[1;32menter <snapshot_id>\033[0m          Scope REPL to a historical snapshot.")
        print("  \033[1;32mleave\033[0m                         Restore context to latest snapshot.")
        print("  \033[1;32mexit\033[0m | \033[1;32mquit\033[0m                   Exit the REPL session.\n")

    def cmd_list(self):
        self.load_components()
        if not self.components:
            print("\033[93mNo components found in the active SpecStore.\033[0m")
            return
        ctx_name = f"Snapshot ({self.active_session_id[:10]})" if self.active_session_id else "Latest Snapshot"
        print(f"\n\033[1;33m{ctx_name} Components ({len(self.components)} total):\033[0m")
        for comp in self.components:
            comp_type = "Template" if comp.is_template else "Component"
            print(f"  • \033[1;36m{comp.ref}\033[0m [\033[32m{comp_type}\033[0m]")
        print()

    def _print_show_claims(self, ref):
        try:
            if isinstance(self.store, SQLiteSpecStore):
                build = self.active_build or self.store._get_latest_build()
                if build:
                    claims = DBImplemented.select().where(DBImplemented.build == build, DBImplemented.ref == ref)
                    self._render_claims(claims)
            elif isinstance(self.store, XmlSpecStore):
                store = XmlSpecStore(self.active_build) if self.active_build else self.store
                snap = store.current_snapshot()
                if snap:
                    claims = [c for c in store.list_implemented(snap) if c.ref == ref]
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

    def cmd_show(self, ref):
        self._validate_ref(ref)
        comp = next((c for c in self.components if c.ref == ref), None)
        if comp is None:
            self._handle_missing_show_ref(ref)
            return
            
        print("\033[1;36m" + "="*60 + "\033[0m")
        print(f"\033[1;33mReference:\033[0m   \033[1;32m{comp.ref}\033[0m")
        print(f"\033[1;33mType:\033[0m        {'Template Requirement' if comp.is_template else 'Requirement'}")
        print(f"\033[1;33mHash:\033[0m        {comp.hash}")
        if comp.inherits:
            print(f"\033[1;33mInherits:\033[0m    " + ", ".join(comp.inherits))
        print(f"\033[1;33mDocstring:\033[0m\n{'-' * 60}\n{comp.docstring}\n{'-' * 60}")
        self._print_show_claims(ref)
        print("\033[1;36m" + "="*60 + "\033[0m\n")

    def _handle_missing_show_ref(self, ref):
        print(f"\033[91mComponent '{ref}' not found in active snapshot context.\033[0m")
        matches = [f for f in self.fqns if ref.lower() in f.lower()]
        if matches:
            print("\033[1;33mDid you mean:\033[0m")
            for m in matches[:5]:
                print(f"  • {m}")

    def _print_sqlite_snapshots(self):
        try:
            builds = DBBuild.select().order_by(DBBuild.created_at.asc())
            if not builds:
                print("No snapshots recorded in database yet.")
            for b in builds:
                git_info = f" (Git: {b.git_commit[:7]})" if b.git_commit else ""
                active_marker = " \033[1;31m(ACTIVE)\033[0m" if self.active_session_id == b.session_id else ""
                print(f"  • \033[1;36m{b.created_at.isoformat()}\033[0m | ID: \033[32m{b.session_id}\033[0m{git_info}{active_marker}")
        except Exception as e:
            print(f"Failed to query database builds: {e}")

    def _print_xml_snapshots(self):
        files = self._get_chronological_builds()
        if not files:
            print("No XML snapshots found in directory.")
        for f in files:
            mtime = os.path.getmtime(f)
            from datetime import datetime, timezone
            dt = datetime.fromtimestamp(mtime, timezone.utc)
            active_marker = " \033[1;31m(ACTIVE)\033[0m" if (self.active_build == f or (self.active_build is None and f == files[-1])) else ""
            print(f"  • \033[1;36m{dt.isoformat()}\033[0m | File: \033[32m{os.path.basename(f)}\033[0m{active_marker}")

    def cmd_snapshots(self):
        print("\033[1;33m\nChronological Snapshot History:\033[0m")
        print("-" * 60)
        if isinstance(self.store, SQLiteSpecStore):
            self._print_sqlite_snapshots()
        elif isinstance(self.store, XmlSpecStore):
            if self.store.is_dir:
                self._print_xml_snapshots()
            else:
                print(f"Single XML file mode: {self.store.xml_path}")
        print("-" * 60 + "\n")

    def cmd_search(self, query):
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Query must be a non-empty string.")
        matches = [c for c in self.components if query.lower() in c.ref.lower() or query.lower() in c.docstring.lower()]
        if not matches:
            print(f"\033[93mNo components found matching '{query}'.\033[0m")
            return
            
        print(f"\n\033[1;33mSearch Results for '{query}' ({len(matches)} matches):\033[0m")
        for comp in matches:
            comp_type = "Template" if comp.is_template else "Component"
            snippet = comp.docstring.split("\n")[0][:60]
            if len(comp.docstring.split("\n")[0]) > 60:
                snippet += "..."
            print(f"  • \033[1;36m{comp.ref}\033[0m [\033[32m{comp_type}\033[0m] - {snippet}")
        print()

    def _find_xml_build(self, arg):
        files = self._get_chronological_builds()
        matching = []
        for f in files:
            base = os.path.basename(f)
            h = base[5:-4]
            if h.startswith(arg) or base.startswith(arg) or base == arg:
                matching.append(f)
        if len(matching) > 1:
            print(f"\033[91mError: Multiple XML snapshots found starting with '{arg}'.\033[0m")
            return None
        return matching[0] if matching else None

    def cmd_enter(self, arg):
        if not arg:
            raise ValueError("Snapshot ID or hash required.")
        if arg.lower() == "latest":
            self.cmd_leave()
            return
            
        if isinstance(self.store, SQLiteSpecStore):
            build = self.find_build_by_id(arg)
            if build:
                self.active_build = build
                self.load_components()
                print(f"\033[1;32mEntered snapshot context: {self.active_session_id}\033[0m")
        elif isinstance(self.store, XmlSpecStore):
            if not self.store.is_dir:
                print("\033[91mError: Snapshot navigation not supported in single XML mode.\033[0m")
                return
            build = self._find_xml_build(arg)
            if build:
                self.active_build = build
                self.load_components()
                print(f"\033[1;32mEntered snapshot context: {self.active_session_id}\033[0m")

    def cmd_leave(self):
        if self.active_build is None:
            print("Already in the latest snapshot context.")
            return
        self.active_build = None
        self.load_components()
        print("\033[1;32mReturned to latest snapshot context.\033[0m")

    def get_components_for_build(self, build):
        from libspec.store import SQLiteSpecStore, XmlSpecStore
        if isinstance(self.store, SQLiteSpecStore):
            return self._load_sqlite_components(build)
        elif isinstance(self.store, XmlSpecStore):
            return self._load_xml_components(build)
        return []

    def find_build_by_id(self, arg):
        from libspec.store import SQLiteSpecStore, XmlSpecStore
        if isinstance(self.store, SQLiteSpecStore):
            build = DBBuild.get_or_none(DBBuild.session_id == arg)
            if not build:
                builds = DBBuild.select().where(DBBuild.session_id.startswith(arg))
                if len(builds) == 1:
                    build = builds[0]
                elif len(builds) > 1:
                    print(f"\033[91mError: Multiple snapshots found starting with '{arg}':\033[0m")
                    for b in builds[:5]:
                        print(f"  • {b.session_id}")
                    return None
            return build
        return None

    def _resolve_diff_default(self):
        new_comps = self.components
        active_build = self.active_build or (self.store._get_latest_build() if isinstance(self.store, SQLiteSpecStore) else None)
        
        if isinstance(self.store, SQLiteSpecStore):
            old_build = self._get_predecessor_build(active_build)
            old_comps = self.get_components_for_build(old_build)
            return old_comps, new_comps, self._get_build_desc(old_build), self._get_build_desc(active_build)
        elif isinstance(self.store, XmlSpecStore):
            if not self.store.is_dir:
                raise ValueError("Single XML mode does not support default diff predecessor lookup.")
            files = self._get_chronological_builds()
            active_file = self.active_build or (files[-1] if files else None)
            old_file = self._get_predecessor_build(active_file)
            old_comps = self.get_components_for_build(old_file)
            return old_comps, new_comps, self._get_build_desc(old_file), self._get_build_desc(active_file)
        raise ValueError("Unsupported SpecStore for diffing.")

    def _resolve_diff_one_arg(self, arg):
        target = self.find_build_by_id(arg)
        if target is None:
            target = self._find_xml_build(arg)
        if target is None:
            raise ValueError(f"Snapshot '{arg}' not found.")
            
        old_comps = self.get_components_for_build(target)
        new_comps = self.components
        
        active_build = self.active_build or (self.store._get_latest_build() if isinstance(self.store, SQLiteSpecStore) else None)
        return old_comps, new_comps, self._get_build_desc(target), self._get_build_desc(active_build)

    def _resolve_diff_two_args(self, arg1, arg2):
        bx = self.find_build_by_id(arg1) or self._find_xml_build(arg1)
        by = self.find_build_by_id(arg2) or self._find_xml_build(arg2)
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

    def cmd_diff(self, arg):
        parts = arg.split() if arg else []
        verbose = "-v" in parts
        if verbose:
            parts.remove("-v")
            
        try:
            old_comps, new_comps, old_desc, new_desc = self._resolve_diff_by_parts(parts)
            added, removed, changed = self._compute_diff(old_comps, new_comps)
            self._print_diff_report(old_desc, new_desc, added, removed, changed, verbose)
        except Exception as e:
            print(f"\033[91mError executing diff: {e}\033[0m")

    def _resolve_diff_by_parts(self, parts):
        if len(parts) == 0:
            return self._resolve_diff_default()
        elif len(parts) == 1:
            return self._resolve_diff_one_arg(parts[0])
        elif len(parts) == 2:
            return self._resolve_diff_two_args(parts[0], parts[1])
        raise ValueError("Too many arguments for diff command.")

    def _print_diff_report(self, old_desc, new_desc, added, removed, changed, verbose):
        print("\n\033[1;33mSpecification Diff Overview:\033[0m")
        print(f"  Comparing: \033[36m{old_desc}\033[0m -> \033[32m{new_desc}\033[0m")
        print("-" * 60)
        
        if not added and not removed and not changed:
            print("  No changes detected.")
            print("-" * 60 + "\n")
            return
            
        self._print_diff_added(added, verbose)
        self._print_diff_removed(removed)
        self._print_diff_changed(changed, verbose)
        print("-" * 60 + "\n")

    def _print_diff_added(self, added, verbose):
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

    def _print_diff_removed(self, removed):
        if not removed:
            return
        print("  \033[1;31m[REMOVED]\033[0m Components:")
        for c in removed:
            comp_type = "Template" if c.is_template else "Component"
            print(f"    • {c.ref} [{comp_type}]")
        print()

    def _print_diff_changed(self, changed, verbose):
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
