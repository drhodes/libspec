"""
Specification for Diátaxis-compliant technical documentation architecture.
Derived from Diátaxis (https://diataxis.fr) systematic documentation framework.
"""

from .err import Feat, Req


class DiataxisFramework(Feat):
    """
    Technical documentation must be structured around Diátaxis, a systematic
    framework organizing content based on four distinct user needs across two
    fundamental dimensions:
    - Action vs. Cognition (doing vs. knowing)
    - Acquisition vs. Application (study vs. work)

    The framework defines four discrete documentation forms: Tutorials, How-To
    Guides, Reference, and Explanation. Each quadrant serves a unique purpose and
    must maintain strict boundary separation.
    """


class TutorialsQuadrant(Feat):
    """
    Tutorials are learning-oriented lessons designed for students acquiring new skills.

    Requirements:
    - Practical & Action-Oriented: The learner acquires skills by doing a meaningful activity.
    - Instructor Responsibility: The tutorial must guarantee safety and success for the student.
    - Narrative of Expectation: Every step must describe what the user should notice and expect.
    - Minimal Explanation: High-level concepts must be deferred; focus remains strictly on execution.
    """


class TutorialPedagogyReq(Req):
    """
    Tutorials must adhere to strict pedagogical principles:
    - Show the destination upfront: Clearly state what will be built or accomplished.
    - Deliver results early and often: Every action must produce a visible, meaningful outcome.
    - Ruthlessly minimize explanation: Do not interrupt learning flow with background theory; link to Explanation docs instead.
    - No options or choices: Provide a single deterministic, foolproof path to guarantee 100% reliability.
    """


class QuickstartTutorialReq(Req):
    """
    `docs/tutorials/quickstart.md` must provide a step-by-step hands-on tutorial:
    - Guides a new user from installing libspec to writing their first specification class (`spec/my_spec.py`).
    - Instructs user on running `libspec build`, inspecting `libspec diff`, and interfacing with an LLM agent via MCP.
    """


class HowToGuidesQuadrant(Feat):
    """
    How-To Guides are goal-oriented directions designed for already-competent users at work.

    Requirements:
    - Problem-Focused: Address specific real-world tasks or operational problems.
    - Adaptable & Logical: Present executable action sequences adaptable to user use-cases.
    - Zero Teaching: Assume domain competence; focus exclusively on completing the task.
    - Explicit Naming: Titles must clearly state the outcome (e.g. `How to configure...`).
    """


class HowToGuideExecutionReq(Req):
    """
    How-To Guides must follow strict execution rules:
    - Start and end at logical boundaries: Avoid end-to-end tutorial handholding.
    - Omit the unnecessary: Exclude basic operational knowledge and deep conceptual theory.
    - Focus on human projects: Frame instructions around human goals rather than tool mechanics.
    """


class InstallationGuideReq(Req):
    """
    `docs/how-to/install.md` must provide concise installation and setup directions:
    - Details package installation via `uv add libspec` (or `pip install libspec`).
    - Instructs user on initializing project configuration via `libspec init`.
    """


class AgentWorkflowGuideReq(Req):
    """
    `docs/how-to/agent-workflow.md` must detail the 9-step developer agent loop:
    - Documents `uv run libspec agent-workflow` execution across agent platforms.
    - Outlines step-by-step guidelines from spec editing to spec diffing, TDD, implementation, code quality verification, SemVer version bumping, and commit presentation.
    """


class SpecDiffingGuideReq(Req):
    """
    `docs/how-to/diffs.md` must document specification diffing practices:
    - Explains multi-commit feature branch diffing against base branches (e.g. `main`).
    - Explains Git commit resolution vs specification-specific revision indexing (`#N` / `@N`).
    - Clarifies why raw Git relative offsets (like `HEAD~1`) may yield empty diffs when non-spec commits intervene.
    """


class ReplGuideReq(Req):
    """
    `docs/how-to/repl.md` must document the interactive REPL shell:
    - Explains snapshot indexing (`#0`, `#1`), time-travel exploration (`enter`/`leave`), and diffing workflows.
    - Documents successor shortcuts (`@N`) and spec-filtered history indexing.
    """


