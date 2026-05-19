'''
Concrete implementation of the isolated, backend-agnostic Data Access Layer (SpecStore),
including Peewee schemas for SQLite and PostgreSQL.
'''

import os
import datetime
import hashlib
from typing import Protocol, Optional, List
from dataclasses import dataclass
from xml.etree import ElementTree as ET

# Attempt to import Peewee
try:
    import peewee
except ImportError:
    peewee = None

# =========================================================================
# 1. Core Domain Dataclasses
# =========================================================================

@dataclass(frozen=True)
class Component:
    ref: str
    docstring: str
    is_template: bool
    inherits: List[str]
    hash: str

    def __post_init__(self):
        if not isinstance(self.ref, str) or not self.ref.strip():
            raise ValueError("Component 'ref' must be a non-empty string.")
        if not isinstance(self.docstring, str):
            raise TypeError("Component 'docstring' must be a string.")
        if not isinstance(self.is_template, bool):
            raise TypeError("Component 'is_template' must be a boolean.")
        if not isinstance(self.inherits, list) or not all(isinstance(x, str) for x in self.inherits):
            raise TypeError("Component 'inherits' must be a list of strings.")
        if not isinstance(self.hash, str) or len(self.hash) != 64:
            raise ValueError("Component 'hash' must be a 64-character SHA-256 hash string.")


@dataclass(frozen=True)
class Snapshot:
    id: str
    created_at: datetime.datetime
    master_hash: str
    git_commit: Optional[str] = None

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("Snapshot 'id' must be a non-empty string.")
        if not isinstance(self.created_at, datetime.datetime):
            raise TypeError("Snapshot 'created_at' must be a datetime object.")
        if not isinstance(self.master_hash, str) or len(self.master_hash) != 64:
            raise ValueError("Snapshot 'master_hash' must be a 64-character SHA-256 hash string.")
        if self.git_commit is not None and not isinstance(self.git_commit, str):
            raise TypeError("Snapshot 'git_commit' must be a string or None.")


@dataclass(frozen=True)
class Implemented:
    ref: str
    spec_hash: str
    file: str
    line: int
    session_id: Optional[str] = None

    def __post_init__(self):
        if not isinstance(self.ref, str) or not self.ref.strip():
            raise ValueError("Implemented 'ref' must be a non-empty string.")
        if not isinstance(self.spec_hash, str) or len(self.spec_hash) != 64:
            raise ValueError("Implemented 'spec_hash' must be a 64-character SHA-256 hash string.")
        if not isinstance(self.file, str) or not self.file.strip():
            raise ValueError("Implemented 'file' must be a non-empty string.")
        if not isinstance(self.line, int) or self.line <= 0:
            raise ValueError("Implemented 'line' must be a positive integer.")
        if self.session_id is not None and not isinstance(self.session_id, str):
            raise TypeError("Implemented 'session_id' must be a string or None.")


# =========================================================================
# 2. Domain Exception Hierarchy
# =========================================================================

class SpecStoreError(Exception):
    '''Root ancestral exception class for all errors originating from the storage layer.'''


class SpecStoreIOError(SpecStoreError):
    '''Raised when reading from or writing to the database, remote server, or filesystem fails.'''


class SpecStoreNotFoundError(SpecStoreError):
    '''Raised when a requested snapshot or component reference is not present in the current build context.'''


class SpecStoreCorruptedDataError(SpecStoreError):
    '''Raised when data verification, deserialization, or rendered docstring formatting fails.'''


# =========================================================================
# 3. SpecStore Protocol Definitions
# =========================================================================

class SpecStore(Protocol):
    '''Backend-agnostic interface boundary establishing the data access operations.'''
    
    def store_snapshot(self, components: List[Component], git_commit: Optional[str] = None, created_at: Optional[datetime.datetime] = None) -> Snapshot:
        '''Atomically registers a compiled tree of components under a new Build snapshot.
        
        Raises SpecStoreIOError if the persistence fails.
        '''
        ...

    def current_snapshot(self) -> Optional[Snapshot]:
        '''Retrieves the active, latest metadata snapshot, or None if the store is empty.'''
        ...

    def get_component(self, ref: str) -> Component:
        '''Retrieves a single component's metadata from the current active snapshot.
        
        Raises SpecStoreNotFoundError if the ref does not exist.
        '''
        ...

    def list_components(self) -> List[Component]:
        '''Lists all components defined under the current active snapshot.'''
        ...

    def store_implemented(self, record: Implemented) -> None:
        '''Appends an implementation log entry immediately upon code injection.
        Enforces a strict one-component-per-invocation rule to ensure atomic writes.
        
        Raises SpecStoreIOError on failure.
        '''
        ...

    def list_implemented(self, snapshot: Snapshot) -> List[Implemented]:
        '''Retrieves all implementation tracking log entries scoped to the snapshot.'''
        ...


