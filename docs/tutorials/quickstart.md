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
    '''This program should emit the
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

---

## Step 5: Diff and Build Snapshots

`libspec` tracks specification states over time. Let's see what is currently pending (not yet committed to the ledger) compared to the SpecStore:

```bash
# Diff the active workspace specifications
uv run libspec diff
```

Now let's save this design snapshot to the ledger and link it to our code. We link it using a revision label:

```bash
# Link spec to current working state
uv run libspec link --revision initial-design
```

You can now view the history of your spec store:

```bash
# List snapshots chronologically
uv run libspec list-snapshots
```

---

## Step 6: Query Specification Components

You can list and search components within snapshots directly from the command line:

```bash
# List all requirements and features in the latest snapshot
uv run libspec list

# Show the details of the App requirement
uv run libspec show spec.app.App

# Perform a semantic search on requirements and docstrings
uv run libspec search "Hello, world!"
```

---

## Step 7: Launch the REPL

For interactive inspection, launch the Python-based REPL:

```bash
# Start the REPL
uv run libspec repl
```

Within the REPL, type `help` to list commands. You can run:
*   `list-snapshots` — view historic iterations.
*   `show spec.app.App` — inspect detailed relationships.
*   `search Hello` — search specifications dynamically.
*   `exit` — exit the interactive prompt.

---

## Next Steps

Now that you have initialized a spec and recorded your first snapshot, proceed to the [Using the MCP Server](../how-to/agents.md) guide to hook up your specs directly to an LLM developer agent!
