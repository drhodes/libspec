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
    The REPL must support a concise, user-friendly set of commands.
    Each command must be implemented cleanly as a subclass of ReplCommand
    and handle its own specific execution context, argument parsing, and safety checks.
    """


class HelpCommandReq(Req):
    """
    `help` (shortcuts: `h`, `?`): Print all available commands, usage
    syntax, and helpful examples.
    """


class ListCommandReq(Req):
    """
    `list` or `components`: List all specification components parsed in the
    current snapshot context.
    """


class ShowCommandReq(Req):
    """
    `show <component_ref>`: Render the full docstring, type, template attributes,
    MRO inheritance relationships, and registered implementation claims for a
    specific component in the current snapshot context.
    """


class SnapshotsCommandReq(Req):
    """
    `snapshots`: List all compiled snapshot history recorded chronologically
    in the active database. The output must number them dynamically such that
    they are enumerated from the most recent to the oldest (least recent),
    meaning the most recent/current snapshot has enumeration index 0, the next
    most recent has index 1, and so on. For each snapshot, the output must
    display the count of new components added (relative to its chronological
    predecessor), the total specification size in bytes, and the associated Git commit hash.
    If the snapshot's Git commit reference is unlinked (null or 'PENDING'), the output
    must explicitly display 'PENDING' in the commit hash column to indicate it has not
    been committed yet.
    """



class SearchCommandReq(Req):
    """
    `search <query>`: Query component references and docstring contents in
    the current snapshot context with case-insensitive substring match.
    """


class EnterCommandReq(Req):
    """
    `enter <snapshot_id_or_date>`: Scope the REPL context to a specific
    historical snapshot, identifying the snapshot using either its unique
    hash/session ID, its ISO creation timestamp, or a relative enumeration
    index explicitly prefixed with a hash symbol (e.g. `#0` for latest, `#1`
    for second latest) to completely preempt prefix collisions with standard
    hexadecimal snapshot ID prefixes that start with digits.
    """


class LeaveCommandReq(Req):
    """
    `leave`: Restore the REPL context to the latest compiled snapshot.
    """


class DiffCommandReq(Req):
    """
    `diff [snapshot_id_or_date] [snapshot_b_or_date] [-v]`: Renders a high-level
    color-coded overview summarizing which components were added, removed, or
    changed between snapshots. This command accepts dynamic relative enumeration
    indices explicitly prefixed with a hash symbol (e.g. `#1`) or standard
    hexadecimal ID/timestamp strings. Passing `-v` renders granular unified
    diffs of modified component docstrings. Passing `-vv` (very verbose)
    renders the full structured semantic spec diff (including added/removed specs,
    polymorphic property diffs, inherited context diffs, and unresolved warnings),
    matching the comprehensive output of the top-level `libspec diff` CLI command.
    """


class RmSnapshotCommandReq(Req):
    """
    `rm-snapshot <snapshot_id_or_date>`: Permanently delete a historical
    snapshot from the active SpecStore. This command accepts dynamic relative
    enumeration indices explicitly prefixed with a hash symbol (e.g. `#2`)
    or standard hexadecimal ID/timestamp strings. To ensure the user never
    deletes the wrong snapshot, the confirmation prompt must print a detailed
    verification card showing the dynamic index reference used (or standard ID),
    the resolved ID/hash, the creation date/timestamp, and git commit metadata.
    This command is protected by a confirmation prompt and will refuse to
    delete the currently active snapshot context or the latest snapshot to
    ensure system safety.
    """


class RestoreSnapshotCommandReq(Req):
    """
    `restore-snapshot <snapshot_id_or_date>`: Restore a previously deleted/tombstoned
    historical snapshot back into the active list of snapshots. This command accepts
    dynamic relative enumeration indices explicitly prefixed with a hash symbol (e.g. `#2`)
    or standard hexadecimal ID/timestamp strings. It retrieves the snapshot from the log
    history and appends a restore event to the SpecStore, bringing the snapshot back into
    active rotation chronologically.
    """


class ExitCommandReq(Req):
    """
    `exit` or `quit` (shortcut: `q`): Terminate the REPL session cleanly.
    """


class ReplAutoReloadReq(Req):
    """
    The interactive REPL must monitor the underlying storage file for modification
    events. When external changes are detected (such as new snapshot compilations or
    migrations modifying the JSON Lines log or SQLite database file), the REPL must
    automatically reload the store records and active component list without requiring
    a restart.
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

class ReplCommandHelpReq(Req):
    """
    Every interactive REPL command must support `--help` and `-h` options to
    render usage formatting, syntax expectations, and colorized examples.
    This help interception must be implemented central to the command dispatcher
    to ensure unified and resilient coverage across all current and future commands.
    """


class ReplShortcutsReq(Req):
    """
    The REPL must support command shortcuts/aliases to speed up navigation:
    - `sn`: Alias/shortcut for `snapshots` command.
    - `ls`: Alias/shortcut for `list` command.
    
    Tab completion of commands must exclude shortcuts/aliases to prevent menu
    clutter.
    
    The padding of the help menu command column must be dynamically adjusted
    based on the longest command name to prevent any description misalignment.
    """


class ReplAutoSuggestGuessingReq(Req):
    """
    The REPL inline auto-suggestion engine must dynamically guess the user's intent:
    - Command Name Guessing: If the user has typed a partial first word, guess and
      suggest the remainder of the first matching primary command (e.g. typing 'sn'
      should match and suggest 'apshots' to complete 'snapshots').
    - History Fallback: If the command name is already complete or no matching command
      exists, fall back to matching suggestions from the current REPL session history
      (e.g., repeating a previous command with specific arguments).
    """


class ReplAutoSuggestStylingReq(Req):
    """
    The inline auto-suggested suffix must be rendered in a dulled, muted color.
    This styling must be configured globally in the prompt-toolkit style sheet (using the
    'auto-suggest' style token mapped to a dark gray hex color like `#666666` or `#888888`,
    or standard `ansigray`) so that suggestions appear as a clear, unobtrusive "ghost"
    text distinct from the user's typed input.
    """


class ReplAutoSuggestBindingsReq(Req):
    """
    The REPL inline suggestions must support ergonomic navigation key bindings to accept suggestions:
    - Right Arrow & Ctrl+F: Accept suggestion if cursor is at the end of the line.
    - End & Ctrl+E: Accept suggestion fully, moving the cursor to the end.
    """


class ReplAutoSuggestExecuteReq(Req):
    """
    To ensure seamless interaction and prevent "Unknown command" errors,
    whenever the user hits the Enter key (submitting the command buffer),
    any active, visible auto-suggestion must be automatically accepted and
    merged into the buffer before the command is evaluated.
    """


class ReplFileChangeCorruptReq(Req):
    """
    To prevent users from acting on stale/out-of-date information printed in the
    terminal after an external file modification:
    - The REPL must capture all standard output printed during the session.
    - Upon change detection, the REPL must clear the terminal screen and reprint the
      entire session history with all whitespace characters (spaces) in those printed
      lines replaced by middle dots (·) to visually mark them as corrupted/stale.
    - Finally, the REPL must print the reload notification.
    """


class Noop(Req):
    """noop"""
