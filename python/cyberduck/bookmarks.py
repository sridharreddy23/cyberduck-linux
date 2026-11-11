"""
Cyberduck Bookmark Manager (.duck Apple XML Property List format).
"""
import os
import plistlib
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional

BOOKMARKS_DIR = Path.home() / ".duck" / "Bookmarks"


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
    def path_val(self) -> str:
        return self.data.get("Path", "")

    @path_val.setter
    def path_val(self, val: str):
        self.data["Path"] = val

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
    """Load all *.duck files from ~/.duck/Bookmarks/."""
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

    return bookmarks
