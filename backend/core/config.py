"""
Centralized Configuration Manager for LME / Naukri Job Automation.
Reads/writes: config.json, veto.json, user_prompt.md, and .env.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import secrets
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv, set_key

from backend.core.constants import OPENAI_COMPLETIONS_URL, OPENROUTER_COMPLETIONS_URL
from backend.core.exceptions import ConfigurationError

# Load environment variables from .env if present
load_dotenv()

CONFIG_PATH = Path("config.json")
VETO_PATH = Path("veto.json")
PROMPT_PATH = Path("user_prompt.md")
SESSION_CACHE_PATH = Path(".session.json")

# ── Default Configurations ──────────────────────────────────────────────────

DEFAULT_CONFIG: Dict[str, Any] = {
    "profile": {
        "role_focus": "backend",
        "experience_years": 2,
        "tech_stack": ["Node.js", "Python", "MongoDB", "REST APIs", "AWS", "Docker"],
        "locations": ["Bangalore", "Hyderabad"],
        "apply_remote": True,
        "current_ctc": "5",
        "expected_ctc": "7",
        "notice_days": 30,
        "resume_path": "",
    },
    "ai": {
        "provider": "openrouter",
        "model": "openrouter/free",
        "score_threshold": 50,
        "daily_apply_limit": 50,
        "ai_score_limit": 300,
        "batch_size": 50,
    },
    "search": {
        "job_age": 2,
        "pages_per_query": 1,
    },
    "queries": [
        {"keyword": "Node.js backend developer", "location": "Bangalore"},
        {"keyword": "Python Developer", "location": ""},
        {"keyword": "Node.js Developer", "location": ""},
        {"keyword": "python backend developer", "location": "Pune"},
    ],
    "cron": {
        "profile_update": {
            "enabled": True,
            "interval_hours": 6,
        },
        "apply": {
            "enabled": True,
            "schedule": "08:00",
            "days": "mon-fri",
            "timezone": "Asia/Kolkata",
        },
    },
    "questionnaire": {
        "skip_ai": False,
        "common_qa": [],
    },
    "telegram": {
        "enabled": False,
        "alerts": {
            "on_apply": True,
            "on_failure": True,
            "on_run_summary": True,
            "on_questionnaire": False,
            "on_error": True,
            "on_scheduler_start": True,
        },
    },
}

DEFAULT_VETO: Dict[str, List[str]] = {
    "titles": [
        "walk-in", "walkin", "walk in",
        "android developer", "ios developer", "flutter developer",
        "frontend developer", "front-end developer",
        "principal engineer", "staff engineer", "architect",
        "vp of", "head of engineering", "head of technology",
        "founder", "tutor", "trainer",
        "data scientist", "ml engineer", "data engineer", "intern", "internship",
        "engineering manager", "etl engineer", "prompt engineer",
        "analyst", "associate is engineer", "infra engineer",
        "observability engineer", "manager",
    ],
    "companies": [
        "accenture", "wipro", "infosys", "tcs", "cognizant",
        "capgemini", "hcl", "tech mahindra", "mphasis", "hexaware",
        "ltimindtree", "persistent", "birlasoft",
    ],
}

DEFAULT_PROMPT = """\
## My Profile

- **Role focus:** Backend developer
- **Experience:** 2 years, backend-focused
- **Core stack:** Node.js, Python, MongoDB, REST APIs, AWS
- **Also know:** Docker, CI/CD, automation, Selenium, Playwright, web scraping,
  n8n, LangChain, RAG, vector DBs, FastAPI, Flask, Express
- **Looking for:** SDE1 / junior-mid backend or fullstack-backend roles
- **Prefers:** startups, product companies, AI/automation work, remote/hybrid
- **Will NOT do:** pure frontend, mobile, ML research, data science, DevOps-only

## Scoring Preference

- Prioritize roles where Node.js or Python is a mandatory/primary tag
- Backend + startup + 0-3 yrs experience → score 80+
- Fullstack with Node.js or Python backend is fine
- Pure frontend, mobile, ML → score 0-15
"""


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merges override dictionary into base dictionary."""
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


