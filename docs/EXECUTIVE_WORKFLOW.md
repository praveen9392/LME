# LME Automation Agent — Executive & Non-Technical Overview

This guide explains how the **LME Job Application Automation Agent** works using clear visual diagrams and non-technical language for Project Managers, recruiters, and stakeholders.

---

## 1. High-Level Concept

Think of LME as an **intelligent digital assistant** that handles job hunting on Naukri 24/7 without opening a browser:

```mermaid
flowchart LR
    A["👤 Candidate (Setup Once)"] --> B["⚙️ LME Automation Agent"]
    B --> C["🔍 Naukri Search & Screening"]
    C --> D["🧠 Free AI Fit Scoring"]
    D --> E["📝 Auto-Answers Questionnaires"]
    E --> F["✅ 1-Click Job Submission"]
    F --> G["📱 Instant Telegram Notifications"]
```

---

## 2. End-to-End Workflow Diagram

```mermaid
flowchart TD
    subgraph S1["1. Candidate Configuration"]
        A["Candidate enters credentials & preferences"] --> B["Stores resume & target keywords"]
        B --> C["Sets criteria: CTC, Experience, Locations"]
    end

    subgraph S2["2. Job Discovery & Security"]
        C --> D["Automated Headless Login"]
        D --> E["Search Naukri for Matching Vacancies"]
        E --> F["Fetch Recommended Jobs Feed"]
    end

    subgraph S3["3. Smart Multi-Stage Filtering"]
        F --> G{"Already Applied?"}
        G -- "Yes" --> H["⏭️ Skip Job (No Duplicates)"]
        G -- "No" --> I{"In Veto Blacklist?"}
        I -- "Yes (e.g. Intern/Unwanted Firm)" --> J["⛔ Reject Job"]
        I -- "No" --> K{"Experience Matches?"}
        K -- "No (e.g. 5+ yrs required)" --> L["⛔ Skip Job"]
        K -- "Yes" --> M["Pass to AI Evaluation"]
    end

    subgraph S4["4. Free AI Scoring Engine"]
        M --> N["OpenRouter Free AI evaluates Job Fit (0-100)"]
        N --> O{"Score >= Threshold (e.g. 50+)?"}
        O -- "No (Poor match)" --> P["⏭️ Log Reason & Skip"]
        O -- "Yes (Strong match)" --> Q["Prepare Application"]
    end

    subgraph S5["5. Automated Submission & Tracking"]
        Q --> R{"Employer Questionnaire?"}
        R -- "Yes" --> S["Answer questions using Candidate Profile & Cache"]
        R -- "No" --> T["Direct 1-Click Apply"]
        S --> T
        T --> U["Submit Application to Naukri"]
        U --> V["Record in SQLite DB & CSV"]
        U --> W["Send Real-time Telegram Alert"]
    end
```

---

## 3. How It Works (For Non-Tech Stakeholders)

| Stage | What Happens | Why It Matters |
| :--- | :--- | :--- |
| **1. Fast & Headless Login** | Connects to Naukri securely in milliseconds without opening heavy browser windows. | Fast, lightweight, and uses minimal computer memory. |
| **2. Intelligent Filtering** | Checks jobs against your blacklist (e.g. internships, unwanted companies) and years of experience. | Prevents spam applications and protects your professional profile. |
| **3. Duplicate Defense** | Generates a 16-character digital fingerprint for every job vacancy. | Ensures you **never** accidentally re-apply to the same company posting twice. |
| **4. Free AI Matching ($0 Cost)** | Evaluates the job description against your resume and assigns a fit score (0–100). | Only roles with a genuine match get applied to. |
| **5. Screening Forms** | Automatically fills in questions like notice period, location preference, and expected CTC. | Handles complex multi-step application forms effortlessly. |
| **6. Profile Freshness & Alerts** | Periodically updates your profile headline on Naukri and sends real-time Telegram updates. | Keeps your resume at the top of recruiter search results 24/7. |
