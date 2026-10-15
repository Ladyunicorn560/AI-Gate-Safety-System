/**
 * employees.js — Employee management + face enrollment
 */

let allEmployees = [];
let empPage = 1;
const empPageSize = 15;
let enrollingEmpId = null;
let enrollFileSelected = false;

window.addEventListener("DOMContentLoaded", async () => {
  if (authToken) {
    await loadContractors();
    loadEmployees();
  }
});

async function loadEmployees() {
  const search    = document.getElementById("emp-search").value;
  const typeFilter = document.getElementById("emp-filter-type").value;
  const enrollFilter = document.getElementById("emp-filter-enrolled").value;

  try {
    const url = search ? `/employees/?q=${encodeURIComponent(search)}` : "/employees/";
    const res = await apiFetch(url);
    let data = res.data || [];

    if (typeFilter) data = data.filter(e => e.EmployeeType === typeFilter);
    if (enrollFilter !== "") data = data.filter(e => String(e.IsEnrolled ? 1 : 0) === enrollFilter);

    allEmployees = data;

    // KPI cards
    const total    = data.length;
    const enrolled = data.filter(e => e.IsEnrolled).length;
    const contract = data.filter(e => e.EmployeeType === "Contract").length;
    document.getElementById("emp-total").textContent      = total;
    document.getElementById("emp-enrolled").textContent   = enrolled;
    document.getElementById("emp-contract").textContent   = contract;
    document.getElementById("emp-not-enrolled").textContent = total - enrolled;

    renderEmployeeTable(data);
  } catch(e) { showToast("Load Error", e.message, "error"); }
}

function renderEmployeeTable(data) {
  empPage = 1;
  document.getElementById("emp-count").textContent = data.length;
  const tbody = document.getElementById("employees-tbody");

  if (!data.length) {
    tbody.innerHTML = `<tr><td colspan="10" class="text-center text-muted" style="padding:32px;">No employees found. Click <strong>+ Add Employee</strong> to register.</td></tr>`;
    document.getElementById("emp-pagination").innerHTML = "";
    return;
  }

  renderEmpPage(data, 1);

  const total = Math.ceil(data.length / empPageSize);
  const pc = document.getElementById("emp-pagination");
  if (total <= 1) { pc.innerHTML = ""; return; }
  pc.innerHTML = Array.from({length: total}, (_, i) =>
    `<button class="page-btn ${i+1===empPage?"active":""}" onclick="empPage=${i+1};renderEmpPage(allEmployees,${i+1})">${i+1}</button>`
  ).join("");
}

function renderEmpPage(data, page) {
  const tbody = document.getElementById("employees-tbody");
  const s = (page - 1) * empPageSize;
  const slice = data.slice(s, s + empPageSize);

  tbody.innerHTML = slice.map(e => `
    <tr>
      <td>
        ${e.IsEnrolled && e.PhotoPath
          ? `<img src="/api/employees/${e.EmployeeID}/photo" style="width:38px;height:38px;border-radius:50%;object-fit:cover;border:2px solid var(--accent-green);" onerror="this.outerHTML='<div style=\\'width:38px;height:38px;border-radius:50%;background:linear-gradient(135deg,var(--accent-blue),var(--accent-cyan));display:flex;align-items:center;justify-content:center;font-weight:700;\\'>${(e.FullName||'?')[0]}</div>'" />`
          : `<div style="width:38px;height:38px;border-radius:50%;background:linear-gradient(135deg,var(--accent-purple),var(--accent-blue));display:flex;align-items:center;justify-content:center;font-weight:700;font-size:14px;">${(e.FullName||"?")[0]}</div>`
        }
      </td>
      <td><span class="badge badge-blue">${e.EmpCode || "—"}</span></td>
      <td><strong>${e.FullName || "—"}</strong></td>
      <td>${e.Department || "—"}</td>
      <td>${e.EmployeeType === "Contract" ? '<span class="badge badge-amber">Contract</span>' : e.EmployeeType === "OAS" ? '<span class="badge badge-purple">O&S</span>' : '<span class="badge badge-blue">Staff</span>'}</td>
      <td>${e.ContractorName || "—"}</td>
      <td>${e.GateName || "Any"}</td>
      <td>${shiftBadge(e.ShiftCode)}</td>
      <td>${e.IsEnrolled ? '<span class="badge badge-green"><span class="dot dot-green"></span> Enrolled</span>' : '<span class="badge badge-amber"><span class="dot dot-amber"></span> Pending</span>'}</td>
      <td>
        <div style="display:flex;gap:6px;">
          <button class="btn btn-secondary btn-sm" onclick="openEnrollModal(${e.EmployeeID}, '${(e.FullName||'').replace(/'/g,"\\'")}')">${e.IsEnrolled ? "Re-Enroll Biometrics" : "Enroll Biometrics"}</button>
          <button class="btn btn-outline-red btn-sm" onclick="if(confirm('Deactivate ${(e.FullName||'').replace(/'/g,"\\'")}?')) deactivateEmployee(${e.EmployeeID})">Remove</button>
        </div>
      </td>
    </tr>`).join("");
}

