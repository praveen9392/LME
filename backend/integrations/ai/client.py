"""
AI Integration Client for OpenRouter and OpenAI API.
Handles batch job scoring and questionnaire answering with model fallback.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

import requests

from backend.core.config import ConfigManager
from backend.core.exceptions import AIProviderError
from backend.core.logging import get_logger

logger = get_logger(__name__)


class AIClient:
    """Provides chat completion interfaces for job scoring and screening questionnaires."""

    def __init__(self, config_manager: Optional[ConfigManager] = None) -> None:
        self.cfg = config_manager or ConfigManager()

    def is_configured(self) -> bool:
        """Returns True if an API key is available for the configured provider."""
        return bool(self.cfg.get_ai_key())

    # ── Job Scoring ─────────────────────────────────────────────────────────

    def score_jobs_batch(self, jobs: List[Dict[str, Any]], candidate_profile: str) -> Dict[str, Dict[str, Any]]:
        """
        Sends a batch of candidate jobs to the LLM for 0-100 scoring.
        Returns a dictionary mapping str(index) -> {"score": int, "reason": str}.
        """
        if not self.is_configured():
            logger.warning("AI scoring skipped: No API key set in .env")
            return {}

        # Build textual representation of each job
        job_block = ""
        for i, j in enumerate(jobs):
            mandatory = ", ".join(j.get("mandatory_tags", [])) or "none"
            optional = ", ".join(j.get("optional_tags", [])) or "none"
            exp = f"{j.get('experience_min', 0)}-{j.get('experience_max', 10)} yrs"
            job_block += (
                f"Job {i}:\n"
                f"  Title:     {j.get('title')}\n"
                f"  Company:   {j.get('company')}\n"
                f"  Mandatory: {mandatory}\n"
                f"  Optional:  {optional}\n"
                f"  Exp:       {exp}\n"
                f"  Days old:  {j.get('days_old', 7)}\n"
                f"---\n"
            )

        prompt = f"""
You are a strict job filter. Score each job 0-100.
Be precise — avoid clustering scores at 85 or 60. Use the full range.

CANDIDATE:
{candidate_profile}

SCORING RUBRIC — use the full range, not just 85/60:

90-100 — perfect fit, apply immediately
  Primary tech is mandatory tag + backend/fullstack role
  + exp 0-2 yrs + familiar supporting stack. Startup or product company.

75-89 — strong fit, apply
  Primary tech present (mandatory or optional) + backend lean
  + exp 0-3 yrs. Maybe one unfamiliar tag but overall good match.

55-74 — decent fit, apply with lower priority
  Some stack overlap, role is fullstack but not backend-heavy,
  or exp is 3-4 yrs, or company type unclear.

30-54 — weak, skip unless nothing better
  Familiar tech present but role is vague, frontend-leaning,
  or exp mismatch 4-5 yrs.

10-29 — poor match
  Very little stack overlap, or role is clearly not backend.

0-9 — do not apply
  Zero stack overlap (Java+Spring only, PHP only, .NET only etc.)
  OR walk-in / venue / intern role.

RULES:
- If primary stack tech + 0-2yr backend → 90+, no exceptions
- Java alongside primary tech is fine — judge the full picture
- "Software Engineer" with primary stack tags → treat as backend, score 70-85
- Pure React/Angular/Vue with no backend tags → 0-15
- DevOps/infra-only with no app dev → 20-40
- Intern roles → 0
- Recency: 0-1 days old → mentally add 5 points

Return ONLY valid JSON, no explanation outside it:
{{
  "0": {{"score": 92, "reason": "Node.js + MongoDB mandatory, 0-2yr, startup backend"}},
  "1": {{"score": 0,  "reason": "Java/Spring only, zero overlap"}}
}}

