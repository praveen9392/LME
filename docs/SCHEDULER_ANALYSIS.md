# SCHEDULER & AUTOMATION AUDIT
## Naukri Job Application Automation Agent

**Document Version:** 1.0.0  
**Status:** Audit Completed  
**Scope:** Background tasks, cron jobs, schedulers, automated runners  

---

## 1. Executive Summary

The application employs two independent automation architectures:
1. **Internal APScheduler Daemon** (`cron/scheduler.py`): An in-process Python daemon utilizing `BlockingScheduler` from APScheduler 3.x to execute profile updates and apply runs on recurring intervals and cron schedules.
2. **Operating System Crontab Runner** (`apply_agent.py` via `web_setup.py` / CLI): An external OS-level cron schedule generated for Linux/macOS systems executing `python apply_agent.py` as a batch process.

Both approaches are analyzed below for timing, concurrency, network activity, fault tolerance, and recommended enhancements.

---

## 2. Inventory of Automated Jobs

### 2.1 Profile Freshness Updater (`job_profile_update`)

- **Implementation**: `cron/profile_updater.py:run_profile_update()`
- **Trigger**: `IntervalTrigger(hours=interval_h, timezone=tz)`
- **Default Schedule**: Every 6 hours (`cron.profile_update.interval_hours: 6`)
- **Business Purpose**: Naukri recruiter search results rank candidates by "Last Modified" timestamp. Periodically updating the profile headline and/or re-uploading the resume keeps the candidate at the top of recruiter searches.
- **External Network Calls**:
  - `POST /central-login-services/v1/login` (Authentication)
  - `GET /cloudgateway-mynaukri/resman-aggregator-services/v0/users/self/dashboard` (Profile ID fetch)
  - `POST /cloudgateway-mynaukri/resman-aggregator-services/v1/users/self/fullprofiles` (Headline update)
  - `POST https://filevalidation.naukri.com/file` (Resume file validation, if configured)
  - `POST /cloudgateway-mynaukri/resman-aggregator-services/v0/users/self/profiles/{id}/advResume` (Resume update, if configured)
  - `POST https://api.telegram.org/bot<TOKEN>/sendMessage` (Status notification)
- **Fault Handling**:
  - Wrapped in top-level `try...except Exception`.
  - Sends a Telegram alert on error if configured (`alert_error`).
  - Does not crash the enclosing scheduler process.

### 2.2 Scheduled Job Apply Agent (`job_apply_agent`)

- **Implementation**: `apply_agent.py:run_agent()`
- **Trigger**: `CronTrigger(hour=h, minute=m, day_of_week=days, timezone=tz)`
- **Default Schedule**: 08:00 AM, Monday through Friday, Timezone: `Asia/Kolkata`
- **Business Purpose**: Fetches newly posted jobs, filters and scores them via AI, applies to eligible jobs, and records history.
- **External Network Calls**:
  - `POST /central-login-services/v1/login` (Authentication)
  - `GET /jobapi/v3/search` (Search queries with `nkparam` header)
  - `GET /jobapi/v4/job/{id}` (External apply detection and detail retrieval)
  - `POST https://openrouter.ai/api/v1/chat/completions` or `https://api.openai.com/v1/chat/completions` (Job scoring & questionnaire answering)
  - `POST /cloudgateway-workflow/workflow-services/apply-workflow/v1/apply` (Application submission)
  - `POST https://api.telegram.org/bot<TOKEN>/sendMessage` (Run start, job applied, failure, summary alerts)
- **Fault Handling**:
  - Job iteration is guarded on a per-job basis: failing an application does not abort the remaining jobs.
  - Schedular-level execution is caught and logged, firing Telegram error alerts if enabled.

---

## 3. Concurrency & Collision Risks

| Risk Scenario | Current Behavior | Impact | Architectural Remediation |
|---|---|---|---|
| **Multiple Scheduler Processes** | No lock file or PID check exists. Starting `scheduler.py` multiple times creates concurrent worker instances. | Concurrent sessions can invalidate Naukri auth tokens and exceed rate limits. | Implement file-based PID lock (`FileLock` / `fcntl` / `msvcrt`) to ensure single-instance execution. |
| **Crontab Overlap** | A long-running apply run might overlap with the next scheduled run. | Duplicate job fetches and possible race conditions on SQLite writes. | Use non-blocking process locks or `flock` in crontab command generation. |
| **Session Invalidation** | Profile updater and Apply agent share the same account credentials. | In headless mode, rapid re-authentication may trigger Naukri's BotGuard MFA challenge. | Centralize token caching and reuse valid bearer tokens (`nauk_at`) until expiration. |

---

## 4. Configuration Schema for Schedulers

```json
{
  "cron": {
    "profile_update": {
      "enabled": true,
      "interval_hours": 6
    },
    "apply": {
      "enabled": true,
      "schedule": "08:00",
      "days": "mon-fri",
      "timezone": "Asia/Kolkata"
    }
  }
}
```

---

## 5. Summary & Recommendations

1. **Preserve Current Execution Intervals**: Keep the default 6-hour interval for profile refreshes and 08:00 Mon-Fri for applications.
2. **Cross-Platform Scheduling Support**: Support both APScheduler (cross-platform daemon) and OS-level crontab/Task Scheduler export.
3. **Instance Mutex / Single-Instance Guard**: Provide an automated lock mechanism to prevent accidental duplicate background workers.
4. **Structured Job Logging**: Transition scheduler log messages from standard output to dedicated rotating log files (`logs/scheduler.log`).
