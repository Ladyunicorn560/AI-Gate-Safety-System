/**
 * attendance.js — Attendance page logic
 */

let allAttendance = [];
let attPage = 1;
const attPageSize = 20;
let gateChart = null, shiftChart = null;

// Set today as default date range
window.addEventListener("DOMContentLoaded", () => {
  const today = new Date().toISOString().split("T")[0];
  document.getElementById("filter-start").value = today;
  document.getElementById("filter-end").value   = today;
  if (authToken) loadAttendance();
});

async function loadAttendance() {
  const start = document.getElementById("filter-start").value;
  const end   = document.getElementById("filter-end").value;
  const gate  = document.getElementById("filter-gate").value;
  const search = document.getElementById("filter-search").value.toLowerCase();

  document.getElementById("att-loading").style.display = "inline-flex";

  try {
    // Load summary
    const sum = await apiFetch(`/attendance/summary`);
    document.getElementById("att-total").textContent    = sum.total_present    || 0;
    document.getElementById("att-contract").textContent = sum.contract_workers || 0;
    document.getElementById("att-oas").textContent      = sum.oas_workers      || 0;
    document.getElementById("att-gates").textContent    = sum.active_gates     || 0;

    // Load records
    let url = `/attendance/range?start=${start}&end=${end}`;
    if (gate) url += `&gate_id=${gate}`;
    const res = await apiFetch(url);
    allAttendance = res.data || [];

    // Client-side search filter
    const filtered = search
      ? allAttendance.filter(r =>
          (r.FullName    || "").toLowerCase().includes(search) ||
          (r.EmpCode     || "").toLowerCase().includes(search) ||
          (r.ContractorName || "").toLowerCase().includes(search))
      : allAttendance;

    // Type filter
    const type = document.getElementById("filter-type").value;
    const typed = type ? filtered.filter(r => r.EmployeeType === type) : filtered;

    renderTable(typed);
    renderCharts(typed);
  } catch (e) {
    showToast("Load Error", e.message, "error");
  } finally {
    document.getElementById("att-loading").style.display = "none";
  }
}

function renderTable(data) {
  attPage = 1;
  const tbody = document.getElementById("attendance-tbody");
  document.getElementById("att-count").textContent = data.length;

  if (!data.length) {
    tbody.innerHTML = `<tr><td colspan="11" class="text-center text-muted" style="padding:32px;">No attendance records found</td></tr>`;
    document.getElementById("att-pagination").innerHTML = "";
    return;
  }

  renderPage(data, attPage);
  renderPagination(data, "att-pagination", (pg) => { attPage = pg; renderPage(data, pg); });
}

function renderPage(data, page) {
  const tbody = document.getElementById("attendance-tbody");
  const start = (page - 1) * attPageSize;
  const slice = data.slice(start, start + attPageSize);

  tbody.innerHTML = slice.map(r => `
    <tr>
      <td>${r.AttendanceDate ? new Date(r.AttendanceDate).toLocaleDateString("en-IN") : "—"}</td>
      <td><span class="badge badge-blue">${r.EmpCode || "—"}</span></td>
      <td><strong>${r.FullName || "—"}</strong></td>
      <td>${r.EmployeeType === "Contract" ? '<span class="badge badge-amber">Contract</span>' : r.EmployeeType === "OAS" ? '<span class="badge badge-purple">O&S</span>' : '<span class="badge badge-blue">Staff</span>'}</td>
      <td>${r.ContractorName || "—"}</td>
      <td>${r.GateName || "—"}</td>
      <td>${shiftLabel(r.ShiftCode)}</td>
      <td>${formatTime(r.EntryTime)}</td>
      <td>${r.ExitTime ? formatTime(r.ExitTime) : '<span class="text-muted">—</span>'}</td>
      <td>${r.Duration_Mins != null ? `<span class="badge badge-green">${r.Duration_Mins}m</span>` : "—"}</td>
      <td>
        ${!r.ExitTime ? `<button class="btn btn-secondary btn-sm" onclick="markExit(${r.EmployeeID})">Exit</button>` : ""}
      </td>
    </tr>`).join("");
}

