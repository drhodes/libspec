"""
Main spec.
"""

from libspec import Spec
from . import (
    app,
    core,
    cli,
    diff,
    types,
    mcp,
    utils,
    lsp_auto_init,
    hello_plugin,
    hello_ast,
    store,
    json_lines_store,
    store_compaction,
    repl,
)


class MainSpec(Spec):
    def modules(self):
        return [
            app,
            core,
            cli,
            diff,
            types,
            mcp,
            utils,
            lsp_auto_init,
            hello_plugin,
            hello_ast,
            store,
            json_lines_store,
            store_compaction,
            repl,
        ]
