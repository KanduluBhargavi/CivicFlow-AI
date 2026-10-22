function escHtml(v){return String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}
// ===============================
// Department Dashboard
// ===============================

const token = localStorage.getItem("access_token");

if (!token) {
    window.location.href = "login.html";
}

const actualRole = (localStorage.getItem("actual_role") || "manager").toLowerCase();
const isOfficer = actualRole === "officer";

function applyDashboardRole() {
    const purpose = document.getElementById("dashboardPurpose");
    const nav = document.getElementById("complaintsNavLabel");
    const profile = document.getElementById("profileNavLabel");
    const oversight = document.getElementById("managerOversight");
    if (isOfficer) {
        if (purpose) purpose.textContent = "Work only on complaints assigned to you, record field actions, meet SLA deadlines and update resolution status.";
        if (nav) nav.textContent = "My Assigned Complaints";
        if (profile) profile.textContent = "Account / Password";
        if (oversight) oversight.style.display = "none";
    } else {
        if (purpose) purpose.textContent = "Coordinate complaint assignment, officer workload, SLA risk, rerouting and departmental accountability.";
        if (nav) nav.textContent = "Department Complaint Queue";
        if (profile) profile.textContent = "Department Profile";
    }
}
applyDashboardRole();

// ===============================
// Logout
// ===============================

function logout() {

    localStorage.clear();

    window.location.href = "login.html";

}

document.getElementById("logoutBtn").addEventListener("click", logout);
document.getElementById("logoutSide").addEventListener("click", logout);

// ===============================
// Load Dashboard Stats
// ===============================

async function loadDashboardStats() {

    try {

        const response = await fetch(`${API_BASE}/department/dashboard`, {

            headers: {
                Authorization: `Bearer ${token}`
            }

        });

        if (!response.ok) {

            alert("Session Expired");

            logout();

            return;

        }

        const data = await response.json();

        document.getElementById("totalComplaintsCount").textContent =
            data.total || 0;

        document.getElementById("pendingCount").textContent =
            data.pending || 0;

        document.getElementById("progressCount").textContent =
            data.in_progress || 0;

        document.getElementById("resolvedCount").textContent =
            data.resolved || 0;

        const criticalCount = Number(data.critical_priority) || 0;
        const highCount = Number(data.high_priority) || 0;
        document.getElementById("highPriorityCount").textContent = criticalCount + highCount;
        const priorityWatchSummary = document.getElementById("priorityWatchSummary");
        if (priorityWatchSummary) priorityWatchSummary.textContent = `${criticalCount} critical · ${highCount} high; critical cases are listed first.`;

        [
          ["unassignedCount", data.unassigned],
          ["atRiskCount", data.at_risk],
          ["breachedCount", data.sla_breached],
          ["activeOfficerCount", data.active_officers]
        ].forEach(([id,val]) => { const el=document.getElementById(id); if(el) el.textContent = val || 0; });

        document.getElementById("departmentName").textContent =
            localStorage.getItem("department") || "Department";

        document.getElementById("welcomeDepartment").textContent =
            (localStorage.getItem("actual_role") === "officer"
                ? (localStorage.getItem("name") || localStorage.getItem("department"))
                : localStorage.getItem("department")) || "Department";

    }

    catch (err) {

        console.log(err);

    }

}

