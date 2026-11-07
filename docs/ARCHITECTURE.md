# SYSTEM ARCHITECTURE SPECIFICATION
## Modular Naukri Job Application Automation Agent

**Document Version:** 2.0.0  
**Status:** Approved Target Architecture  
**Author:** Senior Software Architect  

---

## 1. Architectural Philosophy & Objectives

The restructured architecture transforms a script-heavy, monolithic automation script into an enterprise-ready, modular, and maintainable system while strictly preserving 100% of the existing business logic, algorithms, and interfaces.

### Core Architectural Principles:
1. **Separation of Concerns (SoC)**: Presentation (CLI & Web UI), Orchestration (Services), External Adapters (Integrations), and Persistence (Repositories) are strictly partitioned.
2. **Backward Compatibility**: All legacy CLI flags (`python apply_agent.py --setup`, `--dashboard`, `--list-applied`, etc.), script entry points, and legacy `src.*` import paths are preserved via compatibility shims.
3. **Defense in Depth**: Secrets are masked in logs, local web endpoints validate origins and bind to loopback addresses, and credentials are validated at startup.
4. **Resilience & Observability**: Centralized rotating logging, structured error handling with custom exceptions, and exponential backoff retry for transient network faults.

---

## 2. Target Layered Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        PRESENTATION LAYER                              │
│   CLI (apply_agent.py, main.py)   │   Web UI (Setup Wizard, Dashboard) │
└──────────────────┬───────────────────────────────┬─────────────────────┘
                   │                               │
┌──────────────────▼───────────────────────────────▼─────────────────────┐
│                         APPLICATION SERVICES                           │
│  ApplicationService  │  JobMatchingService  │  QuestionnaireService    │
│  NaukriService       │  ProfileService      │  SchedulerService        │
└──────────────────┬───────────────────────────────┬─────────────────────┘
                   │                               │
┌──────────────────▼───────────────────────────────▼─────────────────────┐
│                    INTEGRATIONS & ADAPTERS                             │
│  Naukri HTTP API (Auth, Search, Apply) │  OpenRouter / OpenAI (LLM)   │
│  Telegram Bot API (Notifications)      │  BotGuard & nkparam (Crypto)  │
└──────────────────┬───────────────────────────────┬─────────────────────┘
                   │                               │
┌──────────────────▼───────────────────────────────▼─────────────────────┐
│                   STORAGE & REPOSITORIES                               │
│  AppliedJobsRepository (SQLite + CSV)  │  TokenPoolRepository (SQLite) │
│  CacheRepository (JSON Caches)         │  ConfigManager (JSON/YAML)    │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Directory Layout (Before vs. After)

### Before (Flat & Coupled):
```
NopeRi/
├── apply_agent.py         # 588 lines (CLI, pipeline, embedded dashboard HTML)
├── main.py                # 99 lines sandbox
├── requirements.txt       # missing requests
├── cron/
│   ├── profile_updater.py
│   ├── scheduler.py
│   └── telegram_alert.py
└── src/
    ├── client/            # 4 large files with mixed concerns
    ├── config/
    ├── exceptions/
    ├── models/
    └── utils/             # web_setup.py (1,626 lines with embedded HTML)
```

