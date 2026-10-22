const token = localStorage.getItem("access_token");
const role = (localStorage.getItem("role") || "").toLowerCase();
if (!token || role !== "admin") window.location.href = "login.html";
const auth = { Authorization: `Bearer ${token}` };
let complaintsCache = [], citizensCache = [], officersCache = [], departmentsCache = [], headsCache = [], escalationsCache = [], hotspotsCache = [];
let hotspotMap = null, hotspotLayer = null;
let adminMapFilteredComplaints = [];

function esc(v){return String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}
function badge(text,kind=''){return `<span class="badge ${kind}">${esc(text||'-')}</span>`;}
function logout(){ localStorage.clear(); window.location.href="login.html"; }
async function get(path){const r=await fetch(`${API_BASE}${path}`,{headers:auth});if(r.status===401||r.status===403){logout();throw new Error('Admin session expired');}if(!r.ok)throw new Error(await r.text());return r.json();}
async function send(path,method,body){const r=await fetch(`${API_BASE}${path}`,{method,headers:{...auth,'Content-Type':'application/json'},body:JSON.stringify(body)});const d=await r.json().catch(()=>({}));if(!r.ok)throw new Error(d.detail||'Request failed');return d;}
function setText(id,val){const e=document.getElementById(id);if(e)e.textContent=val??0;}
function slaKind(v){return v==='Breached'?'danger':v==='At Risk'?'warning':v==='On Track'?'success':'';}
function barList(elId,items){const el=document.getElementById(elId);if(!el)return;const max=Math.max(1,...items.map(x=>x.count||0));el.innerHTML=items.length?items.map(x=>`<div class="bar-row"><span>${esc(x.label)}</span><div class="bar-track"><i style="width:${Math.round((x.count/max)*100)}%"></i></div><strong>${x.count}</strong></div>`).join(''):'<p>No data yet.</p>';}

function setupAdminNotificationMenu(){const btn=document.getElementById('adminNotificationBtn'),menu=document.getElementById('adminNotificationMenu');if(!btn||!menu)return;btn.addEventListener('click',e=>{e.stopPropagation();menu.classList.toggle('open');});document.addEventListener('click',e=>{if(!menu.contains(e.target)&&!btn.contains(e.target))menu.classList.remove('open');});}
function renderAdminNotifications(){const list=document.getElementById('adminNotificationList'),count=document.getElementById('adminNotificationCount');if(!list||!count)return;const rows=complaintsCache.filter(c=>c.sla_state==='Breached'||c.sla_state==='At Risk'||(c.status==='Assigned'&&!c.assignee));count.textContent=rows.length>99?'99+':rows.length;count.style.display=rows.length?'flex':'none';list.innerHTML=rows.length?rows.slice(0,12).map(c=>`<a class="notification-menu-item ${c.sla_state==='Breached'?'danger':'warning'}" href="#"><strong>${esc(c.sla_state||'Needs assignment')}: #${c.complaint_id} — ${esc(c.title)}</strong><small>${esc(c.department)} · ${esc(c.assignee||'No officer assigned')}</small></a>`).join(''):'<p class="notification-empty">No urgent system notifications.</p>';}

function switchTab(name){document.querySelectorAll('.tab-panel').forEach(p=>p.classList.remove('active'));document.querySelectorAll('.tab-btn').forEach(b=>b.classList.toggle('active',b.dataset.tab===name));document.getElementById(`tab-${name}`)?.classList.add('active');}
document.querySelectorAll('.tab-btn').forEach(b=>b.addEventListener('click',()=>{switchTab(b.dataset.tab);if(b.dataset.tab==='hotspots')setTimeout(()=>hotspotMap?.invalidateSize(),120);}));
document.querySelectorAll('[data-go]').forEach(b=>b.addEventListener('click',()=>switchTab(b.dataset.go)));
document.getElementById('logoutBtn').addEventListener('click',logout);document.getElementById('refreshBtn').addEventListener('click',loadAll);

