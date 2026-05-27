'''
Peewee-based SQLite and PostgreSQL SpecStore implementations.
'''

import os
import hashlib
import datetime
from typing import Optional, List

from libspec.store import (
    Component,
    Snapshot,
    Implemented,
    SpecStore,
    SpecStoreIOError,
    SpecStoreNotFoundError,
    SpecStoreCorruptedDataError,
)

# Attempt to import Peewee
try:
    import peewee
except ImportError:
    peewee = None


# =========================================================================
# Peewee ORM Models
# =========================================================================

db_proxy = peewee.Proxy() if peewee else None


class PeeweeBaseModel(peewee.Model if peewee else object):
    class Meta:
        database = db_proxy


class DBBuild(PeeweeBaseModel):
    created_at = peewee.DateTimeField(default=datetime.datetime.now)
    git_commit = peewee.CharField(null=True)
    master_hash = peewee.CharField()
    session_id = peewee.CharField(null=True)
    is_deleted = peewee.BooleanField(default=False)


class DBSpec(PeeweeBaseModel):
    build = peewee.ForeignKeyField(DBBuild, backref="specs", on_delete="CASCADE")
    ref = peewee.CharField(index=True)
    docstring = peewee.TextField()
    is_template = peewee.BooleanField()
    hash = peewee.CharField()


class DBEdge(PeeweeBaseModel):
    build = peewee.ForeignKeyField(DBBuild, backref="edges", on_delete="CASCADE")
    child_ref = peewee.CharField(index=True)
    parent_ref = peewee.CharField()
    position = peewee.IntegerField()


class DBImplemented(PeeweeBaseModel):
    build = peewee.ForeignKeyField(DBBuild, backref="implementations", on_delete="CASCADE")
    ref = peewee.CharField(index=True)
    spec_hash = peewee.CharField()
    file = peewee.CharField()
    line = peewee.IntegerField()
    session_id = peewee.CharField(null=True)

    class Meta:
        table_name = "implemented"


# =========================================================================
# SQLite Store
# =========================================================================

