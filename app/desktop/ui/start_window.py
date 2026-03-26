from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.desktop.db import get_categories, get_difficulties, get_questions, get_training_questions
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

        info = QLabel(f"Přihlášený hráč: {user['username']} • Vyber kategorii, obtížnost a režim")
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
        self.category_description_by_id = {}
        for c in self.categories:
            self.category_cb.addItem(c["name"], c["category_id"])
            self.category_name_by_id[c["category_id"]] = c["name"]
            self.category_description_by_id[c["category_id"]] = (c.get("description") or "").strip()
        self.category_cb.setCurrentIndex(0)

        self.difficulty_cb = QComboBox()
        self.difficulty_cb.setMinimumHeight(46)
        self.difficulties = get_difficulties()
        self.difficulty_name_by_id = {}
        for d in self.difficulties:
            self.difficulty_cb.addItem(d["name"], d["difficulty_id"])
            self.difficulty_name_by_id[d["difficulty_id"]] = d["name"]

        self.mode_cb = QComboBox()
        self.mode_cb.setMinimumHeight(46)
        self.mode_cb.addItem("Normální kvíz", "normal")
        self.mode_cb.addItem("Trénink chyb", "training")

        form.addRow(QLabel("Kategorie"), self.category_cb)
        form.addRow(QLabel("Obtížnost"), self.difficulty_cb)
        form.addRow(QLabel("Režim"), self.mode_cb)
        layout.addLayout(form)

        category_info_card = QFrame()
        category_info_card.setObjectName("InfoCard")
        category_info_layout = QVBoxLayout(category_info_card)
        category_info_layout.setContentsMargins(14, 12, 14, 12)
        category_info_layout.setSpacing(8)

        category_info_head = QHBoxLayout()
        category_info_head.setContentsMargins(0, 0, 0, 0)
        category_info_head.setSpacing(8)

        info_title = QLabel("Popis vybrané kategorie")
        info_title.setObjectName("InfoTitle")
        category_info_head.addWidget(info_title)
        category_info_head.addStretch(1)

        self.category_selected_lbl = QLabel("")
        self.category_selected_lbl.setObjectName("InfoTag")
        category_info_head.addWidget(self.category_selected_lbl)
        category_info_layout.addLayout(category_info_head)

        self.category_description_lbl = QLabel("")
        self.category_description_lbl.setObjectName("InfoText")
        self.category_description_lbl.setWordWrap(True)
        category_info_layout.addWidget(self.category_description_lbl)

        layout.addWidget(category_info_card)

        self.start_btn = QPushButton("Start kvízu")
        self.start_btn.setObjectName("PrimaryButton")
        self.start_btn.setMinimumHeight(54)
        self.start_btn.clicked.connect(self.start_quiz)
        layout.addWidget(self.start_btn)

        root_layout.addWidget(card, 0, Qt.AlignCenter)
        self.category_cb.currentIndexChanged.connect(self._update_category_info)
        self._update_category_info()

    def _update_category_info(self):
        """Aktualizuje panel s popisem vybrané kategorie."""
        category_id = self.category_cb.currentData()
        category_name = self.category_name_by_id.get(category_id, "")
        description = self.category_description_by_id.get(category_id, "")
        self.category_selected_lbl.setText(category_name or "-")

        self.category_description_lbl.setText(
            description
            if category_id is not None and description
            else (
                "Pro tuto kategorii zatím není vyplněný popis."
                if category_id is not None
                else "-"
            )
        )

    def start_quiz(self):
        """Načte otázky dle výběru a otevře herní okno."""
        category_id = self.category_cb.currentData()
        difficulty_id = self.difficulty_cb.currentData()
        mode = self.mode_cb.currentData()

        category_name = self.category_name_by_id.get(category_id, "")
        difficulty_name = self.difficulty_name_by_id.get(difficulty_id, "")

        # Specifický počet otázek platí jen pro aktuální 3 základní témata.
        if category_name in {"IT", "Sport", "Historie"}:
            limit = {"Easy": 3, "Medium": 5, "Hard": 7}.get(difficulty_name, 5)
        else:
            # Budoucí kategorie nemají pevný počet podle obtížnosti.
            limit = 5

        if mode == "training":
            questions = get_training_questions(
                user_id=self.user["user_id"],
                category_id=category_id,
                difficulty_id=difficulty_id,
                limit=limit,
            )
            if not questions:
                QMessageBox.information(
                    self,
                    "Trénink chyb",
                    "Pro tento výběr zatím nemáš žádné špatně zodpovězené otázky.\n"
                    "Nejdřív si zahraj normální kvíz, a pak se sem vrať.",
                )
                return
        else:
            questions = get_questions(category_id, difficulty_id, limit=limit)

        if not questions:
            QMessageBox.warning(self, "Chyba", "Pro tento výběr nejsou otázky.")
            return

        self.quiz_window = QuizWindow(
            user=self.user,
            category_id=category_id,
            difficulty_id=difficulty_id,
            questions=questions,
            mode=mode,
        )
        self.quiz_window.show()
        self.close()
