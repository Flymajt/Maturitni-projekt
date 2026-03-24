class QuizSession:
    def __init__(self, questions):
        self.questions = questions
        self.index = 0
        self.score = 0

    def current_question(self):
        if self.index >= len(self.questions):
            return None
        return self.questions[self.index]

    def answer(self, chosen_letter: str):
        """
        chosen_letter: 'A'/'B'/'C'/'D'
        Vrátí True/False podle správnosti a posune na další otázku.
        """
        q = self.current_question()
        if q is None:
            return None

        correct = (chosen_letter.upper() == q["correct_answer"])
        if correct:
            self.score += 1

        self.index += 1
        return correct

    def is_finished(self):
        return self.index >= len(self.questions)

    def total(self):
        return len(self.questions)
