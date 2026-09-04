"""
Tests for class-member component dependencies, Component base class,
and exotic storytelling error handling.
"""

import pytest

from libspec.common import SpecComponent
from libspec.err import (
    CyclicDependencyError,
    DependencyDeclarationError,
    DependencyError,
    DependencyTypeError,
    NonComponentDependencyError,
    SelfDependencyError,
)
from libspec.spec import Spec
from libspec.spec_types import Component, Feature, Requirement
from libspec.util import topological_sort


class TestComponentHierarchy:
    def test_component_is_base_spec(self):
        assert issubclass(Component, object)
        assert Component.__is_base_spec__ is True
        assert Component.deps == []

    def test_feature_and_requirement_inherit_from_component(self):
        assert issubclass(Feature, Component)
        assert issubclass(Requirement, Component)

    def test_custom_component_inheritance(self):
        class MyService(Component):
            """A custom component."""

        assert issubclass(MyService, Component)
        assert MyService.deps == []


class TestValidDependencyDeclarations:
    def test_valid_deps_list(self):
        class DepA(Component):
            """Dependency A."""

        class DepB(Component):
            """Dependency B."""

        class MyComponent(Component):
            """Main component."""

            deps = [DepA, DepB]

        assert MyComponent.deps == [DepA, DepB]

    def test_valid_depends_on_alias(self):
        class DepA(Component):
            """Dependency A."""

        class MyComponent(Component):
            """Main component."""

            depends_on = [DepA]

        assert MyComponent.depends_on == [DepA]

    def test_deps_not_inherited_by_subclass(self):
        class BaseComp(Component):
            """Base component."""

        class DepA(Component):
            """Prerequisite."""

        class ParentComp(Component):
            """Parent with deps."""

            deps = [DepA]

        class ChildComp(ParentComp):
            """Child without deps."""

        # Child does not define its own deps in __dict__
        assert "deps" not in ChildComp.__dict__


class TestExoticErrorHandling:
    def test_non_component_dependency_error(self):
        class ExternalTool:
            """Unrelated utility."""

        class BadComponent(Component):
            """Declares a plain class dependency."""

            deps = [ExternalTool]  # type: ignore[list-item]

        class TestSpec(Spec):
            def modules(self):
                import sys

                return [sys.modules[__name__]]

        with pytest.raises(NonComponentDependencyError) as exc_info:
            from libspec.dependencies import evaluate_component_dependencies

            evaluate_component_dependencies(BadComponent)

        err_msg = str(exc_info.value)
        assert "LIBSPEC DEPENDENCY COMPLIANCE ERROR" in err_msg
        assert "ExternalTool" in err_msg
        assert "BadComponent" in err_msg
        assert "Actual Inheritance Hierarchy:" in err_msg
        assert "FIX:" in err_msg

    def test_instance_passed_instead_of_class(self):
        class DepA(Component):
            """Valid dependency."""

        class BadComponent(Component):
            """Passes instance instead of class."""

            deps = [DepA()]  # type: ignore[list-item]

        with pytest.raises(DependencyTypeError) as exc_info:
            from libspec.dependencies import evaluate_component_dependencies

            evaluate_component_dependencies(BadComponent)

        err_msg = str(exc_info.value)
        assert "LIBSPEC DEPENDENCY TYPE ERROR" in err_msg
        assert "Instance Passed Instead of Class" in err_msg
        assert "Did you mean:" in err_msg
        assert "deps = [DepA]" in err_msg
        assert "FIX:" in err_msg

    def test_string_passed_instead_of_class(self):
        class BadComponent(Component):
            """Passes string instead of class."""

            deps = ["DepA"]  # type: ignore[list-item]

        with pytest.raises(DependencyTypeError) as exc_info:
            from libspec.dependencies import evaluate_component_dependencies

            evaluate_component_dependencies(BadComponent)

        err_msg = str(exc_info.value)
        assert "LIBSPEC DEPENDENCY TYPE ERROR" in err_msg
        assert "DepA" in err_msg

    def test_invalid_deps_declaration_type(self):
        class DepA(Component):
            """Valid dependency."""

        class BadComponent(Component):
            """Forgets sequence brackets."""

            deps = DepA  # type: ignore[assignment]

        with pytest.raises(DependencyDeclarationError) as exc_info:
            from libspec.dependencies import evaluate_component_dependencies

            evaluate_component_dependencies(BadComponent)

        err_msg = str(exc_info.value)
        assert "LIBSPEC DEPENDENCY DECLARATION ERROR" in err_msg
        assert "must be a list or tuple" in err_msg
        assert "Did you mean:" in err_msg

    def test_self_dependency_error(self):
        class RecursiveComp(Component):
            """Component that depends on itself."""

        RecursiveComp.deps = [RecursiveComp]

        with pytest.raises(SelfDependencyError) as exc_info:
            from libspec.dependencies import evaluate_component_dependencies

            evaluate_component_dependencies(RecursiveComp)

        err_msg = str(exc_info.value)
        assert "LIBSPEC DEPENDENCY INTEGRITY ERROR" in err_msg
        assert "Self-Dependency Detected" in err_msg
        assert "RecursiveComp" in err_msg
        assert "cannot depend on itself" in err_msg
        assert "FIX:" in err_msg

    def test_direct_cyclic_dependency_error(self):
        class CompA(Component):
            """A."""

        class CompB(Component):
            """B."""

        CompA.deps = [CompB]
        CompB.deps = [CompA]

        from libspec.dependencies import validate_dependency_dag

        with pytest.raises(CyclicDependencyError) as exc_info:
            validate_dependency_dag([CompA, CompB])

        err_msg = str(exc_info.value)
        assert "LIBSPEC DEPENDENCY GRAPH ERROR" in err_msg
        assert "Cyclic Dependency Detected" in err_msg
        assert "Cycle Trace:" in err_msg
        assert "CompA" in err_msg
        assert "CompB" in err_msg
        assert "Resolution Strategies:" in err_msg

    def test_transitive_cyclic_dependency_error(self):
        class NodeA(Component):
            """Node A."""

        class NodeB(Component):
            """Node B."""

        class NodeC(Component):
            """Node C."""

        NodeA.deps = [NodeB]
        NodeB.deps = [NodeC]
        NodeC.deps = [NodeA]

        from libspec.dependencies import validate_dependency_dag

        with pytest.raises(CyclicDependencyError) as exc_info:
            validate_dependency_dag([NodeA, NodeB, NodeC])

        err_msg = str(exc_info.value)
        assert "Cyclic Dependency Detected" in err_msg
        assert "NodeA" in err_msg
        assert "NodeB" in err_msg
        assert "NodeC" in err_msg


