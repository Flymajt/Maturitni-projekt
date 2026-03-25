import sys

from PyQt5.QtWidgets import QApplication

from app.desktop.ui.login_window import LoginWindow
from app.desktop.ui.start_window import StartWindow


DESKTOP_THEME = """
QWidget {
    background-color: #EBF4F6;
    color: #09637E;
    font-family: 'Segoe UI';
    font-size: 14px;
}

QWidget#RootPage {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 #EBF4F6,
        stop: 0.55 #D9ECEE,
        stop: 1 #CBE4E7
    );
}

QFrame#Card {
    background-color: rgba(235, 244, 246, 0.96);
    border: 2px solid #7AB2B2;
    border-radius: 18px;
}

QLabel {
    color: #09637E;
    font-weight: 600;
}

QLabel#TitleLabel {
    font-size: 28px;
    font-weight: 800;
}

QLabel#Subtitle {
    color: #088395;
    font-size: 15px;
    font-weight: 600;
}

QLabel#Hint {
    color: #088395;
    font-size: 13px;
    font-weight: 500;
}

QLabel#MetaPill {
    background-color: rgba(8, 131, 149, 0.14);
    border: 1px solid rgba(8, 131, 149, 0.45);
    border-radius: 11px;
    padding: 8px 12px;
    font-size: 13px;
    font-weight: 700;
}

QLabel#QuestionText {
    background-color: #FFFFFF;
    border: 2px solid #7AB2B2;
    border-radius: 14px;
    padding: 20px;
    font-size: 30px;
    font-weight: 800;
}

QPushButton {
    background-color: #09637E;
    color: #EBF4F6;
    border: none;
    border-radius: 11px;
    padding: 10px 14px;
    font-weight: 700;
}

QPushButton:hover {
    background-color: #088395;
}

QPushButton:pressed {
    background-color: #065268;
}

QPushButton#PrimaryButton {
    font-size: 16px;
    font-weight: 800;
    padding: 12px 16px;
}

QPushButton#AnswerButton {
    font-size: 18px;
    font-weight: 800;
    padding: 14px;
    text-align: left;
}

QLineEdit, QComboBox, QTextEdit {
    background-color: #FFFFFF;
    border: 2px solid #7AB2B2;
    border-radius: 10px;
    padding: 8px 10px;
    color: #09637E;
}

QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
    border: 2px solid #088395;
}

QComboBox::drop-down {
    border: none;
}

QComboBox QAbstractItemView {
    background-color: #FFFFFF;
    selection-background-color: #088395;
    selection-color: #EBF4F6;
}
"""


class AppController:
    """Řídí tok desktop aplikace mezi loginem a startem kvízu."""

    def __init__(self):
        self.user = None
        self.start_window = None
        self.login_window = None

    def run(self):
        """Spustí aplikaci a otevře přihlašovací okno."""
        self.login_window = LoginWindow(on_login_success=self.on_login_success)
        self.login_window.show()

    def on_login_success(self, user):
        """Po úspěšném loginu uloží uživatele a otevře start okno."""
        self.user = user
        self.start_window = StartWindow(user=self.user)
        self.start_window.show()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(DESKTOP_THEME)

    controller = AppController()
    controller.run()
    sys.exit(app.exec_())
