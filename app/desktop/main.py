import sys
from PyQt5.QtWidgets import QApplication

# Import oken PyQt
# LoginWindow – okno pro přihlášení / registraci uživatele
# StartWindow – hlavní menu kvízu (výběr tématu a obtížnosti)
from app.desktop.ui.login_window import LoginWindow
from app.desktop.ui.start_window import StartWindow


class AppController:
    """
    Řídicí třída celé desktopové aplikace.
    Stará se o přechod mezi okny (login -> start kvízu)
    a uchovává informace o přihlášeném uživateli.
    """
    def __init__(self):
        self.user = None           # přihlášený uživatel (dict z DB)
        self.start_window = None   # okno výběru kvízu
        self.login_window = None   # okno přihlášení

    def run(self):
        """
        Spuštění aplikace – zobrazí přihlašovací okno.
        """
        self.login_window = LoginWindow(on_login_success=self.on_login_success)
        self.login_window.show()

    def on_login_success(self, user):
        """
        Callback volaný po úspěšném přihlášení.
        Uloží přihlášeného uživatele a otevře hlavní okno kvízu.
        """
        self.user = user
        self.start_window = StartWindow(user=self.user)
        self.start_window.show()


# Vstupní bod aplikace
if __name__ == "__main__":
    # Vytvoření Qt aplikace
    app = QApplication(sys.argv)

    # Inicializace řídicí logiky aplikace
    controller = AppController()
    controller.run()

    # Spuštění hlavní smyčky aplikace
    sys.exit(app.exec_())