class ConfigManager:
    """Central configuration service for application settings, vetoes, and credentials."""

    def __init__(
        self,
        config_path: Path = CONFIG_PATH,
        veto_path: Path = VETO_PATH,
        prompt_path: Path = PROMPT_PATH,
    ) -> None:
        self.config_path = Path(config_path)
        self.veto_path = Path(veto_path)
        self.prompt_path = Path(prompt_path)
        self._config: Optional[dict] = None
        self._veto: Optional[dict] = None

    # ── config.json Management ──────────────────────────────────────────────

    def load(self) -> dict:
        """Loads config.json deep-merged with defaults."""
        if not self.config_path.exists():
            return DEFAULT_CONFIG.copy()
        try:
            with open(self.config_path, encoding="utf-8") as f:
                data = json.load(f)
            return _deep_merge(DEFAULT_CONFIG, data)
        except Exception as exc:
            raise ConfigurationError(f"Failed to read {self.config_path}: {exc}") from exc

    def save(self, config: dict) -> None:
        """Persists config dictionary to config.json."""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
            self._config = config
        except Exception as exc:
            raise ConfigurationError(f"Failed to save {self.config_path}: {exc}") from exc

    @property
    def config(self) -> dict:
        if self._config is None:
            self._config = self.load()
        return self._config

    def reload(self) -> dict:
        self._config = self.load()
        return self._config

    # ── veto.json Management ────────────────────────────────────────────────

    def load_veto(self) -> dict:
        if not self.veto_path.exists():
            self.save_veto(DEFAULT_VETO)
            return DEFAULT_VETO.copy()
        try:
            with open(self.veto_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return DEFAULT_VETO.copy()

    def save_veto(self, veto: dict) -> None:
        try:
            self.veto_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.veto_path, "w", encoding="utf-8") as f:
                json.dump(veto, f, indent=2)
            self._veto = veto
        except Exception as exc:
            raise ConfigurationError(f"Failed to save {self.veto_path}: {exc}") from exc

    @property
    def veto(self) -> dict:
        if self._veto is None:
            self._veto = self.load_veto()
        return self._veto

    # ── user_prompt.md Management ───────────────────────────────────────────

    def load_prompt(self) -> str:
        """Reads candidate scoring prompt from markdown file."""
        if not self.prompt_path.exists():
            try:
                self.prompt_path.write_text(DEFAULT_PROMPT, encoding="utf-8")
            except Exception:
                pass
            return DEFAULT_PROMPT
        return self.prompt_path.read_text(encoding="utf-8").strip()

    def generate_prompt_from_config(self, config: dict) -> str:
        """Generates markdown prompt body from configured profile values."""
        p = config.get("profile", {})
        role = p.get("role_focus", "backend").title()
        exp = p.get("experience_years", 2)
        stack = p.get("tech_stack", [])
        locs = p.get("locations", [])

        stack_str = ", ".join(stack) if stack else "Node.js, Python"
        loc_str = (
            ", ".join(locs) + (" and remote" if p.get("apply_remote") else "")
            if locs else "open to all"
        )
        primary = stack[0] if stack else "Node.js"

        return (
            f"## My Profile\n\n"
            f"- **Role focus:** {role} developer\n"
            f"- **Experience:** {exp} year{'s' if exp != 1 else ''}, {role.lower()}-focused\n"
            f"- **Core stack:** {stack_str}\n"
            f"- **Preferred locations:** {loc_str}\n"
            f"- **Looking for:** SDE1 / junior-mid {role.lower()} or fullstack-backend roles\n"
            f"- **Prefers:** startups, product companies, AI/automation work, remote/hybrid\n"
            f"- **Will NOT do:** pure frontend, mobile, ML research, data science\n\n"
            f"## Scoring Preference\n\n"
            f"- Prioritize roles where {primary} is a mandatory/primary tag\n"
            f"- {role} + startup + 0-{exp + 1} yrs experience → score 80+\n"
            f"- Fullstack with {role.lower()} focus is fine\n"
            f"- Pure frontend, mobile, ML → score 0-15\n"
        )

    # ── Credentials & Environment Accessors ──────────────────────────────────

    def get_naukri_credentials(self) -> tuple[str, str]:
        """
        Retrieves Naukri credentials.
        Prioritizes NAUKRI_USERNAME over USERNAME to prevent Windows %USERNAME% collision.
        """
        username = os.getenv("NAUKRI_USERNAME", "").strip()
        if not username:
            candidate = os.getenv("USERNAME", "").strip()
            # If candidate does not contain '@' and on Windows, it might be the OS username
            if candidate and "@" in candidate:
                username = candidate
            elif candidate and os.name != "nt":
                username = candidate
        password = os.getenv("PASSWORD", "").strip() or os.getenv("NAUKRI_PASSWORD", "").strip()
        return username, password

    def get_session_cookies(self) -> tuple[str, str]:
        """
        Returns cached (nauk_at, nauk_rt) cookies if available.
        Checks:
          1. Environment variables (NAUKRI_NAUK_AT, NAUKRI_NAUK_RT)
          2. Dedicated .session.json
          3. config.json session block (legacy fallback)
        """
        at = os.getenv("NAUKRI_NAUK_AT", "").strip()
        rt = os.getenv("NAUKRI_NAUK_RT", "").strip()
        if at:
            return at, rt

        if SESSION_CACHE_PATH.exists():
            try:
                data = json.loads(SESSION_CACHE_PATH.read_text(encoding="utf-8"))
                return data.get("nauk_at", ""), data.get("nauk_rt", "")
            except Exception:
                pass

        session_cfg = self.config.get("session", {})
        return session_cfg.get("nauk_at", ""), session_cfg.get("nauk_rt", "")

    def store_session_cookies(self, nauk_at: str, nauk_rt: str = "") -> None:
        """Stores session tokens safely in .session.json and in config."""
        try:
            SESSION_CACHE_PATH.write_text(
                json.dumps({"nauk_at": nauk_at, "nauk_rt": nauk_rt}, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass
        # Also store in config for backwards compatibility
        current = self.load()
        current = _deep_merge(current, {"session": {"nauk_at": nauk_at, "nauk_rt": nauk_rt}})
        self.save(current)

    def get_vid(self) -> str:
        """Visitor-ID sent as the `vid` header on Naukri login."""
        env_vid = os.getenv("NAUKRI_VID", "").strip()
        if env_vid:
            return env_vid
        return base64.b64encode(secrets.token_bytes(48)).decode("utf-8")

    def get_ai_url(self) -> str:
        """Returns OpenRouter completion endpoint. Paid endpoints are disabled."""
        return OPENROUTER_COMPLETIONS_URL

    def get_ai_key(self) -> str:
        """Retrieves OpenRouter API key from .env."""
        return os.getenv("OPENROUTER_API_KEY", "").strip() or os.getenv("OPEN_API_KEY", "").strip()

    def get_ai_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.get_ai_key()}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/praveen9392/LME",
            "X-Title": "LME",
        }

    def get_telegram_credentials(self) -> tuple[str, str]:
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        return token, chat_id

    def write_env(self, env_vars: dict) -> None:
        """Writes key-value pairs to the local .env file."""
        if not env_vars:
            return
        env_path = Path(".env")
        try:
            if not env_path.exists():
                env_path.touch()
            for key, val in env_vars.items():
                if val is not None and str(val).strip():
                    set_key(str(env_path), key, str(val).strip())
        except Exception:
            # Fallback manual text write
            existing: dict[str, str] = {}
            if env_path.exists():
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    if "=" in line and not line.startswith("#"):
                        k, _, v = line.partition("=")
                        existing[k.strip()] = v.strip()
            for key, val in env_vars.items():
                if val is not None and str(val).strip():
                    existing[key] = str(val).strip()
            env_path.write_text(
                "\n".join(f"{k}={v}" for k, v in existing.items()) + "\n",
                encoding="utf-8",
            )