async function loadOverview(){const [o,status,priority,dept]=await Promise.all([get('/admin/overview'),get('/admin/analytics/status'),get('/admin/analytics/priority'),get('/admin/analytics/department')]);setText('mComplaints',o.total_complaints);setText('mUsers',o.total_users);setText('mDepartments',o.total_departments);setText('mOfficers',o.total_officers);setText('mResolved',o.resolved);setText('mAtRisk',o.at_risk);setText('mBreached',o.sla_breached);setText('mUnassigned',o.unassigned);barList('statusBars',status);barList('priorityBars',priority);barList('departmentBars',dept);}
async function loadComplaints(){complaintsCache=await get('/admin/complaints');renderComplaints(complaintsCache);renderAttention();renderAdminNotifications();if(hotspotMap)renderHotspotMap();}
function renderComplaints(rows){const b=document.getElementById('allComplaintsBody');b.innerHTML=rows.length?rows.map(c=>`<tr><td>#${c.complaint_id}</td><td><strong>${esc(c.title)}</strong></td><td>${esc(c.district)}, ${esc(c.state)}</td><td>${esc(c.department)}</td><td>${badge(c.priority,['Critical','High'].includes(c.priority)?'danger':c.priority==='Medium'?'warning':'')}</td><td>${badge(c.display_status||c.status)}</td><td>${badge(c.sla_state,slaKind(c.sla_state))}</td><td>${esc(c.assignee||'Unassigned')}</td><td>${c.created_at?new Date(c.created_at).toLocaleDateString():'-'}</td><td><button class="delete-complaint-btn" onclick="deleteComplaint(${Number(c.complaint_id)})" aria-label="Delete complaint ${Number(c.complaint_id)}">Delete</button></td></tr>`).join(''):'<tr><td colspan="10">No complaints available.</td></tr>'; }
function renderAttention(){const rows=complaintsCache.filter(c=>c.sla_state==='Breached'||c.sla_state==='At Risk'||['High','Critical'].includes(c.priority)).slice(0,10);document.getElementById('attentionBody').innerHTML=rows.length?rows.map(c=>`<tr><td>#${c.complaint_id}</td><td>${esc(c.title)}</td><td>${esc(c.department)}</td><td>${badge(c.priority,['Critical','High'].includes(c.priority)?'danger':'warning')}</td><td>${badge(c.sla_state,slaKind(c.sla_state))}</td><td>${esc(c.assignee||'Unassigned')}</td></tr>`).join(''):'<tr><td colspan="6">No urgent system-level issues.</td></tr>';}


async function deleteComplaint(id){
  if(!confirm(`Delete complaint #${id}? This permanently removes the complaint and its attached media. A minimal admin audit record will remain.`))return;
  const reason=prompt('Enter the administrative reason for deletion (at least 8 characters):');
  if(reason===null)return;
  if(reason.trim().length<8){alert('Please provide a clear reason of at least 8 characters.');return;}
  try{await send(`/admin/complaints/${Number(id)}`,'DELETE',{reason:reason.trim()});await Promise.all([loadComplaints(),loadOverview(),loadDepartments()]);alert(`Complaint #${id} was deleted.`);}
  catch(error){alert(error.message||'Could not delete this complaint.');}
}

async function loadDepartments(){[departmentsCache,headsCache]=await Promise.all([get('/admin/departments'),get('/admin/department-heads')]);renderDepartments();renderHeads();fillOfficerDepartmentFilter();}
function renderDepartments(){document.getElementById('departmentsBody').innerHTML=departmentsCache.length?departmentsCache.map(d=>`<tr><td><strong>${esc(d.department_name)}</strong><br><small>${esc(d.state||'National / not set')}</small></td><td>${esc(d.department_code||'-')}</td><td>${esc(d.jurisdiction||'-')}</td><td>${badge(d.ai_supported?'Supported':'Not trained',d.ai_supported?'success':'warning')}</td><td>${d.total}</td><td>${d.in_progress}</td><td>${d.resolved}</td><td>${badge(d.sla_breached,d.sla_breached?'danger':'success')}</td><td>${d.active_officers}</td></tr>`).join(''):'<tr><td colspan="9">No departments found.</td></tr>';}
function renderHeads(){document.getElementById('departmentHeadsBody').innerHTML=headsCache.length?headsCache.map(h=>`<tr><td><strong>${esc(h.department)}</strong></td><td>${esc(h.name)}</td><td>${esc(h.email)}</td><td>${esc(h.username)}</td><td>${esc(h.state||'-')}</td><td>${badge(h.is_active?'Active':'Inactive',h.is_active?'success':'danger')}</td></tr>`).join(''):'<tr><td colspan="6">No Department Heads found.</td></tr>';}

