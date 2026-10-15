/**
 * violations.js — Violations page logic
 */

let allViolations = [];
let vioPage = 1;
const vioPageSize = 20;

window.addEventListener("DOMContentLoaded", () => {
  const today = new Date().toISOString().split("T")[0];
  document.getElementById("vio-filter-start").value = today;
  document.getElementById("vio-filter-end").value   = today;
  if (authToken) loadViolations();
});

async function loadViolations() {
  try {
    // Stats
    const stats = await apiFetch("/violations/stats");
    document.getElementById("vio-total").textContent    = stats.total    || 0;
    document.getElementById("vio-helmet").textContent   = stats.no_helmet || 0;
    document.getElementById("vio-vest").textContent     = stats.no_vest  || 0;
    document.getElementById("vio-resolved").textContent = stats.resolved  || 0;

    // Records
    const start  = document.getElementById("vio-filter-start").value;
    const end    = document.getElementById("vio-filter-end").value;
    const gate   = document.getElementById("vio-filter-gate").value;
    const type   = document.getElementById("vio-filter-type").value;
    const search = document.getElementById("vio-filter-search").value;

    let url = `/violations/search?start=${start}&end=${end}`;
    if (gate)   url += `&gate_id=${gate}`;
    if (type)   url += `&type=${encodeURIComponent(type)}`;
    if (search) url += `&q=${encodeURIComponent(search)}`;

    const res = await apiFetch(url);
    allViolations = res.data || [];
    renderViolationTable(allViolations);
  } catch(e) {
    showToast("Load Error", e.message, "error");
  }
}

function renderViolationTable(data) {
  vioPage = 1;
  document.getElementById("vio-count").textContent = data.length;
  const tbody = document.getElementById("violations-tbody");

  if (!data.length) {
    tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted" style="padding:32px;">No breach records found for selected filters</td></tr>`;
    document.getElementById("vio-pagination").innerHTML = "";
    return;
  }

  renderVioPage(data, vioPage);
  // Pagination
  const total = Math.ceil(data.length / vioPageSize);
  const pc = document.getElementById("vio-pagination");
  if (total <= 1) { pc.innerHTML = ""; return; }
  pc.innerHTML = Array.from({length: total}, (_, i) =>
    `<button class="page-btn ${i+1===vioPage?"active":""}" onclick="vioPage=${i+1};renderVioPage(allViolations,${i+1})">${i+1}</button>`
  ).join("");
}

function renderVioPage(data, page) {
  const tbody = document.getElementById("violations-tbody");
  const start = (page - 1) * vioPageSize;
  const slice = data.slice(start, start + vioPageSize);

  tbody.innerHTML = slice.map(v => `
    <tr>
      <td>
        ${v.SnapshotPath
          ? `<img class="snapshot-thumb" src="/api/snapshot?path=${encodeURIComponent(v.SnapshotPath)}"
                  alt="snapshot" onclick="openSnapshot(${v.ViolationID}, '${escHtml(v.ViolationType)}', '${escHtml(v.GateName)}', '${escHtml(v.Timestamp)}')"
                  onerror="this.style.display='none';this.nextElementSibling.style.display='block'" />
             <span style="display:none;font-size:20px;cursor:pointer" onclick="openSnapshot(${v.ViolationID},'${escHtml(v.ViolationType)}','${escHtml(v.GateName)}','${escHtml(v.Timestamp)}')"></span>`
          : '<span class="text-muted" style="font-size:18px"></span>'
        }
      </td>
      <td>${formatDateTime(v.Timestamp)}</td>
      <td>${v.GateName || "—"}</td>
      <td>${violationTypeBadge(v.ViolationType)}</td>
      <td>${v.FullName ? `<strong>${v.FullName}</strong><br><small class="text-muted">${v.EmpCode||""}</small>` : '<span class="text-muted">Unknown Person</span>'}</td>
      <td>${v.ConfidenceScore != null ? `${(v.ConfidenceScore*100).toFixed(0)}%` : "—"}</td>
      <td>${v.IsResolved ? '<span class="badge badge-green">Resolved</span>' : '<span class="badge badge-red">Open</span>'}</td>
      <td>
        ${!v.IsResolved ? `<button class="btn btn-success btn-sm" onclick="resolveViolation(${v.ViolationID})">✓ Resolve</button>` : ""}
      </td>
    </tr>`).join("");
}

function violationTypeBadge(type) {
  return `<span class="badge badge-red">${type || "—"}</span>`;
}

function escHtml(str) { return String(str || "").replace(/'/g, "\\'").replace(/"/g, "&quot;"); }

async function resolveViolation(vioId) {
  try {
    await apiFetch(`/violations/${vioId}/resolve`, { method: "POST" });
    showToast("Resolved", "Violation marked as resolved.", "success");
    loadViolations();
  } catch(e) { showToast("Error", e.message, "error"); }
}

function openSnapshot(vioId, type, gate, ts) {
  const modal = document.getElementById("snapshot-modal");
  const img   = document.getElementById("snapshot-img");
  const info  = document.getElementById("snapshot-info");
  document.getElementById("snapshot-modal-title").textContent = `${type} — ${gate}`;
  img.src = `/api/violation-snapshot/${vioId}`;
  img.onerror = () => { img.src = ""; img.alt = "Snapshot not available"; };
  info.innerHTML = `
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:13px;">
      <div><span class="text-muted">Gate:</span> <strong>${gate}</strong></div>
      <div><span class="text-muted">Time:</span> <strong>${formatDateTime(ts)}</strong></div>
      <div><span class="text-muted">Type:</span> ${violationTypeBadge(type)}</div>
    </div>`;
  modal.classList.add("show");
}

function closeSnapshotModal() {
  document.getElementById("snapshot-modal").classList.remove("show");
}

async function exportViolationsExcel() {
  const start = document.getElementById("vio-filter-start").value;
  const end   = document.getElementById("vio-filter-end").value;
  try {
    await apiDownload(`/reports/excel?start=${start}&end=${end}&type=Violations`, `Violations_${start}.xlsx`);
    showToast("Exported", "Violations Excel downloaded.", "success");
  } catch(e) { showToast("Export Error", e.message, "error"); }
}
