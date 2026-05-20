'''
Strangler Fig XML adapter — translates legacy XML spec files to the SpecStore protocol.
'''

import os
import glob
import hashlib
import datetime
from typing import Optional, List
from xml.etree import ElementTree as ET

from libspec.store import (
    Component,
    Snapshot,
    Implemented,
    SpecStore,
    SpecStoreIOError,
    SpecStoreNotFoundError,
    SpecStoreCorruptedDataError,
)


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

    def list_snapshots(self) -> List[Snapshot]:
        if not self.is_dir:
            if not os.path.exists(self.xml_path):
                return []
            try:
                tree = ET.parse(self.xml_path)
                root = tree.getroot()
                snapshot_id = root.get("id") or "legacy"
                created_at_str = root.get("date-created") or datetime.datetime.now(datetime.timezone.utc).isoformat()
                master_hash = root.get("master-hash") or "0" * 64
                git_commit = root.get("git-commit")
                return [Snapshot(
                    id=snapshot_id,
                    created_at=datetime.datetime.fromisoformat(created_at_str),
                    master_hash=master_hash,
                    git_commit=git_commit
                )]
            except Exception:
                return []

        files = glob.glob(os.path.join(self.xml_path, "spec-*.xml"))
        files.sort(key=os.path.getmtime)
        snapshots = []
        for f in files:
            try:
                tree = ET.parse(f)
                root = tree.getroot()
                snapshot_id = root.get("id") or "legacy"
                created_at_str = root.get("date-created") or datetime.datetime.now(datetime.timezone.utc).isoformat()
                master_hash = root.get("master-hash") or "0" * 64
                git_commit = root.get("git-commit")
                snapshots.append(Snapshot(
                    id=snapshot_id,
                    created_at=datetime.datetime.fromisoformat(created_at_str),
                    master_hash=master_hash,
                    git_commit=git_commit
                ))
            except Exception:
                continue
        return snapshots

    def get_snapshot(self, id_or_hash: str) -> Optional[Snapshot]:
        snapshots = self.list_snapshots()
        matching = []
        for s in snapshots:
            if id_or_hash in s.id or id_or_hash in s.master_hash or s.id.startswith(id_or_hash) or s.master_hash.startswith(id_or_hash):
                matching.append(s)
        if len(matching) == 1:
            return matching[0]
        elif len(matching) > 1:
            raise SpecStoreNotFoundError(f"Multiple snapshots matched '{id_or_hash}'.")
        raise SpecStoreNotFoundError(f"Snapshot '{id_or_hash}' not found in the XML store.")

    def get_components_for_snapshot(self, snapshot: Snapshot) -> List[Component]:
        if not isinstance(snapshot, Snapshot):
            raise TypeError("snapshot must be a valid Snapshot instance.")

        target_file = None
        if self.is_dir:
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
            raise SpecStoreNotFoundError(f"XML file for snapshot {snapshot.id} not found.")

        try:
            tree = ET.parse(target_file)
            components = []
            for node in tree.getroot().findall("specification"):
                ref = node.get("ref")
                if ref:
                    is_template = node.get("template") == "true"
                    doc_tag = "docstring_template" if is_template else "docstring"
                    doc_node = node.find(doc_tag)
                    docstring = doc_node.text if doc_node is not None else ""
                    inherits = [r.text for r in node.findall("inherits/ref") if r.text]
                    comp_hash = node.get("hash") or hashlib.sha256(docstring.encode("utf-8")).hexdigest()
                    components.append(Component(
                        ref=ref,
                        docstring=docstring,
                        is_template=is_template,
                        inherits=inherits,
                        hash=comp_hash
                    ))
            return components
        except Exception as e:
            raise SpecStoreCorruptedDataError(f"Failed parsing components from snapshot {snapshot.id}: {e}") from e
