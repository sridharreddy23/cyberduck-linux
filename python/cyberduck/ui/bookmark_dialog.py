"""
Exact replica of Windows Cyberduck 'Bookmark' editor (BookmarkForm.cs).
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QSpinBox, QComboBox, QPushButton, QFileDialog, QWidget,
    QCheckBox
)
from PyQt5.QtCore import Qt
from ..icons import get_icon, get_protocol_icon
from ..bookmarks import Bookmark, SUPPORTED_PROTOCOLS


class BookmarkDialog(QDialog):
    def __init__(self, bookmark: Bookmark, parent=None):
        super().__init__(parent)
        self.bookmark = bookmark
        self.setWindowTitle(f"Bookmark – {bookmark.nickname}")
        self.setWindowIcon(get_icon("bookmark"))
        self.resize(480, 360)

        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        grid = QGridLayout()
        grid.setSpacing(8)
        grid.setColumnStretch(1, 1)

        # Nickname
        grid.addWidget(QLabel("Nickname:"), 0, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.nickname_edit = QLineEdit()
        self.nickname_edit.setPlaceholderText("e.g. Production Data Lake or S3 Mash_staging")
        grid.addWidget(self.nickname_edit, 0, 1)

        # Protocol
        grid.addWidget(QLabel("Protocol:"), 1, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.protocol_combo = QComboBox()
        self._populate_protocols()
        self.protocol_combo.currentIndexChanged.connect(self._on_protocol_changed)
        grid.addWidget(self.protocol_combo, 1, 1)

        # Server & Port
        grid.addWidget(QLabel("Server:"), 2, 0, Qt.AlignRight | Qt.AlignVCenter)
        srv_layout = QHBoxLayout()
        srv_layout.setSpacing(6)
        self.server_edit = QLineEdit()
        srv_layout.addWidget(self.server_edit, 1)
        srv_layout.addWidget(QLabel("Port:"))
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        srv_layout.addWidget(self.port_spin)
        grid.addLayout(srv_layout, 2, 1)

        # Username / Access Key ID
        self.user_label = QLabel("Username:")
        grid.addWidget(self.user_label, 3, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.username_edit = QLineEdit()
        grid.addWidget(self.username_edit, 3, 1)

        # Password / Secret Key (Optional saved credential)
        self.pw_label = QLabel("Password:")
        grid.addWidget(self.pw_label, 4, 0, Qt.AlignRight | Qt.AlignVCenter)
        pw_layout = QHBoxLayout()
        pw_layout.setSpacing(6)
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText("Optional saved password or secret key")
        pw_layout.addWidget(self.password_edit, 1)
        self.show_pw_chk = QCheckBox("Show")
        self.show_pw_chk.toggled.connect(
            lambda checked: self.password_edit.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)
        )
        pw_layout.addWidget(self.show_pw_chk)
        grid.addLayout(pw_layout, 4, 1)

        # Path
        grid.addWidget(QLabel("Path:"), 5, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Default bucket or directory (e.g. /my-bucket/folder)")
        grid.addWidget(self.path_edit, 5, 1)

        # SSH Key
        self.key_label = QLabel("SSH Key:")
        grid.addWidget(self.key_label, 6, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.key_widget = QWidget()
        key_layout = QHBoxLayout(self.key_widget)
        key_layout.setContentsMargins(0, 0, 0, 0)
        key_layout.setSpacing(4)
        self.key_edit = QLineEdit()
        key_layout.addWidget(self.key_edit, 1)
        browse_btn = QPushButton("...")
        browse_btn.setFixedWidth(28)
        browse_btn.clicked.connect(self._browse_key)
        key_layout.addWidget(browse_btn)
        grid.addWidget(self.key_widget, 6, 1)

        layout.addLayout(grid)

        # Helper hint banner
        self.hint_label = QLabel("")
        self.hint_label.setStyleSheet("color: #005a9e; font-size: 11px; padding: 4px 6px; background-color: #f0f6ff; border: 1px solid #cce0ff; border-radius: 3px;")
        self.hint_label.setWordWrap(True)
        layout.addWidget(self.hint_label)

        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        self.sso_btn = QPushButton("AWS SSO Switcher...")
        self.sso_btn.setToolTip("Pick an AWS Account & Role from SSO cache")
        self.sso_btn.setVisible(False)
        self.sso_btn.clicked.connect(self._trigger_sso)
        btn_layout.addWidget(self.sso_btn)

        btn_layout.addStretch()
        self.save_btn = QPushButton("Save")
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self._save_and_close)
        btn_layout.addWidget(self.save_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

    def _populate_protocols(self):
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

        self.sso_btn.setVisible(is_s3_sso)

        if is_s3_sso:
            self.user_label.setText("Access Key ID:")
            self.pw_label.setText("Secret Key:")
            self.username_edit.setPlaceholderText("Auto-filled from AWS SSO (ASIA...)")
            self.key_label.setVisible(False)
            self.key_widget.setVisible(False)
            if not self.server_edit.text() or self.server_edit.text() in ("localhost", "127.0.0.1"):
                self.server_edit.setText("s3.amazonaws.com")
            self.hint_label.setVisible(True)
            self.hint_label.setText("ℹ Amazon S3 (IAM Identity Center / SSO): Authenticates with short-lived STS credentials via AWS SSO. Click 'AWS SSO Switcher...' to choose account & role.")
        elif is_s3_keys:
            self.user_label.setText("Access Key ID:")
            self.pw_label.setText("Secret Key:")
            self.username_edit.setPlaceholderText("e.g. AKIAIOSFODNN7EXAMPLE")
            self.key_label.setVisible(False)
            self.key_widget.setVisible(False)
            if not self.server_edit.text() or self.server_edit.text() in ("localhost", "127.0.0.1"):
                self.server_edit.setText("s3.amazonaws.com")
            self.hint_label.setVisible(True)
            self.hint_label.setText("ℹ Amazon S3 (Permanent Credentials): Standard IAM user access key and secret key (AKIA...). No Session Token or SSO login required.")
        elif is_gcs:
            self.user_label.setText("Access Key / Email:")
            self.pw_label.setText("Secret Key:")
            self.username_edit.setPlaceholderText("Google Access Key or Service Account Email")
            self.key_label.setVisible(False)
            self.key_widget.setVisible(False)
            if not self.server_edit.text() or self.server_edit.text() in ("localhost", "127.0.0.1"):
                self.server_edit.setText("storage.googleapis.com")
            self.hint_label.setVisible(True)
            self.hint_label.setText("ℹ Google Cloud Storage (GCS): Connects to storage.googleapis.com using Google interoperability keys or service account credentials.")
        elif is_azure:
            self.user_label.setText("Account Name:")
            self.pw_label.setText("Access Key:")
            self.username_edit.setPlaceholderText("Azure storage account name")
            self.key_label.setVisible(False)
            self.key_widget.setVisible(False)
            if not self.server_edit.text() or self.server_edit.text() in ("localhost", "127.0.0.1"):
                self.server_edit.setText("blob.core.windows.net")
            self.hint_label.setVisible(True)
            self.hint_label.setText("ℹ Microsoft Azure: Connects to Azure Blob Storage using your storage account name and access key.")
        elif is_b2:
            self.user_label.setText("Key ID:")
            self.pw_label.setText("Application Key:")
            self.username_edit.setPlaceholderText("Backblaze application Key ID")
            self.key_label.setVisible(False)
            self.key_widget.setVisible(False)
            if not self.server_edit.text() or self.server_edit.text() in ("localhost", "127.0.0.1"):
                self.server_edit.setText("api.backblazeb2.com")
            self.hint_label.setVisible(True)
            self.hint_label.setText("ℹ Backblaze B2: Connects to Backblaze B2 Cloud Storage using your Key ID and Application Key.")
        elif is_sftp:
            self.user_label.setText("Username:")
            self.pw_label.setText("Password:")
            self.username_edit.setPlaceholderText("")
            self.key_label.setVisible(True)
            self.key_widget.setVisible(True)
            self.hint_label.setVisible(False)
        else:
            self.user_label.setText("Username:")
            self.pw_label.setText("Password:")
            self.username_edit.setPlaceholderText("")
            self.key_label.setVisible(False)
            self.key_widget.setVisible(False)
            self.hint_label.setVisible(False)

    def _trigger_sso(self):
        from .aws_sso_dialog import AwsSsoDialog
        dlg = AwsSsoDialog(self)
        if dlg.exec_() == AwsSsoDialog.Accepted and dlg.credentials:
            creds = dlg.credentials
            if creds.get("access_key"):
                self.username_edit.setText(creds["access_key"])
            if creds.get("secret_key"):
                self.password_edit.setText(creds["secret_key"])
            acc_text = dlg.account_combo.currentText()
            role_text = dlg.role_combo.currentText()
            if not self.nickname_edit.text() or self.nickname_edit.text() == "New Bookmark":
                acc_name = acc_text.split(" (")[0] if " (" in acc_text else acc_text
                self.nickname_edit.setText(f"S3 – {acc_name} ({role_text})")

    def _browse_key(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select SSH Key", "", "All Files (*)")
        if path:
            self.key_edit.setText(path)

    def _load_data(self):
        match_idx = 0
        for i in range(self.protocol_combo.count()):
            data = self.protocol_combo.itemData(i)
            if data and data[0] == self.bookmark.protocol:
                match_idx = i
                break
        self.protocol_combo.setCurrentIndex(match_idx)
        self._on_protocol_changed(match_idx)

        self.nickname_edit.setText(self.bookmark.nickname)
        self.server_edit.setText(self.bookmark.hostname)
        self.port_spin.setValue(self.bookmark.port)
        if self.bookmark.username:
            self.username_edit.setText(self.bookmark.username)
        if self.bookmark.password:
            self.password_edit.setText(self.bookmark.password)
        if self.bookmark.path_val:
            self.path_edit.setText(self.bookmark.path_val)
        if self.bookmark.private_key_file:
            self.key_edit.setText(self.bookmark.private_key_file)

        if not self.server_edit.text() and "s3" in self.bookmark.protocol:
            self.server_edit.setText("s3.amazonaws.com")

    def _save_and_close(self):
        self.bookmark.nickname = self.nickname_edit.text().strip()
        data = self.protocol_combo.currentData()
        if data:
            self.bookmark.protocol = data[0]
        self.bookmark.hostname = self.server_edit.text().strip()
        self.bookmark.port = self.port_spin.value()
        self.bookmark.username = self.username_edit.text().strip()
        pw = self.password_edit.text().strip()
        self.bookmark.password = pw if pw else None
        self.bookmark.path_val = self.path_edit.text().strip()
        key = self.key_edit.text().strip()
        self.bookmark.private_key_file = key if key else None
        self.bookmark.save()

        # Notify open windows to refresh
        from PyQt5.QtWidgets import QApplication
        for w in QApplication.topLevelWidgets():
            if hasattr(w, "_refresh_bookmarks"):
                try:
                    w._refresh_bookmarks()
                except Exception:
                    pass
        self.accept()
