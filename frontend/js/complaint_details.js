function escHtml(v){return String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}
const token = localStorage.getItem("access_token");

const params = new URLSearchParams(window.location.search);

const complaintId = params.get("id");

async function loadComplaint(){

const response = await fetch(

`${API_BASE}/complaints/${complaintId}`,

{

headers:{

Authorization:`Bearer ${token}`

}

}

);

const data = await response.json();

const translationFeedbackPanel = document.getElementById("translationFeedbackPanel");
const translationFeedbackHistory = document.getElementById("translationFeedbackHistory");
const complaintIsEnglish = String(data.language || "").toLowerCase() === "english";
if (translationFeedbackPanel) translationFeedbackPanel.style.display = complaintIsEnglish ? "none" : "block";
if (translationFeedbackHistory) {
  const items = Array.isArray(data.translation_feedback) ? data.translation_feedback : [];
  translationFeedbackHistory.innerHTML = items.map(item => `<div class="translation-feedback-history-item"><strong>${escHtml(item.status)} feedback</strong><p>${escHtml(item.note)}</p>${item.suggested_english ? `<p><b>Suggested wording:</b> ${escHtml(item.suggested_english)}</p>` : ""}${item.review_note ? `<p><b>Department reply:</b> ${escHtml(item.review_note)}</p>` : ""}</div>`).join("");
}

document.getElementById("complaintId").textContent=data.complaint_id;

document.getElementById("title").textContent=data.title;

document.getElementById("description").textContent=data.description;

document.getElementById("department").textContent=data.department;

document.getElementById("priority").textContent=data.priority;

document.getElementById("status").textContent=data.display_status || data.status;

document.getElementById("summary").textContent=data.summary;


const incidentBox = document.getElementById("incidentSummary");
const incidentText = document.getElementById("incidentSummaryText");
if (incidentBox && data.incident_report_count > 1) {
  incidentBox.style.display = "block";
  const impact = data.incident_impact?.level ? ` Community impact: ${data.incident_impact.level}.` : "";
  incidentText.textContent = `${data.incident_report_count} related reports are grouped into the same incident. ${data.incident_affected_count} citizens are currently counted as affected.${impact} Your report remains independently trackable.`;
  const viewIncidentBtn = document.getElementById("viewIncidentBtn");
  if (viewIncidentBtn) {
    viewIncidentBtn.onclick = () => {
      window.location.href = `incident_details.html?id=${encodeURIComponent(data.incident_cluster_id)}`;
    };
  }
} else if (incidentBox) {
  incidentBox.style.display = "none";
}

const officerName = data.assigned_officer?.name || null;
document.getElementById("assignedOfficer").textContent = officerName || "Awaiting individual officer assignment";
document.getElementById("liveDepartment").textContent = data.department || "—";

const liveBadge = document.getElementById("liveStatusBadge");
liveBadge.textContent = data.display_status || data.status || "Received";
liveBadge.dataset.status = String(data.status || "").toLowerCase().replace(/\s+/g, "-");

function formatLiveDate(value){
  if(!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? String(value) : d.toLocaleString();
}

let latestLabel = "Complaint submitted";
let latestTime = data.created_at;
let nextStep = "The complaint will be routed to the responsible department.";

if (data.assigned_at) {
  latestLabel = "Received by department";
  latestTime = data.assigned_at;
  nextStep = "The department will assign an individual officer.";
}
if (data.officer_assigned_at) {
  latestLabel = officerName ? `Assigned to ${officerName}` : "Individual officer assigned";
  latestTime = data.officer_assigned_at;
  nextStep = "The assigned officer will review the case and start action.";
}
if (data.in_progress_at || data.status === "In Progress") {
  latestLabel = officerName ? `${officerName} is working on the complaint` : "Complaint work is in progress";
  latestTime = data.in_progress_at || data.officer_assigned_at || data.assigned_at;
  nextStep = "The officer will update the case as work progresses.";
}
if (data.resolved_at || data.status === "Resolved") {
  latestLabel = "Department marked the complaint resolved";
  latestTime = data.resolved_at || latestTime;
  nextStep = data.citizen_resolution_status === "Confirmed"
    ? "You confirmed the resolution. No further action is required."
    : "Review the resolution proof and confirm whether the issue is actually fixed.";
}

const liveDate = formatLiveDate(latestTime);
document.getElementById("latestUpdate").textContent = `${latestLabel}${liveDate ? ` · ${liveDate}` : ""}`;
document.getElementById("nextStep").textContent = nextStep;

const verify = document.getElementById("resolutionVerification");
const proofBox = document.getElementById("resolutionProofBox");
const verifyStatus = document.getElementById("resolutionVerificationStatus");
if (data.resolution_proof_path) {
  proofBox.innerHTML = `<p><strong>Officer resolution note:</strong> ${escHtml(data.resolution_note || "-")}</p><img src="${API_BASE}/${data.resolution_proof_url}" alt="Resolution proof" style="max-width:100%;max-height:320px;border-radius:12px;">`;
} else { proofBox.innerHTML = '<p>No resolution proof uploaded yet.</p>'; }
if (data.citizen_resolution_status) verifyStatus.textContent = `Citizen verification: ${data.citizen_resolution_status}`;
const disputeUsed = Number(data.resolution_disputes_used || 0);
const reopenBtn = document.getElementById("reopenComplaintBtn");
if (reopenBtn) {
  reopenBtn.disabled = disputeUsed >= 3;
  reopenBtn.title = disputeUsed >= 3 ? "Maximum three reopen requests used. Contact an administrator for review." : `${3 - disputeUsed} reopen requests remaining`;
  reopenBtn.textContent = disputeUsed >= 3 ? "Dispute limit reached — request independent review" : `Not satisfied (${3 - disputeUsed} remaining)`;
}
verify.style.display = data.status === "Resolved" ? "block" : "none";

const satisfactionSection = document.getElementById("satisfactionSection");
if (satisfactionSection) {
  satisfactionSection.style.display =
    (data.status === "Resolved" && data.citizen_resolution_status === "Confirmed")
      ? "block" : "none";
  if (satisfactionSection.style.display === "block") loadComplaintSatisfaction();
}

}

document.getElementById("trackBtn").onclick=function(){

window.location.href=`track.html?id=${complaintId}`;

}

loadComplaint();
async function sendResolutionConfirmation(confirmed){
  const note=document.getElementById("citizenResolutionNote").value.trim();
  const response=await fetch(`${API_BASE}/complaints/${complaintId}/resolution-confirmation`,{
    method:"POST", headers:{Authorization:`Bearer ${token}`,"Content-Type":"application/json"},
    body:JSON.stringify({confirmed,note:note||null})
  });
  const data=await response.json();
  alert(data.message||data.detail);
  if(response.ok) loadComplaint();
}
document.getElementById("confirmResolvedBtn").onclick=()=>sendResolutionConfirmation(true);
document.getElementById("reopenComplaintBtn").onclick=()=>sendResolutionConfirmation(false);

const translationFeedbackForm = document.getElementById("translationFeedbackForm");
if (translationFeedbackForm) translationFeedbackForm.addEventListener("submit", async event => {
  event.preventDefault();
  const status = document.getElementById("translationFeedbackStatus");
  const note = document.getElementById("translationFeedbackNote").value.trim();
  const suggestedEnglish = document.getElementById("suggestedEnglish").value.trim();
  if (note.length < 8) { status.textContent = "Please describe the translation issue in at least 8 characters."; return; }
  const button = document.getElementById("sendTranslationFeedback");
  button.disabled = true;
  status.textContent = "Sending feedback...";
  try {
    const response = await fetch(`${API_BASE}/complaints/${complaintId}/translation-feedback`, {
      method: "POST", headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ note, suggested_english: suggestedEnglish || null })
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.detail || "Could not send translation feedback.");
    status.textContent = result.message || "Feedback sent to the department.";
    document.getElementById("translationFeedbackNote").value = "";
    document.getElementById("suggestedEnglish").value = "";
    await loadComplaint();
  } catch (error) {
    status.textContent = error.message || "Could not send translation feedback.";
  } finally {
    button.disabled = false;
  }
});


