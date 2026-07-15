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

document.getElementById("complaintId").textContent=data.complaint_id;

document.getElementById("title").textContent=data.title;

document.getElementById("description").textContent=data.description;

document.getElementById("department").textContent=data.department;

document.getElementById("priority").textContent=data.priority;

document.getElementById("status").textContent=data.status;

document.getElementById("summary").textContent=data.summary;

document.getElementById("created").textContent=data.created_at;

document.getElementById("assigned").textContent=data.assigned_at || "Not Assigned";

document.getElementById("progress").textContent=data.in_progress_at || "Not Started";

document.getElementById("resolved").textContent=data.resolved_at || "Not Resolved";

}

document.getElementById("trackBtn").onclick=function(){

window.location.href=`track.html?id=${complaintId}`;

}

loadComplaint();