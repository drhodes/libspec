import logging
import sys
import importlib
import glob
import os
from pathlib import Path
from pylsp import hookimpl
import jedi

log = logging.getLogger(__name__)


def _is_ctx_subclass(definition):
    """Check if a jedi definition refers to a Ctx subclass."""
    assert definition is not None, "definition must not be None"
    try:
        if definition.type != 'class':
            return False
        for base in definition.bases():
            if base.name in ('Ctx', 'Req', 'Feat'):
                return True
        return False
    except Exception:
        return False


@hookimpl
def pylsp_hover(config, workspace, document, position):
    """Provide hover information for libspec components."""
    line = position['line'] + 1
    column = position['character']
    script = jedi.Script(document.source, path=document.path)
    try:
        definitions = script.goto(line, column, follow_imports=True)
        if not definitions:
            return None
        d = definitions[0]
        if _is_ctx_subclass(d):
            doc = d.docstring()
            return {
                'contents': {
                    'kind': 'markdown',
                    'value': f"**libspec component**: {d.name}\n\n---\n\n{doc or 'No requirement defined.'}"
                }
            }
    except Exception as e:
        log.error(
            f"Hover failed for '{document.path}' at line {line}, col {column}. "
            f"Cause: {type(e).__name__}: {e}."
        )
    return None


@hookimpl
def pylsp_definitions(config, workspace, document, position):
    """Provide definition jumps for libspec components."""
    line = position['line'] + 1
    column = position['character']
    script = jedi.Script(document.source, path=document.path)
    try:
        definitions = script.goto(line, column, follow_imports=True)
        return [
            {
                'uri': f"file://{d.module_path}",
                'range': {
                    'start': {'line': d.line - 1, 'character': d.column},
                    'end': {'line': d.line - 1, 'character': d.column + len(d.name)}
                }
            }
            for d in definitions if d.module_path
        ]
    except Exception as e:
        log.error(
            f"Definition lookup failed for '{document.path}' at line {line}, col {column}. "
            f"Cause: {type(e).__name__}: {e}."
        )
    return []


@hookimpl
def pylsp_lint(config, workspace, document):
    """Validate libspec requirements (future expansion)."""
    return []


@hookimpl
def pylsp_initialize(config, workspace):
    """Load project-local pylsp plugins from <workspace-root>/.libspec/plugins/.

    spec.hello_plugin.ProjectLocalPlugins
    spec.hello_plugin.PluginLoaderInit
    """
    _load_project_plugins(workspace)


def _load_project_plugins(workspace):
    """Discover and register all *.py files in .libspec/plugins/.

    spec.hello_plugin.ProjectLocalPlugins
    """
    assert workspace is not None, "workspace must not be None"
    root = _resolve_workspace_root(workspace)
    plugins_dir = os.path.join(root, ".libspec", "plugins")

    if not os.path.isdir(plugins_dir):
        log.debug(f"No project-local plugins directory found at '{plugins_dir}'. Skipping.")
        return

    if plugins_dir not in sys.path:
        sys.path.insert(0, plugins_dir)

    try:
        pm = getattr(workspace._config, "plugin_manager", None) or getattr(workspace._config, "_plugin_manager", None)
        if pm is None:
            raise AttributeError("Neither plugin_manager nor _plugin_manager found.")
    except AttributeError:
        log.warning(
            "Project-local plugin loading failed: could not access the pylsp plugin manager "
            "via workspace._config.plugin_manager. The pylsp API may have changed."
        )
        return

    for path in sorted(glob.glob(os.path.join(plugins_dir, "*.py"))):
        _import_and_register(pm, path, Path(path).stem)


def _import_and_register(pm, path, stem):
    """Import a single plugin module and register it with the plugin manager."""
    assert pm is not None, "plugin manager must not be None"
    assert path, "plugin path must not be empty"
    assert stem, "plugin stem must not be empty"

    try:
        module = importlib.import_module(stem)
    except Exception as e:
        log.warning(
            f"Project-local plugin '{path}' could not be imported. "
            f"Cause: {type(e).__name__}: {e}. "
            "Check the plugin file for syntax errors or missing dependencies."
        )
        return

    try:
        pm.register(module)
        log.info(f"Loaded project-local plugin: {path}")
    except Exception as e:
        log.warning(
            f"Project-local plugin '{path}' was imported but failed to register. "
            f"Cause: {type(e).__name__}: {e}. "
            "Ensure all @hookimpl functions use valid pylsp hook names."
        )


def _resolve_workspace_root(workspace):
    """Resolve the workspace root path from the workspace object.

    Tries root_uri (public), _root_uri (private fallback), then root_path,
    and finally os.getcwd() as a last resort with a warning.

    spec.hello_plugin.ProjectLocalPlugins
    """
    assert workspace is not None, "workspace must not be None"

    root_uri = getattr(workspace, "root_uri", None) or getattr(workspace, "_root_uri", None)
    if root_uri:
        if root_uri.startswith("file://"):
            result = root_uri[len("file://"):]
            assert result, f"Resolved an empty path from root_uri '{root_uri}'."
            return result
        log.warning(
            f"Workspace root_uri '{root_uri}' is not a file:// URI. "
            "Cannot resolve a local path from it; falling back to root_path."
        )

    root_path = getattr(workspace, "root_path", None)
    if root_path:
        assert isinstance(root_path, str), f"root_path is not a string: {root_path!r}."
        return root_path

    cwd = os.getcwd()
    log.warning(
        "Could not determine workspace root from the workspace object "
        f"(no root_uri or root_path). Falling back to cwd: '{cwd}'. "
        "Project-local plugins may be loaded from the wrong directory."
    )
    assert cwd, "os.getcwd() returned an empty string."
    return cwd
