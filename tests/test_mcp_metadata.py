from click.testing import CliRunner

from libspec.cli import main
from libspec.mcp_server import get_log, list_components, list_snapshots, show_component
from libspec.store import get_store


def test_mcp_metadata_tools():
    runner = CliRunner()
    with runner.isolated_filesystem():
        # 1. Initialize and compile a snapshot in the isolated filesystem
        runner.invoke(main, ["init"])
        from libspec.store import Component

        comp = Component(
            ref="spec.app.App",
            docstring="Application entrypoint",
            is_template=False,
            inherits=[],
            hash="a" * 64,
        )
        store = get_store()
        store.store_snapshot([comp])

        # 2. Verify store has snapshots
        store = get_store()
        snapshots = store.list_snapshots()
        assert len(snapshots) > 0, "No snapshots present in store for testing."

        # 3. Test list_snapshots
        snapshots_res = list_snapshots()
        assert "ID:" in snapshots_res

        # 4. Test list_components
        components_res = list_components()
        assert "spec.app.App" in components_res

        # 5. Test show_component
        show_res = show_component("spec.app.App")
        assert "Reference:" in show_res
        assert "spec.app.App" in show_res

        # 6. Test get_log
        log_res = get_log()
        assert "SNAPSHOT" in log_res

        # 7. Test declare_dependency
        from libspec.mcp_server import declare_dependency, list_dependencies

        dep_res = declare_dependency("A", "B")
        assert "Successfully declared dependency" in dep_res

        # 8. Test list_dependencies
        deps_list_res = list_dependencies()
        assert "Component Dependencies for 'PENDING':" in deps_list_res
        assert "A" in deps_list_res
        assert "└── depends on: B" in deps_list_res

        # 9. Test list_dependencies with non-existent snapshot
        deps_list_err = list_dependencies("non_existent")
        assert "Error: Snapshot 'non_existent' not found." in deps_list_err