class TestTopologicalSort:
    def test_topological_waves(self):
        class RootA(Component):
            """Root A."""

        class RootB(Component):
            """Root B."""

        class Mid(Component):
            """Mid."""

            deps = [RootA, RootB]

        class Leaf(Component):
            """Leaf."""

            deps = [Mid]

        waves = topological_sort([RootA, RootB, Mid, Leaf])
        assert len(waves) == 3
        assert sorted([c.__name__ for c in waves[0]]) == ["RootA", "RootB"]
        assert [c.__name__ for c in waves[1]] == ["Mid"]
        assert [c.__name__ for c in waves[2]] == ["Leaf"]

    def test_topological_sort_with_fqn_strings(self):
        deps_map = {
            "pkg.Root": [],
            "pkg.Child1": ["pkg.Root"],
            "pkg.Child2": ["pkg.Root"],
            "pkg.Final": ["pkg.Child1", "pkg.Child2"],
        }
        waves = topological_sort(deps_map)
        assert len(waves) == 3
        assert waves[0] == ["pkg.Root"]
        assert sorted(waves[1]) == ["pkg.Child1", "pkg.Child2"]
        assert waves[2] == ["pkg.Final"]


class TestSpecComponentDataModel:
    def test_spec_component_has_deps(self):
        comp = SpecComponent(
            ref="test.Comp",
            docstring="Doc",
            is_template=False,
            inherits=[],
            hash="a" * 64,
            is_dependency=False,
            deps=["dep.A", "dep.B"],
        )
        assert comp.deps == ["dep.A", "dep.B"]

    def test_spec_component_default_deps_empty(self):
        comp = SpecComponent(
            ref="test.Comp",
            docstring="Doc",
            is_template=False,
            inherits=[],
            hash="a" * 64,
        )
        assert comp.deps == []


class TestCliDependenciesCommand:
    def test_cli_dependencies_topo(self):
        from unittest.mock import patch

        from click.testing import CliRunner

        from libspec.cli import main

        runner = CliRunner()
        with runner.isolated_filesystem():
            runner.invoke(main, ["init"])

            comp_a = SpecComponent(
                ref="spec.pkg.A",
                docstring="A",
                is_template=False,
                inherits=[],
                hash="a" * 64,
                deps=[],
            )
            comp_b = SpecComponent(
                ref="spec.pkg.B",
                docstring="B",
                is_template=False,
                inherits=[],
                hash="b" * 64,
                deps=["spec.pkg.A"],
            )

            with patch(
                "libspec.util.compile_live_spec",
                return_value=([comp_a, comp_b], "spec/main_spec.py"),
            ):
                res = runner.invoke(main, ["dependencies", "--topo"])
                assert res.exit_code == 0
                assert "Topological Implementation Order" in res.output
                assert "Wave 1: spec.pkg.A" in res.output
                assert "Wave 2: spec.pkg.B" in res.output

    def test_cli_dependencies_with_explicit_deps(self):
        from unittest.mock import patch

        from click.testing import CliRunner

        from libspec.cli import main

        runner = CliRunner()
        with runner.isolated_filesystem():
            runner.invoke(main, ["init"])

            comp_a = SpecComponent(
                ref="spec.pkg.A",
                docstring="A",
                is_template=False,
                inherits=[],
                hash="a" * 64,
                deps=[],
            )
            comp_b = SpecComponent(
                ref="spec.pkg.B",
                docstring="B",
                is_template=False,
                inherits=[],
                hash="b" * 64,
                deps=["spec.pkg.A"],
            )

            with patch(
                "libspec.util.compile_live_spec",
                return_value=([comp_a, comp_b], "spec/main_spec.py"),
            ):
                res = runner.invoke(main, ["dependencies"])
                assert res.exit_code == 0
                assert "spec.pkg.B" in res.output
                assert "└── depends on: spec.pkg.A" in res.output


class TestSpecCompilationWithDependencies:
    def test_spec_compile_populates_deps(self):
        import sys
        import types

        # Create a dynamic module
        mod = types.ModuleType("test_mod")

        class Prereq(Component):
            """Prerequisite component."""

        class Dependent(Component):
            """Dependent component."""

            deps = [Prereq]

        Prereq.__module__ = "test_mod"
        Dependent.__module__ = "test_mod"
        mod.Prereq = Prereq
        mod.Dependent = Dependent

        class DummySpec(Spec):
            def modules(self):
                return [mod]

        spec_inst = DummySpec()
        comps = spec_inst.get_components()
        comp_map = {c.ref.split(".")[-1]: c for c in comps}

        assert "Prereq" in comp_map
        assert "Dependent" in comp_map
        assert comp_map["Prereq"].deps == []
        assert any("Prereq" in d for d in comp_map["Dependent"].deps)
