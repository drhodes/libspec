
import os
import ast
import re
import logging
from pylsp import hookimpl

log = logging.getLogger(__name__)

class HelloASTError(Exception):
    """Story-driven exception for HelloAST plugin failures."""
    def __init__(self, message, step=None, details=None):
        story = f"HelloAST Plugin Failure: {message}"
        if step:
            story = f"Error during '{step}': {message}"
        if details:
            story += f"\nDetails: {details}"
        super().__init__(story)

@hookimpl
def pylsp_settings(config):
    """Register default settings for HelloAST."""
    assert config is not None, "config cannot be None when registering settings"
    return {"plugins": {"hello_ast": {"enabled": True, "pattern": ".*"}}}

@hookimpl
def pylsp_commands(config, workspace):
    """Register custom commands for HelloAST."""
    return ["hello_ast.scan_workspace"]

@hookimpl
def pylsp_execute_command(config, workspace, command, arguments):
    """Handle custom commands like full workspace scanning."""
    if command == "hello_ast.scan_workspace":
        settings = config.plugin_settings("hello_ast")
        if not settings.get("enabled", True):
            return
        pattern = settings.get("pattern", ".*")
        root = workspace.root_path or os.getcwd()
        
        log.info(f"HelloAST: Starting full workspace scan in {root}")
        
        for dirpath, dirnames, filenames in os.walk(root):
            # Skip common virtual environments and hidden directories
            dirnames[:] = [d for d in dirnames if not d.startswith('.') and d not in ['venv', 'env', '__pycache__']]
            for fname in filenames:
                if fname.endswith(".py"):
                    fpath = os.path.join(dirpath, fname)
                    # workspace.get_document() loads from disk if not open
                    document = workspace.get_document(fpath)
                    _scan_document(document, pattern, workspace)
        
        log.info("HelloAST: Finished full workspace scan.")
        return True

@hookimpl
def pylsp_document_did_open(config, workspace, document):
    """Scan the document for identifiers matching the regex pattern."""
    assert workspace is not None, "workspace cannot be None during document_did_open"
    assert document is not None, "document cannot be None during document_did_open"
    assert getattr(document, "source", None) is not None, "document must have readable source code"

    settings = config.plugin_settings("hello_ast")
    if not settings.get("enabled", True):
        return

    pattern = settings.get("pattern", ".*")
    _scan_document(document, pattern, workspace)

def _scan_document(document, pattern, workspace):
    """Helper function to perform AST parsing and logging on a single document."""
    try:
        regex = re.compile(pattern)
    except re.error as e:
        story = HelloASTError(
            f"The provided regex pattern '{pattern}' is invalid.",
            step="Regex Compilation",
            details=str(e)
        )
        log.error(str(story))
        return

    try:
        tree = ast.parse(document.source)
    except Exception as e:
        story = HelloASTError(
            f"Failed to parse the Python source code for {document.path}.",
            step="AST Parsing",
            details=f"The file may contain syntax errors. Underlying error: {e}"
        )
        log.error(str(story))
        return

    matches = set()
    
    for node in ast.walk(tree):
        name = None
        if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
            name = node.name
        elif isinstance(node, ast.Name):
            name = node.id
        elif isinstance(node, ast.arg):
            name = node.arg
        
        if name and regex.match(name):
            matches.add(name)
    
    if matches:
        output = f"HelloAST: Found {len(matches)} matching identifiers in {document.path} using pattern '{pattern}':\n"
        for m in sorted(matches):
            output += f"  - {m}\n"
        log.info(output)
        
        # Write to a file for explicit verification
        try:
            root = workspace.root_path or os.getcwd()
            out_path = os.path.join(root, "hello_ast_matches.txt")
            with open(out_path, "a") as f:
                f.write(output)
        except IOError as e:
            story = HelloASTError(
                f"Failed to write match results to {out_path}.",
                step="Result Logging",
                details=str(e)
            )
            log.error(str(story))
    else:
        log.info(f"HelloAST: No identifiers matched pattern '{pattern}' in {document.path}")

