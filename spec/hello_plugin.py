'''
Specification for the HelloPlugin pylsp plugin.
'''

from .err import Feat, Req


class HelloPlugin(Feat):
    '''A minimal pylsp plugin that says hello to every file in the workspace.

    The plugin should:
    1. Hook into the document open event.
    2. Log a "Hello" message identifying the file being opened.
    3. Support dynamic configuration/control via the MCP server.
    '''


class HelloPluginMcpControl(Feat):
    '''The `libspec_hello_plugin` MCP tool allows the agent to interact with
    the HelloPlugin.

    Parameters:
    - action (str, optional): The action to perform (e.g., "status", "enable",
      "disable"). If omitted, defaults to "status".

    Returns a JSON-formatted string indicating the current status of the
    HelloPlugin or the result of the requested action.
    '''
    feature_name = "HelloPluginMcpControl"