let selectedSatisfactionRating = 0;

document.querySelectorAll("#satisfactionStars button").forEach(btn => {
  btn.addEventListener("click", () => {
    selectedSatisfactionRating = Number(btn.dataset.rating);
    document.querySelectorAll("#satisfactionStars button").forEach(star => {
      star.classList.toggle("active", Number(star.dataset.rating) <= selectedSatisfactionRating);
    });
    document.getElementById("satisfactionRatingText").textContent =
      `${selectedSatisfactionRating} / 5 stars`;
  });
});

async function loadComplaintSatisfaction(){
  try{
    const response = await fetch(`${API_BASE}/feedback/complaint/${complaintId}`,{
      headers:{Authorization:`Bearer ${token}`}
    });
    if(!response.ok) return;
    const data = await response.json();
    if(!data.submitted) return;

    selectedSatisfactionRating = Number(data.rating || 0);
    document.querySelectorAll("#satisfactionStars button").forEach(star => {
      star.classList.toggle("active", Number(star.dataset.rating) <= selectedSatisfactionRating);
    });
    document.getElementById("satisfactionRatingText").textContent =
      `${selectedSatisfactionRating} / 5 stars · already submitted`;
    document.getElementById("satisfactionComment").value = data.message || "";
    document.getElementById("satisfactionStatus").textContent =
      "You can update this rating if your opinion changes.";
  }catch(error){
    console.debug("Satisfaction lookup skipped", error);
  }
}

document.getElementById("submitSatisfactionBtn").onclick = async function(){
  const status = document.getElementById("satisfactionStatus");
  if(!selectedSatisfactionRating){
    status.textContent = "Please select a star rating.";
    return;
  }
  const comment = document.getElementById("satisfactionComment").value.trim();
  try{
    const response = await fetch(`${API_BASE}/feedback/`,{
      method:"POST",
      headers:{
        Authorization:`Bearer ${token}`,
        "Content-Type":"application/json"
      },
      body:JSON.stringify({
        complaint_id:Number(complaintId),
        rating:selectedSatisfactionRating,
        message:comment || "Resolution satisfaction rating"
      })
    });
    const data = await response.json();
    status.textContent = data.message || data.detail || "Rating saved.";
  }catch(error){
    status.textContent = "Could not save the rating right now.";
  }
};


