"""
Dialog for generating and copying presigned S3/object URLs.
"""
import datetime
from typing import Optional
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPlainTextEdit, QComboBox, QPushButton, QGroupBox, QApplication
)
from PyQt5.QtCore import Qt, QUrl, QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QFont, QDesktopServices
from ..icons import get_icon, get_file_icon
from ..backend.bridge import CyberduckBridge


class PresignedUrlDialog(QDialog):
    url_received = pyqtSignal(dict)

    EXPIRY_OPTIONS = [
        ("15 Minutes", 900),
        ("1 Hour (Default)", 3600),
        ("6 Hours", 21600),
        ("12 Hours", 43200),
        ("24 Hours (1 Day)", 86400),
        ("3 Days", 259200),
        ("7 Days (Maximum)", 604800),
    ]

    def __init__(self, file_data: dict, bridge: CyberduckBridge, parent=None):
        super().__init__(parent)
        self.file_data = file_data
        self.bridge = bridge
        self.current_url = ""
        self.path = file_data.get("absolute", "")
        self.filename = file_data.get("name", "Object")

        self.setWindowTitle(f"Presigned URL – {self.filename}")
        icon = get_icon("browser")
        if icon.isNull():
            icon = get_icon("site")
        self.setWindowIcon(icon)
        self.resize(560, 380)

        self._setup_ui()
        self.url_received.connect(self._on_url_received)

        # Generate default URL on open
        QTimer.singleShot(50, self.generate_url)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        # 1. Target Object Info Header
        header_group = QGroupBox("Target Object")
        h_layout = QGridLayout(header_group)
        h_layout.setSpacing(6)

        icon = get_file_icon(self.filename, False)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(icon.pixmap(32, 32))
        h_layout.addWidget(icon_lbl, 0, 0, 2, 1, Qt.AlignCenter)

        name_lbl = QLabel(f"<b>{self.filename}</b>")
        name_lbl.setFont(QFont("Segoe UI", 10))
        h_layout.addWidget(name_lbl, 0, 1)

        path_lbl = QLabel(self.path)
        path_lbl.setStyleSheet("color: #666;")
        h_layout.addWidget(path_lbl, 1, 1)
        layout.addWidget(header_group)

        # 2. Expiration Settings Group
        settings_group = QGroupBox("URL Options")
        s_layout = QGridLayout(settings_group)
        s_layout.setSpacing(8)

        s_layout.addWidget(QLabel("Valid For:"), 0, 0, Qt.AlignRight)
        self.expiry_combo = QComboBox()
        for label, seconds in self.EXPIRY_OPTIONS:
            self.expiry_combo.addItem(label, seconds)
        # Select 1 Hour as default
        self.expiry_combo.setCurrentIndex(1)
        self.expiry_combo.currentIndexChanged.connect(self._on_expiry_changed)
        s_layout.addWidget(self.expiry_combo, 0, 1)

        s_layout.addWidget(QLabel("HTTP Method:"), 1, 0, Qt.AlignRight)
        self.method_combo = QComboBox()
        self.method_combo.addItem("GET (Download / View)", "GET")
        self.method_combo.addItem("PUT (Upload / Write)", "PUT")
        self.method_combo.currentIndexChanged.connect(self._on_expiry_changed)
        s_layout.addWidget(self.method_combo, 1, 1)

        self.expires_at_lbl = QLabel("")
        self.expires_at_lbl.setStyleSheet("color: #444; font-style: italic;")
        s_layout.addWidget(self.expires_at_lbl, 2, 1)

        self.btn_refresh = QPushButton("Refresh URL")
        self.btn_refresh.setFixedWidth(110)
        self.btn_refresh.clicked.connect(self.generate_url)
        s_layout.addWidget(self.btn_refresh, 0, 2, 2, 1, Qt.AlignVCenter)

        layout.addWidget(settings_group)

        # 3. Presigned URL Display
        url_group = QGroupBox("Generated Presigned URL")
        u_layout = QVBoxLayout(url_group)
        u_layout.setSpacing(6)

        self.url_text = QPlainTextEdit()
        self.url_text.setReadOnly(True)
        self.url_text.setFont(QFont("Monospace", 9))
        self.url_text.setPlaceholderText("Generating presigned URL...")
        self.url_text.setMaximumHeight(85)
        u_layout.addWidget(self.url_text)

        self.status_lbl = QLabel("")
        u_layout.addWidget(self.status_lbl)

        layout.addWidget(url_group)

        # 4. Action Buttons (Copy, Open Browser, Close)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.btn_copy = QPushButton("Copy URL")
        self.btn_copy.setDefault(True)
        self.btn_copy.setEnabled(False)
        self.btn_copy.clicked.connect(self._on_copy_url)
        btn_layout.addWidget(self.btn_copy)

        self.btn_open = QPushButton("Open in Browser")
        self.btn_open.setEnabled(False)
        self.btn_open.clicked.connect(self._on_open_browser)
        btn_layout.addWidget(self.btn_open)

        btn_layout.addStretch()

        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)

        self._update_expiry_display()

    def _get_selected_seconds(self) -> int:
        return self.expiry_combo.currentData() or 3600

    def _get_selected_method(self) -> str:
        return self.method_combo.currentData() or "GET"

    def _update_expiry_display(self):
        seconds = self._get_selected_seconds()
        expiry_dt = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
        self.expires_at_lbl.setText(f"Expires: {expiry_dt.strftime('%A, %b %d, %Y at %I:%M:%S %p')}")

    def _on_expiry_changed(self):
        self._update_expiry_display()
        self.generate_url()

    def generate_url(self):
        seconds = self._get_selected_seconds()
        method = self._get_selected_method()

        self.status_lbl.setStyleSheet("color: #333;")
        self.status_lbl.setText("Generating presigned URL...")
        self.url_text.setPlaceholderText("Requesting signature from S3 provider...")
        self.btn_copy.setEnabled(False)
        self.btn_open.setEnabled(False)
        self.btn_refresh.setEnabled(False)

        # Send command to bridge with callback emitting Qt signal
        self.bridge.get_presigned_url(
            path=self.path,
            expiry=seconds,
            method=method,
            callback=self.url_received.emit
        )

    @pyqtSlot(dict)
    def _on_url_received(self, res: dict):
        self.btn_refresh.setEnabled(True)
        if res.get("status") == "ok":
            self.current_url = res.get("url", "")
            self.url_text.setPlainText(self.current_url)
            self.url_text.selectAll()
            self.btn_copy.setEnabled(True)
            self.btn_open.setEnabled(True)
            self.status_lbl.setStyleSheet("color: #2e7d32; font-weight: bold;")
            self.status_lbl.setText("✓ Presigned URL ready. Valid until expiration time.")
        else:
            error = res.get("error", "Unknown error generating presigned URL")
            self.current_url = ""
            self.url_text.clear()
            self.btn_copy.setEnabled(False)
            self.btn_open.setEnabled(False)
            self.status_lbl.setStyleSheet("color: #c62828; font-weight: bold;")
            self.status_lbl.setText(f"Error: {error}")

    def _on_copy_url(self):
        if self.current_url:
            QApplication.clipboard().setText(self.current_url)
            self.btn_copy.setText("✓ Copied to Clipboard!")
            QTimer.singleShot(2000, lambda: self.btn_copy.setText("Copy URL"))

    def _on_open_browser(self):
        if self.current_url:
            QDesktopServices.openUrl(QUrl(self.current_url))
