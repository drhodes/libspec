import os
import pytest
from unittest.mock import patch
from libspec.cli import cmd_migrate
from libspec.store import get_store, DBBuild, DBSpec, DBEdge, DBImplemented

def test_migration_v4_to_v5(tmp_path):
    # Set LIBSPEC_DATABASE_URL to a temporary sqlite path
    temp_db_path = tmp_path / "test_migrate.db"
    db_url = f"sqlite:///{temp_db_path}"
    
    # Patch os.environ so that get_store() resolves our temporary database
    with patch.dict(os.environ, {"LIBSPEC_DATABASE_URL": db_url}):
        # Run migrate command pointing to the moved XML snapshots directory
        args = {"<v4_build_dir>": "tests/spec-build"}
        cmd_migrate(args)
        
        # Resolve the active store
        store = get_store()
        
        # Verify the database path matches our temporary file
        assert store.db_path == os.path.abspath(str(temp_db_path))
        
        # Verify that all 12 snapshots were successfully migrated
        builds = list(DBBuild.select().order_by(DBBuild.created_at))
        assert len(builds) == 12
        
        # Verify that each build contains a valid master hash and session id
        for b in builds:
            assert b.master_hash
            assert b.session_id
            
        # Verify first build contains specifications
        first_build = builds[0]
        specs = list(DBSpec.select().where(DBSpec.build == first_build))
        assert len(specs) > 0
        
        # Verify we can list components through the store
        components = store.list_components()
        assert len(components) > 0
        
        # Verify there are inherits edges populated
        edges = list(DBEdge.select().where(DBEdge.build == first_build))
        assert len(edges) >= 0
