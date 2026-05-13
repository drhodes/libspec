from libspec.spec import Spec
import projects.rest_api_project.models as models
import projects.rest_api_project.api as api

class RestAPISpec(Spec):
    def modules(self):
        return [models, api]
