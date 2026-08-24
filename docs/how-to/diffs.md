# Feature Branch & Multi-Commit Specification Diffing

When developing on a feature branch with incremental commits (e.g., implementing in stages from Tier 1 through Tier 4), running a default `uv run libspec diff` after committing will output `No changes detected` because `HEAD` matches the live specification files on disk.

To track the **cumulative specification footprint and evolution across intermediate commits** on a feature branch, diff back to the base branch or starting commit reference (such as `main` or `master`).

---

## 1. Diffing Against Base Branch (`main`)

To view all specification changes, additions, and docstring modifications introduced across your feature branch relative to `main`:

```bash
# Diff live specification against base branch (main)
uv run libspec diff main

# Diff live specification against a specific commit hash
uv run libspec diff d777f29
```

This technique ensures that:
* Newly added requirement classes and features are tracked across multi-commit development cycles.
* Uncommitted and committed spec changes are compared holistically against the base branch before merging.

---

## 2. Git Commits vs. Specification Builds

`libspec` distinguishes between **repository-wide Git commits** and **specification builds**:

* **Specification Builds (`@0`, `@1`, ...)**: `libspec` indexes only the Git commits that actually modified files inside the `spec/` directory.
  * `@0` refers to the latest committed specification build.
  * `@1` refers to the specification build immediately preceding `@0`.
  * `@N` refers to $N$ specification builds prior to `@0`.
* **Git Commits (`HEAD`, `HEAD~1`, `commit_sha`)**: Standard Git revision references count every single commit across the entire repository, including CI changes, dependency lockfile updates, merge commits, and non-spec documentation changes.

### Why `diff HEAD~1` Can Output "No changes detected"

When running a single-argument diff like `uv run libspec diff <ref>` (or `diff <ref>` in the REPL):
1. `<ref>` is resolved as the **old snapshot**.
2. The **new snapshot** defaults to `@0` (the latest recorded specification build).

If the intermediate commits between `<ref>` and `HEAD` (such as `HEAD~1` or merge commits) did **not** modify files in `spec/`:
* The specification tree at `HEAD~1` is identical to `@0`.
* Comparing `HEAD~1` $\rightarrow$ `@0` results in `No changes detected`.

### Recommended Practices

* **To compare consecutive specification versions**: Use relative snapshot indexing (e.g. `diff @1`) rather than raw Git offsets (`HEAD~1`). Snapshot indexing automatically filters out irrelevant non-spec commits.
* **To compare the current branch against a base branch**: Run `uv run libspec diff main`.
* **To compare two specific Git revisions**: Provide both explicit commit references, e.g. `uv run libspec diff HEAD~3 HEAD`.

---

## 3. Incorporating into Developer Agent Workflows

When guiding an LLM coding agent (via MCP or CLI), instruct the agent to run:

```bash
uv run libspec diff main
```

This provides the agent with the complete specification delta for the entire feature branch rather than just uncommitted changes in the latest working tree step.

