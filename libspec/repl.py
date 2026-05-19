import sys
import os
import traceback
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
        # Split text into words to understand context
        parts = text.lstrip().split()
        
        # Determine if we are completing a command or an FQN
        is_fqn_mode = False
        if len(parts) > 1:
            is_fqn_mode = True
        elif len(parts) == 1 and text.endswith(" "):
            is_fqn_mode = True

        word = document.get_word_before_cursor(WORD=True)
        
        if is_fqn_mode:
            # We are completing component FQNs
            for fqn in self.fqns:
                if fqn.startswith(word):
                    yield Completion(fqn, start_position=-len(word), display_meta=self.meta.get(fqn, ""))
        else:
            # We are completing REPL commands
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

    def load_components(self):
        try:
            if isinstance(self.store, SQLiteSpecStore):
                # SQLite relational store
                if self.active_build is None:
                    build = self.store._get_latest_build()
                else:
                    build = self.active_build
                    
                if build is None:
                    self.components = []
                    self.fqns = set()
                    self.active_session_id = None
                    return
                    
                self.active_session_id = build.session_id
                
                specs = DBSpec.select().where(DBSpec.build == build)
                components = []
                for spec in specs:
                    edges = DBEdge.select().where(DBEdge.build == build, DBEdge.child_ref == spec.ref).order_by(DBEdge.position.asc())
                    inherits = [edge.parent_ref for edge in edges]
                    components.append(Component(
                         ref=spec.ref,
                         docstring=spec.docstring,
                         is_template=spec.is_template,
                         inherits=inherits,
                         hash=spec.hash
                    ))
                self.components = components
                self.fqns = {c.ref for c in self.components}
                
            elif isinstance(self.store, XmlSpecStore):
                # XML file store
                if self.active_build is None:
                    self.components = self.store.list_components()
                    self.active_session_id = None
                else:
                    # Parse specific file path
                    store = XmlSpecStore(self.active_build)
                    self.components = store.list_components()
                    base = os.path.basename(self.active_build)
                    if base.startswith("spec-") and base.endswith(".xml"):
                        self.active_session_id = base[5:-4]
                    else:
                        self.active_session_id = base
                self.fqns = {c.ref for c in self.components}
            else:
                self.components = self.store.list_components()
                self.fqns = {c.ref for c in self.components}
                self.active_session_id = None
        except SpecStoreNotFoundError:
            self.components = []
            self.fqns = set()
            self.active_session_id = None
        except Exception as e:
            print(f"\033[91mError loading components from SpecStore: {e}\033[0m")
            self.components = []
            self.fqns = set()
            self.active_session_id = None

    def get_summary(self, docstring):
        if not docstring:
            return ""
        # Extract the first non-empty line
        for line in docstring.splitlines():
            line = line.strip()
            if line:
                return line[:60] + "..." if len(line) > 60 else line
        return ""

    def start(self):
        commands = ["help", "list", "components", "show", "snapshots", "search", "enter", "leave", "exit", "quit", "h", "q"]
        meta = {}
        for c in self.components:
            if c.docstring:
                meta[c.ref] = self.get_summary(c.docstring)
            else:
                meta[c.ref] = ""
                
        completer = LibspecCompleter(commands, self.fqns, meta)
        session = PromptSession(completer=completer, complete_style=CompleteStyle.READLINE_LIKE)
        
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
        
        while True:
            try:
                if self.active_session_id:
                    prompt_str = f"\033[1;35mlibspec({self.active_session_id[:10]})>\033[0m "
                else:
                    prompt_str = "\033[1;35mlibspec>\033[0m "
                    
                line = session.prompt(ANSI(prompt_str)).strip()
                if not line:
                    continue
                
                parts = line.split(None, 1)
                cmd = parts[0].lower()
                arg = parts[1].strip() if len(parts) > 1 else ""
                
                if cmd in ("exit", "quit", "q"):
                    print("Goodbye!")
                    break
                elif cmd in ("help", "h", "?"):
                    self.cmd_help()
                elif cmd in ("list", "components"):
                    self.cmd_list()
                elif cmd == "show":
                    if not arg:
                        print("\033[91mError: FQN argument required. Usage: show <component_ref>\033[0m")
                    else:
                        self.cmd_show(arg)
                elif cmd == "snapshots":
                    self.cmd_snapshots()
                elif cmd == "search":
                    if not arg:
                        print("\033[91mError: Search query required. Usage: search <query>\033[0m")
                    else:
                        self.cmd_search(arg)
                elif cmd == "enter":
                    if not arg:
                        print("\033[91mError: Snapshot ID required. Usage: enter <snapshot_id>\033[0m")
                    else:
                        self.cmd_enter(arg)
                        completer.fqns = sorted(list(self.fqns))
                        completer.meta = {c.ref: self.get_summary(c.docstring) for c in self.components if c.docstring}
                elif cmd == "leave":
                    self.cmd_leave()
                    completer.fqns = sorted(list(self.fqns))
                    completer.meta = {c.ref: self.get_summary(c.docstring) for c in self.components if c.docstring}
                else:
                    print(f"\033[91mUnknown command: '{cmd}'. Type 'help' for available commands.\033[0m")
                    
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
        print("  \033[1;32mlist\033[0m | \033[1;32mcomponents\033[0m             List all specification components in the active snapshot context.")
        print("  \033[1;32mshow <FQN>\033[0m                    Show full details of a specific component (supports tab-completion).")
        print("  \033[1;32msnapshots\033[0m                     List chronological build/snapshot history.")
        print("  \033[1;32msearch <query>\033[0m                Search components and docstrings for a keyword.")
        print("  \033[1;32menter <snapshot_id>\033[0m          Scope the REPL context to a specific historical snapshot.")
        print("  \033[1;32mleave\033[0m                         Restore the REPL context to the latest compiled snapshot.")
        print("  \033[1;32mexit\033[0m | \033[1;32mquit\033[0m                   Exit the REPL session.")
        print()

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

    def cmd_show(self, ref):
        comp = None
        for c in self.components:
            if c.ref == ref:
                comp = c
                break
                
        if comp is None:
            print(f"\033[91mComponent '{ref}' not found in active snapshot context.\033[0m")
            matches = [f for f in self.fqns if ref.lower() in f.lower()]
            if matches:
                print("\033[1;33mDid you mean:\033[0m")
                for m in matches[:5]:
                    print(f"  • {m}")
            return
            
        print("\033[1;36m" + "="*60 + "\033[0m")
        print(f"\033[1;33mReference:\033[0m   \033[1;32m{comp.ref}\033[0m")
        comp_type = "Template Feature/Requirement" if comp.is_template else "Feature/Requirement"
        print(f"\033[1;33mType:\033[0m        {comp_type}")
        print(f"\033[1;33mHash:\033[0m        {comp.hash}")
        
        if comp.inherits:
            print(f"\033[1;33mInherits:\033[0m    " + ", ".join(comp.inherits))
            
        print("\033[1;33mDocstring:\033[0m")
        print("-" * 60)
        print(comp.docstring)
        print("-" * 60)
        
        try:
            if isinstance(self.store, SQLiteSpecStore):
                build = self.active_build if self.active_build else self.store._get_latest_build()
                if build:
                    claims = DBImplemented.select().where(DBImplemented.build == build, DBImplemented.ref == ref)
                    if claims:
                        print(f"\033[1;33mImplementation Claims ({len(claims)}):\033[0m")
                        for cl in claims:
                            print(f"  • \033[32m{cl.file}:{cl.line}\033[0m (Session: {cl.session_id})")
                    else:
                        print("\033[93mNo implementation claims recorded for this component in this snapshot.\033[0m")
            elif isinstance(self.store, XmlSpecStore):
                store = XmlSpecStore(self.active_build) if self.active_build else self.store
                snap = store.current_snapshot()
                if snap:
                    claims = [c for c in store.list_implemented(snap) if c.ref == ref]
                    if claims:
                        print(f"\033[1;33mImplementation Claims ({len(claims)}):\033[0m")
                        for cl in claims:
                            print(f"  • \033[32m{cl.file}:{cl.line}\033[0m (Session: {cl.session_id})")
                    else:
                        print("\033[93mNo implementation claims recorded for this component.\033[0m")
        except Exception:
            pass
            
        print("\033[1;36m" + "="*60 + "\033[0m\n")

    def cmd_snapshots(self):
        print("\033[1;33m\nChronological Snapshot History:\033[0m")
        print("-" * 60)
        if isinstance(self.store, SQLiteSpecStore):
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
        elif isinstance(self.store, XmlSpecStore):
            if self.store.is_dir:
                files = []
                import glob
                for f in glob.glob(os.path.join(self.store.directory, "spec-*.xml")):
                    files.append(f)
                files.sort(key=os.path.getmtime)
                if not files:
                    print("No XML snapshots found in directory.")
                for f in files:
                    mtime = os.path.getmtime(f)
                    from datetime import datetime, timezone
                    dt = datetime.fromtimestamp(mtime, timezone.utc)
                    name = os.path.basename(f)
                    active_marker = ""
                    if self.active_build == f:
                        active_marker = " \033[1;31m(ACTIVE)\033[0m"
                    elif self.active_build is None and f == files[-1]:
                        active_marker = " \033[1;31m(ACTIVE)\033[0m"
                    print(f"  • \033[1;36m{dt.isoformat()}\033[0m | File: \033[32m{name}\033[0m{active_marker}")
            else:
                print(f"Single XML file mode: {self.store.xml_path}")
        print("-" * 60 + "\n")

    def cmd_search(self, query):
        self.load_components()
        matches = []
        for c in self.components:
            if query.lower() in c.ref.lower() or query.lower() in c.docstring.lower():
                matches.append(c)
                
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

    def cmd_enter(self, arg):
        if not arg:
            print("\033[91mError: Snapshot ID or hash required. Usage: enter <snapshot_id>\033[0m")
            return
            
        if arg.lower() == "latest":
            self.cmd_leave()
            return
            
        if isinstance(self.store, SQLiteSpecStore):
            build = None
            try:
                build = DBBuild.get_or_none(DBBuild.session_id == arg)
                if not build:
                    builds = DBBuild.select().where(DBBuild.session_id.startswith(arg))
                    if len(builds) == 1:
                        build = builds[0]
                    elif len(builds) > 1:
                        print(f"\033[91mError: Multiple snapshots found starting with '{arg}':\033[0m")
                        for b in builds[:5]:
                            print(f"  • {b.session_id}")
                        return
            except Exception as e:
                print(f"\033[91mError querying database: {e}\033[0m")
                return
                
            if build is None:
                print(f"\033[91mError: No snapshot found matching or starting with '{arg}'.\033[0m")
                return
                
            self.active_build = build
            self.load_components()
            print(f"\033[1;32mEntered snapshot context: {self.active_session_id}\033[0m")
            
        elif isinstance(self.store, XmlSpecStore):
            if not self.store.is_dir:
                print("\033[91mError: Single XML file SpecStore does not support historical snapshot navigation.\033[0m")
                return
                
            import glob
            files = glob.glob(os.path.join(self.store.directory, "spec-*.xml"))
            matching_files = []
            for f in files:
                base = os.path.basename(f)
                h = base[5:-4]
                if h.startswith(arg) or base.startswith(arg) or base == arg:
                    matching_files.append(f)
                    
            if not matching_files:
                print(f"\033[91mError: No XML files found matching or starting with '{arg}'.\033[0m")
                return
            elif len(matching_files) > 1:
                print(f"\033[91mError: Multiple XML snapshots found starting with '{arg}':\033[0m")
                for f in matching_files[:5]:
                    print(f"  • {os.path.basename(f)}")
                return
                
            self.active_build = matching_files[0]
            self.load_components()
            print(f"\033[1;32mEntered snapshot context: {self.active_session_id}\033[0m")
            
        else:
            print("\033[91mError: Active SpecStore does not support snapshot navigation.\033[0m")

    def cmd_leave(self):
        if self.active_build is None:
            print("Already in the latest snapshot context.")
            return
        self.active_build = None
        self.load_components()
        print("\033[1;32mReturned to latest snapshot context.\033[0m")
