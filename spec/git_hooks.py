"""
Specification for the Git Hooks integrations in libspec.
"""

from .err import Feat, Req


class GitHooks(Feat):
    """
    The libspec platform supports Git hook integrations to ensure project state and specs,
    specifications, and database snapshots are kept consistent and synchronized
    with version control system commits.
    """


class PreCommitJsonlStaged(Req):
    """
    To prevent database updates and spec snapshot history from getting out-of-sync
    with the source code commits, a Git pre-commit hook must be provided to ensure
    that the `.libspec/libspec.jsonl` database log file is staged for commit whenever
    it has unstaged modifications.

    Hook requirements:
    1. Location and trigger:
       - The pre-commit hook script must be installed/executable at `.git/hooks/pre-commit`.

    2. Mod-check and staging enforcement:
       - The hook must inspect the git repository's current status.
       - If `.libspec/libspec.jsonl` has unstaged changes (e.g. modified in the working tree
         but not staged in the index), it must abort the commit.
       - If `.libspec/libspec.jsonl` is untracked (e.g. newly created but not staged), it
         must abort the commit.

    3. Aborting the commit:
       - To abort the commit, the hook script must exit with a non-zero exit code (e.g., exit 1).

    4. Diagnostic Error Message:
       - When aborting, the hook must print a detailed error message to stderr explaining
         exactly why the commit was aborted and how the user can resolve the issue (e.g.,
         explaining that `.libspec/libspec.jsonl` has unstaged changes and instructing the
         user to run `git add .libspec/libspec.jsonl` before committing).
    """
# dummy comment spec