// ===============================
// Department-scoped emerging incident alerts and map
// ===============================
let departmentIncidentMap = null;
let departmentIncidentLayer = null;
let departmentMapComplaints = [];
let departmentLeafletPromise = null;
function loadDepartmentLeaflet(){
    if(typeof L!=='undefined')return Promise.resolve();
    if(departmentLeafletPromise)return departmentLeafletPromise;
    departmentLeafletPromise=new Promise((resolve,reject)=>{
        const css=document.createElement('link');css.rel='stylesheet';css.href='https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';document.head.appendChild(css);
        const script=document.createElement('script');script.src='https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';script.onload=resolve;script.onerror=()=>reject(new Error('Leaflet unavailable'));document.body.appendChild(script);
    }).catch(error=>{departmentLeafletPromise=null;throw error;});
    return departmentLeafletPromise;
}
function ensureDepartmentIncidentMap() {
    const el = document.getElementById("departmentIncidentMap");
    if (!el || typeof L === "undefined") return null;
    if (!departmentIncidentMap) {
        departmentIncidentMap = L.map(el, { zoomControl: false }).setView([20.2, 84.5], 6);
        const voyager = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors', maxZoom: 19
        });
        const humanitarian = L.tileLayer('https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors, Tiles style by Humanitarian OpenStreetMap Team', maxZoom: 19
        });
        voyager.addTo(departmentIncidentMap);
        L.control.zoom({ position: 'topright' }).addTo(departmentIncidentMap);
        L.control.scale({ imperial: false, position: 'bottomleft' }).addTo(departmentIncidentMap);
        L.control.layers({ 'Detailed streets': voyager, 'Humanitarian': humanitarian }, {}, { collapsed: true }).addTo(departmentIncidentMap);
        departmentIncidentLayer = L.layerGroup().addTo(departmentIncidentMap);
    }
    return departmentIncidentMap;
}
function fillDepartmentMapFilters(complaints){
    const stateSel=document.getElementById('departmentMapStateFilter'), districtSel=document.getElementById('departmentMapDistrictFilter');
    if(!stateSel||!districtSel)return;
    const rows=Array.isArray(complaints)?complaints:[];
    const oldState=stateSel.value,oldDistrict=districtSel.value;
    const states=[...new Set(rows.map(c=>(c.state||'').trim()).filter(Boolean))].sort((a,b)=>a.localeCompare(b));
    stateSel.innerHTML='<option value="">All States / UTs</option>'+states.map(v=>`<option value="${escHtml(v)}">${escHtml(v)}</option>`).join('');
    stateSel.value=states.includes(oldState)?oldState:'';
    const stateRows=rows.filter(c=>!stateSel.value||(c.state||'').trim()===stateSel.value);
    const districts=[...new Set(stateRows.map(c=>(c.district||'').trim()).filter(Boolean))].sort((a,b)=>a.localeCompare(b));
    districtSel.innerHTML='<option value="">All Districts</option>'+districts.map(v=>`<option value="${escHtml(v)}">${escHtml(v)}</option>`).join('');
    districtSel.value=districts.includes(oldDistrict)?oldDistrict:'';
}
function renderDepartmentMapAnalysis(rows,totalLocated,scopeLabel){
    const el=document.getElementById('departmentMapAnalysis');if(!el)return;
    const unresolved=rows.filter(c=>(c.status||'').toLowerCase()!=='resolved');
    const critical=rows.filter(c=>(c.priority||'').toLowerCase()==='critical').length;
    const high=rows.filter(c=>(c.priority||'').toLowerCase()==='high').length;
    const resolved=rows.length-unresolved.length;
    const areas=new Map();rows.forEach(c=>{const name=(c.area||'').trim()||'Area not provided';areas.set(name,(areas.get(name)||0)+1)});
    const leaders=[...areas.entries()].sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0])).slice(0,4);
    const areaSummary=leaders.length?leaders.map(([name,count])=>`${escHtml(name)} (${count})`).join(', '):'No area details are available for the selected points.';
    const coverage=totalLocated?Math.round(rows.length/totalLocated*100):0;
    el.innerHTML=`<h3>Filtered map analysis <small>· ${escHtml(scopeLabel)}</small></h3>
      <div class="map-analysis-grid">
        <div class="map-analysis-stat"><span>Complaints in view</span><strong>${rows.length}</strong></div>
        <div class="map-analysis-stat"><span>Critical</span><strong>${critical}</strong></div>
        <div class="map-analysis-stat"><span>High</span><strong>${high}</strong></div>
        <div class="map-analysis-stat"><span>Unresolved</span><strong>${unresolved.length}</strong></div>
        <div class="map-analysis-stat"><span>Resolved</span><strong>${resolved} (${rows.length?Math.round(resolved/rows.length*100):0}%)</strong></div>
        <div class="map-analysis-stat"><span>Filter coverage</span><strong>${coverage}%</strong></div>
      </div><div class="map-analysis-notes">
        <p><b>Most reported areas:</b> ${areaSummary}</p>
        <p><b>Operational signal:</b> ${critical?`${critical} Critical complaint(s) need immediate review.`:high?`${high} High-priority complaint(s) are present.`:'No Critical or High complaints in this filtered view.'}</p>
        <p><b>Interpretation:</b> Counts cover this department's visible cases with valid coordinates. Nearby reports can suggest a service concentration; verify details before treating them as one confirmed incident.</p>
      </div>`;
}
function renderDepartmentIncidentMap(alerts, complaints) {
    if(typeof L==='undefined'){
        loadDepartmentLeaflet().then(()=>renderDepartmentIncidentMap(alerts,complaints)).catch(error=>console.warn('Department map unavailable',error));
        return;
    }
    const map=ensureDepartmentIncidentMap(); if(!map||!departmentIncidentLayer)return;
    departmentMapComplaints=Array.isArray(complaints)?complaints:[];
    fillDepartmentMapFilters(departmentMapComplaints);
    const stateSel=document.getElementById('departmentMapStateFilter'),districtSel=document.getElementById('departmentMapDistrictFilter');
    if(stateSel&&!stateSel.dataset.bound){stateSel.addEventListener('change',()=>{fillDepartmentMapFilters(departmentMapComplaints);renderDepartmentIncidentMap([],departmentMapComplaints);});stateSel.dataset.bound='1';}
    if(districtSel&&!districtSel.dataset.bound){districtSel.addEventListener('change',()=>{fillDepartmentMapFilters(departmentMapComplaints);renderDepartmentIncidentMap([],departmentMapComplaints);});districtSel.dataset.bound='1';}
    departmentIncidentLayer.clearLayers();
    const validPoint=item=>item.latitude!==null&&item.latitude!==''&&item.longitude!==null&&item.longitude!==''&&Number.isFinite(Number(item.latitude))&&Number.isFinite(Number(item.longitude))&&Number(item.latitude)!==0&&Number(item.longitude)!==0&&Number(item.latitude)>=-90&&Number(item.latitude)<=90&&Number(item.longitude)>=-180&&Number(item.longitude)<=180;
    const state=stateSel?.value||'',district=districtSel?.value||'';
    const allLocated=departmentMapComplaints.filter(validPoint);
    const rows=allLocated.filter(c=>(!state||(c.state||'').trim()===state)&&(!district||(c.district||'').trim()===district));
    const scopeLabel=[district,state].filter(Boolean).join(', ')||'All department locations';
    renderDepartmentMapAnalysis(rows,allLocated.length,scopeLabel);
    const duplicateCounts=new Map(),bounds=[];
    rows.forEach(c=>{
        const lat=Number(c.latitude),lon=Number(c.longitude),key=`${lat.toFixed(6)}:${lon.toFixed(6)}`;
        const stack=duplicateCounts.get(key)||0;duplicateCounts.set(key,stack+1);
        const angle=stack*137.508*Math.PI/180,offset=stack===0?0:0.00010*Math.ceil(stack/6);
        const point=[lat+Math.sin(angle)*offset,lon+Math.cos(angle)*offset];
        const priority=String(c.priority||'low').toLowerCase();
        const color=priority==='critical'?'#991b1b':priority==='high'?'#dc2626':priority==='medium'?'#ea8a0a':'#2563eb';
        const id=Number(c.complaint_id)||0;
        L.circleMarker(point,{radius:6,color:'#fff',weight:1.5,fillColor:color,fillOpacity:.92}).addTo(departmentIncidentLayer)
          .bindPopup(`<strong>Complaint #${id}</strong><br>${escHtml(c.title||'Complaint')}<br><strong>Priority:</strong> ${escHtml(c.priority||'Unknown')}<br><strong>Status:</strong> ${escHtml(c.display_status||c.status||'Unknown')}<br><strong>Area / Block:</strong> ${escHtml(c.area||'Not provided')}<br><strong>Address:</strong> ${escHtml(c.address||'Not provided')}<br><strong>Location:</strong> ${escHtml(c.district||'District not specified')}, ${escHtml(c.state||'State not specified')}<br><small>Marker may be slightly offset when multiple reports share identical coordinates. District-centroid coordinates are not exact address points.</small>`);
        bounds.push(point);
    });
    const count=document.getElementById('departmentMapResultCount');if(count)count.textContent=`Showing ${rows.length} of ${allLocated.length} geolocated complaints`;
    if(bounds.length===1)map.setView(bounds[0],15);else if(bounds.length>1)map.fitBounds(L.latLngBounds(bounds).pad(0.18),{maxZoom:15});else map.setView(state?[20.2,84.5]:[22.8,79],state?7:5);
    setTimeout(()=>map.invalidateSize(),120);
}
function renderDepartmentSurgeAlerts(payload) {
    const list = document.getElementById("departmentSurgeAlertList");
    if (!list) return;
    const alerts = Array.isArray(payload?.alerts) ? payload.alerts : [];
    renderDepartmentIncidentMap(alerts, Array.isArray(payload?.department_complaints) ? payload.department_complaints : []);
    if (!alerts.length) {
        list.innerHTML = '<p style="margin:0;color:var(--muted,#64748b)">No emerging incident alerts for this department right now. Alerts require 3 different citizens in 24 hours, or 2 including a Critical report.</p>';
        return;
    }
    list.innerHTML = alerts.map(a => {
        const critical = String(a.highest_priority || '').toLowerCase() === 'critical';
        return `<article style="border:1px solid ${critical ? '#ef4444' : '#f59e0b'};border-radius:12px;padding:14px;background:var(--card-bg,#fff)">
          <div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap"><strong>${escHtml(a.title || 'Possible growing incident')}</strong><span style="font-weight:700;color:${critical ? '#dc2626' : '#b45309'}">${escHtml(a.highest_priority || 'Priority unknown')}</span></div>
          <p style="margin:8px 0;color:var(--muted,#64748b)">${escHtml(a.district || 'District not specified')}, ${escHtml(a.state || '')}</p>
          <div style="display:flex;gap:14px;flex-wrap:wrap"><span><b>${Number(a.reports_last_24h)||0}</b> reports / 24h</span><span><b>${Number(a.distinct_reporters_last_24h)||0}</b> different citizens</span><span><b>${Number(a.unresolved_reports)||0}</b> unresolved</span><span><b>${Number(a.total_reports)||0}</b> linked total</span></div>
          <p style="margin:10px 0 0">${escHtml(a.alert_reason || 'Review this incident cluster.')}</p>
          <small style="display:block;margin-top:8px;color:var(--muted,#64748b)">Early-warning signal only; verify details before treating this as a confirmed incident.${a.location_available ? '' : ' No usable coordinates are available, so this alert is not pinned on the map.'}</small>
        </article>`;
    }).join('');
}
async function loadDepartmentSurgeAlerts() {
    const list = document.getElementById("departmentSurgeAlertList");
    const headers={Authorization:`Bearer ${token}`};
    const loadComplaints=async()=>{
        const all=[];let offset=0;const pageSize=1000;
        while(true){
            const response=await fetch(`${API_BASE}/department/complaints?limit=${pageSize}&offset=${offset}`,{headers});
            if(!response.ok)throw new Error('Could not load the full department complaint list.');
            const page=await response.json();if(!Array.isArray(page))throw new Error('Department complaint data was not a list.');
            all.push(...page);if(page.length<pageSize)break;offset+=page.length;
        }
        return all;
    };
    const [complaintResult,alertResult]=await Promise.allSettled([
        loadComplaints(),
        list?fetch(`${API_BASE}/department/emerging-incident-alerts`,{headers}):Promise.resolve(null)
    ]);
    let departmentComplaints=[];
    if(complaintResult.status==='fulfilled')departmentComplaints=complaintResult.value;
    // Keep the complaint map useful when the optional alert service fails.
    renderDepartmentIncidentMap([],departmentComplaints);
    if(!list)return;
    if(complaintResult.status==='rejected'){
        renderDepartmentIncidentMap([],[]);
        list.innerHTML='<p class="map-alert-error" role="status">Department complaints could not be loaded. Refresh the page or check your connection.</p>';
        return;
    }
    if(alertResult.status==='rejected'||!alertResult.value?.ok){
        renderDepartmentSurgeAlerts({alerts:[],department_complaints:departmentComplaints});
        list.insertAdjacentHTML('afterbegin','<p class="map-alert-error" role="status">Incident alerts could not be refreshed. The complaint map and filtered analysis are still available.</p>');
        return;
    }
    const payload=await alertResult.value.json().catch(()=>({}));
    payload.department_complaints=departmentComplaints;
    renderDepartmentSurgeAlerts(payload);
}
const refreshEmergingAlertsBtn = document.getElementById("refreshEmergingAlerts");
if (refreshEmergingAlertsBtn) refreshEmergingAlertsBtn.addEventListener("click", loadDepartmentSurgeAlerts);
if (isOfficer) {
    const incidentPanel = document.getElementById("emergingIncidentPanel");
    if (incidentPanel) incidentPanel.style.display = "none";
} else {
    loadDepartmentSurgeAlerts();
    setInterval(loadDepartmentSurgeAlerts, 60000);
}

