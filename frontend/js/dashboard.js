// ================= USER =================

const userName = localStorage.getItem("name");

document.getElementById("userName").textContent = userName || "Citizen";
document.getElementById("welcomeName").textContent = userName || "Citizen";

// ================= LOGOUT =================

function logout() {

    localStorage.clear();

    window.location.href = "login.html";

}

document.getElementById("logoutBtn").addEventListener("click", logout);
document.getElementById("logoutSide").addEventListener("click", logout);

// ================= SIDEBAR =================

// const dashboardSection = document.getElementById("dashboardSection");
// const complaintSection = document.getElementById("complaintSection");
// const myComplaintSection = document.getElementById("myComplaintSection");
// const trackSection = document.getElementById("trackSection");
// const profileSection = document.getElementById("profileSection");

// function hideAllSections() {

//     dashboardSection.style.display = "none";
//     complaintSection.style.display = "none";
//     myComplaintSection.style.display = "none";
//     trackSection.style.display = "none";
//     profileSection.style.display = "none";

// }

// document.getElementById("dashboardMenu").onclick = () => {

//     hideAllSections();

//     dashboardSection.style.display = "block";

// };

// document.getElementById("lodgeMenu").onclick = () => {

//     hideAllSections();

//     complaintSection.style.display = "block";

// };

// document.getElementById("myComplaintMenu").onclick = () => {

//     hideAllSections();

//     myComplaintSection.style.display = "block";

// };

// document.getElementById("trackMenu").onclick = () => {

//     hideAllSections();

//     trackSection.style.display = "block";

// };

// document.getElementById("profileMenu").onclick = () => {

//     hideAllSections();

//     profileSection.style.display = "block";

// };



// ================= DASHBOARD STATS =================

async function loadDashboardStats() {

    try {

        const token = localStorage.getItem("access_token");

        const response = await fetch(`${API_BASE}/dashboard/stats`, {

            headers: {

                Authorization: `Bearer ${token}`

            }

        });

        const data = await response.json();

        document.getElementById("totalComplaints").textContent = data.total_complaints;
        document.getElementById("pendingComplaints").textContent = data.pending;
        document.getElementById("resolvedComplaints").textContent = data.resolved;
        document.getElementById("rejectedComplaints").textContent = data.rejected;

    }

    catch (error) {

        console.log(error);

    }

}

// ================= RECENT COMPLAINTS =================

async function loadComplaints() {

    try {

        const token = localStorage.getItem("access_token");

        const response = await fetch(`${API_BASE}/dashboard/recent-complaints`, {

            headers: {

                Authorization: `Bearer ${token}`

            }

        });

        const complaints = await response.json();

        const tbody = document.getElementById("recentComplaints");

        tbody.innerHTML = "";

        if (complaints.length === 0) {

            tbody.innerHTML = `
            <tr>
                <td colspan="5">
                    No complaints yet.
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

                <td>${c.department}</td>

                <td>${c.status}</td>

                <td>${c.priority}</td>

            </tr>
            `;

        });

    }

    catch (error) {

        console.log(error);

    }

}

// ================= START =================

loadDashboardStats();

loadComplaints();
