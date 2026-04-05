# Třída `QuizSession` drží stav právě hraného kvízu.
# Neřeší vzhled okna, jen logiku: otázky, skóre a pořadí.
class QuizSession:
    def __init__(self, questions):
        # `questions` je seznam všech otázek pro aktuální hru.
        self.questions = questions
        # `index` říká, na které otázce právě jsme (0 = první otázka).
        self.index = 0
        # `score` je počet správných odpovědí.
        self.score = 0

    def current_question(self):
        # Vrátí otázku na pozici `self.index`.
        # Tady se program rozhoduje:
        # pokud už jsme za koncem seznamu, vrátí `None`.
        if self.index >= len(self.questions):
            return None
        return self.questions[self.index]

    def answer(self, chosen_letter: str):
        # Zpracuje jednu odpověď hráče.
        q = self.current_question()
        # Když už žádná otázka není, nemáme co vyhodnocovat.
        if q is None:
            return None

        # Odpověď porovnáváme bez ohledu na velikost písmen (A/a).
        correct = chosen_letter.upper() == q["correct_answer"]
        # Jen při správné odpovědi zvýšíme skóre.
        if correct:
            self.score += 1

        # Po odpovědi se vždy posuneme na další otázku.
        self.index += 1
        # Vrátíme informaci, jestli byla odpověď správná.
        return correct

    def is_finished(self):
        # Vrací True, když už nejsou žádné další otázky.
        return self.index >= len(self.questions)

    def total(self):
        # Celkový počet otázek v tomto kvízu.
        return len(self.questions)
