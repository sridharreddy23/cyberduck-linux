"""
Icon provider loading Cyberduck's official PNG assets.
"""
from pathlib import Path
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import QFileIconProvider
from PyQt5.QtCore import QFileInfo

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

def _find_img_dir() -> Path:
    candidates = [
        REPO_ROOT / "img",
        Path(__file__).resolve().parent / "img",
        Path("/opt/cyberduck/share/img"),
        Path("/opt/cyberduck/img"),
    ]
    for c in candidates:
        if c.exists() and c.is_dir():
            return c
    return REPO_ROOT / "img"

IMG_DIR = _find_img_dir()

_ICON_CACHE = {}
_FILE_ICON_PROVIDER = None


def get_icon(name: str) -> QIcon:
    """Retrieve an icon from the img directory or return a fallback."""
    if name in _ICON_CACHE:
        return _ICON_CACHE[name]

    # Check root app icon
    if name == "app":
        candidates = [
            REPO_ROOT / "cyberduck-application-rect.png",
            Path("/opt/cyberduck/share/icons/cyberduck.png"),
            Path("/usr/share/icons/hicolor/512x512/apps/cyberduck.png"),
            IMG_DIR / "app.png",
        ]
        for c in candidates:
            if c.exists():
                icon = QIcon(str(c))
                _ICON_CACHE[name] = icon
                return icon

    # Check img directory
    candidates = [
        IMG_DIR / f"{name}.png",
        IMG_DIR / f"{name}@2x.png",
        IMG_DIR / name,
    ]
    for path in candidates:
        if path.exists():
            icon = QIcon(str(path))
            _ICON_CACHE[name] = icon
            return icon

    # Fallback empty icon
    icon = QIcon()
    _ICON_CACHE[name] = icon
    return icon


def get_protocol_icon(protocol_id: str) -> QIcon:
    """Get icon for a protocol (sftp, ftp, s3, dav, etc.)."""
    pid = (protocol_id or "").lower()
    if "sftp" in pid or "ssh" in pid:
        return get_icon("connect")
    elif "ftps" in pid:
        return get_icon("ftp")
    elif "ftp" in pid:
        return get_icon("ftp")
    elif "s3" in pid:
        return get_icon("s3")
    elif "gcs" in pid or "google" in pid or "drive" in pid:
        return get_icon("googledrive")
    elif "azure" in pid:
        return get_icon("azure")
    elif "b2" in pid or "backblaze" in pid:
        return get_icon("site")
    elif "dav" in pid or "http" in pid:
        return get_icon("connection")
    elif "dropbox" in pid:
        return get_icon("dropbox")
    elif "onedrive" in pid:
        return get_icon("onedrive")
    elif "box" in pid:
        return get_icon("box")
    return get_icon("site")


def get_file_icon(name: str, is_dir: bool = False, is_symlink: bool = False) -> QIcon:
    """Return standard Windows file/folder icon."""
    global _FILE_ICON_PROVIDER
    if is_dir:
        folder_icon = get_icon("book")
        if not folder_icon.isNull():
            return folder_icon
        if _FILE_ICON_PROVIDER is None:
            _FILE_ICON_PROVIDER = QFileIconProvider()
        return _FILE_ICON_PROVIDER.icon(QFileIconProvider.Folder)

    ext = Path(name).suffix.lower()
    if ext in (".zip", ".tar", ".gz", ".7z", ".rar", ".bz2"):
        return get_icon("outline") or get_icon("clean")
    elif ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp"):
        return get_icon("file") or get_icon("site")
    elif ext in (".sh", ".py", ".java", ".c", ".cpp", ".cs", ".js", ".html", ".css", ".xml", ".json"):
        return get_icon("pencil") or get_icon("site")
    elif ext in (".exe", ".bin", ".deb", ".rpm"):
        return get_icon("executable") or get_icon("site")

    if _FILE_ICON_PROVIDER is None:
        _FILE_ICON_PROVIDER = QFileIconProvider()
    return _FILE_ICON_PROVIDER.icon(QFileIconProvider.File)