function shiftLabel(code) {
  const m = { G: "General", A: "Morning", B: "Afternoon", C: "Night" };
  return `<span class="badge badge-blue">${m[code] || code || "—"}</span>`;
}

async function markExit(empId) {
  try {
    await apiFetch(`/attendance/manual-exit/${empId}`, { method: "POST" });
    showToast("Exit Marked", "Exit time recorded.", "success");
    loadAttendance();
  } catch(e) { showToast("Error", e.message, "error"); }
}

function renderCharts(data) {
  // Gate-wise chart
  const gateCounts = {};
  data.forEach(r => { gateCounts[r.GateName || "Unknown"] = (gateCounts[r.GateName || "Unknown"] || 0) + 1; });
  const gCtx = document.getElementById("gate-chart");
  if (gCtx) {
    if (gateChart) gateChart.destroy();
    gateChart = new Chart(gCtx, {
      type: "bar",
      data: {
        labels: Object.keys(gateCounts),
        datasets: [{ data: Object.values(gateCounts), backgroundColor: ["#2563eb","#06b6d4","#10b981","#8b5cf6"], borderRadius: 6, borderSkipped: false }],
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { backgroundColor: "#141c32" } }, scales: { y: { beginAtZero: true, grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#94a3b8" } }, x: { grid: { display: false }, ticks: { color: "#94a3b8" } } } },
    });
  }

  // Shift chart
  const shiftCounts = {};
  data.forEach(r => { shiftCounts[shiftName(r.ShiftCode)] = (shiftCounts[shiftName(r.ShiftCode)] || 0) + 1; });
  const sCtx = document.getElementById("shift-chart");
  if (sCtx) {
    if (shiftChart) shiftChart.destroy();
    shiftChart = new Chart(sCtx, {
      type: "doughnut",
      data: {
        labels: Object.keys(shiftCounts),
        datasets: [{ data: Object.values(shiftCounts), backgroundColor: ["#f59e0b","#2563eb","#8b5cf6","#06b6d4"], borderWidth: 0 }],
      },
      options: { responsive: true, maintainAspectRatio: false, cutout: "60%", plugins: { legend: { position: "right", labels: { color: "#94a3b8", font: { size: 11 } } } } },
    });
  }
}

function shiftName(code) { return { G:"General", A:"Morning", B:"Afternoon", C:"Night" }[code] || code || "Unknown"; }

function renderPagination(data, containerId, onPage) {
  const total = Math.ceil(data.length / attPageSize);
  const c = document.getElementById(containerId);
  if (!c || total <= 1) { if(c) c.innerHTML=""; return; }
  c.innerHTML = Array.from({length: total}, (_, i) =>
    `<button class="page-btn ${i+1===attPage?"active":""}" onclick="(${onPage.toString()})(${i+1})">${i+1}</button>`
  ).join("");
}

async function exportExcel() {
  const start = document.getElementById("filter-start").value;
  const end   = document.getElementById("filter-end").value;
  try {
    await apiDownload(`/reports/excel?start=${start}&end=${end}&type=Attendance`, `Attendance_${start}.xlsx`);
    showToast("Exported", "Excel report downloaded.", "success");
  } catch(e) { showToast("Export Error", e.message, "error"); }
}

async function exportPDF() {
  const start = document.getElementById("filter-start").value;
  const end   = document.getElementById("filter-end").value;
  try {
    await apiDownload(`/reports/pdf?start=${start}&end=${end}&type=Attendance`, `Attendance_${start}.pdf`);
    showToast("Exported", "PDF report downloaded.", "success");
  } catch(e) { showToast("Export Error", e.message, "error"); }
}
