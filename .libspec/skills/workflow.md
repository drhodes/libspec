# Libspec Build / Diff / Implement Workflow

This skill encodes the canonical process for specification-driven development in the libspec repository. Use this workflow whenever modifying or extending project requirements.

## 1. Plan & Spec Update
- Identify the requirement or feature to be added/changed.
- Modify the corresponding Python spec file in the `spec/` directory.
- Ensure the docstrings are descriptive and follow the `spec.err.Err` story-telling pattern.

## 2. Build the Specification
Run the `libspec_build` tool to compile the Python spec into an XML artifact.
- **Tool**: `libspec_build`
- **Arguments**: `spec_file="spec/<filename>.py"`
- **Goal**: Ensure the spec compiles without syntax errors.

## 3. Diff the Changes
Run the `libspec_diff` tool to generate a semantic diff between the previous build and the current one.
- **Tool**: `libspec_diff`
- **Arguments**: `build_dir="spec-build"`
- **Action**: Read the output carefully. It lists:
    - **[NEW]** / **[CHANGED]** components.
    - **inherited_specs**: A critical list of requirements (Err, Robustness, PreCondition, etc.) that MUST be applied to the implementation.
    - **REQUIREMENT-ID**: The ID to be cross-referenced in the source code.

## 4. Implementation
Implement the changes in the `libspec/` directory.
- **Rule 1: Requirement IDs**: Insert the relevant `REQUIREMENT-ID` as a comment in the implementation.
- **Rule 2: Error Stories**: Implement error handling that tells a story, including exception types and context (per `spec.err.Err`).
- **Rule 3: Robustness**: Use `assert` statements for `PreCondition` and `PostCondition` as identified in the diff.
- **Rule 4: Boilerplate**: Look for opportunities to refactor and reduce repetition.

## 5. Verification
- Create or run a test script in `scratch/` (e.g., `python3 scratch/test_feature.py`).
- Ensure the behavior matches the acceptance criteria defined in the spec.
- Check that backups (if applicable) are created correctly.

## 6. Commit
Author a git commit message that summarizes both the spec changes and the implementation details.
