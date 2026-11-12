"""
Cyberduck Bookmark Manager (.duck Apple XML Property List format).
"""
import copy
import os
import plistlib
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional

BOOKMARKS_DIR = Path.home() / ".duck" / "Bookmarks"

# Standard protocols supported across Cyberduck Linux
# Format: (protocol_id, display_name, default_port, default_server)
SUPPORTED_PROTOCOLS = [
    ("s3-sso", "Amazon S3 (IAM Identity Center / SSO)", 443, "s3.amazonaws.com"),
    ("s3", "Amazon S3 (Permanent Credentials / Access Key)", 443, "s3.amazonaws.com"),
    ("gcs", "Google Cloud Storage", 443, "storage.googleapis.com"),
    ("azure", "Microsoft Azure Blob Storage", 443, "blob.core.windows.net"),
    ("b2", "Backblaze B2 Cloud Storage", 443, "api.backblazeb2.com"),
    ("sftp", "SFTP (SSH File Transfer Protocol)", 22, ""),
    ("ftp", "FTP (File Transfer Protocol)", 21, ""),
    ("ftps", "FTP-SSL (Explicit AUTH TLS)", 21, ""),
    ("dav", "WebDAV (HTTP)", 80, ""),
    ("davs", "WebDAV (HTTPS)", 443, ""),
]

PROTOCOL_DISPLAY_NAMES = {pid: name for pid, name, _, _ in SUPPORTED_PROTOCOLS}
PROTOCOL_DISPLAY_NAMES.update({
    "googlestorage": "Google Cloud Storage",
    "backblaze": "Backblaze B2 Cloud Storage",
})


class Bookmark:
    def __init__(self, data: Optional[Dict[str, Any]] = None, path: Optional[Path] = None):
        self.data = data or {}
        self.path = path
        if "UUID" not in self.data:
            self.data["UUID"] = str(uuid.uuid4())

    @property
    def uuid(self) -> str:
        return self.data.get("UUID", "")

    @property
    def nickname(self) -> str:
        return self.data.get("Nickname") or self.hostname or "Untitled"

    @nickname.setter
    def nickname(self, val: str):
        self.data["Nickname"] = val

    @property
    def protocol(self) -> str:
        return self.data.get("Protocol", "sftp")

    @protocol.setter
    def protocol(self, val: str):
        self.data["Protocol"] = val

    @property
    def hostname(self) -> str:
        return self.data.get("Hostname", "")

    @hostname.setter
    def hostname(self, val: str):
        self.data["Hostname"] = val

    @property
    def port(self) -> int:
        val = self.data.get("Port", 22)
        try:
            return int(val)
        except (ValueError, TypeError):
            return 22

    @port.setter
    def port(self, val: int):
        self.data["Port"] = str(val)

    @property
    def username(self) -> str:
        return self.data.get("Username", "")

    @username.setter
    def username(self, val: str):
        self.data["Username"] = val

    @property
    def password(self) -> Optional[str]:
        return self.data.get("Password")

    @password.setter
    def password(self, val: Optional[str]):
        if val:
            self.data["Password"] = val
        else:
            self.data.pop("Password", None)

    @property
    def path_val(self) -> str:
        return self.data.get("Path", "")

    @path_val.setter
    def path_val(self, val: str):
        self.data["Path"] = val

    @property
    def region(self) -> Optional[str]:
        return self.data.get("Region")

    @region.setter
    def region(self, val: Optional[str]):
        if val:
            self.data["Region"] = val
        else:
            self.data.pop("Region", None)

    @property
    def private_key_file(self) -> Optional[str]:
        return self.data.get("Private Key File")

    @private_key_file.setter
    def private_key_file(self, val: Optional[str]):
        if val:
            self.data["Private Key File"] = val
            self.data["Private Key File Dictionary"] = {"Path": val}
        else:
            self.data.pop("Private Key File", None)
            self.data.pop("Private Key File Dictionary", None)

    @property
    def subtitle(self) -> str:
        """Returns clean informative summary string for UI listing."""
        parts = []
        proto_name = PROTOCOL_DISPLAY_NAMES.get(self.protocol, self.protocol.upper())
        # Shorten protocol label for subtitle
        short_proto = proto_name.split(" (")[0]
        parts.append(short_proto)

        if self.hostname and self.hostname not in ("s3.amazonaws.com", "storage.googleapis.com", "blob.core.windows.net", "api.backblazeb2.com"):
            parts.append(self.hostname)

        if self.username:
            u = self.username
            if len(u) > 28:
                u = u[:25] + "..."
            parts.append(u)

        if self.path_val and self.path_val != "/":
            p = self.path_val
            if len(p) > 24:
                p = "..." + p[-21:]
            parts.append(p)

        return " • ".join(parts)

    def duplicate(self) -> 'Bookmark':
        """Clone this bookmark with a new UUID and distinct nickname."""
        new_data = copy.deepcopy(self.data)
        new_data["UUID"] = str(uuid.uuid4())
        new_data["Nickname"] = f"{self.nickname} – Copy"
        new_bm = Bookmark(new_data)
        new_bm.save()
        return new_bm

    def save(self):
        BOOKMARKS_DIR.mkdir(parents=True, exist_ok=True)
        if not self.path:
            self.path = BOOKMARKS_DIR / f"{self.uuid}.duck"
        with open(self.path, "wb") as f:
            plistlib.dump(self.data, f, fmt=plistlib.FMT_XML)

    def delete(self):
        if self.path and self.path.exists():
            self.path.unlink()


def load_bookmarks() -> List[Bookmark]:
    """Load all *.duck files from ~/.duck/Bookmarks/, sorted alphabetically."""
    bookmarks = []
    if not BOOKMARKS_DIR.exists():
        return bookmarks

    for p in sorted(BOOKMARKS_DIR.glob("*.duck")):
        try:
            with open(p, "rb") as f:
                data = plistlib.load(f)
                bookmarks.append(Bookmark(data, p))
        except Exception:
            continue

    bookmarks.sort(key=lambda b: b.nickname.lower())
    return bookmarks