// ===============================
// Latest Activity
// ===============================

function timeAgo(dateString) {
    if (!dateString) return "recently";
    const timestamp = new Date(dateString).getTime();
    if (!Number.isFinite(timestamp)) return "recently";
    const diffMs = Math.max(0, Date.now() - timestamp);
    const mins = Math.floor(diffMs / 60000);

    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;

    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;

    const days = Math.floor(hours / 24);
    return `${days}d ago`;

}

function updateLatestActivity(complaints) {
    const el = document.getElementById("latestActivity");
    if (!el) return;
    const mine = (Array.isArray(complaints) ? complaints : [])
        .filter(item => item.latest_activity_at && item.latest_activity_actor)
        .sort((a, b) => new Date(b.latest_activity_at).getTime() - new Date(a.latest_activity_at).getTime());
    if (!mine.length) {
        const roleName = (localStorage.getItem("actual_role") || "manager").toLowerCase() === "officer" ? "you" : "the Department Head";
        el.textContent = `No recent actions recorded by ${roleName}.`;
        return;
    }
    const latest = mine[0];
    let action = latest.latest_activity_title || "Complaint updated";
    const actualRole = (localStorage.getItem("actual_role") || localStorage.getItem("role") || "").toLowerCase();
    const currentName = (localStorage.getItem("name") || "").trim().toLowerCase();
    const assignedName = (latest.assignee || "").trim().toLowerCase();
    if (latest.latest_activity_type === "officer_assignment") {
        action = actualRole === "officer" && currentName && assignedName === currentName
            ? "Complaint assigned to you"
            : (latest.latest_activity_title || `Assigned to ${latest.assignee || "an officer"}`);
    }
    el.textContent = `Complaint #${latest.complaint_id} - ${action} (${timeAgo(latest.latest_activity_at)})`;
}

