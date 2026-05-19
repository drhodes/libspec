'''
Specification for the Interactive Specification Inspector REPL.
'''

from .err import Feat, Req


class LibspecRepl(Feat):
    '''The libspec platform must provide an interactive Read-Eval-Print Loop (REPL)
    to enable users to easily inspect, search, and navigate all aspects of the
    compiled specification suite using the active SpecStore interface layer.
    
    The REPL session must be invoked via the top-level CLI using the `repl` subcommand:
    `uv run libspec repl`
    '''


class ReplCommands(Req):
    '''The REPL must support a concise, user-friendly set of commands:
    
    1. `help` (shortcuts: `h`, `?`): Print all available commands, usage syntax, and helpful examples.
    2. `list` or `components`: List all specification components parsed in the current snapshot context.
    3. `show <component_ref>`: Render the full docstring, type, template attributes, MRO
       inheritance relationships, and registered implementation claims for a specific component in the current snapshot context.
    4. `snapshots`: List all compiled snapshot history recorded chronologically in the active database.
    5. `search <query>`: Query component references and docstring contents in the current snapshot context with case-insensitive
       substring match.
    6. `enter <snapshot_id>`: Scope the REPL context to a specific historical snapshot, updating the prompt
       to indicate the active snapshot using the first 10 characters of its session ID/hash.
    7. `leave`: Restore the REPL context to the latest compiled snapshot.
    8. `exit` or `quit` (shortcut: `q`): Terminate the REPL session cleanly.
    '''


class ReplUserExperience(Req):
    '''The interactive REPL must be designed for professional productivity and ease of use:
    
    1. Interactive Prompt: Present a distinct and responsive prompt (e.g. `libspec> `) to indicate readiness.
    2. Tab-Completion: Integrate context-aware tab-completion using prompt-toolkit to dynamically suggest
       REPL commands (for the first word) and component references/FQNs (for subsequent arguments) using a GNU
       Readline-like layout printed dynamically below the prompt, ensuring zero static whitespace reservation at the bottom.
    3. Resiliency: Gracefully catch keyboard interrupts (`Ctrl+C`), handle unknown or malformed commands without
       crashing, and present descriptive error/warning logs.
    4. ANSI Colorized Outputs: Use ANSI escape sequences to beautifully format and color-code sections, table headers,
       and command summaries.
    '''