document.querySelectorAll('[data-dept-view]').forEach(btn=>btn.addEventListener('click',()=>{document.querySelectorAll('[data-dept-view]').forEach(x=>x.classList.remove('active'));btn.classList.add('active');const heads=btn.dataset.deptView==='heads';document.getElementById('deptViewAll').classList.toggle('hidden',heads);document.getElementById('deptViewHeads').classList.toggle('hidden',!heads);}));
const addPanel=document.getElementById('addDepartmentPanel');document.getElementById('showAddDepartmentBtn').addEventListener('click',()=>addPanel.classList.remove('hidden'));document.getElementById('closeDepartmentForm').addEventListener('click',()=>addPanel.classList.add('hidden'));
document.getElementById('createDepartmentBtn').addEventListener('click',async()=>{const payload={department_name:document.getElementById('newDeptName').value.trim(),department_code:document.getElementById('newDeptCode').value.trim()||null,head_name:document.getElementById('newDeptHead').value.trim(),department_email:document.getElementById('newDeptEmail').value.trim(),username:document.getElementById('newDeptUsername').value.trim(),password:document.getElementById('newDeptPassword').value,state:document.getElementById('newDeptState').value.trim()||null,jurisdiction:document.getElementById('newDeptJurisdiction').value.trim()||null,description:document.getElementById('newDeptDescription').value.trim()||null};if(!payload.department_name||!payload.head_name||!payload.department_email||!payload.username||!payload.password)return alert('Fill department name, head name, email, username and temporary password.');try{const d=await send('/admin/departments','POST',payload);alert(`${d.message}. ${d.ai_note}`);['newDeptName','newDeptCode','newDeptHead','newDeptEmail','newDeptUsername','newDeptPassword','newDeptState','newDeptJurisdiction','newDeptDescription'].forEach(id=>document.getElementById(id).value='');addPanel.classList.add('hidden');await Promise.all([loadDepartments(),loadOverview()]);}catch(e){alert(e.message);}});

async function loadCitizens(){citizensCache=await get('/admin/citizens');fillCitizenStateFilter();filterCitizens();}
function fillCitizenStateFilter(){const sel=document.getElementById('citizenStateFilter'),current=sel.value,states=[...new Set(citizensCache.map(x=>x.state).filter(Boolean))].sort();sel.innerHTML='<option value="">All States</option>'+states.map(s=>`<option>${esc(s)}</option>`).join('');sel.value=current;document.getElementById('citizenSummary').innerHTML=`<span><b>${citizensCache.length}</b> total citizens</span>`+states.slice(0,8).map(s=>`<span>${esc(s)} <b>${citizensCache.filter(c=>c.state===s).length}</b></span>`).join('');}
function filterCitizens(){const q=document.getElementById('citizenSearch').value.toLowerCase(),st=document.getElementById('citizenStateFilter').value;const rows=citizensCache.filter(c=>(!st||c.state===st)&&(!q||JSON.stringify(c).toLowerCase().includes(q)));document.getElementById('citizensBody').innerHTML=rows.length?rows.map(c=>`<tr><td>${c.user_id}</td><td><strong>${esc(c.name)}</strong></td><td>${esc(c.email)}</td><td>${esc(c.phone||'-')}</td><td>${esc(c.state||'-')}</td><td>${esc(c.district||'-')}</td><td>${badge(c.is_active?'Active':'Inactive',c.is_active?'success':'danger')}</td></tr>`).join(''):'<tr><td colspan="7">No citizens match these filters.</td></tr>';}

