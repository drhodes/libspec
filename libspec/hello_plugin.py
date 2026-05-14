import logging
from pylsp import hookimpl

log = logging.getLogger(__name__)

@hookimpl
def pylsp_settings(config):
    """
    Register default settings for the HelloPlugin.
    """
    return {"plugins": {"hello": {"enabled": True}}}

@hookimpl
def pylsp_document_did_open(config, workspace, document):
    """
    Say hello to every file in the workspace when it is opened.
    """
    settings = config.plugin_settings('hello')
    if settings.get('enabled', True):
        log.info(f"Hello World! Document opened: {document.path}")
