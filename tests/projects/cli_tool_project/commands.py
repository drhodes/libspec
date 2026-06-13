from libspec.spec import CmdLine


class GitWrapperCmd(CmdLine):
    """
    Command Line Specification for Git Wrapper
    """

    def status(self):
        """Show the status of the repository."""
        return "Clean working tree"

    def commit(self, message: str):
        """Commit changes with a message."""
        return "Committed successfully"
