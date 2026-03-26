from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.desktop.quiz_logic import QuizSession


def _sample_questions():
    return [
        {"question_text": "Q1", "correct_answer": "A"},
        {"question_text": "Q2", "correct_answer": "C"},
    ]


def test_current_question_returns_expected_item():
    session = QuizSession(_sample_questions())

    assert session.current_question()["question_text"] == "Q1"
    session.index = 2
    assert session.current_question() is None


def test_answer_updates_score_and_index():
    session = QuizSession(_sample_questions())

    assert session.answer("a") is True
    assert session.score == 1
    assert session.index == 1

    assert session.answer("B") is False
    assert session.score == 1
    assert session.index == 2


def test_is_finished_matches_quiz_progress():
    session = QuizSession(_sample_questions())

    assert session.is_finished() is False
    session.answer("A")
    assert session.is_finished() is False
    session.answer("C")
    assert session.is_finished() is True


if __name__ == "__main__":
    test_current_question_returns_expected_item()
    test_answer_updates_score_and_index()
    test_is_finished_matches_quiz_progress()
    print("All assert tests passed.")
