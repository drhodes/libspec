# Quickstart Tutorial

This tutorial guides you through installing `libspec` using `uv`, setting up a workspace, defining your first specification, and compiling snapshots to track design changes.



---

## Prerequisites

Make sure you have `uv` installed. If you do not have it yet, you can install it using:

```bash
# On Linux and macOS
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## Step 1: Initialize Your Project

Let's create a new project folder and initialize it with a `uv` workspace.

```bash
# Create project folder
mkdir hello-libspec && cd hello-libspec

# Initialize python project and workspace
uv init
```

---

## Step 2: Install libspec

Add `libspec` to your project using `uv`. Since we are using `uv`, we add it directly:

```bash
# Add libspec dependency to your project
uv add libspec
```

---

## Step 3: Initialize the Specification Directory

Run the `libspec init` command inside your project directory. This sets up the spec directory skeleton and establishes the canonical `.agents/` workspace agent configuration.

```bash
# Initialize libspec
uv run libspec init
```

This command automatically generates:
1. A `spec/` folder containing standard blueprints:
   - `spec/__init__.py`
   - `spec/main_spec.py` (The root Spec compiler class entry point)
   - `spec/app.py` (Default application feature & requirement templates)
   - `spec/err.py` (Best-practice defensive programming contexts)
2. A `.libspec/` directory (for cache and local settings).
3. Workspace agent skill at `.agents/skills/libspec/SKILL.md`.

---

## Step 4: Explore the Default Specification

Open `spec/app.py` to see the structure of a declaration:

```python
from .err import Feat, Req

class App(Req):
    '''
    This program should emit the
    string "Hello, world!" to the terminal.
    '''

class CmdLine(Feat):
    '''
    This program does not take any command line arguments.
    '''
```

In `libspec`, components are defined as Python classes:
- **`Req` (Requirement)** represents a specific, testable engineering constraint.
- **`Feat` (Feature)** represents a user-facing capability.
- Class docstrings contain the literal specification content.

!!! note
    You are not required to use these default classes; the class hierarchy used for specification can be built from scratch to meet your own needs.

---

## Step 5: Launch the REPL and Check Status

For interactive inspection, launch the Python-based REPL:

```bash
uv run libspec repl
```

!!! note
    You can make this easier to type with a bash alias: 
    ```bash
    alias lspec='uv run libspec'
    ```

Once inside the REPL, check the current live specification drift against Git `HEAD`:

```text
libspec(PENDING)> diff
```

You can view the commit history of your specifications:

```text
libspec(PENDING)> log
```

---

## Step 6: Query Specification Components

You can list, inspect, and search components directly inside the REPL session:

```text
# List all requirements and features in the live spec
libspec(PENDING)> list

# Show the details of the App requirement
libspec(PENDING)> show spec.app.App

# Perform a search on requirements and docstrings
libspec(PENDING)> search "Hello, world!"
```

---

## Step 7: Explore REPL Commands

Within the REPL, type `help` to list all available commands:

*   **`help`**: List all available commands.
*   **`diff [commit_a] [commit_b]`**: Compare live spec against `HEAD`, or diff between Git commits.
*   **`list [-c <commit>]`**: List all specification components in the live spec or a Git commit.
*   **`show <component_ref>`**: Show full structured details of a specific component.
*   **`search <query>`**: Search components and docstrings.
*   **`dependencies` (alias: `deps`)**: Show component dependency tree.
*   **`log`**: Show Git commit history for specifications.
*   **`exit`** (or `quit`): Exit the REPL session.

---

## Next Steps

Now that you have initialized your specification, proceed to the [Developer Agent Workflow](../how-to/agent-workflow.md) and [Using the MCP Server](../how-to/agents.md) guides to hook up your specs directly to an LLM developer agent!

