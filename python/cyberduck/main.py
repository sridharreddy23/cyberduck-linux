"""
Main entry point for Cyberduck Linux (Windows exact UI).
"""
import os
import sys

# Ensure clean Qt display on Wayland / X11
if "QT_QPA_PLATFORM" not in os.environ and "WAYLAND_DISPLAY" in os.environ:
    os.environ["QT_QPA_PLATFORM"] = "xcb"

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from .theme import apply_windows_theme
from .ui.main_window import MainWindow


def main():
    # Enable High DPI scaling
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("Cyberduck")
    app.setOrganizationName("iterate GmbH")

    # Apply Windows 10/11 WinForms Theme
    apply_windows_theme(app)

    window = MainWindow()
    window.show()

    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
