# SETUP AND INSTALLATION GUIDE
## Naukri Job Application Automation Agent

---

## 1. Prerequisites

Before setting up the project, ensure your environment meets the following requirements:

1. **Python**: Python 3.10, 3.11, 3.12, or 3.13 (64-bit).
2. **Node.js**: Node.js 14+ installed and available on `PATH`. (Required for executing the BotGuard `vid` token generator).
3. **Operating System**:
   - Windows 10/11
   - Linux (Ubuntu, Debian, Fedora, Arch)
   - macOS

---

## 2. Installation Steps

### Step 1: Clone the Repository
```bash
git clone <repository_url>
cd LME
```

### Step 2: Create and Activate a Virtual Environment
**On Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**On Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3: Install Required Dependencies
```bash
pip install -r requirements.txt
```

---

## 3. Configuration

### Step 4: Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
# Windows
copy .env.example .env

# Linux / macOS
cp .env.example .env
```

Edit `.env` with your actual credentials:
```env
# Naukri Credentials (Required for automated login)
NAUKRI_USERNAME=your_naukri_email@example.com
PASSWORD=your_naukri_password

# AI Scoring & Questionnaire Resolution (Optional - OpenRouter or OpenAI)
OPENROUTER_API_KEY=sk-or-v1-...
# or direct OpenAI:
# OPEN_API_KEY=sk-...

# Telegram Notifications (Optional)
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
TELEGRAM_CHAT_ID=your_numeric_chat_id
```

> **Note on Windows**: Standardize on `NAUKRI_USERNAME` instead of `USERNAME` to avoid collisions with the Windows OS user account.

---

## 4. Running the Application

### 4.1 First Run — Setup Wizard
To configure your candidate profile, target roles, tech stack, locations, and scoring preferences via the interactive browser wizard:
```bash
python apply_agent.py --setup
```
This launches a local, secure setup server at `http://127.0.0.1:8765`. Follow the 5-step wizard and click **Save & Close**.

### 4.2 Standard Application Run
Execute a full search, score, and apply run:
```bash
python apply_agent.py
```
Or on Windows:
```cmd
run.bat
```

### 4.3 View Analytics Dashboard
Open the interactive dashboard displaying statistics, charts (Chart.js), score tiers, and the recent application table:
```bash
python apply_agent.py --dashboard
```

### 4.4 List and Manage Applied Jobs
View the 50 most recently applied jobs:
```bash
python apply_agent.py --list-applied
```

Allow re-applying to a specific job by removing its hash:
```bash
python apply_agent.py --remove-job <HASH>
```

### 4.5 Manage Company and Title Veto Lists
```bash
# List all current vetoes
python apply_agent.py --veto list

# Add or remove company veto
python apply_agent.py --veto add-company "Infosys"
python apply_agent.py --veto remove-company "Infosys"

# Add or remove title veto
python apply_agent.py --veto add-title "walk-in"
python apply_agent.py --veto remove-title "walk-in"
```

---

## 5. Background Schedulers & Automations

### 5.1 Internal APScheduler Daemon
Runs profile headline bumping every 6 hours and job applications every morning at 08:00 AM (Mon–Fri):
```bash
python cron/scheduler.py
```

### 5.2 Standalone Profile Freshness Updater
Manually bump headline and re-upload resume:
```bash
python cron/profile_updater.py
```

---

## 6. Running Tests

Execute the comprehensive test suite:
```bash
# Run all unit tests (offline, mocked)
pytest tests/unit/ -v

# Run integration tests
pytest tests/integration/ -v

# Run full test suite
pytest tests/ -v
```

---

## 7. Logs & Troubleshooting

- **Log File Location**: `backend/logs/app.log` (automatically created and rotated).
- **Console Output**: Color-coded, human-readable execution status.
- **Sensitive Data**: Passwords, bearer tokens, and API keys are automatically redacted from all log outputs.
