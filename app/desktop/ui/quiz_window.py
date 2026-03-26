import time

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.desktop.db import create_question_report, save_question_attempt, save_result
from app.desktop.quiz_logic import QuizSession


class QuizWindow(QWidget):
    """Herní okno s jednotlivými otázkami a vyhodnocením."""

    def __init__(self, user, category_id, difficulty_id, questions, mode="normal"):
        super().__init__()
        self.setObjectName("RootPage")
        self.setWindowTitle("Quiz - hra")
        self.setMinimumSize(1100, 720)
        self.resize(1220, 780)

        self.user = user
        self.user_id = user["user_id"]
        self.category_id = category_id
        self.difficulty_id = difficulty_id
        self.mode = mode if mode in {"normal", "training"} else "normal"
        self.session = QuizSession(questions)
        self.started_at = None
        self.reported_question_ids = set()
        self.attempt_save_failed = False

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._tick_timer)

        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(14)
        self.layout.setContentsMargins(24, 20, 24, 20)
        self.layout.setAlignment(Qt.AlignTop)

        self._build_header_card()
        self._build_question_card()
        self._build_report_row()

        self.feedback_lbl = QLabel("")
        self.feedback_lbl.setObjectName("Hint")
        self.feedback_lbl.setAlignment(Qt.AlignCenter)
        self.feedback_lbl.setMinimumHeight(36)
        self.feedback_lbl.setMaximumWidth(460)
        self.layout.addWidget(self.feedback_lbl, 0, Qt.AlignHCenter)
        self._set_feedback("Vyber odpověď.", "neutral")

        self.layout.addStretch(1)
        self._build_answers_card()

        self.render_question()

    def _build_header_card(self):
        """Vytvoří horní kartu s názvem, průběhem, skóre a časem."""
        header_card = QFrame()
        header_card.setObjectName("Card")
        header_layout = QVBoxLayout(header_card)
        header_layout.setSpacing(10)
        header_layout.setContentsMargins(22, 18, 22, 16)

        title = QLabel("Interaktivní kvíz")
        title.setObjectName("TitleLabel")
        title.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(title)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(10)

        self.progress_lbl = QLabel("")
        self.progress_lbl.setObjectName("MetaPill")
        self.progress_lbl.setAlignment(Qt.AlignCenter)

        self.score_lbl = QLabel("")
        self.score_lbl.setObjectName("MetaPill")
        self.score_lbl.setAlignment(Qt.AlignCenter)

        mode_label = "Režim: Trénink chyb" if self.mode == "training" else "Režim: Normální kvíz"
        self.mode_lbl = QLabel(mode_label)
        self.mode_lbl.setObjectName("MetaPill")
        self.mode_lbl.setAlignment(Qt.AlignCenter)

        self.time_lbl = QLabel("Čas: 00:00")
        self.time_lbl.setObjectName("MetaPill")
        self.time_lbl.setAlignment(Qt.AlignCenter)

        meta_row.addWidget(self.progress_lbl, 1)
        meta_row.addWidget(self.score_lbl, 1)
        meta_row.addWidget(self.mode_lbl, 1)
        meta_row.addWidget(self.time_lbl, 1)

        header_layout.addLayout(meta_row)
        self.layout.addWidget(header_card)

    def _build_question_card(self):
        """Vytvoří kartu s textem otázky."""
        question_card = QFrame()
        question_card.setObjectName("Card")
        question_layout = QVBoxLayout(question_card)
        question_layout.setContentsMargins(16, 16, 16, 16)

        self.question_lbl = QLabel("")
        self.question_lbl.setObjectName("QuestionText")
        self.question_lbl.setWordWrap(True)
        self.question_lbl.setAlignment(Qt.AlignCenter)

        question_layout.addWidget(self.question_lbl)
        self.layout.addWidget(question_card)

    def _build_report_row(self):
        """Vytvoří řádek pod otázkou s tlačítkem nahlášení vpravo."""
        report_row = QHBoxLayout()
        report_row.setContentsMargins(0, 0, 0, 0)
        report_row.addStretch(1)

        self.report_btn = QPushButton("Nahlásit otázku")
        self.report_btn.setObjectName("ReportButton")
        self.report_btn.setFixedHeight(34)
        self.report_btn.setMinimumWidth(142)
        self.report_btn.clicked.connect(self.report_current_question)
        self.report_btn.setCursor(Qt.PointingHandCursor)

        report_row.addWidget(self.report_btn, 0, Qt.AlignRight)
        self.layout.addLayout(report_row)

    def _build_answers_card(self):
        """Vytvoří kartu s odpověďmi A-D."""
        answers_card = QFrame()
        answers_card.setObjectName("Card")
        answer_grid = QGridLayout(answers_card)
        answer_grid.setContentsMargins(14, 14, 14, 14)
        answer_grid.setHorizontalSpacing(12)
        answer_grid.setVerticalSpacing(12)

        self.btn_a = QPushButton("")
        self.btn_b = QPushButton("")
        self.btn_c = QPushButton("")
        self.btn_d = QPushButton("")

        for btn in (self.btn_a, self.btn_b, self.btn_c, self.btn_d):
            btn.setObjectName("AnswerButton")
            btn.setMinimumHeight(72)
            btn.setCursor(Qt.PointingHandCursor)

        self.btn_a.clicked.connect(lambda: self.choose("A"))
        self.btn_b.clicked.connect(lambda: self.choose("B"))
        self.btn_c.clicked.connect(lambda: self.choose("C"))
        self.btn_d.clicked.connect(lambda: self.choose("D"))

        answer_grid.addWidget(self.btn_a, 0, 0)
        answer_grid.addWidget(self.btn_b, 0, 1)
        answer_grid.addWidget(self.btn_c, 1, 0)
        answer_grid.addWidget(self.btn_d, 1, 1)

        self.layout.addWidget(answers_card)

    def render_question(self):
        """Vykreslí aktuální otázku nebo ukončí kvíz, pokud už nejsou další."""
        q = self.session.current_question()
        if q is None:
            self.finish()
            return

        current_number = self.session.index + 1
        total = self.session.total()

        if current_number == 1 and self.started_at is None:
            # Speedrun: čas měříme od zobrazení první otázky.
            self.started_at = time.monotonic()
            self.timer.start()

        self.progress_lbl.setText(f"Otázka {current_number} / {total}")
        self.score_lbl.setText(f"Skóre: {self.session.score}/{total}")
        self.question_lbl.setText(q["question_text"])

        self.btn_a.setText(f"A) {q['answer_a']}")
        self.btn_b.setText(f"B) {q['answer_b']}")
        self.btn_c.setText(f"C) {q['answer_c']}")
        self.btn_d.setText(f"D) {q['answer_d']}")

    def choose(self, letter):
        """Zpracuje odpověď uživatele a posune se dál."""
        current_question = self.session.current_question()
        if current_question is None:
            return

        result = self.session.answer(letter)
        self._save_question_attempt(current_question, result)

        if result is True:
            self._set_feedback("Správná odpověď", "correct")
        elif result is False:
            self._set_feedback("Špatná odpověď", "wrong")

        if self.session.is_finished():
            self.finish()
        else:
            self.render_question()

    def finish(self):
        """Uloží výsledek do DB a nabídne nový test nebo zavření aplikace."""
        if self.timer.isActive():
            self.timer.stop()

        score = self.session.score
        total = self.session.total()
        duration_seconds = None
        if self.started_at is not None:
            elapsed = time.monotonic() - self.started_at
            duration_seconds = max(1, int(round(elapsed)))

        saved_to_results = False
        if self.mode == "normal":
            save_result(
                user_id=self.user_id,
                category_id=self.category_id,
                difficulty_id=self.difficulty_id,
                score=score,
                total_questions=total,
                duration_seconds=duration_seconds,
            )
            saved_to_results = True

        time_text = self._format_duration(duration_seconds) if duration_seconds is not None else "-"
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle("Konec kvízu")
        save_note = (
            "Uloženo do databáze."
            if saved_to_results
            else "Tréninkový režim: výsledek se neukládá do leaderboardu."
        )
        box.setText(f"Výsledek: {score}/{total}\nČas: {time_text}\n{save_note}")
        box.setInformativeText("Chceš spustit nový test, nebo aplikaci zavřít?")

        play_again_btn = box.addButton("Nový test", QMessageBox.AcceptRole)
        close_btn = box.addButton("Zavřít aplikaci", QMessageBox.RejectRole)
        box.setDefaultButton(play_again_btn)
        box.exec_()

        if box.clickedButton() == play_again_btn:
            self._open_start_window()
            self.close()
            return

        if box.clickedButton() == close_btn:
            QApplication.instance().quit()
            return

        # Fallback - pokud uživatel dialog zavře křížkem, appku ukončíme.
        QApplication.instance().quit()

    def report_current_question(self):
        """Umožní hráči nahlásit problém s aktuální otázkou."""
        question = self.session.current_question()
        if question is None:
            QMessageBox.information(self, "Nahlášení otázky", "Aktuálně není otevřená žádná otázka.")
            return

        question_id = question["question_id"]
        if question_id in self.reported_question_ids:
            QMessageBox.information(self, "Nahlášení otázky", "Tuto otázku už jsi v tomto kvízu nahlásil.")
            return

        reasons = [
            "Špatná správná odpověď",
            "Nejasné zadání",
            "Překlep nebo gramatika",
            "Duplicitní otázka",
            "Jiný problém",
        ]
        reason, ok_reason = QInputDialog.getItem(
            self,
            "Nahlásit otázku",
            "Důvod hlášení:",
            reasons,
            0,
            False,
        )
        if not ok_reason:
            return

        note, ok_note = QInputDialog.getMultiLineText(
            self,
            "Nahlásit otázku",
            "Detail (volitelné):",
            "",
        )
        if not ok_note:
            return

        try:
            create_question_report(
                question_id=question_id,
                user_id=self.user_id,
                reason=reason,
                note=note,
            )
            self.reported_question_ids.add(question_id)
            QMessageBox.information(
                self,
                "Nahlášení otázky",
                "Děkujeme, hlášení bylo odesláno adminovi ke kontrole.",
            )
        except Exception as exc:
            QMessageBox.warning(self, "Nahlášení otázky", f"Hlášení se nepodařilo uložit: {exc}")

    def _tick_timer(self):
        """Aktualizuje zobrazení průběžného času v horní kartě."""
        if self.started_at is None:
            return
        elapsed = max(0, int(time.monotonic() - self.started_at))
        self.time_lbl.setText(f"Čas: {self._format_duration(elapsed)}")

    def _set_feedback(self, text, state):
        """Zobrazí stavovou zprávu s barevným zvýrazněním výsledku odpovědi."""
        self.feedback_lbl.setText(text)

        styles = {
            "neutral": (
                "QLabel {"
                "background-color: rgba(255, 255, 255, 0.66);"
                "color: #09637E;"
                "border: 1px solid rgba(8, 131, 149, 0.35);"
                "border-radius: 10px;"
                "padding: 6px 12px;"
                "font-weight: 600;"
                "}"
            ),
            "correct": (
                "QLabel {"
                "background-color: #DDF7E3;"
                "color: #1F6B3A;"
                "border: 1px solid #9BD8AD;"
                "border-radius: 10px;"
                "padding: 6px 12px;"
                "font-weight: 700;"
                "}"
            ),
            "wrong": (
                "QLabel {"
                "background-color: #FDE0E0;"
                "color: #A63A3A;"
                "border: 1px solid #E6A1A1;"
                "border-radius: 10px;"
                "padding: 6px 12px;"
                "font-weight: 700;"
                "}"
            ),
        }

        self.feedback_lbl.setStyleSheet(styles.get(state, styles["neutral"]))

    def _open_start_window(self):
        """Otevře znovu okno výběru kategorie/obtížnosti pro další kvíz."""
        # Lokální import zabrání kruhovému importu mezi start_window a quiz_window.
        from app.desktop.ui.start_window import StartWindow

        self.start_window = StartWindow(user=self.user)
        self.start_window.show()

    def _save_question_attempt(self, question: dict, answer_result):
        """Uloží pokus na otázce. Při chybě neblokuje průběh kvízu."""
        if answer_result not in (True, False):
            return
        try:
            save_question_attempt(
                user_id=self.user_id,
                question_id=question["question_id"],
                category_id=self.category_id,
                difficulty_id=self.difficulty_id,
                is_correct=answer_result,
                mode=self.mode,
            )
        except Exception as exc:
            if not self.attempt_save_failed:
                QMessageBox.warning(
                    self,
                    "Upozornění",
                    f"Nepodařilo se uložit odpověď do historie tréninku: {exc}",
                )
                self.attempt_save_failed = True

    @staticmethod
    def _format_duration(seconds):
        """Převede sekundy na čitelný formát mm:ss nebo hh:mm:ss."""
        if seconds is None:
            return "-"
        hours, rest = divmod(int(seconds), 3600)
        minutes, secs = divmod(rest, 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"
