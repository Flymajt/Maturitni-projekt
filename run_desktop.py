import sys

from PyQt5.QtWidgets import QApplication

from app.desktop.main import AppController, DESKTOP_THEME


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(DESKTOP_THEME)

    controller = AppController()
    controller.run()
    sys.exit(app.exec_())
