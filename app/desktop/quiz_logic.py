class QuizSession:
    """Udržuje stav probíhajícího kvízu (otázka, skóre, pořadí)."""

    def __init__(self, questions):
        self.questions = questions
        self.index = 0
        self.score = 0

    def current_question(self):
        """Vrátí aktuální otázku, nebo None pokud je kvíz u konce."""
        if self.index >= len(self.questions):
            return None
        return self.questions[self.index]

    def answer(self, chosen_letter: str):
        """Vyhodnotí odpověď, aktualizuje skóre a posune se na další otázku."""
        q = self.current_question()
        if q is None:
            return None

        correct = chosen_letter.upper() == q["correct_answer"]
        if correct:
            self.score += 1

        self.index += 1
        return correct

    def is_finished(self):
        """Vrací True, pokud už nejsou žádné další otázky."""
        return self.index >= len(self.questions)

    def total(self):
        """Celkový počet otázek v aktuálním sezení."""
        return len(self.questions)
