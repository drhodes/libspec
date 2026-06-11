# Integrating with LLM Coding Agents via MCP

`libspec` features a Model Context Protocol (MCP) server that exposes specification tools directly to LLM agents (such as Antigravity, Claude Desktop, Cursor, Cline, or Copilot). This allows the agent to fetch context, search spec components, view diffs, and inspect dependencies natively during a session.

---

## Supported Agents for Auto-Configuration

`libspec` can automatically configure the following coding environments:
*   `antigravity` (Antigravity IDE Agent)
*   `gemini` (Gemini CLI)
*   `claude` (Claude Desktop & Claude Code)
*   `copilot` (GitHub Copilot)
*   `opencode` (OpenCode Agent)
*   `codex` (Codex IDE)

---

## 1. Automated Configuration

To configure your agent of choice, run the `agent-config` (or alias `mcp_agent`) command. Always prefix with `uv run` to ensure correct virtual environment context:

```bash
# List supported agents
uv run libspec agent-config --list

# Configure a specific agent (e.g., Antigravity)
uv run libspec agent-config antigravity
```

This automated step:
1.  Locates your local virtual environment's `uv` executable path.
2.  Creates or updates the agent's MCP configuration directory (e.g., `.gemini/antigravity/mcp_config.json` for Antigravity, `.github/mcp.json` for Copilot, or `.claudesettings.json` for Claude).
3.  Injects the `libspec mcp` tool command payload pointing to the current directory.
4.  Installs a custom **SKILL.md** file containing prompt context guidelines to teach the LLM how and when to invoke `libspec` tools.

---

## 2. Skill Drift & Self-Healing

LLM agent prompts require precise instruction schemas (skills). To prevent prompts from becoming outdated as the core library evolves:
*   On every command invocation (e.g., `libspec diff`), `libspec` scans your workspace's active configurations.
*   If it detects a missing or outdated `SKILL.md` (comparing the hash against package templates), it automatically **auto-heals** the file in place.
*   This ensures the agent always receives the latest specification guidelines.

---

## 3. Manual Configuration

If your developer agent is not listed in the auto-config registry, you can configure it manually by pointing to the standard I/O command:

```json
{
  "mcpServers": {
    "libspec": {
      "command": "uv",
      "args": ["run", "libspec", "mcp"],
      "cwd": "/path/to/your/project"
    }
  }
}
```

Ensure that your agent is run in the root of your workspace (the directory containing `.libspec/`).

---

## Available MCP Tools

Once connected, your coding agent gains access to the following tools:

| MCP Tool Name | Description |
|---|---|
| `mcp_libspec_search` | Search specification components and docstrings by query string. |
| `mcp_libspec_show_component` | View complete details (docstring, inheritance, claims) of a component. |
| `mcp_libspec_list_components` | List all components recorded inside a target snapshot. |
| `mcp_libspec_diff` | Diff the live (pending) specifications against historical snapshots. |
| `mcp_libspec_list_snapshots` | List chronological snapshot history. |
| `mcp_libspec_declare_dependency` | Establish a logical dependency between components. |
| `mcp_libspec_list_dependencies` | View recorded component dependencies. |
