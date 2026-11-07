"""
Job Matching & Filtering Pipeline Service.
Executes multi-stage heuristic filtering and AI candidate scoring.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.core.config import ConfigManager
from backend.core.logging import get_logger
from backend.integrations.ai.client import AIClient
from backend.storage.cache_repo import JsonCache

logger = get_logger(__name__)


class JobMatchingService:
    """
    Multi-stage job filter & ranking pipeline:
    normalize -> dedup -> hard_veto -> experience_filter -> desc_red_flag
    -> title_filter -> company_veto -> tag_presort -> ai_score -> rank -> select.
    """

    SOFTWARE_KEYWORDS = {
        "software", "developer", "engineer", "engineering",
        "backend", "full stack", "fullstack",
        "python", "node", "nodejs", "javascript", "typescript",
        "django", "fastapi", "flask", "golang",
        "devops", "cloud", "sre", "platform",
        "api", "microservices", "infrastructure",
        "tech lead", "sde", "swe", "mts", "programmer", "react",
    }

    FRONTEND_VETO_KEYWORDS = {
        "frontend", "front-end", "front end",
        "angular", "vue", "ui developer", "ui engineer",
        "android", "ios", "flutter", "mobile", "kotlin", "swift",
        "embedded", "firmware",
        "ml engineer", "data engineer", "data scientist",
        "intern", "internship", "lead", "golang", "mlops", "devops",
        "web developer - java technologies",
        "member of technical staff - mts",
    }

    DESC_RED_FLAGS = {
        "walk-in": r"walk.?in|walkin",
        "venue listed": r"venue\s*:|interview venue|bring your resume|carry your resume",
    }

    def __init__(
        self,
        config_manager: Optional[ConfigManager] = None,
        ai_client: Optional[AIClient] = None,
        cache_file: str = "score_cache.json",
        daily_apply_limit: Optional[int] = None,
        min_apply_score: Optional[int] = None,
        ai_score_limit: Optional[int] = None,
        batch_size: Optional[int] = None,
    ) -> None:
        self.cfg = config_manager or ConfigManager()
        self.ai = ai_client or AIClient(self.cfg)
        ai_cfg = self.cfg.config.get("ai", {})

        self.cache_repo = JsonCache(cache_file)
        self.daily_apply_limit = daily_apply_limit if daily_apply_limit is not None else ai_cfg.get("daily_apply_limit", 50)
        self.min_apply_score = min_apply_score if min_apply_score is not None else ai_cfg.get("score_threshold", 50)
        self.ai_score_limit = ai_score_limit if ai_score_limit is not None else ai_cfg.get("ai_score_limit", 300)
        self.batch_size = batch_size if batch_size is not None else ai_cfg.get("batch_size", 50)

        # Load veto rules
        veto = self.cfg.veto
        self.VETO_TITLES: List[str] = [t.lower() for t in veto.get("titles", [])]
        self.VETO_COMPANIES: Set[str] = {c.lower() for c in veto.get("companies", [])}

        # Candidate stack for overlap presorting
        raw_stack = self.cfg.config.get("profile", {}).get("tech_stack", [])
        self.MY_STACK = [t.lower() for t in raw_stack] if raw_stack else self._default_stack()

    @staticmethod
    def _default_stack() -> List[str]:
        return [
            "node", "node.js", "nodejs", "python", "javascript", "typescript",
            "express", "express.js", "fastapi", "flask", "nestjs", "django",
            "mongodb", "mongoose", "postgresql", "mysql", "redis", "dynamodb",
            "aws", "gcp", "docker", "kubernetes", "ci/cd", "github actions", "terraform",
            "rest", "rest api", "graphql", "websocket", "kafka",
            "selenium", "playwright", "langchain", "openai", "llm", "rag",
            "git", "postman", "jwt", "microservices",
        ]

    # ── Pipeline Orchestration ──────────────────────────────────────────────

    def filter_and_rank(self, jobs: List[Any]) -> List[Dict[str, Any]]:
        """Executes the complete heuristic + AI filtering pipeline."""
        raw_count = len(jobs)
        normalized = self.normalize_jobs(jobs)

        n = len(normalized); deduped = self.dedup(normalized); d_dedup = n - len(deduped)
        n = len(deduped); vetoed = self.hard_veto(deduped); d_veto = n - len(vetoed)
        n = len(vetoed); exp_passed = self.experience_filter(vetoed); d_exp = n - len(exp_passed)
        n = len(exp_passed); red_flag_passed = self.desc_red_flag_check(exp_passed); d_flags = n - len(red_flag_passed)
        n = len(red_flag_passed); title_passed = self.title_filter(red_flag_passed); d_title = n - len(title_passed)
        n = len(title_passed); co_passed = self.company_veto(title_passed); d_co = n - len(co_passed)

        presorted = self.tag_presort(co_passed)
        candidate_subset = presorted[: self.ai_score_limit]

        logger.info(
            "Heuristic filter: %d fetched -> %d for scoring (dedup: -%d, veto: -%d, exp: -%d, flags: -%d, title: -%d, company: -%d)",
            raw_count, len(candidate_subset), d_dedup, d_veto, d_exp, d_flags, d_title, d_co,
        )

        scored = self.score_batch(candidate_subset)
        ranked = self.rank(scored)
        selected = self.select(ranked)
        logger.info("AI scoring & selection complete: %d selected for application", len(selected))
        return selected

    # Backwards-compatibility alias
    def run(self, jobs: List[Any]) -> List[Dict[str, Any]]:
        return self.filter_and_rank(jobs)

    # ── Normalization ────────────────────────────────────────────────────────

    def normalize_jobs(self, jobs: List[Any]) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        for j in jobs:
            job = j if isinstance(j, dict) else j.__dict__
            posted = (job.get("posted_date") or "").lower()
            days_old = 7
            if any(w in posted for w in ("today", "hour", "just now")):
                days_old = 0
            elif "yesterday" in posted:
                days_old = 1
            else:
                m = re.search(r"(\d+)\s*day", posted)
                if m:
                    days_old = int(m.group(1))
                else:
                    m = re.search(r"(\d+)\s*week", posted)
                    if m:
                        days_old = int(m.group(1)) * 7

            exp = job.get("experience") or ""
            exp_min, exp_max = 0, 10
            nums = re.findall(r"\d+", exp)
            if len(nums) >= 2:
                exp_min, exp_max = int(nums[0]), int(nums[1])
            elif len(nums) == 1:
                exp_min = exp_max = int(nums[0])

            raw_tags = job.get("tags") or job.get("skills") or []
            if isinstance(raw_tags, str):
                raw_tags = re.split(r"[,;|]", raw_tags)
            tags = [t.strip().lower() for t in raw_tags if t.strip()]

            normalized.append({
                "job_id": str(job.get("job_id") or ""),
                "title": (job.get("title") or "").strip(),
                "company": (job.get("company") or "").strip(),
                "location": (job.get("location") or "").strip(),
                "description": (job.get("description") or "").strip(),
                "tags": tags,
                "mandatory_tags": tags[:2],
                "optional_tags": tags[2:],
                "days_old": days_old,
                "experience_min": exp_min,
                "experience_max": exp_max,
            })
        return normalized

    # ── Heuristic Filters ────────────────────────────────────────────────────

    def dedup(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen: Set[str] = set()
        result: List[Dict[str, Any]] = []
        for j in jobs:
            jid = j.get("job_id")
            if not jid:
                result.append(j)
                continue
            if jid in seen:
                continue
            seen.add(jid)
            result.append(j)
        return result

    def hard_veto(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        clean: List[Dict[str, Any]] = []
        for j in jobs:
            title = (j.get("title") or "").lower()
            if any(kw in title for kw in self.VETO_TITLES):
                continue
            clean.append(j)
        return clean

    def experience_filter(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            j for j in jobs
            if j.get("experience_min", 0) <= 4 and j.get("experience_max", 10) > 0
        ]

    def desc_red_flag_check(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        clean: List[Dict[str, Any]] = []
        for j in jobs:
            desc = (j.get("description") or "").lower()
            flagged = [label for label, pat in self.DESC_RED_FLAGS.items() if re.search(pat, desc)]
            if not flagged:
                clean.append(j)
        return clean

    def title_filter(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        for j in jobs:
            title = (j.get("title") or "").lower()
            if not any(kw in title for kw in self.SOFTWARE_KEYWORDS):
                continue
            if any(kw in title for kw in self.FRONTEND_VETO_KEYWORDS):
                continue
            result.append(j)
        return result

    def company_veto(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        clean: List[Dict[str, Any]] = []
        for j in jobs:
            company = (j.get("company") or "").lower()
            if any(vc in company for vc in self.VETO_COMPANIES):
                continue
            clean.append(j)
        return clean

    def tag_presort(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        my_stack = set(self.MY_STACK)

        def overlap_score(j: Dict[str, Any]) -> int:
            tags = set(j.get("tags", []))
            mandatory_hit = sum(1 for t in j.get("mandatory_tags", []) if t in my_stack)
            total_hit = len(tags & my_stack)
            recency_bonus = max(0, 7 - j.get("days_old", 7))
            return mandatory_hit * 3 + total_hit + recency_bonus

        return sorted(jobs, key=overlap_score, reverse=True)

    # ── AI Scoring & Ranking ─────────────────────────────────────────────────

    def score_batch(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        cache = self.cache_repo.load()
        result: List[Dict[str, Any]] = []

        for i in range(0, len(jobs), self.batch_size):
            batch = jobs[i : i + self.batch_size]
            uncached = [j for j in batch if str(j.get("job_id", "")) not in cache]

            scores: Dict[str, Any] = {}
            if uncached and self.ai.is_configured():
                candidate_prompt = self.cfg.load_prompt()
                scores = self.ai.score_jobs_batch(uncached, candidate_prompt)

            uncached_idx = 0
            for job in batch:
                jid = str(job.get("job_id") or "")
                if jid in cache:
                    data = cache[jid]
                else:
                    data = scores.get(str(uncached_idx), {"score": 0, "reason": "no response"})
                    if not isinstance(data.get("score"), int):
                        data = {"score": 0, "reason": "parse error"}
                    if jid:
                        cache[jid] = data
                    uncached_idx += 1

                job["ai_score"] = data.get("score", 0)
                job["ai_reason"] = data.get("reason", "")
                result.append(job)

        self.cache_repo.save(cache)
        return result

    def rank(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return sorted(
            jobs,
            key=lambda j: j.get("ai_score", 0) + max(0, 3 - j.get("days_old", 7)),
            reverse=True,
        )

    def select(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        apply_list = [j for j in jobs if j.get("ai_score", 0) >= self.min_apply_score]
        return apply_list[: self.daily_apply_limit]
