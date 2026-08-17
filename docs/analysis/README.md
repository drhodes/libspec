# libspec — Analysis Artifacts

This directory contains auto-generated architectural analysis of the **libspec** project (v10.3.2).

## Contents

| File                                                                  | Description |
|-----------------------------------------------------------------------|-------------|
| [overview.md](overview.md)                                            | Mid-to-high level description of how the application works |
| [class_diagram_core.puml](class_diagram_core.svg)                     | Core `Spec` / `Ctx` class hierarchy |
| [class_diagram_spec_types.puml](class_diagram_spec_types.svg)         | Built-in specification vocabulary types |
| [class_diagram_infrastructure.puml](class_diagram_infrastructure.svg) | CLI, REPL, MCP server, AgentConfig, Watcher |
| [class_diagram_data.puml](class_diagram_data.svg)                     | Data model classes (Component, Snapshot, Implemented) |
| [activity_spec_compilation.puml](activity_spec_compilation.svg)       | How spec files are compiled into Components / XML |
| [activity_diff_workflow.puml](activity_diff_workflow.svg)             | Spec diff swim-lane (user ↔ CLI ↔ Git ↔ engine) |
| [activity_mcp_server.puml](activity_mcp_server.svg)                   | MCP server request-handling swim-lane |
| [activity_agent_workflow.puml](activity_agent_workflow.svg)           | Full agent-driven developer workflow swim-lane |
| [activity_agent_config.puml](activity_agent_config.svg)               | Agent-config installation swim-lane |

## Rendering PlantUML

```bash
# Using the PlantUML JAR
java -jar plantuml.jar docs/analysis/*.puml

# Or, convert .puml to .svg using NPM's plantuml-cli
$ npm i -g plantuml-cli
$ plantuml-cli --svg docs/analysis/*.puml

# Or with the VSCode PlantUML extension — open any .puml file and press Alt+D
```
