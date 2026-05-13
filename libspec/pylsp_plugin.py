import logging
from pylsp import hookimpl
import jedi
from libspec.spec import Ctx

log = logging.getLogger(__name__)

def _is_ctx_subclass(definition):
    """Check if a jedi definition refers to a Ctx subclass."""
    try:
        # Check if the symbol is a class
        if definition.type != 'class':
            return False
            
        # We look for 'Ctx' in the base classes.
        # This is a bit heuristic but works well for local specs.
        for base in definition.bases():
            if base.name == 'Ctx' or base.name == 'Req' or base.name == 'Feat':
                return True
        return False
    except Exception:
        return False

@hookimpl
def pylsp_hover(config, workspace, document, position):
    """
    Provide hover information for libspec components.
    """
    # Use jedi to find the definition at the current position
    code = document.source
    line = position['line'] + 1
    column = position['character']
    
    script = jedi.Script(code, path=document.path)
    try:
        definitions = script.goto(line, column, follow_imports=True)
        if not definitions:
            return None
            
        d = definitions[0]
        if _is_ctx_subclass(d):
            # It's a libspec component! 
            # We can return its docstring (which contains the requirement)
            doc = d.docstring()
            return {
                'contents': {
                    'kind': 'markdown',
                    'value': f"**libspec component**: {d.name}\n\n---\n\n{doc or 'No requirement defined.'}"
                }
            }
    except Exception as e:
        log.error(f"Error in libspec hover: {e}")
        
    return None

@hookimpl
def pylsp_definitions(config, workspace, document, position):
    """
    Provide definition jumps for libspec components.
    """
    code = document.source
    line = position['line'] + 1
    column = position['character']
    
    script = jedi.Script(code, path=document.path)
    try:
        definitions = script.goto(line, column, follow_imports=True)
        results = []
        for d in definitions:
            if d.module_path:
                results.append({
                    'uri': f"file://{d.module_path}",
                    'range': {
                        'start': {'line': d.line - 1, 'character': d.column},
                        'end': {'line': d.line - 1, 'character': d.column + len(d.name)}
                    }
                })
        return results
    except Exception as e:
        log.error(f"Error in libspec definitions: {e}")
        
    return []

@hookimpl
def pylsp_lint(config, workspace, document):
    """
    Validate libspec requirements (future expansion).
    """
    return []
