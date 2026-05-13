'''
main spec
'''

from libspec import Spec
from . import app, core, cli, diff, types, mcp, utils

class MainSpec(Spec):
    def modules(self):
        return [app, core, cli, diff, types, mcp, utils]

if __name__ == "__main__":
    MainSpec().write_xml("spec-build")
