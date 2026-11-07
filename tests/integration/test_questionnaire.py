"""
Integration tests for screening questionnaire resolution logic.
"""
import tempfile
from pathlib import Path

from backend.services.questionnaire_service import QuestionnaireService


def test_questionnaire_common_qa_matching():
    with tempfile.TemporaryDirectory() as tmp_dir:
        cache_file = str(Path(tmp_dir) / "qa_cache.json")
        qa_service = QuestionnaireService(cache_file=cache_file)

        mock_questions = [
            {
                "questionId": "q1",
                "questionName": "What is your current CTC?",
                "questionType": "text box",
                "answerOption": {},
            },
            {
                "questionId": "q2",
                "questionName": "Are you comfortable with night shifts?",
                "questionType": "radio",
                "answerOption": {"opt_yes": "Yes", "opt_no": "No"},
            },
            {
                "questionId": "q3",
                "questionName": "Are you willing to relocate to Bangalore?",
                "questionType": "radio",
                "answerOption": {"opt_y": "Yes, completely", "opt_n": "No"},
            },
        ]

        answers = qa_service.answer(mock_questions)
        assert "q1" in answers
        assert answers["q1"] == "5"  # default current CTC

        assert "q2" in answers
        assert answers["q2"] == ["opt_no"]  # night shift = No

        assert "q3" in answers
        assert answers["q3"] == ["opt_y"]  # relocate = Yes


def test_questionnaire_cache_persistence():
    with tempfile.TemporaryDirectory() as tmp_dir:
        cache_file = str(Path(tmp_dir) / "qa_cache.json")
        qa_service = QuestionnaireService(cache_file=cache_file)

        # Pre-seed cache
        qa_service.cache["custom proprietary test question"] = "Specific Custom Answer"
        qa_service.cache_repo.save(qa_service.cache)

        new_service = QuestionnaireService(cache_file=cache_file)
        mock_questions = [
            {
                "questionId": "q_custom",
                "questionName": "custom proprietary test question",
                "questionType": "text box",
                "answerOption": {},
            }
        ]
        answers = new_service.answer(mock_questions)
        assert answers["q_custom"] == "Specific Custom Answer"
