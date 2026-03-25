import mysql.connector
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

from app.desktop.db import create_user


class RegisterWindow(QWidget):
    """Registrační okno pro vytvoření nového uživatele."""

    def __init__(self):
        super().__init__()
        self.setObjectName("RootPage")
        self.setWindowTitle("Registrace")
        self.setMinimumSize(650, 520)
        self.resize(720, 560)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(30, 24, 30, 24)
        root_layout.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setObjectName("Card")
        card.setMaximumWidth(580)

        layout = QVBoxLayout(card)
        layout.setSpacing(12)
        layout.setContentsMargins(28, 24, 28, 22)

        title = QLabel("Vytvoření účtu")
        title.setObjectName("TitleLabel")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Po registraci se přihlas do desktop aplikace.")
        subtitle.setObjectName("Subtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)

        layout.addWidget(QLabel("Uživatelské jméno"))
        self.username_inp = QLineEdit()
        self.username_inp.setPlaceholderText("musí být unikátní")
        self.username_inp.setMinimumHeight(44)
        layout.addWidget(self.username_inp)

        layout.addWidget(QLabel("Heslo"))
        self.password_inp = QLineEdit()
        self.password_inp.setEchoMode(QLineEdit.Password)
        self.password_inp.setMinimumHeight(44)
        layout.addWidget(self.password_inp)

        layout.addWidget(QLabel("Heslo znovu"))
        self.password2_inp = QLineEdit()
        self.password2_inp.setEchoMode(QLineEdit.Password)
        self.password2_inp.setMinimumHeight(44)
        layout.addWidget(self.password2_inp)

        self.create_btn = QPushButton("Vytvořit účet")
        self.create_btn.setObjectName("PrimaryButton")
        self.create_btn.setMinimumHeight(52)
        self.create_btn.clicked.connect(self.register)
        layout.addWidget(self.create_btn)

        root_layout.addWidget(card, 0, Qt.AlignCenter)

    def register(self):
        """Validuje formulář a pokusí se vytvořit uživatele v DB."""
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
        except Exception as exc:
            QMessageBox.warning(self, "Chyba", f"Nepovedlo se vytvořit účet:\n{exc}")
            return

        QMessageBox.information(self, "OK", "Účet vytvořen. Teď se přihlaš.")
        self.close()