async function loadOfficers(){officersCache=await get('/admin/officers');fillOfficerDepartmentFilter();filterOfficers();}
function fillOfficerDepartmentFilter(){const sel=document.getElementById('officerDepartmentFilter');if(!sel)return;const current=sel.value,names=[...new Set(officersCache.map(x=>x.department).filter(Boolean))].sort();sel.innerHTML='<option value="">All Departments</option>'+names.map(s=>`<option>${esc(s)}</option>`).join('');sel.value=current;document.getElementById('officerSummary').innerHTML=`<span><b>${officersCache.length}</b> total officers</span>`+names.slice(0,8).map(s=>`<span>${esc(s)} <b>${officersCache.filter(o=>o.department===s).length}</b></span>`).join('');}
function filterOfficers(){const q=document.getElementById('officerSearch').value.toLowerCase(),dept=document.getElementById('officerDepartmentFilter').value,status=document.getElementById('officerStatusFilter').value;const rows=officersCache.filter(o=>(!dept||o.department===dept)&&(!status||(status==='active'?o.is_active:!o.is_active))&&(!q||JSON.stringify(o).toLowerCase().includes(q)));document.getElementById('officersBody').innerHTML=rows.length?rows.map(o=>`<tr><td>${o.user_id}</td><td><strong>${esc(o.name)}</strong><br><small>${esc(o.email)}</small></td><td>${esc(o.department)}</td><td>${esc(o.district||'-')}, ${esc(o.state||'-')}</td><td>${esc(o.specialization||'General')}</td><td>${o.active_cases||0}/${o.max_active_cases}<br><small>${o.resolution_rate===undefined?'No history':`${Number(o.resolution_rate).toFixed(1)}% resolved · ${o.sla_compliance_rate==null?'—':Number(o.sla_compliance_rate).toFixed(1)+'% SLA'}`}</small></td><td>${badge(o.is_active?'Active':'Inactive',o.is_active?'success':'danger')}<br><small>${o.performance_index==null?'Performance: no history':`Performance: ${Number(o.performance_index).toFixed(1)}`}</small></td></tr>`).join(''):'<tr><td colspan="7">No officers match these filters.</td></tr>';}

document.getElementById('complaintSearch').addEventListener('input',e=>{const q=e.target.value.toLowerCase();renderComplaints(complaintsCache.filter(c=>JSON.stringify(c).toLowerCase().includes(q)));});
document.getElementById('citizenSearch').addEventListener('input',filterCitizens);document.getElementById('citizenStateFilter').addEventListener('change',filterCitizens);document.getElementById('officerSearch').addEventListener('input',filterOfficers);document.getElementById('officerDepartmentFilter').addEventListener('change',filterOfficers);document.getElementById('officerStatusFilter').addEventListener('change',filterOfficers);


async function loadEscalations(){
  escalationsCache = await get('/admin/escalations');
  const body = document.getElementById('adminEscalationBody');
  if(!body) return;
  const active = escalationsCache.filter(e=>e.status!=='Closed');
  body.innerHTML = active.length ? active.map(e=>`
    <tr>
      <td><span class="level-pill level-${e.level}">L${e.level}</span></td>
      <td><strong>#${e.complaint_id}</strong><br><small>${esc(e.title)}</small></td>
      <td>${esc(e.department)}</td>
      <td>${esc(e.district||'-')}, ${esc(e.state||'-')}</td>
      <td>${badge(e.priority,['Critical','High'].includes(e.priority)?'danger':e.priority==='Medium'?'warning':'')}</td>
      <td>${esc(e.reason)}</td>
      <td>${esc(e.source)}</td>
      <td>${badge(e.status,e.status==='Open'?'warning':'')}</td>
      <td><button class="link-btn close-escalation-btn" onclick="closeEscalation(${e.escalation_id})">Close</button></td>
    </tr>`).join('') : '<tr><td colspan="9">No active escalations. SLA risk cases will appear automatically.</td></tr>';
}

async function closeEscalation(id){
  if(!confirm('Close this escalation record?')) return;
  try{
    await send(`/admin/escalations/${id}/close`,'PATCH',{});
    await loadEscalations();
  }catch(e){ alert(e.message); }
}
window.closeEscalation = closeEscalation;

function hotspotKind(level){
  return level==='High'?'danger':level==='Medium'?'warning':'success';
}

