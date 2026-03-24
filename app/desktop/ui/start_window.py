from PyQt5.QtWidgets import QWidget, QLabel, QPushButton, QComboBox, QVBoxLayout, QMessageBox
from app.desktop.db import get_categories, get_difficulties, get_questions
from app.desktop.ui.quiz_window import QuizWindow


class StartWindow(QWidget):
    def __init__(self, user):
        """
        user = {"user_id": int, "username": str, "role": str}
        """
        super().__init__()
        self.user = user
        self.setWindowTitle(f"Quiz – výběr (uživatel: {user['username']})")

        layout = QVBoxLayout()

        layout.addWidget(QLabel("Kategorie:"))
        self.category_cb = QComboBox()
        self.categories = get_categories()
        for c in self.categories:
            self.category_cb.addItem(c["name"], c["category_id"])
        layout.addWidget(self.category_cb)

        layout.addWidget(QLabel("Obtížnost:"))
        self.difficulty_cb = QComboBox()
        self.difficulties = get_difficulties()
        for d in self.difficulties:
            self.difficulty_cb.addItem(d["name"], d["difficulty_id"])
        layout.addWidget(self.difficulty_cb)

        self.start_btn = QPushButton("Start kvízu")
        self.start_btn.clicked.connect(self.start_quiz)
        layout.addWidget(self.start_btn)

        self.setLayout(layout)

    def start_quiz(self):
        category_id = self.category_cb.currentData()
        difficulty_id = self.difficulty_cb.currentData()

        questions = get_questions(category_id, difficulty_id, limit=5)
        if not questions:
            QMessageBox.warning(self, "Chyba", "Pro tento výběr nejsou otázky.")
            return

        self.quiz_window = QuizWindow(
            user_id=self.user["user_id"],
            category_id=category_id,
            difficulty_id=difficulty_id,
            questions=questions
        )
        self.quiz_window.show()
        self.close()
