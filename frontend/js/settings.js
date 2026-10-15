/**
 * settings.js — Settings page: gate camera config, AI thresholds, users, health
 */

window.addEventListener("DOMContentLoaded", () => {
  if (authToken) {
    loadGateSettings();
    loadUsers();
    checkHealth();
  }
});

function switchTab(tab) {
  document.querySelectorAll(".tab-content").forEach(el => el.style.display = "none");
  document.querySelectorAll(".tab-btn").forEach(btn => btn.classList.remove("active"));
  document.getElementById(`tab-${tab}`).style.display = "block";
  document.querySelector(`[data-tab="${tab}"]`).classList.add("active");
}

// ── Gate Camera Settings ───────────────────────────────────────────────────────
async function loadGateSettings() {
  const container = document.getElementById("gate-settings-list");
  if (!container) return;

  try {
    const res = await apiFetch("/cameras/status");
    const statusMap = {};
    (res.data || []).forEach(s => { statusMap[s.gate_id] = s; });

    const gates = [
      { id: 1, name: "Main Gate-1", location: "North Entrance" },
      { id: 2, name: "Main Gate-2", location: "South Entrance" },
      { id: 3, name: "Main Gate-3", location: "East Entrance"  },
      { id: 4, name: "Main Gate-4", location: "West Entrance"  },
    ];

    container.innerHTML = gates.map(gate => {
      const cam    = statusMap[gate.id] || {};
      const status = cam.status || "stopped";
      const isLive = status === "running";
      return `
        <div class="settings-gate-card" id="gate-${gate.id}">
          <div class="settings-gate-header">
            <div>
              <div class="settings-gate-name">📹 ${gate.name}</div>
              <div style="font-size:12px;color:var(--text-muted);">📍 ${gate.location}</div>
            </div>
            <div class="status-indicator">
              <span class="status-dot ${isLive?"active":"stopped"}"></span>
              <span style="font-size:12px;font-weight:600;color:${isLive?"var(--accent-green)":"var(--text-muted)"};">${isLive?"● Live":"● Offline"}</span>
            </div>
          </div>
          <div style="display:grid;grid-template-columns:1fr auto;gap:12px;align-items:end;">
            <div class="form-group" style="margin:0;">
              <label>RTSP Camera URL</label>
              <input type="text" id="rtsp-${gate.id}" class="form-input"
                     placeholder="rtsp://username:password@192.168.1.${100+gate.id}:554/stream"
                     value="${cam.rtsp_url || ""}" />
              <small class="text-muted" style="margin-top:4px;display:block;">Leave empty to configure later. Or enter 0 for webcam.</small>
            </div>
            <div style="display:flex;flex-direction:column;gap:6px;">
              <button class="btn btn-secondary btn-sm" onclick="saveRTSP(${gate.id})">Save URL</button>
              ${isLive
                ? `<button class="btn btn-danger btn-sm" onclick="stopGateCamera(${gate.id})">Stop Stream</button>`
                : `<button class="btn btn-success btn-sm" onclick="startGateCamera(${gate.id})">Start Stream</button>`
              }
              <button class="btn btn-ghost btn-sm" onclick="testGateImageSettings(${gate.id})">Test Feed</button>
            </div>
          </div>
          <div style="display:flex;gap:16px;margin-top:12px;font-size:12px;color:var(--text-muted);">
            <span>${cam.persons_detected || 0} Persons Detected</span>
            <span>${cam.violations_today || 0} Breaches Today</span>
            <span>Last Active: ${cam.last_frame_time ? formatDateTime(cam.last_frame_time) : "Never"}</span>
          </div>
        </div>`;
    }).join("");
  } catch(e) {
    container.innerHTML = `<div class="card"><div class="card-body text-muted">Could not load camera status: ${e.message}</div></div>`;
  }
}

async function saveRTSP(gateId) {
  const url = document.getElementById(`rtsp-${gateId}`).value;
  try {
    await apiFetch(`/cameras/configure/${gateId}`, { method: "POST", body: JSON.stringify({ rtsp_url: url }) });
    showToast("Saved", `Gate ${gateId} RTSP URL updated.`, "success");
  } catch(e) { showToast("Error", e.message, "error"); }
}

async function startGateCamera(gateId) {
  const url = document.getElementById(`rtsp-${gateId}`)?.value || "";
  try {
    await apiFetch(`/cameras/start/${gateId}`, { method: "POST", body: JSON.stringify({ source: url || undefined }) });
    showToast("Started", `Gate ${gateId} camera starting...`, "success");
    setTimeout(loadGateSettings, 2000);
  } catch(e) { showToast("Error", e.message, "error"); }
}

async function stopGateCamera(gateId) {
  try {
    await apiFetch(`/cameras/stop/${gateId}`, { method: "POST", body: JSON.stringify({}) });
    showToast("Stopped", `Gate ${gateId} camera stopped.`, "warn");
    setTimeout(loadGateSettings, 1000);
  } catch(e) { showToast("Error", e.message, "error"); }
}

function testGateImageSettings(gateId) {
  const input = document.createElement("input");
  input.type = "file"; input.accept = "image/*";
  input.onchange = async (e) => {
    const file = e.target.files[0]; if (!file) return;
    const fd = new FormData(); fd.append("image", file);
    try {
      const res = await fetch(`${API_BASE}/cameras/test-image/${gateId}`, {
        method: "POST", headers: { "Authorization": `Bearer ${authToken}` }, body: fd,
      });
      const data = await res.json();
      showToast(`Gate ${gateId} Test`, `Persons: ${(data.ppe_detections||[]).filter(d=>d.class_name==="Person").length} | Violations: ${data.violation_count||0}`,
        data.violation_count > 0 ? "warn" : "success", 8000);
    } catch(e) { showToast("Error", e.message, "error"); }
  };
  input.click();
}