# =========================================================================
# 4. Strangler Fig XML Adapter Implementation
# =========================================================================

class XmlSpecStore(SpecStore):
    '''Strangler Fig passive adapter translating Legacy XML files to the SpecStore interface.
    Performs safe, atomic updates using a temporary file replaced via os.replace.
    Can operate either on a single target XML file, or a directory containing multiple hashed spec-*.xml files.
    '''

    def __init__(self, xml_path: str):
        if not isinstance(xml_path, str) or not xml_path.strip():
            raise ValueError("XmlSpecStore requires a valid XML file path.")
        self.xml_path = os.path.abspath(xml_path)
        # Determine if the path is a directory (does not end with .xml)
        self.is_dir = os.path.isdir(self.xml_path) or not self.xml_path.lower().endswith(".xml")
        if self.is_dir:
            os.makedirs(self.xml_path, exist_ok=True)
            self._latest_xml_path = None
        else:
            self._latest_xml_path = self.xml_path

    def _find_latest_xml_file(self) -> Optional[str]:
        if not self.is_dir:
            return self.xml_path if os.path.exists(self.xml_path) else None
        
        import glob
        pattern = os.path.join(self.xml_path, "spec-*.xml")
        files = glob.glob(pattern)
        if not files:
            # Fallback to check any xml files
            pattern_all = os.path.join(self.xml_path, "*.xml")
            files = glob.glob(pattern_all)
            if not files:
                return None
                
        # Parse XML root dates to determine the chronological latest
        file_info = []
        for f in files:
            try:
                tree = ET.parse(f)
                root = tree.getroot()
                date_str = root.get("date-created")
                if date_str:
                    file_info.append((date_str, f))
                else:
                    mtime = os.path.getmtime(f)
                    dt = datetime.datetime.fromtimestamp(mtime, datetime.timezone.utc)
                    file_info.append((dt.isoformat(), f))
            except Exception:
                mtime = os.path.getmtime(f)
                dt = datetime.datetime.fromtimestamp(mtime, datetime.timezone.utc)
                file_info.append((dt.isoformat(), f))
                
        if not file_info:
            return None
            
        file_info.sort(key=lambda x: x[0])
        return file_info[-1][1]

    def _parse_xml(self) -> Optional[ET.ElementTree]:
        target = self._find_latest_xml_file()
        if target is None or not os.path.exists(target):
            return None
        try:
            return ET.parse(target)
        except Exception as e:
            raise SpecStoreCorruptedDataError(f"Failed to parse XML file at {target}: {e}") from e

    def _write_xml_atomically(self, root: ET.Element, target_path: Optional[str] = None):
        # Format and pretty print
        xml_bytes = ET.tostring(root, encoding="utf-8")
        from xml.dom import minidom
        pretty_xml = minidom.parseString(xml_bytes).toprettyxml(indent="  ")
        
        if target_path is None:
            if self.is_dir:
                # Strip dates/ids temporarily for deterministic naming content digest
                orig_id = root.get("id")
                orig_date = root.get("date-created")
                if "id" in root.attrib:
                    del root.attrib["id"]
                if "date-created" in root.attrib:
                    del root.attrib["date-created"]
                    
                clean_xml_bytes = ET.tostring(root, encoding="utf-8")
                
                # Restore original attributes
                if orig_id is not None:
                    root.set("id", orig_id)
                if orig_date is not None:
                    root.set("date-created", orig_date)
                    
                from libspec.util import easy_hash
                digest = easy_hash(clean_xml_bytes.decode("utf-8"))[:20]
                filename = f"spec-{digest}.xml"
                target_path = os.path.join(self.xml_path, filename)
            else:
                target_path = self.xml_path

        temp_path = target_path + ".tmp"
        try:
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(pretty_xml)
            os.replace(temp_path, target_path)
            if self.is_dir:
                self._latest_xml_path = target_path
        except OSError as e:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise SpecStoreIOError(f"Atomic XML write failed at {target_path}: {e}") from e

    def store_snapshot(self, components: List[Component], git_commit: Optional[str] = None, created_at: Optional[datetime.datetime] = None) -> Snapshot:
        if not isinstance(components, list) or not all(isinstance(c, Component) for c in components):
            raise TypeError("components must be a list of Component instances.")
            
        if created_at is None:
            created_at = datetime.datetime.now(datetime.timezone.utc)
        
        # Sort components alphabetically by ref to compute deterministic master hash
        sorted_components = sorted(components, key=lambda c: c.ref)
        hasher = hashlib.sha256()
        for comp in sorted_components:
            hasher.update(comp.hash.encode("utf-8"))
        master_hash = hasher.hexdigest()
        
        snapshot_id = master_hash[:16]
        
        root = ET.Element("specification_set")
        root.set("id", snapshot_id)
        root.set("date-created", created_at.isoformat())
        root.set("master-hash", master_hash)
        
        try:
            from importlib.metadata import version
            libspec_v = version("libspec")
        except Exception:
            libspec_v = "5.0.0"
        root.set("libspec-version", libspec_v)
        
        if git_commit:
            root.set("git-commit", git_commit)
            
        # Add specifications
        for comp in sorted_components:
            spec_elem = ET.SubElement(root, "specification")
            spec_elem.set("ref", comp.ref)
            spec_elem.set("type", comp.ref.split(".")[-1])
            spec_elem.set("template", "true" if comp.is_template else "false")
            spec_elem.set("hash", comp.hash)
            
            doc_tag = "docstring_template" if comp.is_template else "docstring"
            doc_elem = ET.SubElement(spec_elem, doc_tag)
            doc_elem.text = comp.docstring
            
            if comp.inherits:
                inherits_elem = ET.SubElement(spec_elem, "inherits")
                for parent in comp.inherits:
                    parent_ref = ET.SubElement(inherits_elem, "ref")
                    parent_ref.text = parent
                    
        # Preserve existing implemented claims if latest file already exists
        tree = self._parse_xml()
        if tree is not None:
            claims_elem = tree.getroot().find("implemented_claims")
            if claims_elem is not None:
                root.append(claims_elem)

        self._write_xml_atomically(root)
        return Snapshot(id=snapshot_id, created_at=created_at, master_hash=master_hash, git_commit=git_commit)

    def current_snapshot(self) -> Optional[Snapshot]:
        tree = self._parse_xml()
        if tree is None:
            return None
        root = tree.getroot()
        try:
            snapshot_id = root.get("id") or "legacy"
            created_at_str = root.get("date-created") or datetime.datetime.now(datetime.timezone.utc).isoformat()
            master_hash = root.get("master-hash") or "0" * 64
            git_commit = root.get("git-commit")
            
            return Snapshot(
                id=snapshot_id,
                created_at=datetime.datetime.fromisoformat(created_at_str),
                master_hash=master_hash,
                git_commit=git_commit
            )
        except Exception as e:
            raise SpecStoreCorruptedDataError(f"Failed parsing Snapshot metadata from XML: {e}") from e

    def get_component(self, ref: str) -> Component:
        if not isinstance(ref, str) or not ref.strip():
            raise ValueError("Component FQN reference must be a non-empty string.")
            
        tree = self._parse_xml()
        if tree is None:
            raise SpecStoreNotFoundError("SpecStore is empty. No components found.")
            
        spec_node = tree.getroot().find(f"./specification[@ref='{ref}']")
        if spec_node is None:
            raise SpecStoreNotFoundError(f"Component reference '{ref}' not found in the XML store.")
            
        try:
            is_template = spec_node.get("template") == "true"
            doc_tag = "docstring_template" if is_template else "docstring"
            doc_node = spec_node.find(doc_tag)
            docstring = doc_node.text if doc_node is not None else ""
            
            inherits = [node.text for node in spec_node.findall("inherits/ref") if node.text]
            comp_hash = spec_node.get("hash") or hashlib.sha256(docstring.encode("utf-8")).hexdigest()
            
            return Component(
                ref=ref,
                docstring=docstring,
                is_template=is_template,
                inherits=inherits,
                hash=comp_hash
            )
        except Exception as e:
            raise SpecStoreCorruptedDataError(f"Failed parsing component '{ref}' from XML: {e}") from e

    def list_components(self) -> List[Component]:
        tree = self._parse_xml()
        if tree is None:
            return []
        components = []
        for node in tree.getroot().findall("specification"):
            ref = node.get("ref")
            if ref:
                components.append(self.get_component(ref))
        return components

    def store_implemented(self, record: Implemented) -> None:
        if not isinstance(record, Implemented):
            raise TypeError("record must be a valid Implemented instance.")
            
        latest_file = self._find_latest_xml_file()
        if latest_file is None:
            raise SpecStoreNotFoundError("Cannot record implementation claim on an empty SpecStore snapshot.")
            
        try:
            tree = ET.parse(latest_file)
        except Exception as e:
            raise SpecStoreCorruptedDataError(f"Failed parsing XML file at {latest_file}: {e}") from e
            
        root = tree.getroot()
        claims_elem = root.find("implemented_claims")
        if claims_elem is None:
            claims_elem = ET.SubElement(root, "implemented_claims")
            
        # Deduplicate: remove any existing claim for the exact same ref
        for existing in claims_elem.findall(f"./claim[@ref='{record.ref}']"):
            claims_elem.remove(existing)
            
        claim = ET.SubElement(claims_elem, "claim")
        claim.set("ref", record.ref)
        claim.set("spec_hash", record.spec_hash)
        claim.set("file", record.file)
        claim.set("line", str(record.line))
        if record.session_id:
            claim.set("session_id", record.session_id)
            
        self._write_xml_atomically(root, target_path=latest_file)

    def list_implemented(self, snapshot: Snapshot) -> List[Implemented]:
        if not isinstance(snapshot, Snapshot):
            raise TypeError("snapshot must be a valid Snapshot instance.")
            
        # Determine correct file associated with snapshot
        target_file = None
        if self.is_dir:
            import glob
            files = glob.glob(os.path.join(self.xml_path, "spec-*.xml"))
            for f in files:
                try:
                    tree = ET.parse(f)
                    root = tree.getroot()
                    if root.get("master-hash") == snapshot.master_hash or root.get("id") == snapshot.id:
                        target_file = f
                        break
                except Exception:
                    continue
        else:
            target_file = self.xml_path
            
        if target_file is None or not os.path.exists(target_file):
            return []
            
        try:
            tree = ET.parse(target_file)
        except Exception as e:
            raise SpecStoreCorruptedDataError(f"Failed parsing XML file at {target_file}: {e}") from e
            
        root = tree.getroot()
        claims_elem = root.find("implemented_claims")
        if claims_elem is None:
            return []
            
        claims = []
        for node in claims_elem.findall("claim"):
            try:
                ref = node.get("ref")
                spec_hash = node.get("spec_hash")
                file_path = node.get("file")
                line_str = node.get("line")
                session_id = node.get("session_id")
                
                if ref and spec_hash and file_path and line_str:
                    claims.append(Implemented(
                        ref=ref,
                        spec_hash=spec_hash,
                        file=file_path,
                        line=int(line_str),
                        session_id=session_id
                    ))
            except Exception as e:
                raise SpecStoreCorruptedDataError(f"Failed parsing implementation record from XML: {e}") from e
        return claims


