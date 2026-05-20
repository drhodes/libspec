'''
Universal SpecStore migration utility.

Transfers the complete history from any SpecStore backend to any other,
using the in-memory domain objects (Snapshot, Component, Implemented) as
the intermediate representation. M → memory → N, not M × N.
'''

from libspec.store import SpecStore, SpecStoreIOError


def migrate(source: SpecStore, target: SpecStore) -> dict:
    '''Transfer all snapshots, components, and implementation claims from
    source to target in chronological order.

    Returns a summary dict: {"migrated": int, "skipped": int}.

    Raises SpecStoreIOError if any read or write step fails.
    '''
    try:
        snapshots = source.list_snapshots()
    except Exception as e:
        raise SpecStoreIOError(f"migrate: failed to read snapshots from source: {e}") from e

    migrated = 0
    skipped = 0

    for snap in snapshots:
        preexisting = _target_has_snapshot(target, snap.master_hash)
        try:
            components = source.get_components_for_snapshot(snap)
        except Exception as e:
            raise SpecStoreIOError(
                f"migrate: failed to read components for snapshot {snap.id}: {e}"
            ) from e

        try:
            claims = source.list_implemented(snap)
        except Exception as e:
            raise SpecStoreIOError(
                f"migrate: failed to read claims for snapshot {snap.id}: {e}"
            ) from e

        try:
            written = target.store_snapshot(
                components,
                git_commit=snap.git_commit,
                created_at=snap.created_at,
            )
        except Exception as e:
            raise SpecStoreIOError(
                f"migrate: failed to write snapshot {snap.id} to target: {e}"
            ) from e

        if preexisting:
            skipped += 1
            continue

        # Write claims into target under the written snapshot's active context
        for claim in claims:
            try:
                target.store_implemented(claim)
            except Exception as e:
                raise SpecStoreIOError(
                    f"migrate: failed to write claim {claim.ref} for "
                    f"snapshot {snap.id}: {e}"
                ) from e

        migrated += 1

    return {"migrated": migrated, "skipped": skipped}


def _target_has_snapshot(target: SpecStore, master_hash: str) -> bool:
    try:
        target.get_snapshot(master_hash)
        return True
    except Exception:
        return False


def store_from_url(url: str) -> SpecStore:
    '''Construct a SpecStore from a URL string using the same scheme
    conventions as LIBSPEC_DATABASE_URL.

    Supported schemes: sqlite://, jsonl://, postgresql://, postgres://
    '''
    from libspec.store import (
        SQLiteSpecStore,
        JsonLinesSpecStore,
        PostgresSpecStore,
    )
    import urllib.parse

    if url.startswith("sqlite://"):
        db_path = url[len("sqlite://"):]
        os = __import__("os")
        if db_path.startswith("/.") or (db_path.startswith("/") and os.path.exists(db_path[1:])):
            db_path = db_path[1:]
        return SQLiteSpecStore(db_path)
    elif url.startswith("jsonl://"):
        return JsonLinesSpecStore(url[len("jsonl://"):])
    elif url.startswith("postgresql://") or url.startswith("postgres://"):
        parsed = urllib.parse.urlparse(url)
        db_name = parsed.path[1:]
        conn_params = {k: v for k, v in {
            "user": parsed.username,
            "password": parsed.password,
            "host": parsed.hostname,
            "port": parsed.port or 5432,
        }.items() if v is not None}
        return PostgresSpecStore(db_name, **conn_params)
    else:
        raise SpecStoreIOError(
            f"Unrecognised store URL scheme: '{url}'. "
            "Expected sqlite://, jsonl://, or postgresql://."
        )
