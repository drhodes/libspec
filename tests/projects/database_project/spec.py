from libspec.spec import Spec
import projects.database_project.schemas as schemas

class DatabaseSpec(Spec):
    def modules(self):
        return [schemas]
