"""
Exact replica of Windows Cyberduck 'Bookmark' editor (BookmarkForm.cs).
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QSpinBox, QComboBox, QPushButton, QFileDialog, QWidget
)
from PyQt5.QtCore import Qt
from ..icons import get_icon, get_protocol_icon
from ..bookmarks import Bookmark


class BookmarkDialog(QDialog):
    def __init__(self, bookmark: Bookmark, parent=None):
        super().__init__(parent)
        self.bookmark = bookmark
        self.setWindowTitle(f"Bookmark – {bookmark.nickname}")
        self.setWindowIcon(get_icon("bookmark"))
        self.resize(440, 320)

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
        grid.addWidget(QLabel("Nickname:"), 0, 0, Qt.AlignRight)
        self.nickname_edit = QLineEdit()
        grid.addWidget(self.nickname_edit, 0, 1)

        # Protocol
        grid.addWidget(QLabel("Protocol:"), 1, 0, Qt.AlignRight)
        self.protocol_combo = QComboBox()
        self._populate_protocols()
        self.protocol_combo.currentIndexChanged.connect(self._on_protocol_changed)
        grid.addWidget(self.protocol_combo, 1, 1)

        # Server & Port
        grid.addWidget(QLabel("Server:"), 2, 0, Qt.AlignRight)
        srv_layout = QHBoxLayout()
        self.server_edit = QLineEdit()
        srv_layout.addWidget(self.server_edit, 1)
        srv_layout.addWidget(QLabel("Port:"))
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        srv_layout.addWidget(self.port_spin)
        grid.addLayout(srv_layout, 2, 1)

        # Username
        self.user_label = QLabel("Username:")
        grid.addWidget(self.user_label, 3, 0, Qt.AlignRight)
        self.username_edit = QLineEdit()
        grid.addWidget(self.username_edit, 3, 1)

        # Path
        grid.addWidget(QLabel("Path:"), 4, 0, Qt.AlignRight)
        self.path_edit = QLineEdit()
        grid.addWidget(self.path_edit, 4, 1)

        # SSH Key
        self.key_label = QLabel("SSH Key:")
        grid.addWidget(self.key_label, 5, 0, Qt.AlignRight)
        self.key_widget = QWidget()
        key_layout = QHBoxLayout(self.key_widget)
        key_layout.setContentsMargins(0, 0, 0, 0)
        self.key_edit = QLineEdit()
        key_layout.addWidget(self.key_edit, 1)
        browse_btn = QPushButton("...")
        browse_btn.setFixedWidth(28)
        browse_btn.clicked.connect(self._browse_key)
        key_layout.addWidget(browse_btn)
        grid.addWidget(self.key_widget, 5, 1)

        layout.addLayout(grid)
        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        self.sso_btn = QPushButton("AWS SSO Switcher...")
        self.sso_btn.setToolTip("Pick an AWS Account & Role from SSO")
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
        default_protocols = [
            ("sftp", "SFTP (SSH File Transfer Protocol)", 22),
            ("ftp", "FTP (File Transfer Protocol)", 21),
            ("s3", "Amazon S3", 443),
            ("dav", "WebDAV (HTTP)", 80),
            ("davs", "WebDAV (HTTPS)", 443),
        ]
        for pid, name, port in default_protocols:
            icon = get_protocol_icon(pid)
            self.protocol_combo.addItem(icon, name, (pid, port))

    def _on_protocol_changed(self, idx: int):
        data = self.protocol_combo.itemData(idx)
        if data:
            pid, port = data
            self.port_spin.setValue(port)
            is_s3 = "s3" in pid.lower()
            self.sso_btn.setVisible(is_s3)
            if is_s3:
                self.user_label.setText("Access Key ID:")
                self.username_edit.setPlaceholderText("e.g. AKIAIOSFODNN7EXAMPLE")
                self.key_label.setVisible(False)
                self.key_widget.setVisible(False)
                if not self.server_edit.text() or self.server_edit.text() in ("localhost", "127.0.0.1"):
                    self.server_edit.setText("s3.amazonaws.com")
            else:
                self.user_label.setText("Username:")
                self.username_edit.setPlaceholderText("")
                self.key_label.setVisible(True)
                self.key_widget.setVisible(True)

    def _trigger_sso(self):
        from .aws_sso_dialog import AwsSsoDialog
        dlg = AwsSsoDialog(self)
        if dlg.exec_() == AwsSsoDialog.Accepted and dlg.credentials:
            creds = dlg.credentials
            if creds.get("access_key"):
                self.username_edit.setText(creds["access_key"])
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
        for i in range(self.protocol_combo.count()):
            data = self.protocol_combo.itemData(i)
            if data and data[0] == self.bookmark.protocol:
                self.protocol_combo.setCurrentIndex(i)
                self._on_protocol_changed(i)
                break

        self.nickname_edit.setText(self.bookmark.nickname)
        self.server_edit.setText(self.bookmark.hostname)
        self.port_spin.setValue(self.bookmark.port)
        if self.bookmark.username:
            self.username_edit.setText(self.bookmark.username)
        if self.bookmark.path_val:
            self.path_edit.setText(self.bookmark.path_val)
        if self.bookmark.private_key_file:
            self.key_edit.setText(self.bookmark.private_key_file)

        if not self.server_edit.text() and self.bookmark.protocol == "s3":
            self.server_edit.setText("s3.amazonaws.com")

    def _save_and_close(self):
        self.bookmark.nickname = self.nickname_edit.text().strip()
        data = self.protocol_combo.currentData()
        if data:
            self.bookmark.protocol = data[0]
        self.bookmark.hostname = self.server_edit.text().strip()
        self.bookmark.port = self.port_spin.value()
        self.bookmark.username = self.username_edit.text().strip()
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
