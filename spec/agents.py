"""
Specification for workspace .agents directory, skill installation, drift detection, and self-healing.
"""

from .err import Feat, Req


class AgentsDirectoryLayoutReq(Req):
    """
    The libspec platform recognizes the workspace `.agents/` directory as a primary
    customization root for AI agent skills and configuration.

    Path & Boundary Requirements:
    1. Discovery & Boundary Guards:
       - `.agents/` must be located directly at the project root (`os.path.join(project_root, ".agents")`).
       - If `.agents` exists as a regular file (instead of a directory) or is a dangling symlink,
         libspec must raise a clear `ValueError` diagnostic explaining the filesystem conflict.
       - Path traversal protection: Skill resolution must ensure symlinks do not escape the project boundary.

    2. Directory Hierarchy:
       - `.agents/skills/libspec/`: Canonical target directory for libspec agent workflow skills.
       - Backward Compatibility / Alias: Discovers legacy `.agents/skills/libspec-agent-workflow/` if present.
    """


class AgentsSkillValidationReq(Req):
    """
    Skill rendering, installation, and atomic file safety for `.agents`.

    Validation & File System Safety Rules:
    1. Atomic Installation:
       - Skill content must be rendered via Jinja2 templates and written to a process-isolated
         temporary file (e.g., `.agents/skills/libspec/TEMP_<pid>_SKILL.md`).
    2. Validation Enforcement:
       - The rendered content must be parsed using `SkillParser` to confirm valid YAML frontmatter
         (`name`, `description`) and markdown structure before replacing the active `SKILL.md`.
       - Rejects empty (0-byte) files, non-UTF-8 encodings, or invalid YAML metadata.
    3. Backup & Rollback:
       - If an existing `SKILL.md` is present, a backup (`SKILL.md.bak`) must be preserved prior to atomic rename.
       - If validation fails, the temporary file must be cleaned up, the original `SKILL.md` preserved,
         and a descriptive `ValueError` raised explaining the skill integrity failure.
    """


class AgentsSkillDriftDetectionReq(Req):
    """
    Drift detection for `.agents` skills on startup (CLI or MCP server initialization).

    Robustness & Comparison Rules:
    1. File Type Guard:
       - Verifies that `.agents/skills/libspec/SKILL.md` exists and is a regular file.
       - If `SKILL.md` is a directory or broken link, treats the skill state as drifted/corrupted.
    2. Normalized Comparison:
       - Normalizes line endings (LF vs CRLF) and trailing whitespace when comparing installed `SKILL.md`
         content against rendered template content to prevent false-positive drift warnings across platforms.
    3. Customization Protection:
       - If the installed `SKILL.md` contains the directive comment `libspec: disable-auto-heal`,
         drift detection marks the skill as customized and bypasses auto-healing to preserve manual edits.
    """


class AgentsSkillHealingFeat(Feat):
    """
    Auto-healing and graceful error recovery for `.agents` skills.

    Resiliency & Error Handling Rules:
    1. Auto-Healing Execution:
       - When `auto_heal` is enabled (default in MCP startup and CLI skill check), missing or drifted skills
         under `.agents/skills/libspec/` are automatically re-rendered and updated (unless user opt-out header is set).
    2. Permission & Read-Only Graceful Recovery:
       - If `.agents/` or its subdirectories have read-only permissions (`EACCES`/`EPERM`), healing must catch
         the exception, log a diagnostic warning explaining the permission failure, and allow the application
         to continue running rather than crashing the process.
    3. Concurrency Protection:
       - Process-isolated temporary files ensure multiple concurrent `libspec` invocations do not corrupt
         `SKILL.md` during simultaneous healing.
    """

    feature_name = "AgentsSkillHealingFeat"


