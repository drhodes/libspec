import projects.cli_tool_project.commands as commands
import projects.cli_tool_project.requirements as requirements
from libspec.spec import Spec


class CliToolSpec(Spec):
    def modules(self):
        return [commands, requirements]
