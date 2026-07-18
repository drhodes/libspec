"""
Main spec.
"""

from libspec import Spec

from . import (
    app,
    cli,
    code_quality,
    colors,
    commands,
    core,
    diff,
    git_hooks,
    hello_ast,
    hello_plugin,
    lsp_auto_init,
    mcp,
    repl,
    store,
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
            repl,
            colors,
            git_hooks,
            code_quality,
            commands,
        ]
