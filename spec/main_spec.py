'''
main spec
'''

from libspec import Spec
from . import app, core, cli, diff, types, mcp, utils, lsp_auto_init, hello_plugin, hello_ast, store, migration

class MainSpec(Spec):
    def modules(self):
        return [app, core, cli, diff, types, mcp, utils, lsp_auto_init, hello_plugin, hello_ast, store, migration]

if __name__ == "__main__":
    MainSpec().write_xml("spec-build")
