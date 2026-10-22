const token = localStorage.getItem("access_token");

if (!token) {
    window.location.href = "login.html";
}

// Load Profile

async function loadProfile() {

    const response = await fetch(`${API_BASE}/department/profile`, {
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

    const data = await response.json();

    const isOfficer = data.viewer_role === "officer";
    document.getElementById("profileTitle").textContent = isOfficer ? "Officer Profile" : "Department Profile";
    document.getElementById("profileForm").style.display = isOfficer ? "none" : "block";
    document.getElementById("officerProfile").style.display = isOfficer ? "block" : "none";

    if (isOfficer) {
        document.getElementById("officer_name").value = data.officer_name || data.viewer_name || "";
        document.getElementById("officer_email").value = data.officer_email || "";
        document.getElementById("officer_department").value = data.department_name || "";
        document.getElementById("officer_jurisdiction").value = [data.district, data.state].filter(Boolean).join(", ") || "Not specified";
        document.getElementById("officer_specialization").value = data.specialization || "General";
        document.getElementById("officer_workload").value = `${data.active_cases || 0} active / ${data.max_active_cases || 20} capacity`;
    } else {
        document.getElementById("department_name").value = data.department_name;
        document.getElementById("department_email").value = data.department_email;
        document.getElementById("username").value = data.username;
        document.getElementById("description").value = data.description || "";
    }
}

// Update Profile

document.getElementById("profileForm")
.addEventListener("submit", async (e) => {

    e.preventDefault();

    const response = await fetch(`${API_BASE}/department/profile`, {
        method: "PUT",
        headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            department_name: document.getElementById("department_name").value,
            description: document.getElementById("description").value
        })
    });

    const data = await response.json();

    alert(data.message || data.detail);

    localStorage.setItem("department", document.getElementById("department_name").value);
});

// Change Password

document.getElementById("passwordForm")
.addEventListener("submit", async (e) => {

    e.preventDefault();

    const response = await fetch(`${API_BASE}/department/change-password`, {
        method: "PUT",
        headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            old_password: document.getElementById("oldPassword").value,
            new_password: document.getElementById("newPassword").value
        })
    });

    const data = await response.json();

    alert(data.message || data.detail);

    document.getElementById("passwordForm").reset();
});

loadProfile();
