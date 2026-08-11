// const token = localStorage.getItem("access_token");

// const complaintId =
// new URLSearchParams(window.location.search).get("id");

// async function loadComplaint(){

// const response = await fetch(
// `${API_BASE}/complaints/${complaintId}`,
// {

// headers:{
// Authorization:`Bearer ${token}`
// }

// });

// const c = await response.json();

// document.getElementById("trackBox").innerHTML = `

// <h3>${c.title}</h3>

// <p><b>ID:</b> ${c.complaint_id}</p>

// <p><b>Status:</b> ${c.status}</p>

// <p><b>Department:</b> ${c.department}</p>

// <p><b>Priority:</b> ${c.priority}</p>

// <p><b>Summary:</b> ${c.summary}</p>

// <hr>

// <h3>Timeline</h3>

// <p>✅ Submitted : ${c.created_at}</p>

// <p>📌 Assigned : ${c.assigned_at || "Pending"}</p>

// <p>🛠 In Progress : ${c.in_progress_at || "Pending"}</p>

// <p>🎉 Resolved : ${c.resolved_at || "Pending"}</p>

// `;

// }

// loadComplaint();
const token = localStorage.getItem("access_token");

const complaintId =
    new URLSearchParams(window.location.search).get("id");


async function loadComplaint() {

    try {

        const response = await fetch(
            `${API_BASE}/complaints/${complaintId}`,
            {
                headers: {
                    Authorization: `Bearer ${token}`
                }
            }
        );

        if (!response.ok) {
            throw new Error("Unable to load complaint");
        }

        const c = await response.json();
        console.log("FULL COMPLAINT:", c);
console.log("FULL SUMMARY:", c.summary);
       

        document.getElementById("trackBox").innerHTML = `

            <!-- ================= COMPLAINT HEADER ================= -->

            <div class="complaint-top">

                <div>

                    <span class="complaint-label">
                        CIVICFLOW AI • COMPLAINT
                    </span>

                    <h1>${c.title}</h1>

                    <p class="complaint-id">
                        Complaint ID #${complaintId}
                    </p>

                </div>

                <div class="status-badge ${c.status?.toLowerCase()}">
                    <span class="status-dot"></span>
                    ${c.status}
                </div>

            </div>


            <!-- ================= DETAILS GRID ================= -->

            <div class="info-grid">

                <div class="info-card">

                    <div class="info-icon blue">
                        <i class="fa-solid fa-building"></i>
                    </div>

                    <div>
                        <span>Department</span>
                        <strong>${c.department}</strong>
                    </div>

                </div>


                <div class="info-card">

                    <div class="info-icon orange">
                        <i class="fa-solid fa-flag"></i>
                    </div>

                    <div>
                        <span>Priority</span>
                        <strong>${c.priority}</strong>
                    </div>

                </div>


                <div class="info-card">

                    <div class="info-icon cyan">
                        <i class="fa-solid fa-hashtag"></i>
                    </div>

                    <div>
                        <span>Complaint ID</span>
                        <strong>#${complaintId}</strong>
                    </div>

                </div>


                <div class="info-card">

                    <div class="info-icon green">
                        <i class="fa-solid fa-circle-check"></i>
                    </div>

                    <div>
                        <span>Current Status</span>
                        <strong>${c.status}</strong>
                    </div>

                </div>

            </div>


            <!-- ================= SUMMARY ================= -->

            <div class="summary-box">

                <div class="summary-heading">

                    <div class="summary-icon">
                        <i class="fa-solid fa-file-lines"></i>
                    </div>

                    <div>
                        <span>AI Generated Summary</span>
                        <h3>Complaint Overview</h3>
                    </div>

                </div>

                <p>
                    ${c.summary || "No summary available for this complaint."}
                </p>

            </div>


            <!-- ================= TIMELINE ================= -->

            <div class="tracking-section">

                <div class="tracking-heading">

                    <div>

                        <span class="section-eyebrow">
                            COMPLAINT JOURNEY
                        </span>

                        <h2>Track Your Complaint</h2>

                    </div>

                    <div class="tracking-line"></div>

                </div>


                <div class="timeline">


                    <div class="timeline-item completed">

                        <div class="timeline-marker">
                            <i class="fa-solid fa-check"></i>
                        </div>

                        <div class="timeline-content">

                            <div class="timeline-title">
                                Submitted
                                <span class="completed-label">
                                    Completed
                                </span>
                            </div>

                            <p>
                                Complaint was successfully submitted.
                            </p>

                            

                        </div>

                    </div>


                    <div class="timeline-item completed">

                        <div class="timeline-marker">
                            <i class="fa-solid fa-thumbtack"></i>
                        </div>

                        <div class="timeline-content">

                            <div class="timeline-title">
                                Assigned
                                <span class="completed-label">
                                    Completed
                                </span>
                            </div>

                            <p>
                                Complaint was assigned to the responsible department.
                            </p>

                            <time>
                                ${c.assigned_at || "Not available"}
                            </time>

                        </div>

                    </div>


                    <div class="timeline-item ${
                        c.status === "In Progress" ||
                        c.status === "Resolved"
                            ? "completed"
                            : "active"
                    }">

                        <div class="timeline-marker">
                            <i class="fa-solid fa-screwdriver-wrench"></i>
                        </div>

                        <div class="timeline-content">

                            <div class="timeline-title">
                                In Progress

                                ${
                                    c.status === "In Progress" ||
                                    c.status === "Resolved"
                                        ? `<span class="completed-label">Completed</span>`
                                        : `<span class="active-label">Current</span>`
                                }

                            </div>

                            <p>
                                Department is working on the complaint.
                            </p>

                            <time>
                                ${c.in_progress_at || "Not available"}
                            </time>

                        </div>

                    </div>


                    <div class="timeline-item ${
                        c.status === "Resolved"
                            ? "completed"
                            : "pending"
                    }">

                        <div class="timeline-marker">
                            <i class="fa-solid fa-circle-check"></i>
                        </div>

                        <div class="timeline-content">

                            <div class="timeline-title">

                                Resolved

                                ${
                                    c.status === "Resolved"
                                        ? `<span class="completed-label">Completed</span>`
                                        : `<span class="pending-label">Pending</span>`
                                }

                            </div>

                            <p>
                                Complaint will appear here once it has been resolved.
                            </p>

                            <time>
                                ${c.resolved_at || "Not resolved yet "}
                            </time>

                        </div>

                    </div>


                </div>

            </div>

        `;

    }

    catch (error) {

        console.error(error);

        document.getElementById("trackBox").innerHTML = `

            <div class="error-box">

                <i class="fa-solid fa-triangle-exclamation"></i>

                <h3>Unable to Load Complaint</h3>

                <p>
                    We couldn't retrieve the complaint details.
                    Please try again.
                </p>

            </div>

        `;

    }

}


loadComplaint();