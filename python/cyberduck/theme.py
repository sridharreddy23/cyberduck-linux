"""
Windows OS (WinForms / Windows 10/11 Explorer) Theme and Styling.
"""
from PyQt5.QtWidgets import QApplication, QStyleFactory
from PyQt5.QtGui import QFont, QPalette, QColor

WINDOWS_STYLESHEET = """
* {
    font-family: "Segoe UI", "Selawik", "Noto Sans", "Liberation Sans", sans-serif;
    font-size: 9pt;
}

/* Main Window & Dialogs */
QMainWindow, QDialog, QWidget#centralWidget {
    background-color: #F0F0F0;
    color: #000000;
}

/* Menu Bar */
QMenuBar {
    background-color: #FFFFFF;
    color: #000000;
    border-bottom: 1px solid #D8D8D8;
    padding: 2px 0px;
}

QMenuBar::item {
    background: transparent;
    padding: 3px 8px;
    margin: 1px 1px;
    border-radius: 2px;
}

QMenuBar::item:selected {
    background-color: #E5F1FB;
    color: #000000;
    border: 1px solid #CCE4F7;
}

QMenu {
    background-color: #F2F2F2;
    color: #000000;
    border: 1px solid #CCCCCC;
    padding: 2px;
}

QMenu::item {
    padding: 4px 24px 4px 28px;
    background: transparent;
}

QMenu::item:selected {
    background-color: #91C9F7;
    color: #000000;
}

QMenu::separator {
    height: 1px;
    background-color: #D7D7D7;
    margin: 3px 2px;
}

/* Windows ToolStrip Toolbar */
QToolBar {
    background-color: #F0F0F0;
    border-bottom: 1px solid #D8D8D8;
    border-top: none;
    border-left: none;
    border-right: none;
    spacing: 3px;
    padding: 3px 4px;
}

QToolButton {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 2px;
    padding: 4px 6px;
    font-size: 8.5pt;
    color: #000000;
}

QToolButton:hover {
    background-color: #E5F1FB;
    border: 1px solid #CCE4F7;
}

QToolButton:pressed {
    background-color: #CCE4F7;
    border: 1px solid #0078D7;
}

QToolButton:checked {
    background-color: #CCE4F7;
    border: 1px solid #0078D7;
}

QToolButton:disabled {
    color: #888888;
}

/* ToolBar Separator */
QToolBar::separator {
    width: 1px;
    background-color: #D8D8D8;
    margin: 4px 3px;
}

/* Windows Explorer Tree/Table View (ObjectListView replica) */
QTreeView {
    background-color: #FFFFFF;
    color: #000000;
    border: 1px solid #D8D8D8;
    gridline-color: #F0F0F0;
    selection-background-color: #CCE8FF;
    selection-color: #000000;
    outline: none;
}

QTreeView::item {
    height: 22px;
    padding: 1px 4px;
    border: 1px solid transparent;
}

QTreeView::item:hover {
    background-color: #E5F3FF;
    border: 1px solid #E5F3FF;
}

QTreeView::item:selected {
    background-color: #CCE8FF;
    color: #000000;
    border: 1px solid #99D1FF;
}

QTreeView::item:selected:!active {
    background-color: #E5E5E5;
    color: #000000;
    border: 1px solid #D0D0D0;
}

/* Table / Tree Header */
QHeaderView::section {
    background-color: #F0F0F0;
    color: #000000;
    padding: 3px 6px;
    border: none;
    border-right: 1px solid #D0D0D0;
    border-bottom: 1px solid #D0D0D0;
    font-size: 9pt;
    height: 22px;
}

QHeaderView::section:hover {
    background-color: #E5F1FB;
}

/* Path / Navigation Bar */
QComboBox {
    background-color: #FFFFFF;
    border: 1px solid #ABABAB;
    border-radius: 0px;
    padding: 3px 6px;
    min-height: 20px;
}

QComboBox:hover {
    border: 1px solid #0078D7;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 18px;
    border-left: 1px solid #ABABAB;
}

/* Text Inputs */
QLineEdit {
    background-color: #FFFFFF;
    color: #000000;
    border: 1px solid #ABABAB;
    padding: 3px 6px;
    min-height: 20px;
    border-radius: 0px;
}

QLineEdit:focus {
    border: 1px solid #0078D7;
}

/* Push Buttons */
QPushButton {
    background-color: #E1E1E1;
    color: #000000;
    border: 1px solid #ADADAD;
    padding: 4px 14px;
    min-width: 65px;
    min-height: 21px;
}

QPushButton:hover {
    background-color: #E5F1FB;
    border: 1px solid #0078D7;
}

QPushButton:pressed {
    background-color: #CCE4F7;
    border: 1px solid #005499;
}

QPushButton:default {
    border: 2px solid #0078D7;
}

QPushButton:disabled {
    background-color: #F0F0F0;
    color: #888888;
    border: 1px solid #CCCCCC;
}

/* CheckBoxes & RadioButtons */
QCheckBox, QRadioButton {
    spacing: 5px;
}

/* Status Bar */
QStatusBar {
    background-color: #F0F0F0;
    color: #000000;
    border-top: 1px solid #D8D8D8;
    min-height: 22px;
}

QStatusBar::item {
    border: none;
}

QLabel#statusPanel {
    background-color: transparent;
    padding: 1px 6px;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background: #F0F0F0;
    width: 14px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #CDCDCD;
    min-height: 24px;
}

QScrollBar::handle:vertical:hover {
    background: #A6A6A6;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background: #F0F0F0;
    height: 14px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background: #CDCDCD;
    min-width: 24px;
}

QScrollBar::handle:horizontal:hover {
    background: #A6A6A6;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Tab Widgets (Preferences, Info) */
QTabWidget::pane {
    border: 1px solid #D8D8D8;
    background-color: #FFFFFF;
}

QTabBar::tab {
    background: #F0F0F0;
    border: 1px solid #D8D8D8;
    border-bottom: none;
    padding: 5px 12px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background: #FFFFFF;
    border-bottom: 1px solid #FFFFFF;
}

/* GroupBox */
QGroupBox {
    border: 1px solid #D8D8D8;
    margin-top: 8px;
    padding-top: 10px;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 4px;
    color: #000000;
}
"""


