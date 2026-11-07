// Setup Wizard Frontend Controller
let currentStep = 1;
let accountDone = false;
let accountType = '';
let storedSession = {};
let serverEnv = {};
const qaPatterns = [];
const tagSet = new Set(['Node.js', 'Python', 'MongoDB', 'REST APIs', 'AWS', 'Docker']);

const MODELS = {
  openrouter: [
    { v: 'anthropic/claude-3.5-haiku', l: 'claude-3.5-haiku — fast + cheap' },
    { v: 'anthropic/claude-3.5-sonnet', l: 'claude-3.5-sonnet — balanced' },
    { v: 'anthropic/claude-sonnet-4-5', l: 'claude-sonnet-4-5 — latest' },
    { v: 'openai/gpt-4o-mini', l: 'gpt-4o-mini — cheapest' },
    { v: 'openai/gpt-4o', l: 'gpt-4o' },
    { v: 'google/gemini-2.0-flash-001', l: 'gemini-2.0-flash' },
    { v: 'meta-llama/llama-3.1-8b-instruct:free', l: 'llama-3.1-8b — FREE' },
  ],
  openai: [
    { v: 'gpt-4o-mini', l: 'gpt-4o-mini — cheapest' },
    { v: 'gpt-4o', l: 'gpt-4o' },
  ]
};

document.addEventListener("DOMContentLoaded", () => {
  initNavigation();
  initTabs();
  initTags();
  initRadioGroups();
  initCollapsibles();
  initDayToggles();
  initQA();
  loadConfig();
});

function initNavigation() {
  document.querySelectorAll(".step").forEach(el => {
    el.addEventListener("click", () => {
      const target = parseInt(el.dataset.s, 10);
      if (target < currentStep || accountDone) goTo(target);
    });
  });

  document.getElementById("s1-next").addEventListener("click", () => goTo(2));
  document.getElementById("s2-back").addEventListener("click", () => goTo(1));
  document.getElementById("s2-next").addEventListener("click", () => goTo(3));
  document.getElementById("s3-back").addEventListener("click", () => goTo(2));
  document.getElementById("s3-next").addEventListener("click", () => goTo(4));
  document.getElementById("s4-back").addEventListener("click", () => goTo(3));
  document.getElementById("s4-next").addEventListener("click", () => {
    buildSummary();
    goTo(5);
  });
  document.getElementById("s5-back").addEventListener("click", () => goTo(4));
  document.getElementById("btn-save").addEventListener("click", saveAll);
}

function goTo(n) {
  document.getElementById(`s${currentStep}`).classList.remove("active");
  document.querySelectorAll(".step").forEach(el => {
    const s = parseInt(el.dataset.s, 10);
    el.classList.toggle("done", s < n);
    el.classList.toggle("active", s === n);
  });
  currentStep = n;
  document.getElementById(`s${n}`).classList.add("active");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function initTabs() {
  document.querySelectorAll("#acct-tabs .tab").forEach(tab => {
    tab.addEventListener("click", () => {
      document.querySelectorAll("#acct-tabs .tab").forEach(t => t.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
      tab.classList.add("active");
      document.getElementById(`tab-${tab.dataset.tab}`).classList.add("active");
    });
  });

  document.getElementById("btn-login").addEventListener("click", async () => {
    const btn = document.getElementById("btn-login");
    const msg = document.getElementById("login-msg");
    const email = document.getElementById("email").value.trim();
    const pw = document.getElementById("password").value;
    if (!email || !pw) {
      setMsg(msg, "Please enter email and password.", "err");
      return;
    }
    btn.disabled = true;
    btn.textContent = "Connecting...";
    setMsg(msg, "Authenticating with Naukri...", "info");
    try {
      const res = await post("/api/login", { email, password: pw });
      if (res.ok) {
        storedSession = { nauk_at: res.nauk_at, nauk_rt: res.nauk_rt || "" };
        accountType = "login";
        markAcctDone(`Connected as ${email}`);
        msg.hidden = true;
      } else {
        setMsg(msg, `✕ ${res.error || "Login failed"}`, "err");
        btn.disabled = false;
        btn.textContent = "Connect to Naukri";
      }
    } catch (e) {
      setMsg(msg, "✕ Could not connect to setup server.", "err");
      btn.disabled = false;
      btn.textContent = "Connect to Naukri";
    }
  });

  document.getElementById("btn-cookies").addEventListener("click", async () => {
    const btn = document.getElementById("btn-cookies");
    const msg = document.getElementById("cookies-msg");
    const at = document.getElementById("nauk_at").value.trim();
    const rt = document.getElementById("nauk_rt").value.trim();
    if (!at) {
      setMsg(msg, "nauk_at is required.", "err");
      return;
    }
    btn.disabled = true;
    btn.textContent = "Saving...";
    try {
      const res = await post("/api/cookies", { nauk_at: at, nauk_rt: rt });
      if (res.ok) {
        storedSession = { nauk_at: at, nauk_rt: rt };
        accountType = "cookies";
        markAcctDone("Session cookies saved");
        msg.hidden = true;
      } else {
        setMsg(msg, `✕ ${res.error || "Save failed"}`, "err");
        btn.disabled = false;
        btn.textContent = "Save Cookies";
      }
    } catch (e) {
      setMsg(msg, "✕ Server error.", "err");
      btn.disabled = false;
      btn.textContent = "Save Cookies";
    }
  });
}

function markAcctDone(title, detail = "") {
  accountDone = true;
  const b = document.getElementById("acct-badge");
  b.innerHTML = `<div class="badge-dot"></div><div><strong>${title}</strong>${detail ? `<div style="font-size:12px;opacity:.8">${detail}</div>` : ""}</div>`;
  b.hidden = false;
  document.getElementById("acct-tabs").style.display = "none";
  document.getElementById("s1-next").disabled = false;
  document.getElementById("acct-hint").textContent = "";
}

function initTags() {
  const box = document.getElementById("stack-box");
  const inp = document.getElementById("stack-inp");
  function render() {
    box.querySelectorAll(".chip").forEach(c => c.remove());
    [...tagSet].forEach(t => {
      const chip = document.createElement("span");
      chip.className = "chip";
      chip.innerHTML = `${escapeHtml(t)}<span class="chip-x" data-t="${escapeHtml(t)}">×</span>`;
      box.insertBefore(chip, inp);
    });
  }
  box.addEventListener("click", e => {
    if (e.target.classList.contains("chip-x")) {
      tagSet.delete(e.target.dataset.t);
      render();
    } else {
      inp.focus();
    }
  });
  inp.addEventListener("keydown", e => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      const v = e.target.value.replace(",", "").trim();
      if (v) {
        tagSet.add(v);
        render();
        e.target.value = "";
      }
    } else if (e.key === "Backspace" && !e.target.value && tagSet.size) {
      const last = [...tagSet].pop();
      tagSet.delete(last);
      render();
    }
  });
  render();
}

