const token = localStorage.getItem("access_token");

const complaintId =
new URLSearchParams(window.location.search).get("id");

async function loadComplaint(){

const response = await fetch(
`${API_BASE}/complaints/${complaintId}`,
{

headers:{
Authorization:`Bearer ${token}`
}

});

const c = await response.json();

document.getElementById("trackBox").innerHTML = `

<h3>${c.title}</h3>

<p><b>ID:</b> ${c.complaint_id}</p>

<p><b>Status:</b> ${c.status}</p>

<p><b>Department:</b> ${c.department}</p>

<p><b>Priority:</b> ${c.priority}</p>

<p><b>Summary:</b> ${c.summary}</p>

<hr>

<h3>Timeline</h3>

<p>✅ Submitted : ${c.created_at}</p>

<p>📌 Assigned : ${c.assigned_at || "Pending"}</p>

<p>🛠 In Progress : ${c.in_progress_at || "Pending"}</p>

<p>🎉 Resolved : ${c.resolved_at || "Pending"}</p>

`;

}

loadComplaint();