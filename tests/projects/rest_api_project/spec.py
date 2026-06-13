import projects.rest_api_project.api as api
import projects.rest_api_project.models as models
from libspec.spec import Spec


class RestAPISpec(Spec):
    def modules(self):
        return [models, api]
