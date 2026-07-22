// ===============================
// Department Dashboard
// ===============================

const token = localStorage.getItem("access_token");

if (!token) {
    window.location.href = "login.html";
}

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

        document.getElementById("assignedCount").textContent =
            data.total || 0;

        document.getElementById("pendingCount").textContent =
            data.pending || 0;

        document.getElementById("progressCount").textContent =
            data.in_progress || 0;

        document.getElementById("resolvedCount").textContent =
            data.resolved || 0;

        document.getElementById("highPriorityCount").textContent =
            data.high_priority || 0;

        document.getElementById("departmentName").textContent =
            localStorage.getItem("department") || "Department";

        document.getElementById("welcomeDepartment").textContent =
            localStorage.getItem("department") || "Department";

    }

    catch (err) {

        console.log(err);

    }

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

        const tbody = document.getElementById("complaintsTable");

        tbody.innerHTML = "";

        if (complaints.length === 0) {

            tbody.innerHTML = `

            <tr>

                <td colspan="6">

                    No complaints assigned.

                </td>

            </tr>

            `;

            return;

        }

        complaints.forEach(c => {

            tbody.innerHTML += `

            <tr>

                <td>${c.complaint_id}</td>

                <td>${c.title}</td>

                <td>${c.priority}</td>

                <td>${c.status}</td>

                <td>${new Date(c.created_at).toLocaleDateString()}</td>

                <td>

                    <button
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