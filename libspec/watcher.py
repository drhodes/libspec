import ctypes
import os
import struct
import select
import threading
from typing import List, Callable

# Load libc
try:
    libc = ctypes.CDLL(None)
except Exception:
    try:
        libc = ctypes.CDLL("libc.so.6")
    except Exception:
        libc = None

# sys/inotify.h constants
IN_MODIFY = 0x00000002
IN_CLOSE_WRITE = 0x00000008
IN_MOVED_TO = 0x00000080
IN_CREATE = 0x00000100

class BaseFileWatcher:
    def __init__(self, paths: List[str], on_change: Callable[[], None]):
        self.paths = [os.path.abspath(p) for p in paths]
        self.on_change = on_change

    def start(self) -> None:
        """Start monitoring."""
        raise NotImplementedError()

    def stop(self) -> None:
        """Stop monitoring."""
        raise NotImplementedError()

class InotifyFileWatcher(BaseFileWatcher):
    # REQUIREMENT-ID: spec.repl.ReplInotifyWatcherReq
    def __init__(self, paths: List[str], on_change: Callable[[], None]):
        super().__init__(paths, on_change)
        self.fd = -1
        self.wds = {}  # wd -> dir_path
        self._thread = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if not libc:
            raise RuntimeError("libc not loaded; inotify is not available.")
        
        self.fd = libc.inotify_init()
        if self.fd < 0:
            raise OSError("Failed to initialize inotify")

        watched_dirs = set(os.path.dirname(p) for p in self.paths)
        mask = IN_MODIFY | IN_CLOSE_WRITE | IN_MOVED_TO | IN_CREATE
        
        for dpath in watched_dirs:
            if not os.path.exists(dpath):
                continue
            wd = libc.inotify_add_watch(self.fd, dpath.encode("utf-8"), mask)
            if wd < 0:
                self.stop()
                raise OSError(f"Failed to add watch for directory: {dpath}")
            self.wds[wd] = dpath

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()

    def _watch_loop(self) -> None:
        while not self._stop_event.is_set() and self.fd >= 0:
            try:
                r, _, _ = select.select([self.fd], [], [], 0.2)
            except (OSError, ValueError):
                break
            if not r:
                continue
                
            try:
                data = os.read(self.fd, 4096)
            except OSError:
                break

            offset = 0
            triggered = False
            while offset < len(data):
                if len(data) - offset < 16:
                    break
                wd, mask, cookie, name_len = struct.unpack_from("iIII", data, offset)
                name = b""
                if name_len > 0:
                    name_bytes = data[offset + 16 : offset + 16 + name_len]
                    name = name_bytes.split(b"\x00")[0]
                offset += 16 + name_len

                dir_path = self.wds.get(wd)
                if dir_path and name:
                    try:
                        event_name = name.decode("utf-8")
                    except UnicodeDecodeError:
                        continue
                    full_path = os.path.abspath(os.path.join(dir_path, event_name))
                    if full_path in self.paths:
                        triggered = True

            if triggered and not self._stop_event.is_set():
                self.on_change()

    def stop(self) -> None:
        self._stop_event.set()
        if self.fd >= 0:
            fd = self.fd
            self.fd = -1
            try:
                for wd in list(self.wds.keys()):
                    libc.inotify_rm_watch(fd, wd)
                os.close(fd)
            except OSError:
                pass
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None
        self.wds.clear()