// ===============================
// Load Complaints
// ===============================

async function loadComplaints() {

    try {

        const response = await fetch(`${API_BASE}/department/complaints`, {

            headers: {

                Authorization: `Bearer ${token}`

            }

        });

        const complaints = await response.json();

        updateLatestActivity(complaints);

        const tbody = document.getElementById("complaintsTable");

        const seeMoreBtn = document.getElementById("seeMoreBtn");

        tbody.innerHTML = "";

        // Dashboard only shows the 5 most recent complaints.
        // Full list lives on the "Assigned Complaints" page.
        seeMoreBtn.style.display =
            complaints.length > 5 ? "inline-flex" : "none";

        const recentComplaints = complaints.slice(0, 5);

        if (complaints.length === 0) {

            tbody.innerHTML = `

            <tr>

                <td colspan="6">

                    No complaints found.

                </td>

            </tr>

            `;

            return;

        }

        recentComplaints.forEach(c => {

            tbody.innerHTML += `

            <tr>

                <td>${c.complaint_id}</td>

                <td>${escHtml(c.title)}</td>

                <td>${c.priority}</td>

                <td>${escHtml(c.display_status || c.status)}</td>

                <td>${new Date(c.created_at).toLocaleDateString()}</td>

                <td>

                    <button class="view-btn"
                    onclick="viewComplaint(${c.complaint_id})">

                    View

                    </button>

                </td>

            </tr>

            `;

        });

    }

    catch (err) {

        console.log(err);

    }

}

// ===============================
// View Complaint
// ===============================

function viewComplaint(id) {

    window.location.href =
        `department_complaint_details.html?id=${id}`;

}

// ===============================
// Load Dashboard
// ===============================

loadDashboardStats();

loadComplaints();

setInterval(() => {

    loadDashboardStats();

    loadComplaints();

}, 30000);

function setupDepartmentNotificationMenu(){
    const btn = document.getElementById("departmentNotificationBtn");
    const menu = document.getElementById("departmentNotificationMenu");
    if (!btn || !menu) return;
    btn.addEventListener("click", (event) => { event.stopPropagation(); menu.classList.toggle("open"); });
    document.addEventListener("click", (event) => { if (!menu.contains(event.target) && event.target !== btn) menu.classList.remove("open"); });
}

