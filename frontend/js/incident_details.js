
const token = localStorage.getItem("access_token");
if (!token) window.location.href = "login.html";

const clusterId = new URLSearchParams(window.location.search).get("id");
if (!clusterId) window.location.href = "dashboard.html";

const logoutBtn = document.getElementById("logoutBtn");
if (logoutBtn) logoutBtn.onclick = () => {
  localStorage.clear();
  window.location.href = "login.html";
};

function escapeHtml(value){
  return String(value ?? "").replace(/[&<>"']/g,ch=>({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"
  }[ch]));
}

async function loadIncident(){
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 12000);
  try {
  const response = await fetch(`${API_BASE}/incidents/${encodeURIComponent(clusterId)}`,{
    signal: controller.signal,
    headers:{Authorization:`Bearer ${token}`}
  });
  const data = await response.json();
  if(!response.ok){
    throw new Error(data.detail || "Incident details are currently unavailable");
  }

  document.getElementById("incidentTitle").textContent = data.title || `Incident #${clusterId}`;
  document.getElementById("incidentLocation").textContent =
    `${data.area || "-"}, ${data.district || "-"}, ${data.state || "-"}${data.pincode ? ` · ${data.pincode}` : ""}`;
  document.getElementById("reportCount").textContent = data.total_reports ?? data.impact?.report_count ?? 0;
  document.getElementById("affectedCount").textContent = data.impact?.affected_count ?? 0;
  document.getElementById("incidentDepartment").textContent = data.department || "—";
  document.getElementById("impactLevel").textContent = data.impact?.level || "Local";
  document.getElementById("impactReason").textContent =
    `${data.impact?.reason || ""}. This community-impact signal is separate from the ML complaint priority.`;

  const badge = document.getElementById("impactBadge");
  badge.textContent = `${data.impact?.level || "Local"} impact`;
  badge.className = `impact-badge ${(data.impact?.level || "").toLowerCase()}`;

  const statusSummary = document.getElementById("statusSummary");
  statusSummary.innerHTML = Object.entries(data.status_counts || {})
    .map(([status,count])=>`<span class="status-pill">${escapeHtml(status)} · ${count}</span>`).join("");

  const supportBtn = document.getElementById("supportIncidentBtn");
  if(data.already_reported){
    supportBtn.textContent = "✓ Your report counts you as affected";
    supportBtn.disabled = true;
  }else if(data.supported){
    supportBtn.textContent = "✓ You're marked as affected";
    supportBtn.disabled = true;
  }else{
    supportBtn.onclick = supportIncident;
  }

  const previewNote = document.getElementById("reportPreviewNote");
  if (previewNote) {
    const total = data.total_reports ?? 0;
    const active = data.active_reports ?? 0;
    const resolved = data.resolved_reports ?? 0;
    previewNote.textContent =
      `${total} total reports have been submitted for this issue. ${active} are still active and ${resolved} are resolved. ` +
      `For privacy and readability, only the latest ${data.preview_limit || 5} reports are previewed here${data.already_reported ? ", plus your own report when needed" : ""}.`;
  }

  const reports = document.getElementById("incidentReports");
  reports.innerHTML = (data.reports || []).map(r=>`
    <div class="report-row ${r.is_mine ? "mine" : ""}">
      <a href="${r.is_mine ? `complaint_details.html?id=${r.complaint_id}` : "#"}"
         ${r.is_mine ? "" : 'onclick="return false;"'}
         title="${r.is_mine ? "Open your complaint" : "Other citizens' full complaint details remain private"}">#${r.complaint_id}</a>
      <div><div class="report-title">${escapeHtml(r.title)}</div><div class="report-meta">${r.is_mine ? "Your report" : "Recent citizen report"}</div></div>
      <div>${escapeHtml(r.display_status || r.status)}</div>
      <div>${escapeHtml(r.priority || "-")}</div>
    </div>`).join("") || `<p class="muted">This incident has no additional linked reports yet. Your complaint is still being tracked individually.</p>`;
  } catch (error) {
    document.getElementById("incidentTitle").textContent = "Incident summary temporarily unavailable";
    document.getElementById("incidentLocation").textContent = "Your complaint remains submitted; try refreshing or view your complaint details.";
    document.getElementById("incidentReports").innerHTML = `<p class="muted">We couldn't load the incident report right now. ${escapeHtml(error.name === "AbortError" ? "The request timed out." : error.message)} <button type="button" id="retryIncident">Retry</button></p>`;
    document.getElementById("retryIncident").onclick = loadIncident;
    document.getElementById("supportIncidentBtn").disabled = true;
  } finally { clearTimeout(timer); }
}

async function supportIncident(){
  const button = document.getElementById("supportIncidentBtn");
  button.disabled = true;
  try{
    const response = await fetch(`${API_BASE}/incidents/${encodeURIComponent(clusterId)}/support`,{
      method:"POST",
      headers:{Authorization:`Bearer ${token}`}
    });
    const data = await response.json();
    if(!response.ok) throw new Error(data.detail || "Could not update incident");
    button.textContent = data.already_reported
      ? "✓ Your report counts you as affected"
      : "✓ You're marked as affected";
    await loadIncident();
  }catch(error){
    alert(error.message);
    button.disabled = false;
  }
}

loadIncident();
