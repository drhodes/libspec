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


class ReplCwdValidation(Req):
    """
    The REPL must validate that the current working directory is a valid
    libspec project before starting any interactive session.

    A valid libspec project is one whose current working directory contains
    a `.libspec/` subdirectory (see `spec.utils.IsLibspecProject`).

    Behavior when the check fails:
    - Print a clear, human-readable error message to stderr identifying the
      checked directory and instructing the user to run `libspec init`.
    - Exit immediately with a non-zero exit code (exit code 1).
    - Do not display the REPL prompt or attempt to load the SpecStore.

    The check must be performed inside `LibspecRepl.__init__()` (or the
    REPL startup path invoked by the CLI), before any call to `get_store()`.
    It must use `require_libspec_project()` from `libspec.utils`
    (see `spec.utils.LibspecProjectGuard`).
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


class ListSnapshotsCommandReq(Req):
    """
    `list-snapshots` (shortcut: `ls`): List all compiled snapshot history recorded
    chronologically in the active database.
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
    changed.

    If no arguments are provided, it compiles the live specification files
    on-the-fly (the pending spec) and diffs them against the latest recorded
    snapshot `#0` in the SpecStore without writing to the database.

    If arguments are provided, it resolves both sides from the SpecStore.
    This command accepts dynamic relative enumeration
    indices explicitly prefixed with a hash symbol (e.g. `#1`) or standard
    hexadecimal ID/timestamp strings. Passing `-v` renders granular unified
    diffs of modified component docstrings. Passing `-vv` (very verbose)
    renders the full structured semantic spec diff, matching the top-level
    `libspec diff` command.
    """


class DiffSuccessorShortcutReq(Req):
    """
    The `diff` command must support the `@N` syntax shortcut (e.g. `diff @4`).
    Specifying a single argument starting with `@` followed by an integer index `N`
    (e.g., `@4`) is a shortcut representing a diff comparison between snapshot
    `#N` and its immediate chronological successor `#N+1` (e.g., `#4` and `#5`).
    """




class ReplAgentConfigCommandReq(Req):
    """
    `agent-config <agent> [project_root]`: Configures project-local coding agent
    integrations from within the REPL, setting up MCP configurations and installing skills.
    """


class ExitCommandReq(Req):
    """
    `exit` or `quit` (shortcut: `q`): Terminate the REPL session cleanly.
    """


class ReplAutoReloadReq(Req):
    """
    The interactive REPL must monitor the specification files in the `spec/` directory
    for modification events. When changes are detected, the REPL must automatically reload
    the active component list without requiring a restart.
    """


class ReplInotifyWatcherReq(Req):
    """
    On Linux, the REPL must use the native `inotify` subsystem integrated with the asyncio
    event loop to monitor spec file modifications.
    """


class ReplLinuxInotifyReq(ReplInotifyWatcherReq):
    """
    On Linux, the REPL must use the native `inotify` subsystem integrated with the asyncio
    event loop to monitor spec file modifications.
    """


class ReplLinuxInotifyAsyncReq(ReplLinuxInotifyReq):
    """
    The REPL must integrate the native inotify watcher with the asyncio event loop to
    prevent blocking the main interactive thread.
    """


class ReplLinuxInotifyEventsReq(ReplLinuxInotifyReq):
    """
    The watcher must monitor the files in the `spec/` directory for modification events.
    """


class ReplInotifyReloadCallbackReq(ReplInotifyWatcherReq):
    """
    When a change is detected, the watcher must trigger an asynchronous reload callback.
    """


class ReplInotifyReloadDebounceReq(ReplInotifyReloadCallbackReq):
    """
    The reload callback must debounce file events (e.g. 150ms delay) to avoid multiple rapid reloads.
    """


class ReplInotifyReloadStoreReq(ReplInotifyReloadCallbackReq):
    """
    The reload callback must reload all components upon change.
    """


class ReplTerminalSuspensionReq(ReplInotifyWatcherReq):
    """
    The REPL must use prompt-toolkit's terminal suspension (e.g. run_in_terminal) to
    instantly clear the screen, corrupt the output history, execute the reload, and
    resume the prompt interface without losing the user's current input buffer text.
    """


class ReplUserExperience(Req):
    """
    The interactive REPL must be designed for professional productivity and ease of use.
    """


class ReplInteractivePromptReq(ReplUserExperience):
    """
    Present a distinct and responsive interactive prompt.
    """


class ReplTabCompletionReq(ReplUserExperience):
    """
    Integrate context-aware tab-completion for commands, snapshot IDs, and component references.
    """


class ReplResiliencyReq(ReplUserExperience):
    """
    Gracefully catch keyboard interrupts and handle unknown commands without exiting.
    """


class ReplColorizedOutputReq(ReplUserExperience):
    """
    Use ANSI escape sequences to format headers, diffs, and table structures in color.
    """


class ReplArchitecture(Req):
    """
    The REPL command dispatch system must be designed using the Command Pattern.
    """


class ReplCommandHelpReq(Req):
    """
    Every interactive REPL command must support `--help` and `-h` options.
    """


class ReplCommandHelpOptionReq(ReplCommandHelpReq):
    """
    Every interactive REPL command must capture the `--help` and `-h` arguments.
    """


class ReplCommandHelpOutputReq(ReplCommandHelpReq):
    """
    When help is requested for a command, it must print the usage information and
    not execute the command.
    """


class ReplShortcutsReq(Req):
    """
    The REPL must support command shortcuts/aliases to speed up navigation.
    """


class ReplShortcutsListReq(ReplShortcutsReq):
    """
    The REPL must support shortcuts to list snapshots (e.g. `sn`, `ls`, `snapshots`) and components (e.g. `components`).
    """


class ReplShortcutsCommandReq(ReplShortcutsReq):
    """
    The REPL must support shortcuts for commonly used commands such as exiting (`q`, `quit`), help (`h`, `?`), delete (`rm`), restore (`restore`), and dependencies (`dep`, `deps`).
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
    terminal after an external file modification, the REPL must capture and visually
    corrupt the session history upon change detection.
    """


class ReplOutputCaptureReq(ReplFileChangeCorruptReq):
    """
    The REPL must capture all standard output printed during the session.
    """


class ReplCorruptHistoryReq(ReplFileChangeCorruptReq):
    """
    Upon change detection, the REPL must reprint the entire session history with all
    whitespace characters (spaces) in those printed lines replaced by middle dots (·)
    to visually mark them as corrupted/stale.
    """


class ReplCorruptReloadNotifyReq(ReplFileChangeCorruptReq):
    """
    After reprinting the corrupted history, the REPL must print the reload notification.
    """


class ReplLogCommandReq(Req):
    """
    The REPL must register a primary command named 'log' which triggers the
    display of the Git commit history of the specifications.
    """


class ReplLogFormatReq(Req):
    """
    The output of the log command must be rendered as a beautifully formatted,
    chronological list of Git commits.
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


