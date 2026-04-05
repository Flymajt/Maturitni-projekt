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

# Databázové helpery z desktop DB vrstvy.
# Soubor: `app/desktop/db.py`.
from app.desktop.db import get_user_by_username, verify_login


# Přihlašovací okno desktop aplikace.
class LoginWindow(QWidget):
    def __init__(self, on_login_success):
        # Zavoláme konstruktor rodiče (`QWidget`), aby se okno správně inicializovalo.
        super().__init__()

        # Název objektu používá QSS styl (theme v `app/desktop/main.py`).
        self.setObjectName("RootPage")
        self.setWindowTitle("Přihlášení do kvízu")

        # `on_login_success` je funkce (callback), kterou zavoláme po úspěšném loginu.
        self.on_login_success = on_login_success

        # Nastavení minimální a výchozí velikosti okna.
        self.setMinimumSize(700, 520)
        self.resize(780, 560)

        # Hlavní vertikální layout celého okna.
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(32, 28, 32, 28)
        root_layout.setAlignment(Qt.AlignCenter)

        # "Karta" uprostřed stránky.
        card = QFrame()
        card.setObjectName("Card")
        card.setMaximumWidth(620)

        # Layout uvnitř karty.
        layout = QVBoxLayout(card)
        layout.setSpacing(14)
        layout.setContentsMargins(30, 28, 30, 24)

        # Titulek.
        title = QLabel("Interaktivní kvíz")
        title.setObjectName("TitleLabel")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Podtitulek.
        subtitle = QLabel("Přihlas se a pokračuj do hry.")
        subtitle.setWordWrap(True)
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setObjectName("Subtitle")
        layout.addWidget(subtitle)

        layout.addSpacing(6)

        # Pole pro uživatelské jméno.
        username_lbl = QLabel("Uživatelské jméno")
        layout.addWidget(username_lbl)
        self.username_inp = QLineEdit()
        self.username_inp.setPlaceholderText("např. fly123")
        self.username_inp.setMinimumHeight(44)
        layout.addWidget(self.username_inp)

        # Pole pro heslo.
        password_lbl = QLabel("Heslo")
        layout.addWidget(password_lbl)
        self.password_inp = QLineEdit()
        # `Password` režim skryje znaky hesla tečkami/hvězdičkami.
        self.password_inp.setEchoMode(QLineEdit.Password)
        self.password_inp.setMinimumHeight(44)
        # Enter v poli hesla spustí stejnou akci jako klik na tlačítko Přihlásit.
        self.password_inp.returnPressed.connect(self.login)
        layout.addWidget(self.password_inp)

        # Tlačítko pro odeslání přihlášení.
        self.login_btn = QPushButton("Přihlásit")
        self.login_btn.setObjectName("PrimaryButton")
        self.login_btn.setMinimumHeight(52)
        self.login_btn.clicked.connect(self.login)
        layout.addWidget(self.login_btn)

        # Nápověda, že registrace je dostupná ve webové části.
        web_hint = QLabel("Registrace účtu je na webovém rozhraní.")
        web_hint.setAlignment(Qt.AlignCenter)
        web_hint.setObjectName("Hint")
        layout.addWidget(web_hint)

        # Vložíme kartu doprostřed okna.
        root_layout.addWidget(card, 0, Qt.AlignCenter)

        # Po otevření okna nastavíme kurzor do pole uživatelského jména.
        self.username_inp.setFocus()

    def login(self):
        # Načteme hodnoty z inputů.
        username = self.username_inp.text().strip()
        password = self.password_inp.text()

        # Tady se program rozhoduje:
        # když některé pole chybí, zobrazí chybu a skončí.
        if not username or not password:
            QMessageBox.warning(self, "Chyba", "Vyplň uživatelské jméno i heslo.")
            return

        # Nejprve ověříme, jestli uživatel vůbec existuje.
        db_user = get_user_by_username(username)
        if not db_user:
            QMessageBox.warning(self, "Chyba", "Tento uživatel neexistuje.")
            return

        # Pak ověříme heslo.
        user = verify_login(username, password)
        if not user:
            QMessageBox.warning(self, "Chyba", "Špatné heslo.")
            return

        # Úspěšné přihlášení: informace pro uživatele.
        QMessageBox.information(self, "OK", f"Přihlášen jako: {user['username']}")

        # Zavoláme callback, aby aplikace mohla otevřít další okno.
        self.on_login_success(user)

        # Login okno už není potřeba, proto ho zavřeme.
        self.close()