function shiftBadge(code) {
  const m = { G:"General", A:"Morning", B:"Afternoon", C:"Night" };
  return `<span class="text-muted" style="font-size:12px;">${m[code] || code || "—"}</span>`;
}

// ── Add Employee Modal ─────────────────────────────────────────────────────────
async function loadContractors() {
  try {
    const res = await apiFetch("/employees/contractors");
    const sel = document.getElementById("emp-contractor");
    if (!sel) return;
    (res.data || []).forEach(c => {
      const opt = document.createElement("option");
      opt.value = c.ContractorID;
      opt.textContent = c.ContractorName;
      sel.appendChild(opt);
    });
  } catch(e) {}
}

function openAddEmployeeModal() {
  document.getElementById("emp-modal-title").textContent = "Add New Employee";
  document.getElementById("emp-form").reset();
  document.getElementById("emp-error").textContent = "";
  document.getElementById("emp-modal").classList.add("show");
}

function closeEmpModal() {
  document.getElementById("emp-modal").classList.remove("show");
}

async function saveEmployee(e) {
  e.preventDefault();
  const btn = document.getElementById("emp-save-btn");
  btn.innerHTML = '<span class="spinner"></span> Saving...';
  btn.disabled = true;

  const payload = {
    emp_code:      document.getElementById("emp-code").value,
    full_name:     document.getElementById("emp-fullname").value,
    employee_type: document.getElementById("emp-type").value,
    contractor_id: document.getElementById("emp-contractor").value || null,
    department:    document.getElementById("emp-dept").value,
    designation:   document.getElementById("emp-desig").value,
    gate_id:       document.getElementById("emp-gate").value || null,
    shift_code:    document.getElementById("emp-shift").value,
    phone:         document.getElementById("emp-phone").value,
  };

  try {
    const res = await apiFetch("/employees/", { method: "POST", body: JSON.stringify(payload) });
    showToast("Employee Added", `${payload.full_name} registered. Now enroll their face.`, "success", 5000);
    closeEmpModal();
    loadEmployees();
    // Auto-open enroll modal
    setTimeout(() => openEnrollModal(res.employee_id, payload.full_name), 800);
  } catch(err) {
    document.getElementById("emp-error").textContent = err.message;
  } finally {
    btn.innerHTML = "Save Employee";
    btn.disabled = false;
  }
}

async function deactivateEmployee(empId) {
  try {
    await apiFetch(`/employees/${empId}`, { method: "DELETE" });
    showToast("Deactivated", "Employee deactivated.", "warn");
    loadEmployees();
  } catch(e) { showToast("Error", e.message, "error"); }
}

// ── Face Enrollment Modal ─────────────────────────────────────────────────────
function openEnrollModal(empId, name) {
  enrollingEmpId = empId;
  enrollFileSelected = false;
  document.getElementById("enroll-modal").classList.add("show");
  document.getElementById("enroll-file").value = "";
  document.getElementById("enroll-preview").style.display = "none";
  document.getElementById("enroll-submit-btn").disabled = true;
  document.getElementById("enroll-status").innerHTML = `<p style="color:var(--text-secondary);">Enrolling face for: <strong>${name}</strong></p>`;
}

function closeEnrollModal() {
  document.getElementById("enroll-modal").classList.remove("show");
  enrollingEmpId = null;
}

function previewEnrollPhoto(input) {
  const file = input.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (e) => {
    const preview = document.getElementById("enroll-preview");
    preview.src = e.target.result;
    preview.style.display = "block";
    document.getElementById("enroll-submit-btn").disabled = false;
    enrollFileSelected = true;
  };
  reader.readAsDataURL(file);
}

async function submitEnrollment() {
  if (!enrollingEmpId || !enrollFileSelected) return;
  const file = document.getElementById("enroll-file").files[0];
  if (!file) return;

  const btn = document.getElementById("enroll-submit-btn");
  btn.innerHTML = '<span class="spinner"></span> Processing...';
  btn.disabled = true;

  const statusEl = document.getElementById("enroll-status");
  statusEl.innerHTML = `<p style="color:var(--accent-amber);">Extracting facial vector embedding...</p>`;

  const fd = new FormData();
  fd.append("photo", file);

  try {
    const res = await fetch(`${API_BASE}/employees/${enrollingEmpId}/enroll-face`, {
      method: "POST",
      headers: { "Authorization": `Bearer ${authToken}` },
      body: fd,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Enrollment failed");

    statusEl.innerHTML = `<p style="color:var(--accent-green);">Biometric face vector generated successfully. Employee is ready for gate recognition.</p>`;
    showToast("Face Enrolled", "Personnel biometric vector stored.", "success", 5000);
    setTimeout(() => { closeEnrollModal(); loadEmployees(); }, 1500);
  } catch(err) {
    statusEl.innerHTML = `<p style="color:var(--accent-red);">${err.message}</p>`;
    showToast("Enrollment Failed", err.message, "error");
    btn.innerHTML = "Enroll Face";
    btn.disabled = false;
  }
}
