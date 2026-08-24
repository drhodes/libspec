# Interactive Specification REPL Shell

`libspec` includes a feature-rich, interactive command-line REPL built on top of `prompt-toolkit`. The REPL allows developers to browse snapshots, perform fast searches, drill down into component details, diff versions, and enter historic context scopes.

---

## Starting the REPL

To start the interactive shell, run:

```bash
uv run libspec repl
```

You will be greeted with the interactive prompt:

```text
libspec > 
```

The prompt supports autocomplete (press `Tab`), history navigation (up/down arrow keys), and inline suggestions.

---

## Key REPL Commands

| Command | Usage | Description |
|---|---|---|
| `help` | `help` | Lists all available commands. |
| `list-snapshots` | `list-snapshots` | Displays the list of recorded snapshots, sizes, and active scope markers. |
| `list` | `list` | Lists all specification components in the active snapshot. |
| `show` | `show <component_ref>` | Displays complete details, docstrings, and claims of a component. |
| `search` | `search <query>` | Performs fuzzy searches across component names and docstrings. |
| `diff` | `diff [snap_a] [snap_b] [-v] [-vv]` | Diff two snapshots. `-v` shows unified diffs; `-vv` shows a full semantic patch. |
| `enter` | `enter <index_or_hash>` | Scopes the REPL context to a historical snapshot (e.g. `enter @2` or `enter a1b2c3d4`). |
| `leave` | `leave` | Restores the active context back to the latest snapshot. |
| `compact` | `compact [--dry-run]` | Compacts the SQLite/JSON-Lines database log. |
| `rm-snapshot` | `rm-snapshot <snapshot_id>` | Permanently tombstone/delete a historical snapshot. |
| `restore-snapshot`| `restore-snapshot <snapshot_id>`| Restore a tombstoned snapshot back to the active list. |
| `exit` | `exit` | Closes the REPL session. |

---

## Standard Workflows inside the REPL

### 1. Snapshot Diffing

`libspec` tracks specification builds by filtering Git history to commits that modified `spec/`. In the REPL:
* `@0` refers to the latest recorded specification build.
* `@1` refers to the build immediately before `@0`.
* `@N` is a relative index: `diff @1` compares build `@1` with build `@0`.

#### Common Diff Invocations:

* **Compare uncommitted live spec against latest committed build (`@0`)**:
  ```text
  libspec > diff
  ```
* **Compare previous spec build (`@1`) against latest build (`@0`)**:
  ```text
  libspec > diff @1
  ```
  *(Or with verbose docstring diffs: `diff @1 -v`)*
* **Compare two arbitrary snapshot builds**:
  ```text
  libspec > diff @3 @1
  ```
* **Successor shortcut / relative diff**:
  ```text
  libspec > diff @2 @1
  ```
  *(Diffs `@2` against `@1`)*
* **Full semantic patch report**:
  ```text
  libspec > diff @1 -vv
  ```

### 2. Time-Travel Exploration

If you want to view the specification graph as it existed three builds ago (index `@3` in the snapshot log), you can temporary "enter" that context:

```text
libspec > enter @3
libspec > list
libspec > show spec.app.App
```

All search, list, and show queries will now evaluate inside snapshot `@3` rather than the latest state. To return to the active ledger boundary, type:

```text
libspec > leave
```