async function loadHotspots(){
  const [hotspots, surgeAlerts] = await Promise.all([get('/admin/analytics/hotspots'), get('/admin/analytics/surge-alerts')]);
  hotspotsCache = hotspots;
  renderSurgeAlerts(surgeAlerts);
  const body = document.getElementById('hotspotBody');
  const summary = document.getElementById('hotspotSummary');

  if(summary){
    const total = hotspotsCache.reduce((s,x)=>s+(x.complaint_count||0),0);
    const active = hotspotsCache.reduce((s,x)=>s+(x.active_count||0),0);
    const high = hotspotsCache.filter(x=>x.hotspot_level==='High').length;
    summary.innerHTML = `
      <article><span>Mapped Complaints</span><strong>${total}</strong></article>
      <article><span>Active in Hotspots</span><strong>${active}</strong></article>
      <article><span>High Hotspots</span><strong>${high}</strong></article>
      <article><span>Mapped Cells</span><strong>${hotspotsCache.length}</strong></article>`;
  }

  if(body){
    // The API returns geographic cells for mapping. The summary table is
    // intentionally aggregated by reported district/state so a district with
    // several separate coordinate cells does not appear as duplicate rows.
    const districtGroups = new Map();
    hotspotsCache.forEach(h=>{
      const district=(h.district||'').trim()||'Location not specified';
      const state=(h.state||'').trim()||'State not specified';
      const key=`${state.toLocaleLowerCase()}|${district.toLocaleLowerCase()}`;
      const g=districtGroups.get(key)||{district,state,complaint_count:0,active_count:0,high_critical_count:0,incident_ids:0,cell_count:0};
      g.complaint_count+=Number(h.complaint_count)||0;
      g.active_count+=Number(h.active_count)||0;
      g.high_critical_count+=Number(h.high_critical_count)||0;
      g.incident_ids+=Number(h.incident_count)||0;
      g.cell_count+=1;
      districtGroups.set(key,g);
    });
    const districtRows=[...districtGroups.values()].map(g=>{
      const ratio=g.high_critical_count/Math.max(1,g.complaint_count);
      const level=(g.complaint_count>=5||(g.high_critical_count>=2&&ratio>=0.5))?'High':(g.complaint_count>=3||g.high_critical_count>=1)?'Medium':'Low';
      return {...g,hotspot_level:level};
    }).sort((a,b)=>b.complaint_count-a.complaint_count);
    body.innerHTML = districtRows.length ? districtRows.slice(0,50).map(h=>`
      <tr>
        <td><strong>${esc(h.district)}</strong><br><small>${esc(h.state)} · ${h.cell_count} mapped cell(s)</small></td>
        <td>${h.complaint_count}</td>
        <td>${h.active_count}</td>
        <td>${h.high_critical_count}</td>
        <td>${h.incident_ids}</td>
        <td>${badge(h.hotspot_level,hotspotKind(h.hotspot_level))}</td>
      </tr>`).join('') : '<tr><td colspan="6">No complaint coordinates are available yet.</td></tr>';
  }

  renderHotspotMap();
}


function renderSurgeAlerts(alerts){
  const summary=document.getElementById('surgeAlertSummary');
  const list=document.getElementById('surgeAlertList');
  if(!summary||!list)return;
  const rows=Array.isArray(alerts)?alerts:[];
  summary.textContent=rows.length ? `${rows.length} incident cluster(s) crossed the early-warning threshold in the last 24 hours.` : 'No incident clusters currently meet the early-warning threshold. This does not mean no local problems exist.';
  list.innerHTML=rows.length?rows.map(a=>`<article class="surge-alert-card ${a.highest_priority==='Critical'?'surge-critical':''}">
    <div class="surge-alert-top"><strong>${esc(a.department||'Department not assigned')} · ${esc(a.district||'Location not specified')}</strong>${badge(a.highest_priority||'Priority unknown',a.highest_priority==='Critical'?'danger':a.highest_priority==='High'?'warning':'')}</div>
    <p>${esc(a.title||'Related civic incident')}</p>
    <div class="surge-alert-metrics"><span><b>${a.reports_last_24h}</b> reports in 24h</span><span><b>${a.distinct_reporters_last_24h}</b> different citizens</span><span><b>${a.total_reports}</b> linked reports total</span><span><b>${a.unresolved_reports}</b> unresolved</span></div>
    <p class="surge-alert-reason">${esc(a.alert_reason)}</p>
    <small>Cluster #${a.incident_cluster_id} · Most recent report: ${a.latest_report_at?new Date(a.latest_report_at).toLocaleString():'time unavailable'}</small>
  </article>`).join(''):'<p>No emerging incidents detected from current complaint records.</p>';
}

