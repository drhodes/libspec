import os


def resolve_prefix(
    agent: str = None, prefix: str = None, project_root: str = "."
) -> str:
    """
    Resolves the MCP tool prefix based on agent, prefix, or project root auto-detection.
    """
    if prefix is not None:
        return prefix

    if agent:
        agent_lower = agent.lower()
        if agent_lower in ("antigravity", "gemini"):
            return "mcp_libspec_"
        if agent_lower == "claude":
            return ""
        return "libspec_"

    # Auto-detect active agent in project root
    try:
        from libspec.agent_config import AgentConfig

        for agent_id, cls in AgentConfig._registry.items():
            try:
                config = cls(project_root)
                if config.is_active:
                    if agent_id in ("antigravity", "gemini"):
                        return "mcp_libspec_"
                    if agent_id == "claude":
                        return ""
            except Exception:
                pass
    except Exception:
        pass

    return "libspec_"


def get_agent_workflow(pfx: str = "libspec_") -> str:
    """
    Returns the standardized developer agent workflow formatted as markdown
    with the specified tool prefix.
    """
    hooks = {}
    yaml_path = os.path.join(".libspec", "workflow.yaml")
    if os.path.exists(yaml_path):
        import yaml

        try:
            with open(yaml_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data and "hooks" in data:
                    hooks = data["hooks"] or {}
        except Exception:
            pass

    def get_hook_lines(name: str) -> str:
        lines = hooks.get(name, [])
        if not lines:
            return ""
        if isinstance(lines, str):
            lines = [lines]
        return "\n" + "\n".join(f"   * {line}" for line in lines)

    return f"""## Dev Workflow (Phase-Typed & Paradigm-Aware)
1. **Phase 1: Edit Spec [DECLARATIVE]**: Edit/define the requirements/features in the specification files. **Always decompose broad requirements into granular, single-responsibility requirement classes (e.g. `HelpCommandReq`, `SnapshotsCommandReq`) rather than using monolithic requirement blocks to ensure first-class specification footprinting.** Specs DECLARE the system architecture; do not put one-off imperative task steps here.{get_hook_lines("post-edit")}
2. **Phase 2: Diff Spec (MANDATORY BEFORE CODING) [DECLARATIVE -> IMPERATIVE]**: You **must absolutely** run a spec diff using either the `{pfx}diff` MCP tool or the `uv run libspec diff` command to identify specification drift, review mutations, and compile component deltas into structured imperative action prompts before coding begins.{get_hook_lines("pre-diff")}{get_hook_lines("post-diff")}
3. **Phase 3: Sort Implementation Ordering [IMPERATIVE]**: Inspect component dependencies via the `{pfx}dependencies` tool or `uv run libspec dependencies` command to sort components into topological implementation order, ensuring foundational requirements are built before dependent features.{get_hook_lines("post-dependencies")}
4. **Phase 4: Test Driven Development [IMPERATIVE - Contract Driven]**: Follow best practices in test driven development to write unit and integration tests for the components in topological dependency order, formalizing the declarative acceptance criteria before writing production code.
5. **Phase 5: Implement [IMPERATIVE - Goal Directed]**: Implement the components to ensure the tests pass and satisfy the declared specification contracts.{get_hook_lines("post-implement")}
6. **Phase 6: Code Quality & Verification [IMPERATIVE]**: Run static analysis, linting, formatting, and dead code checks according to the project's guidelines.{get_hook_lines("pre-commit")}
7. **Phase 7: Verify Specification Sync [DECLARATIVE]**: Run a spec diff using the `{pfx}diff` MCP tool or the `uv run libspec diff` command to ensure that the live specifications are fully synchronized with the final implementation and that all changes are accounted for.
8. **Phase 8: Version Bump [IMPERATIVE]**: Bump the project version in `pyproject.toml` according to Semantic Versioning (SemVer: `MAJOR.MINOR.PATCH`). Use helper commands (`make bump-patch`, `make bump-minor`, or `make bump-major`) as appropriate for the change.
9. **Phase 9: Author a git message and present to user [IMPERATIVE]**"""
