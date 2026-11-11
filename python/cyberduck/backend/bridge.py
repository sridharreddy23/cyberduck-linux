"""
Subprocess bridge to the Cyberduck Java core engine daemon.
"""
import json
import os
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from PyQt5.QtCore import QObject, pyqtSignal

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class CyberduckBridge(QObject):
    # Signals
    ready = pyqtSignal(str)
    status_changed = pyqtSignal(str)
    connected = pyqtSignal(dict)
    disconnected = pyqtSignal()
    listing_received = pyqtSignal(str, list)
    file_created = pyqtSignal(str)
    file_deleted = pyqtSignal(str)
    transfer_started = pyqtSignal(str)
    transfer_progress = pyqtSignal(str, int, int, float, str)
    transfer_complete = pyqtSignal(str, bool)
    transfer_failed = pyqtSignal(str, str)
    credentials_requested = pyqtSignal(dict)
    error_received = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process: Optional[subprocess.Popen] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._running = False
        self._callbacks: Dict[str, Callable[[dict], None]] = {}
        self._req_counter = 0
        self._lock = threading.Lock()
        self.is_connected = False
        self.current_workdir = "/"
        self.current_hostname = ""
        self.cached_protocols = []

    def start(self):
        """Start the Java BridgeDaemon process."""
        if self.process and self.process.poll() is None:
            return

        if os.environ.get("CYBERDUCK_CLASSPATH"):
            classpath = os.environ["CYBERDUCK_CLASSPATH"]
        elif (REPO_ROOT / "linux" / "target" / "jpackage-input").is_dir():
            classpath = f"{REPO_ROOT}/linux/target/classes:{REPO_ROOT}/s3/target/classes:{REPO_ROOT}/linux/target/jpackage-input/*"
        elif Path("/opt/cyberduck/lib/app").is_dir():
            classpath = "/opt/cyberduck/lib/app/*"
        else:
            classpath = f"{REPO_ROOT}/linux/target/classes:{REPO_ROOT}/s3/target/classes:{REPO_ROOT}/linux/target/jpackage-input/*:/opt/cyberduck/lib/app/*"

        # Resolve java binary
        java_bin = "java"
        if os.environ.get("JAVA_HOME") and Path(f"{os.environ['JAVA_HOME']}/bin/java").is_file():
            java_bin = f"{os.environ['JAVA_HOME']}/bin/java"
        elif not shutil.which("java"):
            for candidate in (
                "/usr/lib/jvm/default-java/bin/java",
                "/usr/lib/jvm/java-21-openjdk-amd64/bin/java",
                "/usr/lib/jvm/java-17-openjdk-amd64/bin/java",
                "/usr/lib/jvm/java-25-openjdk-amd64/bin/java",
            ):
                if Path(candidate).is_file():
                    java_bin = candidate
                    break

        cmd = [
            java_bin,
            "--enable-native-access=ALL-UNNAMED",
            "-cp",
            classpath,
            "ch.cyberduck.linux.BridgeDaemon",
        ]

        work_dir = str(REPO_ROOT) if (REPO_ROOT / "pom.xml").exists() else str(Path.home())

        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                cwd=work_dir,
            )
            self._running = True
            self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._reader_thread.start()

            # Request protocol list
            self.send_command("protocols", {}, self._on_protocols)
        except Exception as e:
            self.error_received.emit(f"Failed to start Cyberduck engine: {e}")

    def stop(self):
        """Shut down the daemon."""
        self._running = False
        if self.process:
            try:
                self.process.terminate()
            except Exception:
                pass
            self.process = None

    def send_command(self, cmd: str, params: Optional[Dict[str, Any]] = None, callback: Optional[Callable[[dict], None]] = None):
        """Send a JSON command to the daemon."""
        if not self.process or self.process.poll() is not None:
            self.error_received.emit("Cyberduck engine is not running")
            return

        with self._lock:
            self._req_counter += 1
            req_id = str(self._req_counter)
            if callback:
                self._callbacks[req_id] = callback

        payload = {"id": req_id, "cmd": cmd}
        if params:
            payload.update(params)

        try:
            line = json.dumps(payload) + "\n"
            self.process.stdin.write(line)
            self.process.stdin.flush()
        except Exception as e:
            self.error_received.emit(f"Communication error: {e}")

    def _read_loop(self):
        """Background thread reading JSON output from the daemon."""
        while self._running and self.process and self.process.poll() is None:
            try:
                line = self.process.stdout.readline()
                if not line:
                    break
                line = line.strip()
                if not line or not line.startswith("{"):
                    continue

                data = json.loads(line)
                self._handle_message(data)
            except Exception:
                continue

    def _handle_message(self, data: dict):
        """Dispatch daemon messages to callbacks or Qt signals."""
        # Check if it's an event
        if "event" in data:
            event = data["event"]
            if event == "ready":
                self.ready.emit(data.get("version", "9.6.1"))
            elif event == "status":
                self.status_changed.emit(data.get("message", ""))
            elif event == "transferProgress":
                self.transfer_progress.emit(
                    data.get("transferId", ""),
                    data.get("size", 0),
                    data.get("transferred", 0),
                    data.get("progress", 0.0),
                    data.get("text", ""),
                )
            elif event == "transferComplete":
                self.transfer_complete.emit(
                    data.get("transferId", ""),
                    data.get("complete", True),
                )
            elif event == "transferFailed":
                self.transfer_failed.emit(
                    data.get("transferId", ""),
                    data.get("error", "Unknown error"),
                )
            elif event == "promptCredentials":
                self.credentials_requested.emit(data)
            return

        # Check if it's a response with ID
        req_id = data.get("id")
        cb = None
        if req_id:
            with self._lock:
                cb = self._callbacks.pop(req_id, None)

        if cb:
            cb(data)

        # Check standard response statuses if no callback handled it
        if not cb and data.get("status") == "error":
            self.error_received.emit(data.get("error", "Unknown error"))

    def _on_protocols(self, data: dict):
        if data.get("status") == "ok":
            self.cached_protocols = data.get("protocols", [])

    def connect_host(self, protocol: str, hostname: str, port: int, username: str, password: Optional[str] = None, identity: Optional[str] = None, token: Optional[str] = None, callback: Optional[Callable[[dict], None]] = None):
        """Connect to a remote server."""
        self.status_changed.emit(f"Connecting to {hostname}...")
        params = {
            "protocol": protocol,
            "hostname": hostname,
            "port": port,
            "username": username,
            "password": password,
            "identity": identity,
            "token": token,
        }

        def _cb(res: dict):
            if res.get("status") == "ok":
                self.is_connected = True
                self.current_workdir = res.get("workdir", "/")
                self.current_hostname = res.get("hostname", hostname)
                self.connected.emit(res)
                self.list_directory(self.current_workdir)
            else:
                self.is_connected = False
                self.error_received.emit(res.get("error", "Connection failed"))
            if callback:
                callback(res)

        self.send_command("connect", params, _cb)

    def respond_credentials(self, prompt_id: str, username: str, password: str, token: Optional[str] = None, canceled: bool = False):
        """Send credentials response back to waiting daemon prompt."""
        payload = {
            "cmd": "credentialsResponse",
            "promptId": prompt_id,
            "username": username,
            "password": password,
            "token": token,
            "canceled": canceled,
        }
        try:
            line = json.dumps(payload) + "\n"
            if self.process and self.process.stdin:
                self.process.stdin.write(line)
                self.process.stdin.flush()
        except Exception as e:
            self.error_received.emit(f"Failed to deliver credentials: {e}")

    def disconnect_host(self):
        """Disconnect current session."""
        def _cb(res: dict):
            self.is_connected = False
            self.current_workdir = "/"
            self.current_hostname = ""
            self.disconnected.emit()

        self.send_command("disconnect", {}, _cb)

    def list_directory(self, path: str):
        """List contents of a remote directory."""
        self.status_changed.emit(f"Listing directory {path}...")
        params = {"path": path}

        def _cb(res: dict):
            if res.get("status") == "ok":
                self.current_workdir = res.get("path", path)
                files = res.get("files", [])
                self.listing_received.emit(self.current_workdir, files)
                self.status_changed.emit(f"{len(files)} items")
            else:
                self.error_received.emit(res.get("error", "Failed to list directory"))

        self.send_command("list", params, _cb)

    def create_folder(self, name: str):
        """Create a new remote folder."""
        params = {"name": name}

        def _cb(res: dict):
            if res.get("status") == "ok":
                self.file_created.emit(res.get("created", name))
                self.list_directory(self.current_workdir)
            else:
                self.error_received.emit(res.get("error", "Failed to create folder"))

        self.send_command("mkdir", params, _cb)

    def delete_item(self, path: str, is_dir: bool = False):
        """Delete remote file or directory."""
        params = {"path": path, "isDir": is_dir}

        def _cb(res: dict):
            if res.get("status") == "ok":
                self.file_deleted.emit(res.get("deleted", path))
                self.list_directory(self.current_workdir)
            else:
                self.error_received.emit(res.get("error", "Failed to delete item"))

        self.send_command("delete", params, _cb)

    def download_file(self, remote_path: str, local_path: str, transfer_id: Optional[str] = None):
        """Download remote file to local destination."""
        params = {
            "remote": remote_path,
            "local": local_path,
        }
        if transfer_id:
            params["transferId"] = transfer_id

        def _cb(res: dict):
            if res.get("status") == "started":
                self.transfer_started.emit(res.get("transferId", ""))
            else:
                self.error_received.emit(res.get("error", "Failed to start download"))

        self.send_command("download", params, _cb)

    def upload_file(self, local_path: str, remote_name: Optional[str] = None, transfer_id: Optional[str] = None):
        """Upload local file to current workdir."""
        params = {
            "local": local_path,
        }
        if remote_name:
            params["name"] = remote_name
        if transfer_id:
            params["transferId"] = transfer_id

        def _cb(res: dict):
            if res.get("status") == "started":
                self.transfer_started.emit(res.get("transferId", ""))
            else:
                self.error_received.emit(res.get("error", "Failed to start upload"))

        self.send_command("upload", params, _cb)