class SQLiteSpecStore(SpecStore):
    '''Production Peewee SQLite adapter with automatic schemas and append-only build history.'''

    def __init__(self, db_path: str):
        if peewee is None:
            raise SpecStoreIOError("Peewee must be installed to use SQLiteSpecStore.")
        if not isinstance(db_path, str) or not db_path.strip():
            raise ValueError("SQLiteSpecStore requires a valid database file path.")

        self.db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        self.database = peewee.SqliteDatabase(self.db_path, pragmas={
            'journal_mode': 'wal',
            'foreign_keys': 1,
            'ignore_check_constraints': 0,
        })
        db_proxy.initialize(self.database)

        try:
            self.database.create_tables([DBBuild, DBSpec, DBEdge, DBImplemented])
            # Dynamic schema update for backward compatibility with existing databases
            columns = [c.name for c in self.database.get_columns("dbbuild")]
            if "is_deleted" not in columns:
                self.database.execute_sql("ALTER TABLE dbbuild ADD COLUMN is_deleted BOOLEAN DEFAULT 0")
        except peewee.PeeweeException as e:
            raise SpecStoreIOError(f"Failed to create SQLite tables at {self.db_path}: {e}") from e

    def store_snapshot(self, components: List[Component], git_commit: Optional[str] = None, created_at: Optional[datetime.datetime] = None) -> Snapshot:
        if not isinstance(components, list) or not all(isinstance(c, Component) for c in components):
            raise TypeError("components must be a list of Component instances.")

        if created_at is None:
            created_at = datetime.datetime.now(datetime.timezone.utc)
        sorted_components = sorted(components, key=lambda c: c.ref)

        hasher = hashlib.sha256()
        for comp in sorted_components:
            hasher.update(comp.hash.encode("utf-8"))
        master_hash = hasher.hexdigest()
        snapshot_id = master_hash[:16]

        try:
            # Check if this exact snapshot hash is already recorded
            existing_build = DBBuild.get_or_none(DBBuild.master_hash == master_hash)
            if existing_build:
                if git_commit and existing_build.git_commit != git_commit:
                    existing_build.git_commit = git_commit
                    existing_build.save()
                return Snapshot(id=snapshot_id, created_at=existing_build.created_at, master_hash=master_hash, git_commit=existing_build.git_commit)

            with self.database.atomic():
                build = DBBuild.create(
                    created_at=created_at,
                    git_commit=git_commit,
                    master_hash=master_hash,
                    session_id=snapshot_id
                )

                for comp in sorted_components:
                    DBSpec.create(
                        build=build,
                        ref=comp.ref,
                        docstring=comp.docstring,
                        is_template=comp.is_template,
                        hash=comp.hash
                    )

                    for idx, parent in enumerate(comp.inherits):
                        DBEdge.create(
                            build=build,
                            child_ref=comp.ref,
                            parent_ref=parent,
                            position=idx
                        )

            return Snapshot(id=snapshot_id, created_at=created_at, master_hash=master_hash, git_commit=git_commit)
        except peewee.PeeweeException as e:
            raise SpecStoreIOError(f"SQLite store_snapshot failed: {e}") from e

    def _get_latest_build(self) -> Optional[DBBuild]:
        # Filter out empty/dummy mock builds generated by test runs
        build = DBBuild.select().where(DBBuild.is_deleted == False).join(DBSpec).order_by(DBBuild.created_at.desc()).first()
        if build is not None:
            return build
        # Fall back to absolute latest build if no populated build exists
        return DBBuild.select().where(DBBuild.is_deleted == False).order_by(DBBuild.created_at.desc()).first()

    def current_snapshot(self) -> Optional[Snapshot]:
        try:
            build = self._get_latest_build()
            if build is None:
                return None
            return Snapshot(
                id=build.session_id or build.master_hash[:16],
                created_at=build.created_at,
                master_hash=build.master_hash,
                git_commit=build.git_commit
            )
        except peewee.PeeweeException as e:
            raise SpecStoreIOError(f"SQLite current_snapshot lookup failed: {e}") from e

    def most_recent_hash(self) -> Optional[str]:
        try:
            build = self._get_latest_build()
            return build.master_hash if build else None
        except peewee.PeeweeException as e:
            raise SpecStoreIOError(f"SQLite most_recent_hash lookup failed: {e}") from e

    def get_component(self, ref: str) -> Component:
        if not isinstance(ref, str) or not ref.strip():
            raise ValueError("Component reference FQN must be a non-empty string.")

        try:
            build = self._get_latest_build()
            if build is None:
                raise SpecStoreNotFoundError("SpecStore is empty. Compile a snapshot first.")

            spec = DBSpec.select().where(DBSpec.build == build, DBSpec.ref == ref).first()
            if spec is None:
                raise SpecStoreNotFoundError(f"Component '{ref}' not found in the active SQLite snapshot.")

            edges = DBEdge.select().where(DBEdge.build == build, DBEdge.child_ref == ref).order_by(DBEdge.position.asc())
            inherits = [edge.parent_ref for edge in edges]

            return Component(
                ref=spec.ref,
                docstring=spec.docstring,
                is_template=spec.is_template,
                inherits=inherits,
                hash=spec.hash
            )
        except SpecStoreNotFoundError:
            raise
        except peewee.PeeweeException as e:
            raise SpecStoreIOError(f"SQLite get_component failed: {e}") from e

    def list_components(self) -> List[Component]:
        try:
            build = self._get_latest_build()
            if build is None:
                return []

            specs = DBSpec.select().where(DBSpec.build == build)
            components = []
            for spec in specs:
                edges = DBEdge.select().where(DBEdge.build == build, DBEdge.child_ref == spec.ref).order_by(DBEdge.position.asc())
                inherits = [edge.parent_ref for edge in edges]
                components.append(Component(
                     ref=spec.ref,
                     docstring=spec.docstring,
                     is_template=spec.is_template,
                     inherits=inherits,
                     hash=spec.hash
                ))
            return components
        except peewee.PeeweeException as e:
            raise SpecStoreIOError(f"SQLite list_components failed: {e}") from e

    def store_implemented(self, record: Implemented) -> None:
        if not isinstance(record, Implemented):
            raise TypeError("record must be a valid Implemented instance.")

        try:
            build = self._get_latest_build()
            if build is None:
                raise SpecStoreNotFoundError("Cannot record implementation claim on an empty SpecStore snapshot.")

            with self.database.atomic():
                # Deduplicate claim for the active build
                DBImplemented.delete().where(
                    DBImplemented.build == build,
                    DBImplemented.ref == record.ref
                ).execute()

                DBImplemented.create(
                    build=build,
                    ref=record.ref,
                    spec_hash=record.spec_hash,
                    file=record.file,
                    line=record.line,
                    session_id=record.session_id
                )
        except peewee.PeeweeException as e:
            raise SpecStoreIOError(f"SQLite store_implemented failed: {e}") from e

    def list_implemented(self, snapshot: Snapshot) -> List[Implemented]:
        if not isinstance(snapshot, Snapshot):
            raise TypeError("snapshot must be a valid Snapshot instance.")

        try:
            build = DBBuild.select().where(DBBuild.master_hash == snapshot.master_hash).first()
            if build is None:
                return []

            records = DBImplemented.select().where(DBImplemented.build == build)
            claims = []
            for rec in records:
                claims.append(Implemented(
                    ref=rec.ref,
                    spec_hash=rec.spec_hash,
                    file=rec.file,
                    line=rec.line,
                    session_id=rec.session_id
                ))
            return claims
        except peewee.PeeweeException as e:
            raise SpecStoreIOError(f"SQLite list_implemented failed: {e}") from e

    def list_snapshots(self) -> List[Snapshot]:
        try:
            builds = list(DBBuild.select().where(DBBuild.is_deleted == False).order_by(DBBuild.created_at.asc()))
            snapshots = []
            for b in builds:
                snapshots.append(Snapshot(
                    id=b.session_id or b.master_hash[:16],
                    created_at=b.created_at,
                    master_hash=b.master_hash,
                    git_commit=b.git_commit
                ))
            return snapshots
        except peewee.PeeweeException as e:
            raise SpecStoreIOError(f"SQLite list_snapshots failed: {e}") from e

    def get_snapshot(self, id_or_hash: str) -> Optional[Snapshot]:
        try:
            build = DBBuild.get_or_none(DBBuild.session_id == id_or_hash)
            if not build:
                build = DBBuild.get_or_none(DBBuild.master_hash == id_or_hash)
            if not build:
                builds = list(DBBuild.select())
                matching = []
                for b in builds:
                    b_id = b.session_id or ""
                    b_hash = b.master_hash or ""
                    if id_or_hash in b_id or id_or_hash in b_hash or b_id.startswith(id_or_hash) or b_hash.startswith(id_or_hash):
                        matching.append(b)
                if len(matching) == 1:
                    build = matching[0]
                elif len(matching) > 1:
                    raise SpecStoreNotFoundError(f"Multiple snapshots matched '{id_or_hash}'.")

            if not build:
                raise SpecStoreNotFoundError(f"Snapshot '{id_or_hash}' not found in SQLite store.")

            return Snapshot(
                id=build.session_id or build.master_hash[:16],
                created_at=build.created_at,
                master_hash=build.master_hash,
                git_commit=build.git_commit
            )
        except SpecStoreNotFoundError:
            raise
        except peewee.PeeweeException as e:
            raise SpecStoreIOError(f"SQLite get_snapshot failed: {e}") from e

    def get_components_for_snapshot(self, snapshot: Snapshot) -> List[Component]:
        if not isinstance(snapshot, Snapshot):
            raise TypeError("snapshot must be a valid Snapshot instance.")

        try:
            build = DBBuild.select().where(DBBuild.master_hash == snapshot.master_hash).first()
            if build is None:
                raise SpecStoreNotFoundError(f"Snapshot '{snapshot.id}' not found in SQLite store.")

            specs = DBSpec.select().where(DBSpec.build == build)
            components = []
            for spec in specs:
                edges = DBEdge.select().where(DBEdge.build == build, DBEdge.child_ref == spec.ref).order_by(DBEdge.position.asc())
                inherits = [edge.parent_ref for edge in edges]
                components.append(Component(
                     ref=spec.ref,
                     docstring=spec.docstring,
                     is_template=spec.is_template,
                     inherits=inherits,
                     hash=spec.hash
                ))
            return components
        except SpecStoreNotFoundError:
            raise
        except peewee.PeeweeException as e:
            raise SpecStoreIOError(f"SQLite get_components_for_snapshot failed: {e}") from e

    def delete_snapshot(self, snapshot: Snapshot) -> None:
        if not isinstance(snapshot, Snapshot):
            raise TypeError("snapshot must be a valid Snapshot instance.")
            
        try:
            with self.database.atomic():
                updated = DBBuild.update(is_deleted=True).where(
                    (DBBuild.master_hash == snapshot.master_hash) & 
                    (DBBuild.created_at == snapshot.created_at)
                ).execute()
                if updated == 0:
                    raise SpecStoreNotFoundError(f"Snapshot '{snapshot.id}' not found in SQLite store.")
        except peewee.PeeweeException as e:
            raise SpecStoreIOError(f"Failed to delete snapshot '{snapshot.id}' from database: {e}") from e

    def restore_snapshot(self, snapshot: Snapshot) -> None:
        if not isinstance(snapshot, Snapshot):
            raise TypeError("snapshot must be a valid Snapshot instance.")
            
        try:
            with self.database.atomic():
                updated = DBBuild.update(is_deleted=False).where(
                    (DBBuild.master_hash == snapshot.master_hash) & 
                    (DBBuild.created_at == snapshot.created_at)
                ).execute()
                if updated == 0:
                    raise SpecStoreNotFoundError(f"Snapshot '{snapshot.id}' not found in SQLite store.")
        except peewee.PeeweeException as e:
            raise SpecStoreIOError(f"Failed to restore snapshot '{snapshot.id}' in database: {e}") from e