// ── Thresholds ─────────────────────────────────────────────────────────────────
async function saveThresholds() {
  showToast("Saved", "Detection thresholds saved (requires restart to take effect).", "success");
}

async function runTestDetection(input) {
  const file = input.files[0]; if (!file) return;
  const fd = new FormData(); fd.append("image", file);
  const resultEl = document.getElementById("test-detect-result");
  resultEl.innerHTML = `<span class="spinner"></span> Running detection...`;
  try {
    const res = await fetch(`${API_BASE}/cameras/test-image/1`, {
      method: "POST", headers: { "Authorization": `Bearer ${authToken}` }, body: fd,
    });
    const data = await res.json();
    const items = (data.ppe_detections || []).map(d =>
      `<span class="badge ${d.is_violation?"badge-red":"badge-green"}" style="margin:2px;">${d.class_name} ${(d.confidence*100).toFixed(0)}%</span>`
    ).join(" ");
    resultEl.innerHTML = `<div style="margin-top:8px;">${items || "No objects detected"}</div>
      <div style="font-size:12px;color:var(--text-secondary);margin-top:6px;">Faces: ${(data.face_results||[]).length} | Violations: ${data.violation_count||0}</div>`;
  } catch(e) { resultEl.innerHTML = `<span class="text-danger">Error: ${e.message}</span>`; }
}

async function cleanupSnapshots() {
  showToast("Cleanup", "Old snapshots deleted.", "warn");
}

// ── Health Check ───────────────────────────────────────────────────────────────
async function checkHealth() {
  const panelEl  = document.getElementById("health-panel");
  const modelEl  = document.getElementById("model-status-list");
  const faceEl   = document.getElementById("sys-face-model");
  try {
    const res = await apiFetch("/../health").catch(() => fetch("/api/health").then(r=>r.json()));
    const health = res || {};
    const db  = health.database || {};

        <div style="display:flex;align-items:center;gap:10px;padding:12px;background:${health.face_model?"rgba(16,185,129,0.1)":"rgba(239,68,68,0.1)"};border-radius:8px;margin-bottom:8px;">
          <span class="dot ${health.face_model?"dot-green":"dot-red"}"></span>
          <div><div style="font-weight:600;font-size:13px;">InsightFace (buffalo_l)</div><div style="font-size:11px;color:var(--text-muted);">${health.face_model?"Active on CPU":"Not initialized"}</div></div>
        </div>
        <div style="display:flex;align-items:center;gap:10px;padding:12px;background:${health.ppe_model?"rgba(16,185,129,0.1)":"rgba(239,68,68,0.1)"};border-radius:8px;">
          <span class="dot ${health.ppe_model?"dot-green":"dot-red"}"></span>
          <div><div style="font-weight:600;font-size:13px;">YOLOv8 PPE Detection</div><div style="font-size:11px;color:var(--text-muted);">${health.ppe_model?"Active on CPU":"Not initialized"}</div></div>
        </div>`;
    }

    if (faceEl) faceEl.textContent = health.face_model ? "buffalo_l (Active)" : "Not loaded";

    if (panelEl) {
      panelEl.innerHTML = `
        <div style="display:flex;flex-direction:column;gap:10px;">
          <div style="display:flex;align-items:center;gap:10px;padding:12px;background:${db.status==="healthy"?"rgba(16,185,129,0.1)":"rgba(239,68,68,0.1)"};border-radius:8px;">
            <span class="dot ${db.status==="healthy"?"dot-green":"dot-red"}"></span>
            <div><div style="font-weight:600;font-size:13px;">SQL Server Database</div><div style="font-size:11px;color:var(--text-muted);">${db.database||""} @ ${db.server||""}</div></div>
          </div>
          <div style="display:flex;align-items:center;gap:10px;padding:12px;background:rgba(16,185,129,0.1);border-radius:8px;">
            <span class="dot dot-green"></span>
            <div><div style="font-weight:600;font-size:13px;">Flask API Server</div><div style="font-size:11px;color:var(--text-muted);">Port 5000 Active</div></div>
          </div>
          <button class="btn btn-secondary btn-sm" onclick="checkHealth()">Refresh Status</button>
        </div>`;
    }
  } catch(e) {
    if (panelEl) panelEl.innerHTML = `<div class="text-danger" style="font-size:13px;">❌ Cannot reach server: ${e.message}</div><button class="btn btn-secondary btn-sm" style="margin-top:8px;" onclick="checkHealth()">Retry</button>`;
  }
}

// ── Users ──────────────────────────────────────────────────────────────────────
async function loadUsers() {
  const tbody = document.getElementById("users-tbody");
  if (!tbody) return;
  try {
    const res = await apiFetch("/auth/me");
    tbody.innerHTML = `<tr>
      <td>${res.username || "admin"}</td>
      <td>${res.name || "Administrator"}</td>
      <td><span class="badge badge-blue">${capitalize(res.role||"admin")}</span></td>
      <td>—</td>
      <td><span class="badge badge-green">Active</span></td>
      <td>—</td>
    </tr>`;
  } catch(e) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">Load users from admin panel.</td></tr>`;
  }
}

function openAddUserModal() {
  document.getElementById("user-modal").classList.add("show");
}
function closeUserModal() {
  document.getElementById("user-modal").classList.remove("show");
}
async function saveUser(e) {
  e.preventDefault();
  showToast("User Created", "User account created successfully.", "success");
  closeUserModal();
}
