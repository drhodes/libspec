"""
Tests for component dependency visualization (Mermaid, Graphviz DOT, interactive HTML DAG),
reverse dependency analysis (--rdeps), and CLI visualization options.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from libspec.cli import main
from libspec.common import SpecComponent
from libspec.dependencies import (
    compute_reverse_dependencies,
    filter_subgraph,
    render_dot,
    render_html_dag,
    render_mermaid,
)


def _make_dummy_components() -> list[SpecComponent]:
    """
    Graph structure:
      CompA (Wave 1)
      CompB (Wave 2) -> depends on CompA
      CompC (Wave 2) -> depends on CompA
      CompD (Wave 3) -> depends on CompB, CompC
      CompE (Wave 1) -> independent
    """
    return [
        SpecComponent(
            ref="spec.pkg.CompA",
            docstring="Foundational component A.",
            is_template=False,
            inherits=[],
            hash="a" * 64,
            deps=[],
        ),
        SpecComponent(
            ref="spec.pkg.CompB",
            docstring="Component B depending on A.",
            is_template=False,
            inherits=[],
            hash="b" * 64,
            deps=["spec.pkg.CompA"],
        ),
        SpecComponent(
            ref="spec.pkg.CompC",
            docstring="Component C depending on A.",
            is_template=False,
            inherits=[],
            hash="c" * 64,
            deps=["spec.pkg.CompA"],
        ),
        SpecComponent(
            ref="spec.pkg.CompD",
            docstring="Component D depending on B and C.",
            is_template=False,
            inherits=[],
            hash="d" * 64,
            deps=["spec.pkg.CompB", "spec.pkg.CompC"],
        ),
        SpecComponent(
            ref="spec.pkg.CompE",
            docstring="Isolated component E.",
            is_template=True,
            inherits=[],
            hash="e" * 64,
            deps=[],
        ),
    ]


class TestReverseDependencies:
    def test_compute_reverse_dependencies_all(self):
        comps = _make_dummy_components()
        rdeps = compute_reverse_dependencies(comps)

        assert sorted(rdeps["spec.pkg.CompA"]) == ["spec.pkg.CompB", "spec.pkg.CompC"]
        assert rdeps["spec.pkg.CompB"] == ["spec.pkg.CompD"]
        assert rdeps["spec.pkg.CompC"] == ["spec.pkg.CompD"]
        assert rdeps["spec.pkg.CompD"] == []
        assert rdeps["spec.pkg.CompE"] == []

    def test_compute_reverse_dependencies_single_target(self):
        comps = _make_dummy_components()
        rdeps = compute_reverse_dependencies(comps, target_ref="spec.pkg.CompA")
        assert sorted(rdeps["spec.pkg.CompA"]) == ["spec.pkg.CompB", "spec.pkg.CompC"]
        assert len(rdeps) == 1

    def test_compute_reverse_dependencies_transitive(self):
        comps = _make_dummy_components()
        rdeps = compute_reverse_dependencies(
            comps, target_ref="spec.pkg.CompA", transitive=True
        )
        assert sorted(rdeps["spec.pkg.CompA"]) == [
            "spec.pkg.CompB",
            "spec.pkg.CompC",
            "spec.pkg.CompD",
        ]

    def test_filter_subgraph_upstream(self):
        comps = _make_dummy_components()
        subgraph_nodes, subgraph_edges = filter_subgraph(
            comps, target_ref="spec.pkg.CompD", rdeps=False
        )
        assert "spec.pkg.CompD" in subgraph_nodes
        assert "spec.pkg.CompB" in subgraph_nodes
        assert "spec.pkg.CompC" in subgraph_nodes
        assert "spec.pkg.CompA" in subgraph_nodes
        assert "spec.pkg.CompE" not in subgraph_nodes

    def test_filter_subgraph_downstream(self):
        comps = _make_dummy_components()
        subgraph_nodes, subgraph_edges = filter_subgraph(
            comps, target_ref="spec.pkg.CompB", rdeps=True
        )
        assert "spec.pkg.CompB" in subgraph_nodes
        assert "spec.pkg.CompD" in subgraph_nodes
        assert "spec.pkg.CompC" not in subgraph_nodes
        assert "spec.pkg.CompA" not in subgraph_nodes


class TestMermaidRendering:
    def test_render_mermaid_basic(self):
        comps = _make_dummy_components()
        mermaid_src = render_mermaid(comps)

        assert mermaid_src.startswith("flowchart")
        assert "subgraph Wave_" in mermaid_src
        assert "spec.pkg.CompA" in mermaid_src
        assert "spec.pkg.CompB" in mermaid_src
        assert " --> " in mermaid_src

    def test_render_mermaid_rdeps(self):
        comps = _make_dummy_components()
        mermaid_src = render_mermaid(comps, rdeps=True)

        assert "flowchart" in mermaid_src
        assert "subgraph Wave_" in mermaid_src
        assert "spec.pkg.CompA" in mermaid_src

    def test_render_mermaid_scoped(self):
        comps = _make_dummy_components()
        mermaid_src = render_mermaid(comps, target_ref="spec.pkg.CompB")

        assert "spec.pkg.CompB" in mermaid_src
        assert "spec.pkg.CompA" in mermaid_src
        assert "spec.pkg.CompE" not in mermaid_src


class TestDotRendering:
    def test_render_dot_basic(self):
        comps = _make_dummy_components()
        dot_src = render_dot(comps)

        assert dot_src.startswith("digraph")
        assert "subgraph cluster_wave_" in dot_src
        assert "spec.pkg.CompA" in dot_src
        assert "spec.pkg.CompB" in dot_src
        assert "->" in dot_src

    def test_render_dot_rdeps(self):
        comps = _make_dummy_components()
        dot_src = render_dot(comps, rdeps=True)

        assert "digraph" in dot_src
        assert "->" in dot_src


class TestHtmlDagRendering:
    def test_render_html_dag_string(self):
        comps = _make_dummy_components()
        html = render_html_dag(comps)

        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "spec.pkg.CompA" in html
        assert "spec.pkg.CompB" in html
        assert "Foundational component A." in html

    def test_render_html_dag_file_output(self, tmp_path):
        comps = _make_dummy_components()
        out_file = tmp_path / "graph.html"
        render_html_dag(comps, output_path=str(out_file))

        assert out_file.exists()
        content = out_file.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        assert "spec.pkg.CompD" in content


class TestCliVisualizationOptions:
    def test_cli_dependencies_mermaid(self):
        runner = CliRunner()
        comps = _make_dummy_components()

        with (
            patch(
                "libspec.cli.require_libspec_project",
                return_value=None,
            ),
            patch(
                "libspec.util.compile_live_spec",
                return_value=(comps, "spec/main_spec.py"),
            ),
        ):
            res = runner.invoke(main, ["dependencies", "--mermaid"])
            assert res.exit_code == 0
            assert "flowchart" in res.output
            assert "spec.pkg.CompA" in res.output

    def test_cli_dependencies_dot(self):
        runner = CliRunner()
        comps = _make_dummy_components()

        with (
            patch(
                "libspec.cli.require_libspec_project",
                return_value=None,
            ),
            patch(
                "libspec.util.compile_live_spec",
                return_value=(comps, "spec/main_spec.py"),
            ),
        ):
            res = runner.invoke(main, ["dependencies", "--dot"])
            assert res.exit_code == 0
            assert "digraph" in res.output
            assert "cluster_wave_" in res.output

    def test_cli_dependencies_rdeps(self):
        runner = CliRunner()
        comps = _make_dummy_components()

        with (
            patch(
                "libspec.cli.require_libspec_project",
                return_value=None,
            ),
            patch(
                "libspec.util.compile_live_spec",
                return_value=(comps, "spec/main_spec.py"),
            ),
        ):
            res = runner.invoke(main, ["dependencies", "--rdeps"])
            assert res.exit_code == 0
            assert "Reverse Dependencies (Dependents)" in res.output
            assert "spec.pkg.CompA" in res.output
            assert "required by: spec.pkg.CompB" in res.output

    def test_cli_dependencies_html_file(self, tmp_path):
        runner = CliRunner()
        comps = _make_dummy_components()
        out_html = tmp_path / "custom_deps.html"

        with (
            patch(
                "libspec.cli.require_libspec_project",
                return_value=None,
            ),
            patch(
                "libspec.util.compile_live_spec",
                return_value=(comps, "spec/main_spec.py"),
            ),
        ):
            res = runner.invoke(main, ["dependencies", "--html", str(out_html)])
            assert res.exit_code == 0
            assert out_html.exists()
            assert "Generated interactive dependency graph" in res.output

    def test_cli_dependencies_scoped_component(self):
        runner = CliRunner()
        comps = _make_dummy_components()

        with (
            patch(
                "libspec.cli.require_libspec_project",
                return_value=None,
            ),
            patch(
                "libspec.util.compile_live_spec",
                return_value=(comps, "spec/main_spec.py"),
            ),
        ):
            res = runner.invoke(main, ["dependencies", "spec.pkg.CompB", "--rdeps"])
            assert res.exit_code == 0
            assert "spec.pkg.CompB" in res.output
            assert "spec.pkg.CompD" in res.output
            assert "spec.pkg.CompE" not in res.output


class TestMcpDependencies:
    def test_mcp_list_dependencies_formats(self):
        from libspec.mcp_server import list_dependencies

        comps = _make_dummy_components()
        with patch(
            "libspec.util.compile_live_spec", return_value=(comps, "spec/main_spec.py")
        ):
            # Mermaid format
            res_mermaid = list_dependencies(format="mermaid")
            assert "flowchart" in res_mermaid
            assert "spec.pkg.CompA" in res_mermaid

            # DOT format
            res_dot = list_dependencies(format="dot")
            assert "digraph" in res_dot
            assert "cluster_wave_" in res_dot

            # HTML format
            res_html = list_dependencies(format="html")
            assert "<!DOCTYPE html>" in res_html
            assert "spec.pkg.CompA" in res_html

            # rdeps mode
            res_rdeps = list_dependencies(rdeps=True)
            assert "Reverse Dependencies (Dependents)" in res_rdeps
            assert "required by: spec.pkg.CompB" in res_rdeps

            # scoped component
            res_scoped = list_dependencies(component="spec.pkg.CompB")
            assert "Component Dependencies for 'spec.pkg.CompB'" in res_scoped
            assert "depends on: spec.pkg.CompA" in res_scoped


class TestReplDependencies:
    def test_repl_dependencies_command(self, capsys):
        from libspec.repl import DependenciesCommand

        comps = _make_dummy_components()
        mock_repl = MagicMock()
        mock_repl.components = comps

        cmd = DependenciesCommand()

        # Test --topo
        cmd.run(mock_repl, "--topo")
        out = capsys.readouterr().out
        assert "Topological Implementation Order" in out
        assert "Wave 1" in out

        # Test --mermaid
        cmd.run(mock_repl, "--mermaid")
        out = capsys.readouterr().out
        assert "flowchart" in out

        # Test --dot
        cmd.run(mock_repl, "--dot")
        out = capsys.readouterr().out
        assert "digraph" in out

        # Test --rdeps
        cmd.run(mock_repl, "--rdeps")
        out = capsys.readouterr().out
        assert "Reverse Dependencies (Dependents)" in out
        assert "required by:" in out
