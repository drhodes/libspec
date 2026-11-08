"""
Spec diff engine specifications using Git history.
"""

from .core import SpecBase
from .dependencies import TopologicalImplementationOrderingFeat
from .err import Feat, Req
from .store import DecoupledCommonTypes
from .utils import SpecDiscovery


class NativeHashFastPath(Feat):
    """
    When comparing an old component and a new component with the same `ref`,
    if their `hash` values are strictly equal, the component is skipped instantly.

    This ensures exact hash equivalence defines component identity without
    resorting to textual or field-by-field comparisons. To ensure soundness,
    a component's hash must cover both its own contents and its full inheritance
    ancestry.
    """

    deps = [SpecBase, DecoupledCommonTypes]


class InheritanceInComponentHashReq(Req):
    """
    The canonical hash of a specification component must seal its ordered
    inheritance ancestry in addition to its own docstring and dependencies.

    Each component's final hash is computed by combining its own local hash with
    its ancestors' local hashes in ordered MRO sequence (`comp.inherits`). This ensures:
    - Adding, removing, swapping, or reordering an inherited `Ctx` base changes the hash.
    - Mutating the content or docstring of an inherited ancestor changes the hash of all inheritors.
    - Exact hash equivalence in `NativeHashFastPath` soundly guarantees that neither the
      component nor any of its inherited contracts have changed.
    """

    deps = [NativeHashFastPath]


class SnapshotIdInheritanceSensitivityReq(Req):
    """
    Specification snapshot master hashes and snapshot IDs must be sensitive to
    inheritance mutations.

    Because snapshot IDs are derived from component hashes, any change to a
    component's inheritance hierarchy or ancestor content must produce a distinct
    snapshot ID, ensuring two specifications differing in inherited contracts
    never share the same snapshot ID.
    """

    deps = [InheritanceInComponentHashReq]


class CacheVersionInvalidationReq(Req):
    """
    The specification compilation cache (`.libspec/cache`) must incorporate the
    libspec package version in its cache keys and live fingerprints.

    Changes to the package version or hashing algorithms must automatically
    invalidate previously cached artifacts, preventing stale component hashes
    from hiding specification drift after a library upgrade.
    """

    deps = [NativeHashFastPath]


class GitRevisionCompilation(Req):
    """
    To load specifications at a specific historical commit, the diff engine must:
    - Query the Git repository for the spec files at the specified revision.
    - Extract the specification files to a temporary workspace or read their contents
      from the git object database.
    - Load and compile the specifications dynamically in memory.
    """

    deps = [NativeHashFastPath, SpecDiscovery]


class SpecRevisionIndexSyntaxReq(Req):
    """
    Specification revision indexing across all diff interfaces must use the `@N` syntax
    (e.g., `@0` for latest recorded spec build, `@1` for its immediate predecessor, etc.).
    This syntax ensures shell safety across standard command-line environments without
    triggering shell comment parsing or requiring quotation escaping.
    """

    deps = [GitRevisionCompilation]


class GitOffsetDiffHintReq(Req):
    """
    When running a diff specifying Git commit offsets (such as `HEAD~1` or `HEAD~N`)
    where no specification changes are detected, the diff output must display a hint
    suggesting the use of `diff @1` (spec build indexing) to compare against previous specification builds.
    """

    deps = [SpecRevisionIndexSyntaxReq]


class DiffEngine(Req):
    """
    `generate_native_patch(old_commit=None, new_commit=None)` produces a structured diff
    between specification trees at two points in Git history.

    If both arguments are omitted (None), it compiles the live specification files
    in the workspace on the fly and compares them against `HEAD`.

    If only one argument is provided, it diffs it against `HEAD`.

    Output format:
    - A header line: "Diffing State: <old_commit> -> <new_commit>"
    - A separator line of "=" characters.
    - One block per changed/added/removed component, tagged [NEW], [REMOVED],
      or [CHANGED] followed by the component type name.
    - Changed components list each field change as a bullet.
    - A trailing [WARNING] block for any specs with unresolved inherited refs.

    "No changes detected." is printed when there are no diffs, no unresolved
    refs, AND a baseline specification tree was successfully resolved at the old
    revision. Absence of a baseline is a distinct outcome and must never be
    reported as an absence of changes.
    """

    deps = [NativeHashFastPath, GitRevisionCompilation]


class NullSpecDiff(Feat):
    """
    When diffing against a null spec (bootstrap case, or when comparing a snapshot/live spec
    with no preceding commit), the diff runs against an empty list of old components.
    Every component in the new snapshot produces a [NEW] entry.
    """

    deps = [DiffEngine]


class AbsentBaselineDetectionReq(Req):
    """
    Before comparing, the diff engine must explicitly classify whether a baseline
    specification tree exists at the requested revision, distinguishing three
    outcomes that are currently conflated:

    - RESOLVED: spec files were found and compiled at the old revision.
    - ABSENT: the spec module path is untracked or does not exist at that
      revision (a project whose spec has never been committed).
    - UNREADABLE: the files exist but failed to compile at that revision.

    ABSENT is the null-baseline bootstrap case governed by `NullSpecDiff` and
    must be detected structurally, by interrogating the Git object database for
    the spec path, rather than inferred from an empty comparison result.
    """

    deps = [GitRevisionCompilation, NullSpecDiff]


