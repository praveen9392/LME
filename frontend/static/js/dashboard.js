// Dashboard Live Controller
document.addEventListener("DOMContentLoaded", () => {
  fetchDashboardData();
});

async function fetchDashboardData() {
  try {
    const res = await fetch("/api/dashboard-data");
    if (!res.ok) throw new Error("Failed to load dashboard data");
    const data = await res.json();
    renderStats(data.stats);
    renderCharts(data.daily, data.top_companies);
    renderTable(data.recent_jobs);
  } catch (err) {
    console.error("Dashboard data load error:", err);
    document.getElementById("jobs-table-body").innerHTML = `
      <tr>
        <td colspan="5" style="text-align: center; color: var(--warn); padding: 24px;">
          No applications recorded yet or server offline. Run <code>python apply_agent.py</code> to apply to jobs.
        </td>
      </tr>
    `;
  }
}

function renderStats(stats = {}) {
  document.getElementById("stat-total").textContent = stats.total || 0;
  document.getElementById("stat-high").textContent = stats.high || 0;
  document.getElementById("stat-mid").textContent = stats.mid || 0;
  document.getElementById("stat-low").textContent = stats.low || 0;
  document.getElementById("stat-noscore").textContent = stats.no_score || 0;
}

function renderCharts(daily = [], topCo = []) {
  const chartOptions = {
    responsive: true,
    plugins: { legend: { display: false } },
    scales: {
      x: {
        ticks: { color: "#8b949e", maxRotation: 45 },
        grid: { color: "#30363d" }
      },
      y: {
        ticks: { color: "#8b949e", precision: 0 },
        grid: { color: "#30363d" }
      }
    }
  };

  // Daily applications bar chart
  const days = daily.map(d => d.day);
  const counts = daily.map(d => d.count);
  const ctxDaily = document.getElementById("chart-daily");
  if (ctxDaily) {
    new Chart(ctxDaily, {
      type: "bar",
      data: {
        labels: days,
        datasets: [{
          data: counts,
          backgroundColor: "#1f6feb",
          borderRadius: 4
        }]
      },
      options: chartOptions
    });
  }

  // Top companies horizontal bar chart
  const companies = topCo.map(c => c.company);
  const coCounts = topCo.map(c => c.count);
  const ctxCo = document.getElementById("chart-companies");
  if (ctxCo) {
    new Chart(ctxCo, {
      type: "bar",
      data: {
        labels: companies,
        datasets: [{
          data: coCounts,
          backgroundColor: "#388bfd",
          borderRadius: 4
        }]
      },
      options: {
        ...chartOptions,
        indexAxis: "y"
      }
    });
  }
}

function renderTable(jobs = []) {
  const tbody = document.getElementById("jobs-table-body");
  const countSpan = document.getElementById("record-count");
  if (countSpan) countSpan.textContent = `Showing last ${jobs.length} applications`;

  if (!jobs || jobs.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="5" style="text-align: center; color: var(--fg-m); padding: 24px;">
          No applications recorded yet.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = jobs.map(j => {
    const s = j.ai_score;
    let pillClass = "ns";
    let scoreDisplay = "—";
    if (s !== null && s !== undefined && s !== "") {
      const num = parseInt(s, 10);
      scoreDisplay = num;
      pillClass = num >= 70 ? "hi" : num >= 50 ? "mid" : "lo";
    }

    const dateStr = (j.applied_at || "").substring(0, 10);
    return `
      <tr>
        <td><strong>${escapeHtml(j.title || "Untitled")}</strong></td>
        <td style="color: var(--warn);">${escapeHtml(j.company || "N/A")}</td>
        <td>${escapeHtml(j.location || "N/A")}</td>
        <td><span class="pill ${pillClass}">${scoreDisplay}</span></td>
        <td style="color: var(--fg-m);">${dateStr}</td>
      </tr>
    `;
  }).join("");
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
