from PyQt5.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QMessageBox, QHBoxLayout
)

from app.desktop.db import verify_login
from app.desktop.ui.register_window import RegisterWindow


class LoginWindow(QWidget):
    def __init__(self, on_login_success):
        """
        on_login_success: callback(user_dict)
        """
        super().__init__()
        self.setWindowTitle("Přihlášení")
        self.on_login_success = on_login_success

        layout = QVBoxLayout()

        layout.addWidget(QLabel("Uživatelské jméno:"))
        self.username_inp = QLineEdit()
        self.username_inp.setPlaceholderText("např. fly123")
        layout.addWidget(self.username_inp)

        layout.addWidget(QLabel("Heslo:"))
        self.password_inp = QLineEdit()
        self.password_inp.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.password_inp)

        btn_row = QHBoxLayout()
        self.login_btn = QPushButton("Přihlásit")
        self.register_btn = QPushButton("Registrovat")

        self.login_btn.clicked.connect(self.login)
        self.register_btn.clicked.connect(self.open_register)

        btn_row.addWidget(self.login_btn)
        btn_row.addWidget(self.register_btn)

        layout.addLayout(btn_row)
        self.setLayout(layout)

    def login(self):
        username = self.username_inp.text().strip()
        password = self.password_inp.text()

        if not username or not password:
            QMessageBox.warning(self, "Chyba", "Vyplň uživatelské jméno i heslo.")
            return

        user = verify_login(username, password)
        if not user:
            QMessageBox.warning(self, "Chyba", "Špatné jméno nebo heslo.")
            return

        QMessageBox.information(self, "OK", f"Přihlášen jako: {user['username']}")
        self.on_login_success(user)
        self.close()

    def open_register(self):
        self.reg = RegisterWindow()
        self.reg.show()
