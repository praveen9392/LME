"""
Questionnaire Answering Service.
Resolves employer screening questions using: Cache -> Common Q&A -> Batched AI -> Heuristics.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from backend.core.config import ConfigManager
from backend.core.logging import get_logger
from backend.integrations.ai.client import AIClient
from backend.storage.cache_repo import JsonCache

logger = get_logger(__name__)


class QuestionnaireService:
    """Answers Naukri screening questionnaires with tiered fallback resolution."""

    def __init__(
        self,
        config_manager: Optional[ConfigManager] = None,
        ai_client: Optional[AIClient] = None,
        cache_file: str = "qa_cache.json",
    ) -> None:
        self.cfg = config_manager or ConfigManager()
        self.ai = ai_client or AIClient(self.cfg)
        self.cache_repo = JsonCache(cache_file)
        self.cache: Dict[str, Any] = self.cache_repo.load()
        self.profile = self.cfg.config.get("profile", {})
        self.common_qa = self._build_common_qa()

    @staticmethod
    def _norm(text: str) -> str:
        """Lowercases and strips punctuation for fuzzy cache key normalization."""
        return re.sub(r"[^a-z0-9 ]+", " ", text.lower()).strip()

    def answer(self, questionnaire: List[Dict[str, Any]], job: Any = None) -> Dict[str, Any]:
        """
        Resolves {questionId: answer} for all items in the questionnaire.
        Text box answers -> str, Multiple choice answers -> list[str].
        """
        resolved: Dict[str, Any] = {}
        pending: List[Dict[str, Any]] = []

        # Pass 1: Cache and Common Q&A rule match
        for q in questionnaire:
            qid = q["questionId"]
            qtext = (q.get("questionName") or "").strip()
            options = q.get("answerOption") or {}
            cached = self._lookup(qtext, options)
            if cached is not None:
                resolved[qid] = cached
            else:
                pending.append(q)

        # Pass 2: Batched LLM call for unresolved questions
        skip_ai = self.cfg.config.get("questionnaire", {}).get("skip_ai", False)
        if pending and not skip_ai and self.ai.is_configured():
            p = self.profile
            profile_summary = (
                f"{p.get('role_focus', 'backend')} developer, "
                f"{p.get('experience_years', 2)} yrs exp, "
                f"stack: {', '.join(p.get('tech_stack', [])[:6])}, "
                f"notice: {p.get('notice_days', 30)} days, "
                f"CTC: {p.get('current_ctc', '5')} -> {p.get('expected_ctc', '7')} LPA"
            )
            job_info = f"Job: {getattr(job, 'title', '')} at {getattr(job, 'company', '')}" if job else ""
            ai_answers = self.ai.answer_questionnaire_batch(pending, profile_summary, job_info)

            for q in pending:
                qid = q["questionId"]
                qtext = (q.get("questionName") or "").strip()
                ans = ai_answers.get(qid)
                if ans is not None:
                    resolved[qid] = ans
                    self.cache[self._norm(qtext)] = ans
            if ai_answers:
                self.cache_repo.save(self.cache)

        # Pass 3: Heuristic fallback for any still-unresolved questions
        for q in questionnaire:
            qid = q["questionId"]
            if qid not in resolved:
                resolved[qid] = self._static_fallback(q)

        return resolved

    def _lookup(self, text: str, options: Dict[str, Any]) -> Optional[Any]:
        key = self._norm(text)
        # Direct cache hit
        if key in self.cache:
            cached = self.cache[key]
            if options and isinstance(cached, list):
                if all(k in options for k in cached):
                    return cached
            elif not options:
                return cached

        # Substring fuzzy match in common_qa
        for entry in self.common_qa:
            pattern = self._norm(entry["question"])
            if pattern in key or key in pattern:
                raw_ans = entry["answer"]
                if options:
                    matched_key = self._match_option(raw_ans, options)
                    if matched_key:
                        result = [matched_key]
                        self.cache[key] = result
                        self.cache_repo.save(self.cache)
                        return result
                else:
                    self.cache[key] = raw_ans
                    self.cache_repo.save(self.cache)
                    return raw_ans

        return None

    @staticmethod
    def _match_option(value: str, options: Dict[str, Any]) -> Optional[str]:
        val_lower = value.lower()
        for ok, ov in options.items():
            if val_lower in ov.lower() or ov.lower() in val_lower:
                return ok
        return None

    def _static_fallback(self, q: Dict[str, Any]) -> Any:
        p = self.profile
        qtext = (q.get("questionName") or "").lower()
        qtype = (q.get("questionType") or "").lower()
        options = q.get("answerOption") or {}
        exp = str(p.get("experience_years", 2))

        if qtype == "text box":
            if "current ctc" in qtext:
                return p.get("current_ctc", "5")
            if "expected ctc" in qtext:
                return p.get("expected_ctc", "7")
            if "notice" in qtext:
                return str(p.get("notice_days", 30))
            if "experience" in qtext:
                return exp
            return "1"

        if options:
            for k, v in options.items():
                if "yes" in v.lower():
                    return [k]
            return [list(options.keys())[0]]

        return "1"

    def _build_common_qa(self) -> List[Dict[str, str]]:
        p = self.profile
        exp = p.get("experience_years", 2)
        notice = p.get("notice_days", 30)
        cur_ctc = str(p.get("current_ctc", "5"))
        exp_ctc = str(p.get("expected_ctc", "7"))
        stack = p.get("tech_stack", [])
        remote = p.get("apply_remote", True)

        notice_label = (
            "Immediate" if notice == 0
            else "15 days or less" if notice <= 15
            else "1 month" if notice <= 30
            else "2 months" if notice <= 60
            else "3 months or more"
        )

        defaults: List[Dict[str, str]] = [
            {"question": "what is your current ctc", "answer": cur_ctc},
            {"question": "current ctc", "answer": cur_ctc},
            {"question": "what is your expected ctc", "answer": exp_ctc},
            {"question": "expected ctc", "answer": exp_ctc},
            {"question": "what is your notice period", "answer": notice_label},
            {"question": "notice period", "answer": notice_label},
            {"question": "can you join immediately", "answer": "Yes" if notice == 0 else "No"},
            {"question": "total years of experience", "answer": str(exp)},
            {"question": "how many years of experience", "answer": str(exp)},
            {"question": "are you a fresher", "answer": "No" if exp > 0 else "Yes"},
            {"question": "are you willing to relocate", "answer": "Yes"},
            {"question": "are you willing to work from office", "answer": "Yes"},
            {"question": "are you open to work from home", "answer": "Yes" if remote else "No"},
            {"question": "are you comfortable with night shifts", "answer": "No"},
            {"question": "are you comfortable with field work", "answer": "No"},
            {"question": "are you an indian national", "answer": "Yes"},
            {"question": "are you currently employed", "answer": "Yes"},
            {"question": "have you worked in a startup", "answer": "Yes"},
            {"question": "are you open to contract roles", "answer": "No"},
            {"question": "are you open to freelance", "answer": "No"},
        ]

        for tech in stack[:8]:
            tl = tech.lower()
            defaults += [
                {"question": f"do you have experience with {tl}", "answer": "Yes"},
                {"question": f"experience in {tl}", "answer": str(exp)},
                {"question": f"years of experience in {tl}", "answer": str(exp)},
                {"question": f"how many years of {tl} experience", "answer": str(exp)},
            ]

        user_qa = self.cfg.config.get("questionnaire", {}).get("common_qa", [])
        return user_qa + defaults
