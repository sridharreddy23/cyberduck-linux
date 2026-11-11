"""
Exact replica of Windows Cyberduck 'Info' inspector (InfoForm.cs).
"""
import datetime
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QGridLayout, QLabel, QLineEdit, QCheckBox, QGroupBox, QPushButton
)
from PyQt5.QtCore import Qt
from ..icons import get_icon, get_file_icon


class InfoDialog(QDialog):
    def __init__(self, file_data: dict, parent=None):
        super().__init__(parent)
        self.file_data = file_data
        self.setWindowTitle(f"Info – {file_data.get('name', 'File')}")
        self.setWindowIcon(get_icon("info"))
        self.resize(380, 420)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        tabs = QTabWidget()

        # Tab 1: General
        general_tab = QWidget()
        gen_layout = QGridLayout(general_tab)
        gen_layout.setSpacing(8)

        # Header icon + filename
        name = self.file_data.get("name", "")
        is_dir = self.file_data.get("isDir", False)
        icon = get_file_icon(name, is_dir)
        icon_label = QLabel()
        icon_label.setPixmap(icon.pixmap(32, 32))
        gen_layout.addWidget(icon_label, 0, 0, Qt.AlignCenter)

        name_edit = QLineEdit(name)
        name_edit.setReadOnly(True)
        gen_layout.addWidget(name_edit, 0, 1)

        # Details
        gen_layout.addWidget(QLabel("Full Path:"), 1, 0, Qt.AlignRight)
        path_edit = QLineEdit(self.file_data.get("absolute", ""))
        path_edit.setReadOnly(True)
        gen_layout.addWidget(path_edit, 1, 1)

        size_val = self.file_data.get("size", 0)
        gen_layout.addWidget(QLabel("Size:"), 2, 0, Qt.AlignRight)
        gen_layout.addWidget(QLabel(_format_size_detailed(size_val)), 2, 1)

        mod_val = self.file_data.get("modified", 0)
        gen_layout.addWidget(QLabel("Modified:"), 3, 0, Qt.AlignRight)
        mod_str = datetime.datetime.fromtimestamp(mod_val / 1000).strftime("%Y-%m-%d %H:%M:%S") if mod_val else "-"
        gen_layout.addWidget(QLabel(mod_str), 3, 1)

        gen_layout.addWidget(QLabel("Kind:"), 4, 0, Qt.AlignRight)
        kind_str = "Folder" if is_dir else "Plain text document" if name.endswith(".txt") else "File"
        gen_layout.addWidget(QLabel(kind_str), 4, 1)

        gen_layout.setRowStretch(5, 1)
        tabs.addTab(general_tab, "General")

        # Tab 2: Permissions
        perm_tab = QWidget()
        perm_layout = QVBoxLayout(perm_tab)

        perm_str = str(self.file_data.get("permission", ""))
        perm_box = QGroupBox("UNIX Permissions")
        pgrid = QGridLayout(perm_box)
        pgrid.addWidget(QLabel(""), 0, 0)
        pgrid.addWidget(QLabel("Read"), 0, 1, Qt.AlignCenter)
        pgrid.addWidget(QLabel("Write"), 0, 2, Qt.AlignCenter)
        pgrid.addWidget(QLabel("Execute"), 0, 3, Qt.AlignCenter)

        # Owner, Group, Others
        roles = ["Owner", "Group", "Others"]
        for row, role in enumerate(roles, start=1):
            pgrid.addWidget(QLabel(f"{role}:"), row, 0)
            r_chk = QCheckBox()
            r_chk.setChecked(True)
            pgrid.addWidget(r_chk, row, 1, Qt.AlignCenter)

            w_chk = QCheckBox()
            w_chk.setChecked("write" in perm_str if row == 1 else False)
            pgrid.addWidget(w_chk, row, 2, Qt.AlignCenter)

            x_chk = QCheckBox()
            x_chk.setChecked(is_dir)
            pgrid.addWidget(x_chk, row, 3, Qt.AlignCenter)

        perm_layout.addWidget(perm_box)

        octal_layout = QHBoxLayout()
        octal_layout.addWidget(QLabel("Octal mask:"))
        octal_edit = QLineEdit("0755" if is_dir else "0644")
        octal_edit.setFixedWidth(60)
        octal_layout.addWidget(octal_edit)
        octal_layout.addStretch()
        perm_layout.addLayout(octal_layout)
        perm_layout.addStretch()

        tabs.addTab(perm_tab, "Permissions")

        layout.addWidget(tabs)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)


def _format_size_detailed(bytes_val: int) -> str:
    if bytes_val < 1024:
        return f"{bytes_val} bytes"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} KB ({bytes_val:,} bytes)"
    else:
        return f"{bytes_val / (1024 * 1024):.2f} MB ({bytes_val:,} bytes)"
