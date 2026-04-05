from pathlib import Path
import sys

# Pridame koren projektu do `sys.path`, aby slo importovat moduly z `app/...`
# i kdyz test poustime primo jako soubor.
# `Path(__file__)` je cesta k tomuto souboru:
#  Projekt\tests\test_quiz_logic.py`
# `.resolve().parents[1]` se posune o 2 urovene vys:
# `Projekt`
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Import tridy `QuizSession` ze souboru:
# `Projekt\app\desktop\quiz_logic.py`
from app.desktop.quiz_logic import QuizSession


def _sample_questions():
    # Pomocna funkce vraci dve jednoduche testovaci otazky.
    
    return [
        {"question_text": "Q1", "correct_answer": "A"},
        {"question_text": "Q2", "correct_answer": "C"},
    ]


def test_current_question_returns_expected_item():
    # Vytvorime novou quiz session se 2 otazkami.
    session = QuizSession(_sample_questions())

    # Na zacatku musi byt "aktualni otazka" prvni polozka.
    assert session.current_question()["question_text"] == "Q1"
    # Rucne nastavime index za konec seznamu otazek.
    session.index = 2
    # Kdyz jsme za koncem, aktualni otazka uz nema existovat -> None.
    assert session.current_question() is None


def test_answer_updates_score_and_index():
    # Nova session opet startuje na prvni otazce, score = 0, index = 0.
    session = QuizSession(_sample_questions())

    # Odpovime "a" (male pismeno) na otazku, kde je spravne "A".
    # Test tim overuje i to, ze logika je case-insensitive.
    assert session.answer("a") is True
    # Po spravne odpovedi se score zvysi o 1.
    assert session.score == 1
    # A index se posune na dalsi otazku.
    assert session.index == 1

    # Ted odpovime "B" na druhou otazku, kde je spravne "C".
    assert session.answer("B") is False
    # Score se po spatne odpovedi nesmi zmenit.
    assert session.score == 1
    # Index se ale i tak posune dal (na konec kvizu).
    assert session.index == 2


def test_is_finished_matches_quiz_progress():
    # Nova session: pred zodpovezenim otazek neni hotovo.
    session = QuizSession(_sample_questions())

    assert session.is_finished() is False
    # Po prvni odpovedi je stale jedna otazka zbyvajici.
    session.answer("A")
    assert session.is_finished() is False
    # Po druhe odpovedi uz mame zodpovezeno vse.
    session.answer("C")
    assert session.is_finished() is True


if __name__ == "__main__":
    # Tento blok se spusti jen pri primem spusteni:
    test_current_question_returns_expected_item()
    test_answer_updates_score_and_index()
    test_is_finished_matches_quiz_progress()
    print("All assert tests passed.")