function validComplaintPoint(c){
  const lat=Number(c.latitude), lon=Number(c.longitude);
  return c.latitude!==null && c.latitude!=='' && c.longitude!==null && c.longitude!=='' && Number.isFinite(lat) && Number.isFinite(lon) && lat!==0 && lon!==0 && lat>=-90 && lat<=90 && lon>=-180 && lon<=180;
}
function renderMapAnalysis(containerId, rows, totalLocated, scopeLabel){
  const el=document.getElementById(containerId);if(!el)return;
  const unresolved=rows.filter(c=>(c.status||'').toLowerCase()!=='resolved');
  const critical=rows.filter(c=>(c.priority||'').toLowerCase()==='critical').length;
  const high=rows.filter(c=>(c.priority||'').toLowerCase()==='high').length;
  const resolved=rows.length-unresolved.length;
  const groups=(key)=>{const counts=new Map();rows.forEach(c=>{const value=(c[key]||'').trim()||'Not provided';counts.set(value,(counts.get(value)||0)+1)});return [...counts.entries()].sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0]));};
  const topAreas=groups('area').slice(0,3).map(([name,count])=>`${esc(name)} (${count})`).join(', ')||'No area data';
  const topDistricts=groups('district').slice(0,3).map(([name,count])=>`${esc(name)} (${count})`).join(', ')||'No district data';
  const departmentCounts=new Map();rows.forEach(c=>{const name=(c.department||'Unassigned').trim();departmentCounts.set(name,(departmentCounts.get(name)||0)+1)});
  const topDepartments=[...departmentCounts.entries()].sort((a,b)=>b[1]-a[1]).slice(0,3).map(([name,count])=>`${esc(name)} (${count})`).join(', ')||'No department data';
  const coverage=totalLocated?Math.round(rows.length/totalLocated*100):0;
  el.innerHTML=`<h3>Filtered map analysis <small>· ${esc(scopeLabel)}</small></h3>
    <div class="map-analysis-grid">
      <div class="map-analysis-stat"><span>Complaints in view</span><strong>${rows.length}</strong></div>
      <div class="map-analysis-stat"><span>Critical</span><strong>${critical}</strong></div>
      <div class="map-analysis-stat"><span>High</span><strong>${high}</strong></div>
      <div class="map-analysis-stat"><span>Unresolved</span><strong>${unresolved.length}</strong></div>
      <div class="map-analysis-stat"><span>Resolved</span><strong>${resolved} (${rows.length?Math.round(resolved/rows.length*100):0}%)</strong></div>
      <div class="map-analysis-stat"><span>Filter coverage</span><strong>${coverage}%</strong></div>
    </div><div class="map-analysis-notes">
      <p><b>Most reported areas:</b> ${topAreas}</p><p><b>Districts represented:</b> ${topDistricts}</p>
      <p><b>Departments represented:</b> ${topDepartments}</p>
      <p><b>Interpretation:</b> Counts include only complaints with valid stored coordinates. Similar locations indicate a reporting concentration, not proof of a single incident.</p>
    </div>`;
}
function fillAdminMapFilters(){
  const stateSel=document.getElementById('adminMapStateFilter'), districtSel=document.getElementById('adminMapDistrictFilter');
  if(!stateSel||!districtSel)return;
  const oldState=stateSel.value, oldDistrict=districtSel.value;
  const states=[...new Set(complaintsCache.map(c=>(c.state||'').trim()).filter(Boolean))].sort((a,b)=>a.localeCompare(b));
  stateSel.innerHTML='<option value="">All States / UTs</option>'+states.map(st=>`<option value="${esc(st)}">${esc(st)}</option>`).join('');
  stateSel.value=states.includes(oldState)?oldState:'';
  const stateRows=complaintsCache.filter(c=>!stateSel.value||(c.state||'').trim()===stateSel.value);
  const districts=[...new Set(stateRows.map(c=>(c.district||'').trim()).filter(Boolean))].sort((a,b)=>a.localeCompare(b));
  districtSel.innerHTML='<option value="">All Districts</option>'+districts.map(d=>`<option value="${esc(d)}">${esc(d)}</option>`).join('');
  districtSel.value=districts.includes(oldDistrict)?oldDistrict:'';
}
let adminLeafletPromise=null;
function loadAdminLeaflet(){
  if(typeof L!=='undefined')return Promise.resolve();
  if(adminLeafletPromise)return adminLeafletPromise;
  adminLeafletPromise=new Promise((resolve,reject)=>{
    const css=document.createElement('link');css.rel='stylesheet';css.href='https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';document.head.appendChild(css);
    const script=document.createElement('script');script.src='https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';script.onload=resolve;script.onerror=()=>reject(new Error('Leaflet unavailable'));document.body.appendChild(script);
  }).catch(error=>{adminLeafletPromise=null;throw error;});
  return adminLeafletPromise;
}
function renderHotspotMap(){
  const el=document.getElementById('adminHotspotMap'); if(!el)return;
  if(typeof L==='undefined'){
    loadAdminLeaflet().then(renderHotspotMap).catch(error=>console.warn('Admin map unavailable',error));
    return;
  }
  if(!hotspotMap){
    hotspotMap=L.map('adminHotspotMap',{zoomControl:false,scrollWheelZoom:true}).setView([20.2,84.5],6);
    const streets=L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OpenStreetMap contributors',maxZoom:19});
    const humanitarian=L.tileLayer('https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png',{attribution:'© OpenStreetMap contributors, Tiles style by Humanitarian OpenStreetMap Team',maxZoom:19});
    streets.addTo(hotspotMap); L.control.zoom({position:'topright'}).addTo(hotspotMap); L.control.scale({imperial:false,position:'bottomleft'}).addTo(hotspotMap);
    L.control.layers({'Street map':streets,'Humanitarian':humanitarian},{},{position:'topright',collapsed:true}).addTo(hotspotMap); hotspotLayer=L.layerGroup().addTo(hotspotMap);
    document.getElementById('adminMapStateFilter')?.addEventListener('change',()=>{fillAdminMapFilters();renderHotspotMap();});
    document.getElementById('adminMapDistrictFilter')?.addEventListener('change',()=>{fillAdminMapFilters();renderHotspotMap();});
  }
  fillAdminMapFilters(); hotspotLayer.clearLayers();
  const state=document.getElementById('adminMapStateFilter')?.value||'', district=document.getElementById('adminMapDistrictFilter')?.value||'';
  const rows=complaintsCache.filter(c=>validComplaintPoint(c)&&(!state||(c.state||'').trim()===state)&&(!district||(c.district||'').trim()===district));
  const locatedCount=complaintsCache.filter(validComplaintPoint).length;
  const scopeLabel=[district,state].filter(Boolean).join(', ')||'All locations';
  renderMapAnalysis('adminMapAnalysis',rows,locatedCount,scopeLabel);
  const bounds=[]; const duplicates=new Map();
  rows.forEach((c,index)=>{
    const lat=Number(c.latitude),lon=Number(c.longitude),key=`${lat.toFixed(6)}:${lon.toFixed(6)}`;
    const stack=duplicates.get(key)||0; duplicates.set(key,stack+1);
    // Tiny deterministic visual separation keeps same-coordinate reports individually clickable.
    const angle=(stack*137.508)*Math.PI/180, offset=stack===0?0:0.00010*Math.ceil(stack/6);
    const point=[lat+Math.sin(angle)*offset,lon+Math.cos(angle)*offset];
    const p=String(c.priority||'').toLowerCase(); const color=p==='critical'?'#991b1b':p==='high'?'#dc2626':p==='medium'?'#ea8a0a':'#2563eb';
    L.circleMarker(point,{radius:6,color:'#fff',weight:1.5,fillColor:color,fillOpacity:.9}).addTo(hotspotLayer).bindPopup(`<strong>Complaint #${Number(c.complaint_id)||''}</strong><br>${esc(c.title||'Complaint')}<br><strong>Priority:</strong> ${esc(c.priority||'Unknown')}<br><strong>Status:</strong> ${esc(c.display_status||c.status||'Unknown')}<br><strong>Department:</strong> ${esc(c.department||'Unassigned')}<br><strong>Area / Block:</strong> ${esc(c.area||'Not provided')}<br><strong>Address:</strong> ${esc(c.address||'Not provided')}<br><strong>Location:</strong> ${esc(c.district||'District not specified')}, ${esc(c.state||'State not specified')}<br><small>Marker may be slightly offset when multiple reports share identical coordinates. Saved coordinates reflect the submission's stored location; district-centroid coordinates are not exact address points.</small>`);
    bounds.push(point);
  });
  const count=document.getElementById('adminMapResultCount'); if(count)count.textContent=`Showing ${rows.length} of ${locatedCount} geolocated complaints`;
  if(bounds.length===1)hotspotMap.setView(bounds[0],15); else if(bounds.length>1)hotspotMap.fitBounds(L.latLngBounds(bounds).pad(0.18),{maxZoom:15}); else hotspotMap.setView(state?[20.2,84.5]:[22.8,79],state?7:5);
  setTimeout(()=>hotspotMap.invalidateSize(),100);
}
async function loadAll(){try{await Promise.all([loadOverview(),loadComplaints(),loadDepartments(),loadCitizens(),loadOfficers()]);
await Promise.all([loadEscalations(),loadHotspots()]);}catch(e){console.error(e);}}
setupAdminNotificationMenu();loadAll();setInterval(()=>{loadOverview();loadComplaints();loadDepartments();},60000);

