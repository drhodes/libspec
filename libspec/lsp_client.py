import json
import logging
import os
import subprocess
import threading
import time

log = logging.getLogger(__name__)


class LspError(Exception):
    """Custom exception for LSP-related failures with a 'story' context."""

    def __init__(self, message, step=None, details=None):
        story = f"LSP Failure: {message}"
        if step:
            story = f"Error during '{step}': {message}"
        if details:
            story += f"\nDetails: {details}"
        super().__init__(story)


class LspClient:
    """
    A lightweight JSON-RPC client for communicating with a Language Server
    over stdio.
    """

    def __init__(self, command=["uv", "run", "pylsp"]):
        self.command = command
        self.process = None
        self.next_id = 1
        self.responses = {}
        self.event = threading.Event()
        self.read_thread = None
        self.stderr_thread = None

    def start(self, root_uri):
        """Start the LSP process and send the initialize request."""
        assert root_uri.startswith("file://"), (
            f"root_uri must be a file URI, got: {root_uri}"
        )

        if self.process:
            return

        try:
            self.process = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
            )
        except FileNotFoundError:
            raise LspError(
                f"Could not find the LSP executable '{self.command[0]}'.",
                step="process spawn",
                details="Ensure python-lsp-server is installed in the active environment.",
            )

        self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.read_thread.start()

        self.stderr_thread = threading.Thread(target=self._stderr_loop, daemon=True)
        self.stderr_thread.start()

        try:
            # Initialize the LSP
            self.send_request(
                "initialize",
                {
                    "processId": os.getpid(),
                    "rootUri": root_uri,
                    "capabilities": {
                        "textDocument": {
                            "hover": {"contentFormat": ["markdown", "plaintext"]},
                            "definition": {"dynamicRegistration": True},
                            "references": {"dynamicRegistration": True},
                            "documentSymbol": {
                                "hierarchicalDocumentSymbolSupport": True
                            },
                        },
                        "workspace": {"symbol": {"dynamicRegistration": True}},
                    },
                },
            )
            self.send_notification("initialized", {})
        except Exception as e:
            self.stop()
            raise LspError(f"Initialization failed: {e}", step="LSP handshake")

    def send_request(self, method, params):
        """Send a JSON-RPC request and wait for the response."""
        assert self.process is not None, (
            "LSP process must be started before sending requests."
        )

        req_id = self.next_id
        self.next_id += 1

        message = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}

        try:
            self._write_message(message)
        except Exception as e:
            raise LspError(f"Failed to write message: {e}", step=method)

        # Wait for response (timeout 10s)
        start_time = time.time()
        while req_id not in self.responses:
            if not self.read_thread.is_alive():
                raise LspError("LSP reader thread died unexpectedly.", step=method)
            if time.time() - start_time > 10:
                raise LspError("Request timed out after 10s.", step=method)
            time.sleep(0.1)

        res = self.responses.pop(req_id)
        if "error" in res:
            err = res["error"]
            raise LspError(
                err.get("message", "Unknown LSP error"),
                step=method,
                details=json.dumps(err),
            )

        return res

    def execute_command(self, command, arguments=None):
        """Execute a custom workspace command."""
        return self.send_request(
            "workspace/executeCommand",
            {"command": command, "arguments": arguments or []},
        )

    def send_notification(self, method, params):
        """Send a JSON-RPC notification (no response expected)."""
        if not self.process:
            return
        message = {"jsonrpc": "2.0", "method": method, "params": params}
        self._write_message(message)

    def _write_message(self, message):
        content = json.dumps(message)
        header = f"Content-Length: {len(content)}\r\n\r\n"
        self.process.stdin.write(header.encode("ascii"))
        self.process.stdin.write(content.encode("utf-8"))
        self.process.stdin.flush()

    def _read_loop(self):
        try:
            while self.process and self.process.stdout:
                line = self.process.stdout.readline().decode("ascii")
                if not line:
                    break
                if line.startswith("Content-Length: "):
                    length = int(line.split(": ")[1].strip())
                    # Skip until \r\n\r\n
                    while True:
                        header_line = self.process.stdout.readline().decode("ascii")
                        if header_line == "\r\n" or header_line == "\n":
                            break

                    content = self.process.stdout.read(length).decode("utf-8")
                    if not content:
                        break
                    message = json.loads(content)

                    if "id" in message:
                        res_id = message["id"]
                        self.responses[res_id] = message
        except Exception as e:
            log.error(f"LSP Reader Error: {e}")

    def _stderr_loop(self):
        try:
            while self.process and self.process.stderr:
                line = self.process.stderr.readline().decode("utf-8", errors="replace")
                if not line:
                    break
                # Forward server logs to our logger
                log.info(f"LSP Server Log: {line.strip()}")
        except Exception as e:
            log.error(f"LSP Stderr Reader Error: {e}")

    def stop(self):
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except Exception:
                self.process.kill()
            self.process = None
