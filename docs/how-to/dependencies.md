# Declaring and Managing Component Dependencies

Specifications are rarely isolated. Changes in a core security policy requirement can affect multiple feature implementations. To track this, `libspec` enables you to declare logical dependencies between specification components.

These dependencies are recorded directly inside the SpecStore transaction log as logical links, keeping your Python source files clean and free of dependency wiring boilerplate.

---

## 1. Declaring a Dependency

To declare that one specification component depends on another, use the `declare-dependency` command. By default, the command scopes the dependency to the `PENDING` (live) state:

```bash
# syntax: uv run libspec declare-dependency <dependent_ref> <depends_on_ref>
uv run libspec declare-dependency spec.app.App spec.err.Err
```

### Scoping to a Snapshot

You can also record dependencies against a specific historic snapshot by using the `-s` / `--snapshot` option:

```bash
# Declare dependency scoped to snapshot d1b3a5f7
uv run libspec declare-dependency spec.app.App spec.err.Err -s d1b3a5f7
```

---

## 2. Listing Recorded Dependencies

To view the dependency tree recorded for a given state, use the `dependencies` command:

```bash
# View dependencies for the active PENDING state
uv run libspec dependencies

# View dependencies recorded for a specific historical snapshot
uv run libspec dependencies -s d1b3a5f7
```

### Example Output

When dependencies are active, they print in an indented tree format:

```text
Component Dependencies for 'PENDING':
  • spec.app.App
    └── depends on: spec.err.Err
  • spec.app.CmdLine
    └── depends on: spec.app.App
```

---

## 3. Why Use Specification Dependencies?

1. **Context-Aware Agent Prompts**: When an LLM subagent retrieves a requirement to implement, the MCP server automatically fetches the docstrings of all dependent components (and their inherited mixins) so the agent has complete context.
2. **Impact Analysis**: Easily see which downstream features are affected when a core context (like error handling) is changed.
3. **Execution Scheduling**: Concurrency workers use the dependency graph to sort implementation tasks and run them in parallel without creating file conflicts.
