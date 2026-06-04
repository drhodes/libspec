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
    in the active database.
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
    hash/session ID or its ISO creation timestamp.
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
    renders the full structured semantic spec diff, matching the top-level
    `libspec diff` command.
    """


class ReplSnapshotCommandReq(Req):
    """
    `snapshot <spec_file>`: Compiles the specification file directly from within
    the REPL and automatically reloads the context to include the newly compiled components.
    """


class ReplLinkCommandReq(Req):
    """
    `link [--snapshot <snapshot_id>] [--vcs <vcs_type>] --revision <revision> [--metadata <key=val>]`:
    Links a compiled spec snapshot to a version control system revision from the REPL.
    """


class ReplCompactCommandReq(Req):
    """
    `compact [--dry-run]`: Compacts the SpecStore log directly from the REPL.
    """


class RmSnapshotCommandReq(Req):
    """
    `rm-snapshot <snapshot_id_or_date>`: Permanently delete a historical
    snapshot from the active SpecStore.
    """


class RestoreSnapshotCommandReq(Req):
    """
    `restore-snapshot <snapshot_id_or_date>`: Restore a previously deleted/tombstoned
    historical snapshot back into the active list of snapshots.
    """


class ExitCommandReq(Req):
    """
    `exit` or `quit` (shortcut: `q`): Terminate the REPL session cleanly.
    """


class ReplAutoReloadReq(Req):
    """
    The interactive REPL must monitor both the main storage file and all decoupled sidecar
    files (such as VCS link files) for modification events. When external changes are
    detected in either file (such as new snapshot compilations, VCS linking, or compaction),
    the REPL must automatically reload the store records and active component list without
    requiring a restart.
    """


class ReplUserExperience(Req):
    """
    The interactive REPL must be designed for professional productivity and ease of use:

    1. Interactive Prompt: Present a distinct and responsive prompt.
    2. Tab-Completion: Integrate context-aware tab-completion.
    3. Resiliency: Gracefully catch keyboard interrupts, handle unknown commands.
    4. ANSI Colorized Outputs: Use ANSI escape sequences to format headers, diffs, etc.
    """


class ReplArchitecture(Req):
    """
    The REPL command dispatch system must be designed using the Command Pattern.
    """


class ReplCommandHelpReq(Req):
    """
    Every interactive REPL command must support `--help` and `-h` options.
    """


class ReplShortcutsReq(Req):
    """
    The REPL must support command shortcuts/aliases to speed up navigation.
    """


class ReplAutoSuggestGuessingReq(Req):
    """
    The REPL inline auto-suggestion engine must dynamically guess the user's intent.
    """


class ReplAutoSuggestStylingReq(Req):
    """
    The inline auto-suggested suffix must be rendered in a dulled, muted color.
    """


class ReplAutoSuggestBindingsReq(Req):
    """
    The REPL inline suggestions must support ergonomic navigation key bindings.
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


class ReplLogCommandReq(Req):
    """
    The REPL must register a primary command named 'log' which triggers the
    display of the chronological store ledger transaction history.
    """


class ReplLogStoreReaderReq(Req):
    """
    The underlying SpecStore must support a clean interface to retrieve a list of all
    raw, parsed transaction record dictionaries from the append-only log file in
    ascending chronological order (from oldest to newest) without mutating active
    snapshot states.
    """


class ReplLogFormatReq(Req):
    """
    The output of the log command must be rendered as a beautifully formatted,
    tab-aligned, column-based chronological table.
    """


class ReplLogResiliencyReq(Req):
    """
    To ensure the REPL log command remains completely resilient when parsing
    raw event history containing missing, incomplete, or null metadata values.
    """


class DiffRangeProvenance(Feat):
    """
    The interactive REPL `diff` command must support tracking and displaying
    the origin (provenance) of differences across a range of snapshots,
    highlighting exactly which snapshot first introduced each added or modified
    component.
    """


class DiffProvenanceResolution(Req):
    """
    For each added or changed component identified in a diff comparison
    between snapshot `A` and `B`, the REPL must walk the chronological list
    of intermediate snapshots to identify the exact earliest snapshot that
    introduced the component's current content hash.
    """


class DiffProvenanceFormatting(Req):
    """
    The standard, non-verbose output of the REPL `diff` command must append
    a clean parenthetical provenance tag to each listed component showing its
    introduction or change point, dynamically resolving relative indices,
    timestamps, and commit hashes to show history at a glance.
    """
