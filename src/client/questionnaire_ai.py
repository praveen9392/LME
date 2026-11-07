"""
Backward-compatibility adapter for QuestionnaireAI.
"""
from __future__ import annotations

from backend.services.questionnaire_service import QuestionnaireService

# Alias QuestionnaireAI to QuestionnaireService
QuestionnaireAI = QuestionnaireService
