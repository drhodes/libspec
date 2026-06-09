'''
Append-only JSON Lines (JSONL / NDJSON) SpecStore implementation.
'''

import os
import json
import hashlib
import datetime
from typing import Optional, List, Union, Dict

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

    def __init__(self, filepath: str, auto_upgrade: bool = True):
        if not isinstance(filepath, str) or not filepath.strip():
            raise ValueError("JsonLinesSpecStore requires a valid file path.")
        self.filepath = os.path.abspath(filepath)
        # REQUIREMENT-ID: spec.store_compaction.UntrackedSidecarStore
        self.vcs_links_filepath = os.path.join(os.path.dirname(self.filepath), "vcs_links.jsonl")

        # Ensure target directory exists
        dir_path = os.path.dirname(self.filepath)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
            # REQUIREMENT-ID: spec.store_compaction.AutomatedIgnoreConfiguration
            gitignore_path = os.path.join(dir_path, ".gitignore")
            if not os.path.exists(gitignore_path):
                try:
                    with open(gitignore_path, "w", encoding="utf-8") as gf:
                        gf.write("vcs_links.jsonl\n*.bak\n")
                except Exception:
                    pass

        # Internal state reconstructed via replay
        self._snapshots = []
        self._all_snapshots = []
        self._snapshot_components = {}   # snapshot_id -> list[Component]
        self._snapshot_implemented = {}  # snapshot_id -> dict[ref -> Implemented]
        self._all_components = {}        # hash -> Component
        self._snapshot_dependencies = {} # snapshot_id -> dict[ref -> list[str]]
        self._pending_dependencies = []  # list of (ref, depends_on)
        self._pending_implemented = []   # list of Implemented

        # Initial replay to populate state
        self._replay()

        # Check for legacy and self-heal automatically
        if auto_upgrade and os.path.exists(self.filepath):
            raw_events = []
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            raw_events.append(json.loads(line))
            except Exception:
                pass

            has_legacy = False
            for event in raw_events:
                if event.get("type") == "snapshot" and "components" not in event:
                    has_legacy = True
                    break

            if has_legacy:
                self._auto_upgrade_log(raw_events)
                self._replay()

    def _parse_file_events(self, filepath: str, manifests_to_resolve: list) -> None:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
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
                            self._all_snapshots.append(snapshot)

                            # Bind pending dependency and implemented events to this snapshot's ID
                            snap_id = snapshot.id
                            for ref, depends_on in self._pending_dependencies:
                                if snap_id not in self._snapshot_dependencies:
                                    self._snapshot_dependencies[snap_id] = {}
                                if ref not in self._snapshot_dependencies[snap_id]:
                                    self._snapshot_dependencies[snap_id][ref] = []
                                if depends_on not in self._snapshot_dependencies[snap_id][ref]:
                                    self._snapshot_dependencies[snap_id][ref].append(depends_on)
                            self._pending_dependencies = []

                            for record in self._pending_implemented:
                                if snap_id not in self._snapshot_implemented:
                                    self._snapshot_implemented[snap_id] = {}
                                self._snapshot_implemented[snap_id][record.ref] = record
                            self._pending_implemented = []

                            # Defer manifest resolution to the end of replay
                            if "components" in data:
                                manifests_to_resolve.append((snapshot.id, data["components"]))
                        elif rec_type in ("tombstone", "delete_snapshot"):
                            snapshot_id = data["snapshot_id"]
                            self._snapshots = [s for s in self._snapshots if s.id != snapshot_id]
                        elif rec_type in ("restore", "restore_snapshot"):
                            snapshot_id = data["snapshot_id"]
                            snap = next((s for s in self._all_snapshots if s.id == snapshot_id), None)
                            if snap and snap not in self._snapshots:
                                self._snapshots.append(snap)
                                self._snapshots.sort(key=lambda s: s.created_at)
                        elif rec_type == "component":
                            comp = Component(
                                ref=data["ref"],
                                docstring=data["docstring"],
                                is_template=data["is_template"],
                                inherits=data["inherits"],
                                hash=data["hash"],
                                is_dependency=data.get("is_dependency", False)
                            )
                            self._all_components[comp.hash] = comp

                            # Legacy backwards compatibility
                            snapshot_id = data.get("snapshot_id")
                            if snapshot_id:
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
                            if snapshot_id == "PENDING":
                                self._pending_implemented.append(record)
                            else:
                                if snapshot_id not in self._snapshot_implemented:
                                    self._snapshot_implemented[snapshot_id] = {}
                                self._snapshot_implemented[snapshot_id][data["ref"]] = record
                        elif rec_type == "dependency":
                            snapshot_id = data["snapshot_id"]
                            ref = data["ref"]
                            depends_on = data["depends_on"]
                            if snapshot_id == "PENDING":
                                self._pending_dependencies.append((ref, depends_on))
                            else:
                                if snapshot_id not in self._snapshot_dependencies:
                                    self._snapshot_dependencies[snapshot_id] = {}
                                if ref not in self._snapshot_dependencies[snapshot_id]:
                                    self._snapshot_dependencies[snapshot_id][ref] = []
                                if depends_on not in self._snapshot_dependencies[snapshot_id][ref]:
                                    self._snapshot_dependencies[snapshot_id][ref].append(depends_on)
                        elif rec_type == "vcs_link":
                            snapshot_id = data["snapshot_id"]
                            vcs = data["vcs"]
                            revision = data["revision"]
                            for s in self._snapshots:
                                if s.id == snapshot_id or s.master_hash == snapshot_id:
                                    if vcs == "git":
                                        object.__setattr__(s, 'git_commit', revision)
                            for s in self._all_snapshots:
                                if s.id == snapshot_id or s.master_hash == snapshot_id:
                                    if vcs == "git":
                                        object.__setattr__(s, 'git_commit', revision)
                        else:
                            raise SpecStoreCorruptedDataError(f"Unknown record type '{rec_type}' at line {line_num} in {os.path.basename(filepath)}")
                    except json.JSONDecodeError as je:
                        raise SpecStoreCorruptedDataError(f"JSON decode failed on line {line_num} in {os.path.basename(filepath)}: {je}") from je
                    except Exception as e:
                        if isinstance(e, SpecStoreCorruptedDataError):
                            raise
                        raise SpecStoreCorruptedDataError(f"Error parsing log record on line {line_num} in {os.path.basename(filepath)}: {e}") from e
        except OSError as oe:
            raise SpecStoreIOError(f"Failed to read JSON Lines file {os.path.basename(filepath)}: {oe}") from oe

    def _replay(self) -> None:
        self._snapshots = []
        self._all_snapshots = []
        self._snapshot_components = {}
        self._snapshot_implemented = {}
        self._all_components = {}
        self._snapshot_dependencies = {}
        self._pending_dependencies = []
        self._pending_implemented = []

        manifests_to_resolve = []

        # REQUIREMENT-ID: spec.store_compaction.UnifiedSidecarReplay
        if os.path.exists(self.filepath):
            self._parse_file_events(self.filepath, manifests_to_resolve)

        if os.path.exists(self.vcs_links_filepath):
            self._parse_file_events(self.vcs_links_filepath, manifests_to_resolve)

        # Post-replay: Resolve deferred CAS component manifests
        for snap_id, manifest in manifests_to_resolve:
            resolved_components = []
            for ref, comp_hash in manifest.items():
                comp = self._all_components.get(comp_hash)
                if comp is None:
                    raise SpecStoreCorruptedDataError(
                        f"Component with hash '{comp_hash}' referenced by snapshot '{snap_id}' not found in log."
                    )
                if comp.ref != ref:
                    comp = Component(
                        ref=ref,
                        docstring=comp.docstring,
                        is_template=comp.is_template,
                        inherits=comp.inherits,
                        hash=comp.hash,
                        is_dependency=comp.is_dependency
                    )
                resolved_components.append(comp)
            self._snapshot_components[snap_id] = resolved_components

    def _append(self, record: dict, filepath: Optional[str] = None) -> None:
        target = filepath or self.filepath
        try:
            # Deterministic canonical serialization
            json_str = json.dumps(record, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
            with open(target, "a", encoding="utf-8") as f:
                f.write(json_str + "\n")
        except OSError as oe:
            raise SpecStoreIOError(f"Failed writing log record to {os.path.basename(target)}: {oe}") from oe

    def _append_snapshot_record(self, snapshot: Snapshot, components_manifest: dict) -> None:
        rec = {
            "type": "snapshot",
            "id": snapshot.id,
            "created_at": snapshot.created_at.isoformat(),
            "master_hash": snapshot.master_hash,
            "git_commit": snapshot.git_commit,
            "components": components_manifest
        }
        self._append(rec)
        self._snapshots.append(snapshot)
        self._all_snapshots.append(snapshot)

    def _append_component_record(self, comp: Component) -> None:
        rec = {
            "type": "component",
            "ref": comp.ref,
            "docstring": comp.docstring,
            "is_template": comp.is_template,
            "inherits": comp.inherits,
            "hash": comp.hash,
            "is_dependency": comp.is_dependency
        }
        self._append(rec)
        self._all_components[comp.hash] = comp

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

        # Determine the timestamp for this build/migration entry
        actual_created_at = created_at
        if actual_created_at is None:
            actual_created_at = datetime.datetime.now(datetime.timezone.utc)

        sorted_components = sorted(components, key=lambda c: c.ref)
        hasher = hashlib.sha256()
        for comp in sorted_components:
            hasher.update(comp.ref.encode("utf-8"))
            hasher.update(comp.hash.encode("utf-8"))
        master_hash = hasher.hexdigest()

        snapshot_id = master_hash[:16]

        # Prevent creating sequential duplicate builds if the spec hasn't changed from the most recent active build
        if self.most_recent_hash() == master_hash:
            return self.current_snapshot()

        # Check for an existing snapshot with the same hash
        existing = next((s for s in reversed(self._snapshots) if s.id == snapshot_id), None)
        
        if existing is not None:
            # It exists but isn't current. 
            # If this is a fresh build (created_at is None) OR if we're migrating 
            # a newer/different version, we append a new snapshot record.
            # If created_at was provided (migration), we only append if it's strictly newer
            # or if the git_commit has changed.
            if created_at is not None and actual_created_at <= existing.created_at and git_commit == existing.git_commit:
                return existing

        # 1. Build manifest and snapshot record
        manifest = {c.ref: c.hash for c in sorted_components}
        snapshot = Snapshot(id=snapshot_id, created_at=actual_created_at, master_hash=master_hash, git_commit=git_commit)
        self._append_snapshot_record(snapshot, manifest)

        # 2. Deduplicate components and persist
        for comp in sorted_components:
            if comp.hash not in self._all_components:
                self._append_component_record(comp)
        
        self._snapshot_components[snapshot.id] = list(sorted_components)
        self._replay()

        return snapshot

    def current_snapshot(self) -> Optional[Snapshot]:
        if not self._snapshots:
            return None
        return self._snapshots[-1]

    def most_recent_hash(self) -> Optional[str]:
        current = self.current_snapshot()
        return current.master_hash if current else None

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
        for snap in self._all_snapshots:
            if snap.id == id_or_hash or snap.master_hash == id_or_hash:
                return snap
        for snap in self._all_snapshots:
            if snap.id.startswith(id_or_hash) or snap.master_hash.startswith(id_or_hash):
                return snap
        raise SpecStoreNotFoundError(f"Snapshot with identifier or hash prefix '{id_or_hash}' not found.")

    def get_components_for_snapshot(self, snapshot: Snapshot) -> List[Component]:
        if not isinstance(snapshot, Snapshot):
            raise TypeError("snapshot must be a valid Snapshot instance.")
        if not any(s.id == snapshot.id for s in self._snapshots):
            raise SpecStoreNotFoundError(f"Snapshot '{snapshot.id}' not found in active snapshots.")
        return self._snapshot_components.get(snapshot.id, [])

    def delete_snapshot(self, snapshot: Snapshot) -> None:
        if not isinstance(snapshot, Snapshot):
            raise TypeError("snapshot must be a valid Snapshot instance.")

        if not any(s.id == snapshot.id for s in self._snapshots):
            raise SpecStoreNotFoundError(f"Snapshot '{snapshot.id}' not found in active history.")

        rec = {
            "type": "tombstone",
            "snapshot_id": snapshot.id
        }
        self._append(rec)
        self._replay()

    def restore_snapshot(self, snapshot: Snapshot) -> None:
        if not isinstance(snapshot, Snapshot):
            raise TypeError("snapshot must be a valid Snapshot instance.")

        if not any(s.id == snapshot.id for s in self._all_snapshots):
            raise SpecStoreNotFoundError(f"Snapshot '{snapshot.id}' has never been recorded in this store.")

        if any(s.id == snapshot.id for s in self._snapshots):
            # Already active/non-deleted
            return

        rec = {
            "type": "restore",
            "snapshot_id": snapshot.id
        }
        self._append(rec)
        self._replay()

    def store_vcs_link(self, snapshot_id: str, vcs: str, revision: str, metadata: Optional[dict] = None) -> None:
        if not isinstance(snapshot_id, str) or not snapshot_id.strip():
            raise ValueError("snapshot_id must be a non-empty string.")
        if not isinstance(vcs, str) or not vcs.strip():
            raise ValueError("vcs must be a non-empty string.")
        if not isinstance(revision, str) or not revision.strip():
            raise ValueError("revision must be a non-empty string.")

        # Resolve snapshot (raises error if missing)
        snapshot = self.get_snapshot(snapshot_id)

        rec = {
            "type": "vcs_link",
            "snapshot_id": snapshot.id,
            "vcs": vcs,
            "revision": revision,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "metadata": metadata or {}
        }
        # REQUIREMENT-ID: spec.store_compaction.UntrackedSidecarStore
        self._append(rec, filepath=self.vcs_links_filepath)
        self._replay()

    def store_dependency(self, ref: str, depends_on: str, snapshot_id: str = "PENDING") -> None:
        if not isinstance(ref, str) or not ref.strip():
            raise ValueError("ref must be a non-empty string.")
        if not isinstance(depends_on, str) or not depends_on.strip():
            raise ValueError("depends_on must be a non-empty string.")
        if not isinstance(snapshot_id, str) or not snapshot_id.strip():
            raise ValueError("snapshot_id must be a non-empty string.")

        rec = {
            "type": "dependency",
            "snapshot_id": snapshot_id,
            "ref": ref,
            "depends_on": depends_on,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        self._append(rec)
        self._replay()

    def list_dependencies(self, snapshot_or_id: Union[str, Snapshot]) -> Dict[str, List[str]]:
        if isinstance(snapshot_or_id, Snapshot):
            snap_id = snapshot_or_id.id
        elif isinstance(snapshot_or_id, str):
            snap_id = snapshot_or_id
        else:
            raise TypeError("snapshot_or_id must be a Snapshot or a string ID.")

        if snap_id == "PENDING":
            res = {}
            for ref, depends_on in self._pending_dependencies:
                if ref not in res:
                    res[ref] = []
                if depends_on not in res[ref]:
                    res[ref].append(depends_on)
            return res

        return self._snapshot_dependencies.get(snap_id, {})


    def get_raw_events(self) -> List[dict]:
        events = []
        for path in (self.filepath, self.vcs_links_filepath):
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            events.append(data)
                        except json.JSONDecodeError as je:
                            raise SpecStoreCorruptedDataError(
                                f"JSON decode failed on line {line_num} in {os.path.basename(path)}: {je}"
                            ) from je
            except OSError as oe:
                raise SpecStoreIOError(f"Failed to read file {os.path.basename(path)}: {oe}") from oe
        return events

    def compact(self, dry_run: bool = False) -> dict:
        """Compacts the transaction log by:
        - Squashing redundant intermediate snapshots tied to the same Git commit.
        - Deduplicating components content-addressably (CAS).
        - Automatically upgrading legacy log entries to the new manifest format.
        - Doing safe atomic temp-write and replace.
        """
        raw_events = self.get_raw_events()

        # Group snapshots by non-empty git commit
        commit_groups = {}
        for s in self._all_snapshots:
            if s.git_commit and s.git_commit != "PENDING":
                if s.git_commit not in commit_groups:
                    commit_groups[s.git_commit] = []
                commit_groups[s.git_commit].append(s)

        redundant_snapshot_ids = set()
        for commit, group in commit_groups.items():
            if len(group) <= 1:
                continue
            # Survivor is the chronologically latest snapshot in the commit group
            _survivor = group[-1]
            for s in group[:-1]:
                redundant_snapshot_ids.add(s.id)

        # Detect legacy format upgrades
        has_legacy = False
        for event in raw_events:
            if event.get("type") == "snapshot" and "components" not in event:
                has_legacy = True
                break

        # Calculate space savings
        original_size = 0
        if os.path.exists(self.filepath):
            original_size = os.path.getsize(self.filepath)

        compacted_events = []
        written_component_hashes = set()
        active_snapshot_ids = {s.id for s in self._snapshots if s.id not in redundant_snapshot_ids}

        legacy_components_by_snap = {}
        for event in raw_events:
            if event.get("type") == "component" and "snapshot_id" in event:
                snap_id = event["snapshot_id"]
                comp = Component(
                    ref=event["ref"],
                    docstring=event["docstring"],
                    is_template=event["is_template"],
                    inherits=event["inherits"],
                    hash=event["hash"],
                    is_dependency=event.get("is_dependency", False)
                )
                if snap_id not in legacy_components_by_snap:
                    legacy_components_by_snap[snap_id] = []
                legacy_components_by_snap[snap_id].append(comp)

        pending_deps = []
        pending_impls = []

        for event in raw_events:
            e_type = event.get("type")
            if e_type == "snapshot":
                snap_id = event["id"]
                if snap_id in redundant_snapshot_ids or snap_id not in active_snapshot_ids:
                    continue

                if "components" in event:
                    manifest = event["components"]
                    for comp_ref, comp_hash in manifest.items():
                        if comp_hash not in written_component_hashes:
                            comp = self._all_components.get(comp_hash)
                            if comp:
                                compacted_events.append({
                                    "type": "component",
                                    "ref": comp.ref,
                                    "docstring": comp.docstring,
                                    "is_template": comp.is_template,
                                    "inherits": comp.inherits,
                                    "hash": comp.hash,
                                    "is_dependency": comp.is_dependency
                                })
                                written_component_hashes.add(comp_hash)

                    # Output all pending dependencies bound to this snapshot ID
                    for dep in pending_deps:
                        compacted_events.append({
                            "type": "dependency",
                            "snapshot_id": snap_id,
                            "ref": dep["ref"],
                            "depends_on": dep["depends_on"],
                            "created_at": dep["created_at"]
                        })
                    pending_deps = []

                    # Output all pending implemented bound to this snapshot ID
                    for impl in pending_impls:
                        compacted_events.append({
                            "type": "implemented",
                            "snapshot_id": snap_id,
                            "ref": impl["ref"],
                            "spec_hash": impl["spec_hash"],
                            "file": impl["file"],
                            "line": impl["line"],
                            "session_id": impl.get("session_id")
                        })
                    pending_impls = []

                    compacted_events.append(event)
                else:
                    comps = legacy_components_by_snap.get(snap_id, [])
                    manifest = {}
                    for comp in comps:
                        manifest[comp.ref] = comp.hash
                        if comp.hash not in written_component_hashes:
                            compacted_events.append({
                                "type": "component",
                                "ref": comp.ref,
                                "docstring": comp.docstring,
                                "is_template": comp.is_template,
                                "inherits": comp.inherits,
                                "hash": comp.hash,
                                "is_dependency": comp.is_dependency
                            })
                            written_component_hashes.add(comp.hash)

                    # Output all pending dependencies bound to this snapshot ID
                    for dep in pending_deps:
                        compacted_events.append({
                            "type": "dependency",
                            "snapshot_id": snap_id,
                            "ref": dep["ref"],
                            "depends_on": dep["depends_on"],
                            "created_at": dep["created_at"]
                        })
                    pending_deps = []

                    # Output all pending implemented bound to this snapshot ID
                    for impl in pending_impls:
                        compacted_events.append({
                            "type": "implemented",
                            "snapshot_id": snap_id,
                            "ref": impl["ref"],
                            "spec_hash": impl["spec_hash"],
                            "file": impl["file"],
                            "line": impl["line"],
                            "session_id": impl.get("session_id")
                        })
                    pending_impls = []

                    compacted_events.append({
                        "type": "snapshot",
                        "id": snap_id,
                        "created_at": event["created_at"],
                        "master_hash": event["master_hash"],
                        "git_commit": event.get("git_commit"),
                        "components": manifest
                    })
            elif e_type == "implemented":
                snap_id = event["snapshot_id"]
                if snap_id == "PENDING":
                    pending_impls.append(event)
                else:
                    if snap_id in redundant_snapshot_ids or snap_id not in active_snapshot_ids:
                        continue
                    compacted_events.append(event)
            elif e_type == "dependency":
                snap_id = event["snapshot_id"]
                if snap_id == "PENDING":
                    pending_deps.append(event)
                else:
                    if snap_id in redundant_snapshot_ids or snap_id not in active_snapshot_ids:
                        continue
                    compacted_events.append(event)
            elif e_type == "vcs_link":
                snap_id = event["snapshot_id"]
                if snap_id in redundant_snapshot_ids or snap_id not in active_snapshot_ids:
                    continue
                compacted_events.append(event)

        # Re-add any remaining genuinely pending dependencies and implementations
        for dep in pending_deps:
            compacted_events.append(dep)
        for impl in pending_impls:
            compacted_events.append(impl)


        compacted_json_lines = []
        for event in compacted_events:
            json_str = json.dumps(event, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
            compacted_json_lines.append(json_str + "\n")

        compacted_content = "".join(compacted_json_lines)
        compacted_size = len(compacted_content.encode("utf-8"))
        reclaimed_bytes = max(0, original_size - compacted_size)

        if not dry_run:
            if has_legacy:
                backup_path = self.filepath + ".bak"
                try:
                    import shutil
                    shutil.copy2(self.filepath, backup_path)
                except Exception as e:
                    raise SpecStoreIOError(f"Failed to create migration backup file: {e}") from e

            temp_path = self.filepath + ".tmp"
            try:
                with open(temp_path, "w", encoding="utf-8") as f:
                    f.write(compacted_content)
                os.replace(temp_path, self.filepath)
            except Exception as e:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                raise SpecStoreIOError(f"Failed to atomically write compacted log file: {e}") from e

            # Truncate/empty the sidecar file since its surviving vcs_links are now consolidated in the main log
            if os.path.exists(self.vcs_links_filepath):
                try:
                    with open(self.vcs_links_filepath, "w", encoding="utf-8"):
                        pass
                except Exception:
                    pass

            self._replay()

        return {
            "original_size": original_size,
            "compacted_size": compacted_size,
            "reclaimed_bytes": reclaimed_bytes,
            "pruned_snapshots_count": len(redundant_snapshot_ids),
            "upgraded_legacy_format": has_legacy
        }

    def _auto_upgrade_log(self, raw_events: list) -> None:
        # REQUIREMENT-ID: spec.store_compaction.SelfHealingAutoMigration
        import shutil
        backup_path = self.filepath + ".bak"
        temp_path = self.filepath + ".tmp"
        
        # 1. Create a safe backup before any modification
        try:
            shutil.copy2(self.filepath, backup_path)
        except Exception:
            # If we can't create a backup, we do not perform migration to prevent data loss risk!
            return

        try:
            # 2. Perform the in-memory migration
            legacy_components_by_snap = {}
            for event in raw_events:
                if event.get("type") == "component" and "snapshot_id" in event:
                    snap_id = event["snapshot_id"]
                    comp = Component(
                        ref=event["ref"],
                        docstring=event["docstring"],
                        is_template=event["is_template"],
                        inherits=event["inherits"],
                        hash=event["hash"],
                        is_dependency=event.get("is_dependency", False)
                    )
                    if snap_id not in legacy_components_by_snap:
                        legacy_components_by_snap[snap_id] = []
                    legacy_components_by_snap[snap_id].append(comp)

            compacted_events = []
            written_component_hashes = set()
            active_snapshot_ids = {s.id for s in self._snapshots}

            for event in raw_events:
                e_type = event.get("type")
                if e_type == "snapshot":
                    snap_id = event["id"]
                    if snap_id not in active_snapshot_ids:
                        continue

                    if "components" in event:
                        manifest = event["components"]
                        for comp_ref, comp_hash in manifest.items():
                            if comp_hash not in written_component_hashes:
                                comp = self._all_components.get(comp_hash)
                                if comp:
                                    compacted_events.append({
                                        "type": "component",
                                        "ref": comp.ref,
                                        "docstring": comp.docstring,
                                        "is_template": comp.is_template,
                                        "inherits": comp.inherits,
                                        "hash": comp.hash,
                                        "is_dependency": comp.is_dependency
                                    })
                                    written_component_hashes.add(comp_hash)
                        compacted_events.append(event)
                    else:
                        comps = legacy_components_by_snap.get(snap_id, [])
                        manifest = {}
                        for comp in comps:
                            manifest[comp.ref] = comp.hash
                            if comp.hash not in written_component_hashes:
                                compacted_events.append({
                                    "type": "component",
                                    "ref": comp.ref,
                                    "docstring": comp.docstring,
                                    "is_template": comp.is_template,
                                    "inherits": comp.inherits,
                                    "hash": comp.hash,
                                    "is_dependency": comp.is_dependency
                                })
                                written_component_hashes.add(comp.hash)

                        compacted_events.append({
                            "type": "snapshot",
                            "id": snap_id,
                            "created_at": event["created_at"],
                            "master_hash": event.get("master_hash") or "0"*64,
                            "git_commit": event.get("git_commit"),
                            "components": manifest
                        })
                elif e_type == "implemented":
                    snap_id = event["snapshot_id"]
                    if snap_id not in active_snapshot_ids:
                        continue
                    compacted_events.append(event)
                elif e_type == "vcs_link":
                    snap_id = event["snapshot_id"]
                    if snap_id not in active_snapshot_ids:
                        continue
                    compacted_events.append(event)
                elif e_type == "dependency":
                    compacted_events.append(event)
                elif e_type in ("tombstone", "restore"):
                    compacted_events.append(event)

            # 3. Write migrated content to .tmp file
            compacted_json_lines = []
            for event in compacted_events:
                json_str = json.dumps(event, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
                compacted_json_lines.append(json_str + "\n")
            compacted_content = "".join(compacted_json_lines)

            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(compacted_content)

            # 4. Perform atomic os.replace swap
            os.replace(temp_path, self.filepath)

        except Exception:
            # 5. Rollback on any failure: restore from backup and clean up temp
            try:
                if os.path.exists(backup_path):
                    shutil.copy2(backup_path, self.filepath)
            except Exception:
                pass
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception:
                pass


