from unittest.mock import patch
from libspec.mcp_server import list_components, show_component, list_dependencies
from libspec.common import Component


def test_mcp_metadata_tools():
    mock_comp = Component(
        ref="spec.app.App",
        docstring="Application entrypoint",
        is_template=False,
        inherits=[],
        hash="a" * 64,
    )

    # 1. Test list_components
    with patch(
        "libspec.util.compile_live_spec",
        return_value=([mock_comp], "spec/main_spec.py"),
    ):
        res = list_components()
        assert "spec.app.App" in res
        assert "PENDING" in res

    # 2. Test list_components with commit
    with patch("libspec.util.compile_git_spec", return_value=[mock_comp]):
        res = list_components(commit="HEAD~1")
        assert "spec.app.App" in res
        assert "Git Ref: HEAD~1" in res

    # 3. Test show_component
    with patch(
        "libspec.util.compile_live_spec",
        return_value=([mock_comp], "spec/main_spec.py"),
    ), patch(
        "libspec.util.find_implementations_in_workspace", return_value=[]
    ):
        res = show_component("spec.app.App")
        assert "Reference:   spec.app.App" in res
        assert "No implementation claims found" in res

    # 4. Test list_dependencies
    mock_dep_comp = Component(
        ref="spec.app.Sub",
        docstring="Sub component",
        is_template=False,
        inherits=["spec.app.App"],
        hash="b" * 64,
    )
    with patch(
        "libspec.util.compile_live_spec",
        return_value=([mock_comp, mock_dep_comp], "spec/main_spec.py"),
    ):
        res = list_dependencies()
        assert "Component Dependencies for 'PENDING (Live Spec)'" in res
        assert "spec.app.Sub" in res
        assert "└── depends on: spec.app.App" in res
