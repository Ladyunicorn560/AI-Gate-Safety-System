/**
 * app.js — Shared utilities: auth, API calls, toasts, navigation
 */

const API_BASE = (window.location.protocol.startsWith("http") && window.location.port === "5000")
  ? "/api"
  : "http://127.0.0.1:5000/api";
let authToken  = localStorage.getItem("token");
let currentUser = null;

// ── Auth Helpers ──────────────────────────────────────────────────────────────
async function doLogin(e) {
  e.preventDefault();
  const username = document.getElementById("login-username").value;
  const password = document.getElementById("login-password").value;
  const errEl    = document.getElementById("login-error");
  const btn      = document.getElementById("btn-signin");

  btn.innerHTML = '<span class="spinner"></span> Signing in...';
  btn.disabled  = true;
  errEl.textContent = "";

  try {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    
    const contentType = res.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) {
      throw new Error("Backend server is not running on http://127.0.0.1:5000. Please run start.bat!");
    }

    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Login failed");

    authToken   = data.token;
    currentUser = data.user;
    localStorage.setItem("token", authToken);
    localStorage.setItem("user",  JSON.stringify(currentUser));

    hideLoginModal();
    updateUserUI();
    if (typeof loadDashboard === "function") loadDashboard();
    showToast("Welcome back!", `Logged in as ${currentUser.name}`, "success");
  } catch (err) {
    errEl.textContent = err.message;
  } finally {
    btn.innerHTML = "Sign In";
    btn.disabled  = false;
  }
}

function logout() {
  authToken   = null;
  currentUser = null;
  localStorage.removeItem("token");
  localStorage.removeItem("user");
  showLoginModal();
}

function showLoginModal()  {
  document.getElementById("login-modal").classList.add("show");
}
function hideLoginModal()  {
  document.getElementById("login-modal").classList.remove("show");
}

function updateUserUI() {
  try {
    const user = currentUser || JSON.parse(localStorage.getItem("user") || "{}");
    if (!user.name) return;
    const nameEl   = document.getElementById("user-name");
    const roleEl   = document.getElementById("user-role");
    const avatarEl = document.getElementById("user-avatar");
    if (nameEl)   nameEl.textContent   = user.name;
    if (roleEl)   roleEl.textContent   = capitalize(user.role || "user");
    if (avatarEl) avatarEl.textContent = user.name[0].toUpperCase();
  } catch(e) {}
}

// ── API Fetcher ───────────────────────────────────────────────────────────────
async function apiFetch(endpoint, options = {}) {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${authToken}`,
      ...(options.headers || {}),
    },
  });
  if (res.status === 401) { logout(); throw new Error("Session expired"); }
  const contentType = res.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    throw new Error("Backend server is offline or unreachable.");
  }
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

async function apiDownload(endpoint, filename) {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    headers: { "Authorization": `Bearer ${authToken}` },
  });
  if (!res.ok) throw new Error("Download failed");
  const blob = await res.blob();
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

// ── Toast Notifications ───────────────────────────────────────────────────────
function showToast(title, msg = "", type = "info", duration = 4000) {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span class="toast-dot toast-dot-${type}"></span>
    <div class="toast-text">
      <div class="toast-title">${title}</div>
      ${msg ? `<div class="toast-msg">${msg}</div>` : ""}
    </div>
  `;
  container.appendChild(toast);
  setTimeout(() => { toast.style.opacity = "0"; toast.style.transform = "translateX(30px)"; toast.style.transition = "0.3s"; setTimeout(() => toast.remove(), 300); }, duration);
}

// ── Utilities ─────────────────────────────────────────────────────────────────
function capitalize(str) { return str ? str.charAt(0).toUpperCase() + str.slice(1) : ""; }

function formatTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
}

function formatDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

function formatDateTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

function violationBadge(type) {
  return `<span class="badge badge-red"><span class="dot dot-red"></span> ${type}</span>`;
}

function complianceBadge(isCompliant) {
  return isCompliant
    ? `<span class="badge badge-green"><span class="dot dot-green"></span> Compliant</span>`
    : `<span class="badge badge-red"><span class="dot dot-red"></span> Non-Compliant</span>`;
}

function enrolledBadge(isEnrolled) {
  return isEnrolled
    ? `<span class="badge badge-green"><span class="dot dot-green"></span> Enrolled</span>`
    : `<span class="badge badge-amber"><span class="dot dot-amber"></span> Pending</span>`;
}

// ── Clock ─────────────────────────────────────────────────────────────────────
function updateClock() {
  const el = document.getElementById("current-datetime");
  if (el) {
    const now = new Date();
    el.textContent = now.toLocaleDateString("en-IN", {
      weekday: "long", day: "numeric", month: "long", year: "numeric",
      hour: "2-digit", minute: "2-digit", second: "2-digit"
    });
  }
}

// ── Logout Button ─────────────────────────────────────────────────────────────
document.getElementById("btn-logout")?.addEventListener("click", () => {
  if (confirm("Sign out?")) logout();
});

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  updateClock();
  setInterval(updateClock, 1000);
  updateUserUI();

  // Check auth
  if (!authToken) {
    showLoginModal();
  } else {
    hideLoginModal();
    currentUser = JSON.parse(localStorage.getItem("user") || "{}");
  }

  // Active nav highlight
  const path = window.location.pathname.split("/").pop();
  document.querySelectorAll(".nav-item").forEach(item => {
    const href = item.getAttribute("href") || "";
    if (href.includes(path) || (path === "" && href.includes("index"))) {
      item.classList.add("active");
    } else {
      item.classList.remove("active");
    }
  });
});
