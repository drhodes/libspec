import hashlib
from pathlib import Path
import difflib

def easy_hash(text):
    return hashlib.md5(text.encode()).hexdigest()

def fqn(obj):
    return f"{type(obj).__module__}.{type(obj).__qualname__}"
        

def diff_two_latest(dirpath):
    files = [p for p in Path(dirpath).iterdir() if p.is_file()]
    if len(files) < 2:
        raise ValueError("Need at least two files")

    latest = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[:2]
    newer, older = latest[0], latest[1]

    with older.open() as f1, newer.open() as f2:
        return "".join(difflib.unified_diff(
            f1.readlines(),
            f2.readlines(),
            fromfile=str(older),
            tofile=str(newer),
        ))
