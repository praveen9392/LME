"""
HTTP Request Handlers for the Setup Wizard and Analytics Dashboard.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler
import json
import mimetypes
import os
from pathlib import Path
import sqlite3
import sys
import threading
from typing import Any, Dict, Optional

from backend.automation.cron_installer import install_crontab
from backend.core.config import ConfigManager, PROMPT_PATH
from backend.core.logging import get_logger
from backend.integrations.naukri.auth import NaukriAuthClient
from backend.storage.applied_jobs_repo import AppliedJobsDB

logger = get_logger(__name__)

FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend"


class WebHandler(BaseHTTPRequestHandler):
    """Handles static files, HTML templates, and REST APIs for Setup Wizard and Dashboard."""

    shutdown_event: Optional[threading.Event] = None

    def log_message(self, format: str, *args: Any) -> None:
        # Avoid cluttering console output with standard HTTP 200 logs
        logger.debug("%s - - [%s] %s", self.client_address[0], self.log_date_time_string(), format % args)

    # ── GET Handlers ────────────────────────────────────────────────────────

    def do_GET(self) -> None:
        path = self.path.split("?")[0]

        if path in ("/", "/setup", "/index.html"):
            self._serve_template("setup_wizard.html")
        elif path == "/dashboard":
            self._serve_template("dashboard.html")
        elif path.startswith("/static/"):
            self._serve_static(path)
        elif path == "/api/config":
            self._get_config()
        elif path == "/api/prompt":
            self._get_prompt()
        elif path == "/api/dashboard-data":
            self._get_dashboard_data()
        else:
            self._json({"error": "Not Found"}, status=404)

    # ── POST Handlers ───────────────────────────────────────────────────────

    def do_POST(self) -> None:
        body = self._body()
        path = self.path.split("?")[0]

        if path == "/api/login":
            self._handle_login(body)
        elif path == "/api/cookies":
            self._handle_cookies(body)
        elif path == "/api/save":
            self._handle_save(body)
        elif path == "/api/save-prompt":
            self._handle_save_prompt(body)
        elif path == "/api/install-cron":
            self._handle_install_cron(body)
        elif path == "/api/done":
            self._json({"ok": True})
            if self.shutdown_event:
                threading.Thread(target=self.shutdown_event.set, daemon=True).start()
        else:
            self._json({"error": "Not Found"}, status=404)

    # ── API Implementations ──────────────────────────────────────────────────

    def _get_config(self) -> None:
        cfg = ConfigManager()
        data = cfg.load()
        has_or = bool(os.getenv("OPENROUTER_API_KEY"))
        has_oai = bool(os.getenv("OPEN_API_KEY"))
        user, _ = cfg.get_naukri_credentials()
        _, pwd = cfg.get_naukri_credentials()

        data["_env"] = {
            "has_credentials": bool(user and pwd),
            "has_ai_key": has_or or has_oai,
            "ai_key_provider": "openrouter" if has_or else ("openai" if has_oai else ""),
            "cwd": str(Path.cwd()),
            "python": sys.executable,
        }
        data["_prompt"] = cfg.load_prompt()
        self._json(data)

    def _get_prompt(self) -> None:
        cfg = ConfigManager()
        self._json({"prompt": cfg.load_prompt()})

    def _handle_save_prompt(self, body: Dict[str, Any]) -> None:
        prompt_text = body.get("prompt", "").strip()
        if not prompt_text:
            self._json({"ok": False, "error": "Prompt cannot be empty."}, status=400)
            return
        try:
            PROMPT_PATH.write_text(prompt_text, encoding="utf-8")
            self._json({"ok": True})
        except Exception as exc:
            logger.error("Failed to save custom prompt: %s", exc)
            self._json({"ok": False, "error": str(exc)}, status=500)

    def _get_dashboard_data(self) -> None:
        db = AppliedJobsDB()
        total = db.total()

        stats = {
            "total": total,
            "high": 0,
            "mid": 0,
            "low": 0,
            "no_score": 0,
        }
        daily = []
        top_companies = []
        recent_jobs = []

        if total > 0 and Path(db.db_path).exists():
            conn = sqlite3.connect(db.db_path)
            try:
                cur = conn.cursor()
                # Score tiers
                cur.execute("""
                    SELECT
                        SUM(CASE WHEN ai_score >= 70 THEN 1 ELSE 0 END),
                        SUM(CASE WHEN ai_score >= 50 AND ai_score < 70 THEN 1 ELSE 0 END),
                        SUM(CASE WHEN ai_score IS NOT NULL AND ai_score < 50 THEN 1 ELSE 0 END),
                        SUM(CASE WHEN ai_score IS NULL THEN 1 ELSE 0 END)
                    FROM applied_jobs
                """)
                row = cur.fetchone()
                if row:
                    stats["high"] = row[0] or 0
                    stats["mid"] = row[1] or 0
                    stats["low"] = row[2] or 0
                    stats["no_score"] = row[3] or 0

                # Daily applications (last 30 days)
                cur.execute("""
                    SELECT substr(applied_at, 1, 10) as day, COUNT(*) as count
                    FROM applied_jobs
                    GROUP BY day
                    ORDER BY day DESC
                    LIMIT 30
                """)
                daily = [{"day": r[0], "count": r[1]} for r in reversed(cur.fetchall())]

                # Top companies
                cur.execute("""
                    SELECT company, COUNT(*) as count
                    FROM applied_jobs
                    WHERE company != ''
                    GROUP BY company
                    ORDER BY count DESC
                    LIMIT 8
                """)
                top_companies = [{"company": r[0], "count": r[1]} for r in cur.fetchall()]

                # Recent applications
                cur.execute("""
                    SELECT title, company, location, ai_score, applied_at
                    FROM applied_jobs
                    ORDER BY applied_at DESC
                    LIMIT 50
                """)
                recent_jobs = [
                    {
                        "title": r[0] or "",
                        "company": r[1] or "",
                        "location": r[2] or "",
                        "ai_score": r[3],
                        "applied_at": r[4] or "",
                    }
                    for r in cur.fetchall()
                ]
            finally:
                conn.close()

        self._json({
            "stats": stats,
            "daily": daily,
            "top_companies": top_companies,
            "recent_jobs": recent_jobs,
        })

    def _handle_login(self, body: Dict[str, Any]) -> None:
        email = body.get("email", "").strip()
        password = body.get("password", "").strip()
        if not email or not password:
            self._json({"ok": False, "error": "Email and password are required."}, status=400)
            return

        try:
            client = NaukriAuthClient(email, password)
            client.login()
            at = str(client.session.cookies.get("nauk_at", ""))
            rt = str(client.session.cookies.get("nauk_rt", ""))
            cfg = ConfigManager()
            cfg.store_session_cookies(at, rt)
            self._json({"ok": True, "nauk_at": at, "nauk_rt": rt})
        except Exception as exc:
            logger.warning("Web login failed: %s", exc)
            self._json({"ok": False, "error": str(exc)})

    def _handle_cookies(self, body: Dict[str, Any]) -> None:
        at = body.get("nauk_at", "").strip()
        rt = body.get("nauk_rt", "").strip()
        if not at:
            self._json({"ok": False, "error": "nauk_at is required."}, status=400)
            return

        try:
            cfg = ConfigManager()
            cfg.store_session_cookies(at, rt)
            self._json({"ok": True})
        except Exception as exc:
            self._json({"ok": False, "error": str(exc)})

    def _handle_save(self, body: Dict[str, Any]) -> None:
        cfg = ConfigManager()
        env_vars = body.pop("env_vars", {})
        if env_vars:
            cfg.write_env(env_vars)

        try:
            current = cfg.load()
            from backend.core.config import _deep_merge
            merged = _deep_merge(current, body)
            cfg.save(merged)

            if not PROMPT_PATH.exists():
                PROMPT_PATH.write_text(cfg.generate_prompt_from_config(merged), encoding="utf-8")

            self._json({"ok": True})
        except Exception as exc:
            logger.error("Failed to save config via web API: %s", exc)
            self._json({"ok": False, "error": str(exc)}, status=500)

    def _handle_install_cron(self, body: Dict[str, Any]) -> None:
        line = body.get("cron_line", "").strip()
        ok, msg = install_crontab(line)
        self._json({"ok": ok, "error": None if ok else msg})

    # ── Template & Static File Servicing ─────────────────────────────────────

    def _serve_template(self, filename: str) -> None:
        template_path = FRONTEND_DIR / "templates" / filename
        if not template_path.exists():
            self._json({"error": "Template not found"}, status=404)
            return

        content = template_path.read_text(encoding="utf-8")
        data = content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(data)

    def _serve_static(self, url_path: str) -> None:
        # URL path is /static/css/style.css -> file is FRONTEND_DIR / static / css / style.css
        relative_path = url_path.replace("/static/", "", 1)
        file_path = (FRONTEND_DIR / "static" / relative_path).resolve()

        # Prevent directory traversal attacks
        if not str(file_path).startswith(str((FRONTEND_DIR / "static").resolve())):
            self._json({"error": "Forbidden"}, status=403)
            return

        if not file_path.exists() or not file_path.is_file():
            self._json({"error": "Static asset not found"}, status=404)
            return

        mime_type, _ = mimetypes.guess_type(str(file_path))
        mime_type = mime_type or "application/octet-stream"

        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        self.wfile.write(data)

    # ── Helper Utilities ─────────────────────────────────────────────────────

    def _body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def _json(self, data: Dict[str, Any], status: int = 200) -> None:
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        # Restrict CORS to local host
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:8765")
        self.end_headers()
        self.wfile.write(payload)
