import asyncio
import os
import tempfile

import pytest

from libspec.watcher import InotifyFileWatcher


@pytest.mark.anyio
async def test_inotify_file_watcher_detects_changes():
    with tempfile.TemporaryDirectory() as tmpdir:
        file1 = os.path.join(tmpdir, "test1.jsonl")
        with open(file1, "w") as f:
            f.write("initial")

        changes = []

        def on_change():
            changes.append(True)

        watcher = InotifyFileWatcher([file1], on_change)
        watcher.start()

        try:
            # Modify the file
            with open(file1, "w") as f:
                f.write("modified")

            # Allow event loop to run and process the inotify event
            for _ in range(10):
                await asyncio.sleep(0.05)
                if changes:
                    break

            assert len(changes) > 0
        finally:
            watcher.stop()