initStateDistrictDropdown("newDeptState", null);


async function downloadAdminReport(format){
  const button = document.getElementById(format==='csv'?'downloadCsvBtn':'downloadPdfBtn');
  const original = button?.innerHTML;
  if(button){ button.disabled=true; button.innerHTML=`<i class="fa-solid fa-spinner fa-spin"></i> Preparing ${format.toUpperCase()}...`; }
  try{
    const response = await fetch(`${API_BASE}/admin/reports/complaints.${format}`,{headers:auth});
    if(!response.ok) throw new Error('Unable to generate report');
    const blob = await response.blob();
    const disposition = response.headers.get('Content-Disposition') || '';
    const match = disposition.match(/filename="?([^"]+)"?/i);
    const filename = match?.[1] || `civicflow_report.${format}`;
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href=url; a.download=filename; document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
  }catch(e){ alert(e.message); }
  finally{ if(button){button.disabled=false;button.innerHTML=original;} }
}

async function loadBhashiniStatus(){
  const chip=document.getElementById('bhashiniStatusChip');
  const details=document.getElementById('bhashiniStatusDetails');
  if(!chip||!details)return;
  try{
    const data=await get('/admin/integrations/bhashini');
    const anyConfigured=Boolean(data.google?.configured||data.bhashini?.configured);chip.textContent=anyConfigured?'Translation provider ready':'Translation fallback active';
    chip.className=`integration-chip ${anyConfigured?'ready':'pending'}`;
    details.innerHTML=`
      <div><span>Primary</span><strong>${data.google?.provider || 'Google Translate Web (Free)'}</strong></div>
      <div><span>Google Access</span><strong>${data.google?.api_key_configured ? 'Cloud API key configured' : 'Free web fallback (no key)'}</strong></div>
      <div><span>Indian-language fallback</span><strong>BHASHINI NMT</strong></div>
      <div><span>BHASHINI</span><strong>${data.bhashini?.configured?'Configured':'Awaiting approval'}</strong></div>
      <div><span>Target</span><strong>English</strong></div>
      <div><span>Google Cache</span><strong>${data.google?.cache_entries || 0} entries</strong></div>`;
  }catch(e){
    chip.textContent='Status unavailable';
    chip.className='integration-chip pending';
  }
}


document.getElementById('refreshSurgeAlerts')?.addEventListener('click',()=>loadHotspots().catch(e=>{const list=document.getElementById('surgeAlertList');if(list)list.textContent=e.message||'Could not refresh incident alerts.';}));
document.getElementById('downloadCsvBtn')?.addEventListener('click',()=>downloadAdminReport('csv'));
document.getElementById('downloadPdfBtn')?.addEventListener('click',()=>downloadAdminReport('pdf'));
loadBhashiniStatus();


