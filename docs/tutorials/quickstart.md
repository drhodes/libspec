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

Run the `libspec init` command inside your project directory. This sets up the spec directory skeleton and establishes the canonical `.libspec/` metadata marker.

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
2. A `.libspec/` directory (where the SpecStore SQLite transaction ledger will reside).
3. A Git `post-commit` hook (to automatically record revision links on commit).

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
    You are not required to use these default classes; the class heirarchy use for specification can built from scratch to meet your own needs.

---

## Step 5: Launch the REPL and Check Status

For interactive inspection, launch the Python-based REPL:

```bash
uv run libspec repl
```

!!! note
    You can make this easier to type with a bash alias, or what have you: 
    ```bash
    alias lspec='uv run libspec'
    ```

Once inside the REPL, check what is currently pending (not yet committed to the ledger) compared to the SpecStore:

```text
libspec PENDING> diff
```

You can view the history of your spec store (which will include the initial snapshot created during workspace setup):

```text
libspec PENDING> list-snapshots
```

---

## Step 6: Query Specification Components

You can list, inspect, and search components directly inside the REPL session:

```text
# List all requirements and features in the latest snapshot
libspec PENDING> list

# Show the details of the App requirement
libspec PENDING> show spec.app.App

# Perform a semantic search on requirements and docstrings
libspec PENDING> search "Hello, world!"
```

---

## Step 7: Explore Other REPL Commands

Within the REPL, type `help` to list all available commands:

*   **`help`**: List all commands.
*   **`list-snapshots`**: View chronological build/snapshot history.
*   **`list`**: List all specification components in the active snapshot.
*   **`show <component_ref>`**: Show full details of a specific component.
*   **`search <query>`**: Search components and docstrings.
*   **`diff [snap_a] [snap_b]`**: Compare two snapshots.
*   **`enter <id>`**: Scope the REPL context to a historical snapshot.
*   **`leave`**: Restore context to the latest snapshot.
*   **`compact`**: Compact the database log.
*   **`rm-snapshot <id>`**: Permanently delete a historical snapshot.
*   **`restore-snapshot <id>`**: Restore a deleted snapshot.
*   **`link`**: Link a snapshot to a VCS revision.
*   **`log`**: Show chronological SpecStore append-only event ledger.
*   **`exit`**: Exit the REPL session.

---




## Next Steps

Now that you have initialized a spec and recorded your first snapshot, proceed to the [Using the MCP Server](../how-to/agents.md) guide to hook up your specs directly to an LLM developer agent!
