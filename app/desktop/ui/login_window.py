from PyQt5.QtCore import QEvent, Qt
from PyQt5.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
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

        # Ikona oka přímo uvnitř inputu (vpravo), stejně jako na webu.
        self._password_visible = False
        self._password_icon_hovered = False
        self.password_toggle_action = self.password_inp.addAction(
            self._eye_icon(slashed=True, hovered=False),
            QLineEdit.TrailingPosition,
        )
        self.password_toggle_action.triggered.connect(self._toggle_password_visibility)
        self.password_inp.setTextMargins(0, 0, 8, 0)
        self.password_inp.setMouseTracking(True)
        self.password_inp.installEventFilter(self)

        layout.addWidget(self.password_inp)
        self._set_password_visible(False)

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

    def _eye_icon(self, slashed: bool = False, hovered: bool = False) -> QIcon:
        # Vytvoří jednoduchou ikonu oka; při `slashed=True` přidá přeškrtnutí.
        size = 20
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)

        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)

        if hovered:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#DDECEF"))
            painter.drawRoundedRect(0, 0, size, size, 6, 6)

        eye_color = QColor("#09637E" if hovered else "#088395")
        pen = QPen(eye_color)
        pen.setWidth(2)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(3, 7, 13, 6)

        painter.setPen(Qt.NoPen)
        painter.setBrush(eye_color)
        painter.drawEllipse(8, 9, 3, 3)

        if slashed:
            painter.setPen(pen)
            painter.drawLine(4, 15, 16, 5)

        painter.end()
        return QIcon(pix)

    def _is_over_password_toggle(self, pos) -> bool:
        # Pravý okraj inputu vyhrazujeme pro ikonku oka.
        icon_zone_width = 30
        return pos.x() >= (self.password_inp.width() - icon_zone_width)

    def _refresh_password_toggle_icon(self):
        self.password_toggle_action.setIcon(
            self._eye_icon(
                slashed=not self._password_visible,
                hovered=self._password_icon_hovered,
            )
        )

    def _toggle_password_visibility(self):
        self._set_password_visible(not self._password_visible)

    def _set_password_visible(self, visible: bool):
        # True = zobrazit heslo, False = skrýt heslo.
        self._password_visible = visible
        self.password_inp.setEchoMode(QLineEdit.Normal if visible else QLineEdit.Password)
        self._refresh_password_toggle_icon()
        self.password_toggle_action.setToolTip("Skrýt heslo" if visible else "Zobrazit heslo")

    def eventFilter(self, obj, event):
        if obj is self.password_inp:
            if event.type() == QEvent.MouseMove:
                hovered = self._is_over_password_toggle(event.pos())
                if hovered != self._password_icon_hovered:
                    self._password_icon_hovered = hovered
                    self._refresh_password_toggle_icon()
                self.password_inp.setCursor(Qt.PointingHandCursor if hovered else Qt.IBeamCursor)
            elif event.type() == QEvent.Leave:
                if self._password_icon_hovered:
                    self._password_icon_hovered = False
                    self._refresh_password_toggle_icon()
                self.password_inp.setCursor(Qt.IBeamCursor)
        return super().eventFilter(obj, event)

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