function initRadioGroups() {
  ["role-group", "provider-group"].forEach(gid => {
    document.querySelectorAll(`#${gid} .radio-opt`).forEach(opt => {
      opt.addEventListener("click", () => {
        document.querySelectorAll(`#${gid} .radio-opt`).forEach(o => o.classList.remove("sel"));
        opt.classList.add("sel");
        if (gid === "provider-group") reloadModels();
      });
    });
  });

  document.getElementById("score-thr").addEventListener("input", e => {
    document.getElementById("thr-val").textContent = e.target.value;
  });
}

function reloadModels() {
  const selProv = document.querySelector('input[name="provider"]:checked').value;
  const sel = document.getElementById("model-select");
  sel.innerHTML = "";
  (MODELS[selProv] || []).forEach(m => {
    const o = document.createElement("option");
    o.value = m.v;
    o.textContent = m.l;
    sel.appendChild(o);
  });
}

function initCollapsibles() {
  function wire(cbId, blockId) {
    const cb = document.getElementById(cbId);
    const block = document.getElementById(blockId);
    cb.addEventListener("change", () => {
      block.className = cb.checked ? "collapser open" : "collapser shut";
    });
  }
  wire("cron-enable", "cron-block");
  wire("tg-enable", "tg-block");
}

function initDayToggles() {
  document.querySelectorAll(".day-btn").forEach(b => {
    b.addEventListener("click", () => {
      b.classList.toggle("on");
      updateCronLine();
    });
  });
  document.getElementById("cron-time").addEventListener("input", updateCronLine);
  document.getElementById("copy-cron").addEventListener("click", () => {
    const text = document.getElementById("cron-code").textContent;
    navigator.clipboard.writeText(text).then(() => {
      const btn = document.getElementById("copy-cron");
      btn.textContent = "Copied!";
      setTimeout(() => btn.textContent = "Copy", 2000);
    });
  });
  document.getElementById("btn-install-cron").addEventListener("click", async () => {
    const line = document.getElementById("cron-code").textContent.trim();
    const msg = document.getElementById("cron-install-msg");
    const btn = document.getElementById("btn-install-cron");
    btn.disabled = true;
    try {
      const res = await post("/api/install-cron", { cron_line: line });
      if (res.ok) {
        setMsg(msg, "✓ Crontab installed successfully.", "ok");
      } else {
        setMsg(msg, `✕ ${res.error || "Installation failed"}`, "err");
      }
    } catch (e) {
      setMsg(msg, "✕ Failed to contact server.", "err");
    } finally {
      btn.disabled = false;
    }
  });
}

