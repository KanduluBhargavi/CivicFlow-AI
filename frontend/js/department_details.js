const token = localStorage.getItem("access_token");

if (!token) {

    window.location.href = "login.html";

}

const params = new URLSearchParams(window.location.search);

const complaintId = params.get("id");

// ===============================
// Load Complaint
// ===============================

async function loadComplaint() {

    try {

        const response = await fetch(

            `${API_BASE}/department/complaint/${complaintId}`,

            {

                headers: {

                    Authorization: `Bearer ${token}`

                }

            }

        );

        if (!response.ok) {

            alert("Unable to load complaint.");

            return;

        }

        const c = await response.json();

        document.getElementById("complaintId").textContent =
            c.complaint_id;

        document.getElementById("title").textContent =
            c.title;

        document.getElementById("description").textContent =
            c.description;

        document.getElementById("summary").textContent =
            c.ai_summary || "No AI Summary";

        document.getElementById("state").textContent =
            c.state;

        document.getElementById("district").textContent =
            c.district;

        document.getElementById("area").textContent =
            c.area;

        document.getElementById("address").textContent =
            c.address;

        document.getElementById("landmark").textContent =
            c.landmark || "-";

        document.getElementById("pincode").textContent =
            c.pincode;

        document.getElementById("createdAt").textContent =
            new Date(c.created_at).toLocaleString();

        document.getElementById("assignedAt").textContent =
            c.assigned_at
            ? new Date(c.assigned_at).toLocaleString()
            : "-";

        document.getElementById("progressAt").textContent =
            c.in_progress_at
            ? new Date(c.in_progress_at).toLocaleString()
            : "-";

        document.getElementById("resolvedAt").textContent =
            c.resolved_at
            ? new Date(c.resolved_at).toLocaleString()
            : "-";

        // ===========================
        // Priority Badge
        // ===========================

        const priority = document.getElementById("priority");

        priority.textContent = c.priority;

        if (c.priority === "High") {

            priority.classList.add("high");

        }

        else if (c.priority === "Medium") {

            priority.classList.add("medium");

        }

        else {

            priority.classList.add("low");

        }

        // ===========================
        // Status Badge
        // ===========================

        const status = document.getElementById("status");

        status.textContent = c.status;

        if (c.status === "Assigned") {

            status.classList.add("assigned");

        }

        else if (c.status === "In Progress") {

            status.classList.add("progress");

        }

        else {

            status.classList.add("resolved");

        }

        document.getElementById("newStatus").value =
            c.status;

        // ===========================
        // Media
        // ===========================

        const media =
            document.getElementById("mediaContainer");

        if (c.media_url) {

            const extension =
                c.media_url.split(".").pop().toLowerCase();

            if (

                extension === "jpg" ||

                extension === "jpeg" ||

                extension === "png"

            ) {

                media.innerHTML = `

                <img
                src="${API_BASE}/${c.media_url}">

                `;

            }

            else {

                media.innerHTML = `

                <video controls>

                <source
                src="${API_BASE}/${c.media_url}">

                </video>

                `;

            }

        }

        else {

            media.innerHTML =
                "<p>No Media Uploaded.</p>";

        }

    }

    catch (err) {

        console.log(err);

    }

}

// ===============================
// Update Status
// ===============================

document.getElementById("updateStatusBtn")

.addEventListener("click",

async function () {

    const status =

    document.getElementById("newStatus").value;

    const response = await fetch(

        `${API_BASE}/department/update-status/${complaintId}`,

        {

            method: "PUT",

            headers: {

                Authorization: `Bearer ${token}`,

                "Content-Type": "application/json"

            },

            body: JSON.stringify({

                status: status

            })

        }

    );

    const data = await response.json();

    alert(data.message);

    loadComplaint();

});

loadComplaint();