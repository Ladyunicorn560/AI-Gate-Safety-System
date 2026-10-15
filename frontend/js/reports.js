/**
 * reports.js — Report generation page
 */

let currentReportType = "Daily";

window.addEventListener("DOMContentLoaded", async () => {
  const today = new Date().toISOString().split("T")[0];
  document.getElementById("rpt-start").value = today;
  document.getElementById("rpt-end").value   = today;
  if (authToken) await loadContractorsForReport();
});

async function loadContractorsForReport() {
  try {
    const res = await apiFetch("/employees/contractors");
    const sel = document.getElementById("rpt-contractor");
    (res.data || []).forEach(c => {
      const opt = document.createElement("option");
      opt.value = c.ContractorID;
      opt.textContent = c.ContractorName;
      sel.appendChild(opt);
    });
  } catch(e) {}
}

function setReportType(type) {
  currentReportType = type;
  document.querySelectorAll(".report-type-btn").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.type === type);
  });

  const today = new Date();
  const start = document.getElementById("rpt-start");
  const end   = document.getElementById("rpt-end");

  if (type === "Daily") {
    const t = today.toISOString().split("T")[0];
    start.value = t; end.value = t;
  } else if (type === "Weekly") {
    const day  = today.getDay();
    const diff = today.getDate() - day + (day === 0 ? -6 : 1);
    const mon  = new Date(today.setDate(diff));
    const sun  = new Date(mon); sun.setDate(mon.getDate() + 6);
    start.value = mon.toISOString().split("T")[0];
    end.value   = sun.toISOString().split("T")[0];
  } else if (type === "Monthly") {
    const y = today.getFullYear(); const m = today.getMonth();
    start.value = `${y}-${String(m+1).padStart(2,"0")}-01`;
    end.value   = new Date(y, m+1, 0).toISOString().split("T")[0];
  }
}

async function previewReport() {
  const start = document.getElementById("rpt-start").value;
  const end   = document.getElementById("rpt-end").value;
  const gate  = document.getElementById("rpt-gate").value;
  const ctr   = document.getElementById("rpt-contractor").value;

  showLoading(true);
  try {
    let url = `/reports/preview?start=${start}&end=${end}&type=${currentReportType}`;
    if (gate) url += `&gate_id=${gate}`;
    if (ctr)  url += `&contractor_id=${ctr}`;

    const data = await apiFetch(url);
    renderPreview(data);
  } catch(e) {
    showToast("Preview Error", e.message, "error");
  } finally {
    showLoading(false);
  }
}

function renderPreview(data) {
  const sum = data.summary || {};
  const att = data.attendance || [];
  const vio = data.violations || [];

  // Show KPIs
  document.getElementById("rpt-kpis").style.display       = "grid";
  document.getElementById("rpt-att-card").style.display   = "block";
  document.getElementById("rpt-vio-card").style.display   = "block";
  document.getElementById("rpt-empty-card").style.display = "none";

  document.getElementById("rpt-total-present").textContent = sum.total_present    || 0;
  document.getElementById("rpt-total-vio").textContent     = sum.total_violations || 0;
  document.getElementById("rpt-compliance").textContent    = sum.compliance_pct   || "N/A";

  // Attendance table
  document.getElementById("rpt-att-count").textContent = att.length;
  const attTbody = document.getElementById("rpt-att-tbody");
  attTbody.innerHTML = att.map(r => `
    <tr>
      <td>${r.AttendanceDate ? new Date(r.AttendanceDate).toLocaleDateString("en-IN") : "—"}</td>
      <td><span class="badge badge-blue">${r.EmpCode || "—"}</span></td>
      <td>${r.FullName || "—"}</td>
      <td>${r.EmployeeType || "—"}</td>
      <td>${r.GateName || "—"}</td>
      <td>${formatTime(r.EntryTime)}</td>
      <td>${r.ExitTime ? formatTime(r.ExitTime) : "—"}</td>
      <td>${r.Duration_Mins != null ? r.Duration_Mins + " min" : "—"}</td>
    </tr>`).join("") || `<tr><td colspan="8" class="text-center text-muted">No attendance records</td></tr>`;

  // Violations table
  document.getElementById("rpt-vio-count").textContent = vio.length;
  const vioTbody = document.getElementById("rpt-vio-tbody");
  vioTbody.innerHTML = vio.map(v => `
    <tr>
      <td>${formatDateTime(v.Timestamp)}</td>
      <td>${v.GateName || "—"}</td>
      <td><span class="badge badge-red">${v.ViolationType || "—"}</span></td>
      <td>${v.FullName || "Unknown"}</td>
      <td>${v.IsResolved ? '<span class="badge badge-green">Resolved</span>' : '<span class="badge badge-red">Open</span>'}</td>
    </tr>`).join("") || `<tr><td colspan="5" class="text-center text-muted">No violations</td></tr>`;

  showToast("Preview Ready", `${att.length} attendance + ${vio.length} violations`, "success");
}

async function downloadExcel() {
  const start = document.getElementById("rpt-start").value;
  const end   = document.getElementById("rpt-end").value;
  const gate  = document.getElementById("rpt-gate").value;
  const ctr   = document.getElementById("rpt-contractor").value;

  showLoading(true);
  try {
    let url = `/reports/excel?start=${start}&end=${end}&type=${currentReportType}`;
    if (gate) url += `&gate_id=${gate}`;
    if (ctr)  url += `&contractor_id=${ctr}`;
    await apiDownload(url, `AI_Gate_Report_${currentReportType}_${start}.xlsx`);
    showToast("Downloaded!", "Excel report saved.", "success");
  } catch(e) { showToast("Download Error", e.message, "error"); }
  finally { showLoading(false); }
}

async function downloadPDF() {
  const start = document.getElementById("rpt-start").value;
  const end   = document.getElementById("rpt-end").value;
  const gate  = document.getElementById("rpt-gate").value;
  const ctr   = document.getElementById("rpt-contractor").value;

  showLoading(true);
  try {
    let url = `/reports/pdf?start=${start}&end=${end}&type=${currentReportType}`;
    if (gate) url += `&gate_id=${gate}`;
    if (ctr)  url += `&contractor_id=${ctr}`;
    await apiDownload(url, `AI_Gate_Report_${currentReportType}_${start}.pdf`);
    showToast("Downloaded!", "PDF report saved.", "success");
  } catch(e) { showToast("Download Error", e.message, "error"); }
  finally { showLoading(false); }
}

function quickReport(type) {
  const today = new Date();
  if (type === "today") {
    setReportType("Daily");
    previewReport();
  } else if (type === "week") {
    setReportType("Weekly");
    previewReport();
  } else if (type === "month") {
    setReportType("Monthly");
    previewReport();
  } else if (type === "violations-today") {
    const t = today.toISOString().split("T")[0];
    document.getElementById("rpt-start").value = t;
    document.getElementById("rpt-end").value   = t;
    previewReport();
  }
}

function showLoading(show) {
  document.querySelectorAll(".btn").forEach(b => { if(show) b.style.opacity="0.7"; else b.style.opacity=""; });
}
