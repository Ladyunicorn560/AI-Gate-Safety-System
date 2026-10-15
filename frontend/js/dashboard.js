/**
 * dashboard.js — Live dashboard: SocketIO, KPIs, gate cards, charts, activity feed
 */

let socket = null;
let violationChart = null;

// ── Initialize Dashboard ──────────────────────────────────────────────────────
async function loadDashboard() {
  if (!authToken) return;
  try {
    const data = await apiFetch("/dashboard/stats");
    updateKPIs(data);
    initChart(data.violations);
    await loadGates();
    await loadRecentActivity();
    connectSocketIO();
  } catch (err) {
    showToast("Dashboard Error", err.message, "error");
  }
}

// ── KPI Cards ─────────────────────────────────────────────────────────────────
function updateKPIs(data) {
  const att = data.attendance || {};
  const vio = data.violations || {};

  animateCount("kpi-present-val", att.total_present || 0);
  animateCount("kpi-contract-val", att.contract_workers || 0);
  animateCount("kpi-violations-val", vio.total || 0);

  const total = (vio.total || 0);
  const compPct = total === 0 ? 100 : Math.max(0, Math.round((1 - total / Math.max(att.total_present || 1, 1)) * 100));
  document.getElementById("kpi-compliance-val").textContent = `${compPct}%`;

  // Update violation badge in nav
  const badge = document.getElementById("violation-badge");
  if (badge) { badge.textContent = vio.total || 0; badge.style.display = vio.total > 0 ? "" : "none"; }
}

function animateCount(id, target) {
  const el = document.getElementById(id);
  if (!el) return;
  let current = 0;
  const step = Math.ceil(target / 20);
  const timer = setInterval(() => {
    current = Math.min(current + step, target);
    el.textContent = current;
    if (current >= target) clearInterval(timer);
  }, 30);
}

// ── Gate Grid ─────────────────────────────────────────────────────────────────
async function loadGates() {
  const res = await apiFetch("/dashboard/gates");
  const grid = document.getElementById("gate-grid");
  if (!grid) return;
  grid.innerHTML = (res.data || []).map(gate => gateCardHTML(gate)).join("");
}

function gateCardHTML(gate) {
  const statusClass = gate.camera_status === "running" ? "active" : "";
  const dotClass = gate.camera_status === "running" ? "active" : gate.camera_status === "error" ? "error" : "stopped";
  const statusLabel = { running: "Live Stream", stopped: "Offline", error: "Camera Error" }[gate.camera_status] || "—";

  return `
    <div class="gate-card ${statusClass}" id="gate-card-${gate.GateID}">
      <div class="gate-feed">
        <img id="gate-feed-${gate.GateID}" style="display:none;" alt="Gate ${gate.GateID} feed" />
        <div class="gate-feed-placeholder" id="gate-placeholder-${gate.GateID}">
          <div class="feed-icon">
            <svg class="nav-svg" style="width:32px;height:32px;opacity:0.5;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M23 7l-7 5 7 5V7z"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>
          </div>
          <p>${gate.camera_status === "running" ? "Connecting feed..." : "Camera Stream Offline"}</p>
        </div>
        <div class="gate-feed-overlay">
          <div style="display:flex;align-items:center;gap:6px;">
            <span class="gate-status-dot ${dotClass}"></span>
            <span style="color:white;font-size:11px;font-weight:600;letter-spacing:0.5px;">${statusLabel}</span>
          </div>
          <span style="color:white;font-size:11px;" id="gate-time-${gate.GateID}"></span>
        </div>
      </div>
      <div class="gate-info">
        <div class="gate-name">${gate.GateName}</div>
        <div class="gate-location">${gate.Location || "Main Access Zone"}</div>
        <div class="gate-stats">
          <div class="gate-stat">
            <span class="gate-stat-val" id="gate-persons-${gate.GateID}">${gate.persons_detected || 0}</span>
            <span>detected</span>
          </div>
          <div class="gate-stat">
            <span class="gate-stat-val text-danger" id="gate-vio-${gate.GateID}">${gate.violations_today || 0}</span>
            <span>breaches</span>
          </div>
        </div>
        <div class="gate-actions">
          ${gate.camera_status === "running"
      ? `<button class="btn btn-danger btn-sm" onclick="stopGate(${gate.GateID})">Stop Stream</button>`
      : `<button class="btn btn-success btn-sm" onclick="startGate(${gate.GateID})">Start Stream</button>`
    }
          <button class="btn btn-secondary btn-sm" onclick="testGateImage(${gate.GateID})">Test Snapshot</button>
          <a href="pages/settings.html#gate-${gate.GateID}" class="btn btn-ghost btn-sm" title="Configure Camera">Config</a>
        </div>
      </div>
    </div>`;
}