function updateCronLine() {
  const time = document.getElementById("cron-time").value || "08:00";
  const [h, m] = time.split(":").map(Number);
  const days = [...document.querySelectorAll(".day-btn.on")].map(b => b.dataset.d);
  const dayMap = { sun: 0, mon: 1, tue: 2, wed: 3, thu: 4, fri: 5, sat: 6 };
  const nums = days.map(d => dayMap[d]).sort();
  const dExpr = nums.length === 7 ? "*" : nums.join(",");
  const cwd = serverEnv.cwd || "/path/to/LME";
  const py = serverEnv.python || "python3";
  document.getElementById("cron-code").textContent =
    `${m || 0} ${h || 8} * * ${dExpr} cd "${cwd}" && "${py}" apply_agent.py >> "${cwd}/logs/noperi.log" 2>&1`;
}

function initQA() {
  function render() {
    const list = document.getElementById("qa-list");
    list.innerHTML = "";
    qaPatterns.forEach((item, idx) => {
      const row = document.createElement("div");
      row.className = "sum-row";
      row.innerHTML = `<span>${escapeHtml(item.question)} &rarr; <strong style="color:var(--accent)">${escapeHtml(item.answer)}</strong></span><span style="cursor:pointer;color:var(--err)" data-i="${idx}">✕</span>`;
      row.querySelector("[data-i]").addEventListener("click", e => {
        qaPatterns.splice(parseInt(e.target.dataset.i, 10), 1);
        render();
      });
      list.appendChild(row);
    });
  }
  document.getElementById("qa-add").addEventListener("click", () => {
    const q = document.getElementById("qa-q").value.trim();
    const a = document.getElementById("qa-a").value.trim();
    if (q && a) {
      qaPatterns.push({ question: q, answer: a });
      render();
      document.getElementById("qa-q").value = "";
      document.getElementById("qa-a").value = "";
    }
  });
}

function buildSummary() {
  const role = document.querySelector('input[name="role"]:checked').value;
  const exp = document.getElementById("exp-years").value;
  const stack = [...tagSet].join(", ");
  const locs = document.getElementById("locations").value || "All India";
  const remote = document.getElementById("apply-remote").checked ? "Yes" : "No";
  const prov = document.querySelector('input[name="provider"]:checked').value;
  const model = document.getElementById("model-select").value;
  const thr = document.getElementById("score-thr").value;
  const limit = document.getElementById("daily-limit").value;
  const cron = document.getElementById("cron-enable").checked ? "Enabled" : "Disabled";
  const tg = document.getElementById("tg-enable").checked ? "Enabled" : "Disabled";

  const rows = [
    ["Account Status", accountDone ? "Configured" : "Incomplete"],
    ["Target Role", role.toUpperCase()],
    ["Experience", `${exp} Years`],
    ["Tech Stack", stack],
    ["Locations", locs],
    ["Include Remote", remote],
    ["AI Scoring", `${prov} (${model})`],
    ["Min Score Threshold", `${thr} / 100`],
    ["Daily Max Applications", limit],
    ["Automated Crontab", cron],
    ["Telegram Alerts", tg],
  ];

  document.getElementById("summary").innerHTML = rows.map(([k, v]) => `
    <div class="sum-row"><span class="k">${k}</span><span class="v">${escapeHtml(v)}</span></div>
  `).join("");
}

