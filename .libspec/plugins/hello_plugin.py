"""
HelloPlugin — project-local pylsp plugin example.

spec.hello_plugin.HelloPlugin

This file lives at <project-root>/.libspec/plugins/hello_plugin.py
and is loaded automatically by libspec's plugin loader on LSP startup.
It is NOT installed as a package entry point.
"""

import logging
from pylsp import hookimpl

log = logging.getLogger(__name__)


@hookimpl
def pylsp_settings(config):
    """Register default settings for HelloPlugin."""
    return {"plugins": {"hello": {"enabled": True}}}


@hookimpl
def pylsp_document_did_open(config, workspace, document):
    """Say hello to every file opened in the workspace."""
    settings = config.plugin_settings("hello")
    if settings.get("enabled", True):
        log.info(f"Hello World! Document opened: {document.path}")
