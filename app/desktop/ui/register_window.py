from PyQt5.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QMessageBox
)

from app.desktop.db import create_user
import mysql.connector


class RegisterWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Registrace")

        layout = QVBoxLayout()

        layout.addWidget(QLabel("Uživatelské jméno:"))
        self.username_inp = QLineEdit()
        self.username_inp.setPlaceholderText("musí být unikátní")
        layout.addWidget(self.username_inp)

        layout.addWidget(QLabel("Heslo:"))
        self.password_inp = QLineEdit()
        self.password_inp.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.password_inp)

        layout.addWidget(QLabel("Heslo znovu:"))
        self.password2_inp = QLineEdit()
        self.password2_inp.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.password2_inp)

        self.create_btn = QPushButton("Vytvořit účet")
        self.create_btn.clicked.connect(self.register)
        layout.addWidget(self.create_btn)

        self.setLayout(layout)

    def register(self):
        username = self.username_inp.text().strip()
        p1 = self.password_inp.text()
        p2 = self.password2_inp.text()

        if not username or not p1 or not p2:
            QMessageBox.warning(self, "Chyba", "Vyplň všechna pole.")
            return

        if len(username) < 3:
            QMessageBox.warning(self, "Chyba", "Username musí mít aspoň 3 znaky.")
            return

        if len(p1) < 4:
            QMessageBox.warning(self, "Chyba", "Heslo musí mít aspoň 4 znaky.")
            return

        if p1 != p2:
            QMessageBox.warning(self, "Chyba", "Hesla se neshodují.")
            return

        try:
            create_user(username, p1, role="user")
        except mysql.connector.errors.IntegrityError:
            QMessageBox.warning(self, "Chyba", "Toto uživatelské jméno už existuje.")
            return
        except Exception as e:
            QMessageBox.warning(self, "Chyba", f"Nepovedlo se vytvořit účet:\n{e}")
            return

        QMessageBox.information(self, "OK", "Účet vytvořen. Teď se přihlaš.")
        self.close()
