# SECURITY AUDIT REPORT
## Naukri Job Application Automation Agent

**Audit Date:** 2026-11-07  
**Auditor:** Senior Security Engineer & Code Quality Specialist  
**Classification Standards:** OWASP Top 10, CWE / SANS Top 25  

---

## 1. Executive Summary

A comprehensive security audit of the Naukri Job Application Automation codebase was conducted. The application operates as a headless agent handling highly sensitive user credentials (Naukri login, OpenRouter/OpenAI API keys, Telegram Bot tokens), personal identifiable information (PII) including resumes, compensation, and career history, and interacts with third-party external APIs.

Multiple vulnerabilities and weaknesses across credential storage, token exposure, local web server authorization, and environment variable resolution were identified and classified below.

---

## 2. Findings Matrix

| ID | Finding | Severity | Status | Remediation Required |
|---|---|---|---|---|
| **SEC-01** | Session Bearer Tokens Persisted in `config.json` | **HIGH** | Open | Move session cookies to `.env` or dedicated restricted cache, not world-readable JSON config. |
| **SEC-02** | Unauthenticated Local Web Setup Endpoint with Wildcard CORS | **HIGH** | Open | Restrict CORS to `localhost` origin; bind strictly to `127.0.0.1`; validate request origins. |
| **SEC-03** | Sensitive Credential Exposure via Debug `print()` and Unfiltered Logging | **MEDIUM** | Open | Replace `print(res.content)` with safe structured logging; implement secret masking filter for passwords, tokens, and cookies. |
| **SEC-04** | Windows OS Environment Variable Collision (`USERNAME`) | **MEDIUM** | Open | Prioritize `NAUKRI_USERNAME` over generic `USERNAME` to prevent reading Windows OS username. |
| **SEC-05** | Missing CSRF / Origin Protection on Web Configuration Handlers | **MEDIUM** | Open | Add one-time session token or verify `Host` / `Origin` headers on all POST endpoints. |
| **SEC-06** | Transmission of PII to Third-Party LLM Endpoints | **LOW** | Open | Clearly document data transmitted to OpenRouter / OpenAI; sanitize unnecessary personal details in scoring prompts. |
| **SEC-07** | Use of `eval()` in Node.js Driver Script for BotGuard SDK | **LOW** | Open | `eval()` runs local bundled `botguardSdk_v1.min.js`; restrict file path validation and verify SDK integrity (hash check). |
| **SEC-08** | Plaintext Storage of Credentials in `.env` | **INFORMATIONAL** | Accepted | Ensure `.gitignore` enforces exclusion of `.env`, `*.db`, and token caches; document secure file permissions. |

---

## 3. Detailed Vulnerability Analyses

### SEC-01: Session Bearer Tokens Persisted in `config.json`
- **Severity**: **HIGH**
- **CWE**: CWE-312 (Cleartext Storage of Sensitive Information)
- **Description**: In `src/utils/web_setup.py`, lines 1471 & 1570–1575:
  ```python
  def _store_session(nauk_at: str, nauk_rt: str):
      cfg = ConfigManager()
      data = _deep_merge(cfg.load(), {'session': {'nauk_at': nauk_at, 'nauk_rt': nauk_rt}})
      cfg.save(data)
  ```
  This writes the full authentication Bearer token (`nauk_at`) and refresh token into `config.json`. While `.env` is typically guarded, users often share or commit configuration files (`config.json` or sample templates), risking account takeover.
- **Remediation**:
  Store session tokens in a dedicated, explicitly ignored `.session_cache.json` or within `.env` directly, never in the general configuration file.

---

### SEC-02: Unauthenticated Local Web Server with Wildcard CORS
- **Severity**: **HIGH**
- **CWE**: CWE-346 (Origin Validation Error), CWE-306 (Missing Authentication for Critical Function)
- **Description**: The setup wizard runs an `HTTPServer` on port 8765. The HTTP response headers in `web_setup.py` set:
  ```python
  self.send_header('Access-Control-Allow-Origin', '*')
  ```
  Because the server is bound to all local interfaces and permits all cross-origin requests, any malicious website opened in the user's browser while the setup wizard is running could execute JavaScript to `POST /api/save` and exfiltrate or alter API keys and credentials.
- **Remediation**:
  1. Bind strictly to `127.0.0.1` rather than `0.0.0.0` or hostname aliases.
  2. Remove `Access-Control-Allow-Origin: *` or restrict it strictly to `http://127.0.0.1:8765`.
  3. Validate the `Host` and `Origin` headers on all incoming requests.

---

### SEC-03: Sensitive Credential Exposure via Debug Printing & Logging
- **Severity**: **MEDIUM**
- **CWE**: CWE-532 (Insertion of Sensitive Information into Log File)
- **Description**: In `src/client/naukri_client.py` line 179:
  ```python
  if not res.ok:
      print(res.content)
      raise NaukriAuthError("Login failed")
  ```
  If login fails due to an authentication error, the HTTP response body may contain user account identifiers, session tokens, or error traces. Furthermore, uncaught exceptions printed to console or logs can contain full HTTP request headers including Authorization Bearer tokens.
- **Remediation**:
  Implement a custom logging filter that redacts tokens (`Bearer [REDACTED]`), passwords, and API keys before outputting to console or file logs.

---

### SEC-04: Windows OS Environment Variable Collision (`USERNAME`)
- **Severity**: **MEDIUM**
- **CWE**: CWE-436 (Interpretation Conflict)
- **Description**: On Microsoft Windows systems, `%USERNAME%` is an automatic environment variable containing the active Windows account username (e.g. `PRAVEEN`). In `cron/profile_updater.py` line 57:
  ```python
  username = os.getenv("USERNAME", "")
  ```
  If `.env` uses `USERNAME=user@example.com`, `os.getenv("USERNAME")` can unexpectedly resolve to the Windows OS login name instead of the Naukri user email, causing authentication failures or leaking local OS usernames in external network requests.
- **Remediation**:
  Standardize on `NAUKRI_USERNAME` throughout all modules, falling back to `USERNAME` only if `NAUKRI_USERNAME` is unset.

---

### SEC-06: Third-Party Data Transmission & PII Boundaries
- **Severity**: **LOW / INFORMATIONAL**
- **Data Flow Verification**:
  1. **Naukri APIs** (`naukri.com`, `naukimg.com`): Receives credentials, resume PDF, profile details, and screening question answers.
  2. **OpenRouter / OpenAI APIs** (`openrouter.ai`, `openai.com`): Receives the candidate profile text from `user_prompt.md`, job descriptions, and questionnaire text. (Candidate resume PDF is NOT sent to LLMs; only text prompts).
  3. **Telegram Bot API** (`api.telegram.org`): Receives job application summaries, job titles, employer names, and error messages.

---

## 4. Security Action Plan

1. **Centralize & Mask Logging**: Ensure zero credentials, tokens, or personal identifiers appear in console or rotating logs.
2. **Harden Web Setup**: Bind to `127.0.0.1`, remove wildcard CORS, and check origins.
3. **Environment Standardization**: Use `NAUKRI_USERNAME`, `NAUKRI_PASSWORD`, `OPENROUTER_API_KEY`, `OPEN_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
4. **Secure Token Storage**: Store cached session tokens in a dedicated `.session.json` that is strictly gitignored.
