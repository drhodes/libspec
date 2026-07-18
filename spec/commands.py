"""
Specification for the Unified Command Pattern and Core Command Capabilities.
"""

from .err import Feat, Req


class UnifiedCommandPattern(Req):
    """
    All user-facing operations (e.g. `diff`, `log`, `show`, `list`, `search`, `dependencies`)
    must follow a unified command pattern.

    1. Core logic and argument options must be defined in a single central place within
       the core library (e.g., as service functions or engines in `libspec`).
    2. User interfaces (CLI, REPL, and MCP) must act as thin wrappers that only handle
       interface-specific input parsing and output presentation.
    3. Parameters, flags, and options parsed by the interfaces must propagate directly and
       transparently to the underlying core logic.
    """


class UnifiedLogCommand(Feat):
    """
    The unified specification log command retrieves the Git commit history of the specifications.

    Options:
    - `all_commits` (bool/flag, e.g., `-a` or `--all`):
      If True, retrieve all repository commits bypassing the `spec/` path filter and pagination limits.
      If False, retrieve only the latest 20 commits that modified files inside the `spec/` directory.
    """