def apply_windows_theme(app: QApplication):
    """Apply the Windows OS palette, font, and stylesheet."""
    if "Windows" in QStyleFactory.keys():
        app.setStyle(QStyleFactory.create("Windows"))
    elif "Fusion" in QStyleFactory.keys():
        app.setStyle(QStyleFactory.create("Fusion"))

    # Set font to Segoe UI / Selawik
    font = QFont("Selawik", 9)
    if not font.exactMatch():
        font = QFont("Segoe UI", 9)
    app.setFont(font)

    # Windows palette
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#F0F0F0"))
    palette.setColor(QPalette.WindowText, QColor("#000000"))
    palette.setColor(QPalette.Base, QColor("#FFFFFF"))
    palette.setColor(QPalette.AlternateBase, QColor("#F9F9F9"))
    palette.setColor(QPalette.ToolTipBase, QColor("#FFFFFF"))
    palette.setColor(QPalette.ToolTipText, QColor("#000000"))
    palette.setColor(QPalette.Text, QColor("#000000"))
    palette.setColor(QPalette.Button, QColor("#F0F0F0"))
    palette.setColor(QPalette.ButtonText, QColor("#000000"))
    palette.setColor(QPalette.BrightText, QColor("#FF0000"))
    palette.setColor(QPalette.Highlight, QColor("#CCE8FF"))
    palette.setColor(QPalette.HighlightedText, QColor("#000000"))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor("#888888"))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#888888"))
    app.setPalette(palette)

    app.setStyleSheet(WINDOWS_STYLESHEET)
