"""
AWS SSO Account & Role Switcher for Cyberduck backed by local SQLite DB.
Ensures zero GUI freezes or crashes by caching all accounts and roles locally
and fetching network credentials asynchronously in background workers.
"""
import os
import re
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox,
    QPushButton, QPlainTextEdit, QGroupBox, QProgressBar, QMessageBox
)
from PyQt5.QtCore import Qt, QProcess, QUrl, QObject, pyqtSignal
from PyQt5.QtGui import QDesktopServices, QFont
from ..icons import get_icon
from ..bookmarks import Bookmark
from ..aws_db import (
    get_all_accounts, get_roles_for_account, get_cached_credentials,
    fetch_and_cache_role_credentials, sync_all_accounts_and_roles,
    find_active_sso_token, find_active_sso_start_url
)


class SyncWorker(QObject):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(int)
    error = pyqtSignal(str)

    def __init__(self, token: str, region: str = "us-east-1", parent=None):
        super().__init__(parent)
        self.token = token
        self.region = region
        self._thread: Optional[threading.Thread] = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(self):
        try:
            total = sync_all_accounts_and_roles(
                self.token, self.region,
                callback=lambda cur, tot, name: self.progress.emit(cur, tot, name)
            )
            self.finished.emit(total)
        except Exception as e:
            self.error.emit(str(e))


class CredentialsWorker(QObject):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, account_id: str, role_name: str, parent=None):
        super().__init__(parent)
        self.account_id = account_id
        self.role_name = role_name
        self._thread: Optional[threading.Thread] = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(self):
        try:
            creds = fetch_and_cache_role_credentials(self.account_id, self.role_name)
            if creds:
                self.finished.emit(creds)
            else:
                self.error.emit("Failed to retrieve STS credentials from AWS.")
        except Exception as e:
            self.error.emit(str(e))


class AwsSsoDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AWS SSO Account & Role Switcher (Offline DB)")
        self.setWindowIcon(get_icon("connect"))
        self.resize(580, 500)
        self.setModal(True)

        self.login_process: Optional[QProcess] = None
        self.sync_worker: Optional[SyncWorker] = None
        self.creds_worker: Optional[CredentialsWorker] = None

        self.credentials: Optional[Dict[str, str]] = None
        self.detected_url: Optional[str] = None
        self.sso_token: Optional[str] = None
        self.sso_region = "us-east-1"
        self.accounts: List[Dict[str, str]] = []
        self.roles: List[str] = []

        self._setup_ui()
        self._check_session_and_load_db()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Header
        header = QLabel("AWS IAM Identity Center (SSO) Account Switcher")
        header.setFont(QFont("Segoe UI", 10, QFont.Bold))
        layout.addWidget(header)

        # 1. SSO Session Status Bar
        session_box = QGroupBox("SSO Authentication Status")
        sess_layout = QHBoxLayout(session_box)
        sess_layout.setContentsMargins(10, 8, 10, 8)

        self.session_status_lbl = QLabel("Checking SSO session...")
        self.session_status_lbl.setStyleSheet("font-weight: bold;")
        sess_layout.addWidget(self.session_status_lbl, 1)

        self.sync_btn = QPushButton("🔄 Refresh from AWS")
        self.sync_btn.setToolTip("Re-sync all accounts and roles from AWS Identity Center into local database")
        self.sync_btn.clicked.connect(self._start_sync)
        sess_layout.addWidget(self.sync_btn)

        self.login_btn = QPushButton("Log In via Browser")
        self.login_btn.clicked.connect(self._start_sso_login)
        sess_layout.addWidget(self.login_btn)

        layout.addWidget(session_box)

        # Action button to open URL in browser (hidden initially)
        self.open_url_btn = QPushButton("🔗 Open Authorization Page in Browser")
        self.open_url_btn.setStyleSheet(
            "background-color: #0078d4; color: white; font-weight: bold; padding: 6px;"
        )
        self.open_url_btn.setVisible(False)
        self.open_url_btn.clicked.connect(self._open_detected_url)
        layout.addWidget(self.open_url_btn)

        # 2. Account & Role Selection Group
        self.acc_group = QGroupBox("Select Account & Role (Cached in Local DB)")
        acc_layout = QGridLayout(self.acc_group)
        acc_layout.setSpacing(8)

        acc_layout.addWidget(QLabel("AWS Account:"), 0, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.account_combo = QComboBox()
        self.account_combo.currentIndexChanged.connect(self._on_account_changed)
        acc_layout.addWidget(self.account_combo, 0, 1)

        acc_layout.addWidget(QLabel("IAM Role:"), 1, 0, Qt.AlignRight | Qt.AlignVCenter)
        self.role_combo = QComboBox()
        self.role_combo.currentIndexChanged.connect(self._on_role_changed)
        acc_layout.addWidget(self.role_combo, 1, 1)

        layout.addWidget(self.acc_group)

        # 3. Log / Output View
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Monospace", 9))
        self.log_view.setPlaceholderText("SSO output and account information...")
        layout.addWidget(self.log_view, 1)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # 4. Bottom action buttons
        btn_layout = QHBoxLayout()
        self.status_lbl = QLabel("")
        btn_layout.addWidget(self.status_lbl, 1)

        self.save_bookmark_btn = QPushButton("Save as Bookmark")
        self.save_bookmark_btn.setEnabled(False)
        self.save_bookmark_btn.setToolTip("Create a Cyberduck bookmark for this Account and Role")
        self.save_bookmark_btn.clicked.connect(self._save_as_bookmark)
        btn_layout.addWidget(self.save_bookmark_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self._on_cancel)
        btn_layout.addWidget(self.cancel_btn)

        self.use_creds_btn = QPushButton("Apply to Connection")
        self.use_creds_btn.setEnabled(True)
        self.use_creds_btn.setDefault(True)
        self.use_creds_btn.clicked.connect(self._on_apply)
        btn_layout.addWidget(self.use_creds_btn)

        layout.addLayout(btn_layout)

    def _check_session_and_load_db(self):
        token, region = find_active_sso_token()
        if token:
            self.sso_token = token
            self.sso_region = region
            self.session_status_lbl.setText("● Active SSO Session Authenticated")
            self.session_status_lbl.setStyleSheet("color: green; font-weight: bold;")
            self.login_btn.setText("Re-authenticate")
            self.sync_btn.setEnabled(True)
        else:
            self.session_status_lbl.setText("○ No active SSO session")
            self.session_status_lbl.setStyleSheet("color: #d83b01; font-weight: bold;")
            self.login_btn.setText("Log In via Browser")
            self.sync_btn.setEnabled(False)

        # Instant DB load (0ms)
        self._load_accounts_from_db()

    def _load_accounts_from_db(self):
        self.accounts = get_all_accounts()
        if not self.accounts:
            self.log_view.appendPlainText("Local database empty. Click 'Refresh from AWS' or 'Log In' to sync accounts.\n")
            if self.sso_token:
                self._start_sync()
            return

        self.log_view.appendPlainText(f"✓ Loaded {len(self.accounts)} accounts instantly from local SQLite DB.\n")
        self.account_combo.blockSignals(True)
        self.account_combo.clear()
        for a in self.accounts:
            aid = a["accountId"]
            name = a["accountName"]
            self.account_combo.addItem(f"{name} ({aid})", aid)
        self.account_combo.blockSignals(False)

        self.acc_group.setEnabled(True)
        if self.accounts:
            self._on_account_changed(0)

    def _on_account_changed(self, idx: int):
        aid = self.account_combo.currentData()
        if not aid:
            return

        acc_name = self.account_combo.currentText()
        self.roles = get_roles_for_account(aid)
        self.role_combo.blockSignals(True)
        self.role_combo.clear()
        for r in self.roles:
            self.role_combo.addItem(r)
        self.role_combo.blockSignals(False)

        if self.roles:
            self._on_role_changed(0)

    def _on_role_changed(self, idx: int):
        aid = self.account_combo.currentData()
        role = self.role_combo.currentText().strip()
        if not aid or not role:
            return

        # 1. Check SQLite credentials cache
        cached = get_cached_credentials(aid, role)
        if cached:
            self.credentials = cached
            self._persist_to_env(cached["access_key"], cached["secret_key"], cached.get("session_token", ""))
            self.status_lbl.setText(f"✓ Ready: {role} @ {aid}")
            self.status_lbl.setStyleSheet("color: green; font-weight: bold;")
            self.log_view.appendPlainText(f"✓ Using cached credentials for {role} @ {aid}.\n")
        else:
            self.credentials = None
            self.status_lbl.setText(f"Selected: {role} @ {aid} (Ready to apply)")
            self.status_lbl.setStyleSheet("color: #0078d4; font-weight: bold;")

        self.use_creds_btn.setEnabled(True)
        self.save_bookmark_btn.setEnabled(True)

    def _on_apply(self):
        aid = self.account_combo.currentData()
        role = self.role_combo.currentText().strip()
        if not aid or not role:
            return

        if self.credentials:
            self.accept()
            return

        # Fetch credentials on demand
        self.use_creds_btn.setEnabled(False)
        self.status_lbl.setText(f"Loading credentials for {role}...")
        self.status_lbl.setStyleSheet("color: #0078d4; font-weight: bold;")
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)
        from PyQt5.QtWidgets import QApplication
        QApplication.processEvents()

        creds = fetch_and_cache_role_credentials(aid, role)
        self.progress_bar.setVisible(False)
        self.use_creds_btn.setEnabled(True)
        if creds:
            self.credentials = creds
            self._persist_to_env(creds["access_key"], creds["secret_key"], creds.get("session_token", ""))
            self.accept()
        else:
            self.status_lbl.setText("Failed to load credentials.")
            self.status_lbl.setStyleSheet("color: red; font-weight: bold;")
            QMessageBox.critical(
                self, "Authentication Error",
                f"Failed to fetch credentials for {role} ({aid}).\nPlease verify your SSO session."
            )

    def closeEvent(self, event):
        try:
            self._cleanup_workers()
        except Exception:
            pass
        super().closeEvent(event)

    def reject(self):
        try:
            self._cleanup_workers()
        except Exception:
            pass
        super().reject()

    def accept(self):
        try:
            self._cleanup_workers()
        except Exception:
            pass
        super().accept()

    def _cleanup_workers(self):
        try:
            if self.login_process and self.login_process.state() == QProcess.Running:
                self.login_process.terminate()
                self.login_process.waitForFinished(300)
        except Exception:
            pass

    def _start_sync(self):
        if not self.sso_token:
            QMessageBox.warning(self, "SSO Required", "Please log in to AWS SSO first to sync accounts.")
            return

        self.sync_btn.setEnabled(False)
        self.progress_bar.setRange(0, 11)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.log_view.appendPlainText("> Syncing accounts and roles from AWS Identity Center into local DB...\n")

        self.sync_worker = SyncWorker(self.sso_token, self.sso_region, self)
        self.sync_worker.progress.connect(self._on_sync_progress)
        self.sync_worker.finished.connect(self._on_sync_finished)
        self.sync_worker.error.connect(self._on_sync_error)
        self.sync_worker.start()

    def _on_sync_progress(self, cur: int, total: int, name: str):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(cur)
        self.log_view.appendPlainText(f"  [{cur}/{total}] Synced {name}")

    def _on_sync_finished(self, total: int):
        self.sync_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.log_view.appendPlainText(f"✓ Successfully synced {total} accounts to local DB!\n")
        self._load_accounts_from_db()

    def _on_sync_error(self, err: str):
        self.sync_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.log_view.appendPlainText(f"Sync error: {err}\n")

    def _persist_to_env(self, ak: str, sk: str, st: str):
        os.environ["AWS_ACCESS_KEY_ID"] = ak
        os.environ["AWS_SECRET_ACCESS_KEY"] = sk
        if st:
            os.environ["AWS_SESSION_TOKEN"] = st

        env_file = Path.home() / ".config" / "aws" / "env"
        try:
            env_file.parent.mkdir(parents=True, exist_ok=True)
            with open(env_file, "w") as f:
                f.write(f'export AWS_ACCESS_KEY_ID="{ak}"\n')
                f.write(f'export AWS_SECRET_ACCESS_KEY="{sk}"\n')
                if st:
                    f.write(f'export AWS_SESSION_TOKEN="{st}"\n')
        except Exception:
            pass

    def _save_as_bookmark(self):
        aid = self.account_combo.currentData()
        role = self.role_combo.currentText().strip()
        acc_text = self.account_combo.currentText()
        acc_name = acc_text.split(" (")[0] if " (" in acc_text else acc_text

        bm_name = f"S3 – {acc_name} ({role})"
        bm = Bookmark()
        bm.nickname = bm_name
        bm.protocol = "s3"
        bm.hostname = "s3.amazonaws.com"
        bm.port = 443
        bm.data["SSO_Account_Id"] = aid
        bm.data["SSO_Role_Name"] = role
        bm.data["SSO_Region"] = self.sso_region
        if self.credentials:
            bm.username = self.credentials.get("access_key", "")
            if self.credentials.get("session_token"):
                bm.data["Session_Token"] = self.credentials.get("session_token")
            if self.credentials.get("secret_key"):
                bm.data["Secret_Key"] = self.credentials.get("secret_key")
        bm.save()

        # Also write profile to ~/.aws/config
        self._save_aws_config_profile(f"{acc_name.lower().replace(' ', '-')}-{role}", aid, role)

        # Notify any open MainWindow or ConnectionDialog to refresh bookmarks immediately
        from PyQt5.QtWidgets import QApplication
        for w in QApplication.topLevelWidgets():
            if hasattr(w, "_refresh_bookmarks"):
                try:
                    w._refresh_bookmarks()
                except Exception:
                    pass
        if self.parent() and hasattr(self.parent(), "_populate_bookmarks_dropdown"):
            try:
                self.parent()._populate_bookmarks_dropdown()
            except Exception:
                pass

        QMessageBox.information(
            self, "Bookmark Saved",
            f"Bookmark '{bm_name}' saved to Cyberduck!\nIt is now visible in your Bookmarks list and Bookmark menu."
        )

    def _save_aws_config_profile(self, prof_name: str, account_id: str, role_name: str):
        config_file = Path.home() / ".aws" / "config"
        safe_name = re.sub(r"[^A-Za-z0-9_-]", "-", prof_name).strip("-")
        try:
            content = config_file.read_text() if config_file.exists() else ""
            sec_header = f"[profile {safe_name}]"
            if sec_header not in content:
                start_url = find_active_sso_start_url() or ""
                url_line = f"sso_start_url = {start_url}\n" if start_url else ""
                block = f"\n{sec_header}\n{url_line}sso_account_id = {account_id}\nsso_role_name = {role_name}\nregion = {self.sso_region}\n"
                with open(config_file, "a") as f:
                    f.write(block)
        except Exception:
            pass

    def _get_sso_login_args(self) -> List[str]:
        config_file = Path.home() / ".aws" / "config"
        if config_file.exists():
            try:
                content = config_file.read_text()
                m_sess = re.search(r'\[sso-session\s+([^\]]+)\]', content)
                if m_sess:
                    return ["sso", "login", "--sso-session", m_sess.group(1).strip()]
                m_prof = re.search(r'\[profile\s+([^\]]+)\]', content)
                if m_prof:
                    return ["sso", "login", "--profile", m_prof.group(1).strip()]
            except Exception:
                pass
        return ["sso", "login"]

    def _start_sso_login(self):
        self.log_view.clear()
        self.log_view.appendPlainText("> Initiating AWS SSO authorization in your default browser...\n")
        self.login_btn.setEnabled(False)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)
        self.status_lbl.setText("Waiting for browser authorization...")

        self.login_process = QProcess(self)
        self.login_process.readyReadStandardOutput.connect(self._on_stdout)
        self.login_process.readyReadStandardError.connect(self._on_stderr)
        self.login_process.finished.connect(self._on_login_finished)

        args = self._get_sso_login_args()
        self.log_view.appendPlainText(f"> Executing: aws {' '.join(args)}\n")
        self.login_process.start("aws", args)

    def _on_stdout(self):
        data = self.login_process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        self._process_output(data)

    def _on_stderr(self):
        data = self.login_process.readAllStandardError().data().decode("utf-8", errors="replace")
        self._process_output(data)

    def _process_output(self, text: str):
        self.log_view.appendPlainText(text)
        url_match = re.search(r"(https://[^\s]+amazonaws\.com[^\s]+|https://device\.sso[^\s]+)", text)
        if url_match:
            self.detected_url = url_match.group(1).rstrip(".")
            self.open_url_btn.setText(f"🔗 Open SSO Link: {self.detected_url}")
            self.open_url_btn.setVisible(True)
            QDesktopServices.openUrl(QUrl(self.detected_url))

    def _open_detected_url(self):
        if self.detected_url:
            QDesktopServices.openUrl(QUrl(self.detected_url))

    def _on_login_finished(self, exit_code: int, exit_status):
        self.progress_bar.setVisible(False)
        self.login_btn.setEnabled(True)

        if exit_code == 0:
            self.status_lbl.setText("✓ SSO Authorization successful!")
            self.status_lbl.setStyleSheet("color: green; font-weight: bold;")
            token, region = find_active_sso_token()
            if token:
                self.sso_token = token
                self.sso_region = region
                self.session_status_lbl.setText("● Active SSO Session Authenticated")
                self.session_status_lbl.setStyleSheet("color: green; font-weight: bold;")
                self._start_sync()
        else:
            self.status_lbl.setText(f"Login failed (code {exit_code})")
            self.status_lbl.setStyleSheet("color: red; font-weight: bold;")

    def _on_cancel(self):
        if self.login_process and self.login_process.state() == QProcess.Running:
            self.login_process.terminate()
            self.login_process.waitForFinished(1000)
        self.reject()