// ── Camera Controls ───────────────────────────────────────────────────────────
async function startGate(gateId) {
  try {
    await apiFetch(`/cameras/start/${gateId}`, { method: "POST", body: JSON.stringify({}) });
    showToast("Camera Starting", `Gate ${gateId} camera stream initializing...`, "info");
    setTimeout(loadGates, 1500);
  } catch (e) { showToast("Error", e.message, "error"); }
}

async function stopGate(gateId) {
  try {
    await apiFetch(`/cameras/stop/${gateId}`, { method: "POST", body: JSON.stringify({}) });
    showToast("Camera Stopped", `Gate ${gateId} stream stopped.`, "warn");
    setTimeout(loadGates, 1000);
  } catch (e) { showToast("Error", e.message, "error"); }
}

async function startAllCameras() {
  try {
    await apiFetch("/cameras/start-all", { method: "POST", body: JSON.stringify({}) });
    showToast("All Cameras Active", "Starting streams for all gate cameras...", "success");
    setTimeout(loadGates, 2000);
  } catch (e) { showToast("Error", e.message, "error"); }
}

async function stopAllCameras() {
  try {
    await apiFetch("/cameras/stop-all", { method: "POST", body: JSON.stringify({}) });
    showToast("Streams Terminated", "All camera streams stopped.", "warn");
    setTimeout(loadGates, 1000);
  } catch (e) { showToast("Error", e.message, "error"); }
}

