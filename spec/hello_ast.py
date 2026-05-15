from spec.err import Feat, Req

class HelloAST(Feat):
    """
    HelloAST — A project-local pylsp plugin for regex-based identifier discovery.
    
    This plugin leverages the Python `ast` module to find all identifiers 
    (variables, function names, class names) that match a specific regex.
    """
    def feature_name(self):
        return "HelloASTIdentifierSearch"

class PluginDiscovery(Req):
    """The plugin must be located at `.libspec/plugins/hello_ast.py` to be automatically loaded."""

class RegexConfiguration(Req):
    """The plugin must support a `pattern` setting via pylsp configuration."""

class ASTParsing(Req):
    """The plugin must use the `ast` module to traverse the source tree and extract identifiers."""

class WorkspaceScanning(Req):
    """The plugin must be able to scan the entire workspace when triggered."""
