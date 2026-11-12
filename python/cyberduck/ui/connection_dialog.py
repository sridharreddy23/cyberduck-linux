"""
Exact replica of Windows Cyberduck 'Open Connection' dialog (ConnectionForm.cs).
"""
import os
import re
from pathlib import Path
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QSpinBox, QComboBox, QPushButton, QCheckBox,
    QFileDialog, QGroupBox, QWidget, QApplication, QMessageBox
)
from PyQt5.QtCore import Qt
from ..icons import get_icon, get_protocol_icon
from ..bookmarks import load_bookmarks, Bookmark, SUPPORTED_PROTOCOLS


class ConnectionDialog(QDialog):
    def __init__(self, parent=None, bridge=None, initial_bookmark=None):
        super().__init__(parent)
        self.bridge = bridge
        self.setWindowTitle("Open Connection")
        self.setWindowIcon(get_icon("connect"))
        self.resize(490, 400)
        self.setModal(True)

        self._setup_ui()
        if initial_bookmark:
            self._load_bookmark(initial_bookmark)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        grid = QGridLayout()
        grid.setSpacing(8)
        grid.setColumnStretch(1, 1)

        # 0. Bookmark Selector
        grid.addWidget(QLabel("Bookmark:"), 0, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.bookmark_combo = QComboBox()
        self._populate_bookmarks_dropdown()
        self.bookmark_combo.currentIndexChanged.connect(self._on_bookmark_combo_changed)
        grid.addWidget(self.bookmark_combo, 0, 1)

        # 1. Protocol
        grid.addWidget(QLabel("Protocol:"), 1, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.protocol_combo = QComboBox()
        self._populate_protocols()
        self.protocol_combo.currentIndexChanged.connect(self._on_protocol_changed)
        grid.addWidget(self.protocol_combo, 1, 1)

        # 2. Server & Port
        grid.addWidget(QLabel("Server:"), 2, 0, Qt.AlignRight | Qt.AlignVCenter)
        server_layout = QHBoxLayout()
        server_layout.setSpacing(6)
        self.server_edit = QLineEdit()
        self.server_edit.setPlaceholderText("e.g. ftp.example.com or localhost")
        server_layout.addWidget(self.server_edit, 1)

        server_layout.addWidget(QLabel("Port:"))
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(22)
        server_layout.addWidget(self.port_spin)
        grid.addLayout(server_layout, 2, 1)

        # 3. Username / Access Key ID
        self.user_label = QLabel("Username:")
        grid.addWidget(self.user_label, 3, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.username_edit = QLineEdit()
        self.username_edit.setText(os.environ.get("USER", "prs"))
        grid.addWidget(self.username_edit, 3, 1)

        # 4. Password / Secret Access Key
        self.pw_label = QLabel("Password:")
        grid.addWidget(self.pw_label, 4, 0, Qt.AlignRight | Qt.AlignVCenter)
        pw_layout = QHBoxLayout()
        pw_layout.setSpacing(6)
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        pw_layout.addWidget(self.password_edit, 1)

        self.show_pw_chk = QCheckBox("Show")
        self.show_pw_chk.toggled.connect(
            lambda checked: self.password_edit.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)
        )
        pw_layout.addWidget(self.show_pw_chk)
        grid.addLayout(pw_layout, 4, 1)

        # 4b. Session Token (for S3 temporary STS credentials)
        self.token_label = QLabel("Session Token:")
        grid.addWidget(self.token_label, 5, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.token_edit = QLineEdit()
        self.token_edit.setPlaceholderText("Temporary STS security token (ASIA...)")
        self.token_edit.setEchoMode(QLineEdit.Password)
        grid.addWidget(self.token_edit, 5, 1)
        self.token_label.setVisible(False)
        self.token_edit.setVisible(False)

        # 5. SSH Private Key
        self.key_label = QLabel("SSH Private Key:")
        grid.addWidget(self.key_label, 6, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.key_widget = QWidget()
        key_layout = QHBoxLayout(self.key_widget)
        key_layout.setContentsMargins(0, 0, 0, 0)
        key_layout.setSpacing(4)
        self.key_edit = QLineEdit()
        self.key_edit.setPlaceholderText("Optional private key file")
        key_layout.addWidget(self.key_edit, 1)
        self.browse_key_btn = QPushButton("...")
        self.browse_key_btn.setFixedWidth(28)
        self.browse_key_btn.clicked.connect(self._browse_key)
        key_layout.addWidget(self.browse_key_btn)
        grid.addWidget(self.key_widget, 6, 1)

        # 6. Action Buttons for AWS credentials / Anonymous
        chk_layout = QHBoxLayout()
        chk_layout.setSpacing(6)

        self.anon_chk = QCheckBox("Anonymous Login")
        self.anon_chk.toggled.connect(self._on_anon_toggled)
        chk_layout.addWidget(self.anon_chk)

        self.save_pw_chk = QCheckBox("Save Password")
        self.save_pw_chk.setChecked(True)
        chk_layout.addWidget(self.save_pw_chk)

        self.sso_login_btn = QPushButton("AWS SSO Login...")
        self.sso_login_btn.setToolTip("Trigger AWS SSO login in browser and auto-fill credentials")
        self.sso_login_btn.clicked.connect(self._trigger_sso_login)
        self.sso_login_btn.setVisible(False)
        chk_layout.addWidget(self.sso_login_btn)

        self.paste_creds_btn = QPushButton("Paste from Clipboard")
        self.paste_creds_btn.setToolTip("Paste AWS credentials block (e.g. export AWS_ACCESS_KEY_ID=...) from clipboard")
        self.paste_creds_btn.clicked.connect(self._paste_from_clipboard)
        self.paste_creds_btn.setVisible(False)
        chk_layout.addWidget(self.paste_creds_btn)

        self.env_creds_btn = QPushButton("Load from AWS Environment")
        self.env_creds_btn.setToolTip("Auto-fill Access Key, Secret Key, and Session Token from shell or ~/.config/aws/env")
        self.env_creds_btn.clicked.connect(self._load_from_env)
        self.env_creds_btn.setVisible(False)
        chk_layout.addWidget(self.env_creds_btn)

        chk_layout.addStretch()
        grid.addLayout(chk_layout, 7, 1)

        layout.addLayout(grid)

        # Helper hint banner
        self.hint_label = QLabel("")
        self.hint_label.setStyleSheet("color: #005a9e; font-size: 11px; padding: 4px 6px; background-color: #f0f6ff; border: 1px solid #cce0ff; border-radius: 3px;")
        self.hint_label.setWordWrap(True)
        self.hint_label.setVisible(False)
        layout.addWidget(self.hint_label)

        # More Options Collapsible Group
        self.more_group = QGroupBox("More Options")
        more_layout = QGridLayout(self.more_group)
        more_layout.setSpacing(8)

        more_layout.addWidget(QLabel("Path:"), 0, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Initial remote path or bucket (e.g. /my-bucket)")
        more_layout.addWidget(self.path_edit, 0, 1)

        more_layout.addWidget(QLabel("Web URL:"), 1, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.web_url_edit = QLineEdit()
        self.web_url_edit.setPlaceholderText("http://")
        more_layout.addWidget(self.web_url_edit, 1, 1)

        layout.addWidget(self.more_group)
        layout.addStretch()

        # Bottom Buttons (Windows standard Connect / Cancel / Save as Bookmark)
        btn_layout = QHBoxLayout()

        self.save_bm_btn = QPushButton("Save as Bookmark...")
        self.save_bm_btn.setIcon(get_icon("bookmark"))
        self.save_bm_btn.setToolTip("Save these connection settings as a bookmark")
        self.save_bm_btn.clicked.connect(self._save_as_bookmark)
        btn_layout.addWidget(self.save_bm_btn)

        btn_layout.addStretch()

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setDefault(True)
        self.connect_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.connect_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)
        self._on_protocol_changed(0)

    def _populate_protocols(self):
        self.protocol_combo.clear()
        for pid, name, port, default_server in SUPPORTED_PROTOCOLS:
            icon = get_protocol_icon(pid)
            self.protocol_combo.addItem(icon, name, (pid, port, default_server))

    def _on_protocol_changed(self, idx: int):
        data = self.protocol_combo.itemData(idx)
        if not data:
            return
        pid, port, default_server = data
        self.port_spin.setValue(port)

        is_s3_sso = pid == "s3-sso"
        is_s3_keys = pid == "s3"
        is_gcs = pid == "gcs" or pid == "googlestorage"
        is_azure = pid == "azure"
        is_b2 = pid == "b2" or pid == "backblaze"
        is_sftp = pid == "sftp"
        is_ftp = "ftp" in pid

        if is_s3_sso:
            self.hint_label.setVisible(True)
            self.hint_label.setText("ℹ Amazon S3 (IAM Identity Center / SSO): Authenticates with short-lived STS credentials via AWS SSO. Click 'AWS SSO Login...' to select account & role.")
            self.user_label.setText("Access Key ID:")
            self.username_edit.setPlaceholderText("Auto-filled from AWS SSO (ASIA...)")
            if self.username_edit.text() == os.environ.get("USER", "prs"):
                self.username_edit.clear()
            self.pw_label.setText("Secret Access Key:")
            self.password_edit.setPlaceholderText("Auto-filled from AWS SSO")
            if not self.server_edit.text() or self.server_edit.text() in ("localhost", "127.0.0.1"):
                self.server_edit.setText("s3.amazonaws.com")
            self.token_label.setVisible(True)
            self.token_edit.setVisible(True)
            self.key_label.setVisible(False)
            self.key_widget.setVisible(False)
            self.sso_login_btn.setVisible(True)
            self.paste_creds_btn.setVisible(True)
            self.env_creds_btn.setVisible(True)
            has_env = bool(os.environ.get("AWS_ACCESS_KEY_ID")) or (Path.home() / ".config" / "aws" / "env").exists()
            if not self.username_edit.text() and has_env:
                self._load_from_env()

        elif is_s3_keys:
            self.hint_label.setVisible(True)
            self.hint_label.setText("ℹ Amazon S3 (Permanent Credentials): Standard IAM user access key and secret key (AKIA...). No Session Token or SSO login required.")
            self.user_label.setText("Access Key ID:")
            self.username_edit.setPlaceholderText("e.g. AKIAIOSFODNN7EXAMPLE")
            if self.username_edit.text() == os.environ.get("USER", "prs"):
                self.username_edit.clear()
            self.pw_label.setText("Secret Access Key:")
            self.password_edit.setPlaceholderText("e.g. wJalrXUtnFEMI/...")
            if not self.server_edit.text() or self.server_edit.text() in ("localhost", "127.0.0.1"):
                self.server_edit.setText("s3.amazonaws.com")
            # Permanent keys DO NOT use session token or SSO button
            self.token_label.setVisible(False)
            self.token_edit.setVisible(False)
            self.token_edit.clear()
            self.key_label.setVisible(False)
            self.key_widget.setVisible(False)
            self.sso_login_btn.setVisible(False)
            self.paste_creds_btn.setVisible(True)
            self.env_creds_btn.setVisible(False)

        elif is_gcs:
            self.hint_label.setVisible(True)
            self.hint_label.setText("ℹ Google Cloud Storage (GCS): Connects to storage.googleapis.com using Google Cloud interoperability access keys or service account credentials.")
            self.user_label.setText("Access Key / Email:")
            self.username_edit.setPlaceholderText("Google Access Key or Service Account Email")
            if self.username_edit.text() == os.environ.get("USER", "prs"):
                self.username_edit.clear()
            self.pw_label.setText("Secret Key:")
            self.password_edit.setPlaceholderText("Google Secret Key")
            if not self.server_edit.text() or self.server_edit.text() in ("localhost", "127.0.0.1", "s3.amazonaws.com"):
                self.server_edit.setText("storage.googleapis.com")
            self.token_label.setVisible(False)
            self.token_edit.setVisible(False)
            self.token_edit.clear()
            self.key_label.setVisible(False)
            self.key_widget.setVisible(False)
            self.sso_login_btn.setVisible(False)
            self.paste_creds_btn.setVisible(False)
            self.env_creds_btn.setVisible(False)

        elif is_azure:
            self.hint_label.setVisible(True)
            self.hint_label.setText("ℹ Microsoft Azure: Connects to Azure Blob Storage using your storage account name and access key.")
            self.user_label.setText("Account Name:")
            self.username_edit.setPlaceholderText("Azure storage account name")
            if self.username_edit.text() == os.environ.get("USER", "prs"):
                self.username_edit.clear()
            self.pw_label.setText("Access Key:")
            self.password_edit.setPlaceholderText("Azure storage account key")
            if not self.server_edit.text() or self.server_edit.text() in ("localhost", "127.0.0.1", "s3.amazonaws.com"):
                self.server_edit.setText("blob.core.windows.net")
            self.token_label.setVisible(False)
            self.token_edit.setVisible(False)
            self.token_edit.clear()
            self.key_label.setVisible(False)
            self.key_widget.setVisible(False)
            self.sso_login_btn.setVisible(False)
            self.paste_creds_btn.setVisible(False)
            self.env_creds_btn.setVisible(False)

        elif is_b2:
            self.hint_label.setVisible(True)
            self.hint_label.setText("ℹ Backblaze B2: Connects to Backblaze B2 Cloud Storage using your Key ID and Application Key.")
            self.user_label.setText("Key ID:")
            self.username_edit.setPlaceholderText("Backblaze application Key ID")
            if self.username_edit.text() == os.environ.get("USER", "prs"):
                self.username_edit.clear()
            self.pw_label.setText("Application Key:")
            self.password_edit.setPlaceholderText("Backblaze Application Key")
            if not self.server_edit.text() or self.server_edit.text() in ("localhost", "127.0.0.1", "s3.amazonaws.com"):
                self.server_edit.setText("api.backblazeb2.com")
            self.token_label.setVisible(False)
            self.token_edit.setVisible(False)
            self.token_edit.clear()
            self.key_label.setVisible(False)
            self.key_widget.setVisible(False)
            self.sso_login_btn.setVisible(False)
            self.paste_creds_btn.setVisible(False)
            self.env_creds_btn.setVisible(False)

        elif is_sftp:
            self.hint_label.setVisible(False)
            self.user_label.setText("Username:")
            self.username_edit.setPlaceholderText("")
            if not self.username_edit.text():
                self.username_edit.setText(os.environ.get("USER", "prs"))
            self.pw_label.setText("Password:")
            self.password_edit.setPlaceholderText("")
            self.token_label.setVisible(False)
            self.token_edit.setVisible(False)
            self.token_edit.clear()
            self.key_label.setVisible(True)
            self.key_widget.setVisible(True)
            self.key_label.setEnabled(True)
            self.key_widget.setEnabled(True)
            self.sso_login_btn.setVisible(False)
            self.paste_creds_btn.setVisible(False)
            self.env_creds_btn.setVisible(False)

        else:
            # FTP / FTPS / WebDAV
            self.hint_label.setVisible(False)
            self.user_label.setText("Username:")
            self.username_edit.setPlaceholderText("")
            if not self.username_edit.text():
                self.username_edit.setText(os.environ.get("USER", "prs"))
            self.pw_label.setText("Password:")
            self.password_edit.setPlaceholderText("")
            self.token_label.setVisible(False)
            self.token_edit.setVisible(False)
            self.token_edit.clear()
            self.key_label.setVisible(False)
            self.key_widget.setVisible(False)
            self.sso_login_btn.setVisible(False)
            self.paste_creds_btn.setVisible(False)
            self.env_creds_btn.setVisible(False)

    def _on_anon_toggled(self, checked: bool):
        self.username_edit.setEnabled(not checked)
        self.password_edit.setEnabled(not checked)
        self.token_edit.setEnabled(not checked)
        self.key_edit.setEnabled(not checked)
        self.browse_key_btn.setEnabled(not checked)
        if checked:
            self.username_edit.setText("anonymous")
            self.password_edit.clear()
            self.token_edit.clear()

    def _browse_key(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Private Key", str(Path.home() / ".ssh"), "All Files (*)")
        if path:
            self.key_edit.setText(path)

    def _trigger_sso_login(self):
        from .aws_sso_dialog import AwsSsoDialog
        dlg = AwsSsoDialog(parent=self)
        if dlg.exec_() == AwsSsoDialog.Accepted:
            creds = dlg.get_credentials()
            if creds:
                if creds.get("access_key"):
                    self.username_edit.setText(creds["access_key"])
                if creds.get("secret_key"):
                    self.password_edit.setText(creds["secret_key"])
                if creds.get("session_token"):
                    self.token_edit.setText(creds["session_token"])
                if not self.server_edit.text():
                    self.server_edit.setText("s3.amazonaws.com")
                role_name = creds.get("role_name", "")
                acc_name = creds.get("account_name", "")
                self.hint_label.setText(f"✓ AWS SSO Active: Loaded STS credentials for {role_name} ({acc_name})")
                self.hint_label.setStyleSheet("color: #2e7d32; font-size: 11px; padding: 4px 6px; background-color: #e8f5e9; border: 1px solid #a5d6a7; border-radius: 3px;")

    def _paste_from_clipboard(self):
        text = QApplication.clipboard().text()
        if not text:
            return

        ak_match = re.search(r'(?:AWS_ACCESS_KEY_ID|aws_access_key_id)\s*=\s*["\']?([A-Za-z0-9/+=]+)["\']?', text)
        sk_match = re.search(r'(?:AWS_SECRET_ACCESS_KEY|aws_secret_access_key)\s*=\s*["\']?([A-Za-z0-9/+=]+)["\']?', text)
        st_match = re.search(r'(?:AWS_SESSION_TOKEN|aws_session_token|AWS_SECURITY_TOKEN)\s*=\s*["\']?([A-Za-z0-9/+=]+)["\']?', text)

        found = False
        if ak_match:
            self.username_edit.setText(ak_match.group(1))
            found = True
        if sk_match:
            self.password_edit.setText(sk_match.group(1))
            found = True
        if st_match and self.token_edit.isVisible():
            self.token_edit.setText(st_match.group(1))
            found = True

        if found:
            self.hint_label.setText("✓ Credentials pasted from clipboard.")
            self.hint_label.setStyleSheet("color: #2e7d32; font-size: 11px; padding: 4px 6px; background-color: #e8f5e9; border: 1px solid #a5d6a7; border-radius: 3px;")

    def _load_from_env(self):
        ak = os.environ.get("AWS_ACCESS_KEY_ID")
        sk = os.environ.get("AWS_SECRET_ACCESS_KEY")
        st = os.environ.get("AWS_SESSION_TOKEN") or os.environ.get("AWS_SECURITY_TOKEN")

        if not ak:
            env_file = Path.home() / ".config" / "aws" / "env"
            if env_file.exists():
                try:
                    content = env_file.read_text()
                    ak_match = re.search(r'AWS_ACCESS_KEY_ID="?([^"\n]+)"?', content)
                    sk_match = re.search(r'AWS_SECRET_ACCESS_KEY="?([^"\n]+)"?', content)
                    st_match = re.search(r'AWS_SESSION_TOKEN="?([^"\n]+)"?', content)
                    if ak_match:
                        ak = ak_match.group(1)
                    if sk_match:
                        sk = sk_match.group(1)
                    if st_match:
                        st = st_match.group(1)
                except Exception:
                    pass

        if ak:
            self.username_edit.setText(ak)
        if sk:
            self.password_edit.setText(sk)
        if st and self.token_edit.isVisible():
            self.token_edit.setText(st)

        if ak:
            self.hint_label.setText("✓ AWS credentials loaded from environment.")
            self.hint_label.setStyleSheet("color: #2e7d32; font-size: 11px; padding: 4px 6px; background-color: #e8f5e9; border: 1px solid #a5d6a7; border-radius: 3px;")

    def _populate_bookmarks_dropdown(self):
        self.bookmark_combo.blockSignals(True)
        self.bookmark_combo.clear()
        self.bookmark_combo.addItem("(None – Custom Connection)", None)
        for bm in load_bookmarks():
            icon = get_protocol_icon(bm.protocol)
            self.bookmark_combo.addItem(icon, bm.nickname, bm)
        self.bookmark_combo.blockSignals(False)

    def _on_bookmark_combo_changed(self, idx: int):
        bm = self.bookmark_combo.currentData()
        if bm:
            self._load_bookmark(bm)

    def _load_bookmark(self, bm: Bookmark):
        match_idx = 0
        for i in range(self.protocol_combo.count()):
            data = self.protocol_combo.itemData(i)
            if data and (data[0] == bm.protocol or (bm.protocol == "s3" and data[0] in ("s3", "s3-sso"))):
                match_idx = i
                break
        self.protocol_combo.setCurrentIndex(match_idx)
        self._on_protocol_changed(match_idx)

        self.server_edit.setText(bm.hostname)
        self.port_spin.setValue(bm.port)
        if bm.username:
            self.username_edit.setText(bm.username)
        if bm.password:
            self.password_edit.setText(bm.password)
        if bm.path_val:
            self.path_edit.setText(bm.path_val)
        if bm.private_key_file:
            self.key_edit.setText(bm.private_key_file)

        # Sync bookmark combo if not already selected
        if hasattr(self, "bookmark_combo"):
            for i in range(self.bookmark_combo.count()):
                b = self.bookmark_combo.itemData(i)
                if b and getattr(b, "uuid", "") == bm.uuid:
                    self.bookmark_combo.blockSignals(True)
                    self.bookmark_combo.setCurrentIndex(i)
                    self.bookmark_combo.blockSignals(False)
                    break

        # Check for AWS SSO metadata to auto-refresh fresh STS credentials
        aid = bm.data.get("SSO_Account_Id")
        role = bm.data.get("SSO_Role_Name")
        if aid and role:
            try:
                from ..aws_db import get_cached_credentials, fetch_and_cache_role_credentials
                creds = get_cached_credentials(aid, role)
                if not creds:
                    creds = fetch_and_cache_role_credentials(aid, role)
                if creds:
                    if creds.get("access_key"):
                        self.username_edit.setText(creds["access_key"])
                    if creds.get("secret_key"):
                        self.password_edit.setText(creds["secret_key"])
                    if creds.get("session_token"):
                        self.token_edit.setText(creds["session_token"])
                    self.hint_label.setText(f"✓ AWS SSO credentials loaded for {role} ({aid})")
                    self.hint_label.setStyleSheet("color: green; font-size: 11px; padding: 4px 6px; background-color: #f0fff0; border: 1px solid #bce8ba; border-radius: 3px;")
            except Exception:
                pass

        if bm.data.get("Session_Token") and not self.token_edit.text():
            self.token_edit.setText(bm.data.get("Session_Token"))
        if bm.data.get("Secret_Key") and not self.password_edit.text():
            self.password_edit.setText(bm.data.get("Secret_Key"))

    def _save_as_bookmark(self):
        info = self.get_connection_info()
        bm = Bookmark()
        bm.protocol = info["protocol"]
        bm.hostname = info["hostname"]
        bm.port = info["port"]
        bm.username = info["username"]
        if self.save_pw_chk.isChecked() and info["password"]:
            bm.password = info["password"]
        if info.get("path"):
            bm.path_val = info["path"]
        if info.get("identity"):
            bm.private_key_file = info["identity"]

        # Default nickname
        if "s3-sso" in bm.protocol:
            bm.nickname = f"S3 SSO – {bm.username}" if bm.username else "S3 SSO"
        elif "s3" in bm.protocol:
            bm.nickname = f"S3 – {bm.username}" if bm.username else "Amazon S3"
        elif "gcs" in bm.protocol:
            bm.nickname = f"GCS – {bm.hostname}"
        elif "azure" in bm.protocol:
            bm.nickname = f"Azure – {bm.username}"
        elif "b2" in bm.protocol:
            bm.nickname = f"B2 – {bm.username}"
        else:
            bm.nickname = f"{bm.hostname or 'Server'} ({bm.protocol})"

        from .bookmark_dialog import BookmarkDialog
        dlg = BookmarkDialog(bm, parent=self)
        if dlg.exec_() == BookmarkDialog.Accepted:
            self._populate_bookmarks_dropdown()
            # Select newly created bookmark
            for i in range(self.bookmark_combo.count()):
                b = self.bookmark_combo.itemData(i)
                if b and getattr(b, "uuid", "") == bm.uuid:
                    self.bookmark_combo.setCurrentIndex(i)
                    break

    def get_connection_info(self) -> dict:
        data = self.protocol_combo.currentData()
        pid = data[0] if data else "sftp"

        # Map to backend protocols
        backend_proto = pid
        if pid in ("s3-sso", "s3-keys"):
            backend_proto = "s3"
        elif pid == "gcs":
            backend_proto = "googlestorage"

        is_s3 = "s3" in pid.lower()
        is_sftp = "sftp" in pid.lower() or "ssh" in pid.lower()
        token = self.token_edit.text().strip() if (pid == "s3-sso" and self.token_edit.text().strip()) else None

        return {
            "protocol": backend_proto,
            "raw_protocol": pid,
            "hostname": self.server_edit.text().strip(),
            "port": self.port_spin.value(),
            "username": "anonymous" if self.anon_chk.isChecked() else self.username_edit.text().strip(),
            "password": "" if self.anon_chk.isChecked() else self.password_edit.text(),
            "token": token,
            "identity": self.key_edit.text().strip() if (is_sftp and self.key_edit.text().strip()) else None,
            "path": self.path_edit.text().strip(),
        }
