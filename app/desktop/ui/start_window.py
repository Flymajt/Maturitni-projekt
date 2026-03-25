from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.desktop.db import get_categories, get_difficulties, get_questions
from app.desktop.ui.quiz_window import QuizWindow


class StartWindow(QWidget):
    """Okno pro výběr kategorie a obtížnosti před startem kvízu."""

    def __init__(self, user):
        """user = {'user_id': int, 'username': str, 'role': str}"""
        super().__init__()
        self.setObjectName("RootPage")
        self.user = user
        self.setWindowTitle(f"Quiz - výběr (uživatel: {user['username']})")
        self.setMinimumSize(840, 620)
        self.resize(940, 680)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(30, 24, 30, 24)
        root_layout.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setObjectName("Card")
        card.setMaximumWidth(760)

        layout = QVBoxLayout(card)
        layout.setSpacing(16)
        layout.setContentsMargins(32, 28, 32, 26)

        title = QLabel("Příprava nové hry")
        title.setObjectName("TitleLabel")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        info = QLabel(f"Přihlášený hráč: {user['username']} • Vyber kategorii a obtížnost")
        info.setAlignment(Qt.AlignCenter)
        info.setObjectName("Subtitle")
        layout.addWidget(info)

        form = QFormLayout()
        form.setFormAlignment(Qt.AlignTop)
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form.setHorizontalSpacing(20)
        form.setVerticalSpacing(12)

        self.category_cb = QComboBox()
        self.category_cb.setMinimumHeight(46)
        self.categories = get_categories()
        self.category_name_by_id = {}
        for c in self.categories:
            self.category_cb.addItem(c["name"], c["category_id"])
            self.category_name_by_id[c["category_id"]] = c["name"]

        self.difficulty_cb = QComboBox()
        self.difficulty_cb.setMinimumHeight(46)
        self.difficulties = get_difficulties()
        self.difficulty_name_by_id = {}
        for d in self.difficulties:
            self.difficulty_cb.addItem(d["name"], d["difficulty_id"])
            self.difficulty_name_by_id[d["difficulty_id"]] = d["name"]

        form.addRow(QLabel("Kategorie"), self.category_cb)
        form.addRow(QLabel("Obtížnost"), self.difficulty_cb)
        layout.addLayout(form)

        self.start_btn = QPushButton("Start kvízu")
        self.start_btn.setObjectName("PrimaryButton")
        self.start_btn.setMinimumHeight(54)
        self.start_btn.clicked.connect(self.start_quiz)
        layout.addWidget(self.start_btn)

        root_layout.addWidget(card, 0, Qt.AlignCenter)

    def start_quiz(self):
        """Načte otázky dle výběru a otevře herní okno."""
        category_id = self.category_cb.currentData()
        difficulty_id = self.difficulty_cb.currentData()

        category_name = self.category_name_by_id.get(category_id, "")
        difficulty_name = self.difficulty_name_by_id.get(difficulty_id, "")

        # Specifický počet otázek platí jen pro aktuální 3 základní témata.
        if category_name in {"IT", "Sport", "Historie"}:
            limit = {"Easy": 3, "Medium": 5, "Hard": 7}.get(difficulty_name, 5)
        else:
            # Budoucí kategorie nemají pevný počet podle obtížnosti.
            limit = 5

        questions = get_questions(category_id, difficulty_id, limit=limit)
        if not questions:
            QMessageBox.warning(self, "Chyba", "Pro tento výběr nejsou otázky.")
            return

        self.quiz_window = QuizWindow(
            user=self.user,
            category_id=category_id,
            difficulty_id=difficulty_id,
            questions=questions,
        )
        self.quiz_window.show()
        self.close()
