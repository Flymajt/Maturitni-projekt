from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFrame,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.desktop.db import get_user_by_username, verify_login


class LoginWindow(QWidget):
    """Přihlašovací okno desktop aplikace."""

    def __init__(self, on_login_success):
        """on_login_success je callback volaný po úspěšném loginu."""
        super().__init__()
        self.setObjectName("RootPage")
        self.setWindowTitle("Přihlášení do kvízu")
        self.on_login_success = on_login_success

        self.setMinimumSize(700, 520)
        self.resize(780, 560)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(32, 28, 32, 28)
        root_layout.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setObjectName("Card")
        card.setMaximumWidth(620)

        layout = QVBoxLayout(card)
        layout.setSpacing(14)
        layout.setContentsMargins(30, 28, 30, 24)

        title = QLabel("Interaktivní kvíz")
        title.setObjectName("TitleLabel")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Přihlas se a pokračuj do hry.")
        subtitle.setWordWrap(True)
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setObjectName("Subtitle")
        layout.addWidget(subtitle)

        layout.addSpacing(6)

        username_lbl = QLabel("Uživatelské jméno")
        layout.addWidget(username_lbl)
        self.username_inp = QLineEdit()
        self.username_inp.setPlaceholderText("např. fly123")
        self.username_inp.setMinimumHeight(44)
        layout.addWidget(self.username_inp)

        password_lbl = QLabel("Heslo")
        layout.addWidget(password_lbl)
        self.password_inp = QLineEdit()
        self.password_inp.setEchoMode(QLineEdit.Password)
        self.password_inp.setMinimumHeight(44)
        self.password_inp.returnPressed.connect(self.login)
        layout.addWidget(self.password_inp)

        self.login_btn = QPushButton("Přihlásit")
        self.login_btn.setObjectName("PrimaryButton")
        self.login_btn.setMinimumHeight(52)
        self.login_btn.clicked.connect(self.login)
        layout.addWidget(self.login_btn)

        web_hint = QLabel("Registrace účtu je na webovém rozhraní.")
        web_hint.setAlignment(Qt.AlignCenter)
        web_hint.setObjectName("Hint")
        layout.addWidget(web_hint)

        root_layout.addWidget(card, 0, Qt.AlignCenter)
        self.username_inp.setFocus()

    def login(self):
        """Zkusí přihlásit uživatele podle zadaných údajů."""
        username = self.username_inp.text().strip()
        password = self.password_inp.text()

        if not username or not password:
            QMessageBox.warning(self, "Chyba", "Vyplň uživatelské jméno i heslo.")
            return

        db_user = get_user_by_username(username)
        if not db_user:
            QMessageBox.warning(self, "Chyba", "Tento uživatel neexistuje.")
            return

        user = verify_login(username, password)
        if not user:
            QMessageBox.warning(self, "Chyba", "Špatné heslo.")
            return

        QMessageBox.information(self, "OK", f"Přihlášen jako: {user['username']}")
        self.on_login_success(user)
        self.close()
