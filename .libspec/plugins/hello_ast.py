
import os
import ast
import re
import logging
from pylsp import hookimpl

log = logging.getLogger(__name__)

@hookimpl
def pylsp_settings(config):
    """Register default settings for HelloAST."""
    return {"plugins": {"hello_ast": {"enabled": True, "pattern": ".*"}}}

@hookimpl
def pylsp_document_did_open(config, workspace, document):
    """Scan the document for identifiers matching the regex pattern."""
    settings = config.plugin_settings("hello_ast")
    if not settings.get("enabled", True):
        return

    pattern = settings.get("pattern", ".*")
    try:
        regex = re.compile(pattern)
    except re.error as e:
        log.error(f"HelloAST: Invalid regex pattern '{pattern}': {e}")
        return

    try:
        tree = ast.parse(document.source)
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
            with open(os.path.join(workspace.root_path or os.getcwd(), "hello_ast_matches.txt"), "a") as f:
                f.write(output)
        else:
            log.info(f"HelloAST: No identifiers matched pattern '{pattern}' in {document.path}")

    except Exception as e:
        log.error(f"HelloAST: Failed to parse AST for {document.path}: {e}")
