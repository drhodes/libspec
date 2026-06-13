import projects.database_project.schemas as schemas
from libspec.spec import Spec


class DatabaseSpec(Spec):
    def modules(self):
        return [schemas]