function testGateImage(gateId) {
  const input = document.createElement("input");
  input.type = "file"; input.accept = "image/*";
  input.onchange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("image", file);
    try {
      const res = await fetch(`${API_BASE}/cameras/test-image/${gateId}`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${authToken}` },
        body: fd,
      });
      const data = await res.json();
      const msg = `Persons: ${data.ppe_detections?.filter(d => d.class_name === 'Person').length || 0} | Violations: ${data.violation_count || 0}`;
      showToast(`Gate ${gateId} Test Result`, msg, data.violation_count > 0 ? "warn" : "success", 6000);
    } catch (e) { showToast("Test Error", e.message, "error"); }
  };
  input.click();
}

// ── Violation Chart ───────────────────────────────────────────────────────────
function initChart(vioStats = {}) {
  const ctx = document.getElementById("violation-chart");
  if (!ctx) return;
  if (violationChart) violationChart.destroy();

  violationChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["No Helmet", "No Vest", "No Shoes", "No Mask", "Other"],
      datasets: [{
        data: [
          vioStats.no_helmet || 0,
          vioStats.no_vest || 0,
          vioStats.no_shoes || 0,
          vioStats.no_mask || 0,
          Math.max(0, (vioStats.total || 0) - (vioStats.no_helmet || 0) - (vioStats.no_vest || 0) - (vioStats.no_shoes || 0) - (vioStats.no_mask || 0)),
        ],
        backgroundColor: ["#ef4444", "#f59e0b", "#8b5cf6", "#06b6d4", "#6b7280"],
        borderWidth: 0,
        hoverOffset: 8,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      cutout: "65%",
      plugins: {
        legend: { position: "right", labels: { color: "#475569", font: { size: 12, family: "Plus Jakarta Sans" }, padding: 12 } },
        tooltip: { backgroundColor: "#0F172A", titleColor: "#FFFFFF", bodyColor: "#CBD5E1", cornerRadius: 8 },
      },
    },
  });
}

// ── Recent Activity Feed ──────────────────────────────────────────────────────
async function loadRecentActivity() {
  try {
    const data = await apiFetch("/dashboard/recent-activity");
    renderAlerts(data.violations || []);
    renderEntries(data.attendance || []);
  } catch (e) { }
}

function renderAlerts(violations) {
  const el = document.getElementById("alert-list");
  if (!el) return;
  if (!violations.length) { el.innerHTML = `<div class="empty-state">No PPE breaches detected today</div>`; return; }
  el.innerHTML = violations.map(v => `
    <div class="alert-item">
      <div class="alert-icon-box">
        <svg class="alert-svg text-red" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
      </div>
      <div class="alert-body">
        <div class="alert-type">${v.ViolationType}</div>
        <div class="alert-meta">${v.GateName} • ${v.FullName || "Unknown Person"} • ${formatTime(v.Timestamp)}</div>
      </div>
    </div>`).join("");
}

function renderEntries(attendance) {
  const el = document.getElementById("entry-list");
  if (!el) return;
  if (!attendance.length) { el.innerHTML = `<div class="empty-state">No entries recorded today</div>`; return; }
  el.innerHTML = attendance.map(a => `
    <div class="entry-item">
      <div class="entry-avatar">${(a.FullName || "?")[0]}</div>
      <div>
        <div class="entry-name">${a.FullName}</div>
        <div class="entry-meta">${a.GateName} • ${formatTime(a.EntryTime)} • ${a.ContractorName || a.EmployeeType}</div>
      </div>
    </div>`).join("");
}

// ── SocketIO Real-Time ────────────────────────────────────────────────────────
function connectSocketIO() {
  if (socket) return;
  try {
    socket = io("http://localhost:5000", { transports: ["websocket"] });

    socket.on("connect", () => {
      const dot = document.querySelector(".status-dot");
      const label = document.querySelector(".status-label");
      if (dot) { dot.classList.remove("disconnected", "connecting"); dot.classList.add("connected"); }
      if (label) label.textContent = "Live";
    });

    socket.on("disconnect", () => {
      const dot = document.querySelector(".status-dot");
      const label = document.querySelector(".status-label");
      if (dot) { dot.classList.remove("connected", "connecting"); dot.classList.add("disconnected"); }
      if (label) label.textContent = "Disconnected";
    });

    // Live camera frames
    [1, 2, 3, 4].forEach(gateId => {
      socket.on(`frame_gate_${gateId}`, (data) => {
        const img = document.getElementById(`gate-feed-${gateId}`);
        const ph = document.getElementById(`gate-placeholder-${gateId}`);
        const tm = document.getElementById(`gate-time-${gateId}`);
        if (img) {
          img.src = `data:image/jpeg;base64,${data.frame}`;
          img.style.display = "block";
          if (ph) ph.style.display = "none";
        }
        if (tm) tm.textContent = new Date().toLocaleTimeString("en-IN");
        // Update person count
        const ps = document.getElementById(`gate-persons-${gateId}`);
        if (ps && data.stats) ps.textContent = data.stats.persons_detected || 0;
      });
    });

    // Violation events → toast + update badge
    socket.on("violation_event", (data) => {
      showToast(`PPE Breach: ${data.violation_type}`, `${data.gate_name} — ${formatTime(data.timestamp)}`, "error", 6000);
      // Blink gate card
      const card = document.getElementById(`gate-card-${data.gate_id}`);
      if (card) { card.classList.add("gate-violation"); setTimeout(() => card.classList.remove("gate-violation"), 3000); }
      // Refresh violations count
      loadDashboard();
    });

    // Attendance events → entry list
    socket.on("attendance_event", (data) => {
      showToast("Entry Logged", `${data.full_name} @ ${data.gate_name}`, "success", 3000);
      loadRecentActivity();
    });

  } catch (e) {
    console.warn("SocketIO unavailable:", e);
  }
}

// ── AI Model Playground File Upload Handler ───────────────────────────────────
function setupPlaygroundDropzone() {
  const dropzone = document.getElementById("upload-dropzone");
  if (!dropzone) return;

  ["dragenter", "dragover", "dragleave", "drop"].forEach(eventName => {
    dropzone.addEventListener(eventName, preventDefaults, false);
  });

  function preventDefaults(e) { e.preventDefault(); e.stopPropagation(); }

  ["dragenter", "dragover"].forEach(eventName => {
    dropzone.addEventListener(eventName, () => dropzone.classList.add("highlight"), false);
  });

  ["dragleave", "drop"].forEach(eventName => {
    dropzone.addEventListener(eventName, () => dropzone.classList.remove("highlight"), false);
  });

  dropzone.addEventListener("drop", handleDrop, false);

  function handleDrop(e) {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files && files.length > 0) {
      processPlaygroundFile(files[0]);
    }
  }
}

function handlePlaygroundFileSelect(event) {
  const file = event.target.files[0];
  if (file) {
    processPlaygroundFile(file);
  }
}

async function processPlaygroundFile(file) {
  const dropzone = document.getElementById("upload-dropzone");
  const loading = document.getElementById("upload-loading");
  const loadingText = document.getElementById("loading-status-text");
  const results = document.getElementById("playground-results");

  if (!file) return;

  // Show loading spinner
  if (loading) loading.style.display = "flex";
  if (loadingText) loadingText.textContent = `Processing '${file.name}' through YOLOv8 & InsightFace...`;
  const dropContent = dropzone ? dropzone.querySelector(".dropzone-content") : null;
  if (dropContent) dropContent.style.opacity = "0.3";

  const formData = new FormData();
  formData.append("file", file);

  try {
    const headers = {};
    if (authToken) headers["Authorization"] = `Bearer ${authToken}`;

    const response = await fetch(`${API_BASE}/dashboard/test-upload`, {
      method: "POST",
      headers: headers,
      body: formData,
    });

    const data = await response.json();

    if (!response.ok || data.error) {
      throw new Error(data.error || "Failed to process media");
    }

    // Hide loading
    if (loading) loading.style.display = "none";
    if (dropContent) dropContent.style.opacity = "1";
    if (dropzone) dropzone.style.display = "none";
    if (results) results.style.display = "block";

    renderPlaygroundResults(file.name, data);
    showToast("Model Inference Complete", `Successfully analyzed ${file.name}`, "success");
  } catch (err) {
    if (loading) loading.style.display = "none";
    if (dropContent) dropContent.style.opacity = "1";
    showToast("Upload Error", err.message, "error");
  }
}

function renderPlaygroundResults(filename, data) {
  const resFilename = document.getElementById("res-filename");
  const badge = document.getElementById("res-compliance-badge");
  const personCount = document.getElementById("res-person-count");
  const violationCount = document.getElementById("res-violation-count");
  const matchCount = document.getElementById("res-match-count");
  const viewport = document.getElementById("preview-viewport");
  const chipList = document.getElementById("detections-chip-list");
  const keyframesWrap = document.getElementById("video-keyframes-wrap");
  const keyframesGrid = document.getElementById("keyframes-grid");

  if (resFilename) resFilename.textContent = filename;

  const summary = data.summary || {};
  const isPass = summary.compliance_pass;

  if (badge) {
    badge.textContent = isPass ? "SAFETY COMPLIANT" : "PPE VIOLATION DETECTED";
    badge.className = `status-badge-lg ${isPass ? "badge-success" : "badge-danger"}`;
  }

  if (personCount) personCount.textContent = summary.persons || summary.peak_persons || 0;
  if (violationCount) violationCount.textContent = summary.violations_count || summary.total_violations_found || 0;
  if (matchCount) matchCount.textContent = (summary.matched_employees || []).length;

  // Render Visual Media Preview
  if (viewport) {
    if (data.media_type === "image") {
      viewport.innerHTML = `
        <div class="image-comparison-container">
          <img src="${data.annotated_image}" alt="Annotated Output" class="preview-img" />
        </div>`;
    } else if (data.media_type === "video") {
      viewport.innerHTML = `
        <video controls autoplay loop class="preview-video">
          <source src="${API_BASE.replace('/api', '')}${data.video_url}" type="video/mp4" />
          Your browser does not support HTML5 video player.
        </video>`;
    }
  }

  // Render Detection Chips
  if (chipList) {
    let html = "";

    // Show PPE Detections
    if (data.detections && data.detections.length > 0) {
      data.detections.forEach(det => {
        const confPct = Math.round(det.confidence * 100);
        const isVio = det.is_violation;
        const chipClass = isVio ? "chip-danger" : det.class_name.toLowerCase() === "person" ? "chip-info" : "chip-success";
        html += `<span class="det-chip ${chipClass}">
          ${isVio ? "⚠ " : ""}${det.class_name} (${confPct}%)
        </span>`;
      });
    }

    // Show Face Recognition Matches
    if (data.face_matches && data.face_matches.length > 0) {
      data.face_matches.forEach(fm => {
        if (fm.matched) {
          html += `<span class="det-chip chip-accent">
            👤 ${fm.employee.full_name} (Face Match)
          </span>`;
        }
      });
    }

    // Video unique violations summary
    if (data.summary && data.summary.unique_violations && data.summary.unique_violations.length > 0) {
      data.summary.unique_violations.forEach(vName => {
        html += `<span class="det-chip chip-danger">
          ⚠ Breach: ${vName}
        </span>`;
      });
    }

    if (!html) {
      html = `<span class="text-muted">No specific safety items or faces detected in file.</span>`;
    }
    chipList.innerHTML = html;
  }

  // Keyframes rendering for video
  if (keyframesWrap && keyframesGrid) {
    if (data.media_type === "video" && data.keyframes && data.keyframes.length > 0) {
      keyframesWrap.style.display = "block";
      keyframesGrid.innerHTML = data.keyframes.map(kf => `
        <div class="keyframe-card">
          <img src="${kf.image}" alt="Frame at ${kf.timestamp}" />
          <div class="kf-meta">Time: ${kf.timestamp} | Persons: ${kf.persons} | Breaches: ${kf.violations}</div>
        </div>
      `).join("");
    } else {
      keyframesWrap.style.display = "none";
    }
  }
}

function resetPlayground() {
  const dropzone = document.getElementById("upload-dropzone");
  const results = document.getElementById("playground-results");
  const fileInput = document.getElementById("playground-file-input");

  if (fileInput) fileInput.value = "";
  if (results) results.style.display = "none";
  if (dropzone) {
    dropzone.style.display = "flex";
    const dropContent = dropzone.querySelector(".dropzone-content");
    if (dropContent) dropContent.style.opacity = "1";
  }
}

// ── Auto-refresh every 30 seconds ────────────────────────────────────────────
setInterval(() => { if (authToken) loadDashboard(); }, 30000);

// ── Boot ──────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  if (authToken) loadDashboard();
  setupPlaygroundDropzone();
});

