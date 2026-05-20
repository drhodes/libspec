'''
Append-only JSON Lines (JSONL / NDJSON) SpecStore implementation.
'''

import os
import json
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


class JsonLinesSpecStore(SpecStore):
    '''Append-only JSON Lines (JSONL / NDJSON) storage engine implementing the SpecStore protocol.
    Guarantees 100% git-friendliness, canonical determinism, and full event-sourced replay.
    '''

    def __init__(self, filepath: str):
        if not isinstance(filepath, str) or not filepath.strip():
            raise ValueError("JsonLinesSpecStore requires a valid file path.")
        self.filepath = os.path.abspath(filepath)

        # Ensure target directory exists
        dir_path = os.path.dirname(self.filepath)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)

        # Internal state reconstructed via replay
        self._snapshots = []
        self._snapshot_components = {}   # snapshot_id -> list[Component]
        self._snapshot_implemented = {}  # snapshot_id -> dict[ref -> Implemented]

        # Initial replay to populate state
        self._replay()

    def _replay(self) -> None:
        self._snapshots = []
        self._snapshot_components = {}
        self._snapshot_implemented = {}

        if not os.path.exists(self.filepath):
            return

        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        rec_type = data.get("type")
                        if rec_type == "snapshot":
                            created_at = datetime.datetime.fromisoformat(data["created_at"])
                            snapshot = Snapshot(
                                id=data["id"],
                                created_at=created_at,
                                master_hash=data["master_hash"],
                                git_commit=data.get("git_commit")
                            )
                            self._snapshots.append(snapshot)
                        elif rec_type == "component":
                            snapshot_id = data["snapshot_id"]
                            comp = Component(
                                ref=data["ref"],
                                docstring=data["docstring"],
                                is_template=data["is_template"],
                                inherits=data["inherits"],
                                hash=data["hash"]
                            )
                            if snapshot_id not in self._snapshot_components:
                                self._snapshot_components[snapshot_id] = []
                            self._snapshot_components[snapshot_id].append(comp)
                        elif rec_type == "implemented":
                            snapshot_id = data["snapshot_id"]
                            record = Implemented(
                                ref=data["ref"],
                                spec_hash=data["spec_hash"],
                                file=data["file"],
                                line=data["line"],
                                session_id=data.get("session_id")
                            )
                            if snapshot_id not in self._snapshot_implemented:
                                self._snapshot_implemented[snapshot_id] = {}
                            self._snapshot_implemented[snapshot_id][data["ref"]] = record
                        else:
                            raise SpecStoreCorruptedDataError(f"Unknown record type '{rec_type}' at line {line_num}")
                    except json.JSONDecodeError as je:
                        raise SpecStoreCorruptedDataError(f"JSON decode failed on line {line_num}: {je}") from je
                    except Exception as e:
                        if isinstance(e, SpecStoreCorruptedDataError):
                            raise
                        raise SpecStoreCorruptedDataError(f"Error parsing log record on line {line_num}: {e}") from e
        except OSError as oe:
            raise SpecStoreIOError(f"Failed to read JSON Lines file: {oe}") from oe

    def _append(self, record: dict) -> None:
        try:
            # Deterministic canonical serialization
            json_str = json.dumps(record, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
            with open(self.filepath, "a", encoding="utf-8") as f:
                f.write(json_str + "\n")
        except OSError as oe:
            raise SpecStoreIOError(f"Failed writing log record: {oe}") from oe

    def _append_snapshot_record(self, snapshot: Snapshot) -> None:
        rec = {
            "type": "snapshot",
            "id": snapshot.id,
            "created_at": snapshot.created_at.isoformat(),
            "master_hash": snapshot.master_hash,
            "git_commit": snapshot.git_commit
        }
        self._append(rec)
        self._snapshots.append(snapshot)

    def _append_component_record(self, snapshot_id: str, comp: Component) -> None:
        rec = {
            "type": "component",
            "snapshot_id": snapshot_id,
            "ref": comp.ref,
            "docstring": comp.docstring,
            "is_template": comp.is_template,
            "inherits": comp.inherits,
            "hash": comp.hash
        }
        self._append(rec)
        if snapshot_id not in self._snapshot_components:
            self._snapshot_components[snapshot_id] = []
        self._snapshot_components[snapshot_id].append(comp)

    def _append_implemented_record(self, snapshot_id: str, record: Implemented) -> None:
        rec = {
            "type": "implemented",
            "snapshot_id": snapshot_id,
            "ref": record.ref,
            "spec_hash": record.spec_hash,
            "file": record.file,
            "line": record.line,
            "session_id": record.session_id
        }
        self._append(rec)
        if snapshot_id not in self._snapshot_implemented:
            self._snapshot_implemented[snapshot_id] = {}
        self._snapshot_implemented[snapshot_id][record.ref] = record

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

        # Maintain idempotency
        existing = next((s for s in self._snapshots if s.id == snapshot_id), None)
        if existing is not None:
            return existing

        snapshot = Snapshot(id=snapshot_id, created_at=created_at, master_hash=master_hash, git_commit=git_commit)

        self._append_snapshot_record(snapshot)
        for comp in sorted_components:
            self._append_component_record(snapshot_id, comp)

        return snapshot

    def current_snapshot(self) -> Optional[Snapshot]:
        if not self._snapshots:
            return None
        return self._snapshots[-1]

    def get_component(self, ref: str) -> Component:
        snapshot = self.current_snapshot()
        if snapshot is None:
            raise SpecStoreNotFoundError("Cannot get component from an empty SpecStore snapshot.")
        components = self._snapshot_components.get(snapshot.id, [])
        comp = next((c for c in components if c.ref == ref), None)
        if comp is None:
            raise SpecStoreNotFoundError(f"Component '{ref}' not found in active snapshot.")
        return comp

    def list_components(self) -> List[Component]:
        snapshot = self.current_snapshot()
        if snapshot is None:
            return []
        return self._snapshot_components.get(snapshot.id, [])

    def store_implemented(self, record: Implemented) -> None:
        if not isinstance(record, Implemented):
            raise TypeError("record must be a valid Implemented instance.")

        snapshot = self.current_snapshot()
        if snapshot is None:
            raise SpecStoreNotFoundError("Cannot record implementation claim on an empty SpecStore snapshot.")

        self._append_implemented_record(snapshot.id, record)

    def list_implemented(self, snapshot: Snapshot) -> List[Implemented]:
        if not isinstance(snapshot, Snapshot):
            raise TypeError("snapshot must be a valid Snapshot instance.")
        claims_dict = self._snapshot_implemented.get(snapshot.id, {})
        return list(claims_dict.values())

    def list_snapshots(self) -> List[Snapshot]:
        return list(self._snapshots)

    def get_snapshot(self, id_or_hash: str) -> Optional[Snapshot]:
        for snap in self._snapshots:
            if snap.id == id_or_hash or snap.master_hash == id_or_hash:
                return snap
        for snap in self._snapshots:
            if snap.id.startswith(id_or_hash) or snap.master_hash.startswith(id_or_hash):
                return snap
        raise SpecStoreNotFoundError(f"Snapshot with identifier or hash prefix '{id_or_hash}' not found.")

    def get_components_for_snapshot(self, snapshot: Snapshot) -> List[Component]:
        if not isinstance(snapshot, Snapshot):
            raise TypeError("snapshot must be a valid Snapshot instance.")
        if snapshot.id not in self._snapshot_components:
            exists = any(s.id == snapshot.id for s in self._snapshots)
            if not exists:
                raise SpecStoreNotFoundError(f"Snapshot '{snapshot.id}' not found in the store.")
        return self._snapshot_components.get(snapshot.id, [])
