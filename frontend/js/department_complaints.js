function escHtml(v){return String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}
// ===============================
// Assigned Complaints (Full List)
// ===============================

const token = localStorage.getItem("access_token");

if (!token) {
    window.location.href = "login.html";
}

async function loadAllComplaints() {

    try {

        const response = await fetch(`${API_BASE}/department/complaints`, {
            headers: {
                Authorization: `Bearer ${token}`
            }
        });

        if (!response.ok) {
            alert("Session Expired");
            localStorage.clear();
            window.location.href = "login.html";
            return;
        }

        let complaints = await response.json();
        const requestedPriorities = new Set((new URLSearchParams(window.location.search).get("priority") || "")
            .split(",").map(value => value.trim().toLowerCase()).filter(Boolean));
        if (requestedPriorities.size) {
            complaints = complaints
                .filter(c => requestedPriorities.has(String(c.priority || "").toLowerCase()))
                .sort((a, b) => ({ Critical: 0, High: 1 }[a.priority] ?? 2) - ({ Critical: 0, High: 1 }[b.priority] ?? 2));
        }

        const tbody = document.getElementById("complaintsTable");

        tbody.innerHTML = "";

        if (complaints.length === 0) {

            tbody.innerHTML = `
            <tr>
                <td colspan="7">No complaints assigned.</td>
            </tr>
            `;

            return;
        }

        complaints.forEach(c => {

            tbody.innerHTML += `
            <tr>
                <td>${c.complaint_id}</td>
                <td>${escHtml(c.title)}</td>
                <td>${c.priority}</td>
                <td>${escHtml(c.display_status || c.status)}</td>
                <td>${escHtml(c.assignee || "Awaiting Officer")}</td>
                <td>${new Date(c.created_at).toLocaleDateString()}</td>
                <td>
                    <button class="view-btn" onclick="viewComplaint(${c.complaint_id})">
                        View
                    </button>
                </td>
            </tr>
            `;
        });

    } catch (err) {
        console.log(err);
    }
}

function viewComplaint(id) {
    window.location.href = `department_complaint_details.html?id=${id}`;
}

loadAllComplaints();