# =========================================================================
# PostgreSQL Store
# =========================================================================

class PostgresSpecStore(SQLiteSpecStore):
    '''Centralized remote relational PostgreSQL adapter using the exact same model logic.'''

    def __init__(self, db_name: str, **conn_params):
        if peewee is None:
            raise SpecStoreIOError("Peewee must be installed to use PostgresSpecStore.")

        # Try to import postgres adapter
        try:
            from playhouse.postgres_ext import PostgresqlExtDatabase
            self.database = PostgresqlExtDatabase(db_name, **conn_params)
        except ImportError:
            try:
                self.database = peewee.PostgresqlDatabase(db_name, **conn_params)
            except Exception as e:
                raise SpecStoreIOError(f"Failed to initialize Peewee PostgreSQL driver: {e}") from e

        db_proxy.initialize(self.database)

        try:
            self.database.create_tables([DBBuild, DBSpec, DBEdge, DBImplemented])
            # Dynamic schema update for backward compatibility with existing databases
            columns = [c.name for c in self.database.get_columns("dbbuild")]
            if "is_deleted" not in columns:
                self.database.execute_sql("ALTER TABLE dbbuild ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE")
        except peewee.PeeweeException as e:
            raise SpecStoreIOError(f"Failed to create PostgreSQL tables: {e}") from e
