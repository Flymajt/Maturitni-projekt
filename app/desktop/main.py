import sys

from PyQt5.QtWidgets import QApplication

# Přihlašovací okno.
# Soubor: `app/desktop/ui/login_window.py`.
from app.desktop.ui.login_window import LoginWindow
# Okno výběru kategorie/obtížnosti.
# Soubor: `app/desktop/ui/start_window.py`.
from app.desktop.ui.start_window import StartWindow


# Globální vizuální styl desktop aplikace (QSS podobné CSS).
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

QFrame#InfoCard {
    background-color: rgba(255, 255, 255, 0.9);
    border: 1px solid #7AB2B2;
    border-radius: 12px;
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

QLabel#InfoTitle {
    color: #09637E;
    font-size: 14px;
    font-weight: 800;
    margin-top: 2px;
    background-color: transparent;
    border: none;
    padding: 0;
}

QLabel#InfoTag {
    color: #EBF4F6;
    background-color: #09637E;
    border-radius: 9px;
    padding: 4px 10px;
    font-size: 12px;
    font-weight: 800;
}

QLabel#InfoText {
    color: #088395;
    font-size: 13px;
    font-weight: 600;
    background-color: transparent;
    border: none;
    padding: 0;
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

QPushButton#ReportButton {
    font-size: 14px;
    font-weight: 700;
    padding: 7px 10px;
    border-radius: 10px;
    background-color: #0A6F8E;
}

QPushButton#ReportButton:hover {
    background-color: #088395;
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


# Třída, která řídí tok aplikace mezi jednotlivými okny.
class AppController:
    def __init__(self):
        # Aktuálně přihlášený uživatel (po loginu).
        self.user = None
        # Reference na start okno, aby objekt nezanikl.
        self.start_window = None
        # Reference na login okno.
        self.login_window = None

    def run(self):
        # Vytvoříme login okno a předáme callback, který se zavolá při úspěšném loginu.
        self.login_window = LoginWindow(on_login_success=self.on_login_success)
        self.login_window.show()

    def on_login_success(self, user):
        # Uložíme data přihlášeného uživatele.
        self.user = user

        # Otevřeme start okno (výběr kategorie/obtížnosti/režimu).
        self.start_window = StartWindow(user=self.user)
        self.start_window.show()


# Tento blok se spustí jen při přímém spuštění souboru `python .../main.py`.
if __name__ == "__main__":
    # Vytvoření Qt aplikace.
    app = QApplication(sys.argv)

    # Nastavení globálního motivu (QSS) pro všechna okna.
    app.setStyleSheet(DESKTOP_THEME)

    # Inicializace řadiče aplikace.
    controller = AppController()
    controller.run()

    # Spuštění hlavní smyčky GUI.
    sys.exit(app.exec_())