Jobs:
{job_block}
"""
        model_name = self.cfg.config.get("ai", {}).get("model", "openrouter/free")
        # Enforce free model safety: refuse any paid models
        if not (model_name.endswith(":free") or model_name == "openrouter/free"):
            logger.warning("Configured model '%s' is not an OpenRouter free model. Enforcing 'openrouter/free' to prevent billing.", model_name)
            model_name = "openrouter/free"
        try:
            logger.debug("Requesting AI score batch for %d jobs using model '%s'", len(jobs), model_name)
            res = requests.post(
                self.cfg.get_ai_url(),
                headers=self.cfg.get_ai_headers(),
                json={
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                },
                timeout=90,
            )

            if res.status_code == 429:
                logger.warning("OpenRouter free tier rate limit encountered (HTTP 429). Skipping batch gracefully.")
                return {}
            if not res.ok:
                logger.error("OpenRouter API returned HTTP %d: %s", res.status_code, res.text[:200])
                return {}

            content = res.json()["choices"][0]["message"]["content"]
            content = re.sub(r"```json|```", "", content).strip()
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if not match:
                logger.warning("Could not extract JSON from AI response: %s", content[:200])
                return {}

            data = json.loads(match.group(0))
            return data if isinstance(data, dict) else {}

        except Exception as exc:
            logger.error("AI scoring request failed: %s", exc)
            return {}

    # ── Questionnaire Batched Answers ───────────────────────────────────────

    def answer_questionnaire_batch(
        self,
        questions: List[Dict[str, Any]],
        profile_summary: str,
        job_info: str = "",
    ) -> Dict[str, Any]:
        """
        Sends all unanswered questionnaire items to the LLM in a single prompt.
        Returns mapping from questionId -> resolved answer.
        """
        if not self.is_configured() or not questions:
            return {}

        q_lines: List[str] = []
        for i, q in enumerate(questions, 1):
            qtext = (q.get("questionName") or "").strip()
            qtype = (q.get("questionType") or "").lower()
            options = q.get("answerOption") or {}

            line = f"Q{i} ({'text' if qtype == 'text box' else 'choice'}): \"{qtext}\""
            if options:
                opts = "  |  ".join(f"{k}: {v}" for k, v in list(options.items())[:6])
                line += f"\n   Options: {opts}"
            q_lines.append(line)

        q_block = "\n".join(q_lines)
        reply_format = "\n".join(f"Q{i}: <answer>" for i in range(1, len(questions) + 1))

        prompt = (
            f"You are filling in a job application form for a candidate.\n"
            f"Profile: {profile_summary}.\n{job_info}\n\n"
            f"Answer each question with ONE short value.\n"
            f"For choice questions: reply with the option KEY (e.g. \"option_1\").\n"
            f"For text questions: reply with a plain short value (number, Yes, No, etc.).\n\n"
            f"{q_block}\n\n"
            f"Reply in EXACTLY this format, one line per question:\n"
            f"{reply_format}"
        )

        model_name = self.cfg.config.get("ai", {}).get("model", "openrouter/free")
        if not (model_name.endswith(":free") or model_name == "openrouter/free"):
            logger.warning("Configured model '%s' is not an OpenRouter free model. Enforcing 'openrouter/free' to prevent billing.", model_name)
            model_name = "openrouter/free"
        try:
            res = requests.post(
                self.cfg.get_ai_url(),
                headers=self.cfg.get_ai_headers(),
                json={
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": len(questions) * 30 + 50,
                    "temperature": 0.0,
                },
                timeout=30,
            )
            if res.status_code == 429:
                logger.warning("OpenRouter free tier rate limit encountered (HTTP 429) during questionnaire answering.")
                return {}
            if not res.ok:
                logger.error("OpenRouter API returned HTTP %d for questionnaire: %s", res.status_code, res.text[:200])
                return {}
            raw = res.json()["choices"][0]["message"]["content"].strip()
            return self._parse_ai_qa_reply(raw, questions)
        except Exception as exc:
            logger.debug("AI questionnaire request failed: %s", exc)
            return {}

    @staticmethod
    def _parse_ai_qa_reply(raw: str, questions: List[Dict[str, Any]]) -> Dict[str, Any]:
        answers: Dict[str, Any] = {}
        for i, q in enumerate(questions, 1):
            qid = q["questionId"]
            options = q.get("answerOption") or {}

            match = re.search(rf"Q{i}\s*:\s*(.+)", raw, re.IGNORECASE)
            if not match:
                continue

            raw_val = match.group(1).strip().strip('"').strip("'")
            if options:
                if raw_val in options:
                    answers[qid] = [raw_val]
                    continue
                # Match label substring
                matched_key = None
                for ok, ov in options.items():
                    if raw_val.lower() in ov.lower() or ov.lower() in raw_val.lower():
                        matched_key = ok
                        break
                answers[qid] = [matched_key or list(options.keys())[0]]
            else:
                answers[qid] = raw_val

        return answers
