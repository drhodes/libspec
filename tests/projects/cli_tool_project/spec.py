from libspec.spec import Spec
import projects.cli_tool_project.commands as commands
import projects.cli_tool_project.requirements as requirements

class CliToolSpec(Spec):
    def modules(self):
        return [commands, requirements]
