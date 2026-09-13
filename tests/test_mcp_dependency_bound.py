import tomllib
from pathlib import Path

from packaging.requirements import Requirement

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def _mcp_requirement() -> Requirement:
    project = tomllib.loads(PYPROJECT.read_text())["project"]
    matches = [
        Requirement(dep)
        for dep in project["dependencies"]
        if Requirement(dep).name == "mcp"
    ]
    if len(matches) != 1:
        raise AssertionError(
            f"Expected exactly one `mcp` runtime dependency in {PYPROJECT}, "
            f"found {len(matches)}."
        )
    return matches[0]


def test_mcp_dependency_excludes_major_version_2():
    """
    spec.mcp.McpSdkMajorVersionBoundReq

    mcp 2.x removed `mcp.server.fastmcp`, which `libspec/mcp_server.py`
    imports. An unbounded constraint lets consumers resolve 2.x and crash
    `libspec mcp` on startup (GitHub issue #2).
    """
    specifier = _mcp_requirement().specifier
    assert specifier.contains("1.27.0"), (
        f"`mcp{specifier}` must still admit the supported 1.x baseline 1.27.0"
    )
    for version in ("2.0.0", "2.2.0", "3.0.0"):
        assert not specifier.contains(version, prereleases=True), (
            f"`mcp{specifier}` admits mcp {version}, whose API is incompatible "
            f"with libspec/mcp_server.py; add an upper bound `<2`."
        )
