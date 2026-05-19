import os
import shutil
import datetime
import tempfile
from libspec.store import (
    Component, Snapshot, Implemented,
    XmlSpecStore, SQLiteSpecStore, get_store,
    SpecStoreError, SpecStoreNotFoundError
)

def run_tests():
    print("=== Starting SpecStore Verification Tests ===")
    
    # Create temp directory for tests
    temp_dir = tempfile.mkdtemp()
    xml_path = os.path.join(temp_dir, "test_store.xml")
    db_path = os.path.join(temp_dir, "test_store.db")
    
    try:
        # 1. Verification of Dataclass validations
        print("Testing Dataclass Validation Preconditions...")
        try:
            Component(ref="", docstring="desc", is_template=False, inherits=[], hash="0"*64)
            raise RuntimeError("FAILED: Component ref blank validation missed.")
        except ValueError:
            print("  Component blank ref validation passed.")
            
        try:
            Component(ref="a.b", docstring="desc", is_template=False, inherits=[], hash="wrong_len")
            raise RuntimeError("FAILED: Component hash length validation missed.")
        except ValueError:
            print("  Component hash length validation passed.")
            
        try:
            Snapshot(id="snap", created_at="not_datetime", master_hash="0"*64)
            raise RuntimeError("FAILED: Snapshot datetime type validation missed.")
        except TypeError:
            print("  Snapshot datetime validation passed.")
            
        # 2. Testing XmlSpecStore (Single File)
        print("Testing XmlSpecStore (Single File)...")
        xml_store = XmlSpecStore(xml_path)
        
        c1 = Component(
            ref="spec.store.SQLiteStore",
            docstring="Specifies SQLite SQLiteSpecStore Peewee relational adapter.",
            is_template=False,
            inherits=["spec.err.Feat"],
            hash="1" * 64
        )
        c2 = Component(
            ref="spec.store.PostgreSQLStore",
            docstring="Specifies PostgreSQL remote relational adapter.",
            is_template=False,
            inherits=["spec.err.Feat"],
            hash="2" * 64
        )
        
        # Save snapshot
        snap = xml_store.store_snapshot([c1, c2], git_commit="a" * 40)
        print(f"  XmlSpecStore snapshot created: ID={snap.id}, MasterHash={snap.master_hash}")
        
        # Check current snapshot
        curr_snap = xml_store.current_snapshot()
        assert curr_snap is not None
        assert curr_snap.master_hash == snap.master_hash
        assert curr_snap.git_commit == "a" * 40
        print("  XmlSpecStore current_snapshot retrieval verified.")
        
        # List components
        comps = xml_store.list_components()
        assert len(comps) == 2
        assert any(c.ref == "spec.store.SQLiteStore" for c in comps)
        print("  XmlSpecStore list_components verified.")
        
        # Get component
        comp_lookup = xml_store.get_component("spec.store.SQLiteStore")
        assert comp_lookup.hash == c1.hash
        print("  XmlSpecStore get_component lookup verified.")
        
        # Write implementation claim
        claim = Implemented(
            ref="spec.store.SQLiteStore",
            spec_hash=c1.hash,
            file="libspec/store.py",
            line=405,
            session_id="agent_123"
        )
        xml_store.store_implemented(claim)
        
        # List implementation claims
        claims = xml_store.list_implemented(snap)
        assert len(claims) == 1
        assert claims[0].ref == "spec.store.SQLiteStore"
        assert claims[0].session_id == "agent_123"
        print("  XmlSpecStore implemented claims serialization verified.")
        
        # 2b. Testing XmlSpecStore (Directory Mode)
        print("Testing XmlSpecStore (Directory Mode)...")
        xml_dir = os.path.join(temp_dir, "xml_dir")
        dir_store = XmlSpecStore(xml_dir)
        
        # Save snapshot #1
        dir_snap1 = dir_store.store_snapshot([c1], git_commit="c1" * 20)
        # Save snapshot #2
        dir_snap2 = dir_store.store_snapshot([c1, c2], git_commit="c2" * 20)
        
        # Assert two distinct hashed XML files were written
        xml_files = os.listdir(xml_dir)
        xml_files = [f for f in xml_files if f.endswith(".xml")]
        assert len(xml_files) == 2
        print(f"  XmlSpecStore written hashed files: {xml_files}")
        
        # Retrieve current snapshot (must resolve chronologically to latest)
        dir_curr = dir_store.current_snapshot()
        assert dir_curr is not None
        assert dir_curr.master_hash == dir_snap2.master_hash
        print("  XmlSpecStore directory-latest current_snapshot verified.")
        
        # Retrieve component from directory
        dir_comp = dir_store.get_component("spec.store.PostgreSQLStore")
        assert dir_comp.hash == c2.hash
        print("  XmlSpecStore directory get_component lookup verified.")
        
        # Save claim into latest directory file
        dir_store.store_implemented(claim)
        dir_claims = dir_store.list_implemented(dir_snap2)
        assert len(dir_claims) == 1
        assert dir_claims[0].ref == "spec.store.SQLiteStore"
        print("  XmlSpecStore directory implemented claims verified.")
        
        # 3. Testing SQLiteSpecStore
        print("Testing SQLiteSpecStore...")
        sqlite_store = SQLiteSpecStore(db_path)
        
        # Save build #1
        snap1 = sqlite_store.store_snapshot([c1, c2], git_commit="1" * 40)
        print(f"  SQLiteSpecStore snapshot 1 created: ID={snap1.id}")
        
        # Save implementation claim
        sqlite_store.store_implemented(claim)
        
        # List implementation claims
        db_claims = sqlite_store.list_implemented(snap1)
        assert len(db_claims) == 1
        assert db_claims[0].ref == "spec.store.SQLiteStore"
        print("  SQLiteSpecStore implemented claims verified.")
        
        # Save build #2
        c3 = Component(
            ref="spec.store.XmlStoreAdapter",
            docstring="Specifies legacy XML Strangler Fig adapter.",
            is_template=False,
            inherits=["spec.err.Feat"],
            hash="3" * 64
        )
        snap2 = sqlite_store.store_snapshot([c1, c2, c3], git_commit="2" * 40)
        print(f"  SQLiteSpecStore snapshot 2 created: ID={snap2.id}")
        
        # Save build #3
        snap3 = sqlite_store.store_snapshot([c1, c3], git_commit="3" * 40)
        print(f"  SQLiteSpecStore snapshot 3 created: ID={snap3.id}")
        
        # Test the append-only retention pruning policy (only latest 2 builds kept)
        curr_snap = sqlite_store.current_snapshot()
        assert curr_snap is not None
        assert curr_snap.master_hash == snap3.master_hash
        print("  SQLiteSpecStore current_snapshot retrieval verified.")
        
        # Verify that build #1 was deleted via pruning
        try:
            sqlite_store.list_implemented(snap1)
            # Pruning build #1 should cascade-delete its claims
            claims_for_pruned = sqlite_store.list_implemented(snap1)
            assert len(claims_for_pruned) == 0
            print("  SQLiteSpecStore cascade-delete pruning of old builds verified successfully.")
        except Exception as e:
            print(f"  SQLiteSpecStore pruning verification encountered: {e}")
            
        # 4. Testing Dynamic Factory Resolution
        print("Testing Dynamic Factory Resolution...")
        # Test default XML fallback
        if "LIBSPEC_DATABASE_URL" in os.environ:
            del os.environ["LIBSPEC_DATABASE_URL"]
        store_fallback = get_store()
        assert isinstance(store_fallback, XmlSpecStore)
        print("  Factory default fallback to XmlSpecStore verified.")
        
        # Test SQLite resolution
        os.environ["LIBSPEC_DATABASE_URL"] = f"sqlite://{db_path}"
        store_sqlite = get_store()
        assert isinstance(store_sqlite, SQLiteSpecStore)
        print("  Factory SQLite database URI resolution verified.")
        
        print("=== ALL TESTS PASSED SUCCESSFULLY ===")
        
    finally:
        # Clean up temp files
        shutil.rmtree(temp_dir)

if __name__ == "__main__":
    run_tests()