class ReferenceQuadrant(Feat):
    """
    Reference documentation contains information-oriented, technical descriptions of product machinery.

    Requirements:
    - Austere & Authoritative: Purely factual, accurate, and complete descriptions without distraction.
    - Mirror Product Architecture: The documentation structure must mirror the codebase / API structure.
    - Neutral Description: Free of instructions, tutorials, opinions, or speculative advice.
    - Code Examples: Include concise code snippets demonstrating API signatures without procedural teaching.
    """


class ReferenceNeutralityReq(Req):
    """
    Reference material must maintain strict factual neutrality:
    - State facts about machinery behavior, parameters, return types, and exceptions.
    - Exclude procedural instructions, recommendations, or step-by-step guides; cross-link to How-To Guides instead.
    - Standardize formatting across all classes, functions, CLI flags, and configuration fields.
    """


class CliReferenceReq(Req):
    """
    `docs/reference/cli.md` must document all CLI subcommands, flags, and return codes accurately.
    """


class McpReferenceReq(Req):
    """
    `docs/reference/mcp.md` must document all FastMCP tools and resource URIs exposed by the libspec MCP server.
    """


class ApiReferenceReq(Req):
    """
    `docs/reference/api.md` must document the core Python API classes (`Spec`, `Feature`, `Requirement`, `Ctx`, `SpecStore`).
    """


class ExplanationQuadrant(Feat):
    """
    Explanation guides provide understanding-oriented background, context, and architectural discussion.

    Requirements:
    - Big Picture View: Explain design choices, history, constraints, and alternative approaches.
    - Discursive & Reflective: Connect concepts together to help users answer *why* decisions were made.
    - Allow Perspectives: Weigh trade-offs, admit opinions, and explore conceptual boundaries.
    - Separated from Action: Keep conceptual discussion distinct from step-by-step how-to directions.
    """


class ExplanationScopeReq(Req):
    """
    Explanatory material must be bounded effectively:
    - Focus on a single conceptual topic (e.g., `About Store Architecture`).
    - Do not embed procedural step-by-step instructions or raw API reference dumps.
    - Provide rich background context to deepen the practitioner's mental model.
    """


class OsmExplanationReq(Req):
    """
    `docs/explanation/osm.md` must explain Object Specification Mapping (OSM) concepts and design rationale.
    """


class ArchitectureExplanationReq(Req):
    """
    `docs/explanation/architecture.md` must explain SpecStore transaction log architecture and SHA-256 content hashing.
    """


class DiataxisCompass(Feat):
    """
    The Diátaxis Compass is a decision matrix used to classify content and resolve boundary ambiguities:

    +-------------------+--------------------+-----------------------+
    |                   | Acquisition (Study)| Application (Work)    |
    +-------------------+--------------------+-----------------------+
    | Action (Doing)    | Tutorial           | How-To Guide          |
    | Cognition (Knowing)| Explanation       | Reference             |
    +-------------------+--------------------+-----------------------+

    Documentation authors must apply the compass to verify that every document belongs strictly to one quadrant.
    """


class DocumentationArchitectureReq(Req):
    """
    The repository's documentation directory structure (e.g. `docs/`) must strictly reflect the Diátaxis quadrants:
    - `tutorials/`: Step-by-step learning lessons.
    - `how-to/`: Task-focused operational guides.
    - `reference/`: Technical description of API, CLI, and configuration options.
    - `explanation/`: Deep-dive architectural background and design rationale.

    Content must not blur boundaries or mix modes across these directories.
    """


class DocsPublishMakefileRule(Feat):
    """
    `Makefile` must contain `docs-publish` (and `docs-build`) targets:
    - `docs-build`: Runs `uv run mkdocs build` to verify local site compilation.
    - `docs-publish`: Runs `uv run mkdocs gh-deploy --force` to deploy compiled documentation to GitHub Pages.
    """


class GhPagesPublishReq(Req):
    """
    Documentation site must be published directly to GitHub Pages (`gh-pages` branch) via `make docs-publish`.
    """
