"""
Main spec.
"""

from libspec import Spec

from . import (
    agents,
    app,
    cli,
    code_quality,
    colors,
    commands,
    core,
    dependencies,
    diff,
    docs,
    mcp,
    repl,
    store,
    types,
    utils,
)


class MainSpec(Spec):
    def modules(self):
        return [
            agents,
            app,
            core,
            cli,
            dependencies,
            diff,
            types,
            mcp,
            utils,
            store,
            repl,
            colors,
            code_quality,
            commands,
            docs,
        ]
