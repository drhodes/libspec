# Declaring and Managing Component Dependencies

Specifications are rarely isolated. Changes in a core data contract or classification requirement can affect multiple downstream features. To track this, `libspec` supports two orthogonal dependency axes:

1. **Constraint Inheritance (`inherits`)**: Cross-cutting quality rules and error-handling constraints inherited via standard Python subclassing (e.g. `class MyReq(Req, Err, BoilerPlate):`).
2. **Logical Implementation Dependencies (`depends_on`)**: Explicit DAG edges declared directly on component classes indicating which prerequisite components must be implemented and verified first.

---

## 1. Declaring Logical Dependencies in Python

Declare logical dependencies as a class attribute on your specification components in `spec/*.py`:

```python
# spec/audit.py
from .err import Feat, Req

class OutputSchemaReq(Req):
    """JSON output schema specification for evilbit_audit.json."""
    depends_on = (ProbeClassificationReq,)

class ScannerPersistenceReq(Req):
    """State persistence and scan resumption engine."""
    depends_on = (TargetSelectionReq, ProbeClassificationReq, OutputSchemaReq)

class EvilBitAuditApp(Req):
    """Main audit pipeline application."""
    depends_on = (TargetSelectionReq, ProbeClassificationReq, ScannerPersistenceReq, OutputSchemaReq)
```

### Dependency Rules:
- **Type**: A `tuple` of specification component classes (or FQN strings for forward references).
- **Explicit & Non-Inherited**: `depends_on` defines the logical build order for that specific component and is not silently merged into subclasses.
- **DAG Integrity**: The compiler verifies that dependencies form a valid Directed Acyclic Graph (DAG) with no cycles.

---

## 2. Listing Component Dependencies

To inspect component dependencies for the live specification or a specific Git commit:

```bash
# View dependencies for live spec
uv run libspec dependencies

# View dependencies for a specific Git commit
uv run libspec dependencies -c HEAD~1
```

### Example Output

```text
Component Dependencies for 'HEAD (Live Spec)':
  • spec.audit.ScannerPersistenceReq
    └── depends on: spec.audit.ProbeClassificationReq
    └── depends on: spec.audit.OutputSchemaReq
    └── depends on: spec.audit.TargetSelectionReq
  • spec.viz.DataIngestionReq
    └── depends on: spec.audit.OutputSchemaReq
```

---

## 3. Why Use Specification Dependencies?

1. **Topological Implementation Ordering**: Orchestrator agents use `libspec dependencies --topo` to group components into parallel dependency waves, ensuring foundational requirements are built before dependent features.
2. **Context-Aware Agent Prompts**: When an LLM subagent implements a requirement, the MCP server provides the interfaces and contracts of its prerequisite dependencies.
3. **Impact & Drift Analysis**: Changing a base requirement surfaces all affected downstream components in `libspec diff`.

