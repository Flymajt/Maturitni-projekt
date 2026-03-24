from PyQt5.QtWidgets import QWidget, QLabel, QPushButton, QVBoxLayout, QMessageBox
from app.desktop.quiz_logic import QuizSession
from app.desktop.db import save_result


class QuizWindow(QWidget):
    def __init__(self, user_id, category_id, difficulty_id, questions):
        super().__init__()
        self.setWindowTitle("Quiz – hra")

        self.user_id = user_id
        self.category_id = category_id
        self.difficulty_id = difficulty_id

        self.session = QuizSession(questions)

        self.layout = QVBoxLayout()

        self.question_lbl = QLabel("")
        self.layout.addWidget(self.question_lbl)

        self.btn_a = QPushButton("")
        self.btn_b = QPushButton("")
        self.btn_c = QPushButton("")
        self.btn_d = QPushButton("")

        self.btn_a.clicked.connect(lambda: self.choose("A"))
        self.btn_b.clicked.connect(lambda: self.choose("B"))
        self.btn_c.clicked.connect(lambda: self.choose("C"))
        self.btn_d.clicked.connect(lambda: self.choose("D"))

        self.layout.addWidget(self.btn_a)
        self.layout.addWidget(self.btn_b)
        self.layout.addWidget(self.btn_c)
        self.layout.addWidget(self.btn_d)

        self.setLayout(self.layout)

        self.render_question()

    def render_question(self):
        q = self.session.current_question()
        if q is None:
            self.finish()
            return

        self.question_lbl.setText(f"{self.session.index + 1}/{self.session.total()} – {q['question_text']}")
        self.btn_a.setText(f"A) {q['answer_a']}")
        self.btn_b.setText(f"B) {q['answer_b']}")
        self.btn_c.setText(f"C) {q['answer_c']}")
        self.btn_d.setText(f"D) {q['answer_d']}")

    def choose(self, letter):
        result = self.session.answer(letter)

        if result is True:
            QMessageBox.information(self, "Správně", "✅ Správná odpověď!")
        elif result is False:
            QMessageBox.information(self, "Špatně", "❌ Špatná odpověď.")

        if self.session.is_finished():
            self.finish()
        else:
            self.render_question()

    def finish(self):
        score = self.session.score
        total = self.session.total()

        # uložení do DB
        save_result(
            user_id=self.user_id,
            category_id=self.category_id,
            difficulty_id=self.difficulty_id,
            score=score,
            total_questions=total
        )

        QMessageBox.information(self, "Konec", f"Výsledek: {score}/{total}\nUloženo do databáze.")
        self.close()
