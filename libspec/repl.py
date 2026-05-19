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
        print("  \033[1;32mexit\033[0m           Exit the REPL session.\n")
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
        if isinstance(repl.store, SQLiteSpecStore):
            self._print_sqlite(repl)
        elif isinstance(repl.store, XmlSpecStore):
            if repl.store.is_dir:
                self._print_xml(repl)
            else:
                print(f"Single XML file mode: {repl.store.xml_path}")
        print("-" * 60 + "\n")
        return True

    def _print_sqlite(self, repl):
        try:
            builds = DBBuild.select().order_by(DBBuild.created_at.asc())
            if not builds:
                print("No snapshots recorded in database yet.")
            for b in builds:
                git_info = f" (Git: {b.git_commit[:7]})" if b.git_commit else ""
                active_marker = " \033[1;31m(ACTIVE)\033[0m" if repl.active_session_id == b.session_id else ""
                print(f"  • \033[1;36m{b.created_at.isoformat()}\033[0m | ID: \033[32m{b.session_id}\033[0m{git_info}{active_marker}")
        except Exception as e:
            print(f"Failed to query database builds: {e}")

    def _print_xml(self, repl):
        files = repl._get_chronological_builds()
        if not files:
            print("No XML snapshots found in directory.")
        for f in files:
            mtime = os.path.getmtime(f)
            from datetime import datetime, timezone
            dt = datetime.fromtimestamp(mtime, timezone.utc)
            active_marker = " \033[1;31m(ACTIVE)\033[0m" if (repl.active_build == f or (repl.active_build is None and f == files[-1])) else ""
            print(f"  • \033[1;36m{dt.isoformat()}\033[0m | File: \033[32m{os.path.basename(f)}\033[0m{active_marker}")


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
        print()
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
            
        if isinstance(repl.store, SQLiteSpecStore):
            build = repl.find_build_by_id(arg)
            if build:
                repl.active_build = build
                repl.load_components()
                print(f"\033[1;32mEntered snapshot context: {repl.active_session_id}\033[0m")
        elif isinstance(repl.store, XmlSpecStore):
            if not repl.store.is_dir:
                print("\033[91mError: Snapshot navigation not supported in single XML mode.\033[0m")
                return True
            build = repl._find_xml_build(arg)
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
        print("Goodbye!")
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


class Commander:
    def __init__(self):
        self.commands = {}
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
            ExitCommand()
        ]
        for cmd in cmd_list:
            self.commands[cmd.name()] = cmd
            
        self.aliases["h"] = "help"
        self.aliases["?"] = "help"
        self.aliases["components"] = "list"
        self.aliases["quit"] = "exit"
        self.aliases["q"] = "exit"

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
    def __init__(self, commander, fqns, meta):
        self.commander = commander
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
            commands = sorted(list(self.commander.commands.keys()) + list(self.commander.aliases.keys()))
            for cmd in commands:
                if cmd.startswith(word):
                    yield Completion(cmd, start_position=-len(word))


class LibspecRepl:
    def __init__(self):
        self.store = get_store()
        self.components = []
        self.fqns = set()
        self.active_build = None
        self.active_session_id = None
        self.commander = Commander()
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

    def start(self):
        meta = {c.ref: self.get_summary(c.docstring) for c in self.components if c.docstring}
        completer = LibspecCompleter(self.commander, self.fqns, meta)
        session = PromptSession(completer=completer, complete_style=CompleteStyle.READLINE_LIKE)
        
        self._print_welcome()
        
        while True:
            try:
                sess_id = f"({self.active_session_id[:10]})" if self.active_session_id else ""
                prompt_str = f"\033[1;35mlibspec{sess_id}>\033[0m "
                line = session.prompt(ANSI(prompt_str)).strip()
                if not line:
                    continue
                keep_going = self.commander.run(line, self)
                if keep_going is False:
                    break
                completer.fqns = sorted(list(self.fqns))
                completer.meta = {c.ref: self.get_summary(c.docstring) for c in self.components if c.docstring}
            except KeyboardInterrupt:
                print("\nUse 'exit' or Ctrl+D to quit.")
            except EOFError:
                print("\nGoodbye!")
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

    def _resolve_diff_by_parts(self, parts):
        if len(parts) == 0:
            return self._resolve_diff_default()
        elif len(parts) == 1:
            return self._resolve_diff_one_arg(parts[0])
        elif len(parts) == 2:
            return self._resolve_diff_two_args(parts[0], parts[1])
        raise ValueError("Too many arguments for diff command.")