# =========================================================================
# 5. Peewee Database Store Engine (SQLite / PostgreSQL)
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


class SQLiteSpecStore(SpecStore):
    '''Production Peewee SQLite adapter with automatic schemas and append-only 2-build pruning policy.'''

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

    def current_snapshot(self) -> Optional[Snapshot]:
        try:
            build = DBBuild.select().order_by(DBBuild.created_at.desc()).first()
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

    def get_component(self, ref: str) -> Component:
        if not isinstance(ref, str) or not ref.strip():
            raise ValueError("Component reference FQN must be a non-empty string.")
            
        try:
            build = DBBuild.select().order_by(DBBuild.created_at.desc()).first()
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
            build = DBBuild.select().order_by(DBBuild.created_at.desc()).first()
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
            build = DBBuild.select().order_by(DBBuild.created_at.desc()).first()
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
        except peewee.PeeweeException as e:
            raise SpecStoreIOError(f"Failed to create PostgreSQL tables: {e}") from e


# =========================================================================
# 6. Global Store Factory (Dynamic resolution based on Env)
# =========================================================================

def get_store() -> SpecStore:
    '''Constructs and returns the active SpecStore backend according to configurations.
    
    Order of precedence:
    1. If `LIBSPEC_DATABASE_URL` matches a postgres scheme, returns PostgresSpecStore.
    2. Else if `LIBSPEC_DATABASE_URL` matches a sqlite path, returns SQLiteSpecStore.
    3. Else fallback to XmlSpecStore located at 'spec-build/spec_store.xml'.
    '''
    db_url = os.environ.get("LIBSPEC_DATABASE_URL")
    if db_url:
        if db_url.startswith("postgresql://") or db_url.startswith("postgres://"):
            # Parse connection URL
            import urllib.parse
            url = urllib.parse.urlparse(db_url)
            db_name = url.path[1:]
            conn_params = {
                'user': url.username,
                'password': url.password,
                'host': url.hostname,
                'port': url.port or 5432,
            }
            # Strip None values
            conn_params = {k: v for k, v in conn_params.items() if v is not None}
            return PostgresSpecStore(db_name, **conn_params)
        elif db_url.startswith("sqlite://"):
            db_path = db_url.replace("sqlite://", "", 1)
            # Remove leading slash if it exists
            if db_path.startswith("/") and os.path.exists(db_path[1:]):
                db_path = db_path[1:]
            return SQLiteSpecStore(db_path)
            
    # Default database path: .libspec/libspec.db
    default_dir = os.path.abspath(".libspec")
    os.makedirs(default_dir, exist_ok=True)
    default_db = os.path.join(default_dir, "libspec.db")
    return SQLiteSpecStore(default_db)
