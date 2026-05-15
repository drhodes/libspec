'''
Specification for the HelloPlugin pylsp plugin and project-local plugin loading.
'''

from .err import Feat, Req


class ProjectLocalPlugins(Req):
    '''libspec must support loading project-local pylsp plugins from
    `<project-root>/.libspec/plugins/`.

    This is the core mechanism that allows a project to ship its own
    pylsp diagnostics, linters, and hovers without modifying the global
    libspec package.

    The loading strategy must NOT rely on entry points for per-file
    discovery, since entry points require package installation. Instead,
    the existing registered libspec pylsp plugin (`libspec.pylsp_plugin`)
    acts as a "loader" that dynamically imports and registers project-local
    plugins at pylsp startup time.

    Loading sequence:
    1. On `pylsp_initialize`, discover all `*.py` files in
       `<workspace-root>/.libspec/plugins/`.
    2. Add `.libspec/plugins/` to `sys.path` if not already present.
    3. `importlib.import_module` each discovered file by its stem name.
    4. Call `workspace._config._plugin_manager.register(module)` to register
       each module as a pluggy plugin.

    If a file fails to import or register, a descriptive warning must be
    logged; it must not crash the LSP server.
    '''


class HelloPlugin(Feat):
    '''A minimal project-local pylsp plugin that says hello to every file
    in the workspace.

    HelloPlugin is the canonical example plugin. It ships as a template
    at `.libspec/plugins/hello_plugin.py` inside the project being served,
    NOT as a module bundled inside the libspec package.

    The plugin should:
    1. Hook into `pylsp_document_did_open`.
    2. Log a "Hello" message identifying the file being opened.
    3. Support dynamic enable/disable via the `libspec_pylsp_plugin` MCP tool.
    '''


class PluginMcpControl(Feat):
    '''The `libspec_pylsp_plugin` MCP tool allows the agent to interact with
    any pylsp plugin by name.

    Parameters:
    - plugin_name (str): The name of the plugin to control (e.g., "hello", "pyflakes").
    - action (str, optional): The action to perform (e.g., "status", "enable",
      "disable"). If omitted, defaults to "status".

    Returns a JSON-formatted string indicating the current status of the
    requested plugin or the result of the requested action.
    '''
    feature_name = "PluginMcpControl"


class PluginLoaderInit(Feat):
    '''The plugin loader must be triggered on `pylsp_initialize` so that
    all project-local plugins are registered before any document events fire.

    The workspace root is resolved from the LSP `rootUri` parameter passed
    to `pylsp_initialize`.
    '''
    feature_name = "PluginLoaderInit"