// ===============================
// SLA Notifications
// ===============================
async function loadNotifications() {
    try {
        const response = await fetch(`${API_BASE}/department/notifications`, {
            headers: { Authorization: `Bearer ${token}` }
        });
        if (!response.ok) return;
        const data = await response.json();
        const count = document.getElementById("notificationCount");
        const list = document.getElementById("notificationList");
        if (!count || !list) return;
        const unread = Number(data.unread_count ?? data.count ?? 0);
        count.textContent = unread > 99 ? "99+" : String(unread);
        count.style.display = unread ? "flex" : "none";
        const items = data.notifications || [];
        if (!items.length) {
            list.innerHTML = '<p class="notification-empty">No notifications yet. New assignments and important updates will appear here.</p>';
            return;
        }
        list.innerHTML = items.slice(0, 20).map(n => {
            const type = String(n.type || "update");
            const cssClass = n.is_read ? "is-read" : "is-unread";
            const complaintId = Number(n.complaint_id || 0);
            const openLink = complaintId ? `<a href="department_complaint_details.html?id=${complaintId}">Open</a>` : "";
            const readButton = n.is_read ? '<span class="notification-read-label">Read</span>' :
                `<button type="button" class="notification-mark-read" data-notification-id="${Number(n.notification_id)}">Mark read</button>`;
            const timestamp = n.timestamp ? new Date(n.timestamp).toLocaleString() : "";
            return `
                <div class="notification-item ${cssClass} ${escHtml(type)}">
                    <div class="notification-item-main">
                        <strong>${escHtml(n.title || n.complaint_title || "CivicFlow update")}</strong>
                        <p>${escHtml(n.message || "There is an update requiring your attention.")}</p>
                        ${timestamp ? `<small class="notification-timestamp">${escHtml(timestamp)}</small>` : ""}
                    </div>
                    <div class="notification-item-actions">${openLink}${readButton}</div>
                </div>`;
        }).join("");
    } catch (err) {
        console.log("Notification load error", err);
    }
}

