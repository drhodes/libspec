from click.testing import CliRunner
from libspec.cli import main
from libspec.store import get_store
from libspec.mcp_server import list_snapshots, list_components, show_component, get_log


def test_mcp_metadata_tools():
    runner = CliRunner()
    with runner.isolated_filesystem():
        # 1. Initialize and compile a snapshot in the isolated filesystem
        runner.invoke(main, ["init"])
        from libspec.store import Component
        comp = Component(ref="spec.app.App", docstring="Application entrypoint", is_template=False, inherits=[], hash="a"*64)
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