class LiveComparisonFallbackProhibitionReq(Req):
    """
    When a baseline is classified ABSENT or UNREADABLE, the diff engine must not
    substitute the live workspace specification for the old side of the
    comparison. Doing so makes the tree trivially identical to itself and yields
    a false "No changes detected." verdict.

    The header annotation "(identical to live)" is reserved exclusively for a
    RESOLVED baseline whose compiled components genuinely match the live tree.
    """

    deps = [AbsentBaselineDetectionReq]


class NoBaselineReportingReq(Req):
    """
    An ABSENT baseline must be reported as its own labelled outcome, stating that
    no committed specification exists at the revision, that every live component
    is therefore new, and that drift detection begins only once the
    specification is committed.

    This preserves the operator's ability to distinguish "verified in sync" from
    "nothing to verify against", which is the entire value of the diff gate in
    the standard agent workflow.
    """

    deps = [AbsentBaselineDetectionReq, LiveComparisonFallbackProhibitionReq]


class DiffGateExitStatusReq(Req):
    """
    `libspec diff` must communicate baseline classification through its process
    exit status so that Makefile targets, CI pipelines, and coding agents can
    gate on it without parsing prose:

    - Success for a RESOLVED baseline, whether or not drift was found.
    - A distinct non-success status for an ABSENT or UNREADABLE baseline.

    A verification gate that cannot signal "I could not verify" is
    indistinguishable from one that always passes.
    """

    deps = [NoBaselineReportingReq]


class SpecFieldPolymorphism(Feat):
    """
    Diff logic is organized as a hierarchy of SpecField classes, one per
    logical field type. Each subclass implements:
    - `display(seen_values)`: prints the field for the [NEW] case.
    - `diff(old_spec)`: compares with old_spec and returns a change string or
      list of strings, or None if unchanged.

    Field classes:
    - Docstring: compares docstring / docstring_template text using unified diff.
    - Inherits: compares the inherits ref set AND recursively diffs changed
      inherited specs to surface superspec mutations.
    """

    deps = [DiffEngine]


class DocstringDiff(Feat):
    """
    Docstring changes are shown as unified diffs (--- old / +++ new).

    Both <docstring> and <docstring_template> tags are checked; whichever is
    present is used. The diff label is "docstring" for both.

    The `_patch_block()` helper produces the unified diff block with
    fromfile="old/<label>" and tofile="new/<label>" headers.
    """

    deps = [SpecFieldPolymorphism]


class InheritanceDiff(Feat):
    """
    The Inherits field recursively diffs inherited superspecs.

    When the set of inherited refs is identical between old and new, the diff
    engine still checks whether the content of each common inherited spec has
    changed by looking up the ref in old_specs_by_ref and new_specs_by_ref and
    calling `_compare_specs()` recursively.

    A `visited` set prevents infinite loops in circular inheritance graphs.

    If a change is detected in an inherited spec, the message "inherited spec
    '<ref>' changed" is appended to the component's changes.
    """

    deps = [SpecFieldPolymorphism]


class ChangedGuidanceDisplayReq(Req):
    """
    When a component is modified (`[CHANGED]`) and has gained inherited
    specifications, `libspec diff` must display the newly inherited guidance under
    the `inherited_specs (STRICTLY FOLLOW THE GUIDANCE BELOW)` section.

    This ensures that when a requirement gains binding contracts from newly
    inherited classes, the implementer or coding agent receives the full
    guidance inline rather than only a bare ref name.
    """

    deps = [InheritanceDiff, DiffEngine]


class UnresolvedRefWarning(Feat):
    """
    After processing all component diffs, the engine checks for specs that
    inherit refs not present in the current corpus.

    If any are found, a [WARNING] block is printed listing each (component,
    unresolved_ref) pair.
    """

    deps = [DiffEngine]


class NativePatchParameterContract(Req):
    """
    `generate_native_patch` must accept exactly two keyword arguments:
    `old_commit` and `new_commit` (both defaulting to None).

    All call sites must pass these arguments by name. Passing positional-only
    arguments or using an alias such as `new_snap` is not permitted, as it
    causes a TypeError at runtime and silently breaks the `-vv` diff path.
    """

    deps = [DiffEngine]


class DependencyTreeOrdering(Feat):
    """
    The diff engine calculates a topological dependency order across all components
    by resolving inheritance (superspecs) and composition (subspecs).

    `generate_native_patch` renders changed/new components according to this
    dependency tree order (bottom-up / prerequisites-first). Components without
    unmet dependencies are listed first, ensuring that foundational classes or helper
    specs are presented before the higher-level components that rely on them.
    """

    deps = [DiffEngine, TopologicalImplementationOrderingFeat]


class ComponentImplementationOrder(Req):
    """
    When `libspec diff` prints each component block, it includes explicit, actionable
    implementation instructions structured for AI coding agents.

    The component block includes:
    - Step index and topological dependency rank (e.g. `[Step 1/4 - Dependency Rank: 0]`).
    - Explicit list of direct prerequisite specs that must be implemented first.
    - Intra-component implementation sequence (e.g. 1. Base requirements/types, 2. Subspec dependencies, 3. Feature logic).
    - Precise target file path and line hints derived from component source metadata.
    """

    deps = [DependencyTreeOrdering]