async function markNotificationRead(notificationId) {
    try {
        const response = await fetch(`${API_BASE}/department/notifications/${Number(notificationId)}/read`, {
            method: "PATCH", headers: { Authorization: `Bearer ${token}` }
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || "Unable to mark notification as read");
        await loadNotifications();
    } catch (err) { alert(err.message || "Unable to update notification"); }
}

async function markAllNotificationsRead() {
    try {
        const response = await fetch(`${API_BASE}/department/notifications/read-all`, {
            method: "PATCH", headers: { Authorization: `Bearer ${token}` }
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || "Unable to mark notifications as read");
        await loadNotifications();
    } catch (err) { alert(err.message || "Unable to update notifications"); }
}

document.addEventListener("click", event => {
    const readButton = event.target.closest(".notification-mark-read");
    if (readButton) markNotificationRead(readButton.dataset.notificationId);
});
const markAllBtn = document.getElementById("markAllNotificationsRead");
if (markAllBtn) markAllBtn.addEventListener("click", markAllNotificationsRead);
// ===============================
// Geographic Complaint Groups
// Department Head: District -> Area/Locality -> Complaints
// ===============================

function escapeLocationHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function toggleLocationDistrict(index) {
    const body = document.getElementById(`locationDistrictBody-${index}`);
    const icon = document.getElementById(`locationDistrictIcon-${index}`);
    if (!body) return;
    const isOpen = body.classList.toggle("open");
    if (icon) icon.textContent = isOpen ? "−" : "+";
}
window.toggleLocationDistrict = toggleLocationDistrict;

function toggleLocationArea(districtIndex, areaIndex) {
    const list = document.getElementById(`locationAreaComplaints-${districtIndex}-${areaIndex}`);
    const button = document.getElementById(`locationAreaBtn-${districtIndex}-${areaIndex}`);
    if (!list) return;
    const isOpen = list.classList.toggle("open");
    if (button) button.textContent = isOpen ? "Hide complaints" : "View complaints";
}
window.toggleLocationArea = toggleLocationArea;

async function loadLocationGroups() {
    if (isOfficer) return;

    const container = document.getElementById("locationGroups");
    const summary = document.getElementById("locationGroupSummary");
    if (!container) return;

    try {
        const response = await fetch(`${API_BASE}/department/location-groups`, {
            headers: { Authorization: `Bearer ${token}` }
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.detail || "Unable to load location groups");
        }

        const data = await response.json();
        if (summary) {
            summary.textContent = `${data.district_count || 0} district(s) · ${data.total_complaints || 0} complaint(s)`;
        }

        const districts = data.districts || [];
        if (!districts.length) {
            container.innerHTML = `
                <div class="location-empty">
                    <i class="fa-regular fa-map"></i>
                    <strong>No location groups yet</strong>
                    <span>District and area groups appear here after complaints are submitted.</span>
                </div>`;
            return;
        }

        container.innerHTML = districts.map((district, dIndex) => `
            <article class="location-district-card">
                <button class="location-district-head" type="button" onclick="toggleLocationDistrict(${dIndex})">
                    <div class="location-district-title">
                        <span class="location-map-icon"><i class="fa-solid fa-location-dot"></i></span>
                        <div>
                            <strong>${escapeLocationHtml(district.district)}</strong>
                            <small>${escapeLocationHtml(district.state)} · ${district.area_count} area/locality group(s)</small>
                        </div>
                    </div>
                    <div class="location-district-metrics">
                        <span><b>${district.total}</b> total</span>
                        <span class="location-active"><b>${district.active}</b> active</span>
                        <span class="location-priority"><b>${district.high_critical}</b> high/critical</span>
                        <span class="location-expand" id="locationDistrictIcon-${dIndex}">+</span>
                    </div>
                </button>

                <div class="location-district-body" id="locationDistrictBody-${dIndex}">
                    <div class="location-area-grid">
                        ${(district.areas || []).map((area, aIndex) => `
                            <section class="location-area-card">
                                <div class="location-area-head">
                                    <div>
                                        <span class="location-area-kicker">Area / Locality</span>
                                        <h3>${escapeLocationHtml(area.area)}</h3>
                                        <small>${area.pincode ? `Pincode ${escapeLocationHtml(area.pincode)}` : "Pincode not provided"}</small>
                                    </div>
                                    <span class="location-area-count">${area.total}</span>
                                </div>

                                <div class="location-area-stats">
                                    <span>${area.active} active</span>
                                    <span>${area.resolved} resolved</span>
                                    <span>${area.high_critical} high/critical</span>
                                </div>

                                <button
                                    class="location-view-btn"
                                    id="locationAreaBtn-${dIndex}-${aIndex}"
                                    type="button"
                                    onclick="toggleLocationArea(${dIndex}, ${aIndex})">
                                    View complaints
                                </button>

                                <div
                                    class="location-area-complaints"
                                    id="locationAreaComplaints-${dIndex}-${aIndex}">
                                    ${(area.complaints || []).map(c => `
                                        <a class="location-complaint-row" href="department_complaint_details.html?id=${c.complaint_id}">
                                            <div>
                                                <strong>#${c.complaint_id} · ${escapeLocationHtml(c.title)}</strong>
                                                <small>${escapeLocationHtml(c.display_status || c.status)} · ${escapeLocationHtml(c.priority || "—")}</small>
                                            </div>
                                            <i class="fa-solid fa-arrow-right"></i>
                                        </a>
                                    `).join("")}
                                </div>
                            </section>
                        `).join("")}
                    </div>
                </div>
            </article>
        `).join("");

    } catch (err) {
        console.error("Location grouping load error", err);
        container.innerHTML = `<div class="empty-inline">${escapeLocationHtml(err.message)}</div>`;
    }
}


// ===============================
// Officer Accountability
// ===============================
async function loadOfficerPerformance() {
    try {
        const response = await fetch(`${API_BASE}/department/officers`, {
            headers: { Authorization: `Bearer ${token}` }
        });
        if (!response.ok) return;
        const officers = await response.json();
        window.__civicflowOfficerRows = officers;
        const tbody = document.getElementById("officerPerformanceBody");
        if (!tbody) return;

        if (!officers.length) {
            tbody.innerHTML = '<tr><td colspan="11">No officer accounts yet. Use “Add Officer” above.</td></tr>';
            return;
        }

        const fmtPercent = value => value === null || value === undefined ? "—" : `${Number(value).toFixed(1)}%`;
        const fmtHours = value => value === null || value === undefined ? "—" : `${Number(value).toFixed(1)} h`;
        const fmtRating = (value, count) => value === null || value === undefined ? "—" : `${Number(value).toFixed(1)}/5 <small>(${count || 0})</small>`;

        tbody.innerHTML = officers.map(o => `
            <tr class="${o.is_active ? '' : 'officer-inactive'}">
                <td><strong>${escHtml(o.name)}</strong><br><small>${escHtml(o.email)}</small></td>
                <td>${escHtml([o.area || 'Posted locality not set', o.district || 'District not set', o.state || 'State not set'].join(', '))}<br><small>${escHtml(o.specialization || 'General')}${!o.area || !o.district || !o.state ? ' · Update posting details' : ''}</small></td>
                <td><strong>${o.active_cases}/${o.max_active_cases}</strong><br><small>${o.assigned_historical ?? o.assigned ?? 0} recorded assignments</small></td>
                <td>${o.resolved_historical ?? o.resolved ?? 0}</td>
                <td>${fmtPercent(o.resolution_rate)}</td>
                <td>${fmtPercent(o.sla_compliance_rate)}</td>
                <td>${fmtHours(o.avg_resolution_hours)}</td>
                <td>${fmtRating(o.avg_citizen_rating, o.rating_count)}</td>
                <td><span class="performance-chip ${o.performance_index >= 80 ? 'strong' : o.performance_index >= 60 ? 'steady' : 'limited'}">${o.performance_index === null || o.performance_index === undefined ? 'No history' : Number(o.performance_index).toFixed(1)}</span><br><small>${o.reopened_cases || 0} reopened</small></td>
                <td><span class="officer-status ${o.is_active ? 'active' : 'inactive'}">${o.is_active ? 'Active' : 'Inactive'}</span></td>
                <td><div class="officer-manage-actions"><button class="officer-edit-btn" onclick="editOfficerProfile(${o.user_id})">Edit profile</button><button class="officer-toggle-btn ${o.is_active ? '' : 'is-inactive'}" type="button" title="${o.is_active ? 'Deactivate' : 'Reactivate'} ${escHtml(o.name)}" aria-label="${o.is_active ? 'Deactivate' : 'Reactivate'} ${escHtml(o.name)}" onclick="setOfficerStatus(${o.user_id}, ${!o.is_active})"><i class="fa-solid ${o.is_active ? 'fa-toggle-on' : 'fa-toggle-off'}" aria-hidden="true"></i></button><button class="officer-delete-btn" onclick="deleteOfficer(${o.user_id})">Delete</button></div></td>
            </tr>
        `).join("");
    } catch (err) {
        console.log("Officer performance load error", err);
    }
}

async function editOfficerProfile(officerId) {
    const officer = (window.__civicflowOfficerRows || []).find(row => Number(row.user_id) === Number(officerId));
    const dialog = document.getElementById("officerProfileDialog");
    if (!officer || !dialog) return;
    await officerEditDropdownReady;
    document.getElementById("editOfficerName").value = officer.name || "";
    document.getElementById("editOfficerEmail").value = officer.email || "";
    document.getElementById("editOfficerPhone").value = officer.phone || "";
    document.getElementById("editOfficerArea").value = officer.area || "";
    document.getElementById("editOfficerSpecialization").value = officer.specialization || "General";
    document.getElementById("editOfficerCapacity").value = officer.max_active_cases || 20;
    const state = document.getElementById("editOfficerState");
    const district = document.getElementById("editOfficerDistrict");
    state.value = officer.state || "";
    state.dispatchEvent(new Event("change"));
    if (officer.state && ![...state.options].some(option => option.value === officer.state)) {
        state.add(new Option(officer.state, officer.state));
        state.value = officer.state;
    }
    if (officer.district && ![...district.options].some(option => option.value === officer.district)) {
        district.add(new Option(officer.district, officer.district));
    }
    district.value = officer.district || "";
    dialog.dataset.officerId = String(officerId);
    dialog.showModal();
}
window.editOfficerProfile = editOfficerProfile;

async function saveOfficerProfile(event) {
    event.preventDefault();
    const form = document.getElementById("officerProfileForm");
    if (!form?.reportValidity()) return;
    const dialog = document.getElementById("officerProfileDialog");
    const officerId = dialog?.dataset.officerId;
    const saveButton = document.getElementById("saveOfficerProfileBtn");
    if (!officerId) return;
    saveButton.disabled = true;
    try {
        const response = await fetch(`${API_BASE}/department/officers/${officerId}/profile`, {
            method: "PUT",
            headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
            body: JSON.stringify({
                full_name: document.getElementById("editOfficerName").value.trim(),
                email: document.getElementById("editOfficerEmail").value.trim(),
                phone: document.getElementById("editOfficerPhone").value.trim() || null,
                state: document.getElementById("editOfficerState").value,
                district: document.getElementById("editOfficerDistrict").value,
                area: document.getElementById("editOfficerArea").value.trim() || null,
                specialization: document.getElementById("editOfficerSpecialization").value.trim() || "General",
                max_active_cases: Number(document.getElementById("editOfficerCapacity").value),
            }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) return alert(data.detail || "Unable to update officer profile");
        dialog.close();
        await loadOfficerPerformance();
        alert(data.message || "Officer profile updated.");
    } catch (error) {
        alert(error.message || "Network error while updating the officer profile.");
    } finally {
        saveButton.disabled = false;
    }
}

document.getElementById("officerProfileForm")?.addEventListener("submit", saveOfficerProfile);
document.getElementById("closeOfficerProfile")?.addEventListener("click", () => document.getElementById("officerProfileDialog")?.close());
document.getElementById("cancelOfficerProfile")?.addEventListener("click", () => document.getElementById("officerProfileDialog")?.close());

let escalationRows = [];
let escalationPage = 0;
const escalationPageSize = 10;
function renderEscalationPage() {
    const tbody = document.getElementById("escalationBody");
    if (!tbody) return;
    const totalPages = Math.max(1, Math.ceil(escalationRows.length / escalationPageSize));
    escalationPage = Math.min(escalationPage, totalPages - 1);
    document.getElementById("escalationCount").textContent = `${escalationRows.length} active SLA-risk case(s)`;
    document.getElementById("escalationPageInfo").textContent = `Page ${escalationPage+1} of ${totalPages}`;
    document.getElementById("escalationPrev").disabled = escalationPage === 0;
    document.getElementById("escalationNext").disabled = escalationPage >= totalPages-1;
    if (!escalationRows.length) {
        tbody.innerHTML = '<tr><td colspan="7">No active escalations. New SLA-risk cases appear here.</td></tr>';
        return;
    }
    const escapeHtml = (v) => String(v ?? "—").replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    tbody.innerHTML = escalationRows.slice(escalationPage*escalationPageSize,(escalationPage+1)*escalationPageSize).map(e => `
        <tr><td><span class="escalation-level level-${Number(e.level)||1}">L${Number(e.level)||1}</span></td>
        <td><strong>#${Number(e.complaint_id)}</strong><small class="escalation-title">${escapeHtml(e.title)}</small></td>
        <td>${escapeHtml(e.priority)}</td><td class="escalation-reason">${escapeHtml(e.reason)}</td>
        <td>${escapeHtml(e.source)}</td><td><span class="escalation-status">${escapeHtml(e.status)}</span></td>
        <td><div class="escalation-actions"><a class="mini-link-btn" href="department_complaint_details.html?id=${Number(e.complaint_id)}">Open</a>
        ${e.status === "Open" ? `<button type="button" class="mini-action-btn" onclick="acknowledgeEscalation(${Number(e.escalation_id)})">Acknowledge</button>` : ''}</div></td></tr>`).join('');
}
document.getElementById("escalationPrev")?.addEventListener("click",()=>{escalationPage--;renderEscalationPage();});
document.getElementById("escalationNext")?.addEventListener("click",()=>{escalationPage++;renderEscalationPage();});
async function loadEscalations() {
    const tbody = document.getElementById("escalationBody");
    if (!tbody || isOfficer) return;
    try {
        const response = await fetch(`${API_BASE}/department/escalations`, {headers: { Authorization: `Bearer ${token}` }});
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        escalationRows = (await response.json()).filter(x=>x.status !== 'Closed');
        renderEscalationPage();
    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="7">Unable to load the escalation queue. Refresh to retry.</td></tr>';
        console.warn("Escalation load error", err);
    }
}

async function acknowledgeEscalation(id) {
    const response = await fetch(`${API_BASE}/department/escalations/${id}/acknowledge`, {
        method: "PATCH",
        headers: { Authorization: `Bearer ${token}` }
    });
    const data = await response.json();
    if (!response.ok) return alert(data.detail || "Unable to acknowledge escalation");
    loadEscalations();
}
window.acknowledgeEscalation = acknowledgeEscalation;

async function createOfficer() {
    const nameInput = document.getElementById("officerName");
    const emailInput = document.getElementById("officerEmail");
    const passwordInput = document.getElementById("officerPassword");
    const capacityInput = document.getElementById("officerCapacity");
    const name = nameInput?.value.trim() || "";
    const email = emailInput?.value.trim() || "";
    const password = passwordInput?.value || "";
    const phone = document.getElementById("officerPhone")?.value.trim() || null;
    const state = document.getElementById("officerState")?.value.trim() || null;
    const district = document.getElementById("officerDistrict")?.value.trim() || null;
    const area = document.getElementById("officerArea")?.value.trim() || null;
    const specialization = document.getElementById("officerSpecialization")?.value.trim() || "General";
    const maxActiveCases = Number(capacityInput?.value || 20);

    // Enforce validation in JavaScript too: the button is type=button, so
    // native form validation alone would otherwise not run.
    if (!name) { nameInput?.setCustomValidity("Officer name is required."); nameInput?.reportValidity(); nameInput?.setCustomValidity(""); return; }
    if (!email) { emailInput?.setCustomValidity("Officer email is required."); emailInput?.reportValidity(); emailInput?.setCustomValidity(""); return; }
    if (!emailInput?.checkValidity()) { emailInput?.reportValidity(); return; }
    const stateInput = document.getElementById("officerState");
    const districtInput = document.getElementById("officerDistrict");
    if (!stateInput?.value) { stateInput?.setCustomValidity("Select the officer's state or UT."); stateInput?.reportValidity(); stateInput?.setCustomValidity(""); return; }
    if (!districtInput?.value) { districtInput?.setCustomValidity("Select the officer's posting district."); districtInput?.reportValidity(); districtInput?.setCustomValidity(""); return; }
    if (!password.trim() || password.length < 8) {
        passwordInput?.setCustomValidity("Enter a temporary password of at least 8 characters.");
        passwordInput?.reportValidity();
        passwordInput?.setCustomValidity("");
        return;
    }
    if (!Number.isInteger(maxActiveCases) || maxActiveCases < 1 || maxActiveCases > 200) {
        capacityInput?.setCustomValidity("Capacity must be a whole number between 1 and 200.");
        capacityInput?.reportValidity();
        capacityInput?.setCustomValidity("");
        return;
    }

    const button = document.getElementById("createOfficerBtn");
    if (button) button.disabled = true;
    try {
        const response = await fetch(`${API_BASE}/department/officers`, {
            method: "POST",
            headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
            body: JSON.stringify({
                full_name: name, email, password, phone, state, district, area,
                specialization, max_active_cases: maxActiveCases
            })
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            alert(data.detail || "Unable to create officer account");
            return;
        }
        ["officerName", "officerEmail", "officerPassword", "officerPhone", "officerState", "officerDistrict", "officerArea", "officerSpecialization"].forEach(id => {
            const input = document.getElementById(id); if (input) input.value = "";
        });
        if (capacityInput) capacityInput.value = "20";
        alert("Officer account created. They can now log in using the email and temporary password.");
        await loadOfficerPerformance();
    } catch (err) {
        alert(err.message || "Network error while creating the officer account.");
    } finally {
        if (button) button.disabled = false;
    }
}

async function setOfficerStatus(officerId, isActive) {
    const action = isActive ? "reactivate" : "deactivate";
    if (!confirm(`Are you sure you want to ${action} this officer?`)) return;
    const response = await fetch(`${API_BASE}/department/officers/${officerId}/status`, {
        method: "PATCH",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: isActive })
    });
    const data = await response.json();
    if (!response.ok) return alert(data.detail || "Unable to update officer status");
    loadOfficerPerformance();
}
window.setOfficerStatus = setOfficerStatus;

async function deleteOfficer(officerId) {
    const officer = (window.__civicflowOfficerRows || []).find(row => Number(row.user_id) === Number(officerId));
    const label = officer ? `${officer.name} (${officer.email})` : `officer #${officerId}`;
    if (!confirm(`Permanently delete ${label}? This cannot be undone. Active complaints must be reassigned first. Historical complaint events will remain, but assignment/performance records for this officer will be removed.`)) return;
    try {
        const response = await fetch(`${API_BASE}/department/officers/${officerId}`, {
            method: "DELETE",
            headers: { Authorization: `Bearer ${token}` }
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) return alert(data.detail || "Unable to delete officer");
        alert(data.message || "Officer deleted.");
        await loadOfficerPerformance();
    } catch (err) {
        alert(err.message || "Network error while deleting officer.");
    }
}
window.deleteOfficer = deleteOfficer;

const createOfficerBtn = document.getElementById("createOfficerBtn");
if (createOfficerBtn) createOfficerBtn.addEventListener("click", createOfficer);

if (localStorage.getItem("actual_role") === "officer") {
    const panel = document.getElementById("officerAccountabilityPanel");
    if (panel) panel.style.display = "none";
    const escalationPanel = document.getElementById("escalationPanel");
    if (escalationPanel) escalationPanel.style.display = "none";
    const locationGroupsPanel = document.getElementById("locationGroupsPanel");
    if (locationGroupsPanel) locationGroupsPanel.style.display = "none";
}

setupDepartmentNotificationMenu();
loadNotifications();
if (!isOfficer) {
    loadLocationGroups();
    loadOfficerPerformance();
    loadEscalations();
}
setInterval(loadNotifications, 60000);
if (!isOfficer) {
    setInterval(loadLocationGroups, 60000);
    setInterval(loadOfficerPerformance, 60000);
    setInterval(loadEscalations, 60000);
}

initStateDistrictDropdown("officerState", "officerDistrict");
const officerEditDropdownReady = initStateDistrictDropdown("editOfficerState", "editOfficerDistrict");




// Pip is initialized from department_guide.js on staff workspace pages.