class ReplDeclareDependencyCommandReq(Req):
    """
    `declare-dependency <component_ref> <depends_on_ref> [snapshot_id]`:
    Declares a logical dependency where `component_ref` depends on `depends_on_ref`.
    Optionally accepts a target snapshot ID (defaults to `"HEAD"`).
    """


class ReplDependenciesCommandReq(Req):
    """
    `dependencies [snapshot_id]` (shortcut: `deps`):
    Lists all component dependencies recorded for the target snapshot (defaults to the active/current snapshot context).
    """


class ReplPendingSpecLiveReloadReq(Req):
    """
    To prevent stale pending diffs and component listings, when the REPL is scoped
    to the active pending/live specification context (where active_build is None),
    any command execution (including list, components, show, search, diff, etc.)
    must automatically reload and recompile the live specification components on-the-fly
    from source files.

    Furthermore, the compiler must ensure that any submodules under the base package of the
    live specification (e.g. `spec.*`) are removed from Python's cached `sys.modules` registry
    prior to reloading, ensuring that recent file modifications on disk are fully reflected.
    """


class ListSnapshotsPendingLineReq(Req):
    """
    The REPL `list-snapshots` (or `ls`) command must include a special virtual row
    representing the current unsaved/pending (live) specification context when it
    exists.

    This row should:
    - Appear at the top of the snapshots list or as the most recent entry.
    - Display the snapshot ID as `HEAD`.
    - Show the creation date/time (or mark it as "HEAD" / current time).
    - Display `HEAD` for the Git Commit column.
    - Show the size in bytes of the live/pending compiled spec data.
    """
