import sys
import os
import readline
import traceback
from libspec.store import get_store, SpecStoreNotFoundError, DBBuild

class LibspecRepl:
    def __init__(self):
        self.store = get_store()
        self.components = []
        self.fqns = set()
        self.load_components()

    def load_components(self):
        try:
            self.components = self.store.list_components()
            self.fqns = {c.ref for c in self.components}
        except SpecStoreNotFoundError:
            self.components = []
            self.fqns = set()
        except Exception as e:
            print(f"\033[91mError loading components from SpecStore: {e}\033[0m")
            self.components = []
            self.fqns = set()

    def completer(self, text, state):
        try:
            import ctypes
            lib = ctypes.CDLL(readline.__file__)
            lib.rl_attempted_completion_over = 1
        except Exception:
            pass

        line_buffer = readline.get_line_buffer()
        commands = ["help", "list", "components", "show", "snapshots", "search", "exit", "quit", "h", "q"]
        
        parts = line_buffer.lstrip().split()
        
        # If we are completing the very first word (command completion)
        if len(parts) == 0 or (len(parts) == 1 and not line_buffer.endswith(" ")):
            options = [cmd for cmd in commands if cmd.startswith(text)]
        else:
            # We are completing command arguments (FQN completion)
            options = [f for f in self.fqns if f.startswith(text)]
            
        if state < len(options):
            return options[state]
        else:
            return None

    def start(self):
        # Set up readline tab completion
        readline.set_completer(self.completer)
        readline.parse_and_bind("tab: complete")
        readline.set_completer_delims(" \t\n;")
        
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
                line = input("\001\033[1;35m\002libspec>\001\033[0m\002 ").strip()
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
        print("  \033[1;32mlist\033[0m | \033[1;32mcomponents\033[0m             List all specification components in the latest snapshot.")
        print("  \033[1;32mshow <FQN>\033[0m                    Show full details of a specific component (supports tab-completion).")
        print("  \033[1;32msnapshots\033[0m                     List chronological build/snapshot history.")
        print("  \033[1;32msearch <query>\033[0m                Search components and docstrings for a keyword.")
        print("  \033[1;32mexit\033[0m | \033[1;32mquit\033[0m                   Exit the REPL session.")
        print()

    def cmd_list(self):
        self.load_components()
        if not self.components:
            print("\033[93mNo components found in the active SpecStore.\033[0m")
            return
        
        print(f"\n\033[1;33mLatest Snapshot Components ({len(self.components)} total):\033[0m")
        for comp in self.components:
            comp_type = "Template" if comp.is_template else "Component"
            print(f"  • \033[1;36m{comp.ref}\033[0m [\033[32m{comp_type}\033[0m]")
        print()

    def cmd_show(self, ref):
        try:
            comp = self.store.get_component(ref)
        except Exception:
            print(f"\033[91mComponent '{ref}' not found in active store.\033[0m")
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
            snap = self.store.current_snapshot()
            if snap:
                claims = [c for c in self.store.list_implemented(snap) if c.ref == ref]
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
        from libspec.store import SQLiteSpecStore, XmlSpecStore
        
        print("\033[1;33m\nChronological Snapshot History:\033[0m")
        print("-" * 60)
        if isinstance(self.store, SQLiteSpecStore):
            try:
                builds = DBBuild.select().order_by(DBBuild.created_at.asc())
                if not builds:
                    print("No snapshots recorded in database yet.")
                for b in builds:
                    git_info = f" (Git: {b.git_commit[:7]})" if b.git_commit else ""
                    print(f"  • \033[1;36m{b.created_at.isoformat()}\033[0m | ID: \033[32m{b.session_id}\033[0m{git_info}")
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
                    print(f"  • \033[1;36m{dt.isoformat()}\033[0m | File: \033[32m{name}\033[0m")
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