class DeclarativeSpecBoundaryReq(Req):
    """
    The `./spec` directory contains strictly declarative specifications representing
    the enduring architectural blueprint of the system.

    Declarative Scope & Boundary Rules:
    1. Declarative Nature:
       - Specifications in `./spec` declare WHAT the system is, its interface contracts,
         invariants, data schemas, constraints, and behavioral guarantees.
       - Declarations describe the target state that the codebase must satisfy.
    2. Imperative Exclusion:
       - Transient, procedural, or one-off imperative tasks (e.g. "fix bug X", "add method Y
         to file Z", temporary migration scripts) MUST NOT be stored within `./spec`.
       - Keeps `./spec` clean, version-stable, and unpolluted by historical construction residue.
    """


class ImperativePromptModelReq(Req):
    """
    Imperative prompts represent transient, procedural, and disposable instructions
    dispatched to coding agents to perform discrete actions.

    Imperative Prompt Lifecycle:
    1. Operational Scope:
       - Imperative prompts specify concrete file paths, line edits, test assertions,
         and execution steps driving mutations toward declarative goals.
    2. Ephemeral Nature:
       - Imperative prompts are disposable; once executed and verified by tests, the
         codebase satisfies the declarative contract and the imperative prompt is retired.
    3. Non-Colocation:
       - Imperative prompts are dispatched dynamically over MCP or agent channels and
         do not live as first-class specifications in `./spec`.
    """


class WorkflowPhasePromptTypingReq(Req):
    """
    Prompts within the libspec development lifecycle are classified by a two-axis type system:
    Workflow Phase (where we are) and Execution Paradigm (declarative vs. imperative).

    Phase & Paradigm Taxonomy:
    1. Phase 1: Edit Spec (`spec_declaration`) -> DECLARATIVE paradigm.
    2. Phase 2: Diff Spec (`diff_compilation`) -> DECLARATIVE to IMPERATIVE translation.
    3. Phase 3: Sort Implementation Ordering (`topological_scheduling`) -> IMPERATIVE sequencing.
    4. Phase 4: Test Driven Development (`tdd_formulation`) -> IMPERATIVE (contract-driven).
    5. Phase 5: Implement (`code_generation`) -> IMPERATIVE (goal-directed).
    6. Phase 6: Code Quality & Verification (`quality_verification`) -> IMPERATIVE.
    7. Phase 7: Verify Specification Sync (`spec_reconciliation`) -> DECLARATIVE.
    8. Phase 8: Version Bump (`version_release`) -> IMPERATIVE.
    9. Phase 9: Commit & Present (`vcs_commit`) -> IMPERATIVE.
    """


class DispatcherGeneratorRoleReq(Req):
    """
    Clear cognitive role separation between dispatching (orchestrating) agents
    and generating (worker) agents.

    Role Separation Rules:
    1. Dispatching Agent (Orchestrator):
       - MUST understand both the active Workflow Phase and the Execution Paradigm (Declarative vs Imperative).
       - Ingests declarative architecture (`./spec`), dependency DAGs (`depends_on`), and MRO constraints (`inherits`).
       - Translates spec deltas into topological waves of typed imperative prompt envelopes for subagents.
       - Reconciles worker output and verifies full specification synchronization.
    2. Generating Agent (Worker):
       - Receives targeted, self-contained prompt envelopes to execute localized TDD, implementation, or QA.
       - Focuses on satisfying the immediate contract and passing verification gates without needing global state.
    """


class DiffImperativeBridgeFeat(Feat):
    """
    The `libspec diff` engine serves as the compiler bridging declarative specifications
    and imperative code generation.

    Bridge Transformation:
    1. Delta Synthesis:
       - Compares the declarative target in `./spec` against baseline Git revisions or live codebase state.
    2. Actionable Output:
       - Formulates component mutations (`[NEW]`, `[CHANGED]`, `[REMOVED]`) into structured imperative
         action prompts with step sequences, target file hints, prerequisite contracts, and verification commands.
    """

    feature_name = "DiffImperativeBridgeFeat"
