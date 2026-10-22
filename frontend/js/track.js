const token = localStorage.getItem("access_token");
const complaintId = new URLSearchParams(window.location.search).get("id");

function esc(value){ return String(value ?? "").replace(/[&<>"']/g,ch=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[ch])); }
function fmt(value){ if(!value) return "Pending"; const d=new Date(value); return Number.isNaN(d.getTime())?esc(value):d.toLocaleString(); }
function cls(done,current){ return done?"completed":current?"active":"pending"; }
function tag(done,current){ return done?'<span class="completed-label">Completed</span>':current?'<span class="active-label">Current</span>':'<span class="pending-label">Pending</span>'; }

async function loadComplaint(){
  try{
    const response=await fetch(`${API_BASE}/complaints/${complaintId}`,{headers:{Authorization:`Bearer ${token}`}});
    if(!response.ok) throw new Error("Unable to load complaint");
    const c=await response.json();

    const officer=c.assigned_officer?.name||null;
    const deptDone=Boolean(c.assigned_at);
    const officerDone=Boolean(c.officer_assigned_at||officer);
    const progressDone=Boolean(c.in_progress_at||c.status==="In Progress"||c.status==="Resolved");
    const resolvedDone=Boolean(c.resolved_at||c.status==="Resolved");
    const current=resolvedDone?5:progressDone?4:officerDone?3:deptDone?2:1;

    document.getElementById("trackBox").innerHTML=`
      <div class="complaint-top">
        <div><span class="complaint-label">CIVICFLOW AI • COMPLAINT JOURNEY</span><h1>${esc(c.title)}</h1><p class="complaint-id">Complaint ID #${esc(c.complaint_id)}</p></div>
        <div class="status-badge ${String(c.status||"").toLowerCase().replace(/\s+/g,"-")}"><span class="status-dot"></span>${esc(c.display_status||c.status)}</div>
      </div>

      <div class="info-grid">
        <div class="info-card"><div><span>Department</span><strong>${esc(c.department)}</strong></div></div>
        <div class="info-card"><div><span>Priority</span><strong>${esc(c.priority)}</strong></div></div>
        <div class="info-card"><div><span>Assigned Officer</span><strong>${esc(officer||"Awaiting officer")}</strong></div></div>
        <div class="info-card"><div><span>Current Status</span><strong>${esc(c.display_status||c.status)}</strong></div></div>
      </div>

      <div class="tracking-section">
        <div class="tracking-heading"><div><span class="section-eyebrow">COMPLETE LIFECYCLE</span><h2>Track Your Complaint</h2><p>Department receipt and individual officer assignment are shown as separate stages.</p></div></div>
        <div class="timeline">
          <div class="timeline-item completed"><div class="timeline-marker">✓</div><div class="timeline-content"><div class="timeline-title">Submitted ${tag(true,false)}</div><p>Your complaint was successfully registered.</p><time>${fmt(c.created_at)}</time></div></div>

          <div class="timeline-item ${cls(deptDone,current===2)}"><div class="timeline-marker">⌂</div><div class="timeline-content"><div class="timeline-title">Received by Department ${tag(deptDone,current===2)}</div><p>${deptDone?`Routed to ${esc(c.department)}.`:"Routing to the responsible department."}</p><time>${deptDone?fmt(c.assigned_at):"Pending"}</time></div></div>

          <div class="timeline-item ${cls(officerDone,current===3)}"><div class="timeline-marker">👤</div><div class="timeline-content"><div class="timeline-title">Individual Officer Assigned ${tag(officerDone,current===3)}</div><p>${officerDone?`Assigned to ${esc(officer||"an individual officer")}.`:"Waiting for the department to assign an officer."}</p><time>${officerDone?fmt(c.officer_assigned_at):"Awaiting officer assignment"}</time></div></div>

          <div class="timeline-item ${cls(progressDone,current===4)}"><div class="timeline-marker">⚒</div><div class="timeline-content"><div class="timeline-title">In Progress ${tag(progressDone,current===4)}</div><p>${progressDone?`${esc(officer||"The responsible officer")} has started working on the complaint.`:"Work has not started yet."}</p><time>${progressDone?fmt(c.in_progress_at):"Pending"}</time></div></div>

          <div class="timeline-item ${cls(resolvedDone,current===5)}"><div class="timeline-marker">✓</div><div class="timeline-content"><div class="timeline-title">Resolved ${tag(resolvedDone,current===5)}</div><p>${resolvedDone?`The department marked the complaint resolved.${c.citizen_resolution_status==="Confirmed"?" You confirmed the resolution.":" Citizen confirmation may still be pending."}`:"This stage will complete after the issue is resolved."}</p><time>${resolvedDone?fmt(c.resolved_at):"Pending"}</time></div></div>
        </div>
      </div>`;
  }catch(error){
    console.error(error);
    document.getElementById("trackBox").innerHTML='<div class="error-box"><h3>Unable to Load Complaint</h3><p>Please try again.</p></div>';
  }
}
loadComplaint();
