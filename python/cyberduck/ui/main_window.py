"""
Exact replica of Windows Cyberduck Browser (BrowserForm.Designer.cs + BrowserForm.cs).
"""
import os
import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QMenuBar, QMenu, QAction, QToolBar, QToolButton, QTreeView,
    QHeaderView, QComboBox, QLineEdit, QLabel, QStatusBar,
    QFileDialog, QInputDialog, QMessageBox, QListWidget, QListWidgetItem
)
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QIcon, QFont, QKeySequence
from PyQt5.QtCore import Qt, QSize, pyqtSlot, QFileSystemWatcher

from ..icons import get_icon, get_file_icon, get_protocol_icon
from ..bookmarks import load_bookmarks, Bookmark, BOOKMARKS_DIR
from ..backend.bridge import CyberduckBridge
from .connection_dialog import ConnectionDialog
from .transfers_dialog import TransfersWindow
from .info_dialog import InfoDialog
from .bookmark_dialog import BookmarkDialog
from .login_prompt_dialog import LoginPromptDialog
from .presigned_url_dialog import PresignedUrlDialog


class BookmarkListItemWidget(QWidget):
    def __init__(self, bm: Bookmark, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(8)

        icon_lbl = QLabel()
        icon = get_protocol_icon(bm.protocol)
        icon_lbl.setPixmap(icon.pixmap(20, 20))
        layout.addWidget(icon_lbl, 0, Qt.AlignVCenter)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(1)

        title_lbl = QLabel(bm.nickname)
        title_lbl.setFont(QFont("Segoe UI", 9, QFont.Bold))
        text_layout.addWidget(title_lbl)

        sub_lbl = QLabel(bm.subtitle)
        sub_lbl.setFont(QFont("Segoe UI", 8))
        sub_lbl.setStyleSheet("color: #666;")
        text_layout.addWidget(sub_lbl)

        layout.addLayout(text_layout, 1)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cyberduck")
        self.setWindowIcon(get_icon("app"))
        self.resize(960, 620)

        # Initialize bridge to Java engine
        self.bridge = CyberduckBridge(self)
        self.bridge.start()

        # Windows
        self.transfers_window = TransfersWindow(self, self.bridge)

        # State
        self.current_files: List[dict] = []
        self.current_path = "/"
        self.path_history: List[str] = []
        self.path_history_index = -1
        self.show_hidden = False

        self._setup_menus()
        self._setup_toolbar()
        self._setup_ui()
        self._setup_statusbar()
        self._connect_signals()

        # Watch ~/.duck/Bookmarks/ for live external updates
        self.bookmarks_watcher = QFileSystemWatcher(self)
        BOOKMARKS_DIR.mkdir(parents=True, exist_ok=True)
        self.bookmarks_watcher.addPath(str(BOOKMARKS_DIR))
        self.bookmarks_watcher.directoryChanged.connect(self._refresh_bookmarks)
        self.bookmarks_watcher.fileChanged.connect(self._refresh_bookmarks)

        # Load initial bookmarks
        self._refresh_bookmarks()

    def _setup_menus(self):
        menubar = self.menuBar()

        # File Menu
        file_menu = menubar.addMenu("&File")

        self.act_open_conn = QAction(get_icon("connect"), "&Open Connection...", self)
        self.act_open_conn.setShortcut(QKeySequence("Ctrl+O"))
        self.act_open_conn.triggered.connect(self.on_open_connection)
        file_menu.addAction(self.act_open_conn)

        self.act_disconnect = QAction(get_icon("eject"), "&Disconnect", self)
        self.act_disconnect.setShortcut(QKeySequence("Ctrl+D"))
        self.act_disconnect.setEnabled(False)
        self.act_disconnect.triggered.connect(self.on_disconnect)
        file_menu.addAction(self.act_disconnect)

        file_menu.addSeparator()

        self.act_new_folder = QAction(get_icon("folderplus"), "New &Folder...", self)
        self.act_new_folder.setShortcut(QKeySequence("Ctrl+Shift+N"))
        self.act_new_folder.setEnabled(False)
        self.act_new_folder.triggered.connect(self.on_new_folder)
        file_menu.addAction(self.act_new_folder)

        self.act_download = QAction(get_icon("download"), "&Download As...", self)
        self.act_download.setShortcut(QKeySequence("Ctrl+Shift+D"))
        self.act_download.setEnabled(False)
        self.act_download.triggered.connect(self.on_download)
        file_menu.addAction(self.act_download)

        self.act_upload = QAction(get_icon("upload"), "&Upload...", self)
        self.act_upload.setShortcut(QKeySequence("Ctrl+U"))
        self.act_upload.setEnabled(False)
        self.act_upload.triggered.connect(self.on_upload)
        file_menu.addAction(self.act_upload)

        self.act_presign = QAction(get_icon("browser"), "Get &Presigned URL...", self)
        self.act_presign.setShortcut(QKeySequence("Ctrl+Shift+U"))
        self.act_presign.setEnabled(False)
        self.act_presign.triggered.connect(self.on_presigned_url)
        file_menu.addAction(self.act_presign)

        file_menu.addSeparator()

        self.act_rename = QAction("&Rename...", self)
        self.act_rename.setShortcut(QKeySequence("F2"))
        self.act_rename.setEnabled(False)
        self.act_rename.triggered.connect(self.on_rename)
        file_menu.addAction(self.act_rename)

        self.act_delete = QAction(get_icon("delete"), "De&lete...", self)
        self.act_delete.setShortcut(QKeySequence("Delete"))
        self.act_delete.setEnabled(False)
        self.act_delete.triggered.connect(self.on_delete)
        file_menu.addAction(self.act_delete)

        file_menu.addSeparator()

        act_exit = QAction("E&xit", self)
        act_exit.setShortcut(QKeySequence("Alt+F4"))
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        # Edit Menu
        edit_menu = menubar.addMenu("&Edit")
        edit_menu.addAction("Cu&t", lambda: None, QKeySequence("Ctrl+X"))
        edit_menu.addAction("&Copy", lambda: None, QKeySequence("Ctrl+C"))
        edit_menu.addAction("&Paste", lambda: None, QKeySequence("Ctrl+V"))
        edit_menu.addAction("Select &All", self.tree_view.selectAll if hasattr(self, 'tree_view') else lambda: None, QKeySequence("Ctrl+A"))

        # View Menu
        view_menu = menubar.addMenu("&View")
        self.act_reload = QAction(get_icon("reload"), "&Reload", self)
        self.act_reload.setShortcut(QKeySequence("F5"))
        self.act_reload.setEnabled(False)
        self.act_reload.triggered.connect(self.on_refresh)
        view_menu.addAction(self.act_reload)

        view_menu.addSeparator()

        self.act_hidden = QAction("Show &Hidden Files", self, checkable=True)
        self.act_hidden.setShortcut(QKeySequence("Ctrl+Shift+R"))
        self.act_hidden.triggered.connect(self.on_toggle_hidden)
        view_menu.addAction(self.act_hidden)

        # Go Menu
        go_menu = menubar.addMenu("&Go")
        self.act_back = QAction(get_icon("nav-backward"), "&Back", self)
        self.act_back.setShortcut(QKeySequence("Alt+Left"))
        self.act_back.setEnabled(False)
        self.act_back.triggered.connect(self.on_go_back)
        go_menu.addAction(self.act_back)

        self.act_forward = QAction(get_icon("nav-forward"), "&Forward", self)
        self.act_forward.setShortcut(QKeySequence("Alt+Right"))
        self.act_forward.setEnabled(False)
        self.act_forward.triggered.connect(self.on_go_forward)
        go_menu.addAction(self.act_forward)

        self.act_up = QAction(get_icon("nav-up"), "&Enclosing Folder", self)
        self.act_up.setShortcut(QKeySequence("Alt+Up"))
        self.act_up.setEnabled(False)
        self.act_up.triggered.connect(self.on_go_up)
        go_menu.addAction(self.act_up)

        # Bookmark Menu
        self.bm_menu = menubar.addMenu("&Bookmark")
        self.act_new_bm = QAction(get_icon("bookmark"), "&New Bookmark...", self)
        self.act_new_bm.setShortcut(QKeySequence("Ctrl+B"))
        self.act_new_bm.triggered.connect(self.on_new_bookmark)

        self.act_bm_current = QAction(get_icon("add"), "Bookmark &Current Connection...", self)
        self.act_bm_current.setShortcut(QKeySequence("Ctrl+Shift+B"))
        self.act_bm_current.setEnabled(False)
        self.act_bm_current.triggered.connect(self.on_bookmark_current)

        self.act_toggle_bm = QAction("&Toggle Bookmarks", self, checkable=True)
        self.act_toggle_bm.setShortcut(QKeySequence("Ctrl+1"))
        self.act_toggle_bm.setChecked(True)
        self.act_toggle_bm.triggered.connect(self.on_toggle_bookmarks_panel)

        # Window Menu
        win_menu = menubar.addMenu("&Window")
        win_menu.addAction(get_icon("queue"), "&Transfers", self.on_show_transfers, QKeySequence("Ctrl+T"))

        # Help Menu
        help_menu = menubar.addMenu("&Help")
        help_menu.addAction("Help &Topics", lambda: None, QKeySequence("F1"))
        help_menu.addSeparator()
        help_menu.addAction("About Cyberduck", self.on_about)

    def _setup_toolbar(self):
        toolbar = self.addToolBar("Standard")
        toolbar.setIconSize(QSize(32, 32))
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)

        # 1. Open Connection
        self.tb_open_conn = QToolButton()
        self.tb_open_conn.setDefaultAction(self.act_open_conn)
        self.tb_open_conn.setText("Open Connection")
        self.tb_open_conn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        toolbar.addWidget(self.tb_open_conn)

        # 2. Transfers
        self.tb_transfers = QToolButton()
        self.tb_transfers.setIcon(get_icon("queue"))
        self.tb_transfers.setText("Transfers")
        self.tb_transfers.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.tb_transfers.clicked.connect(self.on_show_transfers)
        toolbar.addWidget(self.tb_transfers)

        # 3. Action Menu
        self.tb_action = QToolButton()
        self.tb_action.setIcon(get_icon("sync"))
        self.tb_action.setText("Action")
        self.tb_action.setPopupMode(QToolButton.InstantPopup)
        self.tb_action.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        action_menu = QMenu(self)
        action_menu.addAction(self.act_new_folder)
        action_menu.addAction(self.act_download)
        action_menu.addAction(self.act_upload)
        action_menu.addAction(self.act_presign)
        action_menu.addSeparator()
        action_menu.addAction(self.act_rename)
        action_menu.addAction(self.act_delete)
        self.tb_action.setMenu(action_menu)
        toolbar.addWidget(self.tb_action)

        # 4. Info
        self.tb_info = QToolButton()
        self.tb_info.setIcon(get_icon("info"))
        self.tb_info.setText("Info")
        self.tb_info.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.tb_info.clicked.connect(self.on_info)
        self.tb_info.setEnabled(False)
        toolbar.addWidget(self.tb_info)

        # 5. Reload
        self.tb_reload = QToolButton()
        self.tb_reload.setDefaultAction(self.act_reload)
        self.tb_reload.setText("Reload")
        self.tb_reload.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        toolbar.addWidget(self.tb_reload)

        # 6. New Folder
        self.tb_new_folder = QToolButton()
        self.tb_new_folder.setDefaultAction(self.act_new_folder)
        self.tb_new_folder.setText("New Folder")
        self.tb_new_folder.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        toolbar.addWidget(self.tb_new_folder)

        # 7. Delete
        self.tb_delete = QToolButton()
        self.tb_delete.setDefaultAction(self.act_delete)
        self.tb_delete.setText("Delete")
        self.tb_delete.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        toolbar.addWidget(self.tb_delete)

        # 8. Download
        self.tb_download = QToolButton()
        self.tb_download.setDefaultAction(self.act_download)
        self.tb_download.setText("Download")
        self.tb_download.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        toolbar.addWidget(self.tb_download)

        # 9. Upload
        self.tb_upload = QToolButton()
        self.tb_upload.setDefaultAction(self.act_upload)
        self.tb_upload.setText("Upload")
        self.tb_upload.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        toolbar.addWidget(self.tb_upload)

        # 10. Disconnect
        self.tb_disconnect = QToolButton()
        self.tb_disconnect.setDefaultAction(self.act_disconnect)
        self.tb_disconnect.setText("Disconnect")
        self.tb_disconnect.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        toolbar.addWidget(self.tb_disconnect)

        toolbar.addSeparator()

        # Spacer
        spacer = QWidget()
        spacer.setSizePolicy(QWidget().sizePolicy().Expanding, QWidget().sizePolicy().Preferred)
        toolbar.addWidget(spacer)

        # Filter Box
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter")
        self.filter_edit.setFixedWidth(160)
        self.filter_edit.textChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self.filter_edit)

    def _setup_ui(self):
        central = QWidget(self)
        central.setObjectName("centralWidget")
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Path Navigation Bar (Windows Explorer Style)
        nav_bar = QWidget()
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setContentsMargins(6, 4, 6, 4)
        nav_layout.setSpacing(4)

        self.btn_back = QToolButton()
        self.btn_back.setDefaultAction(self.act_back)
        self.btn_back.setIcon(get_icon("nav-backward"))
        self.btn_back.setFixedSize(24, 24)
        nav_layout.addWidget(self.btn_back)

        self.btn_forward = QToolButton()
        self.btn_forward.setDefaultAction(self.act_forward)
        self.btn_forward.setIcon(get_icon("nav-forward"))
        self.btn_forward.setFixedSize(24, 24)
        nav_layout.addWidget(self.btn_forward)

        self.btn_up = QToolButton()
        self.btn_up.setDefaultAction(self.act_up)
        self.btn_up.setIcon(get_icon("nav-up"))
        self.btn_up.setFixedSize(24, 24)
        nav_layout.addWidget(self.btn_up)

        self.path_combo = QComboBox()
        self.path_combo.setEditable(True)
        self.path_combo.lineEdit().returnPressed.connect(self._on_path_entered)
        nav_layout.addWidget(self.path_combo, 1)

        main_layout.addWidget(nav_bar)

        # Splitter: Bookmarks Sidebar + Main TreeTable
        self.splitter = QSplitter(Qt.Horizontal)

        # Left: Bookmarks Drawer
        self.bookmarks_panel = QWidget()
        bm_layout = QVBoxLayout(self.bookmarks_panel)
        bm_layout.setContentsMargins(0, 0, 0, 0)
        bm_layout.setSpacing(0)

        bm_header = QWidget()
        bmh_layout = QHBoxLayout(bm_header)
        bmh_layout.setContentsMargins(6, 4, 6, 4)
        bmh_title = QLabel("Bookmarks")
        bmh_title.setFont(QFont("Segoe UI", 9, QFont.Bold))
        bmh_layout.addWidget(bmh_title)
        bmh_layout.addStretch()

        add_bm_btn = QToolButton()
        add_bm_btn.setIcon(get_icon("add"))
        add_bm_btn.setToolTip("New Bookmark (Ctrl+B)")
        add_bm_btn.clicked.connect(self.on_new_bookmark)
        bmh_layout.addWidget(add_bm_btn)

        dup_bm_btn = QToolButton()
        dup_bm_btn.setIcon(get_icon("clean"))
        dup_bm_btn.setToolTip("Duplicate Selected Bookmark")
        dup_bm_btn.clicked.connect(self.on_duplicate_bookmark)
        bmh_layout.addWidget(dup_bm_btn)

        edit_bm_btn = QToolButton()
        edit_bm_btn.setIcon(get_icon("info"))
        edit_bm_btn.setToolTip("Edit Bookmark")
        edit_bm_btn.clicked.connect(self.on_edit_bookmark)
        bmh_layout.addWidget(edit_bm_btn)

        del_bm_btn = QToolButton()
        del_bm_btn.setIcon(get_icon("delete"))
        del_bm_btn.setToolTip("Delete Bookmark")
        del_bm_btn.clicked.connect(self.on_delete_bookmark)
        bmh_layout.addWidget(del_bm_btn)

        bm_layout.addWidget(bm_header)

        # Bookmarks Filter Search Bar
        filter_widget = QWidget()
        fw_layout = QHBoxLayout(filter_widget)
        fw_layout.setContentsMargins(6, 2, 6, 6)
        self.bm_search = QLineEdit()
        self.bm_search.setPlaceholderText("Filter Bookmarks...")
        self.bm_search.setClearButtonEnabled(True)
        self.bm_search.textChanged.connect(self._filter_bookmarks)
        fw_layout.addWidget(self.bm_search)
        bm_layout.addWidget(filter_widget)

        self.bookmarks_list = QListWidget()
        self.bookmarks_list.setIconSize(QSize(20, 20))
        self.bookmarks_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.bookmarks_list.customContextMenuRequested.connect(self._on_bookmark_context_menu)
        self.bookmarks_list.itemDoubleClicked.connect(self._on_bookmark_double_clicked)
        bm_layout.addWidget(self.bookmarks_list)

        self.splitter.addWidget(self.bookmarks_panel)

        # Right: Windows TreeListView (ObjectListView replica)
        self.tree_view = QTreeView()
        self.model = QStandardItemModel(0, 5)
        self.model.setHorizontalHeaderLabels(["Filename", "Size", "Modified", "Kind", "Permissions"])
        self.tree_view.setModel(self.model)
        self.tree_view.setSortingEnabled(True)
        self.tree_view.setAnimated(False)
        self.tree_view.setAllColumnsShowFocus(True)
        self.tree_view.setSelectionMode(QTreeView.ExtendedSelection)
        # Prevent accidental inline editing — rename is only via F2 / context menu
        self.tree_view.setEditTriggers(QTreeView.NoEditTriggers)
        # Flat list style — no expand arrows, no indentation (we navigate into folders on double-click)
        self.tree_view.setRootIsDecorated(False)
        self.tree_view.setItemsExpandable(False)
        self.tree_view.setIndentation(0)
        # Visual polish
        self.tree_view.setAlternatingRowColors(True)
        self.tree_view.setUniformRowHeights(True)
        self.tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self._on_context_menu)
        self.tree_view.doubleClicked.connect(self._on_item_double_clicked)
        self.tree_view.selectionModel().selectionChanged.connect(self._on_selection_changed)

        # Header columns configuration
        header = self.tree_view.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.resizeSection(1, 100)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        header.resizeSection(2, 140)
        header.setSectionResizeMode(3, QHeaderView.Interactive)
        header.resizeSection(3, 130)
        header.setSectionResizeMode(4, QHeaderView.Interactive)
        header.resizeSection(4, 110)

        self.splitter.addWidget(self.tree_view)
        self.splitter.setSizes([200, 760])

        main_layout.addWidget(self.splitter, 1)
        self.setCentralWidget(central)

    def _setup_statusbar(self):
        sb = self.statusBar()
        sb.setSizeGripEnabled(True)

        self.sb_status = QLabel("Not connected.")
        self.sb_status.setObjectName("statusPanel")
        sb.addWidget(self.sb_status, 1)

        self.sb_items = QLabel("")
        self.sb_items.setObjectName("statusPanel")
        sb.addPermanentWidget(self.sb_items)

        self.sb_selection = QLabel("")
        self.sb_selection.setObjectName("statusPanel")
        sb.addPermanentWidget(self.sb_selection)

        self.sb_lock = QLabel()
        self.sb_lock.setObjectName("statusPanel")
        sb.addPermanentWidget(self.sb_lock)

    def _connect_signals(self):
        self.bridge.status_changed.connect(self.on_status_changed)
        self.bridge.connected.connect(self.on_connected)
        self.bridge.disconnected.connect(self.on_disconnected)
        self.bridge.listing_received.connect(self.on_listing_received)
        self.bridge.credentials_requested.connect(self.on_credentials_requested)
        self.bridge.error_received.connect(self.on_error_received)

    # --- Slots & Actions ---

    def on_open_connection(self):
        dlg = ConnectionDialog(self, self.bridge)
        if dlg.exec_() == ConnectionDialog.Accepted:
            info = dlg.get_connection_info()
            self.current_protocol = info["protocol"]
            self.current_username = info.get("username", "")
            self.bridge.connect_host(
                protocol=info["protocol"],
                hostname=info["hostname"],
                port=info["port"],
                username=info["username"],
                password=info["password"],
                token=info.get("token"),
                identity=info["identity"],
            )

    def on_disconnect(self):
        self.bridge.disconnect_host()

    def on_refresh(self):
        if self.bridge.is_connected:
            self.bridge.list_directory(self.current_path)

    def on_toggle_hidden(self, checked: bool):
        self.show_hidden = checked
        self._populate_tree(self.current_files)

    def on_toggle_bookmarks_panel(self, checked: bool):
        self.bookmarks_panel.setVisible(checked)

    def on_show_transfers(self):
        self.transfers_window.show()
        self.transfers_window.raise_()
        self.transfers_window.activateWindow()

    def on_new_folder(self):
        name, ok = QInputDialog.getText(self, "New Folder", "Folder Name:", text="New Folder")
        if ok and name.strip():
            self.bridge.create_folder(name.strip())

    def on_new_bookmark(self):
        bm = Bookmark()
        dlg = BookmarkDialog(bm, self)
        if dlg.exec_() == BookmarkDialog.Accepted:
            self._refresh_bookmarks()

    def on_edit_bookmark(self):
        item = self.bookmarks_list.currentItem()
        if not item:
            return
        bm = item.data(Qt.UserRole)
        if bm:
            dlg = BookmarkDialog(bm, self)
            if dlg.exec_() == BookmarkDialog.Accepted:
                self._refresh_bookmarks()

    def on_delete_bookmark(self):
        item = self.bookmarks_list.currentItem()
        if not item:
            return
        bm = item.data(Qt.UserRole)
        if bm:
            confirm = QMessageBox.question(
                self, "Delete Bookmark", f"Delete bookmark '{bm.nickname}'?",
                QMessageBox.Yes | QMessageBox.No
            )
            if confirm == QMessageBox.Yes:
                bm.delete()
                self._refresh_bookmarks()

    def on_download(self):
        selected = self._get_selected_items()
        if not selected:
            return
        if len(selected) == 1:
            item = selected[0]
            remote_path = item.get("absolute")
            filename = item.get("name", "download")
            downloads_dir = str(Path.home() / "Downloads" / filename)
            save_path, _ = QFileDialog.getSaveFileName(self, "Save File", downloads_dir, "All Files (*)")
            if save_path:
                self.on_show_transfers()
                self.bridge.download_file(remote_path, save_path)
        else:
            dest_dir = QFileDialog.getExistingDirectory(
                self, f"Download {len(selected)} items to folder", str(Path.home() / "Downloads")
            )
            if dest_dir:
                self.on_show_transfers()
                for item in selected:
                    r_path = item.get("absolute")
                    fname = item.get("name", "file")
                    local_target = str(Path(dest_dir) / fname)
                    self.bridge.download_file(r_path, local_target)

    def on_upload(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Select Files to Upload", str(Path.home()), "All Files (*)")
        if paths:
            self.on_show_transfers()
            for p in paths:
                self.bridge.upload_file(p)

    def on_presigned_url(self):
        selected = self._get_selected_items()
        if not selected or selected[0].get("isDir"):
            return
        dlg = PresignedUrlDialog(selected[0], self.bridge, self)
        dlg.exec_()

    def on_rename(self):
        selected = self._get_selected_items()
        if not selected:
            return
        item = selected[0]
        old_name = item.get("name", "")
        new_name, ok = QInputDialog.getText(self, "Rename", "New name:", text=old_name)
        if ok and new_name.strip() and new_name.strip() != old_name:
            # Java delete/rename or bridge rename
            pass

    def on_delete(self):
        selected = self._get_selected_items()
        if not selected:
            return
        names = ", ".join(f"'{i.get('name')}'" for i in selected)
        confirm = QMessageBox.question(
            self, "Delete", f"Are you sure you want to delete {names}?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            for item in selected:
                self.bridge.delete_item(item.get("absolute"), is_dir=item.get("isDir", False))

    def on_info(self):
        selected = self._get_selected_items()
        if not selected:
            return
        dlg = InfoDialog(selected[0], self)
        dlg.show()

    def on_about(self):
        QMessageBox.about(
            self,
            "About Cyberduck",
            "<b>Cyberduck for Linux (Windows Native UI)</b><br><br>"
            "Version 9.6.1<br>"
            "Running with native Windows Look & Feel on Python/Qt<br>"
            "Powered by iterate GmbH Cyberduck Java Engine."
        )

    # --- Navigation ---

    def on_go_back(self):
        if self.path_history_index > 0:
            self.path_history_index -= 1
            path = self.path_history[self.path_history_index]
            self.bridge.list_directory(path)

    def on_go_forward(self):
        if self.path_history_index < len(self.path_history) - 1:
            self.path_history_index += 1
            path = self.path_history[self.path_history_index]
            self.bridge.list_directory(path)

    def on_go_up(self):
        if self.current_path and self.current_path != "/":
            parent = str(Path(self.current_path).parent)
            self.bridge.list_directory(parent)

    def _on_path_entered(self):
        path = self.path_combo.currentText().strip()
        if path and self.bridge.is_connected:
            self.bridge.list_directory(path)

    def _on_filter_changed(self, text: str):
        query = text.strip().lower()
        if not query:
            filtered = self.current_files
        else:
            filtered = [f for f in self.current_files if query in f.get("name", "").lower()]
        self._populate_tree(filtered)

    # --- Bridge Callbacks ---

    @pyqtSlot(str)
    def on_status_changed(self, message: str):
        self.sb_status.setText(message)

    @pyqtSlot(dict)
    def on_connected(self, info: dict):
        host = info.get("hostname", "")
        self.setWindowTitle(f"{host} – Cyberduck")
        self.act_disconnect.setEnabled(True)
        self.act_reload.setEnabled(True)
        self.act_new_folder.setEnabled(True)
        self.act_upload.setEnabled(True)
        if hasattr(self, "act_bm_current"):
            self.act_bm_current.setEnabled(True)
        self.sb_lock.setPixmap(get_icon("locked").pixmap(14, 14))

    @pyqtSlot()
    def on_disconnected(self):
        self.setWindowTitle("Cyberduck")
        self.act_disconnect.setEnabled(False)
        self.act_reload.setEnabled(False)
        self.act_new_folder.setEnabled(False)
        self.act_download.setEnabled(False)
        self.act_upload.setEnabled(False)
        self.act_presign.setEnabled(False)
        self.act_rename.setEnabled(False)
        self.act_delete.setEnabled(False)
        if hasattr(self, "act_bm_current"):
            self.act_bm_current.setEnabled(False)
        self.tb_info.setEnabled(False)
        self.sb_lock.clear()
        self.model.removeRows(0, self.model.rowCount())
        self.path_combo.clear()
        self.sb_status.setText("Not connected.")
        self.sb_items.setText("")
        self.sb_selection.setText("")

    @pyqtSlot(str, list)
    def on_listing_received(self, path: str, files: list):
        self.current_path = path
        self.current_files = files

        # Update path history
        if not self.path_history or self.path_history[-1] != path:
            self.path_history = self.path_history[:self.path_history_index + 1]
            self.path_history.append(path)
            self.path_history_index = len(self.path_history) - 1

        self.act_back.setEnabled(self.path_history_index > 0)
        self.act_forward.setEnabled(self.path_history_index < len(self.path_history) - 1)
        self.act_up.setEnabled(path != "/" and path != "")

        # Update path combobox
        if self.path_combo.findText(path) == -1:
            self.path_combo.addItem(path)
        self.path_combo.setCurrentText(path)

        self._populate_tree(files)

    @pyqtSlot(str)
    def on_error_received(self, error: str):
        self.sb_status.setText(f"Connection failed: {error}")
        msg = error
        if "security token" in error.lower() or "expired" in error.lower():
            msg += "\n\nTip: Your AWS session token (STS) appears to be expired.\nPlease refresh your AWS credentials in your terminal (e.g. aws sso login or role assume) and click 'Load from AWS Environment' in the connection dialog."
        QMessageBox.warning(self, "Cyberduck Connection Error", msg)

    @pyqtSlot(dict)
    def on_credentials_requested(self, data: dict):
        dlg = LoginPromptDialog(data, parent=self)
        if dlg.exec_() == LoginPromptDialog.Accepted:
            self.bridge.respond_credentials(
                prompt_id=data.get("promptId", ""),
                username=dlg.username,
                password=dlg.password,
                token=getattr(dlg, "token", None),
                canceled=False,
            )
        else:
            self.bridge.respond_credentials(
                prompt_id=data.get("promptId", ""),
                username="",
                password="",
                token=None,
                canceled=True,
            )

    # --- TreeTable View Rendering ---

    def _populate_tree(self, files: list):
        self.model.removeRows(0, self.model.rowCount())

        # Sort folders first, then alphabetically
        sorted_files = sorted(
            files,
            key=lambda x: (not x.get("isDir", False), x.get("name", "").lower())
        )

        for file_info in sorted_files:
            name = file_info.get("name", "")
            if not self.show_hidden and name.startswith(".") and name not in (".", ".."):
                continue

            is_dir = file_info.get("isDir", False)
            size_bytes = file_info.get("size", 0)
            mod_ts = file_info.get("modified", 0)
            perm = file_info.get("permission", "")

            # 1. Filename item
            icon = get_file_icon(name, is_dir, file_info.get("isSymlink", False))
            name_item = QStandardItem(icon, name)
            name_item.setData(file_info, Qt.UserRole)
            name_item.setEditable(False)

            # 2. Size item
            size_str = "-" if is_dir else _format_size(size_bytes)
            size_item = QStandardItem(size_str)
            size_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            size_item.setEditable(False)

            # 3. Modified item
            mod_str = ""
            if mod_ts:
                try:
                    dt = datetime.datetime.fromtimestamp(mod_ts / 1000)
                    mod_str = dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    mod_str = "-"
            mod_item = QStandardItem(mod_str)
            mod_item.setEditable(False)

            # 4. Kind item
            kind_str = "Folder" if is_dir else _get_kind(name)
            kind_item = QStandardItem(kind_str)
            kind_item.setEditable(False)

            # 5. Permissions item
            perm_display = _format_perm(perm, is_dir)
            perm_item = QStandardItem(perm_display)
            perm_item.setEditable(False)

            self.model.appendRow([name_item, size_item, mod_item, kind_item, perm_item])

        self.sb_items.setText(f"{len(sorted_files)} items")

    def _on_item_double_clicked(self, index):
        item = self.model.itemFromIndex(index.siblingAtColumn(0))
        if not item:
            return
        data = item.data(Qt.UserRole)
        if not data:
            return

        if data.get("isDir", False):
            # Navigate into directory
            self.bridge.list_directory(data.get("absolute"))
        else:
            # Show file info
            dlg = InfoDialog(data, self)
            dlg.show()

    def _on_selection_changed(self):
        selected = self._get_selected_items()
        count = len(selected)
        has_sel = count > 0

        self.act_download.setEnabled(has_sel)
        self.act_rename.setEnabled(count == 1)
        self.act_delete.setEnabled(has_sel)
        self.act_presign.setEnabled(count == 1 and not selected[0].get("isDir", False))
        self.tb_info.setEnabled(count == 1)

        if count == 0:
            self.sb_selection.setText("")
        elif count == 1:
            name = selected[0].get("name", "")
            size = selected[0].get("size", 0)
            size_str = f" ({_format_size(size)})" if not selected[0].get("isDir") else ""
            self.sb_selection.setText(f"1 item selected{size_str}")
        else:
            total_size = sum(x.get("size", 0) for x in selected if not x.get("isDir"))
            self.sb_selection.setText(f"{count} items selected ({_format_size(total_size)})")

    def _get_selected_items(self) -> List[dict]:
        indexes = self.tree_view.selectionModel().selectedRows(0)
        results = []
        for idx in indexes:
            item = self.model.itemFromIndex(idx)
            if item:
                data = item.data(Qt.UserRole)
                if data:
                    results.append(data)
        return results

    def _on_context_menu(self, pos):
        selected = self._get_selected_items()
        menu = QMenu(self)

        if selected:
            is_single = len(selected) == 1
            if is_single and selected[0].get("isDir"):
                menu.addAction("Open", lambda: self.bridge.list_directory(selected[0].get("absolute")))
            menu.addAction(self.act_download)
            if is_single and not selected[0].get("isDir"):
                menu.addAction(self.act_presign)
            menu.addSeparator()
            if is_single:
                menu.addAction(self.act_rename)
            menu.addAction(self.act_delete)
            menu.addSeparator()
            if is_single:
                menu.addAction(get_icon("info"), "Info", self.on_info)
            menu.addAction("Copy Path", lambda: QApplication.clipboard().setText(selected[0].get("absolute")))
        else:
            menu.addAction(self.act_new_folder)
            menu.addAction(self.act_upload)
            menu.addSeparator()
            menu.addAction(self.act_reload)

        menu.exec_(self.tree_view.viewport().mapToGlobal(pos))

    # --- Bookmarks Panel & Menu ---

    def _refresh_bookmarks(self):
        bms = load_bookmarks()

        # 1. Update Bookmarks Drawer List
        self.bookmarks_list.blockSignals(True)
        self.bookmarks_list.clear()
        for bm in bms:
            item = QListWidgetItem(self.bookmarks_list)
            item.setData(Qt.UserRole, bm)
            item.setSizeHint(QSize(200, 44))
            item.setToolTip(f"{bm.protocol}://{bm.hostname}:{bm.port}{bm.path_val}")
            w = BookmarkListItemWidget(bm)
            self.bookmarks_list.setItemWidget(item, w)
        self.bookmarks_list.blockSignals(False)

        # Re-apply current search filter if active
        if hasattr(self, "bm_search") and self.bm_search.text().strip():
            self._filter_bookmarks(self.bm_search.text())

        # 2. Update Bookmarks Menu Bar
        if hasattr(self, "bm_menu"):
            self.bm_menu.clear()
            self.bm_menu.addAction(self.act_new_bm)
            if hasattr(self, "act_bm_current"):
                self.bm_menu.addAction(self.act_bm_current)
            self.bm_menu.addAction(self.act_toggle_bm)
            self.bm_menu.addSeparator()

            if not bms:
                empty_act = self.bm_menu.addAction("(No bookmarks saved)")
                empty_act.setEnabled(False)
            else:
                for bm in bms:
                    icon = get_protocol_icon(bm.protocol)
                    act = self.bm_menu.addAction(icon, bm.nickname)
                    act.setData(bm)
                    act.triggered.connect(lambda chk, b=bm: self._connect_bookmark(b))

    def _filter_bookmarks(self, text: str):
        query = text.strip().lower()
        for i in range(self.bookmarks_list.count()):
            item = self.bookmarks_list.item(i)
            bm: Bookmark = item.data(Qt.UserRole)
            if not bm:
                continue
            matches = (
                not query
                or query in bm.nickname.lower()
                or query in bm.subtitle.lower()
                or query in bm.hostname.lower()
                or query in bm.protocol.lower()
                or query in (bm.username or "").lower()
            )
            item.setHidden(not matches)

    def on_duplicate_bookmark(self):
        item = self.bookmarks_list.currentItem()
        if not item:
            return
        bm: Bookmark = item.data(Qt.UserRole)
        if bm:
            cloned = bm.duplicate()
            self._refresh_bookmarks()

    def on_bookmark_current(self):
        if not self.bridge.is_connected:
            return
        bm = Bookmark()
        bm.hostname = self.bridge.current_hostname
        bm.path_val = self.current_path
        bm.protocol = getattr(self, "current_protocol", "s3")
        bm.username = getattr(self, "current_username", "")
        path_label = self.current_path.strip("/") or "Root"
        bm.nickname = f"{bm.hostname} – {path_label}"
        dlg = BookmarkDialog(bm, self)
        if dlg.exec_() == BookmarkDialog.Accepted:
            self._refresh_bookmarks()

    def _on_bookmark_context_menu(self, pos):
        item = self.bookmarks_list.itemAt(pos)
        menu = QMenu(self)
        if item:
            bm: Bookmark = item.data(Qt.UserRole)
            menu.addAction(get_icon("connect"), f"Connect to '{bm.nickname}'", lambda: self._connect_bookmark(bm))
            menu.addAction(get_icon("open"), "Open Connection Settings...", lambda: self._connect_bookmark(bm))
            menu.addSeparator()
            menu.addAction(get_icon("info"), "Edit Bookmark...", self.on_edit_bookmark)
            menu.addAction(get_icon("clean"), "Duplicate Bookmark", self.on_duplicate_bookmark)
            menu.addAction("Copy URL", lambda: QApplication.clipboard().setText(f"{bm.protocol}://{bm.hostname}{bm.path_val}"))
            menu.addAction(get_icon("delete"), "Delete Bookmark", self.on_delete_bookmark)
            menu.addSeparator()
        if self.bridge.is_connected:
            menu.addAction(get_icon("bookmark"), "Bookmark Current Connection...", self.on_bookmark_current)
        menu.addAction(get_icon("add"), "New Bookmark...", self.on_new_bookmark)
        menu.exec_(self.bookmarks_list.mapToGlobal(pos))

    def _on_bookmark_double_clicked(self, item):
        bm: Bookmark = item.data(Qt.UserRole)
        if bm:
            self._connect_bookmark(bm)

    def _connect_bookmark(self, bm: Bookmark):
        self.current_protocol = bm.protocol
        self.current_username = bm.username
        dlg = ConnectionDialog(self, self.bridge, initial_bookmark=bm)
        if dlg.exec_() == ConnectionDialog.Accepted:
            info = dlg.get_connection_info()
            self.current_protocol = info["protocol"]
            self.current_username = info.get("username", "")
            self.bridge.connect_host(
                protocol=info["protocol"],
                hostname=info["hostname"],
                port=info["port"],
                username=info["username"],
                password=info["password"],
                token=info.get("token"),
                identity=info["identity"],
            )


def _format_size(bytes_val: int) -> str:
    if bytes_val < 1024:
        return f"{bytes_val} B"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} KB"
    elif bytes_val < 1024 * 1024 * 1024:
        return f"{bytes_val / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_val / (1024 * 1024 * 1024):.2f} GB"


def _get_kind(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    mapping = {
        ".txt": "Plain text document",
        ".log": "Log document",
        ".pdf": "PDF document",
        ".zip": "ZIP archive",
        ".tar": "TAR archive",
        ".gz": "GZIP archive",
        ".png": "PNG image",
        ".jpg": "JPEG image",
        ".jpeg": "JPEG image",
        ".gif": "GIF image",
        ".html": "HTML document",
        ".xml": "XML document",
        ".json": "JSON document",
        ".py": "Python script",
        ".java": "Java source",
        ".sh": "Shell script",
        ".pub": "Public Key",
    }
    return mapping.get(ext, f"{ext[1:].upper()} File" if ext else "Document")


def _format_perm(perm_str: str, is_dir: bool) -> str:
    if not perm_str:
        return "drwxr-xr-x" if is_dir else "-rw-r--r--"
    if "user=read_write" in perm_str and "group=read" in perm_str:
        return "drwxr-xr-x" if is_dir else "-rw-r--r--"
    if "user=read_write" in perm_str and "group=none" in perm_str:
        return "-rw-------"
    return "drwxr-xr-x" if is_dir else "-rw-r--r--"
