"""
Exact replica of Windows Cyberduck 'Transfers' window (TransferForm.cs).
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QToolBar, QToolButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar, QLabel, QWidget
)
from PyQt5.QtCore import Qt
from ..icons import get_icon


class TransfersWindow(QDialog):
    def __init__(self, parent=None, bridge=None):
        super().__init__(parent)
        self.bridge = bridge
        self.setWindowTitle("Transfers")
        self.setWindowIcon(get_icon("queue"))
        self.resize(600, 320)

        self._transfer_rows = {}
        self._setup_ui()
        if self.bridge:
            self._connect_bridge()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = QToolBar()
        toolbar.setIconSize(self.parent().iconSize() if self.parent() else toolbar.iconSize())

        self.resume_btn = QToolButton()
        self.resume_btn.setIcon(get_icon("resume"))
        self.resume_btn.setText("Resume")
        self.resume_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        toolbar.addWidget(self.resume_btn)

        self.stop_btn = QToolButton()
        self.stop_btn.setIcon(get_icon("stop"))
        self.stop_btn.setText("Stop")
        self.stop_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        toolbar.addWidget(self.stop_btn)

        self.reload_btn = QToolButton()
        self.reload_btn.setIcon(get_icon("reload"))
        self.reload_btn.setText("Reload")
        self.reload_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        toolbar.addWidget(self.reload_btn)

        toolbar.addSeparator()

        self.clean_btn = QToolButton()
        self.clean_btn.setIcon(get_icon("clean"))
        self.clean_btn.setText("Clear")
        self.clean_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.clean_btn.clicked.connect(self._clear_completed)
        toolbar.addWidget(self.clean_btn)

        layout.addWidget(toolbar)

        # Table
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Name", "Progress", "Transferred", "Speed", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.table.horizontalHeader().resizeSection(1, 140)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setShowGrid(False)

        layout.addWidget(self.table)

    def _connect_bridge(self):
        self.bridge.transfer_started.connect(self.on_transfer_started)
        self.bridge.transfer_progress.connect(self.on_transfer_progress)
        self.bridge.transfer_complete.connect(self.on_transfer_complete)
        self.bridge.transfer_failed.connect(self.on_transfer_failed)

    def add_transfer(self, transfer_id: str, name: str, is_upload: bool = False, total_size: int = 0):
        if transfer_id in self._transfer_rows:
            return

        row = self.table.rowCount()
        self.table.insertRow(row)
        self._transfer_rows[transfer_id] = row

        icon = get_icon("upload" if is_upload else "download")
        name_item = QTableWidgetItem(icon, name)
        self.table.setItem(row, 0, name_item)

        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(0)
        progress_bar.setTextVisible(True)
        self.table.setCellWidget(row, 1, progress_bar)

        size_text = f"0 / {_format_size(total_size)}" if total_size > 0 else "0 bytes"
        self.table.setItem(row, 2, QTableWidgetItem(size_text))
        self.table.setItem(row, 3, QTableWidgetItem("-"))
        self.table.setItem(row, 4, QTableWidgetItem("Running"))

    def on_transfer_started(self, transfer_id: str):
        if transfer_id not in self._transfer_rows:
            self.add_transfer(transfer_id, f"Transfer {transfer_id[:8]}")

    def on_transfer_progress(self, transfer_id: str, size: int, transferred: int, fraction: float, text: str):
        row = self._transfer_rows.get(transfer_id)
        if row is None:
            self.add_transfer(transfer_id, f"Transfer {transfer_id[:8]}", total_size=size)
            row = self._transfer_rows.get(transfer_id)

        bar = self.table.cellWidget(row, 1)
        if bar:
            bar.setValue(int(fraction * 100))

        size_text = f"{_format_size(transferred)} of {_format_size(size)}" if size > 0 else f"{_format_size(transferred)}"
        self.table.item(row, 2).setText(size_text)
        if text:
            self.table.item(row, 3).setText(text)
        self.table.item(row, 4).setText("Transferring")

    def on_transfer_complete(self, transfer_id: str, complete: bool):
        row = self._transfer_rows.get(transfer_id)
        if row is not None:
            bar = self.table.cellWidget(row, 1)
            if bar:
                bar.setValue(100)
            self.table.item(row, 4).setText("Complete" if complete else "Stopped")

    def on_transfer_failed(self, transfer_id: str, error: str):
        row = self._transfer_rows.get(transfer_id)
        if row is not None:
            self.table.item(row, 4).setText(f"Error: {error}")

    def _clear_completed(self):
        to_remove = []
        for tid, row in list(self._transfer_rows.items()):
            status_item = self.table.item(row, 4)
            if status_item and status_item.text() in ("Complete", "Stopped"):
                to_remove.append(tid)

        for tid in to_remove:
            row = self._transfer_rows.pop(tid)
            self.table.removeRow(row)
            # Reindex remaining rows
            for k, v in self._transfer_rows.items():
                if v > row:
                    self._transfer_rows[k] = v - 1


def _format_size(bytes_val: int) -> str:
    if bytes_val < 1024:
        return f"{bytes_val} bytes"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} KB"
    elif bytes_val < 1024 * 1024 * 1024:
        return f"{bytes_val / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_val / (1024 * 1024 * 1024):.2f} GB"