async function saveAll() {
  const btn = document.getElementById("btn-save");
  const msg = document.getElementById("save-msg");
  btn.disabled = true;
  btn.textContent = "Saving...";

  const role = document.querySelector('input[name="role"]:checked').value;
  const locs = document.getElementById("locations").value.split(",").map(s => s.trim()).filter(Boolean);
  const prov = document.querySelector('input[name="provider"]:checked').value;
  const model = document.getElementById("model-select").value;
  const apiKey = document.getElementById("api-key").value.trim();
  const tgToken = document.getElementById("tg-token").value.trim();
  const tgChat = document.getElementById("tg-chat").value.trim();

  const env_vars = {};
  if (apiKey) env_vars[prov === "openrouter" ? "OPENROUTER_API_KEY" : "OPEN_API_KEY"] = apiKey;
  if (tgToken) env_vars["TELEGRAM_BOT_TOKEN"] = tgToken;
  if (tgChat) env_vars["TELEGRAM_CHAT_ID"] = tgChat;

  const config = {
    profile: {
      role_focus: role,
      experience_years: parseInt(document.getElementById("exp-years").value, 10) || 2,
      tech_stack: [...tagSet],
      locations: locs,
      apply_remote: document.getElementById("apply-remote").checked,
      current_ctc: document.getElementById("current-ctc").value.trim() || "5",
      expected_ctc: document.getElementById("expected-ctc").value.trim() || "7",
      notice_days: parseInt(document.getElementById("notice-days").value, 10) || 30,
    },
    ai: {
      provider: prov,
      model: model,
      score_threshold: parseInt(document.getElementById("score-thr").value, 10),
      daily_apply_limit: parseInt(document.getElementById("daily-limit").value, 10) || 50,
    },
    questionnaire: {
      skip_ai: document.getElementById("skip-qa-ai").checked,
      common_qa: qaPatterns,
    },
    cron: {
      apply: {
        enabled: document.getElementById("cron-enable").checked,
        schedule: document.getElementById("cron-time").value || "08:00",
        timezone: document.getElementById("cron-tz").value,
      }
    },
    telegram: {
      enabled: document.getElementById("tg-enable").checked,
    },
    session: storedSession,
    env_vars: env_vars,
  };

  try {
    const customPrompt = document.getElementById("custom-prompt") ? document.getElementById("custom-prompt").value.trim() : "";
    if (customPrompt) {
      await post("/api/save-prompt", { prompt: customPrompt });
    }
    const res = await post("/api/save", config);
    if (res.ok) {
      setMsg(msg, "✓ Configuration successfully saved! You can close this window now.", "ok");
      btn.textContent = "Saved";
      setTimeout(() => post("/api/done", {}).catch(() => {}), 1000);
    } else {
      setMsg(msg, `✕ ${res.error || "Failed to save configuration"}`, "err");
      btn.disabled = false;
      btn.textContent = "Save & Close";
    }
  } catch (e) {
    setMsg(msg, "✕ Server error saving configuration.", "err");
    btn.disabled = false;
    btn.textContent = "Save & Close";
  }
}

async function loadConfig() {
  try {
    const res = await fetch("/api/config");
    if (!res.ok) return;
    const cfg = await res.json();
    serverEnv = cfg._env || {};
    updateCronLine();

    if (serverEnv.has_credentials) {
      markAcctDone("Credentials found in environment", "Using NAUKRI_USERNAME & PASSWORD from .env");
      goTo(2);
    } else if (cfg.session && cfg.session.nauk_at) {
      storedSession = cfg.session;
      markAcctDone("Stored session found");
    }

    if (serverEnv.has_ai_key) {
      document.getElementById("key-found-badge").hidden = false;
      document.getElementById("key-found-text").textContent = `Key already set in .env (${serverEnv.ai_key_provider})`;
    }

    if (cfg._prompt) {
      const promptEl = document.getElementById("custom-prompt");
      if (promptEl) promptEl.value = cfg._prompt;
    }

    const p = cfg.profile || {};
    if (p.experience_years) document.getElementById("exp-years").value = p.experience_years;
    if (p.notice_days) document.getElementById("notice-days").value = p.notice_days;
    if (p.current_ctc) document.getElementById("current-ctc").value = p.current_ctc;
    if (p.expected_ctc) document.getElementById("expected-ctc").value = p.expected_ctc;
    if (p.locations) document.getElementById("locations").value = p.locations.join(", ");
    if (p.tech_stack && p.tech_stack.length) {
      tagSet.clear();
      p.tech_stack.forEach(t => tagSet.add(t));
      const box = document.getElementById("stack-box");
      const inp = document.getElementById("stack-inp");
      box.querySelectorAll(".chip").forEach(c => c.remove());
      [...tagSet].forEach(t => {
        const chip = document.createElement("span");
        chip.className = "chip";
        chip.innerHTML = `${escapeHtml(t)}<span class="chip-x" data-t="${escapeHtml(t)}">×</span>`;
        box.insertBefore(chip, inp);
      });
    }

    const qa = (cfg.questionnaire || {}).common_qa || [];
    if (qa.length) {
      qa.forEach(item => qaPatterns.push(item));
      const list = document.getElementById("qa-list");
      list.innerHTML = "";
      qaPatterns.forEach((item, idx) => {
        const row = document.createElement("div");
        row.className = "sum-row";
        row.innerHTML = `<span>${escapeHtml(item.question)} &rarr; <strong style="color:var(--accent)">${escapeHtml(item.answer)}</strong></span><span style="cursor:pointer;color:var(--err)" data-i="${idx}">✕</span>`;
        row.querySelector("[data-i]").addEventListener("click", e => {
          qaPatterns.splice(parseInt(e.target.dataset.i, 10), 1);
          row.remove();
        });
        list.appendChild(row);
      });
    }
  } catch (e) {
    console.error("Config prefill error:", e);
  }
}

function setMsg(el, text, type) {
  el.className = `msg ${type}`;
  el.innerHTML = text;
  el.hidden = false;
}

function post(path, body) {
  return fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then(r => r.json());
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
