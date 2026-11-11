"""
Exact replica of Windows Cyberduck Login Prompt (LoginForm.cs).
"""
import os
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QPushButton, QCheckBox
)
from PyQt5.QtCore import Qt
from ..icons import get_icon


class LoginPromptDialog(QDialog):
    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self.prompt_id = data.get("promptId", "")
        self.hostname = data.get("hostname", "")
        self.initial_username = data.get("username", "")
        self.title_text = data.get("title", f"Login {self.hostname}")
        self.reason_text = data.get("reason", f"Login {self.hostname} with username and password")
        self.is_s3 = "s3" in self.hostname.lower() or "amazon" in self.hostname.lower()

        self.setWindowTitle(self.title_text)
        self.setWindowIcon(get_icon("connect"))
        self.resize(420, 240 if self.is_s3 else 200)
        self.setModal(True)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Prompt description header
        self.header_label = QLabel(self.reason_text)
        self.header_label.setWordWrap(True)
        self.header_label.setStyleSheet("font-weight: bold; margin-bottom: 5px;")
        layout.addWidget(self.header_label)

        grid = QGridLayout()
        grid.setSpacing(8)

        # Username / Access Key ID
        user_lbl = "Access Key ID:" if self.is_s3 else "Username:"
        grid.addWidget(QLabel(user_lbl), 0, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.username_edit = QLineEdit(self.initial_username)
        grid.addWidget(self.username_edit, 0, 1)

        # Password / Secret Access Key
        pw_lbl = "Secret Access Key:" if self.is_s3 else "Password:"
        grid.addWidget(QLabel(pw_lbl), 1, 0, Qt.AlignRight | Qt.AlignVCenter)
        pw_layout = QHBoxLayout()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        pw_layout.addWidget(self.password_edit, 1)

        self.show_pw_chk = QCheckBox("Show")
        self.show_pw_chk.toggled.connect(
            lambda chk: self.password_edit.setEchoMode(QLineEdit.Normal if chk else QLineEdit.Password)
        )
        pw_layout.addWidget(self.show_pw_chk)
        grid.addLayout(pw_layout, 1, 1)

        # Session Token (for S3 STS)
        if self.is_s3:
            grid.addWidget(QLabel("Session Token:"), 2, 0, Qt.AlignRight | Qt.AlignVCenter)
            self.token_edit = QLineEdit()
            self.token_edit.setEchoMode(QLineEdit.Password)
            self.token_edit.setPlaceholderText("Optional STS session token (required for ASIA... keys)")
            # Auto-fill from env if available
            st = os.environ.get("AWS_SESSION_TOKEN", "")
            if st:
                self.token_edit.setText(st)
            grid.addWidget(self.token_edit, 2, 1)

        # Save Password checkbox
        row = 3 if self.is_s3 else 2
        self.save_chk = QCheckBox("Save password")
        self.save_chk.setChecked(True)
        grid.addWidget(self.save_chk, row, 1)

        layout.addLayout(grid)
        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        if self.is_s3:
            self.sso_btn = QPushButton("AWS SSO Switcher...")
            self.sso_btn.setToolTip("Switch account/role or refresh expired AWS SSO credentials")
            self.sso_btn.clicked.connect(self._trigger_sso)
            btn_layout.addWidget(self.sso_btn)

        btn_layout.addStretch()

        self.login_btn = QPushButton("Login")
        self.login_btn.setDefault(True)
        self.login_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.login_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)
        self.password_edit.setFocus()

    def _trigger_sso(self):
        from .aws_sso_dialog import AwsSsoDialog
        dlg = AwsSsoDialog(self)
        if dlg.exec_() == AwsSsoDialog.Accepted and dlg.credentials:
            creds = dlg.credentials
            if creds.get("access_key"):
                self.username_edit.setText(creds["access_key"])
            if creds.get("secret_key"):
                self.password_edit.setText(creds["secret_key"])
            if creds.get("session_token") and hasattr(self, "token_edit"):
                self.token_edit.setText(creds["session_token"])

    @property
    def username(self) -> str:
        return self.username_edit.text().strip()

    @property
    def password(self) -> str:
        return self.password_edit.text()

    @property
    def token(self):
        if self.is_s3 and hasattr(self, "token_edit"):
            val = self.token_edit.text().strip()
            return val if val else None
        return None

    @property
    def save_password(self) -> bool:
        return self.save_chk.isChecked()
