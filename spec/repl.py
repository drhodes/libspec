"""
Specification for the Interactive Specification Inspector REPL.
"""

from .err import Feat, Req


class LibspecRepl(Feat):
    """
    The libspec platform must provide an interactive Read-Eval-Print Loop
    (REPL) to enable users to easily inspect, search, and navigate all aspects
    of the compiled specification suite using the active SpecStore interface
    layer.

    The REPL session must be invoked via the top-level CLI using the `repl`
    subcommand: `uv run libspec repl`
    """


class ReplCommands(Req):
    """
    The REPL must support a concise, user-friendly set of commands:

    1. `help` (shortcuts: `h`, `?`): Print all available commands, usage
    syntax, and helpful examples. 2. `list` or `components`: List all
    specification components parsed in the current snapshot context. 3. `show
    <component_ref>`: Render the full docstring, type, template attributes, MRO
    inheritance relationships, and registered implementation claims for a
    specific component in the current snapshot context. 4. `snapshots`: List
    all compiled snapshot history recorded chronologically in the active
    database. 5. `search <query>`: Query component references and docstring
    contents in the current snapshot context with case-insensitive substring
    match. 6. `enter <snapshot_id_or_date>`: Scope the REPL context to a
    specific historical snapshot, identifying the snapshot using either its
    unique hash/session ID or its ISO creation timestamp. 7. `leave`: Restore
    the REPL context to the latest compiled snapshot. 8. `diff
    [snapshot_id_or_date] [snapshot_b_or_date] [-v]`: Renders a high-level
    color-coded overview summarizing which components were added, removed, or
    changed between snapshots. Passing `-v` renders granular unified diffs of
    modified component docstrings. 9. `exit` or `quit` (shortcut: `q`):
    Terminate the REPL session cleanly.
    """


class ReplUserExperience(Req):
    """
    The interactive REPL must be designed for professional productivity and ease of use:

    1. Interactive Prompt: Present a distinct and responsive prompt (e.g.
    `libspec> `) to indicate readiness. 2. Tab-Completion: Integrate
    context-aware tab-completion using prompt-toolkit. Dynamically suggest REPL
    commands for the first word, component FQNs/references exclusively as
    arguments to `show`. For `enter` and `diff` commands, triggering tab
    completion on an empty argument prints the beautifully formatted
    chronological snapshot history table above the prompt to guide the user,
    yielding a concise list of short hash IDs in the completion menu to prevent
    clutter. When a prefix is supplied, completions are filtered to only
    matching hashes; if no snapshot hash starts with the prefix, an informative
    error message is printed above the prompt. Uses a GNU Readline-like layout
    printed below the prompt with zero static whitespace reservation. 3.
    Resiliency: Gracefully catch keyboard interrupts (`Ctrl+C`), handle unknown
    or malformed commands without crashing, and present descriptive
    error/warning logs. 4. ANSI Colorized Outputs: Use ANSI escape sequences to
    beautifully format and color-code sections, table headers, and command
    summaries.
    """


class ReplArchitecture(Req):
    """
    The REPL command dispatch system must be designed using the Command Pattern
    to promote maximum modularity, extensibility, and separation of
    concerns:

    1. Base Command Interface: All commands must inherit from a common
    `ReplCommand` base class defining name, description, and execution
    interfaces. 2. Commander Registry: A dedicated `Commander` dispatcher must
    manage command registration, map user aliases dynamically, and parse raw
    string arguments to delegate execution to the appropriate command object.
    3. State Encapsulation: Subclassed commands must be fully stateless or keep
    state changes strictly scoped, accepting a reference to the central REPL
    class to execute context mutations.
    """