### After (Modular & Layered):
```
LME/
├── apply_agent.py                 # Clean root CLI entry point (backward compatible)
├── main.py                        # Clean sandbox runner (backward compatible)
├── requirements.txt               # Complete, verified dependencies
├── .env.example                   # Annotated template without secrets
├── .gitignore                     # Comprehensive exclusions
├── run.bat                        # Windows launcher
├── user_prompt.md                 # Candidate profile for AI scoring
├── config.json                    # Configuration (generated)
├── veto.json                      # Veto lists
│
├── backend/                       # Python Backend Core
│   ├── __init__.py
│   ├── core/                      # Cross-cutting concerns
│   │   ├── __init__.py
│   │   ├── config.py              # Centralized configuration & validation
│   │   ├── logging.py             # Rotating file + console logger with secret masking
│   │   ├── exceptions.py          # Custom exception hierarchy
│   │   └── constants.py           # API endpoints and RSA public keys
│   │
│   ├── models/                    # Data models and value objects
│   │   ├── __init__.py
│   │   └── models.py              # Job, NaukriSession, ApplicationHistory dataclasses
│   │
│   ├── storage/                   # Persistence & data repositories
│   │   ├── __init__.py
│   │   ├── applied_jobs_repo.py   # SQLite & CSV deduplication store
│   │   ├── token_pool_repo.py     # SQLite nkparam pool
│   │   └── cache_repo.py          # JSON cache management (score & QA caches)
│   │
│   ├── integrations/              # External service adapters
│   │   ├── __init__.py
│   │   ├── naukri/                # Naukri internal API integrations
│   │   │   ├── __init__.py
│   │   │   ├── session.py         # Session builder (httpcloak / curl_cffi)
│   │   │   ├── auth.py            # Login, cookie session, OTP verify
│   │   │   ├── profile.py         # Headline update, resume upload, profile ID
│   │   │   ├── jobs.py            # Search, recommended, details, apply HTTP calls
│   │   │   ├── crypto.py          # nkparam RSA signing & BotGuard vid generator
│   │   │   └── extractors.py      # Form key discovery from JavaScript bundles
│   │   │
│   │   ├── ai/                    # LLM scoring & questionnaire integration
│   │   │   ├── __init__.py
│   │   │   └── client.py          # OpenRouter / OpenAI chat completions client
│   │   │
│   │   └── telegram/              # Telegram notifications
│   │       ├── __init__.py
│   │       └── client.py          # Safe HTTP client for Telegram alerts
│   │
│   ├── services/                  # Business logic services
│   │   ├── __init__.py
│   │   ├── naukri_service.py      # Unified Naukri operations facade
│   │   ├── job_matching_service.py# Multi-stage heuristic & AI filter pipeline
│   │   ├── questionnaire_service.py # 4-tier screening questionnaire resolver
│   │   ├── application_service.py # Core search -> score -> apply orchestrator
│   │   └── profile_service.py     # Profile headline & resume bump service
│   │
│   ├── automation/                # Scheduling & automated runners
│   │   ├── __init__.py
│   │   ├── scheduler.py           # APScheduler background runner with mutex
│   │   └── cron_installer.py      # Crontab line generator & installer
│   │
│   └── web/                       # Local web services
│       ├── __init__.py
│       ├── server.py              # Hardened local HTTP server (port 8765)
│       └── handlers.py            # REST endpoints for setup & dashboard APIs
│
├── frontend/                      # Web UI Assets
│   ├── templates/                 # Clean HTML templates
│   │   ├── setup_wizard.html      # 5-step browser setup wizard
│   │   └── dashboard.html         # Visual analytics dashboard with Chart.js
│   └── static/                    # CSS, JS, Assets
│       ├── css/
│       │   └── style.css          # Design system & dark mode tokens
│       └── js/
│           ├── setup_wizard.js    # Multi-step wizard frontend controller
│           └── dashboard.js       # Chart.js initialization & data rendering
│
├── cron/                          # Backward-compatibility shims
│   ├── __init__.py
│   ├── scheduler.py
│   ├── profile_updater.py
│   └── telegram_alert.py
│
├── src/                           # Backward-compatibility import shims
│   ├── client/
│   ├── config/
│   ├── exceptions/
│   ├── models/
│   └── utils/
│
├── tests/                         # Comprehensive Automated Test Suite
│   ├── __init__.py
│   ├── unit/                      # Unit tests (offline, fast, mocked)
│   │   ├── test_config.py
│   │   ├── test_crypto.py
│   │   ├── test_filter_pipeline.py
│   │   ├── test_logging.py
│   │   ├── test_models.py
│   │   └── test_storage.py
│   └── integration/               # Integration tests
│       ├── test_job_service.py
│       ├── test_questionnaire.py
│       └── test_web_server.py
│
├── logs/                          # Rotating log files (gitignored)
│   └── noperi.log
│
└── docs/                          # Architecture & Audit Documentation
    ├── REVERSE_ENGINEERING.md
    ├── ARCHITECTURE.md
    ├── SECURITY_AUDIT.md
    ├── SCHEDULER_ANALYSIS.md
    └── SETUP.md
```

---

## 4. Key Subsystem Specifications

### 4.1 Configuration Management (`backend/core/config.py`)
- Employs a single `AppConfig` class with typed accessors.
- Resolves `.env` with fallback: `NAUKRI_USERNAME` -> `USERNAME`.
- Validates required fields upon pipeline initialization.
- Deep-merges defaults with `config.json` so missing keys never raise `KeyError`.

### 4.2 Structured Logging & Secret Masking (`backend/core/logging.py`)
- Standardizes on Python's `logging` library.
- Formatter: `%(asctime)s | %(levelname)-8s | [%(name)s:%(funcName)s] %(message)s`.
- Custom `SecretMaskingFilter` automatically replaces:
  - Bearer tokens (`Bearer ey...`, `nauk_at=...`)
  - Passwords (`password="***"`, `PASSWORD=***`)
  - API keys (`sk-or-v1-...`, `sk-...`, Telegram Bot tokens)
- Handlers:
  - Console `StreamHandler` with clean ANSI formatting.
  - Rotating `RotatingFileHandler` writing to `logs/noperi.log` (5 MB max, 5 backup files).

### 4.3 Deduplication & Persistence Layer (`backend/storage/applied_jobs_repo.py`)
- Primary key: 16-character SHA-256 hash of `job_id|company.lower().strip()`.
- Thread-safe SQLite transactions.
- Dual-write to `applied_jobs.csv` for human inspection.
- Legacy fallback query: checks both `hash = ?` and `job_id = ?` to prevent duplicate applications for historical records.

---

## 5. Security Architecture

1. **Local Web Binding**: All local servers bind strictly to `127.0.0.1`.
2. **CORS Restrictions**: Wildcard CORS (`*`) is eliminated; responses only accept requests from `127.0.0.1:8765`.
3. **Session Token Isolation**: Session cookies (`nauk_at`, `nauk_rt`) are cached in a dedicated `.session.json` with strict file permissions, leaving `config.json` free of sensitive tokens.
4. **Credential Redaction**: Zero credentials or tokens are printed or logged.
