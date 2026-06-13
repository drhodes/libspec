"""
Main spec.
"""

from libspec import Spec

from . import (
    app,
    cli,
    code_quality,
    colors,
    core,
    diff,
    git_hooks,
    hello_ast,
    hello_plugin,
    json_lines_store,
    lsp_auto_init,
    mcp,
    repl,
    store,
    store_compaction,
    types,
    utils,
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
            colors,
            git_hooks,
            code_quality,
        ]
